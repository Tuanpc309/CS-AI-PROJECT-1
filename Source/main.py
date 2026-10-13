"""Entry point: python main.py [--level levels/basic_01.json]."""
from __future__ import annotations

import argparse
import multiprocessing
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Bloxorz Solver — chơi tay và BFS/DFS/UCS/A*")
    parser.add_argument("--level", type=Path, help="Màn JSON muốn mở; mặc định basic_01")
    args = parser.parse_args()
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
