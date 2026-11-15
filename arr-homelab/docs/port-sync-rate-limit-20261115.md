# Port synchronization and 1Password rate limits

Read-only inspection of ddocker on November 15 found
`arr-qbit-port-sync.service` failing with a 1Password CLI `Too many requests`
error. The helper reported only a missing managed field, masking the actual
quota failure. Its timer retried every minute and continued issuing managed
credential reads during the limit.

At inspection, the tunnel was healthy on CA Montreal, qBittorrent remained
bound to `tun0`, and its listening port matched Gluetun's current forwarded
port. An external TCP probe reached that port, and a 5 MB HTTPS transfer
through the VPN achieved approximately 8.8 MB/s. The observed failure did not
establish a current port mismatch or a general VPN outage. The rate-limit
error does not establish that this timer alone exhausted the account quota.

The timer now checks every fifteen minutes with up to thirty seconds jitter,
reducing recurring managed reads by approximately 93%. The helper classifies
the rate-limit error without printing raw CLI output or credentials. It still
refuses mutations when managed authentication fails, and still validates VPN
health and the `tun0` binding before any listening-port change.

The tradeoff is up to fifteen minutes thirty seconds to synchronize a port
after a VPN session changes. Outbound connections remain available through
the VPN during that interval. No reusable password, cookie, or authentication
token is persisted as a new cache.

## Verification and approved publication

Three local HTTP/authentication tests pass, including a quota error that fails
closed and does not expose fixture private error details. Systemd unit syntax
was verified locally with a stub Docker service dependency. Production
activation remains unverified until the existing quota window resets.

After owner approval, back up the current helper and timer, install these two
files, run `systemctl daemon-reload`, and restart only the port-sync timer.
Do not recreate Gluetun, qBittorrent, or the ARR stack for this repair. Confirm
the next timer cadence. After the quota window resets, observe one successful
scheduled run and compare the actual listening and forwarded ports through
an authenticated API diagnostic. Do not repeatedly force failed managed reads.

If a changed port needs immediate synchronization during a confirmed quota
outage, use an explicitly approved supported qBittorrent API operation after
verifying the VPN, current assignment, and scope. Do not disable authentication
or the kill switch. Roll back the saved helper/timer and reload systemd if
necessary; restoring minute polling reintroduces the excess-read behavior.
