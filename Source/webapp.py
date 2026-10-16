"""Responsive browser UI. All moves still go through the existing Python engine.

Run: python main.py --web --no-browser
The server is local by default; --host 0.0.0.0 enables devices on the same LAN.
"""
from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from time import monotonic
from urllib.parse import urlsplit
import webbrowser

from controller import GameController
from geometry import move
from loader import load_level
from models import Action, Algorithm, SearchConfig, SessionPhase
from solvers import solve

BASE = Path(__file__).resolve().parent
WEB = BASE / "web"
UNDO_LIMIT = 5
LEVEL_NAMES = {
    "quiet_01": ("Khoảng lặng", "Một khối nhỏ. Một hành trình mới."),
    "basic_01": ("Bước đầu tiên", "Hai lần lăn, một khởi đầu."),
    "basic_02": ("Qua khúc quanh", "Đổi góc nhìn. Tìm lối đi."),
    "fragile_01": ("Khẽ chạm", "Nằm xuống để đi qua những ô mong manh."),
    "fragile_02": ("Đường vòng", "Đường ngắn chưa hẳn là đường dễ."),
    "switch_01": ("Một kết nối", "Chạm công tắc để mở một lối đi."),
    "switch_02": ("Điểm tựa", "Đứng thẳng trên công tắc nặng."),
    "split_01": ("Hai nửa", "Tách ra, tìm nhau, rồi cùng về đích."),
    "split_02": ("Đồng điệu", "Đôi khi cần một chút giúp đỡ từ nửa kia."),
    "combined_01": ("Giao điểm", "Mỗi chuyển động đều tạo ra kết nối."),
    "combined_02": ("Hợp nhất", "Đặt mọi mảnh ghép về đúng chỗ."),
    "no_solution_01": ("Đảo xa", "Màn thử nghiệm vô nghiệm · không chấm sao."),
    "no_solution_02": ("Vòng lặp", "Màn thử nghiệm vô nghiệm · không chấm sao."),
}


class Catalog:
    def __init__(self, initial_level: Path | None = None):
        manifest = json.loads((WEB / "levels" / "campaign.json").read_text(encoding="utf-8"))
        if manifest.get("version") != 1:
            raise ValueError("Unsupported campaign version.")
        campaign = {}
        paths = {}
        for item in manifest["levels"]:
            key, filename = item["id"], item["file"]
            if key in campaign or filename != f"{key}.json" or Path(filename).name != filename:
                raise ValueError("Invalid or duplicate campaign level.")
            campaign[key] = item
            paths[key] = WEB / "levels" / filename
        extras = {p.stem: p for p in (BASE / "levels").glob("*.json")}
        extras["quiet_01"] = WEB / "levels" / "quiet_01.json"
        order = list(LEVEL_NAMES)
        paths.update(sorted(extras.items(), key=lambda item: (
            order.index(item[0]) if item[0] in order else len(order), item[0])))
        if initial_level:
            paths[initial_level.stem] = initial_level.resolve()
        self.paths = paths
        self.default = initial_level.stem if initial_level else next(iter(campaign))
        self.items = []
        for index, (key, path) in enumerate(self.paths.items()):
            level, _ = load_level(path)
            entry = campaign.get(key)
            if entry and level.id != key:
                raise ValueError("Campaign level ID does not match its manifest.")
            title, subtitle = LEVEL_NAMES.get(key, (level.id, "Tìm đường đưa khối vào ô đích."))
            self.items.append({"id": key, "number": index + 1 if entry else index + 1 - len(campaign),
                               "title": entry["title"] if entry else title,
                               "subtitle": entry["subtitle"] if entry else subtitle,
                               "collection": "campaign" if entry else "extra",
                               "difficulty": entry["difficulty"] if entry else None,
                               "difficultyLabel": entry["difficultyLabel"] if entry else None,
                               "mechanics": entry["mechanics"] if entry else [],
                               "biomeId": level.biome_id,
                               "chapter": entry.get("chapter", 1) if entry else None,
                               "chapterLevel": entry.get("chapterLevel", index + 1) if entry else None,
                               "chapterTotal": sum(item.get("biomeId") == level.biome_id for item in campaign.values()) if entry else None,
                               "passcode": f"{int(sha256(key.encode()).hexdigest()[:8], 16) % 1000000:06d}",
                               "practice": key.startswith("no_solution_")})

    @lru_cache(maxsize=128)
    def optimum(self, key: str) -> int | None:
        # UNIT BFS counts every action, including cube selection, like the HUD.
        level, start = load_level(self.paths[key])
        result = solve(level, start, Algorithm.BFS,
                       SearchConfig(time_limit_seconds=2, measure_memory=False))
        return result.solution_length if result.found else None


