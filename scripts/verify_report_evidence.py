"""Save reproducible software-check logs without changing application behavior."""
import json
from datetime import datetime, timezone
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/evaluation'

def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    npm = shutil.which('npm')
    node = shutil.which('node')
    if not npm or not node:
        raise SystemExit('Install Node.js and npm before running the checks.')
    git_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    report = {'run_started_utc': datetime.now(timezone.utc).isoformat(),
              'git_head': git_head, 'python': platform.python_version(),
              'platform': platform.platform(),
              'node': subprocess.check_output([node, '--version'], text=True).strip(),
              'scope': 'Existing checkout and installed dependencies, not a fresh clone or clean installation.',
              'checks': []}
    commands = [
        ('backend-tests', [sys.executable, '-m', 'pytest', '-q', '--basetemp=.pytest_cache/report-evidence-recorded']),
        ('frontend-tests', [npm, '--prefix', 'web', 'test']),
        ('frontend-build', [npm, '--prefix', 'web', 'run', 'build']),
        ('benchmark-run', [sys.executable, 'benchmark_report.py']),
    ]
    for name, command in commands:
        print(f'Running {name}...', flush=True)
        completed = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        log = OUTPUT / f'{name}.txt'
        log.write_text(completed.stdout, encoding='utf-8')
        report['checks'].append({'name': name, 'command': command,
                                 'exit_code': completed.returncode,
                                 'log': log.relative_to(ROOT).as_posix()})
        (OUTPUT / 'current-checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f'{name}: exit {completed.returncode}; {log.relative_to(ROOT)}', flush=True)
    raise SystemExit(0 if all(c['exit_code'] == 0 for c in report['checks']) else 1)

if __name__ == '__main__':
    main()
