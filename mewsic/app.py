import json
import locale
import os

import mpv
from bindings import MEWSIC_BINDINGS
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView
from ytmusicapi import YTMusic


# --- Pywal Integration ---
def load_pywal_colors():
    """Fetches colors from pywal's JSON cache. Falls back to retro green if missing."""
    colors = {
        "bg": "#000000",
        "fg": "#33ff00",
        "border": "#33ff00",
        "accent": "#66ff66",
    }
    wal_file = os.path.expanduser("~/.cache/wal/colors.json")
    try:
        if os.path.exists(wal_file):
            with open(wal_file, "r") as f:
                wal_data = json.load(f)
            colors["bg"] = wal_data["special"]["background"]
            colors["fg"] = wal_data["special"]["foreground"]
            colors["border"] = wal_data["colors"]["color4"]
            colors["accent"] = wal_data["colors"]["color6"]
    except Exception as e:
        pass
    return colors


theme = load_pywal_colors()


class MewsicCore:
    def __init__(self):
        self.ytmusic = YTMusic()
        locale.setlocale(locale.LC_NUMERIC, "C")

        self.player = mpv.MPV(
            ytdl=True,
            ytdl_format="bestaudio/best",  # Forces raw audio to prevent silent hangs
            video=False,
            vo="null",
            hwdec="no",
            cache="yes",
            demuxer_max_bytes=4_000_000,
            demuxer_max_back_bytes=0,
            audio_buffer=0.1,
        )

        # Callback variable for when a track ends naturally
        self.on_track_ended_callback = None

        # Listen for the MPV 'idle-active' property to reliably trigger autoplay
        @self.player.property_observer("idle-active")
        def on_idle(name, value):
            if value is True and self.on_track_ended_callback:
                self.on_track_ended_callback()

    def search_songs(self, query: str):
        results = self.ytmusic.search(query, filter="songs", limit=12)
        return [
            {
                "title": track.get("title", "Unknown"),
                "artist": ", ".join([a["name"] for a in track.get("artists", [])]),
                "id": track.get("videoId"),
            }
            for track in results
            if track.get("videoId")
        ]

    def get_recommendation(self, video_id: str, history: set):
        """Fetches the radio queue based on the current track, ignoring history."""
        try:
            # Fetch a larger queue (limit=10) so we have backups if top tracks are in history
            res = self.ytmusic.get_watch_playlist(videoId=video_id, limit=10)
            tracks = res.get("tracks", [])

            for t in tracks:
                vid = t.get("videoId")
                # Check if the track exists AND if it has never been played in this session
                if vid and vid not in history:
                    return {
                        "title": t.get("title", "Unknown"),
                        "artist": ", ".join([a["name"] for a in t.get("artists", [])]),
                        "id": vid,
                    }
        except Exception:
            pass
        return None

    def play(self, video_id: str):
        url = f"https://www.youtube.com/watch?v={video_id}"
        self.player.play(url)

    def toggle_pause(self):
        self.player.pause = not self.player.pause
        return self.player.pause


