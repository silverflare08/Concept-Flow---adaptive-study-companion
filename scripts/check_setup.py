"""Run from the repository root: python scripts/check_setup.py [--models]."""
import argparse
import importlib.util
from importlib.metadata import version
import json
import os
import platform
import shutil
import sys
from urllib.request import urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--models', action='store_true', help='Also check local Ollama model availability')
args = parser.parse_args()
failures = []
print(f'Python: {platform.python_version()} ({sys.executable})')
if sys.version_info < (3, 11): failures.append('Python 3.11 or newer is required.')
for module in ['studybuddy', 'fastapi', 'uvicorn', 'multipart', 'pydantic', 'sqlalchemy', 'pypdf', 'pymupdf', 'pptx', 'PIL', 'faster_whisper', 'yt_dlp', 'python_calamine', 'pyarrow']:
    found = importlib.util.find_spec(module) is not None
    print(f'{module}: {"OK" if found else "MISSING"}')
    if not found: failures.append(f'Missing Python package for {module}. Install the app, ingestion and specialist extras.')
for binary in ['node', 'npm', 'ollama']:
    path = shutil.which(binary)
    print(f'{binary}: {path or "MISSING"}')
    if not path: failures.append(f'Install {binary} and reopen your terminal.')
print(f'ffmpeg: {shutil.which("ffmpeg") or "not installed (recommended for media/YouTube compatibility)"}')
if importlib.util.find_spec('av') is not None:
    av_version = version('av')
    print(f'PyAV: {av_version}')
    if int(av_version.split('.')[0]) >= 19:
        failures.append('PyAV 19 is incompatible with the pinned speech reader. Run: python -m pip install "av>=11,<19"')
if args.models:
    endpoint = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434/api/chat').rsplit('/api/', 1)[0] + '/api/tags'
    try:
        with urlopen(endpoint, timeout=5) as response:
            names = {row['name'] for row in json.load(response).get('models', [])}
        for model in [os.getenv('OLLAMA_MODEL', 'qwen2.5:3b-instruct'), os.getenv('OLLAMA_VISION_MODEL', 'qwen3-vl:2b-instruct')]:
            if model == 'qwen3-vl:2b': model = 'qwen3-vl:2b-instruct'
            print(f'{model}: {"OK" if model in names else "MISSING"}')
            if model not in names: failures.append(f'Run: ollama pull {model}')
    except Exception as error:
        failures.append(f'Ollama is unavailable at {endpoint}: {error}. Start Ollama first.')
if failures:
    print('\nSetup needs attention:')
    for issue in failures: print(f'- {issue}')
    sys.exit(1)
print('\nRequired setup checks passed. This checks availability; it does not benchmark model quality.')
