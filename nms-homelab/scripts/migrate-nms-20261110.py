"""Cut over the verified home NMS to a separately restored MariaDB 11.4 volume.

Run as root on nms with a reviewed Compose JSON as the argument. Add --check
to validate the live prerequisites without creating files or stopping services. The
controller must have verified the image digests and isolated restore/migration
tests. This script pauses only LibreNMS and its dispatcher. Credentials remain
in the existing Docker environment and child-process environments; none are
printed, placed in command arguments, or written into recovery files.

The original database bind directory and image IDs are retained. A sanitized
Compose snapshot permits rollback without downgrading the new data directory.
On a normal exception the script attempts that rollback or restarts the original
apps. A process interruption requires inspecting STATUS before another action;
do not rerun this one-time migration against an existing new database directory.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path('/opt/docker-stacks/nms-stack')
RECOVERY = ROOT / 'maintenance-20261110'
NEW_DATA = ROOT / 'db-11.4'
SEED = 'nms-db-seed-20261110'
NETWORK = 'nms-db-seed-20261110'
DB_IMAGE = 'mariadb:11.4.13@sha256:d1891ede5a559f1086f55053bb8cc1569b0298338c4d72d71725a7f74f6ba620'
APP_IMAGE = 'librenms/librenms:26.10.2@sha256:66f586a84355b6c80758e373aaa7c0b230284d1d22588b29b3706540041e2806'
STATUS = RECOVERY / 'status.json'
ROLLBACK = RECOVERY / 'rollback-compose.json'
SECRET_ENV = {'MYSQL_PASSWORD': 'MYSQL_PASSWORD',
              'MYSQL_ROOT_PASSWORD': 'MYSQL_ROOT_PASSWORD',
              'DB_PASSWORD': 'MYSQL_PASSWORD'}
environment = dict(os.environ)


def run(args, timeout=120, check=True):
    """Capture subprocess output privately; errors never echo environment/data."""
    result = subprocess.run(args, env=environment, text=True, capture_output=True,
                            timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f'{args[0]} operation failed, exit {result.returncode}')
    return result


def record(phase, **values):
    """Persist non-secret progress atomically for a detached controller."""
    state.update(phase=phase, **values)
    temp = STATUS.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2) + '\n')
    temp.chmod(0o600)
    temp.replace(STATUS)
    print(json.dumps({'phase': phase, **values}), flush=True)


def query(container, sql, root=False):
    """Use the container's own authentication; return only requested SQL output."""
    prefix = ('MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mariadb -uroot '
              if root else 'MYSQL_PWD="$MYSQL_PASSWORD" exec mariadb -u "$MYSQL_USER" ')
    return run(['docker', 'exec', container, 'sh', '-c',
                prefix + '--host=127.0.0.1 -N -B "$MYSQL_DATABASE" -e "$1"',
                'query', sql], timeout=30).stdout.strip()


def counts(container):
    values = query(container, 'SELECT COUNT(*) FROM information_schema.tables '
                   'WHERE table_schema=DATABASE(); SELECT COUNT(*) FROM devices; '
                   'SELECT COUNT(*) FROM migrations; SELECT @@lower_case_table_names;')
    return tuple(map(int, values.splitlines()))


def wait_database(container):
    """Require authenticated TCP SQL, avoiding the temporary init-only server."""
    for _ in range(120):
        try:
            return query(container, 'SELECT VERSION();', root=True)
        except (RuntimeError, subprocess.TimeoutExpired):
            time.sleep(2)
    raise RuntimeError('Database did not become ready')


def compose(path, services):
    """Apply only named services; untouched dependencies are preserved."""
    return run(['docker', 'compose', '--project-directory', str(ROOT),
                '--env-file', '/dev/null', '-f', str(path),
                'up', '-d', '--no-deps', *services], timeout=180)


def wait_app():
    for _ in range(120):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/login', timeout=5) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError('LibreNMS login did not become ready')


assert os.geteuid() == 0
assert run(['hostname']).stdout.strip().lower() == 'nms'
assert len(sys.argv) in {2, 3}
assert len(sys.argv) == 2 or sys.argv[2] == '--check'
candidate_path = Path(sys.argv[1]).resolve()
candidate = json.loads(candidate_path.read_text())
assert candidate['name'] == 'nms-stack'
assert set(candidate['services']) == {'db', 'librenms', 'dispatcher', 'redis', 'oxidized'}
assert candidate['services']['db']['image'] == DB_IMAGE
assert all(candidate['services'][s]['image'] == APP_IMAGE for s in ['librenms', 'dispatcher'])
assert '--lower-case-table-names=0' in candidate['services']['db']['command']
assert candidate['services']['db']['volumes'][0]['source'] == str(NEW_DATA)
assert candidate['services']['db']['volumes'][0]['bind']['create_host_path'] is False
assert not NEW_DATA.exists() and not RECOVERY.exists()
assert shutil.disk_usage(ROOT).free > 5 * 1024 ** 3
for kind, name in [('container', SEED), ('network', NETWORK)]:
    assert run(['docker', kind, 'inspect', name], check=False).returncode != 0

# Capture the live configuration in memory, and keep only its sanitized form.
live = json.loads(run(['docker', 'compose', '--project-directory', str(ROOT),
                      'config', '--format', 'json']).stdout)
assert set(live['services']) == set(candidate['services'])
containers = json.loads(run(['docker', 'inspect', 'librenms_db', 'librenms',
                            'librenms_dispatcher', 'librenms_redis', 'oxidized']).stdout)
