# Deploying the monitor and the nightly job

Two supported hosts: the Mac you develop on (launchd user agents, no sudo) or a small Linux VPS (systemd user
units). Both run the same two things:

- `swing monitor run`, always on, restarted on exit (`scripts/run-monitor.sh`);
- `swing nightly`, 06:30 ET on weekdays (`scripts/run-nightly.sh`; falls back to the step-by-step chain on a
  checkout without the `nightly` command): ingest -> features -> scan -> rank -> size -> review -> positions ->
  execute -> journal.

The monitor never submits orders. The nightly does, on the **paper** account only, as shipped
(`execution.broker: alpaca`, `execution.nightly_execute: true`, `ALPACA_PAPER=true`): its execute step is the
autopilot (`docs/OPERATIONS.md` section 1.1), approved as `autopilot:paper`, capped at
`execution.max_new_orders_per_day`, blocked by `state/KILL`. To keep the scheduled run plan-only, set
`execution.nightly_execute: false` or `SWING_NIGHTLY_ARGS="--no-execute"`. A live account is only auto-traded
with both `execution.auto_submit_live: true` and `SWING_ALLOW_LIVE=yes` in the unit's environment; do not add
either before the gates in `docs/gates.md` pass.

The scheduled `nightly` reads equity and positions from the broker in `execution.broker`. Without a broker it
sizes against `risk.account_equity_override`, or `SWING_NIGHTLY_ARGS="--equity 100000"` in the unit
(`Environment=`) / the plist's `EnvironmentVariables`; without any of these the size step is skipped and the
log says so.

## Mac vs $6 VPS

| | Mac (launchd) | VPS (systemd), e.g. a 1 vCPU / 1 GB box at ~$6/month |
|---|---|---|
| cost | $0 | ~$6 |
| uptime | only while awake and on the network; sleep kills the websockets and the 06:30 job waits for wake | 24/7; `Persistent=true` catches a missed 06:30 after a reboot |
| secrets | `.env` in the repo (0600) | `.env` (0600) or systemd `LoadCredential` (below) |
| clock | macOS time sync (Settings -> General -> Date & Time); check with `sntp time.apple.com` | install `chrony` (`apt install chrony`, `chronyc tracking`); the latency figures in `swing monitor report` are only meaningful with a synced clock |
| IP | residential: fine for every feed, including the Tier B ones that dislike datacenter IPs | datacenter: Alpaca/EDGAR/Nasdaq are fine; some Tier B sources (Google News RSS, Substack) may throttle |
| time zone | launchd fires in local time; convert if the Mac is not on ET | the timer is written in `America/New_York` and converts itself |
| when to pick | the first two weeks of paper monitoring, and whenever you are at the desk anyway | once you rely on the 06:30 nightly and on P3 alerts for held positions |

Recommendation: start on the Mac for the two-week monitor validation (gate 3), then move the monitor to the
VPS and keep research (`backtest`, `rank`, `review`) on the Mac. Only one monitor at a time: Alpaca allows one
websocket connection per endpoint per key (error `406 connection limit exceeded`), so a Mac monitor and a VPS
monitor on the same paper key cannot coexist; the nightly job uses REST only and never conflicts.

## Mac: launchd user agents

```bash
scripts/install-launchd.sh --dry-run                     # render + plutil-lint both plists, install nothing
scripts/install-launchd.sh                               # install monitor + nightly (idempotent, no sudo)
scripts/install-launchd.sh --nightly --hour 3 --minute 30 # Mac on Pacific time: 03:30 PT = 06:30 ET
scripts/install-launchd.sh --hc-monitor https://hc-ping.com/<uuid-1> --hc-nightly https://hc-ping.com/<uuid-2>
scripts/uninstall-launchd.sh                             # bootout + remove the plists
```

What the installer does: fills `@@REPO_DIR@@`, `@@UV_DIR@@`, `@@HOME@@`, the schedule and the ping URLs in
`deploy/launchd/*.plist`, writes `~/Library/LaunchAgents/com.swing.{monitor,nightly}.plist`, validates with
`plutil -lint`, then `launchctl bootout` (ignored if not loaded) + `bootstrap` + `enable`. Re-running after a
change to `.env`, the scripts or the schedule is the supported way to restart.

