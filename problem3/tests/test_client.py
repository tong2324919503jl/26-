"""Protocol tests use an in-process mock; they never contact the official platform."""

import json
import math
import socket
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from problem3.client import BudgetExceeded, ClientError, HttpClient, ProtocolError, TransportError


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


@contextmanager
def mock_simulator(*, remaining=1200, drop_path=None, reject_path=None,
                   unknown_path=None, http_error_path=None, on_drop=None, partial_path=None):
    state = {"requests": [], "cache": {}, "executed": [], "position": (0, 0),
             "channel": 1, "virtual_time": 0.0, "dropped": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            payload = json.loads(raw)
            key = payload["request_id"]
            state["requests"].append((self.path, raw))
            status = 200
            if key in state["cache"]:
                response = state["cache"][key]
            elif self.path == reject_path or self.path == http_error_path:
                response = {"accepted": False, "real_timestamp_ms": 1000, "virtual_time_s": 0}
                status = 400 if self.path == http_error_path else 200
            else:
                state["executed"].append(self.path)
                response = {"accepted": True, "real_timestamp_ms": 1000, "virtual_time_s": state["virtual_time"]}
                if self.path == "/enter":
                    response.update(max_virtual_duration_s=360000, max_real_duration_s=1200,
                                    remaining_real_duration_s=remaining)
                elif self.path in {"/measure", "/clear"}:
                    point = (payload["position"]["x"], payload["position"]["y"])
                    state["virtual_time"] += math.dist(point, state["position"]) / 5
                    state["position"] = point
                    if self.path == "/measure":
                        state["virtual_time"] += 5 + (payload["channel"] != state["channel"])
                        state["channel"] = payload["channel"]
                        response.update(measure_result="direction", svd_deg=123.45)
                    else:
                        state["virtual_time"] += 3
                        response.update(clear_result="no_target_in_range")
                    response["virtual_time_s"] = state["virtual_time"]
                elif self.path == "/exit":
                    response["exit_reason"] = "user_exit"
                if self.path == unknown_path:
                    response["measure_result"] = "unexpected"
                state["cache"][key] = response
            if self.path == drop_path and not state["dropped"]:
                state["dropped"] = True
                if on_drop:
                    on_drop()
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            data = json.dumps(response).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.path == partial_path and not state["dropped"]:
                state["dropped"] = True
                self.wfile.write(data[:len(data) // 2])
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.log = Path(self.directory.name) / "session.jsonl"

    def make_client(self, url, **kwargs):
        return HttpClient(url, "team-123", self.log, retry_delay_s=0, **kwargs)

    def test_protocol_timing_example_and_clear_does_not_switch_channel(self):
        with mock_simulator() as (url, _):
            client = self.make_client(url)
            self.assertTrue(client.enter()["accepted"])
            self.assertEqual(client.measure((300, 400), 1)["virtual_time_s"], 105)
            self.assertEqual(client.measure((300, 400), 2)["virtual_time_s"], 111)
            self.assertEqual(client.clear((300, 0), 3)["virtual_time_s"], 194)
            self.assertEqual(client.current_channel, 2)
            self.assertEqual(client.position, (300.0, 0.0))
            self.assertEqual(client.measure((300, 0), 2)["virtual_time_s"], 199)
            self.assertEqual(client.exit()["exit_reason"], "user_exit")
            self.assertFalse(client.can_exit)

    def test_accepted_but_lost_response_reuses_identical_request(self):
        with mock_simulator(drop_path="/measure") as (url, state):
            client = self.make_client(url)
            client.enter()
            result = client.measure((300, 400), 2)
            self.assertEqual(result["virtual_time_s"], 106)
            requests = [r for r in state["requests"] if r[0] == "/measure"]
            self.assertEqual(len(requests), 2)
            self.assertEqual(requests[0], requests[1])
            self.assertEqual(state["executed"].count("/measure"), 1)
            self.assertEqual(client.virtual_time_s, 106.0)

    def test_exhausted_retry_keeps_pending_and_blocks_new_action(self):
        with mock_simulator(drop_path="/measure") as (url, state):
            client = self.make_client(url, max_retries=0)
            client.enter()
            with self.assertRaises(TransportError):
                client.measure((30, 0), 1)
            original = client.pending_request
            self.assertFalse(client.can_exit)
            with self.assertRaises(TransportError):
                client.clear((30, 0), 1)
            with self.assertRaises(TransportError):
                client.exit()
            self.assertEqual(client.retry_pending()["virtual_time_s"], 11)
            self.assertIsNone(client.pending_request)
            self.assertEqual(json.loads(state["requests"][-1][1]), original)
            self.assertEqual(state["executed"].count("/measure"), 1)

    def test_truncated_response_is_retried_as_the_same_action(self):
        with mock_simulator(partial_path="/clear") as (url, state):
            client = self.make_client(url)
            client.enter()
            self.assertEqual(client.clear((30, 0), 1)["clear_result"], "no_target_in_range")
            self.assertEqual(client.virtual_time_s, 9)
            self.assertEqual(state["executed"].count("/clear"), 1)
            requests = [r for r in state["requests"] if r[0] == "/clear"]
            self.assertEqual(requests[0], requests[1])

    def test_rejection_zero_does_not_reset_accepted_state(self):
        with mock_simulator(reject_path="/clear") as (url, _):
            client = self.make_client(url)
            client.enter()
            client.measure((12, 1), 2)
            before = (client.virtual_time_s, client.position, client.current_channel)
            self.assertFalse(client.clear((300, 400), 5)["accepted"])
            self.assertEqual((client.virtual_time_s, client.position, client.current_channel), before)

    def test_http_error_is_not_an_accepted_action(self):
        with mock_simulator(http_error_path="/measure") as (url, _):
            client = self.make_client(url)
            client.enter()
            with self.assertRaises(ProtocolError):
                client.measure((100, 100), 2)
            self.assertEqual(client.virtual_time_s, 0)
            self.assertEqual(client.position, (0, 0))
            self.assertIsNone(client.pending_request)

    def test_unknown_result_is_not_silently_no_signal(self):
        with mock_simulator(unknown_path="/measure") as (url, _):
            client = self.make_client(url)
            client.enter()
            with self.assertRaises(ProtocolError):
                client.measure((0, 0), 1)
            self.assertEqual(client.virtual_time_s, 0)
            self.assertIsNotNone(client.pending_request)

    def test_remaining_duration_and_exit_reserve(self):
        clock = FakeClock()
        with mock_simulator(remaining=13) as (url, state):
            client = self.make_client(url, clock=clock, exit_reserve_s=5)
            client.enter()
            self.assertEqual(client.check_budget(), 8)
            clock.now += 8
            with self.assertRaises(BudgetExceeded):
                client.measure((0, 0), 1)
            self.assertEqual(state["executed"], ["/enter"])
            self.assertTrue(client.can_exit)
            self.assertTrue(client.exit()["accepted"])

    def test_enter_lost_response_does_not_extend_deadline(self):
        clock = FakeClock()
        with mock_simulator(remaining=20, drop_path="/enter",
                            on_drop=lambda: setattr(clock, "now", clock.now + 7)) as (url, _):
            client = self.make_client(url, clock=clock)
            client.enter()
            self.assertEqual(client.check_budget(), 8)

    def test_zero_budget_does_not_probe_exit(self):
        with mock_simulator(remaining=0) as (url, state):
            client = self.make_client(url)
            client.enter()
            self.assertFalse(client.can_exit)
            with self.assertRaises(BudgetExceeded):
                client.exit()
            self.assertEqual(state["executed"], ["/enter"])

    def test_no_overwrite_of_existing_log(self):
        self.log.write_text("original\n", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.make_client("http://127.0.0.1:2026")
        self.assertEqual(self.log.read_text(encoding="utf-8"), "original\n")

    def test_invalid_input_is_rejected_before_network(self):
        with mock_simulator() as (url, state):
            client = self.make_client(url)
            with self.assertRaises(ClientError):
                client.measure((0, 0), 1)
            client.enter()
            for point, channel in [((float("nan"), 0), 1), ((2000001, 0), 1), ((0, 0), True), ((0, 0), 21)]:
                with self.assertRaises(ValueError):
                    client.measure(point, channel)
            self.assertEqual(state["executed"], ["/enter"])

    def test_concurrent_callers_are_serialized_and_ids_are_new(self):
        with mock_simulator() as (url, state):
            client = self.make_client(url)
            client.enter()
            errors = []
            def worker(channel):
                try:
                    client.measure((0, 0), channel)
                except Exception as error:
                    errors.append(error)
            threads = [threading.Thread(target=worker, args=(channel,)) for channel in range(1, 6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=3)
            self.assertEqual(errors, [])
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            ids = [json.loads(raw)["request_id"] for _, raw in state["requests"]]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(client.virtual_time_s, state["virtual_time"])


if __name__ == "__main__":
    unittest.main()
