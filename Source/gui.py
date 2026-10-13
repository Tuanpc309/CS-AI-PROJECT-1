"""Giao diện Tkinter 2D. Luật và vòng đời phiên chơi nằm ở controller."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from controller import GameController
from engine import occupied_cells
from models import Action, Algorithm, CostPolicy, Mode, SessionPhase


class BloxorzApp:
    def __init__(self, root: tk.Tk, levels_dir: Path, initial_level: Path | None = None) -> None:
        self.root = root
        self.controller = GameController()
        self.paths = {p.stem: p for p in sorted(Path(levels_dir).glob("*.json"))}
        if initial_level and initial_level.is_file():
            self.paths[initial_level.stem] = initial_level
        self._closed = False
        self._tick_id: str | None = None
        root.title("Bloxorz Solver")
        root.geometry("1080x760")
        root.minsize(900, 680)
        root.configure(bg="#f1f5f9")
        self._build()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Up>", lambda e: self._key(Action.UP))
        root.bind("<Down>", lambda e: self._key(Action.DOWN))
        root.bind("<Left>", lambda e: self._key(Action.LEFT))
        root.bind("<Right>", lambda e: self._key(Action.RIGHT))
        root.bind("<space>", lambda e: self._key(Action.SWITCH))
        self.canvas.bind("<Configure>", lambda e: self.draw_board())
        if self.paths:
            chosen = initial_level.stem if initial_level and initial_level.stem in self.paths else next(iter(self.paths))
            self.level_var.set(chosen)
            self._load_selected()
        else:
            self.controller.message = "Không tìm thấy màn JSON trong thư mục levels."
            self.render()
        self._tick_id = root.after(50, self._tick)

    def _build(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f1f5f9")
        style.configure("TLabel", background="#f1f5f9", foreground="#1e293b", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        style.configure("Sub.TLabel", foreground="#64748b")
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 8))
        style.configure("Accent.TButton", background="#334155", foreground="white")
        style.map("Accent.TButton", background=[("active", "#475569"), ("disabled", "#cbd5e1")])
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="BLOXORZ SOLVER", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Lăn khối vào goal · Chơi tay hoặc khám phá bốn thuật toán tìm kiếm", style="Sub.TLabel").pack(anchor="w", pady=(3, 16))
        content = ttk.Frame(outer)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=0)
        content.rowconfigure(0, weight=1)
        board = ttk.Frame(content)
        board.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        self.phase_var = tk.StringVar(value="Đang chơi")
        ttk.Label(board, textvariable=self.phase_var, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        self.canvas = tk.Canvas(board, bg="#e8eef5", highlightthickness=0, width=640, height=480)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set())
        self.legend = ttk.Label(board, text="F Sàn    G Goal    O Fragile    B Cầu    S Soft    X Heavy    ( ) Split\nMũi tên: di chuyển    Space: đổi cube A/B", style="Sub.TLabel")
        self.legend.pack(anchor="w", pady=(12, 0))
        # Bảng kết quả dài hơn vùng nhìn khi cửa sổ thấp: cuộn cột phải.
        side_shell = ttk.Frame(content)
        side_shell.grid(row=0, column=1, sticky="ns")
        self.side_scroll = tk.Canvas(side_shell, bg="#f1f5f9", highlightthickness=0, width=318)
        self.side_scroll.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(side_shell, orient="vertical", command=self.side_scroll.yview)
        scrollbar.pack(side="right", fill="y")
        self.side_scroll.configure(yscrollcommand=scrollbar.set)
        side = self.side_frame = ttk.Frame(self.side_scroll, width=300)
        side_window = self.side_scroll.create_window((0, 0), window=side, anchor="nw")
        side.bind("<Configure>", lambda e: self.side_scroll.configure(scrollregion=self.side_scroll.bbox("all")))
        self.side_scroll.bind("<Configure>", lambda e: self.side_scroll.itemconfigure(side_window, width=e.width))
        self.root.bind("<MouseWheel>", self._scroll_sidebar, add="+")
        self.level_var = tk.StringVar()
        self.policy_var = tk.StringVar(value=CostPolicy.UNIT.value)
        ttk.Label(side, text="MÀN CHƠI", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.level_box = ttk.Combobox(side, textvariable=self.level_var, values=tuple(self.paths), state="readonly", width=31)
        self.level_box.pack(fill="x", pady=(6, 8))
        self.level_box.bind("<<ComboboxSelected>>", lambda e: self._load_selected())
        buttons = ttk.Frame(side)
        buttons.pack(fill="x")
        self.new_button = ttk.Button(buttons, text="New Game", command=self._load_selected)
        self.new_button.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.restart_button = ttk.Button(buttons, text="Restart", command=self._restart)
        self.restart_button.pack(side="left", expand=True, fill="x")
        ttk.Separator(side).pack(fill="x", pady=18)
        ttk.Label(side, text="GIẢI TỪ VỊ TRÍ HIỆN TẠI", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(side, text="Chi phí", style="Sub.TLabel").pack(anchor="w", pady=(8, 3))
        self.policy_box = ttk.Combobox(side, textvariable=self.policy_var,
            values=tuple(p.value for p in CostPolicy), state="readonly", width=31)
        self.policy_box.pack(fill="x")
        algorithms = ttk.Frame(side)
        algorithms.pack(fill="x", pady=10)
        self.solve_buttons: list[ttk.Button] = []
        for index, algorithm in enumerate(Algorithm):
            button = ttk.Button(algorithms, text=algorithm.value.replace("ASTAR", "A*"),
                style="Accent.TButton", command=lambda a=algorithm: self._solve(a))
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0 if index % 2 == 0 else 4, 0), pady=3)
            self.solve_buttons.append(button)
        algorithms.columnconfigure(0, weight=1)
        algorithms.columnconfigure(1, weight=1)
        self.replay_button = ttk.Button(side, text="Replay lời giải", command=self._replay)
        self.replay_button.pack(fill="x")
        ttk.Label(side, text="BFS: ít thao tác nhất\nUCS/A*: chi phí thấp nhất", style="Sub.TLabel").pack(anchor="w", pady=(8, 0))
        ttk.Separator(side).pack(fill="x", pady=16)
        ttk.Label(side, text="KẾT QUẢ", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.metrics_var = tk.StringVar(value="Chưa chạy solver.")
        ttk.Label(side, textvariable=self.metrics_var, justify="left", wraplength=300).pack(anchor="w", pady=(8, 8))
        self.actions_text = tk.Text(side, height=6, width=34, wrap="word", font=("Segoe UI", 9),
            bg="white", fg="#475569", relief="flat", state="disabled", padx=8, pady=8)
        self.actions_text.pack(fill="x")
        self.status_var = tk.StringVar()
        ttk.Label(outer, textvariable=self.status_var, wraplength=990, justify="left").pack(anchor="w", pady=(18, 0))

    def _load_selected(self) -> None:
        path = self.paths.get(self.level_var.get())
        if path is None or self.controller.busy:
            return
        try:
            self.controller.load(path)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Không tải được màn", str(exc), parent=self.root)
        self.render()
        self.canvas.focus_set()

    def _scroll_sidebar(self, event: tk.Event) -> str | None:
        widget_path = str(event.widget)
        if (widget_path.startswith(str(self.side_frame)) or event.widget == self.side_scroll):
            if isinstance(event.widget, (ttk.Combobox, tk.Text)):
                return None
            self.side_scroll.yview_scroll(-int(event.delta / 120), "units")
            return "break"
        return None

    def _restart(self) -> None:
        self.controller.restart()
        self.render()
        self.canvas.focus_set()

    def _key(self, action: Action) -> str | None:
        # Khi combobox mở, phím mũi tên vẫn dùng để chọn mục, không di chuyển khối.
        if self.root.focus_get() in (self.level_box, self.policy_box):
            return None
        if self.controller.handle_action(action):
            self.render()
        return "break"

    def _solve(self, algorithm: Algorithm) -> None:
        self.controller.begin_solve(algorithm, CostPolicy(self.policy_var.get()))
        self.render()
        self.canvas.focus_set()

    def _replay(self) -> None:
        self.controller.begin_replay()
        self.render()
        self.canvas.focus_set()

    def _tick(self) -> None:
        if self._closed:
            return
        changed = self.controller.poll_solver()
        changed = self.controller.advance_replay() or changed
        if changed:
            self.render()
        self._tick_id = self.root.after(50, self._tick)

    def render(self) -> None:
        c = self.controller
        phases = {SessionPhase.PLAYING: "Đang chơi", SessionPhase.WON: "Đã thắng",
                  SessionPhase.LOST: "Khối bị rơi", SessionPhase.SOLVING: "Đang tìm lời giải…",
                  SessionPhase.REPLAYING: "Đang phát lại…"}
        self.phase_var.set(f"{phases[c.phase]}  ·  {c.action_count} thao tác")
        self.status_var.set(c.message)
        enabled = "disabled" if c.busy else "normal"
        self.new_button.configure(state=enabled)
        self.restart_button.configure(state=enabled)
        self.level_box.configure(state="disabled" if c.busy else "readonly")
        self.policy_box.configure(state="disabled" if c.busy else "readonly")
        for button in self.solve_buttons:
            button.configure(state="disabled" if c.busy or c.phase == SessionPhase.LOST or c.level is None else "normal")
        self.replay_button.configure(state="normal" if c.can_replay else "disabled")
        result = c.last_result
        if result is None:
            self.metrics_var.set("Đang tìm kiếm…" if c.phase == SessionPhase.SOLVING else "Chưa có kết quả tìm kiếm.")
            actions = ""
        else:
            def count(value: int | None) -> str:
                return "—" if value is None else str(value)
            self.metrics_var.set(
                f"Trạng thái: {result.status.value}\n"
                f"Thuật toán: {result.metadata.get('algorithm', '—')}\n"
                f"Policy: {result.metadata.get('cost_policy', '—')}\n"
                f"Thao tác: {count(result.solution_length)}  ·  Cost: {count(result.solution_cost)}\n"
                f"Di chuyển: {count(result.movement_count)}  ·  Đổi cube: {count(result.selection_count)}\n"
                f"Tổng: {result.total_time_seconds:.4f} s\n"
                f"Search: {result.search_time_seconds:.4f} s\n"
                f"Tiền xử lý: {result.preprocessing_time_seconds:.4f} s\n"
                f"Peak Python: {result.peak_memory_bytes / 1024 ** 2:.3f} MiB\n"
                f"Expanded: {result.expanded_nodes}")
            if result.metadata.get("metrics_available") is False:
                self.metrics_var.set(f"Trạng thái: {result.status.value}\nChưa thu được số liệu từ worker.")
            actions = " → ".join(a.value for a in result.actions) if result.actions else ("Lời giải rỗng: đã ở goal." if result.found else "Chưa có lời giải.")
        self.actions_text.configure(state="normal")
        self.actions_text.delete("1.0", "end")
        self.actions_text.insert("1.0", actions)
        self.actions_text.configure(state="disabled")
        self.draw_board()

    def draw_board(self) -> None:
        self.canvas.delete("all")
        level, state = self.controller.level, self.controller.current_state
        if level is None or state is None:
            return
        w, h = max(400, self.canvas.winfo_width()), max(300, self.canvas.winfo_height())
        size = min(48, max(18, min((w - 48) // level.width, (h - 48) // level.height)))
        x0, y0 = (w - level.width * size) / 2, (h - level.height * size) / 2
        colours = {"F": "#d4dce6", "G": "#172033", "O": "#fdba74", "S": "#a7d9ba",
                   "X": "#c4b5fd", "T": "#67d6cf", "B": "#93c5fd"}
        for r, row in enumerate(level.grid):
            for col, tile in enumerate(row):
                if tile == ".":
                    continue
                cell = (r, col)
                x, y = x0 + col * size, y0 + r * size
                colour = colours[tile]
                bridge_on = True
                if tile == "B":
                    index = level.bridge_index_at(cell)
                    bridge_on = index is not None and state.bridges[index]
                    colour = "#93c5fd" if bridge_on else "#e8eef5"
                self.canvas.create_rectangle(x+2, y+2, x+size-2, y+size-2, fill=colour,
                    outline="#64748b" if bridge_on else "#94a3b8", width=1, dash=() if bridge_on else (3, 3), tags="tile")
                symbol = {"G": "G", "O": "O", "S": "S", "X": "X", "T": "( )", "B": "B" if bridge_on else "B−"}.get(tile)
                if symbol:
                    self.canvas.create_text(x+size/2, y+size/2, text=symbol,
                        fill="white" if tile == "G" else "#334155", font=("Segoe UI", max(9, size//4), "bold"), tags="tile-symbol")
        cells = occupied_cells(state)
        if state.mode == Mode.MERGED:
            rr, cc = zip(*cells)
            x, y = x0 + min(cc)*size, y0 + min(rr)*size
            x2, y2 = x0 + (max(cc)+1)*size, y0 + (max(rr)+1)*size
            self.canvas.create_rectangle(x+6, y+6, x2-6, y2-6, fill="#fbbf24", outline="#92400e", width=3, tags="block")
            self.canvas.create_text((x+x2)/2, (y+y2)/2, text=state.orientation.value,
                fill="#78350f", font=("Segoe UI", max(10, size//3), "bold"), tags="block-label")
        else:
            for index, (r, col) in enumerate(state.cubes):
                x, y = x0+col*size, y0+r*size
                self.canvas.create_rectangle(x+6, y+6, x+size-6, y+size-6,
                    fill="#fbbf24" if index == 0 else "#f9a8d4", outline="#0f172a" if index == state.active_cube else "#64748b",
                    width=4 if index == state.active_cube else 1, tags="block")
                self.canvas.create_text(x+size/2, y+size/2, text="AB"[index], fill="#1e293b",
                    font=("Segoe UI", max(10, size//3), "bold"), tags="block-label")
        # Ký hiệu nhỏ ở góc còn thấy được khi khối phủ switch/fragile/goal.
        for r, col in cells:
            tile = level.tile_at((r, col))
            if tile in "GOSXT":
                self.canvas.create_text(x0+col*size+5, y0+r*size+5, anchor="nw",
                    text="( )" if tile == "T" else tile, fill="#334155", font=("Segoe UI", 8, "bold"), tags="overlay-symbol")
        if self.controller.phase == SessionPhase.LOST:
            self.canvas.create_text(w/2, max(18, y0-18), text="KHỐI BỊ RƠI — RESTART ĐỂ THỬ LẠI",
                fill="#b91c1c", font=("Segoe UI", 12, "bold"))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._tick_id:
            self.root.after_cancel(self._tick_id)
        self.controller.close()
        self.root.destroy()
