"""
Session pool — مالک از داخل ربات اکانت‌ها رو اضافه/حذف می‌کنه.
هر entry: {phone, session_string, name, active, fail_count}
"""
import json
import os
from typing import Optional

SESSION_STORE = "/tmp/sessions.json"


def _load() -> list[dict]:
    if not os.path.exists(SESSION_STORE):
        return []
    with open(SESSION_STORE) as f:
        return json.load(f)


def _save(sessions: list[dict]) -> None:
    with open(SESSION_STORE, "w") as f:
        json.dump(sessions, f, indent=2)


def add_session(phone: str, session_string: str, name: str = "") -> bool:
    sessions = _load()
    for s in sessions:
        if s["phone"] == phone:
            s["session_string"] = session_string
            s["name"] = name
            s["active"] = True
            s["fail_count"] = 0
            _save(sessions)
            return False  # updated existing
    sessions.append({
        "phone": phone,
        "session_string": session_string,
        "name": name,
        "active": True,
        "fail_count": 0,
    })
    _save(sessions)
    return True  # new


def remove_session(phone: str) -> bool:
    sessions = _load()
    new = [s for s in sessions if s["phone"] != phone]
    _save(new)
    return len(new) < len(sessions)


def list_sessions() -> list[dict]:
    return _load()


def get_active_sessions() -> list[dict]:
    sessions = _load()
    # اگه pool خالیه، fallback به env var
    if not sessions:
        env = os.environ.get("TELEGRAM_SESSION_STRING", "").strip()
        if env:
            return [{"phone": "env", "session_string": env, "name": "env", "active": True, "fail_count": 0}]
    return [s for s in sessions if s["active"]]


def mark_session_failed(phone: str) -> None:
    sessions = _load()
    for s in sessions:
        if s["phone"] == phone:
            s["fail_count"] += 1
            if s["fail_count"] >= 3:
                s["active"] = False
    _save(sessions)


def reset_sessions() -> None:
    sessions = _load()
    for s in sessions:
        s["fail_count"] = 0
        s["active"] = True
    _save(sessions)
