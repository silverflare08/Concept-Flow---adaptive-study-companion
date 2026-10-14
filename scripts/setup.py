"""Install project dependencies and local models from the repository root."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
os.chdir(root)
if sys.version_info < (3, 11):
    raise SystemExit('Python 3.11 or newer is required. Python 3.11 is recommended.')
for binary, link in [('node','https://nodejs.org'), ('npm','https://nodejs.org'), ('ollama','https://ollama.com/download')]:
    if not shutil.which(binary):
        raise SystemExit(f'Install {binary} from {link}, then reopen your terminal and run this command again.')
environment = root / '.venv'
python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
def run(args, cwd=root):
    print('\n> ' + ' '.join(map(str,args)), flush=True)
    subprocess.run(list(map(str,args)), cwd=cwd, check=True)
try:
    if not python.exists(): run([sys.executable, '-m', 'venv', environment])
    run([python, '-m', 'pip', 'install', '--upgrade', 'pip'])
    install = [python, '-m', 'pip', 'install']
    version = subprocess.check_output([python,'-c','import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'], text=True).strip()
    if os.name == 'nt' and version == '3.11': install += ['-c', 'requirements-windows-py311.txt']
    run(install + ['-e', '.[dev,app,ingestion,specialist]'])
    run([shutil.which('npm'), 'ci'], cwd=root / 'web')
    for model in ['qwen2.5:3b-instruct', 'qwen3-vl:2b-instruct']:
        run([shutil.which('ollama'), 'pull', model])
    run([python, '-c', 'from faster_whisper import WhisperModel; WhisperModel("base",device="cpu",compute_type="int8"); print("Speech model ready")'])
    run([python, 'scripts/check_setup.py', '--models'])
    run([python, 'scripts/smoke_samples.py'])
except subprocess.CalledProcessError as error:
    raise SystemExit(f'Setup stopped at the command above (exit {error.returncode}). Fix that error and rerun; completed downloads can be reused.')
print('\nSetup complete. Start ConceptFlow with: python scripts/start.py')
