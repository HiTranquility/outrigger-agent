# Keel risk register — what is covered, how it is enforced, which test proves it

> Every guard rule must trace back to a loss (STPA chain: **loss → unsafe action → constraint → gate → test**).
> A row without a test is a gap and is labelled as such. `tests/test_keel.py::RegisterIntegrity` fails if a test named
> here does not exist — the register cannot silently drift away from the code.
> Last reviewed: 2026-11-11 · Keel 0.1.0

## 1. Losses we protect against

| Id | Loss |
| :-- | :-- |
| L-1 | User data or work lost (deleted, overwritten, history rewritten) |
| L-2 | Secrets or private data leave the machine |
| L-3 | The computer or its security settings are changed or compromised |
| L-4 | Money, licence seats or time spent without consent |
| L-5 | A wrong result is trusted (invented source, unchecked number, "done" without evidence) |
| L-6 | The human loses control (agent acts unattended, approves itself, disables its guard) |

## 2. Risks, controls and evidence

Enforcement: **guard** = blocked by the hook whatever the agent decides · **rule** = written in `AGENTS.md` /
`.keel/rules`, relies on the agent following it · **gap** = known hole, see §4.

| Id | Unsafe action | Loss | Constraint / gate | Enforcement | Tests |
| :-- | :-- | :-: | :-- | :-: | :-- |
| R-01 | Delete files (`rm`, `del`, `Remove-Item`, `find -delete`, MATLAB `delete`) | L-1 | soft delete via `cli.py trash`; root/outside/never_delete = high; bulk = approval | guard | `Rules.test_root_delete_high` `Rules.test_project_delete_redirected_to_trash` `Rules.test_never_delete_adr` `TrashRestore.test_roundtrip_with_manifest` `TrashRestore.test_bulk_trash_needs_approval` |
| R-02 | Overwrite a file the user owns | L-1 | yellow zone: copy to `.keel/state/backups/` before the edit | guard | `Rules.test_yellow_write_backs_up` |
| R-03 | Rewrite or discard git history | L-1 | force push, `reset --hard`, `clean -f` = high | guard | `Rules.test_git_rewrite_high` |
| R-04 | Read or copy secrets | L-2 | red zone, even for reads; `.env.example` allowed | guard | `Rules.test_secret_read_blocked` |
| R-05 | Send data out (upload, POST, `scp`, `git push`) | L-2 | upload = high; push = approval | guard | `Rules.test_upload_high` `Rules.test_git_push_medium` |
| R-06 | Run code from the internet / install unknown software | L-3 | download piped to a shell = high; installs and unknown hosts = approval; host allow-list | guard | `Rules.test_pipe_to_shell_high` `Rules.test_install_gated` `Rules.test_unknown_host_fetch_gated` |
| R-07 | Write a script, then run it (hidden delete/upload/exec inside) | L-1, L-2, L-3 | pack scanners: MATLAB scans all `.m` before `-batch`; Python scans the script named in the command and `-c` code | guard (partial) | `PythonPack.test_script_that_deletes_is_gated` `PythonPack.test_script_that_uploads_is_gated` `PythonPack.test_inline_subprocess_gated` `MatlabPack.test_headless_with_dangerous_code_is_gated` `MatlabPack.test_command_syntax_delete` `Trust.test_trusted_script_runs_until_it_changes` |
| R-08 | Change the system (registry, firewall, services, `sudo`, encoded PowerShell) | L-3 | high | guard | `Rules.test_sudo_high` `Rules.test_encoded_command_high` |
| R-09 | Act unattended (schedules) or keep going after the human says stop | L-6 | schedules = high; `STOP` file blocks all writes | guard | `Rules.test_schedule_high` `Rules.test_stop_blocks_writes_not_reads` |
| R-10 | Agent disables its guard or approves itself | L-6 | protected zone; `approve`/`resume`/`empty-trash` human-only; approval bound to SHA-256 of the exact input, single use | guard | `Rules.test_writing_engine_blocked` `Rules.test_self_approval_high` `Approvals.test_approval_is_once_and_exact` `Trust.test_agent_cannot_trust` `Trust.test_rules_are_protected` |
| R-11 | Guard crashes and lets everything through | L-6 | fail-closed: any engine error denies (exit 2) | guard | `HookProcess.test_fail_closed_on_broken_config` `HookProcess.test_deny_json` |
| R-12 | Open apps / hold licence seats without consent | L-4 | L2 apps need approval; every launch logged in `apps.jsonl` | guard | `MatlabPack.test_gui_is_l2` `MatlabPack.test_headless_clean_is_low_and_logged_as_app` |
| R-13 | Act through MCP tools the shell rules cannot see | L-1…L-3 | risky MCP verbs need approval; MCP `command` inputs go through shell rules | guard (heuristic) | `Rules.test_risky_mcp_needs_approval` |
| R-14 | Present invented sources or unchecked numbers as fact | L-5 | S1–S5, 🆕 marker, report section "not done / not verified" | rule | — gap G-3 |
| R-15 | Follow instructions injected through a web page or file | L-1…L-6 | only allow-listed hosts without approval; guard ignores the agent's intent (a hijacked agent is still blocked) | guard (partial) + rule | `Rules.test_unknown_host_fetch_gated` |
| R-16 | Human approves without understanding | L-1…L-6 | GATE template (what, risk, cost, rollback); `approve` prints the exact action and reasons first | rule + guard | `Approvals.test_approval_is_once_and_exact` |
| R-17 | Poisoned agent memory or notes steer later sessions | L-5, L-6 | memory clean-up = archive + report; agent memory folder outside the project is allowed | rule | — gap G-4 |
| R-18 | No trace of what happened | L-5, L-6 | audit log for every block/approval; daily summary by the Stop hook | guard | `HookProcess.test_stop_hook_writes_daily_log` |