Useful commands:

```bash
launchctl print gui/$(id -u)/com.swing.monitor | head -20     # state, pid, last exit status
launchctl kickstart -k gui/$(id -u)/com.swing.monitor         # restart now
launchctl kickstart -k gui/$(id -u)/com.swing.nightly         # run the nightly now
tail -f data/logs/monitor.err.log                             # structlog goes to stderr
```

Details that bite:

- **Sleep.** A sleeping Mac has no websockets. Settings -> Energy (or Battery -> Options) -> "Prevent automatic
  sleeping when the display is off" while on power, or schedule a wake before 06:30 with
  `sudo pmset repeat wakeorpoweron MTWRF 06:25:00`. launchd runs a missed `StartCalendarInterval` on wake, but
  not a job missed while powered off.
- **PATH.** launchd does not read your shell profile. The plist sets `PATH` to the directory that holds `uv`
  plus Homebrew; if `uv` moves, re-run the installer.
- **Logs** are appended forever under `data/logs/`. Rotate by hand: `uninstall --keep-files`, move the file,
  `install`.
- **Full Disk Access.** If the repo lives under `~/Desktop` or `~/Documents`, macOS may deny the agent access
  to it; move the repo to `~/swing-engine` or grant `bash` Full Disk Access in Privacy & Security.
- **Signals.** `bootout`/`kickstart -k` send SIGTERM; the monitor drains for up to 30 s. `ExitTimeOut` is 90 s
  before launchd escalates to SIGKILL.

## VPS: systemd user units

```bash
# once, as the user that owns the checkout (assumed at ~/swing-engine; edit the units if elsewhere)
sudo apt install chrony sqlite3 curl && sudo loginctl enable-linger "$USER"   # the only two root steps
curl -LsSf https://astral.sh/uv/install.sh | sh && uv sync --extra dev
mkdir -p ~/.config/systemd/user data/logs
cp deploy/systemd/swing-monitor.service deploy/systemd/swing-nightly.service deploy/systemd/swing-nightly.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now swing-monitor.service swing-nightly.timer
systemctl --user list-timers swing-nightly.timer      # next fire shown in local time, computed from 06:30 ET
systemctl --user status swing-monitor                 # Restart=always, RestartSec=15
systemctl --user start swing-nightly.service          # run the nightly right now
```

`loginctl enable-linger` is what lets user units run without an open SSH session; without it the monitor
stops when you log out.

### Secrets: `.env` or `LoadCredential`

The application reads `<repo>/.env` (pydantic-settings) and does not read `$CREDENTIALS_DIRECTORY` itself.
On a single-user VPS a `chmod 600 .env` is adequate. If you prefer systemd credentials (file never readable by
other services, not visible in `systemctl show`):

1. Put each secret in its own file under `~/.config/swing/` (mode 0600), e.g. `alpaca_key`, `alpaca_secret`,
   `anthropic_key`, `telegram_token`.
2. Uncomment the `LoadCredential=ID:PATH` lines in `swing-monitor.service` (and the Anthropic one in
   `swing-nightly.service`). At runtime systemd exposes each as `$CREDENTIALS_DIRECTORY/<ID>`. User-level
   `LoadCredential` needs systemd >= 250 (Debian 12, Ubuntu 22.04 and newer).
3. Bridge them into the environment the app reads, since the app wants `ALPACA_API_KEY` etc.: add an
   `ExecStartPre`-free wrapper, e.g. change `ExecStart` to

   ```
   ExecStart=/bin/bash -c 'export ALPACA_API_KEY="$(cat "$CREDENTIALS_DIRECTORY/alpaca_key")" ALPACA_SECRET_KEY="$(cat "$CREDENTIALS_DIRECTORY/alpaca_secret")" ANTHROPIC_API_KEY="$(cat "$CREDENTIALS_DIRECTORY/anthropic_key")" TELEGRAM_BOT_TOKEN="$(cat "$CREDENTIALS_DIRECTORY/telegram_token")"; exec %h/swing-engine/scripts/run-monitor.sh'
   ```

   Environment variables override `.env` values in pydantic-settings, so `.env` can then hold only the
   non-secret entries (`ALPACA_PAPER=true`, `EDGAR_USER_AGENT`, `TELEGRAM_CHAT_ID`).
