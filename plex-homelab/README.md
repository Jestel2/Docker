# Plex container maintenance — 2026-11-10

The live stack is `/opt/stacks/plextacular/compose.yaml`; its sole service is Plex. Jellyfin and Plextreme run separately. The current server is 1.43.4.10903-e5521bd8c; the reviewed target is 1.43.5.11079-b3b13e506, pinned to the amd64 manifest in this overlay.

Apply the image overlay to the existing live Compose file and compare their renderings privately: only the Plex image may differ. Preserve host networking, user/group settings, claim configuration and all five mounts. Keep the configured Plex library identity. Do not print or copy Plex authentication values.

Before replacing Plex, pull the pinned image, verify its binary version without attaching library data, retain the old image ID and take database recovery points using the bundled Plex SQLite tool. Preserve both the library and blobs databases; verify the backup operation and integrity using Plex's own SQLite build. Confirm media mounts before startup. Do not copy or modify media libraries.

Stop only Plex for replacement. Start the candidate with the unchanged live mounts and settings, then require its health check, identity version and unchanged library identity. Verify library availability and playback through the intended client where available. An HTTP response alone does not prove playback. Persist the pinned image in the existing Compose after recovery checks pass; the override is a reviewed image selection, not a replacement stack layout.

Preserve the old image and database recovery points until normal post-maintenance backups are verified. A database schema change can require restoring the older database before using the older image. Do not prune images, delete volumes, or alter Jellyfin/Plextreme. Preparation and Git merge do not establish production rollout.
