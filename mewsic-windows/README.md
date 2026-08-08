# 🎵 Mewsic

Mewsic is a sleek, terminal-based (TUI) music player powered by YouTube Music, mpv, and Textual. 

Search for tracks, queue up your favorite artists, and let the endless radio feature automatically recommend and play related music. It even remembers your last played track and restores your session when you restart.

## Features
* **Endless Radio:** Automatically fetches and queues recommendations based on the currently playing track.
* **Session Restore:** Remembers your volume and the last song you played, seamlessly restoring your queue on startup.
* **Album Art:** Fetches and caches high-quality album art directly in your terminal.
* **Idle Previews:** Browse upcoming recommendations; if you idle for 5 seconds, the album art automatically snaps back to the currently playing track.
---

## Installation

### General Requirements
* Python 3.8+
* mpv media player installed on your system.
* yt-dlp (for extracting audio streams).

### One line installation
```powershell
irm https://raw.githubusercontent.com/xubmxd/Mewsic/main/install.ps1 | iex
```
### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/Mewsic.git
cd Mewsic
```

### 2. Set Up a Virtual Environment
```bash
python -m venv .venv
```
**Activate it:**
* **Windows (cmd):** `.venv\Scriptsctivate`
* **Windows (PowerShell):** `.\.venv\Scripts\Activate.ps1`

### 3. Install Dependencies
```bash
pip install -r requirements.txt
python -m pip install yt-dlp
```

---

## Windows-Specific Setup 
Running mpv through Python on Windows requires the raw C-library .dll file, not just the standard media player. If you get an OSError: Cannot find mpv-1.dll, follow these exact steps:

 **Extract the DLL:**
   * Open the archive and locate libmpv-2.dll (or mpv-2.dll).
   * Copy this file and paste it directly into your mewsic project folder, right next to mewsic.py.
---

## Usage

Make sure your virtual environment is activated, then run:

```bash
python mewsic.py
```

### Controls
* **Search:** Type your query in the top-left box and hit Enter.
* **Play:** Use the arrow keys to navigate the search results or recommendations, and press Enter to play.
* **Seek:** Click anywhere on the progress bar at the bottom right to jump to that part of the song.
* **Switch Focus** You can switch focus from search window using `Tab` key.
* **Navigation** You can navigate using J and K keys to navigate the search results in the results tab.
* **Skip song or Play Previous Song** You can skip a song using the `n` key, and play the previous song using the `b` key.
---

## Troubleshooting
* **REC_ERR: 'endpoint' or Radio API Failures:** YouTube Music frequently updates its backend. If recommendations fail to load, ensure your ytmusicapi is fully up to date by running: pip install --upgrade ytmusicapi. Mewsic is built with a fallback system that will search the artist's discography if the radio endpoint fails!
