# ⚓ Keel — Getting started

1. **Install** (Python 3.11+; Keel installs nothing for you):
   `python install.py --target <project> --dry`, then without `--dry`. Add `--pack <path>` for each Keel Pro pack.
2. **Live check:** start your agent in bypass mode, ask it to run `rm -rf sandbox/keel-live-check`. You must see
   `KEEL BLOCKED`. If not, Keel is not protecting you — stop.
3. **Phone notifications:** install the ntfy app, subscribe to a long random topic, put it in
   `.keel/local/notify.toml` (`channel = "ntfy"`), test with `python .keel/engine/cli.py notify-test`.
   Messages carry only risk, project name and approval id.
4. **When blocked:** read the agent's GATE; to agree, run `python .keel/engine/cli.py approve K-…` in your own
   terminal. One use, exact input only, 30 minutes.
5. **Brakes:** `cli.py stop "reason"` blocks every write; only you can `cli.py resume`.

Commands: `status · pending · approve · deny · trash · trash-list · restore · archive · empty-trash · stop · resume ·
scan · notify-test · selftest`. Human-only: `approve, deny, resume, empty-trash` (the guard blocks the agent).

Limits: a seatbelt, not a sandbox — see the README.
