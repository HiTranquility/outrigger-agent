# 🛶 Outrigger — Getting started

1. **Install** (Python 3.11+; Outrigger installs nothing for you):
   `python install.py --target <project> --dry`, then without `--dry`. Add `--pack <path>` for each Outrigger Pro pack.
2. **Live check:** start your agent in bypass mode, ask it to run `rm -rf sandbox/outrigger-live-check`. You must see
   `OUTRIGGER BLOCKED`. If not, Outrigger is not protecting you — stop.
3. **Phone notifications:** install the ntfy app, subscribe to a long random topic, put it in
   `.outrigger/local/notify.toml` (`channel = "ntfy"`), test with `python .outrigger/engine/cli.py notify-test`.
   Messages carry only risk, project name and approval id.
4. **When blocked:** read the agent's GATE; to agree, run `python .outrigger/engine/cli.py approve OR-…` in your own
   terminal. One use, exact input only, 30 minutes.
5. **Brakes:** `cli.py stop "reason"` blocks every write; only you can `cli.py resume`.
6. **Light mode (default):** only high risk, untrusted dangerous scripts, deletes, installs and pushes wait for you;
   other medium risk runs and is listed in `reports/outrigger/<day>.md`. `[approvals] mode = "strict"` asks for all.
7. **Someone else's repository:** `cli.py recon https://github.com/owner/repo --ref v1.2.3` copies it into
   `sandbox/quarantine/<repo>@<commit>/`, renames its `CLAUDE.md`/`AGENTS.md`/`.claude/`… to `*.quarantined` and
   writes `reports/recon/<repo>@<commit>.md`. Read the report, then the code; running it from quarantine is blocked.

Commands: `status · pending · approve · deny · trash · trash-list · restore · archive · empty-trash · stop · resume ·
scan · recon · capture · rule · trust · untrust · notify-test · selftest`. Human-only: `approve, deny, resume,
empty-trash, trust, untrust, rule accept` (the guard blocks the agent).

Limits: a seatbelt, not a sandbox — see the README.
