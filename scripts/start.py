"""Run the local API and frontend together; Ctrl+C stops both."""
import os
import argparse
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
from urllib.request import urlopen

parser=argparse.ArgumentParser()
parser.add_argument('--api-port',type=int,default=8000)
parser.add_argument('--web-port',type=int,default=5173)
parser.add_argument('--check',action='store_true',help='Verify startup, then stop both servers')
args=parser.parse_args()

root = Path(__file__).resolve().parents[1]
python = root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
npm = shutil.which('npm')
if not python.exists() or not npm:
    raise SystemExit('Run python scripts/setup.py first.')
for port in [args.api_port,args.web_port]:
    with socket.socket() as probe:
        try: probe.bind(('127.0.0.1',port))
        except OSError: raise SystemExit(f'Port {port} is unavailable. Stop the previous server or configure the API/Vite ports as described in README.')
children=[]
try:
    environment=os.environ.copy()
    environment['PYTHONUNBUFFERED']='1'
    environment['VITE_API_URL']=f'http://127.0.0.1:{args.api_port}'
    command=[str(python),'-m','uvicorn','studybuddy.api:app','--host','127.0.0.1','--port',str(args.api_port)]
    if (root / '.env').exists(): command += ['--env-file', '.env']
    children.append(subprocess.Popen(command,cwd=root,env=environment,start_new_session=os.name != 'nt'))
    children.append(subprocess.Popen([npm,'run','dev','--','--host','127.0.0.1','--port',str(args.web_port)],cwd=root/'web',env=environment,start_new_session=os.name != 'nt'))
    print(f'\nConceptFlow: http://127.0.0.1:{args.web_port}\nKeep Ollama running. Ctrl+C stops both servers.',flush=True)
    if args.check:
        for url in [f'http://127.0.0.1:{args.api_port}/api/workspace',f'http://127.0.0.1:{args.web_port}/']:
            deadline=time.monotonic()+30
            while True:
                try:
                    with urlopen(url,timeout=2) as response:
                        if response.status==200: break
                except OSError:
                    if time.monotonic()>deadline: raise SystemExit(f'Startup failed: {url}')
                    time.sleep(.5)
        print('API and frontend startup checks passed.',flush=True)
        raise SystemExit(0)
    while all(child.poll() is None for child in children): time.sleep(.5)
except KeyboardInterrupt:
    print('\nStopping ConceptFlow...',flush=True)
finally:
    for child in children:
        if child.poll() is None:
            if os.name == 'nt': subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True)
            else: os.killpg(child.pid, signal.SIGTERM)
    for child in children:
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired: child.kill()