class MewsicApp(App):
    """A pywal-integrated TUI music player with Auto-Play."""

    CSS = f"""
    Screen {{
        background: {theme['bg']};
        color: {theme['fg']};
    }}
    Header {{
        background: {theme['bg']};
        color: {theme['border']};
        text-style: bold;
    }}
    Footer {{
        background: {theme['bg']};
        color: {theme['border']};
    }}
    #main-container {{
        height: 1fr;
    }}
    #left-pane {{
        width: 60%;
        height: 100%;
        margin: 1;
    }}
    #right-pane {{
        width: 40%;
        height: 100%;
        margin: 1;
        border: solid {theme['border']};
        content-align: center middle;
        background: {theme['bg']};
    }}
    Input {{
        border: solid {theme['border']};
        background: {theme['bg']};
        color: {theme['fg']};
    }}
    Input:focus {{
        border: double {theme['accent']};
    }}
    ListView {{
        border: solid {theme['border']};
        background: {theme['bg']};
        color: {theme['fg']};
        height: 1fr;
        margin-top: 1;
    }}
    ListItem {{
        color: {theme['fg']};
        padding: 0 1;
    }}
    ListItem.--highlight {{
        background: {theme['border']};
        color: {theme['bg']};
        text-style: bold;
    }}
    #ascii-art {{
        text-align: center;
        text-style: bold;
        color: {theme['border']};
    }}
    #now-playing-text {{
        text-align: center;
        margin-top: 2;
        color: {theme['fg']};
    }}
    #status-bar {{
        dock: bottom;
        height: 3;
        border-top: solid {theme['border']};
        background: {theme['bg']};
        color: {theme['border']};
        content-align: center middle;
    }}
    """
    BINDINGS = MEWSIC_BINDINGS

    CASSETTE_ART = """
  _________________
 | ============= |
 | |  mewsic   | |
 | |___________| |
 |  ___     ___  |
 | ( O )   ( O ) |
 |__\_/_____\_/__|
 """

    def __init__(self):
        super().__init__()
        self.core = MewsicCore()
        self.search_results = []
        self.current_track = None
        self.upcoming_track = None

        # Add a set to keep track of every song played in this session
        self.play_history = set()

        self.core.on_track_ended_callback = self.handle_track_ended

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield Input(placeholder="> AWAITING QUERY...", id="search-box")
                yield ListView(id="results-list")

            with Vertical(id="right-pane"):
                yield Label(self.CASSETTE_ART, id="ascii-art")
                yield Label(
                    "SYSTEM IDLE\n\nAwaiting track selection.", id="now-playing-text"
                )

        yield Label("SYS_STATUS: READY", id="status-bar")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if query:
            status_bar = self.query_one("#status-bar", Label)
            status_bar.update(f"SYS_STATUS: FETCHING DATA FOR '{query.upper()}'...")
            self.perform_search(query)

    @work(thread=True)
    def perform_search(self, query: str) -> None:
        try:
            self.search_results = self.core.search_songs(query)
            self.call_from_thread(self.update_results_ui)
        except Exception as e:
            self.call_from_thread(self.show_error, str(e))

    def update_results_ui(self) -> None:
        list_view = self.query_one("#results-list", ListView)
        list_view.clear()

        for track in self.search_results:
            list_view.append(
                ListItem(Label(f" > {track['title']} // {track['artist']}"))
            )

        status_bar = self.query_one("#status-bar", Label)
        status_bar.update("SYS_STATUS: DATA RECEIVED. AWAITING EXECUTION.")

    def show_error(self, error_msg: str) -> None:
        status_bar = self.query_one("#status-bar", Label)
        status_bar.update(f"SYS_ERR: {error_msg}")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        list_view = self.query_one("#results-list", ListView)
        index = list_view.index

        if index is not None and index < len(self.search_results):
            selected_track = self.search_results[index]
            self.execute_play(selected_track)

    def execute_play(self, track: dict) -> None:
        """Centralized method to start playing a track and fetch the next one."""
        self.current_track = track
        self.upcoming_track = None

        # Add this track's ID to the history so it never gets recommended again
        self.play_history.add(track["id"])

        status_bar = self.query_one("#status-bar", Label)
        status_bar.update(f"SYS_STATUS: BUFFERING AUDIO STREAM...")

        dashboard = self.query_one("#now-playing-text", Label)
        dashboard.update(
            f"[ AUDIO STREAM ACTIVE ]\n\n{track['title']}\nby {track['artist']}\n\n[ CALCULATING NEXT TRACK... ]"
        )

        self.core.play(track["id"])
        status_bar.update(f"SYS_STATUS: PLAYBACK INITIATED")

        # Pass a copy of the history to the background worker
        self.fetch_recommendation(track["id"], self.play_history.copy())

    @work(thread=True)
    def fetch_recommendation(self, video_id: str, history: set) -> None:
        """Worker thread to fetch the 'Up Next' radio track."""
        upcoming = self.core.get_recommendation(video_id, history)
        if upcoming:
            self.call_from_thread(self.update_upcoming_ui, video_id, upcoming)

    def update_upcoming_ui(self, source_video_id: str, upcoming: dict) -> None:
        """Updates the dashboard with the upcoming track."""
        # Ensure we haven't already clicked another song before this finished
        if self.current_track and self.current_track["id"] == source_video_id:
            self.upcoming_track = upcoming
            dashboard = self.query_one("#now-playing-text", Label)
            dashboard.update(
                f"[ AUDIO STREAM ACTIVE ]\n\n{self.current_track['title']}\nby {self.current_track['artist']}\n\n[ UP NEXT ]\n{upcoming['title']}"
            )

    def handle_track_ended(self) -> None:
        """Called by MPV when a track finishes natively (or network drops)."""
        if self.upcoming_track:
            # We must use call_from_thread because mpv's callback runs in C-thread land
            self.call_from_thread(self.execute_play, self.upcoming_track)

    def action_toggle_playback(self) -> None:
        is_paused = self.core.toggle_pause()
        status_bar = self.query_one("#status-bar", Label)
        dashboard = self.query_one("#now-playing-text", Label)

        if self.current_track:
            next_text = (
                f"\n\n[ UP NEXT ]\n{self.upcoming_track['title']}"
                if self.upcoming_track
                else "\n\n[ CALCULATING NEXT TRACK... ]"
            )
            if is_paused:
                status_bar.update("SYS_STATUS: PLAYBACK HALTED")
                dashboard.update(
                    f"[ STREAM PAUSED ]\n\n{self.current_track['title']}\nby {self.current_track['artist']}{next_text}"
                )
            else:
                status_bar.update("SYS_STATUS: PLAYBACK RESUMED")
                dashboard.update(
                    f"[ AUDIO STREAM ACTIVE ]\n\n{self.current_track['title']}\nby {self.current_track['artist']}{next_text}"
                )

    def action_skip_track(self) -> None:
        """Skips the current song and plays the upcoming track."""
        if self.upcoming_track:
            # Play the upcoming track directly through our execution pipeline
            self.execute_play(self.upcoming_track)
        elif self.current_track:
            # If they press skip too fast before the next track was calculated
            status_bar = self.query_one("#status-bar", Label)
            status_bar.update(
                "SYS_STATUS: STILL CALCULATING NEXT TRACK... PLEASE WAIT."
            )


if __name__ == "__main__":
    app = MewsicApp()
    app.run()
