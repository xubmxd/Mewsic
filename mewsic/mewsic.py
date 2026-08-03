import io
import json
import locale
import os
import threading  # Added for the pre-fetch worker

import mpv
import requests
from bindings import MEWSIC_BINDINGS
from PIL import Image
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import (Footer, Header, Input, Label, ListItem, ListView,
                             Static)
# Import the stable Kitty image protocol widget
from textual_image.widget import Image as KittyImage
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
    except Exception:
        pass
    return colors


theme = load_pywal_colors()


class MewsicCore:
    def __init__(self):
        self.ytmusic = YTMusic()
        locale.setlocale(locale.LC_NUMERIC, "C")

        self.player = mpv.MPV(
            ytdl=True,
            ytdl_format="bestaudio/best",
            video=False,
            vo="null",
            hwdec="no",
            cache="yes",
            demuxer_max_bytes=4_000_000,
            demuxer_max_back_bytes=0,
            audio_buffer=0.1,
        )

        self.player.volume = 100
        self.on_track_ended_callback = None

        self.current_track = None
        self.upcoming_track = None
        self.play_history = set()
        self.previous_tracks = []

        @self.player.property_observer("idle-active")
        def on_idle(name, value):
            if value is True and self.on_track_ended_callback:
                self.on_track_ended_callback()

    def search_songs(self, query: str):
        results = self.ytmusic.search(query, filter="songs", limit=12)
        parsed_results = []
        for track in results:
            if track.get("videoId"):
                thumbnails = track.get("thumbnails") or track.get("thumbnail") or []
                thumb_url = thumbnails[-1]["url"] if thumbnails else None

                parsed_results.append(
                    {
                        "title": track.get("title", "Unknown"),
                        "artist": ", ".join(
                            [a["name"] for a in track.get("artists", [])]
                        ),
                        "id": track.get("videoId"),
                        "thumbnail": thumb_url,
                    }
                )
        return parsed_results

    def get_recommendation(self, video_id: str, history: set):
        try:
            res = self.ytmusic.get_watch_playlist(videoId=video_id, limit=10)
            tracks = res.get("tracks", [])

            for t in tracks:
                vid = t.get("videoId")
                if vid and vid not in history:
                    thumbnails = t.get("thumbnails") or t.get("thumbnail") or []
                    thumb_url = thumbnails[-1]["url"] if thumbnails else None

                    return {
                        "title": t.get("title", "Unknown"),
                        "artist": ", ".join([a["name"] for a in t.get("artists", [])]),
                        "id": vid,
                        "thumbnail": thumb_url,
                    }
        except Exception:
            pass
        return None

    def get_progress(self):
        try:
            return self.player.time_pos, self.player.duration
        except Exception:
            return None, None

    def seek(self, seconds: int):
        try:
            self.player.seek(seconds)
        except Exception:
            pass

    def seek_percent(self, percent: float):
        try:
            if self.player.duration:
                self.player.time_pos = self.player.duration * percent
        except Exception:
            pass

    def change_volume(self, delta: int) -> int:
        try:
            current_vol = self.player.volume
            if current_vol is None:
                current_vol = 100

            new_vol = max(0, min(100, current_vol + delta))
            self.player.volume = new_vol
            return int(new_vol)
        except Exception:
            return 100

    def play_track(self, track: dict, is_back=False):
        if not is_back and self.current_track:
            self.previous_tracks.append(self.current_track)

        self.current_track = track
        self.upcoming_track = None
        self.play_history.add(track["id"])

        url = f"https://www.youtube.com/watch?v={track['id']}"
        self.player.play(url)

    def next_track(self):
        if self.upcoming_track:
            self.play_track(self.upcoming_track)
            return self.current_track
        return None

    def previous_track(self):
        if self.previous_tracks:
            last_track = self.previous_tracks.pop()
            self.play_track(last_track, is_back=True)
            return self.current_track
        return None

    def toggle_pause(self):
        self.player.pause = not self.player.pause
        return self.player.pause

    def play(self, video_id: str):
        url = f"https://www.youtube.com/watch?v={video_id}"
        self.player.play(url)


class TrackListView(ListView):
    BINDINGS = [("j", "move_down", "Down"), ("k", "move_up", "Up")]

    def action_move_down(self) -> None:
        if self.index is None and len(self.children) > 0:
            self.index = 0
        elif self.index is not None and self.index < len(self.children) - 1:
            self.index += 1

    def action_move_up(self) -> None:
        if self.index is not None and self.index > 0:
            self.index -= 1


class InteractiveBar(Static):
    class Seek(Message):
        def __init__(self, percent: float) -> None:
            self.percent = percent
            super().__init__()

    def on_click(self, event) -> None:
        if self.size.width > 0:
            percent = event.x / self.size.width
            percent = max(0.0, min(1.0, percent))
            self.post_message(self.Seek(percent))


