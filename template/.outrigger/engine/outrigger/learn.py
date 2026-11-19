"""Standing rules learned from the human's approvals (0.3.2, ADR-0011).

When the human has approved the SAME KIND of action `suggest_after` times (default 3) within `window_days`, the guard
suggests a standing rule. Only the human can accept it, from their own terminal (`cli.py rule accept L-…`); after that
the action runs without asking until the rule expires (`ttl_days`) or is dropped.

"Same kind" is a signature the engine computes from what it sees — the host of a fetch, the package being installed,
the remote and branch of a push, the folder files are deleted from — never from what the agent says (ADR-0010).
Only MEDIUM risk is learnable. High risk (the guard itself, secrets, originals, force-push, mass delete at the root…)
is never covered by a rule, and neither are scripts with dangerous calls: `trust` already handles those, bound to
the file's bytes, which is stricter than any pattern.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from . import state
from .config import Config

LEARNABLE = {"net-unknown", "install", "git-push", "git-branch", "git-clone", "git-stash", "delete-redirect",
             "write-outside", "app", "mcp-risky"}
URL = re.compile(r"https?://[^\s'\"<>|;&)]+", re.IGNORECASE)
IP = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$|:")
# Hosting where every customer gets a sub-domain: learning `github.io` would trust everyone's site.
SHARED = ("github.io", "gitlab.io", "blogspot.com", "wordpress.com", "substack.com", "medium.com", "pages.dev",
          "vercel.app", "netlify.app", "herokuapp.com", "web.app", "firebaseapp.com", "azurewebsites.net",
          "cloudfront.net", "s3.amazonaws.com", "googleusercontent.com", "notion.site", "glitch.me", "replit.app")
SLD = {"co", "com", "ac", "gov", "edu", "org", "net", "or", "ne", "go"}
DELETE = {"rm", "del", "erase", "rd", "rmdir", "remove-item", "ri", "unlink", "trash-put", "rimraf"}


def domain(host: str) -> str:
    """The part of a host name a person means by "this site": cmu.edu for insights.sei.cmu.edu."""
    h = host.lower().strip(".")
    h = h[4:] if h.startswith("www.") else h
    labels = h.split(".")
    if IP.search(h) or len(labels) <= 2:
        return h
    for s in SHARED:
        if h == s:
            return h
        if h.endswith("." + s):
            return ".".join(labels[-(s.count(".") + 2):])
    if len(labels[-1]) == 2 and labels[-2] in SLD:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _base(tok: str) -> str:
    b = tok.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return b[:-4] if b.endswith((".exe", ".cmd", ".bat")) else b


def _dir(cfg: Config, path: str, cwd: Path) -> str | None:
    p = Path(path.strip("\"'"))
    p = p if p.is_absolute() else cwd / p
    rel = cfg.rel(p)
    if rel is None:
        return Path(p).resolve(strict=False).parent.as_posix().lower() + "/"
    parent = str(PurePosixPath(rel).parent)
    return "" if parent == "." else parent + "/"


def _targets(cfg: Config, tool_l: str, short: str, tool_input: dict, segments: list[list[str]], paths: list[str],
             cwd: Path) -> dict[str, set[str]]:
    t: dict[str, set[str]] = {c: set() for c in LEARNABLE}
    if short in {"webfetch", "web_fetch", "fetch"}:
        host = urlparse(str(tool_input.get("url", ""))).hostname
        if host:
            t["net-unknown"].add(domain(host))
    for p in paths:
        d = _dir(cfg, p, cwd)
        if d is not None and cfg.rel(p, cwd) is None:
            t["write-outside"].add(d)
    if tool_l.startswith("mcp__"):
        t["mcp-risky"].add(tool_l)
        t["app"].add(tool_l)
    cur = cwd
    for seg in segments:
        if not seg:
            continue
        head, low = _base(seg[0]), [a.lower() for a in seg[1:]]
        args = [a for a in seg[1:] if not a.startswith("-")]
        if head in {"cd", "pushd", "set-location", "sl", "chdir"} and args:
            p = Path(args[0].strip("\"'"))
            cur = p if p.is_absolute() else cur / p
            continue
        for u in URL.findall(" ".join(seg)):
            h = urlparse(u).hostname
            if h:
                t["net-unknown"].add(domain(h))
        if head == "git" and low:
            sub, rest = low[0], [a for a in seg[2:] if not a.startswith("-")]
            if sub == "push":
                t["git-push"].add("git push " + " ".join(rest[:2]) if rest else "git push")
            elif sub == "branch":
                t["git-branch"].add("git branch -d " + " ".join(rest[:1]))
            elif sub == "stash":
                t["git-stash"].add("git stash " + " ".join(rest[:1]))
            elif sub == "clone" and rest:
                h = urlparse(rest[0]).hostname or rest[0].split(":")[0].split("@")[-1]
                t["git-clone"].add(domain(h))
        elif head in DELETE:
            for a in args:
                d = _dir(cfg, a, cur)
                if d is not None:
                    t["delete-redirect"].add(d)
        elif low and (head in {"pip", "pip3", "pipx", "npm", "pnpm", "yarn", "bun", "uv", "winget", "choco", "scoop",
                               "conda", "mamba", "apt", "apt-get", "brew", "gem", "cargo"}):
            pkgs = sorted(a.lower() for a in args[1:])
            if pkgs:
                t["install"].add(f"{head} {low[0]} " + " ".join(pkgs))
        elif head in {"python", "python3", "py"} and "-m" in low:
            i = low.index("-m")
            pkgs = sorted(a.lower() for a in args if a.lower() not in {"pip", "install"} and not a.endswith(".py"))
            if low[i + 1:i + 3] == ["pip", "install"] and pkgs:
                t["install"].add("pip install " + " ".join(pkgs))
        elif head in {"start", "start-process", "saps", "explorer", "invoke-item", "ii", "code", "notepad", "open",
                      "xdg-open", "msedge", "chrome", "firefox"}:
            t["app"].add(head + (" " + args[0].lower() if args else ""))
    return t


def signatures(cfg: Config, tool_l: str, short: str, tool_input: dict, findings: list, segments: list[list[str]],
               paths: list[str], cwd: Path) -> list[tuple[str, str]] | None:
    """[(code, target), …] covering every finding above low risk, or None when any of them cannot be learned."""
    serious = [f for f in findings if f.risk != "low"]
    if not serious or any(f.risk != "medium" or f.code not in LEARNABLE for f in serious):
        return None
    t = _targets(cfg, tool_l, short, tool_input, segments, paths, cwd)
    sigs: set[tuple[str, str]] = set()
    for f in serious:
        if not t[f.code]:
            return None   # the engine cannot say what this finding is about, so it cannot generalise it
        sigs |= {(f.code, x) for x in t[f.code]}
    return sorted(sigs)


def rule_id(code: str, target: str) -> str:
    return "L-" + hashlib.sha256(f"{code}|{target}".encode("utf-8")).hexdigest()[:6]


def describe(code: str, target: str) -> str:
    return {
        "net-unknown": f"fetch from {target} and its sub-domains",
        "git-clone": f"git clone from {target}",
        "delete-redirect": f"delete files directly inside `{target or './'}` (not sub-folders)",
        "write-outside": f"write files directly inside `{target}`",
        "install": f"`{target}` (exactly these packages)",
    }.get(code, f"`{target}`")


# ---------- storage (.outrigger/state/rules.json — the guard blocks the agent from writing it) ----------

def _file(cfg: Config) -> Path:
    return cfg.state_dir / "rules.json"


def rules(cfg: Config) -> dict:
    f = _file(cfg)
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except json.JSONDecodeError:
        return {}   # a broken file grants nothing


def _save(cfg: Config, data: dict) -> None:
    _file(cfg).parent.mkdir(parents=True, exist_ok=True)
    _file(cfg).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def active(cfg: Config) -> dict:
    out = {}
    for rid, r in rules(cfg).items():
        try:
            if datetime.fromisoformat(r["expires"]) > state.now():
                out[rid] = r
        except (KeyError, ValueError):
            continue
    return out


def covered(cfg: Config, sigs: list[tuple[str, str]] | None) -> list[str] | None:
    """Rule ids that cover EVERY signature, or None."""
    if not sigs:
        return None
    act = {(r["code"], r["target"]): rid for rid, r in active(cfg).items()}
    hit = []
    for code, target in sigs:
        rid = act.get((code, target))
        if rid is None:
            return None
        hit.append(rid)
    return sorted(set(hit))


def _setting(cfg: Config, key: str, default: int) -> int:
    try:
        return int(cfg.section("rules").get(key, default))
    except (TypeError, ValueError):
        return default


def suggestions(cfg: Config) -> list[dict]:
    """Signatures the human approved at least `suggest_after` times (distinct approvals) inside the window."""
    after, window = _setting(cfg, "suggest_after", 3), _setting(cfg, "window_days", 30)
    if after <= 0:
        return []
    since = state.now() - timedelta(days=window)
    seen: dict[tuple[str, str], dict] = {}
    for e in state.read_log(cfg, since):
        if e.get("decision") != "approval-granted":
            continue
        for code, target in e.get("sigs") or []:
            s = seen.setdefault((code, target), {"ids": set(), "examples": []})
            if e.get("id") not in s["ids"]:
                s["ids"].add(e.get("id"))
                s["examples"].append(str(e.get("summary", ""))[:160])
    taken = {(r["code"], r["target"]) for r in active(cfg).values()}
    out = []
    for (code, target), s in sorted(seen.items(), key=lambda kv: -len(kv[1]["ids"])):
        if len(s["ids"]) >= after and (code, target) not in taken and code in LEARNABLE:
            out.append({"id": rule_id(code, target), "code": code, "target": target, "count": len(s["ids"]),
                        "describe": describe(code, target), "examples": s["examples"][-3:],
                        "approvals": sorted(i for i in s["ids"] if i)})
    return out


def accept(cfg: Config, rid: str) -> dict:
    s = next((x for x in suggestions(cfg) if x["id"] == rid), None)
    if s is None:
        raise KeyError(f"{rid} is not a current suggestion (see `cli.py rule list`)")
    data = rules(cfg)
    days = _setting(cfg, "ttl_days", 90)
    data[rid] = {"code": s["code"], "target": s["target"], "accepted": state.now().isoformat(timespec="seconds"),
                 "expires": (state.now() + timedelta(days=days)).isoformat(timespec="seconds"),
                 "from_approvals": s["approvals"]}
    _save(cfg, data)
    return data[rid]


def drop(cfg: Config, rid: str) -> bool:
    data = rules(cfg)
    if rid not in data:
        return False
    del data[rid]
    _save(cfg, data)
    return True
