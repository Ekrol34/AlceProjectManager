#!/usr/bin/env python3
"""
Alce Project Manager
---------------------
Visual project manager based on the AlceEngine-Project repository.

Requirements:
    pip install gitpython

Usage:
    python alce_project_manager.py
"""

import os, sys, stat, json, shutil, threading, subprocess, base64, platform, struct
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

try:
    import git
except ImportError:
    print("Please install gitpython: pip install gitpython")
    sys.exit(1)

def resource_path(relative):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.abspath("."), relative)

# ─── Constants ────────────────────────────────────────────────────────────────
REPO_URL    = "https://github.com/Ekrol34/AlceEngine"
AUTHOR_URL  = "https://github.com/Ekrol34"
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".alce_manager.json")

KNOWN_EDITORS = [
    ("Visual Studio Code", ["code"]),
    ("Visual Studio",      ["devenv"]),
    ("Cursor",             ["cursor"]),
    ("Sublime Text",       ["subl", "sublime_text"]),
    ("Notepad++",          ["notepad++"]),
    ("PyCharm",            ["pycharm", "charm"]),
    ("Neovim",             ["nvim"]),
    ("Vim",                ["vim"]),
    ("Atom",               ["atom"]),
    ("Other (browse...)",  []),
]

# ─── Theme definitions ────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "BG_DARK":  "#0D0F14",
        "BG_PANEL": "#13161E",
        "BG_CARD":  "#1A1E2A",
        "BG_HOVER": "#222636",
        "TEXT_PRI": "#E8EAF6",
        "TEXT_SEC": "#7A82A6",
        "TEXT_DIM": "#404668",
        "BORDER":   "#252A3A",
        "LOG_BG":   "#13161E",
        "LOG_FG":   "#7A82A6",
    },
    "light": {
        "BG_DARK":  "#F0F2F8",
        "BG_PANEL": "#E2E6F0",
        "BG_CARD":  "#FFFFFF",
        "BG_HOVER": "#D6DCF0",
        "TEXT_PRI": "#1A1E2A",
        "TEXT_SEC": "#4A5280",
        "TEXT_DIM": "#9AA0C0",
        "BORDER":   "#C8CFDF",
        "LOG_BG":   "#E2E6F0",
        "LOG_FG":   "#4A5280",
    },
}

ACCENT  = "#5B8CFF"
ACCENT2 = "#3DFFC0"
ACCENT3 = "#C084FC"
DANGER  = "#FF4F6B"
SUCCESS = "#3DFFC0"
WARNING = "#FFB347"

FONT_TITLE = ("Courier New", 22, "bold")
FONT_HEAD  = ("Courier New", 11, "bold")
FONT_BODY  = ("Courier New", 10)
FONT_SMALL = ("Courier New", 9)
FONT_MONO  = ("Courier New", 9)


# ─── OS theme detection ────────────────────────────────────────────────────────
def detect_system_theme():
    try:
        if platform.system() == "Windows":
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            v, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return "light" if v == 1 else "dark"
        elif platform.system() == "Darwin":
            r = subprocess.run(["defaults","read","-g","AppleInterfaceStyle"],
                               capture_output=True, text=True)
            return "dark" if "Dark" in r.stdout else "light"
        else:
            r = subprocess.run(["gsettings","get","org.gnome.desktop.interface","color-scheme"],
                               capture_output=True, text=True)
            return "dark" if "dark" in r.stdout.lower() else "light"
    except Exception:
        return "dark"


# ─── Persistence ──────────────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"workspace": os.path.expanduser("~/AlceProjects"),
            "projects": [], "editor": None, "theme": "system"}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Config save error: {e}")


# ─── Utilities ────────────────────────────────────────────────────────────────
def folder_size(path):
    if not os.path.exists(path):
        return "—"
    total = 0
    try:
        for dp, _, files in os.walk(path):
            for fn in files:
                try:
                    total += os.path.getsize(os.path.join(dp, fn))
                except OSError:
                    pass
    except Exception:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024:
            return f"{total:.1f} {unit}"
        total /= 1024
    return f"{total:.1f} TB"


def find_editor_exe(candidates):
    import shutil as sh
    for c in candidates:
        p = sh.which(c)
        if p:
            return p
    return None


