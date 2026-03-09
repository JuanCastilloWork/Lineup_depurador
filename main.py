
"""
LineUp Depurator - GUI
Integración con depuration.py + config.ini para opciones de usuario.
"""

from __future__ import annotations

import configparser
import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# ── Palette ────────────────────────────────────────────────────────────────
BG       = "#1E1E1E"
SURFACE  = "#272727"
TITLEBAR = "#161616"
BORDER   = "#333333"
INPUT_BG = "#1A1A1A"
ACCENT   = "#4A9EFF"
TEXT     = "#E0E0E0"
MUTED    = "#888888"
SUCCESS  = "#4ADE80"
WARN     = "#F59E0B"
DANGER   = "#FF5A5A"

# ── Fonts ──────────────────────────────────────────────────────────────────
FM     = ("Consolas", 10)
FM_SM  = ("Consolas", 9)
FM_LG  = ("Consolas", 12, "bold")
FUI    = ("Segoe UI", 10)
FUI_SM = ("Segoe UI", 9)
FUI_XS = ("Segoe UI", 8)

# ── Config.ini ─────────────────────────────────────────────────────────────
CONFIG_PATH = Path("config.ini")

DEFAULTS: dict[str, dict[str, str]] = {
    "paths": {
        "folder_path":   "./test/",
        "output_path":   "./output/",
        "template_path": "./templates/report_template.html.j2",
        "fonts_dir":     "./fonts/",
    },
    "params": {
        "min_match_score": "80",
    },
    "validations": {
        "verify_headers":       "true",
        "detect_overlaps":      "true",
        "fuzzy_sheet_matching": "true",
        "strict_headers":       "false",
        "embed_fonts":          "false",
    },
}


def load_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    for section, pairs in DEFAULTS.items():
        cfg[section] = pairs
    if CONFIG_PATH.exists():
        cfg.read(CONFIG_PATH, encoding="utf-8")
    return cfg


def save_config(cfg: configparser.ConfigParser) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        cfg.write(fh)


# ── Queue-based logging handler ────────────────────────────────────────────
class QueueHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord):
        self.q.put((record.levelname.lower(), self.format(record)))


# ── Crisp Toggle ──────────────────────────────────────────────────────────
class Toggle(tk.Canvas):
    """
    Pill toggle drawn at 2x internal resolution so edges are pixel-crisp.
    Logical size: LW x LH px.  The Canvas scrollregion is set to 2x that,
    and the widget is sized to LW x LH so Tk scales the drawing down.
    """
    LW, LH = 46, 24
    S = 1  # render scale

    def __init__(self, parent: tk.Widget, variable: tk.BooleanVar, **kw):
        bg = kw.pop("bg", BG)
        super().__init__(
            parent,
            width=self.LW, height=self.LH,
            bg=bg, highlightthickness=0,
            **kw,
        )
        self.configure(scrollregion=(0, 0, self.LW * self.S, self.LH * self.S))
        self.var = variable
        self._draw()
        self.bind("<Button-1>", lambda _: self.var.set(not self.var.get()))
        self.var.trace_add("write", lambda *_: self._draw())

    def _draw(self):
        s, W, H = self.S, self.LW * self.S, self.LH * self.S
        self.delete("all")
        on   = self.var.get()
        pill = ACCENT if on else "#444444"
        r    = H // 2
        # pill shape: left cap + fill + right cap
        self.create_oval(0, 0, H, H, fill=pill, outline="")
        self.create_oval(W - H, 0, W, H, fill=pill, outline="")
        self.create_rectangle(r, 0, W - r, H, fill=pill, outline="")
        # thumb
        pad = s * 3
        tx  = (W - H + pad) if on else pad
        self.create_oval(tx, pad, tx + H - pad * 2, H - pad,
                         fill="white", outline="")


