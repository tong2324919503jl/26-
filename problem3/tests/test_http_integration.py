"""Full policy + CLI + HTTP regression on isolated synthetic development cases.

The server below is a small localhost test mirror, not the official simulator.
It exposes only the four public response shapes and never reveals source truth.
All child-process outputs are isolated in temporary directories.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from problem3.scenarios import generate_case
from problem3.simulator import LocalSimulator, SimulationLimit


ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def public_http_mirror(case):
    simulator = LocalSimulator(case)
    state = {'requests': [], 'responses': [], 'cache': {}, 'active': 0,
             'maximum_active': 0, 'handler_errors': []}
    state_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            counting = True
            with state_lock:
                state['active'] += 1
                state['maximum_active'] = max(state['maximum_active'], state['active'])
            try:
                raw = self.rfile.read(int(self.headers['Content-Length']))
                payload = json.loads(raw)
                state['requests'].append((self.path, payload))
                request_id = payload['request_id']
                status = 200
                rejected = dict(accepted=False, real_timestamp_ms=0, virtual_time_s=0)
                if self.path not in {'/enter', '/measure', '/clear', '/exit'}:
                    status, result = 404, rejected
                elif payload.get('robot_id') != 'local-test' or payload.get('arena_id') != 'default':
                    result = rejected
                elif request_id in state['cache']:
                    prior_path, prior_raw, prior_result = state['cache'][request_id]
                    if (self.path, raw) != (prior_path, prior_raw):
                        status, result = 409, rejected
                    else:
                        result = prior_result
                else:
                    try:
                        if self.path in {'/enter', '/exit'}:
                            result = getattr(simulator, self.path[1:])()
                        else:
                            point = payload['position']
                            result = getattr(simulator, self.path[1:])((point['x'], point['y']), payload['channel'])
                    except SimulationLimit:
                        result = rejected
                    if result['accepted'] is True:
                        state['cache'][request_id] = self.path, raw, result
                state['responses'].append((self.path, result))
                # A next serial request may arrive as soon as its predecessor's
                # response body reaches the child process, before this handler
                # returns. Count overlapping action execution, not that harmless
                # handler cleanup interval; the JSONL assertions verify the full
                # request/response order independently below.
                with state_lock:
                    state['active'] -= 1
                    counting = False
                data = json.dumps(result).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as error:
                state['handler_errors'].append(repr(error))
                raise
            finally:
                if counting:
                    with state_lock:
                        state['active'] -= 1

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', simulator, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


class HttpEndToEndTests(unittest.TestCase):
    def run_problem(self, problem, index):
        # Short reception radii and fixed extreme errors; P4 additionally has
        # outward-facing boundary sources. These are development cases only.
        case = generate_case(problem, index, 'development')
        self.assertTrue(10 <= len(case['sources']) <= 16)
        with tempfile.TemporaryDirectory(prefix=f'p{problem}_http_test_') as folder:
            destination = Path(folder)
            with public_http_mirror(case) as (base_url, simulator, state):
                environment = dict(os.environ, PYTHONIOENCODING='utf-8')
                process = subprocess.run(
                    [sys.executable, str(ROOT/f'problem{problem}/solve.py'), '--online',
                     '--robot-id', 'local-test', '--base-url', base_url,
                     '--output-dir', str(destination/'outputs')],
                    cwd=destination, capture_output=True, text=True, encoding='utf-8',
                    env=environment, timeout=60)
            self.assertEqual(process.returncode, 0, process.stdout+'\n'+process.stderr)
            self.assertEqual(state['handler_errors'], [])
            self.assertEqual(state['maximum_active'], 1)
            self.assertEqual(len(simulator.cleared), len(case['sources']))
            self.assertFalse(simulator.active)
            self.assertEqual(state['requests'][0][0], '/enter')
            self.assertEqual(state['requests'][-1][0], '/exit')
            ids = [payload['request_id'] for _, payload in state['requests']]
            self.assertEqual(len(ids), len(set(ids)), 'Stable local transport should need no retries')
            for path, response in state['responses']:
                self.assertTrue(response['accepted'], (path, response))
                self.assertFalse({'sources', 'source_count', 'radius', 'orientation_deg'} & set(response))
            summaries = list((destination/'outputs/online').glob('*_summary.json'))
            self.assertEqual(len(summaries), 1)
            summary = json.loads(summaries[0].read_text(encoding='utf-8'))
            self.assertTrue(summary['entered'])
            self.assertTrue(summary['exit_accepted'])
            self.assertTrue(summary['statistics_final'])
            self.assertIsNone(summary['error'])
            self.assertIsNone(summary['source_count'])
            self.assertIsNone(summary['cleared_fraction'])
            self.assertIsNone(summary['platform_case_code'])
            self.assertIsNone(summary['platform_program_runtime_s'])
            self.assertEqual(summary['cleared_count'], len(case['sources']))
            self.assertAlmostEqual(summary['virtual_time_s'], simulator.virtual_time_s, places=5)
            self.assertTrue(summary['policy']['completion_certified'])
            logs = list((destination/'outputs/online').glob('*_client_trace.jsonl'))
            self.assertEqual(len(logs), 1)
            records = [json.loads(line) for line in logs[0].read_text(encoding='utf-8').splitlines()]
            flow = [record for record in records if record['event'] != 'client_created']
            self.assertEqual(len(flow), 2*len(state['requests']))
            for request, response in zip(flow[::2], flow[1::2]):
                self.assertEqual(request['event'], 'request')
                self.assertEqual(response['event'], 'response')
                self.assertEqual(request['payload']['request_id'], response['request_id'])
                self.assertEqual(request['path'], response['path'])

    def test_problem3_full_online_cli_on_local_synthetic_http(self):
        self.run_problem(3, 18)

    def test_problem4_full_online_cli_on_local_synthetic_http(self):
        self.run_problem(4, 19)


if __name__ == '__main__':
    unittest.main()