def open_with_editor(exe, folder):
    subprocess.Popen([exe, folder],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ─── Git logic ────────────────────────────────────────────────────────────────
def clone_project(name, workspace, log_cb, done_cb):
    dest = os.path.join(workspace, name)
    if os.path.exists(dest):
        done_cb(False, f"A folder named '{name}' already exists in the workspace.")
        return
    os.makedirs(workspace, exist_ok=True)
    try:
        log_cb(f"  Cloning from {REPO_URL}...")
        git.Repo.clone_from(REPO_URL, dest, depth=1)
        log_cb("  Detaching from original repository...")
        git_dir = os.path.join(dest, ".git")
        if os.path.exists(git_dir):
            def _force(fn, p, _):
                os.chmod(p, stat.S_IWRITE); fn(p)
            shutil.rmtree(git_dir, onerror=_force)
        log_cb("  Project ready and fully detached ✓")
        done_cb(True, dest)
    except Exception as e:
        if os.path.exists(dest):
            shutil.rmtree(dest, ignore_errors=True)
        done_cb(False, str(e))


def delete_project_folder(path, log_cb, done_cb):
    if not os.path.exists(path):
        done_cb(False, "Project folder not found on disk.")
        return
    try:
        log_cb(f"  Removing {path}...")
        shutil.rmtree(path)
        log_cb("  Folder removed ✓")
        done_cb(True, path)
    except Exception as e:
        done_cb(False, str(e))


def create_branch(branch_name, project_path, log_cb, done_cb):
    """
    Creates a new branch on the remote repo containing only:
      - ./Source/Alce/  (entire subtree, relative to selected project root)
      - ./Build/cli.py  (relative to selected project root)
    The rest of the remote tree is cleared on that branch.
    """
    if branch_name.lower() in ("main", "master"):
        done_cb(False, "Branch name 'main' or 'master' is not allowed.")
        return

    import tempfile

    # ── Validate source paths before touching the remote ─────────────────────
    src_alce = os.path.join(project_path, "Source", "Alce")
    src_cli  = os.path.join(project_path, "Build",  "cli.py")

    if not os.path.isdir(src_alce):
        done_cb(False,
                f"Source/Alce directory not found in the selected project:\n{src_alce}\n\n"
                "Make sure the project contains a Source/Alce subfolder.")
        return
    if not os.path.isfile(src_cli):
        done_cb(False,
                f"Build/cli.py not found in the selected project:\n{src_cli}\n\n"
                "Make sure the project contains Build/cli.py.")
        return

    tmp = tempfile.mkdtemp(prefix="alce_tmp_")
    try:
        # ── Clone remote to temp dir ──────────────────────────────────────────
        log_cb("  Connecting to remote repository...")
        repo = git.Repo.clone_from(REPO_URL, tmp)

        # ── Check branch doesn't already exist remotely ───────────────────────
        remote_branches = [ref.remote_head for ref in repo.remotes.origin.refs]
        if branch_name in remote_branches:
            done_cb(False, f"Branch '{branch_name}' already exists on the remote.")
            return

        # ── Create and switch to the new branch ───────────────────────────────
        log_cb(f"  Creating branch '{branch_name}'...")
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()

        # ── Clear entire working tree (keep .git) ─────────────────────────────
        log_cb("  Clearing default tree...")
        for item in os.listdir(tmp):
            if item == ".git":
                continue
            item_path = os.path.join(tmp, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

        # ── Copy Source/Alce ──────────────────────────────────────────────────
        log_cb("  Copying Source/Alce ...")
        dst_alce = os.path.join(tmp, "Source", "Alce")
        shutil.copytree(src_alce, dst_alce)

        # ── Copy Build/cli.py ─────────────────────────────────────────────────
        log_cb("  Copying Build/cli.py ...")
        dst_build = os.path.join(tmp, "Build")
        os.makedirs(dst_build, exist_ok=True)
        shutil.copy2(src_cli, os.path.join(dst_build, "cli.py"))

        # ── Stage all changes ─────────────────────────────────────────────────
        log_cb("  Staging files...")
        repo.git.add(A=True)

        # ── Commit ────────────────────────────────────────────────────────────
        log_cb("  Committing...")
        repo.index.commit(
            f"feat({branch_name}): upload Source/Alce and Build/cli.py"
        )

        # ── Push new branch to remote ─────────────────────────────────────────
        log_cb("  Pushing branch to remote...")
        repo.remotes.origin.push(refspec=f"{branch_name}:{branch_name}")

        log_cb(f"  Branch '{branch_name}' created and pushed ✓")
        done_cb(True, branch_name)

    except git.GitCommandError as e:
        done_cb(False, f"Git error: {e.stderr or str(e)}")
    except Exception as e:
        done_cb(False, str(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ─── Rounded-rect helper ─────────────────────────────────────────────────────
import math as _math

def _rrect(canvas, x1, y1, x2, y2, r, fill="", outline="black", width=1):
    """Seam-free rounded rectangle using a smooth polygon."""
    r = min(r, (x2 - x1) // 2, (y2 - y1) // 2)
    if r < 1:
        if fill:
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width)
        return
    steps = 12
    pts = []
    for cx, cy, start_deg in [
        (x2 - r, y1 + r, -90),
        (x2 - r, y2 - r,   0),
        (x1 + r, y2 - r,  90),
        (x1 + r, y1 + r, 180),
    ]:
        for i in range(steps + 1):
            a = _math.radians(start_deg + i * 90 / steps)
            pts.extend([cx + r * _math.cos(a), cy + r * _math.sin(a)])
    if fill:
        canvas.create_polygon(pts, fill=fill, outline="", smooth=True)
    if outline and width > 0:
        canvas.create_polygon(pts, fill="", outline=outline, width=width, smooth=True)


# ─── Tooltip ─────────────────────────────────────────────────────────────────
class Tooltip:
    def __init__(self, widget, text):
        self._widget = widget
        self._text   = text
        self._tip    = None
        self._after  = None
        widget.bind("<Enter>",    self._schedule, add="+")
        widget.bind("<Leave>",    self._cancel,   add="+")
        widget.bind("<Button-1>", self._cancel,   add="+")

    def _schedule(self, event):
        self._cancel(None)
        self._after = self._widget.after(500, lambda: self._show(event))

    def _show(self, event):
        if self._tip:
            return
        x = self._widget.winfo_rootx() + self._widget.winfo_width() // 2
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6
        self._tip = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self._text, justify="left",
                 bg="#1A1E2A", fg="#E8EAF6",
                 font=("Courier New", 8),
                 relief="flat", bd=0,
                 padx=8, pady=4).pack()
        tw.configure(bg="#5B8CFF")
        inner = tw.winfo_children()[0]
        inner.pack_configure(padx=1, pady=1)

    def _cancel(self, _):
        if self._after:
            self._widget.after_cancel(self._after)
            self._after = None
        if self._tip:
            self._tip.destroy()
            self._tip = None


# ─── IconBtn ──────────────────────────────────────────────────────────────────
class IconBtn(tk.Canvas):
    def __init__(self, parent, text, icon, color, command=None, width=140,
                 bg=None, tooltip=None, **kw):
        self._panel_bg = bg or "#13161E"
        super().__init__(parent, width=width, height=38,
                         bg=self._panel_bg, highlightthickness=0, cursor="hand2", **kw)
        self._color   = color
        self._text    = text
        self._icon    = icon
        self._cmd     = command
        self._hovered = False
        self._draw()
        self.bind("<Enter>",           lambda _: self._hover(True))
        self.bind("<Leave>",           lambda _: self._hover(False))
        self.bind("<Button-1>",        lambda _: self._draw(pressed=True))
        self.bind("<ButtonRelease-1>", self._release)
        if tooltip:
            Tooltip(self, tooltip)

    def update_bg(self, bg):
        self._panel_bg = bg
        self.configure(bg=bg)
        self._draw()

    def _hover(self, v):
        self._hovered = v; self._draw()

    @staticmethod
    def _scale(hex_color, factor):
        rgb = bytes.fromhex(hex_color.lstrip("#"))
        return "#" + "".join(f"{min(255, max(0, int(c * factor))):02x}" for c in rgb)

    def _draw(self, pressed=False):
        self.delete("all")
        W, H = int(self["width"]), int(self["height"])
        self.create_rectangle(0, 0, W, H, fill=self._panel_bg, outline="")
        pad = 2 if pressed else 0
        x1 = pad + 2; y1 = pad + 2; x2 = W - pad - 2; y2 = H - pad - 2
        r  = (y2 - y1) // 2
        if pressed:
            fill   = self._scale(self._color, 0.68)
            border = self._scale(self._color, 0.50)
        elif self._hovered:
            fill   = self._scale(self._color, 1.22)
            border = self._scale(self._color, 1.35)
        else:
            fill   = self._color
            border = self._scale(self._color, 0.72)
        _rrect(self, x1, y1, x2, y2, r, fill=fill, outline=border, width=1)
        cx = (x1 + x2) // 2; cy = (y1 + y2) // 2
        self.create_text(cx, cy, text=self._text,
                         fill="#FFFFFF", font=FONT_HEAD, anchor="center")

    def _release(self, _):
        self._draw()
        if self._cmd: self._cmd()


# ─── ThemeToggle ──────────────────────────────────────────────────────────────
class ThemeToggle(tk.Canvas):
    W_BTN = 110
    H_BTN = 38

    def __init__(self, parent, theme, on_toggle, bg, **kw):
        super().__init__(parent, width=self.W_BTN, height=self.H_BTN,
                         bg=bg, highlightthickness=0, cursor="hand2", **kw)
        self._theme     = theme
        self._bg        = bg
        self._on_toggle = on_toggle
        self._hov       = False
        self._pressed   = False
        self._draw()
        self.bind("<Button-1>",        self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>",           lambda _: self._h(True))
        self.bind("<Leave>",           lambda _: self._h(False))
        Tooltip(self, "Toggle dark / light theme")

    def update(self, theme, bg):
        self._theme = theme; self._bg = bg
        self.configure(bg=bg); self._draw()

    def _h(self, v): self._hov = v; self._draw()

    def _on_press(self, _):
        self._pressed = True; self._draw()

    def _on_release(self, _):
        self._pressed = False
        self._on_toggle()

    @staticmethod
    def _scale(hex_color, factor):
        rgb = bytes.fromhex(hex_color.lstrip("#"))
        return "#" + "".join(f"{min(255, max(0, int(c * factor))):02x}" for c in rgb)

    def _draw(self):
        self.delete("all")
        W, H = self.W_BTN, self.H_BTN
        col  = "#88AAFF" if self._hov else ACCENT
        self.create_rectangle(0, 0, W, H, fill=self._bg, outline="")
        pad = 2 if self._pressed else 0
        x1 = pad + 2; y1 = pad + 2; x2 = W - pad - 2; y2 = H - pad - 2
        r  = (y2 - y1) // 2
        if self._pressed:
            fill   = self._scale(col, 0.68)
            border = self._scale(col, 0.50)
        elif self._hov:
            fill   = self._scale(col, 1.22)
            border = self._scale(col, 1.35)
        else:
            fill   = col
            border = self._scale(col, 0.72)
        _rrect(self, x1, y1, x2, y2, r, fill=fill, outline=border, width=1)
        icon  = "☀" if self._theme == "light" else "☾"
        label = f"{icon}  {'LIGHT' if self._theme == 'light' else 'DARK'}"
        cx = (x1 + x2) // 2; cy = (y1 + y2) // 2
        self.create_text(cx, cy, text=label,
                         fill="#FFFFFF", font=FONT_HEAD, anchor="center")


# ─── EmptyState ───────────────────────────────────────────────────────────────
class EmptyState(tk.Canvas):
    """
    Canvas-drawn empty state. Shows an animated dot-grid background,
    a centred card with icon and message, and a clickable NEW pill.

    Hover/click are handled via canvas-level Motion and Button-1 bindings
    (no tag_bind) to avoid crashes when items are deleted on redraw.
    """

    def __init__(self, parent, palette, on_new, **kw):
        self._pal          = palette
        self._on_new       = on_new
        self._anim_offset  = 0
        self._anim_id      = None
        self._pill_hovered = False
        self._pill_coords  = None   # (bx1, by1, bx2, by2) updated each draw
        super().__init__(parent, bg=palette["BG_DARK"],
                         highlightthickness=0, bd=0, **kw)
        self.bind("<Configure>", lambda _: self.after_idle(self._draw))
        self.bind("<Motion>",    self._on_motion)
        self.bind("<Leave>",     self._on_leave)
        self.bind("<Button-1>",  self._on_click)

    def update_palette(self, palette):
        self._pal = palette
        self.configure(bg=palette["BG_DARK"])
        self._draw()

    # ── Coordinate helpers ────────────────────────────────────────────────────
    def _in_pill(self, x, y):
        if not self._pill_coords:
            return False
        bx1, by1, bx2, by2 = self._pill_coords
        return bx1 <= x <= bx2 and by1 <= y <= by2

    # ── Canvas events ─────────────────────────────────────────────────────────
    def _on_motion(self, event):
        over = self._in_pill(event.x, event.y)
        if over != self._pill_hovered:
            self._pill_hovered = over
            self.configure(cursor="hand2" if over else "arrow")
            self._draw()

    def _on_leave(self, event):
        if self._pill_hovered:
            self._pill_hovered = False
            self.configure(cursor="arrow")
            self._draw()

    def _on_click(self, event):
        if self._in_pill(event.x, event.y):
            self._on_new()

    # ── Drawing ───────────────────────────────────────────────────────────────
    def _draw(self):
        self.delete("all")
        W = self.winfo_width()
        H = self.winfo_height()
        if W < 10 or H < 10:
            return
        pal = self._pal

        # ── Animated dot grid ─────────────────────────────────────────────────
        dot_gap = 26
        off     = self._anim_offset % dot_gap
        for gx in range(-dot_gap, W + dot_gap, dot_gap):
            for gy in range(-dot_gap, H + dot_gap, dot_gap):
                x, y = gx + off, gy + off
                self.create_oval(x - 1, y - 1, x + 1, y + 1,
                                 fill=pal["TEXT_DIM"], outline="")

        # ── Card geometry ─────────────────────────────────────────────────────
        cw = min(W - 60, 340)
        ch = 210
        cx = W // 2
        cy = H // 2
        x1, y1 = cx - cw // 2, cy - ch // 2
        x2, y2 = cx + cw // 2, cy + ch // 2

        # Drop shadow
        self.create_rectangle(x1 + 6, y1 + 6, x2 + 6, y2 + 6,
                               fill="#000000", outline="", stipple="gray25")
        # Card body
        _rrect(self, x1, y1, x2, y2, 12,
               fill=pal["BG_CARD"], outline=pal["BORDER"], width=1)
        # Accent top bar
        _rrect(self, x1 + 1, y1 + 1, x2 - 1, y1 + 5, 6,
               fill=ACCENT, outline="")

        # ── Hex glyph ─────────────────────────────────────────────────────────
        self.create_text(cx, cy - 48, text="⬡",
                         fill=pal["TEXT_DIM"], font=("Courier New", 44))
        self.create_text(cx, cy - 48, text="⊕",
                         fill=ACCENT, font=("Courier New", 20, "bold"))

        # ── Heading ───────────────────────────────────────────────────────────
        self.create_text(cx, cy + 6,
                         text="NO PROJECTS YET",
                         fill=pal["TEXT_PRI"],
                         font=("Courier New", 12, "bold"),
                         anchor="center")

        # ── Hint ──────────────────────────────────────────────────────────────
        self.create_text(cx, cy + 26,
                         text="Clone the AlceEngine repo to get started",
                         fill=pal["TEXT_SEC"],
                         font=("Courier New", 8),
                         anchor="center")

        # ── NEW pill ──────────────────────────────────────────────────────────
        bw, bh = 126, 28
        bx1 = cx - bw // 2
        by1 = cy + 50
        bx2 = cx + bw // 2
        by2 = by1 + bh
        self._pill_coords = (bx1, by1, bx2, by2)   # stored for hit-testing
        pill_col = "#7AAAFF" if self._pill_hovered else ACCENT
        _rrect(self, bx1, by1, bx2, by2, bh // 2,
               fill=pill_col, outline="")
        self.create_text(cx, (by1 + by2) // 2,
                         text="⊕  NEW PROJECT",
                         fill="#FFFFFF",
                         font=("Courier New", 8, "bold"))

    # ── Animation ─────────────────────────────────────────────────────────────
    def start_anim(self):
        self._tick()

    def stop_anim(self):
        if self._anim_id:
            self.after_cancel(self._anim_id)
            self._anim_id = None

    def _tick(self):
        self._anim_offset += 1
        self._draw()
        self._anim_id = self.after(55, self._tick)


# ─── ProjectCard ──────────────────────────────────────────────────────────────
class ProjectCard(tk.Canvas):
    """
    Fully Canvas-drawn project card. No nested Frame widgets.
    Features:
      - Rounded card body with accent left bar
      - Status dot (green = on disk, red = missing)
      - Size badge (teal outline pill)
      - Hover highlight
      - Selection state (bright accent bar)
      - Circular delete button on the right
    """

    CARD_H   = 76
    RADIUS   = 8
    BAR_W    = 4
    ICON_R   = 13   # radius of the project icon circle (was 7 — now larger)

    def __init__(self, parent, project, on_select, on_delete, on_open,
                 palette, icon_img=None, **kw):
        self._pal      = palette
        self._project  = project
        self._on_select = on_select
        self._on_delete = on_delete
        self._on_open   = on_open
        self._selected    = False
        self._hovered     = False
        self._del_hovered = False
        self._icon_img    = icon_img
        self._del_coords  = None

        super().__init__(parent,
                         height=self.CARD_H,
                         bg=palette["BG_DARK"],
                         highlightthickness=0, bd=0,
                         cursor="hand2", **kw)

        self.bind("<Configure>",       lambda _: self._draw())
        self.bind("<Enter>",           lambda _: self._set_hover(True))
        self.bind("<Leave>",           self._on_leave)
        self.bind("<Motion>",          self._on_motion)
        self.bind("<Button-1>",        self._on_click)
        self.bind("<Double-Button-1>", self._on_dclick)

    # ── Public ────────────────────────────────────────────────────────────────
    def set_selected(self, val):
        self._selected = val
        self._draw()

    def update_palette(self, palette):
        self._pal = palette
        self.configure(bg=palette["BG_DARK"])
        self._draw()

    # ── Drawing ───────────────────────────────────────────────────────────────
    def _draw(self):
        self.delete("all")
        W  = self.winfo_width()
        H  = self.CARD_H
        if W < 10:
            return

        pal    = self._pal
        name   = self._project.get("nombre", "—")
        path   = self._project.get("ruta",   "—")
        exists = os.path.exists(path)
        size   = folder_size(path)

        # Reserve space for delete button on the right
        r_del    = 13
        del_margin = r_del * 2 + 16   # total right margin used by delete btn

        # ── Card background ───────────────────────────────────────────────────
        bg = pal["BG_HOVER"] if (self._selected or self._hovered) else pal["BG_CARD"]
        _rrect(self, 1, 1, W - 1, H - 1, self.RADIUS,
               fill=bg, outline=pal["BORDER"], width=1)

        # ── Left accent bar ───────────────────────────────────────────────────
        bar_col = ACCENT if self._selected else pal["TEXT_DIM"]
        _rrect(self, 1, 6, self.BAR_W + 3, H - 6, 3,
               fill=bar_col, outline="")

        # ── Status indicator circle (now bigger, matches icon size) ──────────
        r_icon = self.ICON_R
        dot_x, dot_y = 10 + r_icon, H // 2
        dot_col = SUCCESS if exists else DANGER
        self.create_oval(dot_x - r_icon, dot_y - r_icon, dot_x + r_icon, dot_y + r_icon,
                         fill=dot_col, outline="")
        inner_r = max(2, r_icon - 4)
        self.create_oval(dot_x - inner_r, dot_y - inner_r, dot_x + inner_r, dot_y + inner_r,
                         fill="#FFFFFF", outline="")

        # ── Icon image (if any) — drawn on top of the status dot, larger ─────
        if self._icon_img:
            try:
                self.create_image(dot_x, dot_y, image=self._icon_img, anchor="center")
            except Exception:
                pass

        # ── Name (top-left text area) ─────────────────────────────────────────
        text_x = 16 + r_icon * 2 + 6
        self.create_text(text_x, 18,
                         text=name,
                         fill=pal["TEXT_PRI"],
                         font=FONT_HEAD,
                         anchor="w")

        # ── Size badge — anchored to top-right (before delete button) ─────────
        badge_w  = len(size) * 6 + 16
        badge_x2 = W - del_margin - 4
        badge_x1 = badge_x2 - badge_w
        by1, by2 = 9, 27
        _rrect(self, badge_x1, by1, badge_x2, by2, 7,
               fill=pal["BG_DARK"], outline=ACCENT2, width=1)
        self.create_text((badge_x1 + badge_x2) // 2, (by1 + by2) // 2,
                         text=size, fill=ACCENT2,
                         font=("Courier New", 7, "bold"))

        # ── Path (truncated) ─────────────────────────────────────────────────
        max_chars = max(10, (W - del_margin - text_x - 10) // 6)
        path_disp = path if len(path) <= max_chars else "…" + path[-max_chars:]
        self.create_text(text_x, 38,
                         text=path_disp,
                         fill=pal["TEXT_DIM"],
                         font=FONT_SMALL,
                         anchor="w")

        # ── Status label ──────────────────────────────────────────────────────
        status_txt = "on disk" if exists else "folder missing"
        status_col = ACCENT2 if exists else DANGER
        self.create_text(text_x, 56,
                         text=f"● {status_txt}",
                         fill=status_col,
                         font=("Courier New", 8),
                         anchor="w")

        # ── Delete button (drawn last so coords are stable) ───────────────────
        dx = W - del_margin // 2 - 2
        dy = H // 2
        del_color = DANGER if self._del_hovered else pal["TEXT_DIM"]
        del_bg    = "#3A0F1A" if self._del_hovered else pal["BG_DARK"]
        del_bdr   = DANGER   if self._del_hovered else pal["BORDER"]
        self._del_coords = (dx - r_del, dy - r_del, dx + r_del, dy + r_del)
        self.create_oval(dx - r_del, dy - r_del, dx + r_del, dy + r_del,
                         fill=del_bg, outline=del_bdr)
        self.create_text(dx, dy,
                         text="✕", fill=del_color,
                         font=("Courier New", 9, "bold"))

    # ── Events ────────────────────────────────────────────────────────────────
    def _set_hover(self, val):
        self._hovered = val
        self._draw()

    def _in_del_zone(self, x, y):
        if not self._del_coords:
            return False
        x1, y1, x2, y2 = self._del_coords
        return x1 <= x <= x2 and y1 <= y <= y2

    def _on_motion(self, event):
        in_del = self._in_del_zone(event.x, event.y)
        if in_del != self._del_hovered:
            self._del_hovered = in_del
            self.configure(cursor="hand2")
            self._draw()

    def _on_leave(self, event):
        changed = self._hovered or self._del_hovered
        self._hovered     = False
        self._del_hovered = False
        if changed:
            self._draw()

    def _on_click(self, event):
        if self._in_del_zone(event.x, event.y):
            self._on_delete(self._project)
        else:
            self._on_select(self._project)

    def _on_dclick(self, event):
        if not self._in_del_zone(event.x, event.y):
            self._on_open(self._project)


# ─── Editor picker ────────────────────────────────────────────────────────────
class EditorPickerDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._pal = parent.palette
        self.title("Choose Editor")
        self.configure(bg=self._pal["BG_DARK"])
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._build()
        self.update_idletasks()
        px = parent.winfo_x() + parent.winfo_width()  // 2
        py = parent.winfo_y() + parent.winfo_height() // 2
        w, h = 480, 460
        self.geometry(f"{w}x{h}+{px-w//2}+{py-h//2}")

    def _build(self):
        pal = self._pal
        bg = pal["BG_DARK"]; card = pal["BG_CARD"]
        tk.Label(self, text="SELECT YOUR CODE EDITOR",
                 fg=ACCENT, bg=bg, font=FONT_HEAD).pack(pady=(20, 4))
        tk.Label(self, text="Your choice will be saved for future sessions.",
                 fg=pal["TEXT_SEC"], bg=bg, font=FONT_SMALL).pack(pady=(0, 14))

        frame = tk.Frame(self, bg=bg)
        frame.pack(fill="both", expand=True, padx=20)
        self._var = tk.StringVar(value="")

        for display, candidates in KNOWN_EDITORS:
            exe = find_editor_exe(candidates) if candidates else None
            tag = exe if exe else display
            row = tk.Frame(frame, bg=card, cursor="hand2")
            row.pack(fill="x", pady=3)
            rb = tk.Radiobutton(row, variable=self._var, value=tag,
                                bg=card, activebackground=pal["BG_HOVER"],
                                selectcolor=card, fg=pal["TEXT_PRI"],
                                font=FONT_BODY, bd=0, highlightthickness=0, text="")
            rb.pack(side="left", padx=(10, 0), pady=8)
            tk.Label(row, text="●", fg=SUCCESS if exe else pal["TEXT_DIM"],
                     bg=card, font=("Courier New", 8)).pack(side="left", padx=(0, 6))
            tk.Label(row, text=display,
                     fg=pal["TEXT_PRI"] if exe else pal["TEXT_DIM"],
                     bg=card, font=FONT_BODY).pack(side="left")
            if exe:
                tk.Label(row, text=f"  {exe}", fg=pal["TEXT_DIM"],
                         bg=card, font=FONT_SMALL).pack(side="left")
            row.bind("<Button-1>", lambda e, v=tag: self._var.set(v))

        def confirm():
            val = self._var.get()
            if not val:
                messagebox.showwarning("No selection", "Please select an editor.", parent=self)
                return
            if val == "Other (browse...)":
                p = filedialog.askopenfilename(title="Select executable", parent=self,
                    filetypes=[("Executable","*.exe"),("All files","*.*")])
                if not p: return
                val = p
            self.result = val
            self.destroy()

        bf = tk.Frame(self, bg=bg); bf.pack(pady=16)
        ok = tk.Canvas(bf, width=160, height=40, bg=bg, highlightthickness=0)
        ok.pack()
        self._draw_ok(ok, False)
        ok.bind("<Button-1>", lambda _: confirm())
        ok.bind("<Enter>",    lambda _: self._draw_ok(ok, True))
        ok.bind("<Leave>",    lambda _: self._draw_ok(ok, False))

    def _draw_ok(self, c, hover):
        c.delete("all")
        W, H = 160, 40
        r    = H // 2 - 2
        rgb  = bytes.fromhex(ACCENT.lstrip("#"))
        if hover:
            fill   = "#" + "".join(f"{min(255,int(v*1.22)):02x}" for v in rgb)
            border = "#" + "".join(f"{min(255,int(v*1.35)):02x}" for v in rgb)
        else:
            fill   = ACCENT
            border = "#" + "".join(f"{max(0,int(v*0.72)):02x}" for v in rgb)
        _rrect(c, 2, 2, W-2, H-2, r, fill=fill, outline=border, width=1)
        c.create_text(W//2, H//2, text="✔  CONFIRM",
                      fill="#FFFFFF", font=FONT_HEAD)


# ─── Help dialog ─────────────────────────────────────────────────────────────
class HelpDialog(tk.Toplevel):
    SECTIONS = [
        ("OVERVIEW", "Alce Project Manager lets you create, open and manage local copies of the AlceEngine-Project repository. Every copy is fully detached from the original — no Git history, no remote connection — so you can start a brand-new project from it without any ties to the source repo."),
        ("NEW  —  Clone a project", "Creates a new local copy of the AlceEngine-Project repository.\n\n1. Click NEW and enter a name for your project.\n2. The repo is cloned into your workspace folder.\n3. The .git folder is deleted automatically, so the copy has NO connection to the original repository.\n4. You can open it in any editor, run git init, and start fresh.\n\nThe copy is independent: changes you make here never affect the original repo."),
        ("OPEN  —  Open in editor", "Opens the selected project folder in your preferred code editor.\n\n• Single-click a project to select it, then press OPEN.\n• Double-click a project to select and open it immediately.\n• If no editor is configured, the app will auto-detect one and ask you to confirm, or let you browse for an executable.\n• Your choice is saved and reused automatically next time."),
        ("DELETE  —  Remove a project", "Permanently deletes the selected project folder from disk and removes it from the list.\n\n⚠  This cannot be undone. The folder and all its contents are deleted.\n\nIf the folder cannot be removed (e.g. a file is open), the app will ask whether to remove just the list entry without touching the folder."),
        ("UPDATE  —  Push changes to remote branch", "Creates a new branch on the remote repository containing only the relevant files from the selected project.\n\nFiles pushed:\n  • Source/Alce/  (entire subtree)\n  • Build/cli.py\n\nAll other files in the remote tree are excluded from that branch.\n\n• Select a project first, then click UPDATE.\n• Enter the desired branch name.\n• main and master are permanently protected.\n• If either required path is missing in your project, the operation is aborted before touching the remote."),
        ("WORKSPACE", "The workspace is the folder where all new project copies are created.\n\nClick the path shown under WORKSPACE in the sidebar to open a folder picker and change it. The setting is saved between sessions."),
        ("EDITOR", "The preferred editor used by the OPEN action and double-click.\n\nClick the editor name under EDITOR in the sidebar to open the editor picker. The picker shows all supported editors and highlights which ones are installed on your system.\n\nSupported: VS Code, Visual Studio, Cursor, Sublime Text, Notepad++, PyCharm, Neovim, Vim, Atom, or any custom executable."),
        ("PROJECT ICONS", "Each project card can display a custom icon.\n\nIf the project folder contains exactly one file named icon.ico (anywhere in its subfolder tree), that icon is shown on the card. If there are zero or more than one, the default Alce icon is used instead."),
        ("DARK / LIGHT THEME", "Click the DARK / LIGHT toggle in the top-right corner of the window to switch between themes. The preference is saved between sessions.\n\nThe app also detects your OS theme on first launch (Windows, macOS, Linux)."),
    ]

    def __init__(self, parent):
        super().__init__(parent)
        self._pal = parent.palette
        pal = self._pal
        self.title("Help — Alce Project Manager")
        self.configure(bg=pal["BG_DARK"])
        self.resizable(True, True)
        self.grab_set()
        self.update_idletasks()
        pw = parent.winfo_width(); ph = parent.winfo_height()
        px = parent.winfo_x();    py = parent.winfo_y()
        w, h = min(700, pw - 40), min(580, ph - 40)
        x = px + (pw - w) // 2;  y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(500, 400)
        self._build(pal)

    def _build(self, pal):
        title_f = tk.Frame(self, bg=pal["BG_PANEL"])
        title_f.pack(fill="x")
        tk.Label(title_f, text="?  HELP", fg=ACCENT,
                 bg=pal["BG_PANEL"], font=FONT_HEAD).pack(side="left", padx=16, pady=10)
        tk.Label(title_f, text="Alce Project Manager — User Guide",
                 fg=pal["TEXT_SEC"], bg=pal["BG_PANEL"],
                 font=FONT_SMALL).pack(side="left")
        close_btn = tk.Label(title_f, text="  ✕  ", fg=pal["TEXT_DIM"],
                             bg=pal["BG_PANEL"], font=("Courier New", 12, "bold"),
                             cursor="hand2")
        close_btn.pack(side="right", padx=10)
        close_btn.bind("<Button-1>", lambda _: self.destroy())
        close_btn.bind("<Enter>",    lambda _: close_btn.config(fg=DANGER))
        close_btn.bind("<Leave>",    lambda _: close_btn.config(fg=pal["TEXT_DIM"]))
        tk.Frame(self, bg=pal["BORDER"], height=1).pack(fill="x")

        outer  = tk.Frame(self, bg=pal["BG_DARK"])
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=pal["BG_DARK"], highlightthickness=0, bd=0)
        sb     = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                              bg=pal["BG_PANEL"], troughcolor=pal["BG_DARK"], width=6)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        inner  = tk.Frame(canvas, bg=pal["BG_DARK"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        for i, (heading, body) in enumerate(self.SECTIONS):
            sec = tk.Frame(inner, bg=pal["BG_CARD"])
            sec.pack(fill="x", padx=16, pady=(12 if i == 0 else 6, 0))
            hdr_f = tk.Frame(sec, bg=pal["BG_CARD"])
            hdr_f.pack(fill="x")
            tk.Frame(hdr_f, bg=ACCENT, width=3).pack(side="left", fill="y")
            tk.Label(hdr_f, text=f"  {heading}", fg=ACCENT,
                     bg=pal["BG_CARD"], font=FONT_HEAD,
                     anchor="w").pack(side="left", pady=8)
            tk.Frame(sec, bg=pal["BORDER"], height=1).pack(fill="x", padx=8)
            tk.Label(sec, text=body, fg=pal["TEXT_SEC"],
                     bg=pal["BG_CARD"], font=FONT_SMALL,
                     justify="left", wraplength=620,
                     anchor="w").pack(fill="x", padx=12, pady=(6, 10))
        tk.Frame(inner, bg=pal["BG_DARK"], height=16).pack()


# ─── Main window ──────────────────────────────────────────────────────────────
class AlceManager(tk.Tk):

    # Diameter (in px) used to display the default "logo" icon next to each
    # project card. Increase this to make the card icon bigger.
    CARD_ICON_SIZE = 26

    def __init__(self):
        super().__init__()
        self.title("Alce Project Manager")
        self.geometry("980x700")
        self.minsize(820, 580)

        self._card_icon   = self._load_icon_img()
        self._logo_img    = self._load_logo_img()
        self._set_window_icon()
        self._config      = load_config()
        self._projects    = self._config.get("projects", [])
        self._selected    = None
        self._cards       = []
        self._btns        = []
        self._proj_images = []
        self._empty_state = None

        saved = self._config.get("theme", "system")
        self._theme_pref   = saved
        self._active_theme = detect_system_theme() if saved == "system" else saved
        self.palette       = THEMES[self._active_theme]

        self.configure(bg=self.palette["BG_DARK"])
        self._build_ui()
        self._refresh_list()

    # ── Image helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def _find_project_ico(project_path):
        if not os.path.isdir(project_path):
            return None
        found = []
        try:
            for dirpath, _, files in os.walk(project_path):
                for fname in files:
                    if fname.lower() == "icon.ico":
                        found.append(os.path.join(dirpath, fname))
                        if len(found) > 1:
                            return None
        except Exception:
            return None
        return found[0] if len(found) == 1 else None

    def _ico_to_photoimage(self, ico_path, target_px=None):
        """Loads the largest embedded PNG frame from an .ico file and returns
        a tk.PhotoImage roughly `target_px` pixels wide (defaults to
        CARD_ICON_SIZE)."""
        target_px = target_px or self.CARD_ICON_SIZE
        try:
            with open(ico_path, "rb") as f:
                data = f.read()
            num = struct.unpack_from("<H", data, 4)[0]
            best_data, best_size = None, 0
            for i in range(num):
                off      = 6 + i * 16
                img_size = struct.unpack_from("<I", data, off + 8)[0]
                img_off  = struct.unpack_from("<I", data, off + 12)[0]
                img_data = data[img_off:img_off + img_size]
                if img_data[:8] == b"\x89PNG\r\n\x1a\n" and img_size > best_size:
                    best_size = img_size; best_data = img_data
            if best_data:
                img    = tk.PhotoImage(data=base64.b64encode(best_data).decode())
                factor = max(1, img.width() // target_px)
                return img.subsample(factor, factor) if factor > 1 else img
        except Exception:
            pass
        return None

    def _load_icon_img(self):
        """Loads the default per-card icon shown on project cards.
        Looks for icon.ico next to the script; falls back to None
        (the card will simply show its status dot)."""
        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        return self._ico_to_photoimage(ico_path, target_px=self.CARD_ICON_SIZE)

    def _load_logo_img(self, subsample=None):
        """Loads the footer logo directly from logo.png on disk.

        Looks first next to the script, then in the PyInstaller bundle
        (resource_path), falling back to None if not found so the UI keeps
        working even without the file."""
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png"),
            resource_path("logo.png"),
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    img = tk.PhotoImage(file=path)
                    if subsample and subsample > 1:
                        img = img.subsample(subsample, subsample)
                    else:
                        # Auto-scale down to a sensible footer size if the
                        # source PNG is larger than ~32px wide.
                        factor = max(1, img.width() // 32)
                        if factor > 1:
                            img = img.subsample(factor, factor)
                    return img
                except Exception:
                    continue
        return None

    def _set_window_icon(self):
        """Sets the application icon shown in the window title bar AND the
        Windows taskbar.

        On Windows, only `iconbitmap()` with a real .ico file reliably
        controls both the title bar and the taskbar icon, so we look for
        logo.ico first (next to the script, then in the PyInstaller bundle).
        If no .ico is available, we fall back to logo.png via
        `iconphoto()`, which at least sets the title bar icon on
        Windows/Linux/macOS (taskbar grouping on Windows may still show the
        default Python icon in that fallback case)."""
        ico_candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico"),
            resource_path("logo.ico"),
        ]
        for path in ico_candidates:
            if os.path.exists(path):
                try:
                    self.iconbitmap(path)
                    return
                except Exception:
                    continue

        # No logo.ico found — fall back to logo.png for at least the
        # title-bar icon (and Linux/macOS taskbar/dock icon).
        png_candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png"),
            resource_path("logo.png"),
        ]
        for path in png_candidates:
            if os.path.exists(path):
                try:
                    icon_img = tk.PhotoImage(file=path)
                    self.iconphoto(True, icon_img)
                    self._window_icon_img = icon_img  # keep a reference
                    return
                except Exception:
                    continue

    # ── Theme ─────────────────────────────────────────────────────────────────
    def _cycle_theme(self):
        self._active_theme = "light" if self._active_theme == "dark" else "dark"
        self._theme_pref   = self._active_theme
        self._config["theme"] = self._active_theme
        save_config(self._config)
        self.palette = THEMES[self._active_theme]
        self._apply_theme()

    def _apply_theme(self):
        pal = self.palette
        self.configure(bg=pal["BG_DARK"])
        self._mass_recolor(self, pal["BG_DARK"])
        self._theme_toggle.update(self._active_theme, pal["BG_DARK"])
        self._title_lbl.configure(fg=pal["TEXT_PRI"], bg=pal["BG_DARK"])
        self._help_btn.configure(bg=pal["BG_DARK"])
        self._draw_help_btn(self._help_btn, False, pal)
        for b in self._btns:
            b.update_bg(pal["BG_PANEL"])
        self._log_text.configure(bg=pal["LOG_BG"], fg=pal["LOG_FG"])
        self._footer.configure(bg=pal["BG_PANEL"])
        for w in self._footer.winfo_children():
            try: w.configure(bg=pal["BG_PANEL"])
            except Exception: pass
        self._refresh_list()

    def _mass_recolor(self, w, bg):
        skip = ("IconBtn", "ThemeToggle", "ProjectCard", "EmptyState")
        if w.__class__.__name__ in skip:
            return
        try: w.config(bg=bg)
        except Exception: pass
        for c in w.winfo_children():
            self._mass_recolor(c, bg)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        pal = self.palette

        hdr = tk.Frame(self, bg=pal["BG_DARK"])
        hdr.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(hdr, text="ALCE", fg=ACCENT, bg=pal["BG_DARK"], font=FONT_TITLE).pack(side="left")
        self._title_lbl = tk.Label(hdr, text=" PROJECT MANAGER", fg=pal["TEXT_PRI"],
                                   bg=pal["BG_DARK"], font=FONT_TITLE)
        self._title_lbl.pack(side="left")
        tk.Label(hdr, text=f"  ·  {REPO_URL}", fg=pal["TEXT_SEC"],
                 bg=pal["BG_DARK"], font=FONT_SMALL).pack(side="left", pady=(6, 0))
        self._theme_toggle = ThemeToggle(hdr, self._active_theme, self._cycle_theme, pal["BG_DARK"])
        self._theme_toggle.pack(side="right", pady=(6, 0))

        help_btn = tk.Canvas(hdr, width=28, height=28, bg=pal["BG_DARK"],
                             highlightthickness=0, cursor="hand2")
        help_btn.pack(side="right", pady=(6, 0), padx=(0, 10))
        self._draw_help_btn(help_btn, False, pal)
        help_btn.bind("<Button-1>", lambda _: self._show_help())
        help_btn.bind("<Enter>",    lambda _: self._draw_help_btn(help_btn, True, self.palette))
        help_btn.bind("<Leave>",    lambda _: self._draw_help_btn(help_btn, False, self.palette))
        self._help_btn = help_btn
        Tooltip(help_btn, "Open the user guide")

        tk.Frame(self, bg=pal["BORDER"], height=1).pack(fill="x", padx=24, pady=(14, 0))

        center = tk.Frame(self, bg=pal["BG_DARK"])
        center.pack(fill="both", expand=True, padx=24, pady=16)
        center.columnconfigure(1, weight=1)
        center.rowconfigure(0, weight=1)

        self._build_sidebar(center)
        self._build_main_panel(center)
        self._build_footer()

    def _build_sidebar(self, parent):
        pal     = self.palette
        sidebar = tk.Frame(parent, bg=pal["BG_PANEL"], width=200)
        sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        sidebar.pack_propagate(False)
        self._sidebar = sidebar

        ws_f = tk.Frame(sidebar, bg=pal["BG_PANEL"])
        ws_f.pack(fill="x", padx=12, pady=(16, 0))
        tk.Label(ws_f, text="WORKSPACE", fg=pal["TEXT_DIM"],
                 bg=pal["BG_PANEL"], font=FONT_SMALL).pack(anchor="w")
        self._ws_var = tk.StringVar(value=self._config.get("workspace", ""))
        self._ws_lbl = tk.Label(ws_f, textvariable=self._ws_var, fg=pal["TEXT_SEC"],
                                bg=pal["BG_PANEL"], font=FONT_MONO, wraplength=170,
                                justify="left", cursor="hand2")
        self._ws_lbl.pack(anchor="w", pady=(2, 0))
        self._ws_lbl.bind("<Button-1>", lambda _: self._change_workspace())
        self._ws_lbl.bind("<Enter>",    lambda _: self._ws_lbl.config(fg=ACCENT))
        self._ws_lbl.bind("<Leave>",    lambda _: self._ws_lbl.config(fg=pal["TEXT_SEC"]))
        tk.Label(ws_f, text="(click to change)", fg=pal["TEXT_DIM"], bg=pal["BG_PANEL"],
                 font=("Courier New", 7)).pack(anchor="w")

        tk.Frame(sidebar, bg=pal["BORDER"], height=1).pack(fill="x", padx=12, pady=10)

        ed_f = tk.Frame(sidebar, bg=pal["BG_PANEL"])
        ed_f.pack(fill="x", padx=12, pady=(0, 4))
        tk.Label(ed_f, text="EDITOR", fg=pal["TEXT_DIM"],
                 bg=pal["BG_PANEL"], font=FONT_SMALL).pack(anchor="w")
        self._editor_var = tk.StringVar(value=self._editor_label())
        self._ed_lbl = tk.Label(ed_f, textvariable=self._editor_var, fg=ACCENT2,
                                bg=pal["BG_PANEL"], font=FONT_MONO, cursor="hand2")
        self._ed_lbl.pack(anchor="w", pady=(2, 0))
        self._ed_lbl.bind("<Button-1>", lambda _: self._change_editor())
        self._ed_lbl.bind("<Enter>",    lambda _: self._ed_lbl.config(fg=ACCENT))
        self._ed_lbl.bind("<Leave>",    lambda _: self._ed_lbl.config(fg=ACCENT2))
        tk.Label(ed_f, text="(click to change)", fg=pal["TEXT_DIM"], bg=pal["BG_PANEL"],
                 font=("Courier New", 7)).pack(anchor="w")

        tk.Frame(sidebar, bg=pal["BORDER"], height=1).pack(fill="x", padx=12, pady=10)

        btns = tk.Frame(sidebar, bg=pal["BG_PANEL"])
        btns.pack(fill="x", padx=12)
        self._btns.clear()
        for text, icon, color, cmd, tip in [
            ("NEW",    "⊕", ACCENT,  self._action_new,    "Clone the repo as a new detached project"),
            ("OPEN",   "▶", ACCENT3, self._action_open,   "Open selected project in your code editor"),
            ("DELETE", "⊘", DANGER,  self._action_delete, "Permanently delete the selected project from disk"),
            ("UPDATE", "⟳", ACCENT2, self._action_update, "Push Source/Alce and Build/cli.py from selected project to a new remote branch"),
        ]:
            b = IconBtn(btns, text, icon, color, cmd,
                        width=174, bg=pal["BG_PANEL"], tooltip=tip)
            b.pack(pady=(0, 7))
            self._btns.append(b)

        tk.Frame(sidebar, bg=pal["BORDER"], height=1).pack(fill="x", padx=12, pady=10)
        for line in ["NEW    →  clone repo",
                     "OPEN   →  open in editor",
                     "DELETE →  remove local copy",
                     "UPDATE →  push to remote branch"]:
            tk.Label(sidebar, text=line, fg=pal["TEXT_DIM"], bg=pal["BG_PANEL"],
                     font=("Courier New", 7)).pack(anchor="w", padx=14)

    def _build_main_panel(self, parent):
        pal   = self.palette
        panel = tk.Frame(parent, bg=pal["BG_DARK"])
        panel.grid(row=0, column=1, sticky="nsew")
        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)
        self._panel = panel

        lf = tk.Frame(panel, bg=pal["BG_DARK"])
        lf.grid(row=0, column=0, sticky="nsew")
        lf.rowconfigure(1, weight=1)
        lf.columnconfigure(0, weight=1)

        hdr = tk.Frame(lf, bg=pal["BG_DARK"])
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(hdr, text="PROJECTS", fg=pal["TEXT_DIM"],
                 bg=pal["BG_DARK"], font=FONT_SMALL).pack(side="left")
        self._count_lbl = tk.Label(hdr, text="0", fg=ACCENT,
                                   bg=pal["BG_DARK"], font=FONT_SMALL)
        self._count_lbl.pack(side="left", padx=(6, 0))

        lc = tk.Frame(lf, bg=pal["BG_DARK"])
        lc.grid(row=1, column=0, sticky="nsew")
        lc.rowconfigure(0, weight=1)
        lc.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(lc, bg=pal["BG_DARK"],
                                 highlightthickness=0, bd=0)
        sb = tk.Scrollbar(lc, orient="vertical", command=self._canvas.yview,
                          bg=pal["BG_PANEL"], troughcolor=pal["BG_DARK"], width=6)
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        self._list_inner = tk.Frame(self._canvas, bg=pal["BG_DARK"])
        self._canvas_win = self._canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw")
        self._list_inner.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(self._canvas_win, width=e.width))
        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        log_frame = tk.Frame(panel, bg=pal["LOG_BG"])
        log_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        tk.Label(log_frame, text="LOG", fg=pal["TEXT_DIM"],
                 bg=pal["LOG_BG"], font=FONT_SMALL).pack(anchor="w", padx=10, pady=(6, 0))
        self._log_text = tk.Text(log_frame, height=6, bg=pal["LOG_BG"], fg=pal["LOG_FG"],
                                 font=FONT_MONO, relief="flat", state="disabled",
                                 bd=0, insertbackground=ACCENT, wrap="word")
        self._log_text.pack(fill="x", padx=10, pady=(2, 8))
        self._log_text.tag_config("ok",   foreground=SUCCESS)
        self._log_text.tag_config("err",  foreground=DANGER)
        self._log_text.tag_config("info", foreground=ACCENT)
        self._log_text.tag_config("warn", foreground=WARNING)

        sty = ttk.Style()
        sty.theme_use("default")
        sty.configure("Alce.Horizontal.TProgressbar",
                       troughcolor=pal["LOG_BG"], background=ACCENT, thickness=3)
        self._progress = ttk.Progressbar(panel, mode="indeterminate",
                                         style="Alce.Horizontal.TProgressbar")
        self._progress.grid(row=2, column=0, sticky="ew", pady=(4, 0))

    def _build_footer(self):
        pal = self.palette
        tk.Frame(self, bg=pal["BORDER"], height=1).pack(fill="x", side="bottom")
        self._footer = tk.Frame(self, bg=pal["BG_PANEL"])
        self._footer.pack(fill="x", side="bottom")
        inner = tk.Frame(self._footer, bg=pal["BG_PANEL"])
        inner.pack(fill="x", padx=18, pady=6)
        if self._logo_img:
            logo_lbl = tk.Label(inner, image=self._logo_img,
                                bg=pal["BG_PANEL"], cursor="hand2")
            logo_lbl.pack(side="left", padx=(0, 6))
            logo_lbl.bind("<Button-1>", lambda _: self._open_url(AUTHOR_URL))
        author = tk.Label(inner, text=f"by Ekrol34  ·  {AUTHOR_URL}",
                          fg=pal["TEXT_DIM"], bg=pal["BG_PANEL"],
                          font=FONT_SMALL, cursor="hand2")
        author.pack(side="left")
        author.bind("<Button-1>", lambda _: self._open_url(AUTHOR_URL))
        author.bind("<Enter>",    lambda _: author.config(fg=ACCENT))
        author.bind("<Leave>",    lambda _: author.config(fg=pal["TEXT_DIM"]))
        tk.Label(inner, text="Alce Project Manager  v1.0",
                 fg=pal["TEXT_DIM"], bg=pal["BG_PANEL"],
                 font=FONT_SMALL).pack(side="right")

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _open_url(url):
        import webbrowser; webbrowser.open(url)

    @staticmethod
    def _draw_help_btn(canvas, hover, pal):
        canvas.delete("all")
        col  = ACCENT if not hover else "#88AAFF"
        rgb  = bytes.fromhex(col.lstrip("#"))
        fill = "#" + "".join(f"{max(0,int(v*0.18)):02x}" for v in rgb)
        canvas.create_oval(2, 2, 26, 26, fill=fill, outline=col, width=1)
        canvas.create_text(14, 14, text="?", fill=col,
                           font=("Courier New", 11, "bold"))

    def _show_help(self):
        dlg = HelpDialog(self)
        self.wait_window(dlg)

    def _editor_label(self):
        e = self._config.get("editor")
        return os.path.basename(e) if e else "not set"

    def _log(self, msg, tag=""):
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _log_clear(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def _start_progress(self): self._progress.start(12)
    def _stop_progress(self):  self._progress.stop()

    def _refresh_list(self):
        # Stop and destroy empty-state if active
        if self._empty_state is not None:
            try: self._empty_state.stop_anim()
            except Exception: pass
            try: self._empty_state.destroy()
            except Exception: pass
            self._empty_state = None

        for w in self._cards:
            w.destroy()
        self._cards.clear()
        self._selected    = None
        self._proj_images = []
        pal = self.palette
        self._canvas.configure(bg=pal["BG_DARK"])
        self._list_inner.configure(bg=pal["BG_DARK"])

        if not self._projects:
            # ── Animated empty state ─────────────────────────────────────────
            es = EmptyState(self._list_inner, pal, self._action_new)
            # Fixed height so the inner frame doesn't expand indefinitely.
            # The canvas will stretch inside the scrollable viewport.
            es.pack(fill="x")
            es.configure(height=340)
            self._empty_state = es
            self.after(80, es.start_anim)
        else:
            for p in self._projects:
                proj_path = p.get("ruta", "")
                proj_ico  = self._find_project_ico(proj_path)
                if proj_ico:
                    icon_img = self._ico_to_photoimage(proj_ico)
                    if icon_img:
                        self._proj_images.append(icon_img)
                    else:
                        icon_img = self._card_icon
                else:
                    icon_img = self._card_icon

                card = ProjectCard(self._list_inner, p,
                                   on_select=self._select_project,
                                   on_delete=self._delete_confirm,
                                   on_open=self._open_project,
                                   palette=pal,
                                   icon_img=icon_img)
                card.pack(fill="x", pady=(0, 6))
                self._cards.append(card)

        self._count_lbl.config(text=str(len(self._projects)), bg=pal["BG_DARK"])

    def _open_project(self, project):
        self._select_project(project)
        self._action_open()

    def _select_project(self, project):
        self._selected = project
        for c in self._cards:
            if isinstance(c, ProjectCard):
                c.set_selected(c._project == project)

    def _save(self):
        self._config["projects"] = self._projects
        save_config(self._config)

    def _change_workspace(self):
        d = filedialog.askdirectory(title="Select workspace folder",
            initialdir=self._config.get("workspace", os.path.expanduser("~")))
        if d:
            self._config["workspace"] = d
            self._ws_var.set(d)
            save_config(self._config)

    def _change_editor(self):
        dlg = EditorPickerDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self._config["editor"] = dlg.result
            self._editor_var.set(self._editor_label())
            save_config(self._config)
            self._log(f"  Editor saved: {dlg.result}", "ok")

    def _resolve_editor(self):
        exe = self._config.get("editor")
        if exe and os.path.exists(exe): return exe
        if not exe:
            for _, cands in KNOWN_EDITORS:
                found = find_editor_exe(cands)
                if found:
                    if messagebox.askyesno("Editor detected",
                            f"Detected:\n{found}\n\nSet as default?"):
                        self._config["editor"] = found
                        self._editor_var.set(self._editor_label())
                        save_config(self._config)
                        return found
                    break
        dlg = EditorPickerDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self._config["editor"] = dlg.result
            self._editor_var.set(self._editor_label())
            save_config(self._config)
            return dlg.result
        return None

    # ── Actions ───────────────────────────────────────────────────────────────
    def _action_new(self):
        name = simpledialog.askstring("New Project", "Project name:", parent=self)
        if not name or not name.strip(): return
        name = name.strip()
        if name in [p["nombre"] for p in self._projects]:
            messagebox.showerror("Error", f"A project named '{name}' already exists.")
            return
        ws   = self._config.get("workspace", os.path.expanduser("~/AlceProjects"))
        path = os.path.join(ws, name)
        self._log_clear()
        self._log(f"► NEW · {name}", "info")
        self._start_progress()

        def done(ok, msg):
            self._stop_progress()
            if ok:
                self._log(f"  Path: {msg}", "ok")
                self._log("  Project created and detached from original repo ✓", "ok")
                self._projects.append({"nombre": name, "ruta": path})
                self._save()
                self.after(0, self._refresh_list)
            else:
                self._log(f"  ERROR: {msg}", "err")

        threading.Thread(target=clone_project,
            args=(name, ws, lambda m: self.after(0, self._log, m), done),
            daemon=True).start()

    def _action_open(self):
        if not self._selected:
            messagebox.showinfo("No selection", "Select a project from the list first.")
            return
        path = self._selected.get("ruta", "")
        name = self._selected.get("nombre", "?")
        if not os.path.exists(path):
            messagebox.showerror("Folder missing",
                f"The folder for '{name}' was not found:\n{path}")
            return
        exe = self._resolve_editor()
        if not exe: return
        self._log_clear()
        self._log(f"► OPEN · {name}", "info")
        self._log(f"  Editor: {exe}", "info")
        self._log(f"  Path:   {path}", "info")
        try:
            open_with_editor(exe, path)
            self._log("  Editor launched ✓", "ok")
        except Exception as e:
            self._log(f"  ERROR: {e}", "err")

    def _action_delete(self):
        if not self._selected:
            messagebox.showinfo("No selection", "Select a project from the list to delete it.")
            return
        self._delete_confirm(self._selected)

    def _delete_confirm(self, project):
        name = project.get("nombre", "?")
        path = project.get("ruta",   "")
        if not messagebox.askyesno("Confirm deletion",
                f"Delete project «{name}»?\n\nPath: {path}\n\n"
                "This will permanently remove the folder from disk."):
            return
        self._log_clear()
        self._log(f"► DELETE · {name}", "info")
        self._start_progress()

        def done(ok, msg):
            self._stop_progress()
            if ok:
                self._log("  Folder removed ✓", "ok")
                self._projects = [p for p in self._projects if p != project]
                self._save(); self.after(0, self._refresh_list)
            else:
                self._log(f"  ERROR: {msg}", "err")
                if messagebox.askyesno("Warning",
                        "Could not remove folder.\nRemove entry from list anyway?"):
                    self._projects = [p for p in self._projects if p != project]
                    self._save(); self.after(0, self._refresh_list)

        threading.Thread(target=delete_project_folder,
            args=(path, lambda m: self.after(0, self._log, m), done),
            daemon=True).start()

    def _action_update(self):
        # ── Require a project selection first ─────────────────────────────────
        if not self._selected:
            messagebox.showinfo("No selection",
                "Select a project first.\n\n"
                "UPDATE pushes Source/Alce and Build/cli.py "
                "from the selected project to a new remote branch.")
            return

        project_name = self._selected.get("nombre", "?")
        project_path = self._selected.get("ruta",   "")

        if not os.path.isdir(project_path):
            messagebox.showerror("Folder missing",
                f"The folder for project '{project_name}' was not found:\n{project_path}")
            return

        branch = simpledialog.askstring(
            "New Remote Branch",
            f"Branch name to create on the remote repository.\n"
            f"Source project:  {project_name}\n\n"
            f"Files that will be pushed:\n"
            f"  • Source/Alce/  (entire subtree)\n"
            f"  • Build/cli.py\n\n"
            f"⚠  'main' and 'master' are protected.",
            parent=self)

        if not branch or not branch.strip():
            return
        branch = branch.strip()

        if branch.lower() in ("main", "master"):
            messagebox.showerror("Protected branch",
                "Cannot create a branch named 'main' or 'master'.\n"
                "This program never operates on the main branch.")
            return

        self._log_clear()
        self._log(f"► UPDATE · project '{project_name}' → branch '{branch}'", "info")
        self._log(f"  Repository: {REPO_URL}", "info")
        self._log(f"  Pushing:  Source/Alce/  +  Build/cli.py", "info")
        self._log("  PROTECTION: main/master will never be touched ✓", "warn")
        self._start_progress()

        def done(ok, msg):
            self._stop_progress()
            if ok:
                self._log(f"  Branch '{msg}' pushed to remote ✓", "ok")
            else:
                self._log(f"  ERROR: {msg}", "err")

        threading.Thread(
            target=create_branch,
            args=(branch, project_path,
                  lambda m: self.after(0, self._log, m), done),
            daemon=True
        ).start()


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AlceManager()
    app.mainloop()