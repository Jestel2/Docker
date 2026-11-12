#!/usr/bin/env python3
"""Host-side ARR operations; secrets are consumed in memory from 1Password.

Run as root on ddocker. HTTP calls stay on host loopback, and no credential
values or authentication responses are emitted. API mutations use supported
application APIs; this tool never edits a live application database.
"""
import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path('/opt/docker-stacks/arr-stack')
PORTS = {'sonarr': 8989, 'radarr': 7878, 'prowlarr': 9696}
KEYS = {}


def secret(field):
    """Read one managed field without persisting its value or CLI output."""
    if field not in KEYS:
        os.environ['OP_SERVICE_ACCOUNT_TOKEN'] = Path('/etc/1password/arr-stack.token').read_text().strip()
        os.environ['OP_BIOMETRIC_UNLOCK_ENABLED'] = 'false'
        os.environ['OP_CACHE'] = 'false'
        result = subprocess.run(['op', 'read', f'op://JesterTek/ARR Stack/{field}'],
                                capture_output=True, text=True, timeout=25)
        if result.returncode or not result.stdout.strip():
            raise RuntimeError(f'Managed field unavailable: {field}')
        KEYS[field] = result.stdout.strip()
    return KEYS[field]


def http(url, method='GET', payload=None, headers=None, opener=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method,
        headers={'Content-Type': 'application/json', **(headers or {})})
    with (opener.open if opener else urllib.request.urlopen)(req, timeout=35) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def arr(app, path, method='GET', payload=None):
    version = 'v1' if app == 'prowlarr' else 'v3'
    return http(f'http://127.0.0.1:{PORTS[app]}/api/{version}/{path}', method,
                payload, {'X-Api-Key': secret(f'{app.upper()}_API_KEY')})


def fields(resource, values):
    for field in resource['fields']:
        if field['name'] in values:
            field['value'] = values[field['name']]
    return resource


def rewire():
    """Restore cross-service integrations after the management network move."""
    for app in ('sonarr', 'radarr'):
        for client in arr(app, 'downloadclient'):
            if client['implementation'] == 'QBittorrent':
                fields(client, {'host': 'gluetun', 'port': 8080})
                # Secret placeholders are resolved by Arr to its stored credential.
                arr(app, f'downloadclient/{client["id"]}', 'PUT', client)
                arr(app, 'downloadclient/test', 'POST', client)
        print(f'{app}: authenticated downloader integration tested')
    for application in arr('prowlarr', 'applications'):
        app = application['implementation'].lower()
        if app in ('sonarr', 'radarr'):
            fields(application, {'prowlarrUrl': 'http://prowlarr:9696',
                                 'baseUrl': f'http://{app}:{PORTS[app]}',
                                 'apiKey': secret(f'{app.upper()}_API_KEY')})
            arr('prowlarr', f'applications/{application["id"]}', 'PUT', application)
    for proxy in arr('prowlarr', 'indexerproxy'):
        if proxy['implementation'] == 'FlareSolverr':
            fields(proxy, {'host': 'http://gluetun:8191'})
            arr('prowlarr', f'indexerproxy/{proxy["id"]}', 'PUT', proxy)
    host = arr('prowlarr', 'config/host')
    host.update(proxyEnabled=True, proxyType='http', proxyHostname='gluetun',
                proxyPort=8888, proxyBypassLocalAddresses=True,
                proxyBypassFilter='sonarr,radarr,prowlarr,gluetun,localhost,127.0.0.1')
    arr('prowlarr', 'config/host', 'PUT', host)
    command = arr('prowlarr', 'command', 'POST', {'name': 'ApplicationIndexerSync'})
    print(f'Prowlarr application sync queued: {command["id"]}')


def seerr_paths():
    """Change settings only while Seerr is stopped during the guarded rollout."""
    running = subprocess.run(['docker', 'inspect', '--format', '{{.State.Running}}', 'seerr'],
                             capture_output=True, text=True, check=True).stdout.strip()
    if running != 'false':
        raise RuntimeError('Seerr must be stopped before its settings file is changed')
    path = ROOT / 'config/seerr/settings.json'
    config = json.loads(path.read_text())
    for app, root in [('sonarr', '/truenas/Media/TV_Shows'), ('radarr', '/truenas/Media/Videos')]:
        for instance in config.get(app, []):
            instance['hostname'] = app
            if instance.get('isDefault') and not instance.get('is4k'):
                instance['activeDirectory'] = root
    path.write_text(json.dumps(config, indent=2))
    print('Seerr service addresses and default TrueNAS destinations configured')


