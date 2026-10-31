"""Static hosting bridge. Reuses WebSession and the original Python engine.

The build embeds known optimum values so phones never run a BFS during play.
The desktop HTTP server and Tkinter paths are unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path
import secrets

from webapp import Catalog, WebSession

_catalog = None
_sessions = {}


def browser_dispatch(encoded: str) -> str:
    global _catalog
    try:
        request = json.loads(encoded)
        path, data = request.get("path"), request.get("body")
        if not isinstance(data, dict):
            raise ValueError("Nội dung cần là một JSON object.")
        if _catalog is None:
            _catalog = Catalog()
            optima = json.loads(Path(__file__).with_name("web_optima.json").read_text(encoding="utf-8"))
            _catalog.optimum = lambda key: optima[key]
        if path == "/api/session":
            key = data.get("level", _catalog.default)
            if not isinstance(key, str):
                raise ValueError("Mã màn không hợp lệ.")
            # This dispatch runs in one Web Worker; WASM does not spawn processes.
            session = WebSession(_catalog, key, sync_solver=True)
            token = secrets.token_urlsafe(32)
            if len(_sessions) >= 16:
                _sessions.pop(next(iter(_sessions))).close()
            _sessions[token] = session
            result = {"session": token, "catalog": _catalog.items, **session.snapshot()}
        elif path == "/api/command":
            session = _sessions.get(request.get("token"))
            if session is None:
                return json.dumps({"status": 410, "body": {"error": "Phiên đã kết thúc. Kết nối lại để bắt đầu."}})
            command = data.get("command")
            if not isinstance(command, str) or (command == "load" and not isinstance(data.get("level"), str)):
                raise ValueError("Lệnh hoặc mã màn không hợp lệ.")
            result = session.command(command, data)
        else:
            return json.dumps({"status": 404, "body": {"error": "Không tìm thấy API."}})
        return json.dumps({"status": 200, "body": result}, ensure_ascii=False)
    except (ValueError, TypeError, AttributeError) as error:
        return json.dumps({"status": 400, "body": {"error": str(error)}}, ensure_ascii=False)