class WebSession:
    """UI state wraps the controller; snapshots retain bridges and split cubes."""
    def __init__(self, catalog: Catalog, level_id: str):
        self.catalog = catalog
        self.game = GameController()
        self.lock = threading.Lock()
        self.touched = monotonic()
        self.history: list[tuple] = []
        self.paused = False
        self.undos = UNDO_LIMIT
        self.fallen_state = None
        self.load(level_id)

    def load(self, level_id: str):
        if level_id not in self.catalog.paths:
            raise ValueError("Không tìm thấy màn chơi.")
        self.game.load(self.catalog.paths[level_id])
        self.level_id = level_id
        self.optimal = self.catalog.optimum(level_id)
        self.history.clear()
        self.undos = UNDO_LIMIT
        self.paused = False
        self.fallen_state = None

    def command(self, command: str, data: dict):
        game = self.game
        if command == "load":
            self.load(data.get("level", ""))
        elif command == "restart":
            game.restart()
            self.history.clear()
            self.undos = UNDO_LIMIT
            self.paused = False
            self.fallen_state = None
        elif command == "pause":
            if game.phase == SessionPhase.PLAYING:
                self.paused = True
        elif command == "resume":
            self.paused = False
        elif command == "undo":
            if not self.paused and self.history and self.undos > 0:
                game.current_state, game.action_count = self.history.pop()
                game.phase = SessionPhase.PLAYING
                game.last_events = ()
                game.message = "Đã trở về bước trước. Thử một hướng khác nhé."
                self.undos -= 1
                self.fallen_state = None
        elif command == "move":
            try:
                action = Action(data.get("action"))
            except (ValueError, TypeError):
                raise ValueError("Hướng di chuyển không hợp lệ.") from None
            if not self.paused and game.phase == SessionPhase.PLAYING:
                previous = (game.current_state, game.action_count)
                game.handle_action(action)
                if previous[0] != game.current_state or game.phase == SessionPhase.LOST:
                    self.history.append(previous)
                if game.phase == SessionPhase.LOST:
                    self.fallen_state = move(previous[0], action)
        elif command != "state":
            raise ValueError("Lệnh không hợp lệ.")
        self.touched = monotonic()
        return self.snapshot()

    def snapshot(self):
        game = self.game
        info = next(item for item in self.catalog.items if item["id"] == self.level_id)
        optimal = self.optimal
        thresholds = [optimal, optimal + max(2, (optimal + 2) // 3)] if optimal is not None else None
        stars = (3 if game.action_count <= thresholds[0] else
                 2 if game.action_count <= thresholds[1] else 1) if thresholds else None
        return {"level": {**asdict(game.level), **info,
                          "width": game.level.width, "height": game.level.height, "optimal": optimal,
                          "thresholds": thresholds},
                "state": asdict(game.current_state),
                "fallenState": asdict(self.fallen_state) if self.fallen_state else None,
                "phase": "PAUSED" if self.paused else game.phase.value,
                "moves": game.action_count, "stars": stars,
                "undos": self.undos, "undoLimit": UNDO_LIMIT,
                "canUndo": bool(self.history and self.undos and not self.paused),
                "message": game.message,
                "events": [asdict(event) for event in game.last_events]}


class GameServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, catalog):
        self.catalog = catalog
        self.sessions: dict[str, WebSession] = {}
        self.sessions_lock = threading.Lock()
        super().__init__(address, GameHandler)


class GameHandler(BaseHTTPRequestHandler):
    server: GameServer

    def log_message(self, format, *args):
        pass

    def respond(self, status, body, content_type="application/json; charset=utf-8"):
        payload = json.dumps(body, ensure_ascii=False).encode() if not isinstance(body, bytes) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_GET(self):
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/styles.css": ("styles.css", "text/css; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/transport.js": ("transport.js", "text/javascript; charset=utf-8"),
                  "/board.js": ("board.js", "text/javascript; charset=utf-8"),
                  "/rolling.js": ("rolling.js", "text/javascript; charset=utf-8"),
                  "/motion.js": ("motion.js", "text/javascript; charset=utf-8"),
                  "/camera.js": ("camera.js", "text/javascript; charset=utf-8"),
                  "/gestures.js": ("gestures.js", "text/javascript; charset=utf-8"),
                  "/profiles.js": ("profiles.js", "text/javascript; charset=utf-8"),
                  "/profile-ui.js": ("profile-ui.js", "text/javascript; charset=utf-8"),
                  "/run-clock.js": ("run-clock.js", "text/javascript; charset=utf-8"),
                  "/impact.js": ("impact.js", "text/javascript; charset=utf-8"),
                  "/landing-dust.js": ("landing-dust.js", "text/javascript; charset=utf-8"),
                  "/wind.js": ("wind.js", "text/javascript; charset=utf-8"),
                  "/biomes.js": ("biomes.js", "text/javascript; charset=utf-8"),
                  "/vendor/three.module.js": ("vendor/three.module.js", "text/javascript; charset=utf-8"),
                  "/vendor/three.core.js": ("vendor/three.core.js", "text/javascript; charset=utf-8"),
                  "/favicon.svg": ("favicon.svg", "image/svg+xml")}
        path = urlsplit(self.path).path
        if path not in assets:
            self.respond(404, {"error": "Không tìm thấy tài nguyên."})
            return
        filename, content_type = assets[path]
        self.respond(200, (WEB / filename).read_bytes(), content_type)

    def do_POST(self):
        # A JSON request from the same origin is required. No wildcard CORS.
        origin = self.headers.get("Origin")
        if ((origin and origin != f"http://{self.headers.get('Host')}") or
                self.headers.get("Sec-Fetch-Site") == "cross-site"):
            self.respond(403, {"error": "Yêu cầu khác nguồn không được chấp nhận."})
            return
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("Yêu cầu cần có định dạng JSON.")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("Kích thước yêu cầu không hợp lệ.")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Nội dung cần là một JSON object.")
            if self.path == "/api/session":
                key = data.get("level", self.server.catalog.default)
                if not isinstance(key, str):
                    raise ValueError("Mã màn không hợp lệ.")
                session = WebSession(self.server.catalog, key)
                token = secrets.token_urlsafe(32)
                with self.server.sessions_lock:
                    expired = [k for k, v in self.server.sessions.items() if monotonic() - v.touched > 86400]
                    for old in expired:
                        del self.server.sessions[old]
                    if len(self.server.sessions) >= 128:
                        self.respond(503, {"error": "Đã có quá nhiều phiên đang mở."})
                        return
                    self.server.sessions[token] = session
                self.respond(200, {"session": token, "catalog": self.server.catalog.items,
                                   **session.snapshot()})
            elif self.path == "/api/command":
                token = self.headers.get("X-Session", "")
                with self.server.sessions_lock:
                    session = self.server.sessions.get(token)
                if session is None:
                    self.respond(410, {"error": "Phiên đã kết thúc. Tải lại trang để bắt đầu."})
                    return
                command = data.get("command")
                if not isinstance(command, str) or (command == "load" and not isinstance(data.get("level"), str)):
                    raise ValueError("Lệnh hoặc mã màn không hợp lệ.")
                with session.lock:
                    result = session.command(command, data)
                self.respond(200, result)
            else:
                self.respond(404, {"error": "Không tìm thấy API."})
        except (ValueError, TypeError, UnicodeError) as error:
            self.respond(400, {"error": str(error)})


def run_web(host="127.0.0.1", port=8000, initial_level=None, open_browser=True):
    server = GameServer((host, port), Catalog(initial_level))
    address = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{address}:{server.server_port}"
    print(f"Bloxorz: {url}\nPress Ctrl+C to stop.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
