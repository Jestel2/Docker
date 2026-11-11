# Keep application and runtime maintenance — 2026-11-11

Production API is0.54.3/Python3.13.5, custom UI Node24.22.1. The pinned API candidate is0.55.0 and the UI is the currently published matching upstream artifact. Derived images retain those upstream application files and move the runtimes to Python3.13.18 and Node24.22.2 on patched Alpine3.23. All sources are pinned by registry digest; application data and credentials must never enter a build context.

Official runtime releases: https://www.python.org/downloads/release/python-31318/ and https://nodejs.org/en/blog/release/v24.22.2. Refresh published security releases again before rollout; a scheduled release is not a published patch.

Build as local/keep-api:0.55.0-python3.13.18-20261111 and local/keep-ui:node24.22.2-20261111. API keeps the existing Python minor/musl ABI, service user1000 and startup/background job behavior. UI keeps service user1001/group65533 and standalone Next artifacts; its startup requires the existing managed auth secret and logs no secret fragments. API shell tracing is removed. Existing shared-state paths, auth configuration, providers, workflows and websocket settings remain authoritative.

Native SQLite backup/migration on an isolated copy passed with51tables/revision67ff7efffed4 and unchanged1tenant/1user/443alerts/4providers/0incidents/5workflows. Repeat native migration/import/pip checks against the derived runtime, then validate API health and UI/auth routes without production mounts or outbound network. Never run the image entrypoint or workflow workers for the migration-only test. Existing provider-secret files were not copied.

Before production replacement, obtain a fresh native DB backup and integrity checks, compare image-only Compose renderings privately, retain exact previous image IDs and the configured state bind, review/merge the change, and stop only Keep API/UI for replacement. Keep websocket and direct LibreNMS delivery active. Require API/UI readiness, unchanged principal/provider/workflow counts, existing authentication and state mounts, and no failed startup/migration before persisting images. Do not send test notifications without explicit user authorization.

If migration changes schema, rollback requires the verified prior DB snapshot with the original images; do not blindly run old code on changed data. Preserve snapshots and image identities until normal post-maintenance backups pass. Interactive login and provider delivery are separate checks when no user session or notification authorization is available.
