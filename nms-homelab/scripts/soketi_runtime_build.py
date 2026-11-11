"""Build and test the Soketi Node24 patch without changing production.

Inputs are a sanitized Dockerfile and the verified local application image.
Outputs are the candidate image and a root-readable status file. This controller
owns one isolated test container, which receives ephemeral test credentials only
through environment variables and has neither network access nor state mounts.
No production environment, credentials, provider jobs or notifications are used.
Only a successful native import, full startup, readiness and cleanup yields exit0.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

WORK = Path('/var/tmp/soketi-maintenance-20261111')
STATUS = WORK / 'build-status.json'
SOURCE = 'local/soketi:1.6.1-node24-uws71-trixie'
SOURCE_ID = 'sha256:fc5cb65e6508800976cdbf82b851da5a85082625f856863ca3a46808856b2fc0'
IMAGE = 'local/soketi:1.6.1-node24.22.2-uws71-trixie-20261111'
NAME = 'soketi-runtime-probe-20261111'
ENV = dict(os.environ)

def run(args, timeout=120):
    """Capture subprocess output privately; failures expose only tool/exit type."""
    result = subprocess.run(args, env=ENV, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed with exit {result.returncode}')
    return result.stdout

def record(phase, **values):
    """Persist nonsecret evidence, never captured application logs or environment."""
    values.update(phase=phase, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), production_changed=False)
    STATUS.write_text(json.dumps(values, indent=2) + '\n')
    STATUS.chmod(0o600)
    print(json.dumps(values), flush=True)

assert os.geteuid() == 0 and run(['hostname']).strip().lower() == 'nms'
WORK.mkdir(mode=0o700, exist_ok=True)
assert not STATUS.exists()
assert run(['docker', 'image', 'inspect', SOURCE, '--format', '{{.Id}}']).strip() == SOURCE_ID
assert subprocess.run(['docker', 'container', 'inspect', NAME], capture_output=True).returncode != 0
record('verified_source_image', source_id=SOURCE_ID)
created = False
try:
    run(['docker', 'build', '--tag', IMAGE, str(WORK / 'runtime')], 1200)
    probe = 'console.log(JSON.stringify({node:process.version,uws:require("uWebSockets.js/package.json").version}));require("uWebSockets.js");console.log("native_import=ok")'
    output = run(['docker', 'run', '--rm', '--network', 'none', '--memory', '256m', '--entrypoint', 'node', IMAGE, '-e', probe])
    assert 'v24.22.2' in output and '20.71.0' in output and 'native_import=ok' in output
    # Test keys have no relationship to any configured production application.
    ENV['SOKETI_DEFAULT_APP_ID'] = 'maintenance-isolated-20261111'
    ENV['SOKETI_DEFAULT_APP_KEY'] = secrets.token_urlsafe(32)
    ENV['SOKETI_DEFAULT_APP_SECRET'] = secrets.token_urlsafe(48)
    run(['docker', 'run', '-d', '--name', NAME, '--network', 'none', '--memory', '256m', '--env', 'SOKETI_DEFAULT_APP_ID', '--env', 'SOKETI_DEFAULT_APP_KEY', '--env', 'SOKETI_DEFAULT_APP_SECRET', IMAGE])
    created = True
    for attempt in range(45):
        try:
            output = run(['docker', 'exec', NAME, 'node', '-e', 'fetch("http://127.0.0.1:6001/ready").then(r=>{console.log(r.status);process.exit(r.status===200?0:1)}).catch(()=>process.exit(1))'], 10)
            assert output.strip() == '200'
            break
        except Exception:
            time.sleep(2)
    else:
        raise RuntimeError('Isolated Soketi readiness failed')
    image_id = run(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}']).strip()
    record('isolated_runtime_verified', image_id=image_id, node='v24.22.2', uws='20.71.0', full_startup=True, native_import=True, readiness=200)
except Exception as error:
    record('runtime_test_failed', failure_type=type(error).__name__)
    raise
finally:
    if created:
        run(['docker', 'stop', '--timeout', '30', NAME], 60)
        run(['docker', 'rm', NAME])
