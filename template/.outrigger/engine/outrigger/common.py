"""Shared vocabulary of the guard: Finding, risk order, command-name sets and patterns, path helper."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass
class Finding:
    risk: str
    code: str
    reason: str
    app: str | None = None


DELETE = {"rm", "del", "erase", "rd", "rmdir", "remove-item", "ri", "unlink", "shred", "srm", "trash-put", "rimraf"}
READ_ONLY = {"cat", "type", "get-content", "gc", "less", "more", "head", "tail", "grep", "rg", "findstr",
             "select-string", "ls", "dir", "get-childitem", "gci", "wc", "stat", "file", "test-path", "echo",
             # 0.3.1 (ADR-0010 C): comparing files changes nothing — a `diff` of two engines was blocked as high risk
             "diff", "cmp", "comm", "fc", "compare-object", "sha256sum", "md5sum", "get-filehash"}
# Commands that write their path arguments (ADR-0010 A). Before 0.3.1 only `>` redirects into protected zones were
# checked, so `cp x protected/y` passed. MOVE-like commands also change their source; COPY-like ones only the target.
MOVE_LIKE = {"mv", "move", "move-item", "mi", "rename-item", "rni", "ren", "rename"}
COPY_LIKE = {"cp", "copy", "copy-item", "cpi", "xcopy", "robocopy", "install", "ln"}
SYSTEM_HIGH = {"format", "diskpart", "bcdedit", "shutdown", "restart-computer", "stop-computer", "regedit",
               "set-mppreference", "add-mppreference", "vssadmin", "mkfs", "dd", "runas", "su", "takeown",
               "set-executionpolicy", "cipher", "__sudo__", "iex", "invoke-expression", "__encoded__"}
SCHEDULE = {"schtasks", "register-scheduledtask", "set-scheduledtask", "unregister-scheduledtask",
            "new-scheduledtask", "new-scheduledtasktrigger", "new-scheduledtaskaction", "crontab", "at", "launchctl"}
NET = {"curl", "wget", "invoke-webrequest", "iwr", "invoke-restmethod", "irm", "bitsadmin",
       "start-bitstransfer", "certutil"}
NET_OUT = {"scp", "sftp", "ftp", "rsync", "nc", "ncat", "telnet", "ssh"}
INSTALLERS = {
    "pip": {"install"}, "pip3": {"install"}, "uv": {"add", "pip"}, "pipx": {"install"},
    "npm": {"install", "i", "add"}, "pnpm": {"add", "install", "i"}, "yarn": {"add", "install"},
    "bun": {"add", "install", "i"}, "winget": {"install", "upgrade"}, "choco": {"install", "upgrade"},
    "scoop": {"install"}, "conda": {"install", "create"}, "mamba": {"install"}, "apt": {"install"},
    "apt-get": {"install"}, "brew": {"install"}, "gem": {"install"}, "cargo": {"install"},
    "install-module": None, "install-package": None, "npx": None,
}


def worst(findings: list[Finding]) -> str:
    return max((f.risk for f in findings), key=RISK_ORDER.get, default="low")


OUTRIGGER_CLI = re.compile(r"\.outrigger[\\/]engine[\\/]cli\.py", re.IGNORECASE)


CD = {"cd", "pushd", "set-location", "sl", "chdir"}
MSYS_DRIVE = re.compile(r"^/([a-zA-Z])(/|$)")


def _as_path(token: str, cwd: Path) -> Path:
    p = MSYS_DRIVE.sub(lambda m: m.group(1) + ":/", token.strip("\"'"))   # Git Bash: /c/Users -> c:/Users
    p = Path(os.path.expandvars(os.path.expanduser(p)))
    return p if p.is_absolute() else cwd / p
