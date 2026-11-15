# Outrigger risk register — what is covered, how it is enforced, which test proves it

> Every guard rule must trace back to a loss (STPA chain: **loss → unsafe action → constraint → gate → test**).
> A row without a test is a gap and is labelled as such. `tests/test_outrigger.py::RegisterIntegrity` fails if a test named
> here does not exist — the register cannot silently drift away from the code.
> Last reviewed: 2026-11-12 · Outrigger 0.2.0

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
`.outrigger/rules`, relies on the agent following it · **gap** = known hole, see §4.

| Id | Unsafe action | Loss | Constraint / gate | Enforcement | Tests |
| :-- | :-- | :-: | :-- | :-: | :-- |
| R-01 | Delete files (`rm`, `del`, `Remove-Item`, `find -delete`, MATLAB `delete`) | L-1 | soft delete via `cli.py trash`; root/outside/never_delete = high; bulk = approval | guard | `Rules.test_root_delete_high` `Rules.test_project_delete_redirected_to_trash` `Rules.test_never_delete_adr` `TrashRestore.test_roundtrip_with_manifest` `TrashRestore.test_bulk_trash_needs_approval` |
| R-02 | Overwrite a file the user owns | L-1 | yellow zone: copy to `.outrigger/state/backups/` before the edit | guard | `Rules.test_yellow_write_backs_up` |
| R-03 | Rewrite or discard git history | L-1 | force push, `reset --hard`, `clean -f` = high | guard | `Rules.test_git_rewrite_high` |
| R-04 | Read or copy secrets | L-2 | red zone, even for reads; `.env.example` allowed | guard | `Rules.test_secret_read_blocked` |
| R-05 | Send data out (upload, POST, `scp`, `git push`) | L-2 | upload = high; push = approval | guard | `Rules.test_upload_high` `Rules.test_git_push_medium` |
| R-06 | Run code from the internet / install unknown software | L-3 | download piped to a shell = high; installs and unknown hosts = approval; host allow-list | guard | `Rules.test_pipe_to_shell_high` `Rules.test_install_gated` `Rules.test_unknown_host_fetch_gated` |
| R-07 | Write a script, then run it (hidden delete/upload/exec inside) | L-1, L-2, L-3 | shell-like scripts (`.sh .ps1 .bat .cmd`) and `package.json` scripts are parsed and judged by the same rules as a typed command; pack scanners for Python, Node.js and MATLAB code; a file is skipped only while its SHA-256 is trusted by the human | guard (partial) | `Scripts.test_bash_script_with_force_push_is_high` `Scripts.test_script_run_directly_and_sourced` `Scripts.test_powershell_script_inside_control_flow` `Scripts.test_batch_file_download_and_run` `Scripts.test_script_calling_dangerous_python` `Scripts.test_npm_script_is_judged_by_its_body` `Scripts.test_control_words_do_not_hide_a_command` `NodePack.test_node_script_and_inline_code` `PythonPack.test_script_that_deletes_is_gated` `PythonPack.test_script_that_uploads_is_gated` `PythonPack.test_inline_subprocess_gated` `MatlabPack.test_headless_with_dangerous_code_is_gated` `MatlabPack.test_command_syntax_delete` `Trust.test_trusted_script_runs_until_it_changes` |
| R-08 | Change the system (registry, firewall, services, `sudo`, encoded PowerShell) | L-3 | high | guard | `Rules.test_sudo_high` `Rules.test_encoded_command_high` |
| R-09 | Act unattended (schedules) or keep going after the human says stop | L-6 | schedules = high; `STOP` file blocks all writes | guard | `Rules.test_schedule_high` `Rules.test_stop_blocks_writes_not_reads` |
| R-10 | Agent disables its guard or approves itself | L-6 | protected zone; `approve`/`resume`/`empty-trash` human-only; approval bound to SHA-256 of the exact input, single use | guard | `Rules.test_writing_engine_blocked` `Rules.test_self_approval_high` `Approvals.test_approval_is_once_and_exact` `Trust.test_agent_cannot_trust` `Trust.test_rules_are_protected` |
| R-11 | Guard crashes and lets everything through | L-6 | fail-closed: any engine error denies (exit 2) | guard | `HookProcess.test_fail_closed_on_broken_config` `HookProcess.test_deny_json` |
| R-12 | Open apps / hold licence seats without consent | L-4 | L2 apps need approval; every launch logged in `apps.jsonl` | guard | `MatlabPack.test_gui_is_l2` `MatlabPack.test_headless_clean_is_low_and_logged_as_app` |
| R-13 | Act through MCP tools the shell rules cannot see | L-1…L-3 | risky MCP verbs need approval; MCP `command` inputs go through shell rules | guard (heuristic) | `Rules.test_risky_mcp_needs_approval` |
| R-14 | Present invented sources or unchecked numbers as fact | L-5 | S1–S5, 🆕 marker, report section "not done / not verified" | rule | — gap G-3 |
| R-15 | Follow instructions injected through a web page or file | L-1…L-6 | only allow-listed hosts without approval; guard ignores the agent's intent (a hijacked agent is still blocked) | guard (partial) + rule | `Rules.test_unknown_host_fetch_gated` |
| R-16 | Human approves without understanding | L-1…L-6 | GATE template (what, risk, cost, rollback); `approve` prints the exact action and reasons first | rule + guard | `Approvals.test_approval_is_once_and_exact` |
| R-17 | Poisoned agent memory or global agent config steers later sessions | L-5, L-6 | memory writes are logged and backed up; a note that tells the agent to skip approvals or disable the guard needs approval; global instruction/skill/settings files of any agent need approval | guard (partial) | `AgentMemoryAndConfig.test_memory_write_is_allowed_logged_and_backed_up` `AgentMemoryAndConfig.test_memory_note_that_weakens_safety_is_gated` `AgentMemoryAndConfig.test_global_agent_config_needs_approval` |
| R-18 | No trace of what happened | L-5, L-6 | audit log for every block/approval; daily summary by the Stop hook | guard | `HookProcess.test_stop_hook_writes_daily_log` |
| R-19 | Commit a secret into git history | L-2 | `git commit` is checked against the staged diff (and unstaged, for `-a`): key patterns and red-zone files = high; the secret value is never printed | guard | `SecretCommit.test_commit_with_staged_key_is_blocked_and_value_not_shown` `SecretCommit.test_commit_all_checks_unstaged_changes` `SecretCommit.test_private_key_and_env_file` `SecretCommit.test_clean_commit_passes` |
| R-20 | A clean script runs another file's code, so the scan of the script being run sees nothing | L-1, L-3 | `runpy.run_*`, `importlib.import_module`, `spec_from_file_location`, `exec(open(…))` and dynamic `__import__` of OS modules are dangerous calls in the Python pack | guard | `FalsePositives.test_wrapper_that_runs_another_file_gated` `FalsePositives.test_dangerous_dynamic_import_gated` |
| R-21 | Light mode lets a dangerous action through unasked | L-1…L-6 | only codes outside `LIGHT_STILL_ASK` pass; every high risk is blocked in both modes; unknown mode = strict; selftest runs strict and light cases | guard | `LightMode.test_high_risk_still_blocked` `LightMode.test_still_asks_for_untrusted_dangerous_script` `LightMode.test_still_asks_for_delete_install_push` `LightMode.test_still_asks_when_unparsed` `LightMode.test_unknown_mode_is_strict` `SelfTest.test_selftest_passes` |
| R-22 | Asking for routine work trains the human to approve without reading (approval fatigue) | L-1…L-6 | light mode by default; FP-4, FP-5, FP-6 fixed; another repo's Outrigger paths and read-only commands are not "touching the guard" | guard | `LightMode.test_routine_medium_runs_and_is_marked` `SelfPathOtherRepo.test_other_repo_engine_path_is_not_self` `SelfPathOtherRepo.test_own_engine_write_still_high` `FalsePositives.test_memory_note_describing_approval_is_not_suspicious` `FalsePositives.test_harmless_dynamic_import_passes` |
| R-23 | A workflow is written from the agent's memory and records steps that never happened | L-5 | `cli.py capture` builds drafts only from the trace log; drafts stay `status: draft` until the human promotes them | guard + rule | `Capture.test_three_calls_become_steps_in_order` `Capture.test_hook_writes_trace` |