# ── Layout helpers ─────────────────────────────────────────────────────────
def section_label(parent: tk.Widget, text: str):
    f = tk.Frame(parent, bg=BG)
    f.pack(fill="x", pady=(12, 5))
    tk.Label(f, text=text, font=FM_SM, fg=ACCENT, bg=BG).pack(side="left")
    tk.Frame(f, bg=BORDER, height=1).pack(
        side="left", fill="x", expand=True, padx=(8, 0), pady=1)


def path_row(parent: tk.Widget, label: str, var: tk.StringVar,
             row: int, pick_file: bool = False):
    tk.Label(parent, text=label, font=FM_SM, fg=MUTED, bg=BG, anchor="w"
             ).grid(row=row * 2, column=0, columnspan=2,
                    sticky="w", pady=(8, 2))
    entry = tk.Entry(
        parent, textvariable=var, font=FM_SM,
        bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
        relief="flat", highlightthickness=1,
        highlightcolor=ACCENT, highlightbackground=BORDER,
    )
    entry.grid(row=row * 2 + 1, column=0, sticky="ew", ipady=5)

    def browse():
        p = (filedialog.askopenfilename(
                filetypes=[("Template", "*.j2 *.html"), ("All", "*.*")])
             if pick_file else filedialog.askdirectory())
        if p:
            var.set(p)

    tk.Button(
        parent, text="…", font=FM_SM, bg=SURFACE, fg=MUTED,
        relief="flat", cursor="hand2", padx=10, pady=4,
        activebackground=BORDER, activeforeground=TEXT,
        command=browse,
    ).grid(row=row * 2 + 1, column=1, padx=(6, 0))


def toggle_row(parent: tk.Widget, label: str, desc: str, var: tk.BooleanVar):
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="x", pady=4)
    info = tk.Frame(row, bg=BG)
    info.pack(side="left", fill="x", expand=True)
    tk.Label(info, text=label, font=FUI, fg=TEXT, bg=BG, anchor="w"
             ).pack(anchor="w")
    if desc:
        tk.Label(info, text=desc, font=FUI_XS, fg=MUTED, bg=BG, anchor="w"
                 ).pack(anchor="w")
    Toggle(row, var, bg=BG).pack(side="right", padx=(8, 0), pady=2)
    tk.Frame(parent, bg="#2A2A2A", height=1).pack(fill="x")


