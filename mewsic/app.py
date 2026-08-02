import os
import json
import mpv
import locale
from ytmusicapi import YTMusic
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Input, ListView, ListItem, Label

# --- Pywal Integration ---
def load_pywal_colors():
    """Fetches colors from pywal's JSON cache. Falls back to retro green if missing."""
    # Default Fallback Theme (The Retro Green)
    colors = {
        "bg": "#000000",
        "fg": "#33ff00",
        "border": "#33ff00",
        "accent": "#66ff66"
    }
    
    wal_file = os.path.expanduser("~/.cache/wal/colors.json")
    
    try:
        if os.path.exists(wal_file):
            with open(wal_file, 'r') as f:
                wal_data = json.load(f)
            
            # Map Pywal colors to our UI
            colors["bg"] = wal_data["special"]["background"]
            colors["fg"] = wal_data["special"]["foreground"]
            # color4 is usually a vibrant primary accent in Pywal
            colors["border"] = wal_data["colors"]["color4"] 
            # color6 is a good secondary highlight
            colors["accent"] = wal_data["colors"]["color6"] 
    except Exception as e:
        print(f"Failed to load pywal: {e}. Using fallback theme.")
        
    return colors

# Load the colors globally so we can inject them into the CSS
theme = load_pywal_colors()


class MewsicCore:
    def __init__(self):
        self.ytmusic = YTMusic()
        locale.setlocale(locale.LC_NUMERIC, 'C')
        
        # Aggressive RAM Optimization Profile
        self.player = mpv.MPV(
            ytdl=True,
            video=False,
            vo="null",
            hwdec="no",
            cache="yes",
            demuxer_max_bytes=4_000_000,
            demuxer_max_back_bytes=0,
            audio_buffer=0.1
        )

    def search_songs(self, query: str):
        results = self.ytmusic.search(query, filter="songs", limit=12)
        return [
            {
                "title": track.get('title', 'Unknown'),
                "artist": ", ".join([a['name'] for a in track.get('artists', [])]),
                "id": track.get('videoId')
            }
            for track in results if track.get('videoId')
        ]

    def play(self, video_id: str):
        url = f"https://www.youtube.com/watch?v={video_id}"
        self.player.play(url)

    def toggle_pause(self):
        self.player.pause = not self.player.pause
        return self.player.pause


class MewsicApp(App):
    """A pywal-integrated TUI music player."""
    
    # --- Dynamic Pywal CSS ---
    # We use double brackets {{ }} because this is a Python f-string
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
    
    BINDINGS = [
        ("space", "toggle_playback", "Play/Pause"),
        ("q", "quit", "Quit")
    ]

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
        
        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield Input(placeholder="> AWAITING QUERY...", id="search-box")
                yield ListView(id="results-list")
                
            with Vertical(id="right-pane"):
                yield Label(self.CASSETTE_ART, id="ascii-art")
                yield Label("SYSTEM IDLE\n\nAwaiting track selection.", id="now-playing-text")
                
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
            list_view.append(ListItem(Label(f" > {track['title']} // {track['artist']}")))
        
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
            
            status_bar = self.query_one("#status-bar", Label)
            status_bar.update(f"SYS_STATUS: BUFFERING AUDIO STREAM...")
            
            dashboard = self.query_one("#now-playing-text", Label)
            dashboard.update(f"[ AUDIO STREAM ACTIVE ]\n\n{selected_track['title']}\nby {selected_track['artist']}")
            
            self.core.play(selected_track['id'])
            status_bar.update(f"SYS_STATUS: PLAYBACK INITIATED")

    def action_toggle_playback(self) -> None:
        is_paused = self.core.toggle_pause()
        status_bar = self.query_one("#status-bar", Label)
        dashboard = self.query_one("#now-playing-text", Label)
        
        if self.current_track:
            if is_paused:
                status_bar.update("SYS_STATUS: PLAYBACK HALTED")
                dashboard.update(f"[ STREAM PAUSED ]\n\n{self.current_track['title']}\nby {self.current_track['artist']}")
            else:
                status_bar.update("SYS_STATUS: PLAYBACK RESUMED")
                dashboard.update(f"[ AUDIO STREAM ACTIVE ]\n\n{self.current_track['title']}\nby {self.current_track['artist']}")

if __name__ == "__main__":
    app = MewsicApp()
    app.run()
