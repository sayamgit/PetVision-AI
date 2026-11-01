"""Run the synthetic upload stress check in a disposable 512 MiB Linux container."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--image', default='petvision:release')
parser.add_argument('--docker', default=os.environ.get('DOCKER_BINARY') or shutil.which('docker'))
args = parser.parse_args()
if not args.docker:
    parser.error('Docker CLI not found. Set DOCKER_BINARY or pass --docker with its executable path.')
name = 'petvision-qa-' + uuid.uuid4().hex[:12]
script = Path(__file__).with_name('check_container.py').read_text(encoding='utf-8')
result = subprocess.run([args.docker, 'run', '--name', name, '--memory=512m',
    '--memory-swap=512m', '--network=none', '-i', '-e', 'PETVISION_TEST_CONCURRENT=1',
    '--entrypoint=python', args.image, '-'], input=script, text=True)
try:
    state = json.loads(subprocess.check_output([args.docker, 'inspect', '--format', '{{json .State}}', name]))
    print(json.dumps({'exit_code': state['ExitCode'], 'oom_killed': state['OOMKilled']}))
    if state['Running']:
        raise SystemExit('Test container is still running: ' + name)
    if result.returncode or state['OOMKilled']:
        raise SystemExit('Container stress check failed.')
finally:
    subprocess.run([args.docker, 'rm', name], check=True)
