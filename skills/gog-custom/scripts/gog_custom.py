#!/usr/bin/env python3
"""gog_custom.py — strict read-only wrapper for gogcli (gog).

All calls must come through a JSON contract:
  python3 gog_custom.py --json '{"action":"gmail_search_threads","payload":{...}}'

Security goals:
- Hard-block write/admin/destructive operations by *not exposing them*.
- Enforce bounded result sizes to prevent accidental huge dumps.
- Force non-interactive JSON output.

This is NOT a general gog CLI wrapper.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

GOG_BIN = os.environ.get("GOG_BIN", "/opt/homebrew/bin/gog")
# NOTE: We do NOT parse gogcli config.json for aliases.
# Aliases are resolved via `gog auth alias list`.


def _err(msg: str, *, code: int = 2, extra: Optional[dict] = None) -> "NoReturn":
    out: Dict[str, Any] = {"ok": False, "error": msg}
    if extra:
        out["extra"] = extra
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    raise SystemExit(code)


def _ok(payload: Any) -> None:
    sys.stdout.write(json.dumps({"ok": True, "result": payload}, ensure_ascii=False) + "\n")


def _load_request(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        _err(f"Invalid JSON: {e}")
    if not isinstance(data, dict):
        _err("Request must be a JSON object")
    if "action" not in data or "payload" not in data:
        _err("Request must contain 'action' and 'payload'")
    if not isinstance(data["action"], str):
        _err("'action' must be a string")
    if not isinstance(data["payload"], dict):
        _err("'payload' must be an object")
    return data  # type: ignore[return-value]


def _clamp_int(v: Any, *, default: int, min_v: int, max_v: int, name: str) -> int:
    if v is None:
        return default
    if isinstance(v, bool) or not isinstance(v, int):
        _err(f"'{name}' must be an integer")
    if v < min_v:
        return min_v
    if v > max_v:
        return max_v
    return v


def _opt_str(v: Any, name: str) -> Optional[str]:
    if v is None:
        return None
    if not isinstance(v, str) or not v.strip():
        _err(f"'{name}' must be a non-empty string")
    return v


def _opt_bool(v: Any, name: str) -> Optional[bool]:
    if v is None:
        return None
    if not isinstance(v, bool):
        _err(f"'{name}' must be boolean")
    return v


def _opt_str_list(v: Any, name: str) -> Optional[List[str]]:
    if v is None:
        return None
    if not isinstance(v, list) or any((not isinstance(x, str) or not x.strip()) for x in v):
        _err(f"'{name}' must be an array of non-empty strings")
    return [x for x in v]


def _auth_alias_map() -> Dict[str, str]:
    """Return gog's alias→account map.

    Source of truth is:
      gog --json --no-input auth alias list

    Expected JSON shape (v0.11+):
      {"aliases": {"personal": "me@gmail.com", ...}}

    If the command fails for any reason, we return an empty map and fall back to
    passing the alias through unchanged (gog may still accept it depending on CLI behavior).
    """
    try:
        res = _run_gog([GOG_BIN, "--json", "--no-input", "auth", "alias", "list"])
    except SystemExit:
        # _run_gog already emitted a JSON error; but alias resolution is a convenience.
        # For robustness, don't hard-fail account resolution on this.
        return {}

    if isinstance(res, dict):
        aliases = res.get("aliases")
        if isinstance(aliases, dict):
            out: Dict[str, str] = {}
            for k, v in aliases.items():
                if isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip():
                    out[k.strip().lower()] = v.strip()
            return out
    return {}


def _resolve_account(acct: Optional[str]) -> Optional[str]:
    """Resolve an account identifier.

    - If acct looks like an email (contains '@'), return as-is.
    - Otherwise treat it as a gog auth alias and resolve via `gog auth alias list`.

    No config.json parsing; no hard-coded aliases.
    """
    if not acct:
        return None
    acct = acct.strip()
    if not acct:
        return None
    if "@" in acct:
        return acct

    amap = _auth_alias_map()
    return amap.get(acct.lower()) or acct


def _base_gog_args(account: Optional[str]) -> List[str]:
    if not os.path.exists(GOG_BIN):
        _err(f"gog binary not found at {GOG_BIN}")

    args = [
        GOG_BIN,
        "--json",
        "--no-input",
        "--enable-commands",
        "gmail,calendar",
    ]
    if account:
        args += ["--account", account]
    return args


def _run_gog(args: List[str]) -> Any:
    # Force a minimal env; keep PATH for gog subprocess dependencies.
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "GOG_KEYRING_PASSWORD", "GOG_KEYRING_BACKEND", "GOG_ACCOUNT")}

    # If not present in the process env, try to load from Clawdbot config skill entry.
    if not env.get("GOG_KEYRING_PASSWORD"):
        cfg_path = os.path.expanduser("~/.clawdbot/clawdbot.json")
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            skill_env = (((cfg.get("skills") or {}).get("entries") or {}).get("gog-custom") or {}).get("env") or {}
            if isinstance(skill_env, dict):
                pw = skill_env.get("GOG_KEYRING_PASSWORD")
                if isinstance(pw, str) and pw.strip():
                    env["GOG_KEYRING_PASSWORD"] = pw
                acct = skill_env.get("GOG_ACCOUNT")
                if isinstance(acct, str) and acct.strip() and not env.get("GOG_ACCOUNT"):
                    env["GOG_ACCOUNT"] = acct
        except Exception:
            # Ignore config load failures; gog will throw a clear error if password is needed.
            pass

    try:
        p = subprocess.run(
            args,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except Exception as e:
        _err(f"Failed to execute gog: {e}")

    if p.returncode != 0:
        _err(
            "gog command failed",
            code=3,
            extra={
                "returncode": p.returncode,
                "stderr": (p.stderr or "").strip()[:8000],
                "cmd": args,
            },
        )

    out = (p.stdout or "").strip()
    if not out:
        return None

    try:
        return json.loads(out)
    except json.JSONDecodeError:
        # gog should always return JSON with --json; treat non-JSON as an error.
        _err("Expected JSON output from gog", extra={"stdout": out[:8000], "cmd": args})


def _require_account(payload: Dict[str, Any]) -> str:
    """Return the resolved gog account identifier.

    gog requires an explicit account when multiple tokens exist.

    We support passing either:
      - an email address (e.g. "me@gmail.com"), or
      - a nickname/alias (e.g. "personal"), resolved via config.json.
    """
    acct = payload.get("account")
    acct_s = _opt_str(acct, "account") if acct is not None else None
    acct_s = acct_s or os.environ.get("GOG_ACCOUNT")

    acct_s = _resolve_account(acct_s)
    if not acct_s:
        _err("'account' is required (set payload.account or export GOG_ACCOUNT)")
    return acct_s


def gmail_search_threads(payload: Dict[str, Any]) -> Any:
    query = _opt_str(payload.get("query"), "query")
    if query is None:
        _err("'query' is required")

    account = _require_account(payload)
    max_n = _clamp_int(payload.get("max"), default=10, min_v=1, max_v=25, name="max")
    page = _opt_str(payload.get("page"), "page")

    args = _base_gog_args(account) + ["gmail", "search", query, "--max", str(max_n)]
    if page:
        args += ["--page", page]
    return _run_gog(args)


def gmail_get_thread(payload: Dict[str, Any]) -> Any:
    thread_id = _opt_str(payload.get("threadId"), "threadId")
    if thread_id is None:
        _err("'threadId' is required")

    account = _require_account(payload)

    # NOTE: attachments download is intentionally not supported.
    args = _base_gog_args(account) + ["gmail", "thread", "get", thread_id]
    return _run_gog(args)


def gmail_get_message(payload: Dict[str, Any]) -> Any:
    message_id = _opt_str(payload.get("messageId"), "messageId")
    if message_id is None:
        _err("'messageId' is required")

    account = _require_account(payload)
    fmt = payload.get("format")
    if fmt is None:
        fmt_s = "metadata"
    else:
        fmt_s = _opt_str(fmt, "format")
        if fmt_s not in ("full", "metadata", "raw"):
            _err("'format' must be one of: full, metadata, raw")

    args = _base_gog_args(account) + ["gmail", "get", message_id, "--format", fmt_s]
    return _run_gog(args)


def calendar_calendars(payload: Dict[str, Any]) -> Any:
    account = _require_account(payload)
    args = _base_gog_args(account) + ["calendar", "calendars"]
    return _run_gog(args)


def _calendar_time_range_flags(payload: Dict[str, Any]) -> List[str]:
    flags: List[str] = []

    from_s = _opt_str(payload.get("from"), "from")
    to_s = _opt_str(payload.get("to"), "to")
    days = payload.get("days")
    today = _opt_bool(payload.get("today"), "today")
    tomorrow = _opt_bool(payload.get("tomorrow"), "tomorrow")
    week = _opt_bool(payload.get("week"), "week")

    # Only allow one of the "relative" shortcuts to reduce ambiguity.
    shortcuts = [x for x in [today, tomorrow, week] if x]
    if len(shortcuts) > 1:
        _err("Only one of 'today'|'tomorrow'|'week' may be true")

    if from_s:
        flags += ["--from", from_s]
    if to_s:
        flags += ["--to", to_s]

    if days is not None:
        days_i = _clamp_int(days, default=30, min_v=1, max_v=365, name="days")
        flags += ["--days", str(days_i)]

    if today:
        flags += ["--today"]
    if tomorrow:
        flags += ["--tomorrow"]
    if week:
        flags += ["--week"]

    return flags


def calendar_events(payload: Dict[str, Any]) -> Any:
    account = _require_account(payload)
    cal_id = _opt_str(payload.get("calendarId"), "calendarId")
    max_n = _clamp_int(payload.get("max"), default=50, min_v=1, max_v=200, name="max")

    args = _base_gog_args(account) + ["calendar", "events"]
    if cal_id:
        args.append(cal_id)

    args += _calendar_time_range_flags(payload)
    args += ["--max", str(max_n)]
    return _run_gog(args)


def calendar_get_event(payload: Dict[str, Any]) -> Any:
    account = _require_account(payload)
    cal_id = _opt_str(payload.get("calendarId"), "calendarId")
    event_id = _opt_str(payload.get("eventId"), "eventId")
    if cal_id is None or event_id is None:
        _err("'calendarId' and 'eventId' are required")

    args = _base_gog_args(account) + ["calendar", "event", cal_id, event_id]
    return _run_gog(args)


def calendar_search(payload: Dict[str, Any]) -> Any:
    account = _require_account(payload)
    query = _opt_str(payload.get("query"), "query")
    if query is None:
        _err("'query' is required")

    max_n = _clamp_int(payload.get("max"), default=50, min_v=1, max_v=200, name="max")

    args = _base_gog_args(account) + ["calendar", "search", query]
    args += _calendar_time_range_flags(payload)
    args += ["--max", str(max_n)]
    return _run_gog(args)


def calendar_freebusy(payload: Dict[str, Any]) -> Any:
    account = _require_account(payload)
    cal_ids = _opt_str_list(payload.get("calendarIds"), "calendarIds")
    if not cal_ids:
        _err("'calendarIds' is required")

    args = _base_gog_args(account) + ["calendar", "freebusy", ",".join(cal_ids)]
    args += _calendar_time_range_flags(payload)
    return _run_gog(args)


def calendar_conflicts(payload: Dict[str, Any]) -> Any:
    account = _require_account(payload)
    cal_ids = _opt_str_list(payload.get("calendarIds"), "calendarIds")
    if not cal_ids:
        _err("'calendarIds' is required")

    args = _base_gog_args(account) + ["calendar", "conflicts", "--calendars", ",".join(cal_ids)]
    args += _calendar_time_range_flags(payload)
    return _run_gog(args)


def auth_list(payload: Dict[str, Any]) -> Any:
    # Does not require --account.
    args = [
        GOG_BIN,
        "--json",
        "--no-input",
        "auth",
        "list",
    ]
    return _run_gog(args)


def auth_alias_list(payload: Dict[str, Any]) -> Any:
    """Return gog's current alias→account map."""
    return {"aliases": _auth_alias_map()}


