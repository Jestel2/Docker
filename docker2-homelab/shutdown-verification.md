# SQL shutdown verification — 2026-11-11

The live 16.0.4260.1 engine completed T-SQL SHUTDOWN in seconds and exited 255. Docker events recorded a die event with exitCode 255 and no kill event for SQL. Its errorlog ended with `Server shut down by request from login sa.` and SQL Trace shutdown; Service Broker and .NET had shut down. The original engine and DVLS recovered and passed DBCC CHECKDB and app checks after the overly strict exit-0 gate refused that stop.

For this verified image, require completed supported SHUTDOWN, the requested-shutdown log marker, no running engine, no OOM kill, and the observed exit 0 or 255 before cold cloning. Do not accept Docker timeout/SIGKILL/exit137, OOM, or unrelated exits. Preserve original data and image; recovery uses those unchanged originals. Controller systemd exit 0 remains required for final completion.
