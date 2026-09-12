"""Run the current solve default with public replies only, in a local worker."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_teammate_p34_worker import PublicProxy, protect, receive, send


def main():
    root = Path(sys.argv[1]).resolve()
    problem = int(sys.argv[2])
    if problem not in (3, 4):
        raise ValueError('problem must be 3 or 4')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    # Load the installed numerical runtime before the native-call audit guard.
    # Policy construction and every subsequent action still run under protect().
    if problem == 4:
        import numpy
    protect(root)
    from scripts.benchmark_search import get_algorithm_version, get_policy

    version = get_algorithm_version(problem, 'adaptive')
    imports = {
        name: str(Path(module.__file__).resolve())
        for name, module in list(sys.modules.items())
        if name.startswith(('problem3', 'problem4', 'scripts.benchmark_search'))
        and getattr(module, '__file__', None)
    }
    if any(not Path(path).is_relative_to(root) for path in imports.values()):
        raise RuntimeError('Policy imports escaped the repository')
    send({'type': 'ready', 'implementation': 'current_solve', 'problem': problem,
          'strategy': 'adaptive', 'algorithm_version': version, 'imports': imports,
          'imports_sha256': {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                             for name, path in imports.items()}})
    while True:
        command = receive()
        if command.get('type') == 'stop':
            return
        if command != {'type': 'run'}:
            raise ValueError('Only a run token is accepted; no case data')
        proxy = PublicProxy()
        started, cpu = time.perf_counter(), time.process_time()
        result, error = {}, None
        try:
            proxy.enter()
            policy = get_policy(problem, 'adaptive')
            result = policy.run(proxy)
            result['algorithm_version'] = version
            proxy.exit()
        except BaseException as exc:
            error = f'{type(exc).__name__}: {exc}'
            traceback.print_exc(file=sys.stderr)
        normal_exit = proxy.exited
        if proxy.entered and not proxy.exited:
            try:
                proxy.exit()
            except Exception:
                pass
        send({'type': 'result', 'policy': result, 'error': error,
              'normal_exit': normal_exit, 'exited': proxy.exited,
              'policy_cpu_s': time.process_time() - cpu,
              'policy_wall_s': time.perf_counter() - started})


if __name__ == '__main__':
    main()