class MewsicApp(App):
    """A pywal-integrated TUI music player with Auto-Play and Art Caching."""
    TITLE = "mewsic"

    CSS = f"""
    Screen {{
        background: transparent; 
        color: {theme['fg']};
    }}
    Header {{
        background: transparent;
        color: {theme['border']};
        text-style: bold;
    }}
    Footer {{
        background: transparent;
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
        background: transparent;
    }}
    #volume-label {{
        width: 100%;
        text-align: right;
        color: {theme['accent']};
        text-style: bold;
        padding-right: 2;
        margin-top: 1;
    }}
    Input {{
        border: solid {theme['border']};
        background: transparent;
        color: {theme['fg']};
    }}
    Input:focus {{
        border: double {theme['accent']};
    }}
    ListView {{
        border: solid {theme['border']};
        background: transparent;
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
    #status-bar {{
        dock: bottom;
        height: 3;
        border-top: solid {theme['border']};
        background: transparent;
        color: {theme['border']};
        content-align: center middle;
    }}
    
    #album-art {{
        height: 1fr;
        width: 100%;
        content-align: center middle;
    }}
    #info-container {{
        dock: bottom;
        height: auto;
        width: 100%;
        padding-top: 1;
        border-top: dashed {theme['border']};
    }}
    #progress-container {{
        height: 1;
        width: 100%;
        margin-top: 1;
    }}
    #time-current, #time-total {{
        width: 7;
    }}

    """

    BINDINGS = MEWSIC_BINDINGS

    def __init__(self):
        super().__init__()
        self.core = MewsicCore()
        self.search_results = []
        self.current_track = None
        self.upcoming_track = None
        self.play_history = set()

        self.core.on_track_ended_callback = self.handle_track_ended

        # --- NEW: Image Pre-fetching Cache ---
        self.image_cache = {}
        self.stop_prefetch = threading.Event()

    def on_mount(self) -> None:
        self.set_interval(0.5, self.update_progress_bar)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield Input(placeholder="> AWAITING QUERY...", id="search-box")
                yield TrackListView(id="results-list")

            with Vertical(id="right-pane"):
                yield Label("VOL: 100%", id="volume-label")
                yield KittyImage(id="album-art")

                with Vertical(id="info-container"):
                    yield Label(
                        "SYSTEM IDLE\n\nAwaiting track selection.",
                        id="now-playing-text",
                    )

                    with Horizontal(id="progress-container"):
                        yield Label("--:--", id="time-current")
                        yield InteractiveBar("░" * 20, id="progress-bar")
                        yield Label("--:--", id="time-total")

        yield Label("SYS_STATUS: READY", id="status-bar")
        yield Footer()

    def _prefetch_worker(self, results):
        """Silently downloads and formats images for the top results."""
        for track in results[:15]:
            if self.stop_prefetch.is_set():
                break
            url = track.get("thumbnail")
            if not url or url in self.image_cache:
                continue

            try:
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    image = Image.open(io.BytesIO(response.content))
                    image = image.resize((400, 400))
                    self.image_cache[url] = image
            except Exception:
                pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None:
            return

        list_view = self.query_one("#results-list", TrackListView)
        try:
            index = list_view.children.index(event.item)
            if index is not None and index < len(self.search_results):
                selected_track = self.search_results[index]
                if selected_track.get("thumbnail"):
                    url = selected_track["thumbnail"]
                    # Instantly load from cache if available, otherwise fetch
                    if url in self.image_cache:
                        self.update_album_art(self.image_cache[url])
                    else:
                        self.fetch_and_display_art(url)
        except ValueError:
            pass

    @work(thread=True, exclusive=True)
    def fetch_and_display_art(self, url: str) -> None:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                image = Image.open(io.BytesIO(response.content))
                image = image.resize((400, 400))
                self.image_cache[url] = image  # Cache it for next time
                self.call_from_thread(self.update_album_art, image)
        except Exception:
            pass

    def update_album_art(self, pil_image: Image) -> None:
        album_widget = self.query_one("#album-art", KittyImage)
        album_widget.image = pil_image

    def update_progress_bar(self) -> None:
        if not self.current_track or self.core.player.pause:
            return

        time_pos, duration = self.core.get_progress()

        if time_pos is not None and duration is not None and duration > 0:

            def fmt_time(seconds):
                m, s = divmod(int(seconds), 60)
                return f"{m:02d}:{s:02d}"

            self.query_one("#time-current", Label).update(fmt_time(time_pos))
            self.query_one("#time-total", Label).update(fmt_time(duration))

            prog_bar = self.query_one("#progress-bar", InteractiveBar)
            percent = time_pos / duration

            bar_length = prog_bar.size.width or 20
            filled_length = int(bar_length * percent)

            bar_text = "█" * filled_length + "░" * (bar_length - filled_length)
            prog_bar.update(bar_text)

    def on_interactive_bar_seek(self, event: InteractiveBar.Seek) -> None:
        if self.current_track:
            self.core.seek_percent(event.percent)
            self.update_progress_bar()
            status_bar = self.query_one("#status-bar", Label)
            status_bar.update(f"SYS_STATUS: JUMPED TO {int(event.percent * 100)}%")

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

            # Stop any ongoing prefetch and clear cache for new search
            self.stop_prefetch.set()
            self.image_cache.clear()
            self.stop_prefetch = threading.Event()

            # Start prefetching top 15 results
            threading.Thread(
                target=self._prefetch_worker, args=(self.search_results,), daemon=True
            ).start()

            self.call_from_thread(self.update_results_ui)
        except Exception as e:
            self.call_from_thread(self.show_error, str(e))

    def update_results_ui(self) -> None:
        list_view = self.query_one("#results-list", TrackListView)
        list_view.clear()

        for track in self.search_results:
            list_view.append(
                ListItem(Label(f" > {track['title']} // {track['artist']}"))
            )

        list_view.focus()
        status_bar = self.query_one("#status-bar", Label)
        status_bar.update("SYS_STATUS: DATA RECEIVED. AWAITING EXECUTION.")

    def show_error(self, error_msg: str) -> None:
        status_bar = self.query_one("#status-bar", Label)
        status_bar.update(f"SYS_ERR: {error_msg}")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        list_view = self.query_one("#results-list", TrackListView)
        index = list_view.index

        if index is not None and index < len(self.search_results):
            selected_track = self.search_results[index]
            self.execute_play(selected_track)

    def execute_play(self, track: dict, is_back: bool = False) -> None:
        # Push to history if we are moving forward
        if not is_back and self.current_track:
            self.core.previous_tracks.append(self.current_track)

        self.current_track = track
        self.upcoming_track = None
        self.play_history.add(track["id"])

        if track.get("thumbnail"):
            url = track["thumbnail"]
            if url in self.image_cache:
                self.update_album_art(self.image_cache[url])
            else:
                self.fetch_and_display_art(url)

        status_bar = self.query_one("#status-bar", Label)
        status_bar.update(f"SYS_STATUS: BUFFERING AUDIO STREAM...")

        dashboard = self.query_one("#now-playing-text", Label)
        dashboard.update(
            f"[ AUDIO STREAM ACTIVE ]\n\n{track['title']}\nby {track['artist']}\n\n[ CALCULATING NEXT TRACK... ]"
        )

        self.query_one("#progress-bar", InteractiveBar).update("[ Buffering... ]")

        self.core.play(track["id"])
        status_bar.update(f"SYS_STATUS: PLAYBACK INITIATED")
        self.fetch_recommendation(track["id"], self.play_history.copy())

    @work(thread=True)
    def fetch_recommendation(self, video_id: str, history: set) -> None:
        upcoming = self.core.get_recommendation(video_id, history)
        if upcoming:
            self.call_from_thread(self.update_upcoming_ui, video_id, upcoming)

    def update_upcoming_ui(self, source_video_id: str, upcoming: dict) -> None:
        if self.current_track and self.current_track["id"] == source_video_id:
            self.upcoming_track = upcoming
            dashboard = self.query_one("#now-playing-text", Label)
            dashboard.update(
                f"[ AUDIO STREAM ACTIVE ]\n\n{self.current_track['title']}\nby {self.current_track['artist']}\n\n[ UP NEXT ]\n{upcoming['title']}"
            )

    def handle_track_ended(self) -> None:
        if self.upcoming_track:
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
        if self.upcoming_track:
            self.execute_play(self.upcoming_track)
        elif self.current_track:
            status_bar = self.query_one("#status-bar", Label)
            status_bar.update(
                "SYS_STATUS: STILL CALCULATING NEXT TRACK... PLEASE WAIT."
            )

    def action_play_previous(self) -> None:
        if self.core.previous_tracks:
            last_track = self.core.previous_tracks.pop()
            self.execute_play(last_track, is_back=True)
        else:
            status_bar = self.query_one("#status-bar", Label)
            status_bar.update("SYS_STATUS: NO PREVIOUS TRACK AVAILABLE")

    def action_seek_forward(self) -> None:
        if self.current_track:
            self.core.seek(10)
            self.update_progress_bar()
            status_bar = self.query_one("#status-bar", Label)
            status_bar.update("SYS_STATUS: SEEK +10s")

    def action_seek_backward(self) -> None:
        if self.current_track:
            self.core.seek(-10)
            self.update_progress_bar()
            status_bar = self.query_one("#status-bar", Label)
            status_bar.update("SYS_STATUS: SEEK -10s")

    def action_volume_up(self) -> None:
        new_vol = self.core.change_volume(10)
        self.query_one("#volume-label", Label).update(f"VOL: {new_vol}%")
        status_bar = self.query_one("#status-bar", Label)
        status_bar.update(f"SYS_STATUS: VOLUME INCREASED ({new_vol}%)")

    def action_volume_down(self) -> None:
        new_vol = self.core.change_volume(-10)
        self.query_one("#volume-label", Label).update(f"VOL: {new_vol}%")
        status_bar = self.query_one("#status-bar", Label)
        status_bar.update(f"SYS_STATUS: VOLUME DECREASED ({new_vol}%)")


if __name__ == "__main__":
    app = MewsicApp()
    try:
        app.run()
    except KeyboardInterrupt:
        if hasattr(app, "stop_prefetch"):
            app.stop_prefetch.set()
