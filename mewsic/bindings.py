# bindings.py

"""
Global keybindings for Mewsic.
Format: ("key", "action_name", "Description")
"""

MEWSIC_BINDINGS = [
    ("space", "toggle_playback", "Play/Pause"),
    ("n", "skip_track", "Skip to Next"),
    ("b", "play_previous", "Previous"),
    ("right", "seek_forward", "Seek +10s"),
    ("left", "seek_backward", "Seek -10s"),
    ("=", "volume_up", "Vol +"),
    ("-", "volume_down", "Vol -"),
    ("q", "quit", "Quit App")
]
