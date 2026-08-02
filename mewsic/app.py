import mpv
import locale
from ytmusicapi import YTMusic
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Input, ListView, ListItem, Label

class MewsicCore:
    def __init__(self):
        self.ytmusic = YTMusic()
        
        # prevent segmentation error
        locale.setlocale(locale.LC_NUMERIC, 'C')
        
        # ytdl=True hooks into yt-dlp to stream, video=False keeps memory usage minimal
        self.player = mpv.MPV(ytdl=True, video=False)

    def search_songs(self, query: str):
        results = self.ytmusic.search(query, filter="songs", limit=8)
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
    """A lightweight, ad-free TUI music player."""
    
    CSS = """
    Screen {
        align: center middle;
    }
    #search-box {
        dock: top;
        margin: 1 2;
    }
    #results-list {
        margin: 1 2;
        border: round white;
        height: 60%;
    }
    #status-bar {
        dock: bottom;
        height: 3;
        background: $accent;
        color: white;
        content-align: center middle;
        text-style: bold;
    }
    """
    
    BINDINGS = [
        ("space", "toggle_playback", "Play/Pause"),
        ("q", "quit", "Quit")
    ]

    def __init__(self):
        super().__init__()
        self.core = MewsicCore()
        self.search_results = []
        self.current_track = None  # Clean internal state tracking

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Input(placeholder="Search for music...", id="search-box")
        yield ListView(id="results-list")
        yield Label("Not playing anything yet.", id="status-bar")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Triggered when the user presses Enter in the search bar."""
        query = event.value.strip()
        if query:
            status_bar = self.query_one("#status-bar", Label)
            status_bar.update(f"Searching for '{query}'...")
            
            # Run the search via background worker thread
            self.perform_search(query)

    @work(thread=True)
    def perform_search(self, query: str) -> None:
        """Worker thread for network scraping."""
        try:
            self.search_results = self.core.search_songs(query)
            self.call_from_thread(self.update_results_ui)
        except Exception as e:
            self.call_from_thread(self.show_error, str(e))

    def update_results_ui(self) -> None:
        """Updates the TUI list with search results."""
        list_view = self.query_one("#results-list", ListView)
        list_view.clear()
        
        for track in self.search_results:
            list_view.append(ListItem(Label(f"🎵 {track['title']} — {track['artist']}")))
        
        status_bar = self.query_one("#status-bar", Label)
        status_bar.update("Search complete. Use Up/Down arrows and Enter to play.")

    def show_error(self, error_msg: str) -> None:
        status_bar = self.query_one("#status-bar", Label)
        status_bar.update(f"Error: {error_msg}")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Triggered when the user presses Enter on a list item."""
        list_view = self.query_one("#results-list", ListView)
        index = list_view.index
        
        if index is not None and index < len(self.search_results):
            selected_track = self.search_results[index]
            self.current_track = selected_track  # Safely store what is playing
            
            status_bar = self.query_one("#status-bar", Label)
            status_bar.update(f"Loading: {selected_track['title']}...")
            
            # Start streaming the chosen song
            self.core.play(selected_track['id'])
            status_bar.update(f"▶ Now Playing: {selected_track['title']} by {selected_track['artist']}")

    def action_toggle_playback(self) -> None:
        """Toggles music playback via spacebar."""
        is_paused = self.core.toggle_pause()
        status_bar = self.query_one("#status-bar", Label)
        
        # Cleanly update UI using our state object
        if self.current_track:
            status = "⏸ Paused" if is_paused else "▶ Now Playing"
            status_bar.update(f"{status}: {self.current_track['title']} by {self.current_track['artist']}")

if __name__ == "__main__":
    app = MewsicApp()
    app.run()
