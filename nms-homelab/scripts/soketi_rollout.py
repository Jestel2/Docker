"""Replace only Soketi after Git review and isolated runtime/startup gates.

The live Compose file owns all settings and credentials. This controller changes
only the websocket image, preserves other container IDs and Keep database binds,
and persists the image after readiness/version/native import checks. Failure
recreates the retained original image. No events or test notifications are sent.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path('/opt/docker-stacks/keep')
LIVE = ROOT / 'compose.yaml'
WORK = Path('/var/tmp/soketi-maintenance-20261111')
STATUS = WORK / 'rollout-status.json'
NAME = 'keep-keep-websocket-server-1'
SERVICE = 'keep-websocket-server'
IMAGE = 'local/soketi:1.6.1-node24.22.2-uws71-trixie-20261111'
state = {}

def run(args, timeout=120):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f'{args[0]} failed with exit {p.returncode}')
    return p.stdout

def record(phase, **values):
    state.update(phase=phase, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **values)
    tmp = STATUS.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2) + '\n')
    tmp.chmod(0o600)
    tmp.replace(STATUS)
    print(json.dumps({'phase':phase, **values}), flush=True)

def inspect(name):
    return json.loads(run(['docker', 'inspect', name]))[0]

def compose(overlay=None):
    args = ['docker', 'compose', '--project-directory', str(ROOT), '-f', str(LIVE)]
    if overlay:
        args += ['-f', str(overlay)]
    return args

def http(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status

def ready():
    for attempt in range(60):
        try:
            assert http('http://127.0.0.1:6101/ready') == 200
            assert http('http://10.20.60.15:8180/healthcheck') == 200
            assert http('http://10.20.60.15:3200/api/auth/providers') == 200
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError('Soketi/Keep readiness failed')

def others():
    entries = [json.loads(x) for x in run(['docker', 'ps', '--no-trunc', '--format', 'json']).splitlines()]
    return {x['Names']:x['ID'] for x in entries if x['Names'] != NAME}

assert os.geteuid() == 0 and run(['hostname']).strip().lower() == 'nms'
assert not STATUS.exists()
build = json.loads((WORK / 'build-status.json').read_text())
assert build['phase'] == 'isolated_runtime_verified'
unit = run(['systemctl', 'show', 'soketi-runtime-build-20261111.service', '-p', 'SubState', '-p', 'Result', '-p', 'ExecMainStatus'])
assert 'SubState=exited' in unit and 'Result=success' in unit and 'ExecMainStatus=0' in unit
ready()
before = inspect(NAME)
assert before['State']['Running'] and before['Mounts'] == []
assert before['Image'] == 'sha256:fc5cb65e6508800976cdbf82b851da5a85082625f856863ca3a46808856b2fc0'
target = json.loads(run(['docker', 'image', 'inspect', IMAGE]))[0]['Id']
assert target == build['image_id']
raw = LIVE.read_text()
candidate = WORK / 'rollout-image.yaml'
candidate.write_text(f'services:\n  {SERVICE}:\n    image: {IMAGE}\n')
candidate.chmod(0o600)
rollback = WORK / 'rollback-image.yaml'
rollback.write_text(f'services:\n  {SERVICE}:\n    image: {before["Image"]}\n')
rollback.chmod(0o600)
a = json.loads(run(compose() + ['config', '--format', 'json']))
b = json.loads(run(compose(candidate) + ['config', '--format', 'json']))
x, y = copy.deepcopy(a), copy.deepcopy(b)
x['services'][SERVICE].pop('image')
y['services'][SERVICE].pop('image')
assert x == y
previous = a['services'][SERVICE]['image']
assert raw.count(previous) == 1
replacement = raw.replace(previous, IMAGE, 1)
unrelated = others()
state.update(original_image=before['Image'], target_image=target)
record('image_only_preflight_passed')
try:
    run(compose(candidate) + ['up', '-d', '--no-deps', '--force-recreate', SERVICE], 300)
    ready()
    after = inspect(NAME)
    assert after['Image'] == target and after['State']['Running']
    assert after['Mounts'] == before['Mounts']
    for key in ['PortBindings', 'NetworkMode', 'RestartPolicy']:
        assert after['HostConfig'][key] == before['HostConfig'][key]
    def settings(container):
        env = dict(x.split('=', 1) for x in container['Config']['Env'])
        env.pop('NODE_VERSION', None)
        return env
    assert settings(after) == settings(before)
    output = run(['docker', 'exec', NAME, 'node', '-e', 'console.log(process.version);require("uWebSockets.js");console.log(require("uWebSockets.js/package.json").version)'])
    assert output.strip().splitlines() == ['v24.22.2', '20.71.0']
    assert others() == unrelated and LIVE.read_text() == raw
    tmp = LIVE.with_suffix('.maintenance.tmp')
    tmp.write_text(replacement)
    tmp.chmod(LIVE.stat().st_mode & 0o777)
    tmp.replace(LIVE)
    record('soketi_cutover_verified', node='v24.22.2', uws='20.71.0', readiness=200, keep_health=200, settings_and_unrelated_containers_preserved=True)
except Exception as error:
    record('rollout_failed', failure_type=type(error).__name__)
    run(compose(rollback) + ['up', '-d', '--no-deps', '--force-recreate', SERVICE], 300)
    ready()
    record('original_soketi_recovered', readiness=200)
    raise
