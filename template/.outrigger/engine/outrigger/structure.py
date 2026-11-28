"""Structure gate (ADR-0015): a file that is already too big may only shrink; a new file may not start too big.

Opt-in: `[structure] enabled = true` in outrigger.toml (the human decides). Metrics per file:
  lines      line count (like `wc -l`)
  use_state  `useState(` / `useState<` calls in a .tsx/.jsx file
  ctor_deps  most parameters of one constructor (TS `constructor(...)`; C# class constructors and primary
             constructors; `record`/`struct` are data, not dependencies)
Files already over a limit when the gate is switched on are written to the baseline by `cli.py structure --seed`
(human only); after that the agent may run `cli.py structure --update`, which only lowers or removes entries.
The baseline is a protected file, so it cannot be raised by editing it.
On `git commit` the staged content is judged; the files on disk are judged too (the larger value wins) when the
commit names paths, uses -a/-i/-o/--pathspec-from-file, or follows a `git add` in the same command.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from .common import Finding
from .config import Config, match_any

BASELINE_REL = ".outrigger/local/structure-baseline.json"
DEFAULTS = {
    "enabled": False, "max_lines": 400, "max_use_state": 10, "max_ctor_deps": 6,
    "include": ["**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.cs", "**/*.java", "**/*.kt",
                "**/*.go", "**/*.rs", "**/*.dart", "**/*.php", "**/*.rb", "**/*.m"],
    "exclude": ["**/node_modules/**", "**/.outrigger/**", "sandbox/**", "**/dist/**", "**/build/**", "**/bin/**",
                "**/obj/**", "**/.venv/**", "**/test/**", "**/tests/**", "**/__tests__/**", "**/*.test.*",
                "**/*.spec.*", "**/test_*.py", "**/*_test.py", "**/*_test.go", "**/migrations/**",
                "**/migration/**", "**/*.d.ts", "**/*.gen.*", "**/*.g.dart", "**/*.freezed.dart",
                "**/*.designer.cs", "**/*modelsnapshot.cs", "**/generated/**", "**/locales/**", "**/mocks/**"],
}
LIMIT = {"lines": "max_lines", "use_state": "max_use_state", "ctor_deps": "max_ctor_deps"}
HINT = {"lines": "split by use case", "use_state": "group state into a hook/reducer/store",
        "ctor_deps": "the class does too many things; split by use case"}
SKIP_DIRS = {".git", ".outrigger", "node_modules", ".venv", "__pycache__", "sandbox", "dist", "build", "bin", "obj"}
# git commit options that take a value as the next token (lower-cased: -C/-c and -F/-f collapse)
COMMIT_VALUE_OPTS = {"-m", "-f", "-c", "-t", "--message", "--file", "--template", "--reuse-message",
                     "--reedit-message", "--fixup", "--squash", "--author", "--date", "--cleanup", "--trailer"}
MAX_BYTES = 2_000_000


class StructureError(Exception):
    """The gate cannot judge (bad baseline, git failure): callers fail closed."""


def settings(cfg: Config) -> dict:
    return {**DEFAULTS, **cfg.section("structure")}


def in_scope(rel: str, s: dict) -> bool:
    return match_any(rel, s["include"]) and not match_any(rel, s["exclude"])


def count_lines(text: str) -> int:
    if not text:
        return 0
    breaks = text.count("\n")
    return breaks if text.endswith("\n") else breaks + 1


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"'])//.*$", r"\1", text)


def count_params(text: str, open_idx: int) -> int:
    """Top-level parameters from the `(` at open_idx. Commas inside (), [], {}, generic <…> and string literals do
    not count; `<` opens a generic only right after a name (`Map<`), so `x > 1` and `=>` are no brackets."""
    depth, angle, params, content, quote, prev = 0, 0, 0, False, "", ""
    for ch in text[open_idx:]:
        if quote:
            if ch == quote and prev != "\\":
                quote = ""
            prev = ch if prev != "\\" else ""
            continue
        if ch in "\"'`" and depth >= 1:
            quote, content, prev = ch, True, ch
            continue
        if ch in "([{":
            depth += 1
            content = content or depth > 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                break
            content = True
        elif ch == "<" and (prev.isalnum() or prev == "_"):
            angle += 1
            content = True
        elif ch == ">" and angle and prev != "=":
            angle -= 1
        elif depth == 1 and not angle:
            if ch == ",":
                params += content
                content = False
            elif not ch.isspace():
                content = True
        prev = ch
    return params + content


def ctor_deps(rel: str, text: str) -> int:
    code = strip_comments(text)
    best = 0
    if rel.endswith((".ts", ".tsx")):
        for m in re.finditer(r"\bconstructor\s*\(", code):
            best = max(best, count_params(code, m.end() - 1))
    elif rel.endswith(".cs"):
        for name in set(re.findall(r"(?<!record )\bclass\s+(\w+)", code)):
            pat = (rf"\b(?:(?:public|internal|protected|private)\s+)+{name}\s*\("
                   rf"|(?<!record )\bclass\s+{name}\s*(?:<[^>]*>)?\s*\(|^[ \t]*{name}\s*\(")
            for m in re.finditer(pat, code, re.M):
                best = max(best, count_params(code, m.end() - 1))
    return best


def over_limits(rel: str, text: str, s: dict) -> dict[str, int]:
    values = {"lines": count_lines(text), "ctor_deps": ctor_deps(rel, text)}
    if rel.endswith((".tsx", ".jsx")):
        values["use_state"] = len(re.findall(r"\buseState\s*[<(]", strip_comments(text)))
    return {m: v for m, v in values.items() if v > s[LIMIT[m]]}


def _git(cwd: Path, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, input=stdin, timeout=30)


def project_files(cfg: Config) -> list[str]:
    """Tracked + staged files (git), else a walk of the project that skips build and tool folders."""
    try:
        r = _git(cfg.root, "ls-files", "-z", "--cached")
    except (OSError, subprocess.SubprocessError):
        r = None
    if r is not None and r.returncode == 0:
        names = r.stdout.decode("utf-8", "replace").split("\0")
        return sorted(p for p in names if p and (cfg.root / p).is_file())
    out = []
    for top, dirs, files in os.walk(cfg.root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        out += [(Path(top) / f).relative_to(cfg.root).as_posix() for f in files]
    return sorted(out)


def read_baseline(cfg: Config) -> dict[str, dict[str, int]]:
    p = cfg.root / BASELINE_REL
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:          # JSONDecodeError and UnicodeDecodeError are ValueErrors
        raise StructureError(f"{BASELINE_REL} cannot be read ({type(exc).__name__})") from exc
    files = data.get("files") if isinstance(data, dict) else None
    ok = isinstance(files, dict) and all(
        isinstance(v, dict) and all(k in LIMIT and type(n) is int for k, n in v.items()) for v in files.values())
    if not ok:
        raise StructureError(f"{BASELINE_REL} is malformed (expected files: {{path: {{metric: int}}}})")
    return files


def write_baseline(cfg: Config, files: dict[str, dict[str, int]]) -> None:
    body = {"_note": "Written by `cli.py structure`. Entries may only go down (--update). Never edit by hand.",
            "files": {k: dict(sorted(v.items())) for k, v in sorted(files.items())}}
    p = cfg.root / BASELINE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def measure_project(cfg: Config) -> dict[str, dict[str, int]]:
    s = settings(cfg)
    out = {}
    for rel in project_files(cfg):
        if in_scope(rel, s):
            text = (cfg.root / rel).read_text(encoding="utf-8", errors="replace")
            hits = over_limits(rel, text, s)
            if hits:
                out[rel] = hits
    return out


def compare(current: dict, baseline: dict, s: dict, update: bool) -> tuple[list[str], dict]:
    """Ratchet: new over limit / grown → error; shrunk or gone → error unless update (then lowered)."""
    errors, lowered = [], {}
    for rel, metrics in sorted(current.items()):
        for m, now in sorted(metrics.items()):
            allowed = baseline.get(rel, {}).get(m)
            if allowed is None:
                errors.append(f"{rel}: {m}={now} > {s[LIMIT[m]]} — new file over the limit, {HINT[m]}")
            elif now > allowed:
                errors.append(f"{rel}: {m}={now} > baseline {allowed} — may only shrink, {HINT[m]}")
            else:
                lowered.setdefault(rel, {})[m] = now
                if now < allowed and not update:
                    errors.append(f"{rel}: {m}={now} < baseline {allowed} — lower it: cli.py structure --update")
    for rel, metrics in sorted(baseline.items()):
        for m in sorted(metrics):
            if m not in current.get(rel, {}) and not update:
                errors.append(f"{rel}: {m} is under the limit now — remove it: cli.py structure --update")
    return errors, lowered


def commit_reads_disk(low: list[str]) -> bool:
    """True when `git commit <low…>` can take content that is not staged yet: -a/-i/-o, pathspecs, a pathspec file."""
    i = 1
    while i < len(low):
        a = low[i]
        if a == "--":
            return i + 1 < len(low)
        if a in {"--all", "--include", "--only", "-i", "-o"} or a.startswith("--pathspec-from-file"):
            return True
        if a in COMMIT_VALUE_OPTS:
            i += 2
            continue
        if a.startswith("--"):
            i += 1
            continue
        if a.startswith("-"):
            takes_value = False
            for j, f in enumerate(a[1:]):
                if f in "aio":
                    return True
                if f in "mfct":                      # value is the rest of this token, or the next token
                    takes_value = j == len(a) - 2
                    break
                if f == "u":                         # -u<mode> (-uno): the mode is the rest of this token
                    break
            i += 2 if takes_value else 1
            continue
        return True                                  # a bare word is a pathspec
    return False


def _names(out: bytes) -> set[str]:
    return {n for n in out.decode("utf-8", "replace").split("\0") if n}


def staged_findings(low: list[str], cfg: Config, cwd: Path, force_disk: bool = False,
                    untracked: bool = False) -> list[Finding]:
    """On `git commit` (low = ["commit", …]): judge the files the commit would carry. Fails closed."""
    s = settings(cfg)
    if not s["enabled"]:
        return []
    disk = force_disk or commit_reads_disk(low)
    try:
        baseline = read_baseline(cfg)
        top_r = _git(cwd, "rev-parse", "--show-toplevel")
        if top_r.returncode != 0:
            raise StructureError("not inside a git repository")
        top = Path(top_r.stdout.decode("utf-8", "replace").strip())
        staged_r = _git(top, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
        if staged_r.returncode != 0:
            raise StructureError("`git diff --cached` failed")
        names = _names(staged_r.stdout)
        if disk:
            mod = _git(top, "diff", "--name-only", "--diff-filter=ACMR", "-z")
            if mod.returncode != 0:
                raise StructureError("listing changed files failed")
            names |= _names(mod.stdout)
            if untracked:                            # only `git add` can bring an untracked file into the commit
                new = _git(top, "ls-files", "--others", "--exclude-standard", "-z")
                if new.returncode != 0:
                    raise StructureError("listing new files failed")
                names |= _names(new.stdout)
        keyed = {}
        for name in names:
            path = top / name
            try:
                key = path.relative_to(cfg.root).as_posix()
            except ValueError:
                key = name
            if in_scope(key, s):
                keyed[name] = key
        index_text = _index_blobs(top, [n for n in keyed if n in _names(staged_r.stdout)])
        hits = []
        for name, key in sorted(keyed.items()):
            texts = [index_text[name]] if name in index_text else []
            worst: dict[str, int] = {}
            if disk and (top / name).is_file():
                if (top / name).stat().st_size <= MAX_BYTES:
                    texts.append((top / name).read_text(encoding="utf-8", errors="replace"))
                else:                                # too big to parse: still count its lines, never skip it
                    big = _stream_lines(top / name)
                    if big > s["max_lines"]:
                        worst["lines"] = big
            for text in texts:
                for m, v in over_limits(key, text, s).items():
                    worst[m] = max(worst.get(m, 0), v)
            for m, now in sorted(worst.items()):
                allowed = baseline.get(key, {}).get(m)
                if allowed is None or now > allowed:
                    hits.append(f"{key} {m}={now} ({'new, limit ' + str(s[LIMIT[m]]) if allowed is None else 'baseline ' + str(allowed)})")
    except (OSError, subprocess.SubprocessError, StructureError) as exc:
        return [Finding("medium", "structure-check-failed", f"could not check file sizes for the commit ({exc})")]
    if not hits:
        return []
    shown_hits = "; ".join(hits[:6]) + (f"; … +{len(hits) - 6} more" if len(hits) > 6 else "")
    return [Finding("medium", "structure-grow",
                    f"the commit makes files too big: {shown_hits}. Split by use case; a file that is already too "
                    "big may only shrink (ADR-0015). `cli.py structure` lists everything")]


def _stream_lines(path: Path) -> int:
    lines, last = 0, b"\n"
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            lines += chunk.count(b"\n")
            last = chunk[-1:]
    return lines + (last != b"\n")


def _index_blobs(top: Path, names: list[str]) -> dict[str, str]:
    """Staged content of `names`, read with one `git ls-files -s` and one `git cat-file --batch` call."""
    if not names:
        return {}
    ls = _git(top, "ls-files", "-s", "-z", "--", *names)
    if ls.returncode != 0:
        raise StructureError("`git ls-files -s` failed")
    shas: dict[str, str] = {}
    for entry in _names(ls.stdout):
        meta, _, path = entry.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[2] == "0":
            shas[path] = parts[1]
    if set(names) - set(shas):
        raise StructureError("a staged file has no index entry (merge in progress?)")
    order = sorted(shas)
    batch = _git(top, "cat-file", "--batch", stdin="".join(shas[n] + "\n" for n in order).encode())
    if batch.returncode != 0:
        raise StructureError("`git cat-file --batch` failed")
    out, data, pos = {}, batch.stdout, 0
    for name in order:
        head_end = data.index(b"\n", pos)
        size = int(data[pos:head_end].split()[2])
        out[name] = data[head_end + 1:head_end + 1 + size].decode("utf-8", "replace")
        pos = head_end + 1 + size + 1
    return out