by_service = {c['Config']['Labels']['com.docker.compose.service']: c for c in containers}
compose_files = {c['Config']['Labels']['com.docker.compose.project.config_files'] for c in containers}
assert compose_files == {str(ROOT / 'compose.yaml')}
assert by_service['db']['Mounts'][0]['Source'] == str(ROOT / 'db')
db_environment = dict(item.split('=', 1) for item in by_service['db']['Config']['Env'])
for key in ['MYSQL_ROOT_PASSWORD', 'MYSQL_PASSWORD', 'MYSQL_USER', 'MYSQL_DATABASE']:
    assert db_environment.get(key)
    environment[key] = db_environment[key]
assert environment['MYSQL_DATABASE'] == 'librenms'
assert all(c['State']['Running'] for c in containers)
baseline = counts('librenms_db')
assert baseline[0] >= 164 and baseline[1] == 14 and baseline[2] == 390 and baseline[3] == 0
for name, service in live['services'].items():
    service['image'] = by_service[name]['Image']
    for key, value in service.get('environment', {}).items():
        if re.search(r'password|secret|token|key|community', key, re.I):
            assert key in SECRET_ENV
            service['environment'][key] = '${' + SECRET_ENV[key] + ':?managed runtime secret required}'
sanitized = json.dumps(live, indent=2) + '\n'
assert all(value not in sanitized for key, value in db_environment.items() if 'PASSWORD' in key)
if len(sys.argv) == 3:
    print(json.dumps({'preflight': 'passed', 'baseline_counts': baseline,
                      'credential_output': False, 'production_changes': False}))
    sys.exit(0)
RECOVERY.mkdir(mode=0o700)
ROLLBACK.write_text(sanitized)
ROLLBACK.chmod(0o600)
state = {'baseline_counts': baseline, 'original_database_directory': str(ROOT / 'db'),
         'new_database_directory': str(NEW_DATA), 'original_image_ids':
         {name: c['Image'] for name, c in by_service.items()}}
record('preflight_passed')
apps_stopped = cutover = seed_created = network_created = False
try:
    run(['docker', 'stop', '--time', '90', 'librenms_dispatcher', 'librenms'])
    apps_stopped = True
    record('writers_paused')
    NEW_DATA.mkdir(mode=0o750)
    run(['docker', 'network', 'create', '--internal', NETWORK])
    network_created = True
    args = ['docker', 'run', '-d', '--name', SEED, '--network', NETWORK,
            '--memory', '768m', '--cpus', '2', '--mount',
            f'type=bind,source={NEW_DATA},target=/var/lib/mysql']
    for key in ['MYSQL_ROOT_PASSWORD', 'MYSQL_PASSWORD', 'MYSQL_USER', 'MYSQL_DATABASE']:
        args += ['--env', key]
    args += [DB_IMAGE, '--lower-case-table-names=0', '--innodb-buffer-pool-size=128M']
    run(args)
    seed_created = True
    wait_database(SEED)
    # The dump streams directly between containers and is never saved to a file.
    dump = subprocess.Popen(['docker', 'exec', 'librenms_db', 'sh', '-c',
        'MYSQL_PWD="$MYSQL_PASSWORD" exec mariadb-dump -u "$MYSQL_USER" '
        '--single-transaction --quick --skip-lock-tables --hex-blob '
        '--databases "$MYSQL_DATABASE"'], env=environment, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL)
    restore = subprocess.Popen(['docker', 'exec', '-i', SEED, 'sh', '-c',
        'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mariadb -uroot'], env=environment,
        stdin=dump.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dump.stdout.close()
    assert restore.wait(timeout=300) == 0
    assert dump.wait(timeout=30) == 0
    assert counts(SEED) == baseline
    integrity = run(['docker', 'exec', SEED, 'sh', '-c',
        'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mariadb-check -uroot --check "$MYSQL_DATABASE"'])
    assert all(line.rstrip().endswith('OK') for line in integrity.stdout.splitlines() if line.strip())
    run(['docker', 'stop', '--time', '90', SEED])
    run(['docker', 'container', 'rm', SEED])
    seed_created = False
    record('separate_database_restored', integrity='passed')
    run(['docker', 'stop', '--time', '90', 'librenms_db'])
    # Mark before Compose: even a partial recreation requires original-volume rollback.
    cutover = True
    record('cutover_started')
    compose(candidate_path, ['db'])
    assert wait_database('librenms_db').startswith('11.4.13')
    compose(candidate_path, ['librenms', 'dispatcher'])
    wait_app()
    migrated = counts('librenms_db')
    assert migrated[1] == baseline[1] and migrated[2] >= 408 and migrated[3] == 0
    # Install the approved desired state only after the database/application gates.
    temp = ROOT / 'docker-compose.maintenance.tmp'
    temp.write_text(json.dumps(candidate, indent=2) + '\n')
    temp.chmod(0o644)
    temp.replace(ROOT / 'compose.yaml')
    record('cutover_verified', migrated_counts=migrated, login_http=200,
           librenms='26.10.2', mariadb='11.4.13')
except Exception as error:
    record('migration_failed', failure_type=type(error).__name__)
    if cutover:
        run(['docker', 'stop', '--time', '90', 'librenms_dispatcher', 'librenms',
             'librenms_db'], check=False, timeout=300)
        compose(ROLLBACK, ['db'])
        wait_database('librenms_db')
        assert counts('librenms_db') == baseline
        compose(ROLLBACK, ['librenms', 'dispatcher'])
        wait_app()
        record('rollback_verified', login_http=200)
    elif apps_stopped:
        run(['docker', 'start', 'librenms', 'librenms_dispatcher'])
        wait_app()
        record('original_apps_restored', login_http=200)
    raise
finally:
    if seed_created:
        run(['docker', 'stop', '--time', '90', SEED], check=False)
        run(['docker', 'container', 'rm', SEED], check=False)
    if network_created:
        run(['docker', 'network', 'rm', NETWORK], check=False)
