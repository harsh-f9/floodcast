# STATE

- Milestone: v2-prod-harden
- Hosting decision: LAPTOP PRIMARY, Render fallback mirror (user-approved).
- Boot-anchor live: `anchor_db_for_yesterday()` in baseflow_glofas + background AnchorThread in startup (DRY_RUN-aware, never blocks/crashes boot). Verified: idempotent skip (temp DB), live resolve 09-22 present zero-writes, full local uvicorn boot (health/stations/station-0 200, scheduler + alerts mounted, anchor in background).
- Local run: `start_local.bat` (verified), uvicorn installed. `INTERVIEW_GUIDE.md`: night-before, morning-of, remote-access (tunnel + Vercel switch), boot sequence, Render-fallback lines, keep-alive checklist, emergency lines.
- OPS_RUNBOOK.md reframed laptop-first. Local DB still 378 (reseed→367 on wipe).
- Still held: residual percentiles → intervals UI, dummy-API label, ProjectDetail live page, stamp footer, Vercel URL switch (needs tunnel URL at the time).