# ── Main Application ────────────────────────────────────────────────────────
class LineUpApp(tk.Tk):
    W, H = 640, 620

    def __init__(self):
        super().__init__()
        self.title("LineUp Depurator")
        self.geometry(f"{self.W}x{self.H}")
        self.resizable(False, False)
        self.configure(bg=BG)

        self.cfg = load_config()
        p, v, pr = self.cfg["paths"], self.cfg["validations"], self.cfg["params"]

        # Tk variables wired to config
        self.folder_var   = tk.StringVar(value=p["folder_path"])
        self.output_var   = tk.StringVar(value=p["output_path"])
        self.template_var = tk.StringVar(value=p["template_path"])
        self.fonts_var    = tk.StringVar(value=p["fonts_dir"])
        self.score_var    = tk.IntVar(value=int(pr["min_match_score"]))

        self.val_headers  = tk.BooleanVar(value=v.getboolean("verify_headers"))
        self.val_overlaps = tk.BooleanVar(value=v.getboolean("detect_overlaps"))
        self.val_fuzzy    = tk.BooleanVar(value=v.getboolean("fuzzy_sheet_matching"))
        self.val_strict   = tk.BooleanVar(value=v.getboolean("strict_headers"))
        self.val_fonts    = tk.BooleanVar(value=v.getboolean("embed_fonts"))

        self.running     = False
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.status_text = tk.StringVar(value="● listo")

        self._build()
        self._poll_log()

    # ══ Build UI ═══════════════════════════════════════════════════════════

    def _build(self):
        self._build_titlebar()
        self._build_tabs()
        self._build_statusbar()

    def _build_titlebar(self):
        bar = tk.Frame(self, bg=TITLEBAR, height=40)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="Lineup Diario", font=(FM_SM,20),
                 fg=MUTED, bg=TITLEBAR).pack(side="top", padx=10)

        for w in (bar,):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_move)

    def _drag_start(self, e):
        self._ox, self._oy = e.x, e.y

    def _drag_move(self, e):
        self.geometry(
            f"+{self.winfo_x() + e.x - self._ox}"
            f"+{self.winfo_y() + e.y - self._oy}"
        )

    def _build_tabs(self):
        tab_bar = tk.Frame(self, bg="#1A1A1A", height=36)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        self.tab_btns:   dict[str, tk.Button] = {}
        self.tab_frames: dict[str, tk.Frame]  = {}

        for key, label in [("run", "▶  Ejecutar"),
                            ("config", "⚙  Config"),
                            ("log", "≡  Log")]:
            btn = tk.Button(tab_bar, text=label, font=FM_SM, relief="flat",
                            cursor="hand2",
                            command=lambda k=key: self._switch_tab(k))
            btn.pack(side="left", fill="both", expand=True)
            self.tab_btns[key] = btn

        cont = tk.Frame(self, bg=BG)
        cont.pack(fill="both", expand=True, padx=18, pady=12)

        self.tab_frames["run"]    = self._build_run_tab(cont)
        self.tab_frames["config"] = self._build_config_tab(cont)
        self.tab_frames["log"]    = self._build_log_tab(cont)
        self._switch_tab("run")

    def _switch_tab(self, key: str):
        for f in self.tab_frames.values():
            f.pack_forget()
        self.tab_frames[key].pack(fill="both", expand=True)
        for k, btn in self.tab_btns.items():
            btn.config(fg=ACCENT if k == key else MUTED,
                       bg=BG     if k == key else "#1A1A1A")

    # ── Run tab ───────────────────────────────────────────────────────────
    def _build_run_tab(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=BG)

        section_label(frame, "RUTAS")
        grid = tk.Frame(frame, bg=BG)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1)
        path_row(grid, "CARPETA DE ENTRADA",  self.folder_var,   0)
        path_row(grid, "CARPETA DE SALIDA",   self.output_var,   1)
        path_row(grid, "TEMPLATE REPORTE",    self.template_var, 2, pick_file=True)
        path_row(grid, "DIRECTORIO DE FONTS", self.fonts_var,    3)

        section_label(frame, "PARÁMETROS")
        sc = tk.Frame(frame, bg=BG)
        sc.pack(fill="x", pady=2)
        tk.Label(sc, text="MIN_MATCH_SCORE", font=FM_SM, fg=MUTED, bg=BG
                 ).pack(side="left")
        tk.Label(sc, textvariable=self.score_var, font=FM_SM, fg=TEXT,
                 bg=BG, width=4).pack(side="left", padx=8)
        tk.Scale(sc, from_=0, to=100, orient="horizontal",
                 variable=self.score_var, showvalue=False,
                 bg=BG, fg=TEXT, troughcolor=INPUT_BG,
                 highlightthickness=0, sliderrelief="flat",
                 activebackground=ACCENT
                 ).pack(side="left", fill="x", expand=True)

        self.run_btn = tk.Button(
            frame, text="▶  EJECUTAR DEPURACIÓN", font=FM_LG,
            bg=ACCENT, fg="white", relief="flat", cursor="hand2", pady=10,
            activebackground="#1d4ed8", activeforeground="white",
            command=self._run,
        )
        self.run_btn.pack(fill="x", pady=(16, 0))
        return frame

    # ── Config tab ────────────────────────────────────────────────────────
    def _build_config_tab(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=BG)
        section_label(frame, "VALIDACIONES OPCIONALES")
        toggle_row(frame, "Verificar headers",
                   "Compara encabezados con layout esperado", self.val_headers)
        toggle_row(frame, "Detectar solapamientos",
                   "Revisa conflictos de intervalo entre filas", self.val_overlaps)
        toggle_row(frame, "Fuzzy matching de hojas",
                   "Tolerancia en nombres de hojas Excel", self.val_fuzzy)
        toggle_row(frame, "Headers estrictos",
                   "Score mínimo 95 en lugar del default", self.val_strict)
        toggle_row(frame, "Embeber fuentes en reporte",
                   "Incluye fonts inline en el HTML", self.val_fonts)

        btn_row = tk.Frame(frame, bg=BG)
        btn_row.pack(fill="x", pady=(16, 0))
        tk.Button(
            btn_row, text="💾  Guardar configuración", font=FM_SM,
            bg=SURFACE, fg=TEXT, relief="flat", cursor="hand2",
            padx=10, pady=6,
            activebackground=BORDER, activeforeground=TEXT,
            command=self._save_config,
        ).pack(side="right")

        tk.Label(frame,
                 text="config.ini · Los cambios se aplican al próximo run",
                 font=("Consolas", 8), fg="#555555", bg=BG
                 ).pack(pady=(10, 0))
        return frame

    # ── Log tab ───────────────────────────────────────────────────────────
    def _build_log_tab(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=BG)
        section_label(frame, "LOG DE EJECUCIÓN")

        log_frame = tk.Frame(frame, bg="#111111",
                             highlightthickness=1, highlightbackground=BORDER)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_frame, bg="#111111", fg=MUTED, font=FM_SM,
            relief="flat", state="disabled", wrap="word",
            insertbackground=TEXT,
        )
        scroll = tk.Scrollbar(log_frame, command=self.log_text.yview,
                              bg=SURFACE, troughcolor="#111111")
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        for tag, color in [("info", MUTED), ("warning", WARN),
                           ("error", DANGER), ("critical", DANGER),
                           ("success", SUCCESS), ("idx", "#444444")]:
            self.log_text.tag_config(tag, foreground=color)

        self._append_log("info", "Listo para procesar.")

        btn_row = tk.Frame(frame, bg=BG)
        btn_row.pack(fill="x", pady=(8, 0))
        tk.Button(btn_row, text="Limpiar log", font=FM_SM,
                  bg=SURFACE, fg=MUTED, relief="flat", cursor="hand2",
                  command=self._clear_log).pack(side="right")
        return frame

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=TITLEBAR, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status_lbl = tk.Label(bar, textvariable=self.status_text,
                                   font=FM_SM, fg=SUCCESS, bg=TITLEBAR)
        self.status_lbl.pack(side="left", padx=14)
        tk.Label(bar, text="config.ini · v1.0",
                 font=FM_SM, fg="#555555", bg=TITLEBAR).pack(side="right", padx=14)

    # ══ Actions ══════════════════════════════════════════════════════════════

    def _append_log(self, level: str, msg: str):
        self.log_text.configure(state="normal")
        n = int(self.log_text.index("end-1c").split(".")[0])
        self.log_text.insert("end", f"[{n:02d}] ", "idx")
        self.log_text.insert("end", msg + "\n", level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _set_status(self, text: str, color: str):
        self.status_text.set(text)
        self.status_lbl.configure(fg=color)

    def _save_config(self):
        self.cfg["paths"]["folder_path"]              = self.folder_var.get()
        self.cfg["paths"]["output_path"]              = self.output_var.get()
        self.cfg["paths"]["template_path"]            = self.template_var.get()
        self.cfg["paths"]["fonts_dir"]                = self.fonts_var.get()
        self.cfg["params"]["min_match_score"]         = str(self.score_var.get())
        self.cfg["validations"]["verify_headers"]     = str(self.val_headers.get()).lower()
        self.cfg["validations"]["detect_overlaps"]    = str(self.val_overlaps.get()).lower()
        self.cfg["validations"]["fuzzy_sheet_matching"] = str(self.val_fuzzy.get()).lower()
        self.cfg["validations"]["strict_headers"]     = str(self.val_strict.get()).lower()
        self.cfg["validations"]["embed_fonts"]        = str(self.val_fonts.get()).lower()
        save_config(self.cfg)
        self._append_log("success", "Configuración guardada en config.ini")

    # ── Run ───────────────────────────────────────────────────────────────
    def _run(self):
        if self.running:
            return
        self._save_config()

        folder = Path(self.folder_var.get())
        if not folder.exists():
            messagebox.showerror(
                "Carpeta no encontrada",
                f"La carpeta de entrada no existe:\n{folder}",
            )
            return

        self.running = True
        self.run_btn.configure(text="⏳  Procesando...",
                               bg="#1d3a5e", state="disabled")
        self._set_status("● procesando", ACCENT)
        self._switch_tab("log")
        self._clear_log()
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self):
        """Background thread: imports and calls depuration.py."""
        qh = QueueHandler(self.log_queue)
        qh.setFormatter(logging.Formatter("%(message)s"))

        # depuration.py crea dos loggers nombrados a nivel de módulo:
        #   logging.getLogger(__name__)  →  'depuration'
        #   logging.getLogger('console') →  'console'
        # Les añadimos el QueueHandler directamente para capturar
        # sus mensajes en el widget, sin tocar el archivo de depuration.
        _LOGGER_NAMES = ("depuration", "console", "__main__")
        watched: list[logging.Logger] = []
        for name in _LOGGER_NAMES:
            lg = logging.getLogger(name)
            lg.addHandler(qh)
            watched.append(lg)
        # También cubrimos el root por si algún otro módulo loguea ahí
        root_log = logging.getLogger()
        root_log.addHandler(qh)

        try:
            from depuration import depurate_lineup_files  # type: ignore
            from report import render_report              # type: ignore
            from config import OFFICES                    # type: ignore
            import config as _cfg                         # type: ignore
            from client_report import LineUpExcelReport

            cfg = load_config()
            p, v, pr = cfg["paths"], cfg["validations"], cfg["params"]

            folder_path   = Path(p["folder_path"])
            output_path   = Path(p["output_path"])
            template_path = Path(p["template_path"])
            fonts_dir     = Path(p["fonts_dir"])
            min_score     = int(pr["min_match_score"])
            embed_fonts   = v.getboolean("embed_fonts")

            # Patch runtime constant
            _cfg.MIN_MATCH_SCORE = min_score

            # ── Optional: patch header verify strictness ──────────────────
            # depurate_lineup_files passes min_score; strict_headers would
            # need a separate constant in config.py if desired.

            result = depurate_lineup_files(folder_path, OFFICES, min_score)

            output_path.mkdir(parents=True, exist_ok=True)
            if result.has_errors:

                out = render_report(
                    result=result,
                    template_path=template_path,
                    output_path=output_path / "reporte_depuracion.html",
                    embed_fonts=embed_fonts,
                    fonts_dir=fonts_dir,
                )
                self.log_queue.put(("success", f"✔  Reporte generado: {out}"))
            else:
                LineUpExcelReport(result.offices).create_report(output_path/'lineup_diario.xlsx')

        except ImportError as exc:
            self.log_queue.put(("error", f"ImportError: {exc}"))
            self.log_queue.put(("error",
                "Asegurate de correr la GUI desde el directorio raíz del proyecto."))
        except Exception as exc:
            self.log_queue.put(("error", f"Error inesperado: {exc}"))
            import traceback
            for line in traceback.format_exc().splitlines():
                self.log_queue.put(("error", line))
        finally:
            for lg in watched:
                lg.removeHandler(qh)
            root_log.removeHandler(qh)
            self.after(0, self._finish_run)

    def _finish_run(self):
        self.running = False
        self.run_btn.configure(text="▶  EJECUTAR DEPURACIÓN",
                               bg=ACCENT, state="normal")
        self._set_status("● listo", SUCCESS)

    def _poll_log(self):
        """Drain log_queue into the Text widget — runs every 80 ms on main thread."""
        try:
            while True:
                level, msg = self.log_queue.get_nowait()
                tag = {"warning": "warning", "error": "error",
                       "critical": "critical", "success": "success"
                       }.get(level, "info")
                self._append_log(tag, msg)
        except queue.Empty:
            pass
        self.after(80, self._poll_log)

# ── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = LineUpApp()
    app.mainloop()
