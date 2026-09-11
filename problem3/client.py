"""Serial HTTP client for attachment 2; construction never contacts the simulator."""

from __future__ import annotations

import http.client
import json
import math
import threading
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener


class ClientError(RuntimeError):
    """The client cannot safely treat an action as successful."""


class BudgetExceeded(ClientError):
    """The remaining time must be reserved for leaving the simulator."""


class ProtocolError(ClientError):
    """HTTP or JSON does not satisfy the published protocol."""


class TransportError(ClientError):
    """An action has an unknown outcome; only the identical action may be retried."""


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_body(response):
    body = response.read(1048577)
    length = response.headers.get("Content-Length")
    if length is not None and length.isdigit() and len(body) < min(int(length), 1048577):
        raise http.client.IncompleteRead(body, int(length) - len(body))
    return body


class HttpClient:
    """Send one action at a time and preserve a separate, non-overwritten JSONL log.

    Accepted business responses are returned unchanged. A normal rejected response
    is also returned unchanged: callers must require ``accepted is True``. Errors
    raise ClientError. If a response is lost, retries reuse the exact request bytes.
    After an unresolved outcome, retry_pending() is the only allowed network action.
    """

    def __init__(self, base_url, robot_id, log_path, *, timeout_s=5.0,
                 max_retries=2, retry_delay_s=0.2, exit_reserve_s=5.0,
                 clock=time.monotonic, sleep=time.sleep):
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                or parsed.username or parsed.password):
            raise ValueError("Simulator base_url must be a local HTTP origin, e.g. http://127.0.0.1:2026")
        if (not isinstance(robot_id, str) or not 1 <= len(robot_id.encode("utf-8")) <= 64
                or any(unicodedata.category(c) in {"Cc", "Cf"} for c in robot_id)):
            raise ValueError("robot_id must be the exact team ID, 1..64 UTF-8 bytes, without control/format characters")
        if (not _number(timeout_s) or timeout_s <= 0 or not _number(exit_reserve_s)
                or exit_reserve_s < 0 or not _number(retry_delay_s) or retry_delay_s < 0
                or not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 0):
            raise ValueError("Invalid timeout, retry count, delay, or exit reserve")
        self.base_url = base_url.rstrip("/")
        self.robot_id = robot_id
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"event": "client_created", "base_url": self.base_url,
                                     "created_utc": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False) + "\n")
        self.timeout_s = float(timeout_s)
        self.max_retries = max_retries
        self.retry_delay_s = float(retry_delay_s)
        self.exit_reserve_s = float(exit_reserve_s)
        self._clock, self._sleep = clock, sleep
        # The official simulator is local-only. System proxy settings must not
        # forward team IDs or robot actions through an unrelated proxy server.
        self._opener = build_opener(ProxyHandler({}))
        self._lock = threading.RLock()
        self._pending = None
        self._deadline = None
        self._entered = False
        self._exited = False
        self.position = (0.0, 0.0)
        self.current_channel = 1
        self.virtual_time_s = 0.0
        self.max_virtual_duration_s = 360000.0
        self.remaining_real_duration_s = None

    @property
    def pending_request(self):
        """A copy of an unresolved action for diagnostics; never mutate/reissue it."""
        with self._lock:
            return None if self._pending is None else json.loads(self._pending[2].decode("utf-8"))

    @property
    def can_exit(self):
        with self._lock:
            return (self._entered and not self._exited and self._pending is None
                    and self._deadline is not None and self._clock() < self._deadline)

    def check_budget(self, virtual_cost_s=0.0):
        """Return usable real seconds, raising before spending the exit reserve.

        Use the /enter remaining time, conservatively counted from the first send
        (including lost-response retry time), rather than assuming 1200 seconds.
        """
        with self._lock:
            self._require_active()
            if not _number(virtual_cost_s) or virtual_cost_s < 0:
                raise ValueError("virtual_cost_s must be finite and nonnegative")
            usable = self._deadline - self._clock() - self.exit_reserve_s
            if usable <= 0:
                raise BudgetExceeded("Real-time budget reached; reserve remaining time for /exit")
            if self.virtual_time_s + virtual_cost_s >= self.max_virtual_duration_s:
                raise BudgetExceeded("Virtual-time budget reached")
            return usable

    def enter(self):
        with self._lock:
            if self._entered or self._exited:
                raise ClientError("This client already entered a test; do not start it again")
            return self._new_action("/enter")

    def measure(self, point, channel):
        return self._located_action("/measure", point, channel)

    def clear(self, point, channel):
        return self._located_action("/clear", point, channel)

    def exit(self):
        with self._lock:
            self._require_active()
            if self._clock() >= self._deadline:
                raise BudgetExceeded("Test deadline has passed; inspect the simulator, do not probe /exit")
            return self._new_action("/exit")

    def retry_pending(self):
        """Retry an unresolved request with its original path, ID and exact bytes."""
        with self._lock:
            if self._pending is None:
                raise ClientError("There is no unresolved request")
            return self._send_pending()

    def _require_active(self):
        if not self._entered or self._exited:
            raise ClientError("Call /enter successfully before actions; ended tests cannot resume")

    def _located_action(self, path, point, channel):
        with self._lock:
            self._require_active()
            if (not isinstance(point, (tuple, list)) or len(point) != 2
                    or any(not _number(x) or abs(x) > 2000000 for x in point)):
                raise ValueError("position must have two finite coordinates within +/-2000000 m")
            if not isinstance(channel, int) or isinstance(channel, bool) or not 1 <= channel <= 20:
                raise ValueError("channel must be an integer in 1..20")
            cost = math.dist(self.position, point) / 5 + 5
            if path == "/measure" and channel != self.current_channel:
                cost += 1
            self.check_budget(cost)
            return self._new_action(path, {"position": {"x": point[0], "y": point[1]}, "channel": channel})

    def _new_action(self, path, fields=None):
        if self._pending is not None:
            raise TransportError("Previous outcome unresolved: use retry_pending(), do not send another action")
        payload = {"arena_id": "default", "robot_id": self.robot_id,
                   "request_id": path[1:] + "-" + uuid.uuid4().hex}
        payload.update(fields or {})
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self._pending = (path, payload, raw, self._clock())
        return self._send_pending()

    def _log(self, event, **fields):
        record = {"event": event, "recorded_utc": datetime.now(timezone.utc).isoformat(), **fields}
        with self.log_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")

    def _send_pending(self):
        path, payload, raw, started = self._pending
        for attempt in range(self.max_retries + 1):
            timeout = self.timeout_s
            if self._deadline is not None:
                # Retry the same possibly executed action even inside the reserve,
                # but never intentionally send after the actual test deadline.
                timeout = min(timeout, self._deadline - self._clock())
                if timeout <= 0:
                    raise BudgetExceeded("Deadline passed with an unresolved action; inspect simulator status")
            self._log("request", path=path, payload=payload, attempt=attempt)
            request = Request(self.base_url + path, data=raw,
                              headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
            try:
                try:
                    with self._opener.open(request, timeout=timeout) as response:
                        status, body = response.status, _read_body(response)
                except HTTPError as error:
                    with error:
                        status, body = error.code, _read_body(error)
            except (URLError, OSError, http.client.HTTPException) as error:
                self._log("transport_error", path=path, request_id=payload["request_id"], error=str(error))
                if attempt == self.max_retries:
                    raise TransportError("No complete response; action outcome unknown. Use retry_pending() with the same client") from error
                delay = self.retry_delay_s * (2 ** attempt)
                if self._deadline is not None:
                    delay = min(delay, max(0, self._deadline - self._clock()))
                self._sleep(delay)
                continue
            try:
                if len(body) > 1048576:
                    raise ValueError("Response exceeds 1 MiB")
                result = json.loads(body.decode("utf-8"), object_pairs_hook=_json_object)
                self._validate_response(path, result)
            except (ValueError, TypeError, KeyError) as error:
                self._log("protocol_error", path=path, http_status=status, error=str(error))
                raise ProtocolError("Malformed/unknown response; action outcome unresolved") from error
            self._log("response", path=path, request_id=payload["request_id"], http_status=status, response=result)
            if status != 200:
                if result["accepted"] is False:
                    self._pending = None
                raise ProtocolError(f"HTTP {status}; action not confirmed. Response: {result}")
            if result["accepted"] is True:
                self.virtual_time_s = float(result["virtual_time_s"])
                if path == "/enter":
                    self._entered = True
                    self.position, self.current_channel = (0.0, 0.0), 1
                    self.max_virtual_duration_s = float(result["max_virtual_duration_s"])
                    self.remaining_real_duration_s = int(result["remaining_real_duration_s"])
                    self._deadline = started + self.remaining_real_duration_s
                elif path in {"/measure", "/clear"}:
                    self.position = (float(payload["position"]["x"]), float(payload["position"]["y"]))
                    if path == "/measure":
                        self.current_channel = payload["channel"]
                elif path == "/exit":
                    self._exited = True
            self._pending = None
            return result

    def _validate_response(self, path, result):
        if not isinstance(result, dict) or type(result.get("accepted")) is not bool:
            raise ValueError("accepted must be boolean")
        for name in ("real_timestamp_ms", "virtual_time_s"):
            if not _number(result.get(name)) or result[name] < 0:
                raise ValueError(f"Invalid {name}")
        if result["accepted"] is False:
            return
        if result["virtual_time_s"] < self.virtual_time_s:
            raise ValueError("Accepted virtual time moved backwards")
        if path == "/enter":
            for name in ("max_virtual_duration_s", "max_real_duration_s", "remaining_real_duration_s"):
                if not _number(result.get(name)) or result[name] < 0:
                    raise ValueError(f"Missing/invalid {name}")
            remaining = result["remaining_real_duration_s"]
            if remaining != int(remaining) or remaining > 1200 or result["max_virtual_duration_s"] <= 0:
                raise ValueError("Invalid time limits")
        elif path == "/measure":
            if result.get("measure_result") not in {"no_signal", "near", "direction"}:
                raise ValueError("Unknown measure_result")
            if result["measure_result"] == "direction" and (
                    not _number(result.get("svd_deg")) or not 0 <= result["svd_deg"] < 360):
                raise ValueError("Invalid svd_deg")
        elif path == "/clear" and result.get("clear_result") not in {"success", "no_target_in_range"}:
            raise ValueError("Unknown clear_result")
        elif path == "/exit" and result.get("exit_reason") != "user_exit":
            raise ValueError("Unknown exit_reason")
