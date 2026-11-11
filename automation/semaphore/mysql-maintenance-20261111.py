"""Upgrade only Semaphore MySQL using a cold clone and native compatibility gate.

Preconditions: reviewed Git changes, successful isolated logical restore, current
MySQL8.0.45/Semaphore2.17.37, healthy application, no running automation processes.
The controller stops app/DB gracefully, retains the original volume untouched,
and copies the complete cleanly stopped DB into one new named Docker volume.
MySQL8.4 upgrades that isolated clone with no network. Existing accounts and root
authentication are preserved; no password is generated, copied to a file or logged.
The original Semaphore binary runs migration-only against the clone with config
streamed via stdin; no job workers, schedules or provider connections run there.
Only successful integrity/row-count/authentication/application gates persist the
new DB image/volume. Failure restores the original DB image/volume and app. New
candidate state remains retained for inspection. VM disks/settings are untouched.
"""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request

ROOT = Path('/opt/semaphore')
LIVE = ROOT / 'docker-compose.yml'
WORK = Path('/var/tmp/semaphore-maintenance-20261111')
PREFLIGHT_ONLY = '--preflight-only' in sys.argv
STATUS = WORK / ('mysql-preflight-status.json' if PREFLIGHT_ONLY else 'mysql-rollout-status.json')
DB = 'semaphore-mysql-1'
APP = 'semaphore-semaphore-1'
APP_IMAGE = 'sha256:0b38eff72bdcf533b24eb2b8ca8a23acf890306bdba31659e7638b3dedde07e3'
IMAGE = 'mysql@sha256:a81d043930e51745522bd5c430961cf8286f0a23f0a9a2a6e0108f7ea71b0902'
OLD_KEY = 'semaphore-mysql'
NEW_KEY = 'semaphore-mysql-8.4-20261111'
OLD_VOLUME = 'semaphore_semaphore-mysql'
NEW_VOLUME = 'semaphore_' + NEW_KEY
ISOLATED = 'semaphore-mysql-upgrade-20261111'
ENV = dict(os.environ)
state = {}

def run(args, timeout=120, input=None):
    """Capture private output; failures expose only tool and return code."""
    p = subprocess.run(args, input=input, env=ENV, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f'{args[0]} failed with exit {p.returncode}')
    return p.stdout

def record(phase, **values):
    """Atomically save nonsecret completion evidence owned by this controller."""
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

def query(name, sql):
    command = 'export MYSQL_PWD="$MYSQL_PASSWORD"; exec mysql -u "$MYSQL_USER" "$MYSQL_DATABASE" -N -e "$1"'
    return run(['docker', 'exec', name, 'sh', '-c', command, 'query', sql], 60).strip()

def rows(name, integrity=False):
    """Read schema/count metadata only; never return project/task/key contents."""
    tables = query(name, 'SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema=DATABASE() ORDER BY TABLE_NAME;').splitlines()
    assert len(tables) == 37
    counts = {}
    for table in tables:
        quoted = '`' + table.replace('`', '``') + '`'
        counts[table] = int(query(name, 'SELECT COUNT(*) FROM ' + quoted))
        if integrity:
            checks = query(name, 'CHECK TABLE ' + quoted).splitlines()
            assert any(line.endswith('\tstatus\tOK') for line in checks)
            assert not any('\terror\t' in line for line in checks)
    return counts

def app_ready():
    for attempt in range(60):
        try:
            with urllib.request.urlopen('http://127.0.0.1:3000/api/ping', timeout=5) as response:
                assert response.status == 200
            assert inspect(APP)['State']['Running']
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError('Semaphore did not recover')

def db_ready(name, version):
    for attempt in range(150):
        container = inspect(name)
        assert container['State']['Running'] and not container['State']['OOMKilled']
        try:
            assert query(name, 'SELECT VERSION();') == version
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError('Database upgrade/authentication failed')

def stop(name, require_clean=True):
    """Require a graceful server exit before cold copy or volume handoff."""
    run(['docker', 'stop', '--timeout', '120', name], 150)
    current = inspect(name)['State']
    assert not current['Running']
    if require_clean:
        assert not current['OOMKilled'] and current['ExitCode'] == 0

