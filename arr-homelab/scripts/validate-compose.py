#!/usr/bin/env python3
"""Validate namespace isolation and management-port ownership in rendered Compose."""
import json
import os
from pathlib import Path
import subprocess
import sys

source = Path(sys.argv[1])
env = dict(os.environ, PIA_USER='validation', PIA_PASS='validation')
result = subprocess.run(['docker', 'compose', '-f', str(source), '--profile', 'maintenance',
                         'config', '--format', 'json'], env=env, capture_output=True, text=True, check=True)
services = json.loads(result.stdout)['services']
assert services['qbittorrent']['network_mode'] == 'service:gluetun'
assert services['flaresolverr']['network_mode'] == 'service:gluetun'
management_ports = {8989, 7878, 9696, 5055}
for name in ('sonarr', 'radarr', 'prowlarr', 'seerr'):
    assert 'network_mode' not in services[name], name
    assert services[name].get('ports'), name
assert not management_ports.intersection(p['target'] for p in services['gluetun']['ports'])
assert not any(p['target'] == 8888 for p in services['gluetun']['ports'])
assert all(p.get('host_ip') == '127.0.0.1' for p in services['cleanuparr']['ports'])
assert services['recyclarr']['profiles'] == ['maintenance']
assert all('@sha256:' in s['image'] for s in services.values())
print('Compose renders; VPN isolation, service ports and image pins verified')
