import locale

import mpv
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView
from ytmusicapi import YTMusic


class MewsicCore:
    def __init__(self):
        self.ytmusic = YTMusic()
        locale.setlocale(locale.LC_NUMERIC, "C")

        # --- Aggressive RAM Optimization Profile ---
        self.player = mpv.MPV(
            ytdl=True,
            # 1. Kill all video processing completely
            video=False,
            vo="null",  # Absolutely no video output driver
            hwdec="no",  # No GPU memory contexts allocated
            # 2. Severely restrict the stream caching
            cache="yes",  # Keep cache on so streams don't stutter...
            demuxer_max_bytes=4_000_000,  # ...but limit forward buffer to ~4MB (default is huge)
            demuxer_max_back_bytes=0,  # 0MB backward buffer (we don't need to rewind)
            # 3. Audio optimizations
            audio_buffer=0.1,  # Tiny audio output buffer (100ms)
        )

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

    def play(self, video_id: str):
        url = f"https://www.youtube.com/watch?v={video_id}"
        self.player.play(url)

    def toggle_pause(self):
        self.player.pause = not self.player.pause
        return self.player.pause


class MewsicApp(App):
    """A retro, ad-free TUI music player."""

    # --- The Retro CSS Theme ---
    CSS = """
    Screen {
        background: #000000;
        color: #33ff00;
    }
    Header {
        background: #002200;
        color: #33ff00;
        text-style: bold;
    }
    Footer {
        background: #002200;
        color: #33ff00;
    }
    #main-container {
        height: 1fr;
    }
    #left-pane {
        width: 60%;
        height: 100%;
        margin: 1;
    }
    #right-pane {
        width: 40%;
        height: 100%;
        margin: 1;
        border: solid #33ff00;
        content-align: center middle;
        background: #051005;
    }
    Input {
        border: solid #33ff00;
        background: #000000;
        color: #33ff00;
    }
    Input:focus {
        border: double #66ff66;
    }
    ListView {
        border: solid #33ff00;
        background: #000000;
        color: #33ff00;
        height: 1fr;
        margin-top: 1;
    }
    ListItem {
        color: #33ff00;
        padding: 0 1;
    }
    ListItem.--highlight {
        background: #004400;
        color: #ffffff;
        text-style: bold;
    }
    #ascii-art {
        text-align: center;
        text-style: bold;
        color: #33ff00;
    }
    #now-playing-text {
        text-align: center;
        margin-top: 2;
        color: #66ff66;
    }
    #status-bar {
        dock: bottom;
        height: 3;
        border-top: solid #33ff00;
        background: #000000;
        color: #33ff00;
        content-align: center middle;
    }
    """

    BINDINGS = [("space", "toggle_playback", "Play/Pause"), ("q", "quit", "Quit")]

    # The ASCII Cassette Tape
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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # The new Two-Pane Layout
        with Horizontal(id="main-container"):
            # Left Side: Search & Results
            with Vertical(id="left-pane"):
                yield Input(placeholder="> AWAITING QUERY...", id="search-box")
                yield ListView(id="results-list")

            # Right Side: Dashboard
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
            self.current_track = selected_track

            # Update Status Bar
            status_bar = self.query_one("#status-bar", Label)
            status_bar.update(f"SYS_STATUS: BUFFERING AUDIO STREAM...")

            # Update Dashboard (Right Pane)
            dashboard = self.query_one("#now-playing-text", Label)
            dashboard.update(
                f"[ AUDIO STREAM ACTIVE ]\n\n{selected_track['title']}\nby {selected_track['artist']}"
            )

            self.core.play(selected_track["id"])
            status_bar.update(f"SYS_STATUS: PLAYBACK INITIATED")

    def action_toggle_playback(self) -> None:
        is_paused = self.core.toggle_pause()
        status_bar = self.query_one("#status-bar", Label)
        dashboard = self.query_one("#now-playing-text", Label)

        if self.current_track:
            if is_paused:
                status_bar.update("SYS_STATUS: PLAYBACK HALTED")
                dashboard.update(
                    f"[ STREAM PAUSED ]\n\n{self.current_track['title']}\nby {self.current_track['artist']}"
                )
            else:
                status_bar.update("SYS_STATUS: PLAYBACK RESUMED")
                dashboard.update(
                    f"[ AUDIO STREAM ACTIVE ]\n\n{self.current_track['title']}\nby {self.current_track['artist']}"
                )


if __name__ == "__main__":
    app = MewsicApp()
    app.run()
