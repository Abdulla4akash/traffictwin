"""Launch exactly one serial worker per trace; no retries or scientific imports."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['qualify', 'run'])
    args = parser.parse_args()
    design = json.loads((HERE / 'CONFIG.json').read_text())
    raw = Path(design['execution']['raw_root']); raw.mkdir(parents=True, exist_ok=True)
    workers = {}; streams = []; start = time.monotonic()
    for trace in design['traces']:
        evidence = HERE / 'evidence' / trace
        if args.action == 'run' and (evidence / 'STOPPED.json').exists():
            continue
        stream = (raw / f'{args.action}_{trace}.log').open('x')
        streams.append(stream)
        workers[trace] = subprocess.Popen([sys.executable, '-u', str(HERE / 'runner.py'), args.action, trace],
                                          stdout=stream, stderr=subprocess.STDOUT)
    # Prevent idle sleep during the owner-authorised local study only.
    caffeine = subprocess.Popen(['/usr/bin/caffeinate', '-i', '-w', str(__import__('os').getpid())])
    try:
        while any(proc.poll() is None for proc in workers.values()):
            time.sleep(1)
        result = {'action': args.action, 'worker_exit_codes': {trace: proc.returncode for trace, proc in workers.items()},
                  'wall_s': time.monotonic() - start,
                  'finished_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'retries': 0}
        with (raw / f'{args.action.upper()}_SUPERVISOR.json').open('x') as stream:
            json.dump(result, stream, indent=2); stream.write('\n')
        print(json.dumps(result), flush=True)
        return 0 if all(proc.returncode == 0 for proc in workers.values()) else 1
    finally:
        for stream in streams:
            stream.close()
        caffeine.terminate()


if __name__ == '__main__':
    raise SystemExit(main())
