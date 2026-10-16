"""Entry point: python main.py [--level levels/basic_01.json]."""
from __future__ import annotations

import argparse
import multiprocessing
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Bloxorz Solver — chơi tay và BFS/DFS/UCS/A*")
    parser.add_argument("--level", type=Path, help="Màn JSON muốn mở; mặc định basic_01")
    parser.add_argument("--web", action="store_true", help="Mở giao diện web isometric, hỗ trợ mobile")
    parser.add_argument("--host", default="127.0.0.1", help="Địa chỉ web server; 0.0.0.0 để chơi qua LAN")
    parser.add_argument("--port", type=int, default=8000, help="Cổng web server (mặc định 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Không tự mở trình duyệt")
    args = parser.parse_args()
    if args.web:
        from webapp import run_web
        run_web(args.host, args.port, args.level, not args.no_browser)
        return
    import tkinter as tk
    from gui import BloxorzApp
    base = Path(__file__).resolve().parent
    level = args.level or base / "levels" / "basic_01.json"
    root = tk.Tk()
    BloxorzApp(root, base / "levels", level)
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