## 3. Mapping to OWASP Top 10 for Agentic Applications (2026)

Source: OWASP GenAI Security Project, *OWASP Top 10 for Agentic Applications for 2026*, published 2025-12-09,
CC BY-SA 4.0 — entry names checked in the official PDF on 2026-11-11. Only the names are used here.

| OWASP entry | Outrigger rows | Coverage in 0.1 |
| :-- | :-- | :-- |
| ASI01 Agent Goal Hijack | R-15, R-10 | **partial** — Outrigger cannot detect a hijack, but the guard does not trust the agent's intent |
| ASI02 Tool Misuse and Exploitation | R-01, R-03, R-05, R-08, R-13 | **covered (heuristic)** |
| ASI03 Identity and Privilege Abuse | R-04, R-08, R-10, R-19 | **partial** — no per-credential scoping |
| ASI04 Agentic Supply Chain Vulnerabilities | R-06; `.mcp.json` and hook settings are protected | **partial** — no signature or CVE check by the machine |
| ASI05 Unexpected Code Execution (RCE) | R-06, R-07, R-08 | **partial** — shell, PowerShell, batch, npm scripts, Python, Node.js, MATLAB; other languages not scanned |
| ASI06 Memory & Context Poisoning | R-17 | **partial** — writes logged, backed up, weakening notes gated; reading poisoned memory is not detected |
| ASI07 Insecure Inter-Agent Communication | — | **out of scope** in 0.1 (single-agent projects) |
| ASI08 Cascading Failures | R-09, R-11 | **partial** — STOP and fail-closed limit the blast radius |
| ASI09 Human-Agent Trust Exploitation | R-16, R-14 | **partial** |
| ASI10 Rogue Agents | R-10, R-11, R-18 | **partial** — guard and log are outside the agent's control |