assert os.geteuid() == 0 and run(['hostname']).strip().lower() == 'terminal'
assert not STATUS.exists()
prior = json.loads((WORK / 'mysql-restore-status.json').read_text())
assert prior['phase'] == 'isolated_mysql_restore_verified' and prior['restored_tables'] == 37
unit = run(['systemctl', 'show', 'semaphore-mysql-restore-test-20261111.service', '-p', 'SubState', '-p', 'Result', '-p', 'ExecMainStatus'])
assert 'SubState=exited' in unit and 'Result=success' in unit and 'ExecMainStatus=0' in unit
app_ready()
db_before, app_before = inspect(DB), inspect(APP)
assert db_before['State']['Running'] and app_before['Image'] == APP_IMAGE
assert '2.17.37' in run(['docker', 'exec', APP, '/usr/local/bin/semaphore', 'version'])
assert query(DB, 'SELECT VERSION();') == '8.0.45'
assert next(m for m in db_before['Mounts'] if m['Destination'] == '/var/lib/mysql')['Name'] == OLD_VOLUME
assert db_before['Config']['Cmd'] == ['mysqld']
processes = run(['docker', 'top', APP, '-eo', 'comm']).splitlines()[1:]
assert all(x.strip() in ['tini', 'semaphore'] for x in processes)
for kind, name in [('volume', NEW_VOLUME), ('container', ISOLATED)]:
    assert subprocess.run(['docker', kind, 'inspect', name], capture_output=True).returncode != 0
image_id = json.loads(run(['docker', 'image', 'inspect', IMAGE]))[0]['Id']
candidate = WORK / 'mysql-image-volume.yaml'
candidate.write_text(f'services:\n  mysql:\n    image: {IMAGE}\n    volumes:\n      - {NEW_KEY}:/var/lib/mysql\nvolumes:\n  {NEW_KEY}:\n')
candidate.chmod(0o600)
rollback = WORK / 'mysql-rollback.yaml'
rollback.write_text(f'services:\n  mysql:\n    image: {db_before["Image"]}\n    volumes:\n      - {OLD_KEY}:/var/lib/mysql\n')
rollback.chmod(0o600)
a = json.loads(run(compose() + ['config', '--format', 'json']))
b = json.loads(run(compose(candidate) + ['config', '--format', 'json']))
x, y = copy.deepcopy(a), copy.deepcopy(b)
x['services']['mysql'].pop('image')
y['services']['mysql'].pop('image')
for doc in [x, y]:
    next(v for v in doc['services']['mysql']['volumes'] if v['target'] == '/var/lib/mysql').pop('source')
y['volumes'].pop(NEW_KEY)
assert x == y
raw = LIVE.read_text()
replacement, count = re.subn(r'(?m)^([ \t]*image:[ \t]*)mysql:8\.0[ \t]*$', lambda m:m[1]+IMAGE, raw)
assert count == 1
replacement, count = re.subn(r'(?m)^([ \t]*-[ \t]*)semaphore-mysql:(/var/lib/mysql[ \t]*)$', lambda m:m[1]+NEW_KEY+':'+m[2], replacement)
assert count == 1
replacement, count = re.subn(r'(?m)^([ \t]{2})semaphore-mysql:[ \t]*$', lambda m:m[1]+NEW_KEY+':', replacement)
assert count == 1
for item in db_before['Config']['Env']:
    key, value = item.split('=', 1)
    if key.startswith('MYSQL_'):
        ENV[key] = value
assert ENV['MYSQL_DATABASE'] == 'semaphore' and ENV.get('MYSQL_PASSWORD')
state.update(original_db_image=db_before['Image'], original_volume=OLD_VOLUME, target_image=image_id, candidate_volume=NEW_VOLUME, app_image=APP_IMAGE)
record('native_restore_and_topology_preflight_passed')
if PREFLIGHT_ONLY:
    sys.exit(0)
