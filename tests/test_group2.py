"""0.6.0 (ADR-0015): record numbering across month folders and branches; the opt-in file-size gate on git commit."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_outrigger import ENGINE, Project  # noqa: E402

from outrigger import config, records, structure  # noqa: E402


def lines(n: int) -> str:
    return "".join(f"x{i} = {i}\n" for i in range(n))


class GitProject(Project):
    def setUp(self):
        super().setUp()
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.org")
        self.git("config", "user.name", "t")
        self.git("commit", "-q", "--allow-empty", "-m", "root")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.tmp, capture_output=True, text=True)

    def put(self, rel, text):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")

    def cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(self.tmp / ".outrigger" / "engine" / "cli.py"), *args],
                              cwd=self.tmp, capture_output=True, text=True, encoding="utf-8")

    def enable_structure(self, **limits):
        p = self.tmp / ".outrigger" / "outrigger.toml"
        text = p.read_text(encoding="utf-8").replace("enabled = false", "enabled = true", 1)
        for key, value in limits.items():
            text = re.sub(rf"^{key} = \d+$", f"{key} = {value}", text, count=1, flags=re.M)
        p.write_text(text, encoding="utf-8")
        self.cfg = config.load(self.tmp)

    def commit_decision(self, command="git commit -m x"):
        return self.d("Bash", {"command": command})


class NextId(GitProject):
    def test_counts_month_folders_flat_records_and_issue_folders(self):
        self.put("docs/decisions/ADR-0002-old-flat.md", "x")
        self.put("docs/decisions/10-2026/ADR-0007-in-a-month.md", "x")
        self.put("docs/issues/11-2026/ISSUE-004-a-folder/issue.md", "x")
        self.assertEqual(records.next_id(self.cfg, "ADR"), ("ADR-0008", []))
        self.assertEqual(records.next_id(self.cfg, "issue")[0], "ISSUE-005")
        self.assertEqual(records.next_id(self.cfg, "REQ")[0], "REQ-001")

    def test_number_held_by_an_unmerged_branch_is_taken(self):
        self.put("docs/issues/11-2026/ISSUE-004-here/issue.md", "x")
        self.git("branch", "feature/ISSUE-009-2026-11-elsewhere")
        self.assertEqual(records.next_id(self.cfg, "ISSUE")[0], "ISSUE-010")

    def test_same_number_two_slugs_is_reported(self):
        self.put("reports/bugs/11-2026/BUG-003-one.md", "x")
        self.put("reports/bugs/11-2026/BUG-003-two.md", "x")
        rid, warnings = records.next_id(self.cfg, "BUG")
        self.assertEqual(rid, "BUG-004")
        self.assertTrue(warnings and "BUG-003" in warnings[0])

    def test_cli_next_id_and_unknown_type(self):
        self.put("docs/requirements/11-2026/REQ-012-x.md", "x")
        self.assertEqual(self.cli("next-id", "REQ").stdout.strip(), "REQ-013")
        self.assertEqual(self.cli("next-id", "NOPE").returncode, 2)


class StructureGate(GitProject):
    def test_off_by_default_a_big_commit_passes(self):
        self.put("app/big.py", lines(900))
        self.git("add", "app/big.py")
        self.assertTrue(self.commit_decision().allow)

    def test_new_big_file_asks_in_light_mode(self):
        self.set_mode("light")
        self.enable_structure()
        self.put("app/big.py", lines(401))
        self.git("add", "app/big.py")
        d = self.commit_decision()
        self.assertFalse(d.allow)
        self.assertIn("structure-grow", [f.code for f in d.findings])
        self.assertIn("app/big.py lines=401", d.reason(self.cfg))

    def test_baseline_file_may_shrink_not_grow(self):
        self.put("app/old.py", lines(500))
        self.git("add", "app/old.py")
        self.git("commit", "-q", "-m", "old")
        structure.write_baseline(self.cfg, structure.measure_project(self.cfg))
        self.enable_structure()
        self.put("app/old.py", lines(480))
        self.git("add", "app/old.py")
        self.assertTrue(self.commit_decision().allow)
        self.put("app/old.py", lines(501))
        self.git("add", "app/old.py")
        self.assertEqual(self.commit_decision().findings[-1].code, "structure-grow")

    def test_judges_the_index_not_the_disk(self):
        self.enable_structure()
        self.put("app/a.py", lines(10))
        self.git("add", "app/a.py")
        self.put("app/a.py", lines(900))                     # unstaged growth: not part of `git commit`
        self.assertTrue(self.commit_decision().allow)
        self.assertFalse(self.commit_decision("git commit -am x").allow)

    def test_tests_and_generated_files_are_not_measured(self):
        self.enable_structure()
        for rel in ("tests/test_big.py", "web/src/a.test.ts", "web/src/types.d.ts", "db/migrations/0001.py"):
            self.put(rel, lines(900))
            self.git("add", rel)
        self.assertTrue(self.commit_decision().allow)

    def test_constructor_and_use_state_limits(self):
        self.enable_structure(max_ctor_deps=3, max_use_state=2)
        self.put("web/svc.ts", "class S {\n  constructor(@Inject(forwardRef(() => X)) private x: X, private cb: () => void,\n"
                               "    private a: Map<string, number>, private b: B,) {}\n}\n")
        self.put("web/Page.tsx", "const [a] = useState(1)\nconst [b] = React.useState<number>(2)\nconst [c] = useState(3)\n")
        self.put("api/Dto.cs", "public sealed record Dto(int A, int B, int C, int D);\n")
        self.git("add", ".")
        reason = self.commit_decision().reason(self.cfg)
        self.assertIn("web/svc.ts ctor_deps=4", reason)
        self.assertIn("web/Page.tsx use_state=3", reason)
        self.assertNotIn("Dto.cs", reason)

    def test_broken_baseline_fails_closed(self):
        self.enable_structure()
        (self.tmp / structure.BASELINE_REL).write_text("{ broken", encoding="utf-8")
        self.put("app/a.py", lines(5))
        self.git("add", "app/a.py")
        d = self.commit_decision()
        self.assertIn("structure-check-failed", [f.code for f in d.findings])
        self.assertFalse(d.allow)

    def test_agent_cannot_seed_or_edit_the_baseline(self):
        seed = self.d("Bash", {"command": "python .outrigger/engine/cli.py structure --seed"})
        self.assertFalse(seed.allow)
        self.assertTrue(self.d("Bash", {"command": "python .outrigger/engine/cli.py structure --update"}).allow)
        edit = self.d("Write", {"file_path": str(self.tmp / structure.BASELINE_REL), "content": "{}"})
        self.assertFalse(edit.allow)

    def test_cli_seed_once_then_update_only_lowers(self):
        self.put("app/old.py", lines(500))
        self.git("add", "app/old.py")
        self.assertEqual(self.cli("structure", "--seed").returncode, 0)
        self.assertNotEqual(self.cli("structure", "--seed").returncode, 0)
        self.put("app/new.py", lines(450))
        self.git("add", "app/new.py")
        out = self.cli("structure", "--update")
        self.assertNotEqual(out.returncode, 0)                 # a new big file is never added by --update
        base = json.loads((self.tmp / structure.BASELINE_REL).read_text(encoding="utf-8"))["files"]
        self.assertEqual(base, {"app/old.py": {"lines": 500}})
        (self.tmp / "app/new.py").unlink()
        self.git("rm", "-q", "--cached", "app/new.py")
        self.put("app/old.py", lines(420))
        self.assertEqual(self.cli("structure", "--update").returncode, 0)
        base = json.loads((self.tmp / structure.BASELINE_REL).read_text(encoding="utf-8"))["files"]
        self.assertEqual(base, {"app/old.py": {"lines": 420}})


class StructureBypasses(GitProject):
    """Reviewer findings on 0.6.0 (ADR-0015): every way a grown file or a secret slipped past `git commit`."""

    def setUp(self):
        super().setUp()
        self.enable_structure()
        self.put("app/small.py", lines(10))
        self.git("add", "app/small.py")
        self.git("commit", "-q", "-m", "small")
        self.put("app/small.py", lines(900))                 # grown on disk, not staged

    def test_paths_include_only_and_pathspec_file_read_disk(self):
        (self.tmp / "paths.txt").write_text("app/small.py\n", encoding="utf-8")
        for cmd in ("git commit -m x app/small.py", "git commit -m x -- app/small.py", "git commit -o -m x app/small.py",
                    "git commit -i -m x app/small.py", "git commit -m x --pathspec-from-file=paths.txt",
                    "git commit --all -m x", "git commit -qam x"):
            self.assertIn("structure-grow", [f.code for f in self.commit_decision(cmd).findings], cmd)
        self.assertTrue(self.commit_decision("git commit -m x").allow)   # nothing staged → nothing grows

    def test_add_then_commit_reads_disk(self):
        d = self.commit_decision("git add app/small.py && git commit -m x")
        self.assertIn("structure-grow", [f.code for f in d.findings])

    def test_add_then_commit_catches_secrets_too(self):
        key = "AKIA" + "Q" * 16
        self.put("app/config.py", f'KEY = "{key}"\n')
        d = self.commit_decision("git add -A && git commit -m x")
        self.assertEqual(d.risk, "high")
        self.assertNotIn(key, d.reason(self.cfg))

    def test_git_global_options_do_not_hide_the_subcommand(self):
        self.assertEqual(self.d("Bash", {"command": "git -C . push --force origin main"}).risk, "high")
        self.assertEqual(self.d("Bash", {"command": "git -c core.pager=cat reset --hard"}).risk, "high")
        self.assertIn("structure-grow", [f.code for f in self.commit_decision("git -c user.name=x commit -am x").findings])
        self.assertIn("structure-grow", [f.code for f in self.commit_decision("git -C app commit -am x").findings])

    def test_seed_cannot_be_reached_by_abbreviation_quotes_or_editing(self):
        for cmd in ("python .outrigger/engine/cli.py structure --se", "python .outrigger/engine/cli.py structure --see",
                    "python .outrigger/engine/cli.py \"structure\" --seed",
                    "python -c \"open('.outrigger/local/structure-baseline.json','w').write('{}')\"",
                    "python .outrigger/engine/cli.py trash .outrigger/local/structure-baseline.json --reason x"):
            self.assertFalse(self.d("Bash", {"command": cmd}).allow, cmd)
        out = self.cli("structure", "--se")
        self.assertNotEqual(out.returncode, 0)
        self.assertFalse((self.tmp / structure.BASELINE_REL).exists())

    def test_update_refuses_without_a_baseline(self):
        self.assertNotEqual(self.cli("structure", "--update").returncode, 0)
        self.assertFalse((self.tmp / structure.BASELINE_REL).exists())

    def test_malformed_baseline_entries_fail_closed(self):
        for body in ('{"files": {"a.py": "x"}}', '{"files": {"a.py": {"lines": "9"}}}', '{"files": []}'):
            (self.tmp / structure.BASELINE_REL).write_text(body, encoding="utf-8")
            self.git("add", "app/small.py")
            self.assertIn("structure-check-failed", [f.code for f in self.commit_decision().findings], body)
        (self.tmp / structure.BASELINE_REL).write_bytes(bytes([0xFF, 0xFE]) + b"{")
        self.assertIn("structure-check-failed", [f.code for f in self.commit_decision().findings])


class CountParams(unittest.TestCase):
    def test_comparisons_strings_and_csharp_without_modifier(self):
        c = structure.ctor_deps
        self.assertEqual(c("a.ts", "class A { constructor(a = x > 1 ? 2 : 3, b: B) {} }"), 2)
        self.assertEqual(c("a.ts", 'class A { constructor(a = "(", b: B, c: C) {} }'), 3)
        self.assertEqual(c("a.cs", 'class A {\n  A(string s = "a,b", int n = 1) {}\n}'), 2)
        self.assertEqual(c("a.cs", "public sealed record Dto(int A, int B, int C);"), 0)


class NextIdBranches(GitProject):
    def test_a_date_after_the_type_is_not_a_number(self):
        self.git("branch", "feature/ISSUE-2026-11-no-number")
        self.git("branch", "docs/pm-2026-11-review")
        self.assertEqual(records.next_id(self.cfg, "ISSUE")[0], "ISSUE-001")
        self.assertEqual(records.next_id(self.cfg, "PM")[0], "PM-001")

class StructureBypassesRound2(GitProject):
    """Review round 2 of 0.6.0: holes opened by the first round of fixes."""

    def setUp(self):
        super().setUp()
        self.enable_structure()

    def test_file_over_two_megabytes_is_still_measured(self):
        self.put("app/huge.py", lines(10))
        self.git("add", "app/huge.py")
        self.git("commit", "-q", "-m", "huge")
        self.put("app/huge.py", "x = 1\n" * 420_000)        # ≈ 2.4 MB
        for cmd in ("git commit -m x app/huge.py", "git add app/huge.py && git commit -m x", "git commit -am x"):
            self.assertIn("structure-grow", [f.code for f in self.commit_decision(cmd).findings], cmd)

    def test_add_then_commit_follows_cd_and_work_tree(self):
        nested = self.tmp / "nested"
        nested.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=nested, check=True)
        (nested / "big.py").write_text(lines(900), encoding="utf-8")
        for cmd in ("cd nested && git add big.py && git commit -m x",
                    "git --git-dir=nested/.git --work-tree=nested add big.py && "
                    "git --git-dir=nested/.git --work-tree=nested commit -m x"):
            self.assertIn("structure-grow", [f.code for f in self.commit_decision(cmd).findings], cmd)

    def test_commit_all_does_not_ask_about_untracked_scratch(self):
        self.put("app/scratch.py", lines(900))               # untracked: `-a` does not commit it
        self.assertTrue(self.commit_decision("git commit -am x").allow)
        self.assertTrue(self.commit_decision("git commit -uno -m x").allow)

    def test_update_then_commit_message_is_not_self_approval(self):
        d = self.d("Bash", {"command": 'python .outrigger/engine/cli.py structure --update && git commit -m "--sec fix"'})
        self.assertNotIn("self-approval", [f.code for f in d.findings])


class RecordLayout(Project):
    def test_issue_folders_are_green_and_templates_routed(self):
        self.assertEqual(self.cfg.zone_of("docs/issues/11-2026/ISSUE-001-x/phase/phase-1.md"), "green")
        rules = (ENGINE.parent / "rules" / "records.md").read_text(encoding="utf-8")
        for name in ("ISSUE.md", "PHASE.md"):
            self.assertIn(f"`{name}`", rules)
        self.assertIn("cli.py next-id", rules)


if __name__ == "__main__":
    unittest.main()
