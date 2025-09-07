#!/usr/bin/env python3
"""
Aero TUI Shell base implementation (Textual + tmux)
Fully patched for Textual 6+ with ModalScreen, correct indentation, and spaces only (no tabs)
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Button, Input, Label, ListView, ListItem
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
import sqlite3
import subprocess
import shutil
import os
import json
from pathlib import Path

DB_PATHS = ["/var/lib/aero_shell/aero.db", str(Path.home() / ".aero_shell.db")]
APPS_DIRS = ["/opt/aero_apps", str(Path.home() / ".local/share/aero_apps")]
TMUX_SESSION = "aero_home"


def find_db_path():
    for p in DB_PATHS:
        if os.path.exists(p):
            return p
    fallback = DB_PATHS[-1]
    os.makedirs(os.path.dirname(fallback), exist_ok=True)
    return fallback


def find_apps_dir():
    for d in APPS_DIRS:
        if os.path.isdir(d):
            return d
    fallback = APPS_DIRS[-1]
    os.makedirs(fallback, exist_ok=True)
    return fallback


DB_PATH = find_db_path()
APPS_DIR = find_apps_dir()


def init_db(path=DB_PATH):
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS nic_map (
        ifname TEXT PRIMARY KEY,
        nickname TEXT
    )
    """)
    conn.commit()
    conn.close()


init_db()

# --- tmux helpers ---
def tmux_available():
    return shutil.which("tmux") is not None