changed = False
isolated_created = False
cutover_attempted = False
try:
    changed = True
    stop(APP)
    baseline = rows(DB, integrity=True)
    stop(DB)
    record('original_database_cleanly_stopped', table_count=len(baseline))
    run(['docker', 'volume', 'create', '--label', 'com.docker.compose.project=semaphore', '--label', 'com.docker.compose.volume='+NEW_KEY, NEW_VOLUME])
    run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'sh', '--mount', f'type=volume,source={OLD_VOLUME},target=/source,readonly', '--mount', f'type=volume,source={NEW_VOLUME},target=/target', IMAGE, '-c', 'test -z "$(ls -A /target)" && cp -a /source/. /target/'], 1200)
    record('native_cold_clone_created', original_volume_retained=True)
    env_args = []
    for key in ENV:
        if key.startswith('MYSQL_'):
            env_args += ['--env', key]
    run(['docker', 'run', '-d', '--name', ISOLATED, '--network', 'none', '--memory', '1g', '--cpus', '1', '--mount', f'type=volume,source={NEW_VOLUME},target=/var/lib/mysql', *env_args, IMAGE])
    isolated_created = True
    db_ready(ISOLATED, '8.4.13')
    assert rows(ISOLATED, integrity=True) == baseline
    # This opens only the cloned database over its loopback network. The original
    # root authentication/account tables are already present, so image startup
    # neither generates a new root password nor executes initialization scripts.
    config = {'dialect':'mysql', 'tmp_path':'/tmp/semaphore', 'mysql':{'host':'127.0.0.1:3306', 'name':ENV['MYSQL_DATABASE'], 'user':ENV['MYSQL_USER'], 'pass':ENV['MYSQL_PASSWORD']}}
    run(['docker', 'run', '--rm', '-i', '--network', 'container:'+ISOLATED, '--memory', '192m', '--entrypoint', '/usr/local/bin/semaphore', APP_IMAGE, 'migrate', '--config', '/dev/stdin'], 180, input=json.dumps(config))
    assert rows(ISOLATED) == baseline
    config = None
    record('isolated_mysql_upgrade_and_semaphore_compatibility_verified', candidate_version='8.4.13', table_count=37, row_counts_preserved=True, integrity=True)
    stop(ISOLATED)
    run(['docker', 'rm', ISOLATED])
    isolated_created = False
    cutover_attempted = True
    run(compose(candidate) + ['up', '-d', '--no-deps', '--force-recreate', 'mysql'], 300)
    db_ready(DB, '8.4.13')
    run(['docker', 'start', APP])
    app_ready()
    assert inspect(APP)['Id'] == app_before['Id'] and inspect(APP)['Image'] == APP_IMAGE
    after = inspect(DB)
    assert after['Image'] == image_id
    assert next(m for m in after['Mounts'] if m['Destination'] == '/var/lib/mysql')['Name'] == NEW_VOLUME
    assert rows(DB, integrity=True) == baseline
    assert LIVE.read_text() == raw
    tmp = LIVE.with_suffix('.maintenance.tmp')
    tmp.write_text(replacement)
    st = LIVE.stat()
    os.chown(tmp, st.st_uid, st.st_gid)
    tmp.chmod(st.st_mode & 0o777)
    tmp.replace(LIVE)
    record('mysql_cutover_verified', mysql='8.4.13', semaphore='2.17.37', table_count=37, integrity=True, row_counts_preserved=True, semaphore_health=200, original_root_authentication_preserved=True, app_and_automation_settings_preserved=True)
except Exception as error:
    record('mysql_rollout_failed', failure_type=type(error).__name__)
    if changed:
        if inspect(APP)['State']['Running']:
            stop(APP)
        if isolated_created:
            stop(ISOLATED, require_clean=False)
            run(['docker', 'rm', ISOLATED])
            isolated_created = False
        if cutover_attempted:
            if subprocess.run(['docker', 'container', 'inspect', DB], capture_output=True).returncode == 0:
                stop(DB, require_clean=False)
            run(compose(rollback) + ['up', '-d', '--no-deps', '--force-recreate', 'mysql'], 300)
        else:
            run(['docker', 'start', DB])
        db_ready(DB, '8.0.45')
        run(['docker', 'start', APP])
        app_ready()
        if LIVE.read_text() != raw:
            LIVE.write_text(raw)
        record('original_mysql_and_semaphore_recovered', mysql='8.0.45', semaphore_health=200, candidate_volume_retained=True)
    raise