## 4. Known gaps (told to buyers)

| Id | Gap | Mitigation now | Planned |
| :-- | :-- | :-- | :-- |
| G-1 | Scripts in languages without a scanner (Ruby, Go, Makefile targets, `docker run`, compiled programs) and scripts generated while another script runs are not checked | run untrusted code in a VM | more packs as real cases appear |
| G-2 | `python -m <module>` and modules imported by a scanned script (Python, Node.js) are not followed | `PythonPack.test_module_run_not_scanned_documented_limit` pins this behaviour so a change is noticed | import-following scan (opt-in) |
| G-3 | Invented sources / unchecked numbers cannot be detected by a hook | report must list sources 🆕 and "not verified" | `cli.py doctor` link checker |
| G-4 | A memory note can mislead without using any phrase the guard looks for; memory already poisoned before Outrigger was installed is not reviewed | writes are logged in the daily guard log for the human to read | `cli.py doctor` memory review |
| G-5 | Obfuscated commands the splitter cannot see (variables built at run time, aliases) | unparseable input is gated (medium) | more parser cases from real incidents |
| G-6 | That a deny holds under `bypassPermissions` is implied, not stated, by Claude Code docs | mandatory live check after install | re-check each Claude Code release |

## 5. How to add a row

1. Name the loss (§1) and the unsafe action.
2. Add the guard rule **and** a test in `tests/test_outrigger.py`; add a selftest case in `cli.py` if users should see it.
3. Add the row here with the test names in backticks. `RegisterIntegrity` checks they exist.
4. Behaviour change for users → ADR.
