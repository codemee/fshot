"""Compare instrumented packaged builds with alternating startup runs."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', action='append', required=True, type=Path)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--output', type=Path, default=Path('build/startup-benchmark'))
    args = parser.parse_args()
    if args.runs < 1 or args.timeout <= 0:
        parser.error('runs and timeout must be positive')
    executables = [path.resolve(strict=True) for path in args.exe]
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for run in range(args.runs):
        order = list(enumerate(executables))
        if run % 2:
            order.reverse()
        for index, executable in order:
            trace = (args.output / f'build-{index + 1}-run-{run + 1}.jsonl').resolve()
            trace.write_text('', encoding='utf-8')
            env = os.environ.copy()
            env['FSHOT_STARTUP_TRACE'] = str(trace)
            with tempfile.TemporaryDirectory(prefix='fshot-startup-cwd-') as cwd:
                env['FSHOT_STARTUP_STARTED_NS'] = str(time.perf_counter_ns())
                process = subprocess.Popen([str(executable), '--startup-probe'], cwd=cwd, env=env)
                try:
                    code = process.wait(timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                       capture_output=True, timeout=15)
                    else:
                        process.kill()
                    process.wait(timeout=15)
                    raise RuntimeError(f'Startup timed out: {executable}; inspect {trace}')
            events = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
            times = {event['event']: event['elapsed_ms'] for event in events}
            if code != 0 or 'event_loop_ready' not in times:
                raise RuntimeError(f'Startup failed ({code}): {executable}; inspect {trace}')
            results.append({'executable': str(executable), 'run': run + 1, 'events_ms': times})
            (args.output / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
            print(f'{executable.name} run {run + 1}: {times}', flush=True)
    for executable in executables:
        samples = [row['events_ms']['event_loop_ready'] for row in results if row['executable'] == str(executable)]
        print(f'{executable}: event_loop_ready median {statistics.median(samples):.1f} ms ({len(samples)} runs)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