def recyclarr(preview):
    """Run a disposable container; only this invocation receives Arr credentials."""
    env = dict(os.environ)
    for app in ('SONARR', 'RADARR'):
        env[f'{app}_API_KEY'] = secret(f'{app}_API_KEY')
    command = ['docker', 'compose', 'run', '--rm', '-T', '--no-deps', 'recyclarr', 'sync']
    if preview:
        command.append('--preview')
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def qbittorrent():
    """Authenticate using the central password; never use localhost auth bypass."""
    base = 'http://127.0.0.1:8080'
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    data = urllib.parse.urlencode({'username': 'admin',
                                  'password': secret('QBITTORRENT_WEBUI_PASSWORD')}).encode()
    req = urllib.request.Request(base + '/api/v2/auth/login', data=data,
                                 headers={'Referer': base})
    with opener.open(req, timeout=20) as response:
        if response.read() != b'Ok.':
            raise RuntimeError('Managed qBittorrent authentication rejected')
    return base, opener


def port_sync():
    """Update only the listening port after verifying the VPN and interface binding."""
    health = subprocess.run(['docker', 'inspect', '--format', '{{.State.Health.Status}}', 'gluetun'],
                            capture_output=True, text=True, check=True).stdout.strip()
    if health != 'healthy':
        raise RuntimeError('VPN is not healthy; port synchronization skipped')
    port_file = ROOT / 'config/gluetun/forwarded_port'
    port = int(port_file.read_text().strip())
    if not 1024 <= port <= 65535:
        raise RuntimeError('Invalid VPN forwarded port')
    base, opener = qbittorrent()
    prefs = http(base + '/api/v2/app/preferences', opener=opener)
    if prefs.get('current_network_interface') != 'tun0':
        raise RuntimeError('qBittorrent is not bound to tun0; port sync refused')
    if prefs['listen_port'] != port:
        data = urllib.parse.urlencode({'json': json.dumps({'listen_port': port, 'random_port': False, 'upnp': False})}).encode()
        req = urllib.request.Request(base + '/api/v2/app/setPreferences', data=data,
                                     headers={'Referer': base})
        with opener.open(req, timeout=20) as response:
            response.read()
    actual = http(base + '/api/v2/app/preferences', opener=opener)['listen_port']
    if actual != port:
        raise RuntimeError('Downloader listening port did not match the VPN port')
    print(f'VPN/downloader listening port verified: {port}')