def tmux(cmd_args):
    if not tmux_available():
        return (1, b"", b"tmux not found")
    try:
        proc = subprocess.run(["tmux"] + cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return (proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8"))
    except Exception as e:
        return (1, "", str(e))


def ensure_tmux_session(session=TMUX_SESSION):
    code, out, err = tmux(["has-session", "-t", session])
    if code == 0:
        return True
    code, out, err = tmux(["new-session", "-d", "-s", session])
    return code == 0


def tmux_set_status(time_format_24=True, nic_summary=""):
    right = 'Aero | Battery: #(cat /sys/class/power_supply/BAT*/capacity 2>/dev/null || echo N/A) ' \
            + '| %Y-%m-%d ' \
            + ('%H:%M' if time_format_24 else '%I:%M %p')
    tmux(["set-option", "-t", TMUX_SESSION, "status-right", right])


def detect_network_interfaces():
    res = {}
    try:
        out = subprocess.check_output(["ip", "-4", "addr"], stderr=subprocess.DEVNULL).decode()
        lines = out.splitlines()
        cur = None
        for line in lines:
            if line.startswith(" "):
                if cur and "inet " in line:
                    parts = line.strip().split()
                    ip = parts[1]
                    res[cur] = ip
            else:
                if ": " in line:
                    try:
                        idx, rest = line.split(": ", 1)
                        name = rest.split(":")[0]
                        cur = name
                    except:
                        cur = None
    except Exception:
        pass
    return res

# --- Textual Modals ---
class MessageModal(ModalScreen):
    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        yield Static(self.message)
        yield Button("OK", id="ok")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        await self.app.pop_screen()


class SetupScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container():
            yield Static("Welcome to Aero TUI Shell — First time setup", id="title")
            yield Label("Create local user")
            yield Input(placeholder="username", id="username")
            yield Input(placeholder="password", password=True, id="password")
            yield Label("Time format")
            yield Button("12-hour", id="12hr")
            yield Button("24-hour", id="24hr")
            yield Label("Network interfaces detected (you may give nicknames)")
            self.nic_list = ListView(id="nic_list")
            yield self.nic_list
            yield Button("Finish setup", id="finish", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        nics = detect_network_interfaces()
        if not nics:
            self.nic_list.append(ListItem(Label("No network interfaces detected")))
        else:
            for ifname, ip in nics.items():
                self.nic_list.append(ListItem(Label(f"{ifname}: {ip}")))
        self.time_24 = True

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id
        if btn == "12hr":
            self.time_24 = False
        elif btn == "24hr":
            self.time_24 = True
        elif btn == "finish":
            username = self.query_one("#username", Input).value.strip()
            password = self.query_one("#password", Input).value.strip()
            if not username or not password:
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            try:
                c.execute("INSERT OR REPLACE INTO users (id, username, password) VALUES (1, ?, ?)", (username, password))
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('time_24', ?)", (json.dumps(self.time_24),))
                conn.commit()
            finally:
                conn.close()
            ensure_tmux_session()
            tmux_set_status(time_format_24=self.time_24)
            await self.app.switch_screen("home")


class Tile(Static):
    pane_id: reactive[str | None] = reactive(None)
    title: reactive[str] = reactive("Home")

    def compose(self) -> ComposeResult:
        yield Label(self.title)
        yield Static("(tile content placeholder)")


class HomeScreen(Screen):
    BINDINGS = [
        ("ctrl+a", "open_apps", "Open apps"),
        ("ctrl+equals", "tile_right", "Tile right"),
        ("ctrl+-", "tile_left", "Tile left"),
        ("ctrl+d", "close_tile", "Close tile"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal():
            self.left = Vertical()
            self.right = Vertical()
            yield self.left
            yield self.right
        yield Footer()
        t = Tile()
        t.title = "Home Menu"
        self.left.mount(t)
        self.selected_tile = t
        ensure_tmux_session()
        self.create_tmux_pane_for_tile(t)

    def create_tmux_pane_for_tile(self, tile: Tile):
        code, out, err = tmux(["split-window", "-t", TMUX_SESSION, "-d", "-P", "-F", "#{pane_id}", "bash"])
        if code == 0 and out.strip():
            tile.pane_id = out.strip()

    def action_open_apps(self) -> None:
        apps = self.scan_apps()
        self.app.push_screen(AppPickerScreen(apps, self))

    def scan_apps(self):
        files = []
        try:
            for entry in os.listdir(APPS_DIR):
                p = os.path.join(APPS_DIR, entry)
                if os.path.isfile(p) and os.access(p, os.X_OK):
                    files.append(p)
        except Exception:
            pass
        return files

    def action_tile_right(self) -> None:
        t = Tile()
        t.title = "App"
        self.right.mount(t)
        self.selected_tile = t
        self.create_tmux_pane_for_tile(t)

    def action_tile_left(self) -> None:
        t = Tile()
        t.title = "App"
        self.left.mount(t)
        self.selected_tile = t
        self.create_tmux_pane_for_tile(t)

    def action_close_tile(self) -> None:
        if self.selected_tile:
            if getattr(self.selected_tile, "pane_id", None):
                tmux(["kill-pane", "-t", self.selected_tile.pane_id])
            self.selected_tile.remove()
            self.selected_tile = None

    def run_app_in_selected_tile(self, app_path: str):
        pane = getattr(self.selected_tile, "pane_id", None)
        if not pane:
            self.create_tmux_pane_for_tile(self.selected_tile)
            pane = getattr(self.selected_tile, "pane_id", None)
        if pane:
            tmux(["send-keys", "-t", pane, f"exec {app_path}", "C-m"])
        else:
            tmux(["new-window", "-t", TMUX_SESSION, app_path])


class AppPickerScreen(Screen):
    BINDINGS = [("escape", "pop", "Close")]

    def __init__(self, apps, home_screen: HomeScreen):
        super().__init__()
        self.apps = apps
        self.home = home_screen

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        lv = ListView(id="apps_list")
        for a in self.apps:
            lv.append(ListItem(Label(a)))
        yield lv
        yield Footer()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        label = event.item.query_one(Label)
        app_path = label.renderable
        self.home.run_app_in_selected_tile(app_path)
        await self.app.pop_screen()

    def action_pop(self) -> None:
        self.app.pop_screen()


class AeroApp(App):
    def on_mount(self) -> None:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE id=1")
        row = c.fetchone()
        conn.close()
        if row:
            self.push_screen("home")
        else:
            self.push_screen("setup")

    def compose(self) -> ComposeResult:
        yield


if __name__ == "__main__":
    app = AeroApp()
    app.register_screen("setup", SetupScreen())
    app.register_screen("home", HomeScreen())
    app.run()
