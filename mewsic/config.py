import os
import json

APP_TITLE = "Mewsic"
DEFAULT_REC_LIMIT = 15
DEFAULT_VOLUME = 100
STATE_FILE = os.path.expanduser("~/.cache/mewsic_state.json")

def load_pywal_colors():
    colors = {
        "bg": "#170911",
        "fg": "#c5c1c3",
        "border": "#E53D42",
        "accent": "#F14F51",
    }
    wal_file = os.path.expanduser("~/.cache/wal/colors.json")
    try:
        if os.path.exists(wal_file):
            with open(wal_file, "r") as f:
                wal_data = json.load(f)
            colors["bg"] = wal_data["special"]["background"]
            colors["fg"] = wal_data["special"]["foreground"]
            colors["border"] = wal_data["colors"]["color2"]
            colors["accent"] = wal_data["colors"]["color6"]
    except Exception:
        pass
        
    return colors

THEME = load_pywal_colors()

LIST_BINDINGS = [
    ("j", "move_down", "Down"),
    ("k", "move_up", "Up"),
]

MEWSIC_BINDINGS = [
    ("space", "toggle_playback", "Play/Pause"),
    ("n", "skip_track", "Skip to Next"),
    ("N", "set_next_track", "Set Next Track"),
    ("b", "play_previous", "Previous"),
    ("=", "volume_up", "Vol +"),
    ("-", "volume_down", "Vol -"),
    ("l", "toggle_loop", "Loop Track"),
    ("right", "seek_forward", "Seek +10s"),
    ("left", "seek_backward", "Seek -10s"),
    ("q", "quit", "Quit"),
]
