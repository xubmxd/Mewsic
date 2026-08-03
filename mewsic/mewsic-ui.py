import os
import requests
import subprocess
import threading
import urwid
# Import the backend logic from your original file
from mewsic import MewsicCore


# --- Urwid Custom Widgets ---
class SearchBox(urwid.Edit):
    """Custom Edit widget that triggers a search on 'enter'."""
    def __init__(self, callback, *args, **kwargs):
        self.callback = callback
        super().__init__(*args, **kwargs)

    def keypress(self, size, key):
        if key == 'enter':
            self.callback(self.get_edit_text())
            return None
        return super().keypress(size, key)


class TrackItem(urwid.WidgetWrap):
    """Selectable track list item."""
    def __init__(self, track, callback):
        self.track = track
        self.callback = callback
        text = f" > {track['title']} // {track['artist']}"
        self.item = urwid.AttrMap(urwid.Text(text), 'normal', 'highlight')
        super().__init__(self.item)

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == 'enter':
            self.callback(self.track)
            return None
        return key


# --- Main Application UI ---
class MewsicApp:
    def __init__(self):
        self.core = MewsicCore()
        self.core.on_track_ended_callback = self.handle_track_ended
        self.imv_process = None
        self.play_history = set()
        self.current_track = None
        self.upcoming_track = None
        
        # Color Palette - 'default' background maps to terminal transparency
        self.palette = [
            ('normal', 'light gray', 'default'),
            ('accent', 'light green', 'default'),
            ('highlight', 'black', 'light green'),
            ('header', 'white', 'default'),
            ('error', 'light red', 'default'),
        ]
        
        self.build_ui()

    def build_ui(self):
        self.header = urwid.Text(("header", " mewsic // SYS_STATUS: READY\n"), align='center')
        
        # Left Pane
        self.search_box = SearchBox(self.perform_search, ("accent", "> SEARCH: "))
        self.list_walker = urwid.SimpleFocusListWalker([])
        self.list_box = urwid.ListBox(self.list_walker)
        
        left_pane = urwid.Pile([
            ('pack', self.search_box),
            ('pack', urwid.Divider("-")),
            self.list_box
        ])

        # Right Pane
        self.vol_label = urwid.Text(("accent", "VOL: 100%"), align='right')
        self.dashboard = urwid.Text(("normal", "\n\nSYSTEM IDLE\n\nAwaiting track selection."), align='center')
        self.progress_text = urwid.Text(("normal", "--:-- / --:--"), align='center')
        self.progress_bar = urwid.ProgressBar('normal', 'highlight', current=0, done=100)
        
        right_pile = urwid.Pile([
            ('pack', self.vol_label),
            self.dashboard,
            ('pack', urwid.Divider("-")),
            ('pack', self.progress_text),
            ('pack', self.progress_bar)
        ])
        right_pane = urwid.Filler(right_pile, valign='top')

        # THE FIX: Explicitly tell Urwid that both column 0 and column 1 contain Box widgets
        self.columns = urwid.Columns([
            ('weight', 60, left_pane),
            ('weight', 40, right_pane)
        ], dividechars=2, box_columns=[0, 1])
        
        self.layout = urwid.Frame(
            body=self.columns,
            header=self.header
        )

    def set_status(self, text):
        self.header.set_text(("header", f" mewsic // {text}\n"))
        self.loop.draw_screen()

    def perform_search(self, query):
        if not query.strip():
            return
            
        self.set_status(f"SYS_STATUS: FETCHING DATA FOR '{query.upper()}'...")
        
        def worker():
            try:
                results = self.core.search_songs(query)
                self.loop.set_alarm_in(0, self.update_results_ui, results)
            except Exception as e:
                self.loop.set_alarm_in(0, lambda loop, user_data: self.set_status(f"SYS_ERR: {str(e)}"))
                
        threading.Thread(target=worker, daemon=True).start()

    def update_results_ui(self, loop, user_data):
        results = user_data
        self.list_walker.clear()
        for track in results:
            self.list_walker.append(TrackItem(track, self.execute_play))
        
        self.set_status("SYS_STATUS: DATA RECEIVED. AWAITING EXECUTION.")
        self.columns.focus_position = 0
        self.columns.contents[0][0].focus_position = 2 

    def update_album_art(self, url):
        """Downloads the image and pushes it to an IMV overlay process."""
        def worker():
            try:
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    img_path = "/tmp/mewsic_cover.jpg"
                    with open(img_path, "wb") as f:
                        f.write(response.content)
                    
                    if self.imv_process and self.imv_process.poll() is None:
                        self.imv_process.terminate()
                        
                    self.imv_process = subprocess.Popen(
                        ["imv", "-u", "nearest_neighbour", "-b", "000000", img_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
            except Exception:
                pass
                
        threading.Thread(target=worker, daemon=True).start()

    def execute_play(self, track):
        self.current_track = track
        self.upcoming_track = None
        self.play_history.add(track["id"])

        if track.get("thumbnail"):
            self.update_album_art(track["thumbnail"])

        self.set_status("SYS_STATUS: BUFFERING AUDIO STREAM...")
        self.dashboard.set_text(
            f"[ AUDIO STREAM ACTIVE ]\n\n{track['title']}\nby {track['artist']}\n\n[ CALCULATING NEXT TRACK... ]"
        )

        self.core.play(track["id"])
        self.set_status("SYS_STATUS: PLAYBACK INITIATED")
        
        def worker():
            upcoming = self.core.get_recommendation(track["id"], self.play_history.copy())
            if upcoming:
                self.loop.set_alarm_in(0, self.update_upcoming_ui, upcoming)
                
        threading.Thread(target=worker, daemon=True).start()

    def update_upcoming_ui(self, loop, upcoming):
        self.upcoming_track = upcoming
        if self.current_track:
            self.dashboard.set_text(
                f"[ AUDIO STREAM ACTIVE ]\n\n{self.current_track['title']}\nby {self.current_track['artist']}\n\n[ UP NEXT ]\n{upcoming['title']}"
            )

    def handle_track_ended(self):
        if self.upcoming_track:
            self.loop.set_alarm_in(0, lambda loop, user_data: self.execute_play(self.upcoming_track))

    def update_progress(self, loop, user_data):
        if self.current_track and not self.core.player.pause:
            pos, dur = self.core.get_progress()
            if pos is not None and dur is not None and dur > 0:
                m1, s1 = divmod(int(pos), 60)
                m2, s2 = divmod(int(dur), 60)
                
                self.progress_text.set_text(f"{m1:02d}:{s1:02d} / {m2:02d}:{s2:02d}")
                percent = min(100, max(0, int((pos / dur) * 100)))
                self.progress_bar.set_completion(percent)
                
        self.loop.set_alarm_in(0.5, self.update_progress)

    def handle_input(self, key):
        if key in ('q', 'Q'):
            if self.imv_process:
                self.imv_process.terminate()
            raise urwid.ExitMainLoop()
        
        # --- Vim Navigation ---
        elif key == 'j':
            try:
                self.list_box.focus_position += 1
            except IndexError:
                pass
        elif key == 'k':
            try:
                self.list_box.focus_position -= 1
            except IndexError:
                pass
                
        # --- Playback Controls ---
        elif key == ' ':
            is_paused = self.core.toggle_pause()
            self.set_status("SYS_STATUS: PAUSED" if is_paused else "SYS_STATUS: RESUMED")
            
        elif key == ']':
            self.core.seek(10)
        elif key == '[':
            self.core.seek(-10)
            
        elif key == '+':
            vol = self.core.change_volume(10)
            self.vol_label.set_text(("accent", f"VOL: {vol}%"))
        elif key == '-':
            vol = self.core.change_volume(-10)
            self.vol_label.set_text(("accent", f"VOL: {vol}%"))
        
        elif key == ' ':
            is_paused = self.core.toggle_pause()
            self.set_status("SYS_STATUS: PAUSED" if is_paused else "SYS_STATUS: RESUMED")
            
        elif key == ']':
            self.core.seek(10)
        elif key == '[':
            self.core.seek(-10)
            
        elif key == '+':
            vol = self.core.change_volume(10)
            self.vol_label.set_text(("accent", f"VOL: {vol}%"))
        elif key == '-':
            vol = self.core.change_volume(-10)
            self.vol_label.set_text(("accent", f"VOL: {vol}%"))

    def run(self):
        self.loop = urwid.MainLoop(self.layout, self.palette, unhandled_input=self.handle_input)
        self.loop.set_alarm_in(0.5, self.update_progress)
        self.loop.run()


if __name__ == "__main__":
    app = MewsicApp()
    app.run()