## 3. Mapping to OWASP Top 10 for Agentic Applications (2026)

Source: OWASP GenAI Security Project, *OWASP Top 10 for Agentic Applications for 2026*, published 2025-12-09,
CC BY-SA 4.0 — entry names checked in the official PDF on 2026-11-11. Only the names are used here.

| OWASP entry | Keel rows | Coverage in 0.1 |
| :-- | :-- | :-- |
| ASI01 Agent Goal Hijack | R-15, R-10 | **partial** — Keel cannot detect a hijack, but the guard does not trust the agent's intent |
| ASI02 Tool Misuse and Exploitation | R-01, R-03, R-05, R-08, R-13 | **covered (heuristic)** |
| ASI03 Identity and Privilege Abuse | R-04, R-08, R-10 | **partial** — no per-credential scoping |
| ASI04 Agentic Supply Chain Vulnerabilities | R-06; `.mcp.json` and hook settings are protected | **partial** — no signature or CVE check by the machine |
| ASI05 Unexpected Code Execution (RCE) | R-06, R-07, R-08 | **partial** — only languages with a pack scanner |
| ASI06 Memory & Context Poisoning | R-17 | **gap** (rule only) |
| ASI07 Insecure Inter-Agent Communication | — | **out of scope** in 0.1 (single-agent projects) |
| ASI08 Cascading Failures | R-09, R-11 | **partial** — STOP and fail-closed limit the blast radius |
| ASI09 Human-Agent Trust Exploitation | R-16, R-14 | **partial** |
| ASI10 Rogue Agents | R-10, R-11, R-18 | **partial** — guard and log are outside the agent's control |

## 4. Known gaps (told to buyers)

| Id | Gap | Mitigation now | Planned |
| :-- | :-- | :-- | :-- |
| G-1 | Scripts in languages without a pack (`bash x.sh`, `node x.js`, `.bat`, `.ps1` files) are not scanned | run untrusted code in a VM | shell/node/PowerShell-file packs |
| G-2 | `python -m <module>` and imported modules are not scanned | `PythonPack.test_module_run_not_scanned_documented_limit` pins this behaviour so a change is noticed | import-following scan (opt-in) |
| G-3 | Invented sources / unchecked numbers cannot be detected by a hook | report must list sources 🆕 and "not verified" | `cli.py doctor` link checker |
| G-4 | Agent memory outside the project (`~/.claude/**`) is writable | memory clean-up workflow | optional protection of memory folders |
| G-5 | Obfuscated commands the splitter cannot see (variables built at run time, aliases) | unparseable input is gated (medium) | more parser cases from real incidents |
| G-6 | That a deny holds under `bypassPermissions` is implied, not stated, by Claude Code docs | mandatory live check after install | re-check each Claude Code release |

## 5. How to add a row

1. Name the loss (§1) and the unsafe action.
2. Add the guard rule **and** a test in `tests/test_keel.py`; add a selftest case in `cli.py` if users should see it.
3. Add the row here with the test names in backticks. `RegisterIntegrity` checks they exist.
4. Behaviour change for users → ADR.
