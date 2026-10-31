"""Responsive browser UI. All moves still go through the existing Python engine.

Run: python main.py --web --no-browser
The server is local by default; --host 0.0.0.0 enables devices on the same LAN.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from functools import lru_cache
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import threading
import sys
from time import monotonic
from urllib.parse import urlsplit
import webbrowser

from controller import GameController
from engine import is_goal, transition
from geometry import move
from loader import load_level
from models import (Action, Algorithm, CostPolicy, SearchConfig, SearchResult,
                    SearchStatus, SessionPhase, TransitionStatus)
from solvers import solve
from solvers.common import normalize_algorithm, step_cost
from worker import start_search

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
    def __init__(self, catalog: Catalog, level_id: str, *, sync_solver: bool = False):
        self.catalog = catalog
        self.game = GameController()
        self.lock = threading.Lock()
        self.touched = monotonic()
        self.history: list[tuple] = []
        self.paused = False
        self.undos = UNDO_LIMIT
        self.fallen_state = None
        self.sync_solver = sync_solver
        self.results: dict[str, dict] = {}
        self._origin = None
        self._search_job = None
        self._retired_jobs = []
        self._active_search = None
        self._request_id = 0
        self._replay = dict(active=False, algorithm=None, cost_policy=None, index=0, total=0, action=None)
        self.load(level_id)

    def load(self, level_id: str):
        if not isinstance(level_id, str) or level_id not in self.catalog.paths:
            raise ValueError("Không tìm thấy màn chơi.")
        if self._active_search or self._replay["active"]:
            raise ValueError("Hãy dừng tìm kiếm/phát lại trước khi đổi màn.")
        self.game.load(self.catalog.paths[level_id])
        self.level_id = level_id
        self.optimal = self.catalog.optimum(level_id)
        self.history.clear()
        self.undos = UNDO_LIMIT
        self.paused = False
        self.fallen_state = None
        self._clear_solutions()

    def _clear_solutions(self):
        self.results.clear()
        self._origin = None
        self._replay = dict(active=False, algorithm=None, cost_policy=None, index=0, total=0, action=None)

    @staticmethod
    def _selection(data):
        algorithm, policy = data.get("algorithm"), data.get("cost_policy", "UNIT")
        if not isinstance(algorithm, str) or not isinstance(policy, str):
            raise ValueError("Thuật toán và chi phí phải là chuỗi.")
        try:
            return normalize_algorithm(algorithm), CostPolicy(policy)
        except ValueError:
            raise ValueError("Chọn BFS, DFS, UCS hoặc A* và chi phí hợp lệ.") from None

    @staticmethod
    def _config(data, *, measure_memory):
        seconds = data.get("time_limit_seconds", 30.0)
        memory = data.get("memory_limit_bytes", 256 * 1024 * 1024)
        if (type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds <= 30
                or type(memory) is not int or not 0 <= memory <= 256 * 1024 * 1024):
            raise ValueError("Ngân sách phải từ 0 đến 30 giây và 256 MiB.")
        return SearchConfig(cost_policy=CostPolicy(data.get("cost_policy", "UNIT")),
                            time_limit_seconds=seconds, memory_limit_bytes=memory,
                            measure_memory=measure_memory)

    def _memory_available(self):
        if sys.platform != "emscripten":
            return True
        # Some WASM builds cannot trace allocations. Never report their 0 as a measurement.
        try:
            import tracemalloc
            tracemalloc.start(1)
            probe = bytearray(1024)
            available = tracemalloc.get_traced_memory()[1] >= len(probe)
            tracemalloc.stop()
            return available
        except (RuntimeError, NotImplementedError):
            return False

    def _verify(self, result, policy):
        if not result.found:
            return result
        state = self._origin["state"]
        total_cost = 0
        for action in result.actions:
            step = transition(self.game.level, state, action)
            if step.status not in (TransitionStatus.VALID, TransitionStatus.WIN) or step.next_state is None:
                return replace(result, status=SearchStatus.ERROR, actions=(), solution_length=None,
                               movement_count=None, selection_count=None, solution_cost=None,
                               metadata={**result.metadata, "message": "Lời giải không qua được kiểm tra engine.",
                                         "replay_verified": False})
            total_cost += step_cost(self.game.level, state, action, step.next_state, step.events, policy)
            state = step.next_state
        switches = sum(action == Action.SWITCH for action in result.actions)
        if (not is_goal(self.game.level, state) or result.solution_cost != total_cost
                or result.solution_length != len(result.actions) or result.selection_count != switches
                or result.movement_count != len(result.actions) - switches):
            return replace(result, status=SearchStatus.ERROR, actions=(), solution_length=None,
                           movement_count=None, selection_count=None, solution_cost=None,
                           metadata={**result.metadata, "message": "Lời giải hoặc metrics không khớp engine.",
                                     "replay_verified": False})
        return replace(result, metadata={**result.metadata, "replay_verified": True})

    def _finish_search(self, result):
        active = self._active_search
        if active is None:
            return
        algorithm, policy = Algorithm(active["algorithm"]), CostPolicy(active["cost_policy"])
        result = self._verify(result, policy)
        record = asdict(result)
        record["status"] = result.status.value
        record["actions"] = [action.value for action in result.actions]
        record.update(algorithm=algorithm.value, cost_policy=policy.value)
        measured = result.metadata.get("metrics_available", True)
        memory_available = measured and result.metadata.get("memory_measurement") != "disabled"
        record["metadata"] = {**result.metadata, "memory_available": memory_available}
        if not measured:
            for field in ("preprocessing_time_seconds", "search_time_seconds", "total_time_seconds", "expanded_nodes"):
                record[field] = None
        if not memory_available:
            record["peak_memory_bytes"] = None
        self.results[f"{algorithm.value}:{policy.value}"] = record
        self._active_search = None

    def _reap(self):
        self._retired_jobs = [job for job in self._retired_jobs if not job.reap()]

    def _poll_search(self):
        self._reap()
        if self._search_job is None:
            return
        item = self._search_job.poll()
        if item is None:
            return
        request_id, result = item
        self._retired_jobs.append(self._search_job)
        self._search_job = None
        if request_id == self._request_id:
            self._finish_search(result)

    def _solve(self, data):
        algorithm, policy = self._selection(data)
        available = self._memory_available()
        config = self._config(data, measure_memory=available)
        if self._active_search or self._replay["active"]:
            raise ValueError("Đang tìm kiếm hoặc phát lại lời giải.")
        if self.game.phase == SessionPhase.LOST:
            raise ValueError("Hãy Restart hoặc hoàn tác trước khi tìm lời giải.")
        if self._origin is None:
            self._origin = dict(state=self.game.current_state, moves=self.game.action_count,
                                history=tuple(self.history), undos=self.undos)
        self._active_search = dict(algorithm=algorithm.value, cost_policy=policy.value)
        self._request_id += 1
        if self.sync_solver:
            self._finish_search(solve(self.game.level, self._origin["state"], algorithm, config))
        else:
            try:
                self._search_job = start_search(self._request_id, self.game.level,
                                                self._origin["state"], algorithm, config)
            except Exception as error:
                self._finish_search(SearchResult(SearchStatus.ERROR, metadata={
                    "message": f"Không khởi động được solver: {error}", "metrics_available": False}))

    def _cancel_search(self):
        if self._search_job is not None:
            self._search_job.stop()
            self._retired_jobs.append(self._search_job)
            self._search_job = None
        if self._active_search:
            active = self._active_search
            key = f"{active['algorithm']}:{active['cost_policy']}"
            self.results[key] = {**active, "status": "CANCELLED", "actions": [],
                                 "solution_length": None, "solution_cost": None,
                                 "movement_count": None, "selection_count": None,
                                 "preprocessing_time_seconds": None, "search_time_seconds": None,
                                 "total_time_seconds": None, "peak_memory_bytes": None, "expanded_nodes": None,
                                 "metadata": {"message": "Đã dừng tìm kiếm.", "metrics_available": False,
                                              "memory_available": False}}
        self._active_search = None
        self._request_id += 1

    def _start_replay(self, data):
        algorithm, policy = self._selection(data)
        record = self.results.get(f"{algorithm.value}:{policy.value}")
        if self._origin is None or record is None or record["status"] != "FOUND":
            raise ValueError("Thuật toán này chưa có lời giải để phát lại.")
        game = self.game
        game.current_state, game.action_count = self._origin["state"], self._origin["moves"]
        game.phase = SessionPhase.PLAYING
        game.last_events = ()
        self.history = list(self._origin["history"])
        self.undos = self._origin["undos"]
        self.fallen_state = None
        self.paused = False
        self._replay_actions = tuple(Action(action) for action in record["actions"])
        self._replay = dict(active=bool(self._replay_actions), algorithm=algorithm.value,
                            cost_policy=policy.value, index=0, total=len(self._replay_actions), action=None)
        if not self._replay_actions:
            game.phase = SessionPhase.WON if is_goal(game.level, game.current_state) else SessionPhase.PLAYING
        game.message = "Đang phát lại lời giải." if self._replay["active"] else "Đã ở ô đích."

    def _replay_step(self):
        if not self._replay["active"]:
            self._replay["action"] = None
            return
        game = self.game
        action = self._replay_actions[self._replay["index"]]
        previous = (game.current_state, game.action_count)
        game.handle_action(action)
        if game.current_state == previous[0] or game.phase == SessionPhase.LOST:
            self._replay["active"] = False
            game.message = "Lỗi phát lại: action không còn hợp lệ."
            raise ValueError(game.message)
        self.history.append(previous)
        self._replay["index"] += 1
        self._replay["action"] = action.value
        if self._replay["index"] == self._replay["total"]:
            self._replay["active"] = False
            if not is_goal(game.level, game.current_state):
                raise ValueError("Lỗi phát lại: chưa tới ô đích.")
            game.message = "Phát lại hoàn tất."

    def close(self):
        self._cancel_search()
        for job in self._retired_jobs:
            job.stop()
            if not job.reaped:
                job.process.join(timeout=.3)
                job.reap()
        self._retired_jobs.clear()
        self.game.close()

    def command(self, command: str, data: dict):
        game = self.game
        self._poll_search()
        if self._active_search and command not in ("state", "solve_poll", "solve_cancel"):
            raise ValueError("Đang tìm lời giải. Hãy chờ hoặc dừng tìm kiếm.")
        if self._replay["active"] and command not in ("state", "replay_step", "replay_stop"):
            raise ValueError("Đang phát lại. Hãy dừng phát lại trước.")
        if command == "solve":
            self._solve(data)
        elif command == "solve_poll":
            pass
        elif command == "solve_cancel":
            self._cancel_search()
        elif command == "replay_start":
            self._start_replay(data)
        elif command == "replay_step":
            self._replay_step()
        elif command == "replay_stop":
            self._replay["active"] = False
            self._replay["action"] = None
            self.paused = False
            game.message = "Đã dừng phát lại ở trạng thái hiện tại."
        elif command == "load":
            self.load(data.get("level", ""))
        elif command == "restart":
            game.restart()
            self.history.clear()
            self.undos = UNDO_LIMIT
            self.paused = False
            self.fallen_state = None
            self._clear_solutions()
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
                self._clear_solutions()
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
                    self._clear_solutions()
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
        phase = ("SOLVING" if self._active_search else "REPLAYING" if self._replay["active"]
                 else "PAUSED" if self.paused and game.phase == SessionPhase.PLAYING else game.phase.value)
        return {"level": {**asdict(game.level), **info,
                          "width": game.level.width, "height": game.level.height, "optimal": optimal,
                          "thresholds": thresholds},
                "state": asdict(game.current_state),
                "fallenState": asdict(self.fallen_state) if self.fallen_state else None,
                "phase": phase,
                "moves": game.action_count, "stars": stars,
                "undos": self.undos, "undoLimit": UNDO_LIMIT,
                "canUndo": bool(self.history and self.undos and not self.paused
                                and not self._active_search and not self._replay["active"]),
                "message": game.message,
                "events": [asdict(event) for event in game.last_events],
                "solver": {"results": {key: dict(record) for key, record in self.results.items()},
                           "active": dict(self._active_search) if self._active_search else None,
                           "busy": self._active_search is not None,
                           # The static runtime solves inside one WASM worker. Its
                           # message queue cannot interrupt a synchronous search.
                           "can_cancel": not self.sync_solver,
                           "origin_moves": self._origin["moves"] if self._origin else None},
                "replay": dict(self._replay)}


class GameServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, catalog):
        self.catalog = catalog
        self.sessions: dict[str, WebSession] = {}
        self.sessions_lock = threading.Lock()
        super().__init__(address, GameHandler)

    def server_close(self):
        with self.sessions_lock:
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for session in sessions:
            with session.lock:
                session.close()
        super().server_close()


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
                  "/solutions.js": ("solutions.js", "text/javascript; charset=utf-8"),
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
                        self.server.sessions[old].close()
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