def auth_status(payload: Dict[str, Any]) -> Any:
    # Uses explicit account (required if multiple tokens).
    account = _require_account(payload)
    args = _base_gog_args(account) + ["auth", "status"]
    return _run_gog(args)


ACTIONS = {
    "auth_list": auth_list,
    "auth_status": auth_status,
    "auth_alias_list": auth_alias_list,
    "gmail_search_threads": gmail_search_threads,
    "gmail_get_thread": gmail_get_thread,
    "gmail_get_message": gmail_get_message,
    "calendar_calendars": calendar_calendars,
    "calendar_events": calendar_events,
    "calendar_get_event": calendar_get_event,
    "calendar_search": calendar_search,
    "calendar_freebusy": calendar_freebusy,
    "calendar_conflicts": calendar_conflicts,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", dest="json_str", help="Request JSON (or omit to read from stdin)")
    ns = ap.parse_args()

    raw = ns.json_str
    if raw is None:
        raw = sys.stdin.read()

    if not raw or not raw.strip():
        _err("Missing request JSON")

    req = _load_request(raw)
    action = req["action"]
    payload = req["payload"]

    fn = ACTIONS.get(action)
    if not fn:
        _err("Action not allowed", extra={"action": action, "allowed": sorted(ACTIONS.keys())})

    result = fn(payload)
    _ok(result)


if __name__ == "__main__":
    main()
