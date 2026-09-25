# FloodCast — Interview Day Guide (laptop is the backend)

## The setup in one paragraph
The backend runs on **your laptop**, not Render. Render stays as a backup/demo mirror.
Your laptop holds the database (persists across restarts), fetches yesterday's river
data on boot, and serves predictions. The website (Vercel) talks to whichever backend
URL you set.

## What to do when

### Night before
1. Plug in power. Set sleep to Never while plugged in (Settings → Power).
2. Connect to stable Wi-Fi (phone hotspot works as backup — note its name).
3. Double-click `start_local.bat`. Wait for `🌊 Flood Prediction system fully initialized!`
   then `anchor result: ...` (takes ~1–2 min first boot — it downloads yesterday's data).
4. Open `http://localhost:8000/stations` — you should see ~378 stations.
5. Run one district Master Predict from the dashboard to warm the chain. Done — lid can close
   (set "do nothing when lid closed while plugged in") or leave open.

### Morning of interview (30 min before)
1. Wake laptop, confirm Wi-Fi.
2. If backend window is closed, double-click `start_local.bat` again (restart is safe:
   seeding is skipped, migrations re-apply harmlessly, anchor check finishes in seconds
   when data is fresh).
3. Check `http://localhost:8000/` → `{"status":"ok",...}`.
4. Open the site, run one station prediction to confirm numbers flow.

### If interviewers are remote (not in the room)
- Easiest: **share your screen** and drive the dashboard yourself.
- If they must click it themselves, expose the laptop (verified working):
  ```bat
  cloudflared tunnel --url http://localhost:8000
  ```
  Copy the `https://<random>.trycloudflare.com` URL it prints, set Vercel env
  `VITE_API_URL` to it, redeploy frontend in Vercel dashboard, then open the site
  and run one prediction to confirm. Caveats: the URL changes every tunnel restart
  (redo the Vercel step), and keep both the backend window AND the tunnel window open.

## What happens when the backend starts
1. Tables + migrations ensured (safe to re-run).
2. Seeds 367 stations only if the database is empty (normally skipped — your data stays).
3. In the **background** (boot never waits): guarantees the anchor is never older than
   the Sept floor (instant check, no heavy downloads on boot — free-tier RAM is limited).
   Fresh latest-date pulls run from the laptop/CLI. Watch for
   `anchor result: {'status': 'present'|'anchored', ...}`.
4. Starts the 6AM scheduler. Serves immediately at `http://localhost:8000`.

## How Render fits in
- Render = fallback mirror. It sleeps when idle (first click takes ~1 min to wake),
  wipes its database on redeploys, and needs laptop pushes to function.
- If the laptop backend ever fails mid-interview: switch `VITE_API_URL` back to
  `https://floodcast-backend-vx1j.onrender.com`, wake it by opening the URL once,
  wait a minute, continue demo on slightly older data. Mention it as
  "edge deployment" — it sounds intentional.

## Keep-alive checklist (maximum uptime)
- [ ] Charger plugged in, sleep = Never (plugged in), lid-close = Do nothing
- [ ] Windows Update paused (Settings → pause updates for 7 days)
- [ ] Close Chrome tabs / heavy apps; keep only backend window + demo browser
- [ ] Notifications on Silent / Do Not Disturb; disable screensaver lock if possible
- [ ] Backend console window left OPEN (closing it stops the server)
- [ ] Phone hotspot name/password noted as backup Wi-Fi
- [ ] One full dry run the night before (Master Predict end-to-end)

## Emergency lines (say calmly, all true)
- Data stale? "The anchor pipeline pulls the latest published GloFAS run — it publishes
  with a ~2-day lag, so the model always chains from the freshest available actual."
- Weird number? "Let me show the confidence path — every forecast carries its anchor date
  and model version, so nothing is a black box."
- Backend down? Switch to the Render mirror (above) and continue.