4. `LoadCredentialEncrypted=` (with `systemd-creds encrypt`) ties the file to the host's TPM/secret; use it on a
   shared box. `SetCredential=` inlines the value in the unit file and is only for non-secrets.

### Hardening in the units

`ProtectSystem=strict` makes the filesystem read-only except `ReadWritePaths` (`data/`, `state/`, the uv
cache). If you move the repo or the uv cache, update those lines or the service fails with a permission error
at the first write. `PrivateTmp`, `NoNewPrivileges` cost nothing.

## healthchecks.io dead-man pings (free: 20 checks, 100 log entries each)

Create two checks at https://healthchecks.io (verify: https://healthchecks.io/docs/): **swing-nightly** with a
period of 1 day and a grace of 2 hours, schedule-based (`30 6 * * 1-5`, time zone `America/New_York`), and
**swing-monitor** with a period of ~2 days (it only pings on start and exit). Both wrappers send
`<url>/start` before the work, `<url>` on success and `<url>/fail` on a non-zero exit; the URL comes from
`HEALTHCHECKS_URL` (set by the launchd installer flags or `Environment=` in the units). Point the check's
notifications at the same Telegram chat so a silent 06:30 reaches your phone through a path that does not
depend on the engine.

The monitor ping says "the process started/stopped", not "the feeds are alive"; feed liveness is the in-process
watchdog, which raises a P3 when a feed is stale during market hours.

## Time, DST and the 06:30 schedule

- The nightly must finish before the 08:30 ET digest and start after the 18:00 ET FINRA files and the
  overnight EDGAR filings; 06:30 ET is the compromise, with 2 hours of slack for a slow Massive refresh.
- **systemd**: `OnCalendar=Mon..Fri *-*-* 06:30:00 America/New_York` moves with US DST on its own
  (systemd.time(7) accepts an IANA zone at the end of a calendar spec). The box itself can stay on UTC.
- **launchd**: `StartCalendarInterval` has no time-zone field; it fires at 06:30 in the Mac's zone. A Mac on ET
  needs nothing. A Mac in another zone needs `--hour/--minute` and a manual change at each DST transition
  if its zone and ET do not switch on the same dates (Arizona, Europe, most of Asia).
- Market holidays: the nightly runs anyway (ingest finds nothing new, scan reuses the last session); it is
  cheap and keeps the healthcheck honest. The monitor's watchdog knows NYSE holidays and early closes.
- `chrony` on the VPS; on the Mac keep automatic time. Alert latency is measured against source timestamps.

## One Alpaca socket per endpoint

Alpaca permits one websocket connection per data endpoint per key (`wss://stream.data.alpaca.markets/v2/iex`,
`.../v1beta1/news`, `wss://paper-api.alpaca.markets/stream`). A second connection is refused with
`406 connection limit exceeded` and the first can be bumped. Therefore:

- exactly one `swing monitor run` per key: never a Mac and a VPS instance together, never a second terminal
  with `--feeds alpaca_news` "just to look";
- the nightly job, `swing size --broker alpaca` and `swing paper` use REST only and are safe at any time;
- for experiments, create a second paper account (Alpaca allows several) and a second `.env`, or use
  `swing monitor run --dry-run`, which replays a file and opens no sockets.

## Upgrading the code under a running service

```bash
git pull && uv sync --extra dev && uv run pytest -q         # tests first, no network
touch state/KILL                                              # no orders while restarting
scripts/install-launchd.sh            # or: systemctl --user restart swing-monitor
uv run swing status && rm state/KILL
```
