"""Smoke giao diện thật: vẽ mọi màn, chơi tay, giải bất đồng bộ và replay."""
from pathlib import Path
from time import monotonic, sleep
import tkinter as tk

import pytest

from gui import BloxorzApp
from models import Action, Algorithm, SessionPhase


@pytest.fixture(scope="module")
def app():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Máy không hỗ trợ cửa sổ Tk: {exc}")
    root.withdraw()
    levels = Path(__file__).resolve().parents[1] / "levels"
    app = BloxorzApp(root, levels, levels / "basic_01.json")
    yield app
    app.close()


@pytest.fixture(autouse=True)
def reset_session(app):
    # Một Tk root cho cả module, cùng vòng đời với ứng dụng thực tế.
    app.level_var.set("basic_01")
    app._load_selected()


def test_every_level_renders_and_manual_win_restarts(app):
    for level_id in app.paths:
        app.level_var.set(level_id)
        app._load_selected()
        assert app.canvas.find_withtag("tile")
        assert app.canvas.find_withtag("block")
        assert app.controller.level.id == level_id
    app.level_var.set("basic_01")
    app._load_selected()
    app._key(Action.RIGHT)
    app._key(Action.RIGHT)
    assert app.controller.phase == SessionPhase.WON
    assert "Đã thắng" in app.phase_var.get()
    app._restart()
    assert app.controller.action_count == 0


def test_gui_worker_poll_and_replay_controls(app):
    app._solve(Algorithm.ASTAR)
    assert app.new_button.instate(["disabled"])
    assert app.replay_button.instate(["disabled"])
    deadline = monotonic() + 15
    while app.controller.busy and monotonic() < deadline:
        app.root.update()
        sleep(.01)
    assert not app.controller.busy
    assert app.controller.last_result.found
    assert app.replay_button.instate(["!disabled"])
    assert "FOUND" in app.metrics_var.get()
    app._replay()
    for _ in range(3):
        app.controller.advance_replay(app.controller._next_replay_at)
    app.render()
    assert app.controller.phase == SessionPhase.WON
    assert app.controller.action_count == 2