def cleanup(live):
    """Bootstrap Cleanuparr with managed admin auth and a conservative queue policy.

    New instances are always configured in dry run first. Live mode requires an
    explicit invocation after checking the dry-run activity. DownloadCleaner and
    failed-import deletion remain disabled to preserve pre-import source files.
    """
    password = secret('CLEANUPARR_ADMIN_PASSWORD')
    # Check downloader auth before creating an account or enabling any cleanup job.
    qbittorrent()
    base = 'http://127.0.0.1:11011/api/'
    status = http(base + 'auth/status')
    if not status['setupCompleted']:
        http(base + 'auth/setup/account', 'POST', {'username': 'admin', 'password': password})
        http(base + 'auth/setup/complete', 'POST', {})
    login = http(base + 'auth/login', 'POST', {'username': 'admin', 'password': password})
    headers = {'Authorization': 'Bearer ' + login['tokens']['accessToken']}
    def call(path, method='GET', payload=None):
        return http(base + path, method, payload, headers)
    general = call('configuration/general')
    general.update(dryRun=True, connectivityCheckEnabled=True,
                   connectivityCheckUrls=['https://www.cloudflare.com', 'https://www.google.com'],
                   strikeInactivityWindowHours=48)
    general['auth']['disableAuthForLocalAddresses'] = False
    call('configuration/general', 'PUT', general)
    for app, version in [('sonarr', 4), ('radarr', 6)]:
        config = call(f'configuration/{app}')
        instance = next((x for x in config.get('instances', []) if x['name'] == app), None)
        payload = {'enabled': True, 'name': app, 'url': f'http://{app}:{PORTS[app]}',
                   'apiKey': secret(f'{app.upper()}_API_KEY'), 'version': version}
        path = f'configuration/{app}/instances'
        call(path + (f'/{instance["id"]}' if instance else ''), 'PUT' if instance else 'POST', payload)
    clients = call('configuration/download_client')['clients']
    client = next((x for x in clients if x['name'] == 'qBittorrent'), None)
    payload = {'enabled': True, 'name': 'qBittorrent', 'typeName': 'qBittorrent',
               'host': 'http://gluetun:8080', 'username': 'admin',
               'password': secret('QBITTORRENT_WEBUI_PASSWORD')}
    call('configuration/download_client' + (f'/{client["id"]}' if client else ''), 'PUT' if client else 'POST', payload)
    call('configuration/download_client/test', 'POST', payload)
    queue = call('configuration/queue_cleaner')
    queue.update(enabled=True, cronExpression='0 0/15 * * * ?', downloadingMetadataMaxStrikes=0,
                 processNoContentId=False, failedImport={'maxStrikes': 0}, errored={'maxStrikes': 96, 'ignorePrivate': True, 'deletePrivate': False})
    for rule in call('queue-rules/stall'):
        rule['enabled'] = False
        call(f'queue-rules/stall/{rule["id"]}', 'PUT', rule)
    rule = {'name': 'Public downloads stalled for 24 hours', 'enabled': True,
            'maxStrikes': 96, 'privacyType': 'Public', 'minCompletionPercentage': 0,
            'maxCompletionPercentage': 99, 'resetStrikesOnProgress': True,
            'deletePrivateTorrentsFromClient': False, 'changeCategory': False}
    existing = next((x for x in call('queue-rules/stall') if x['name'] == rule['name']), None)
    call('queue-rules/stall' + (f'/{existing["id"]}' if existing else ''), 'PUT' if existing else 'POST', rule)
    call('configuration/queue_cleaner', 'PUT', queue)
    if live:
        general['dryRun'] = False
        call('configuration/general', 'PUT', general)
    print('Cleanuparr queue policy configured: ' + ('live' if live else 'dry run'))


def check():
    report = {}
    for app, endpoint in [('sonarr', 'series'), ('radarr', 'movie')]:
        profiles = arr(app, 'qualityprofile')
        for profile in profiles:
            if profile['upgradeAllowed']:
                raise RuntimeError(f'{app} profile {profile["name"]} allows upgrades')
            def inspect(items):
                for item in items:
                    if item.get('items'):
                        inspect(item['items'])
                    elif item['allowed'] and any(x in item['quality']['name'].lower() for x in ('remux', 'raw-hd')):
                        raise RuntimeError(f'{app} has an allowed Remux/Raw-HD quality')
            inspect(profile['items'])
        report[app] = {'library_count': len(arr(app, endpoint)),
                       'profiles': len(profiles), 'no_upgrades_or_remux': True}
        for client in arr(app, 'downloadclient'):
            if client['implementation'] == 'QBittorrent':
                arr(app, 'downloadclient/test', 'POST', client)
        report[app]['downloader_test'] = 'passed'
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['rewire', 'seerr-paths', 'recyclarr', 'port-sync', 'cleanup', 'check', 'qbit-auth'])
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'recyclarr': recyclarr(args.preview)
        elif args.action == 'cleanup': cleanup(args.live)
        elif args.action == 'qbit-auth': qbittorrent(); print('Managed downloader authentication passed')
        else: {'rewire': rewire, 'seerr-paths': seerr_paths, 'port-sync': port_sync, 'check': check}[args.action]()
    except urllib.error.HTTPError as exc:
        # Response bodies may contain secrets. Emit only the status and action.
        print(f'{args.action}: application returned HTTP {exc.code}', file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'{args.action}: {exc}', file=sys.stderr)
        sys.exit(1)

