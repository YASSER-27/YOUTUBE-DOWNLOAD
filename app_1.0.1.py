import sys
import os
import json
import time
import re
import shutil
import requests
import threading
import subprocess
from datetime import datetime

from PySide6.QtCore import (
    Qt, QThread, Signal, QUrl, QPoint,
    QPropertyAnimation, QEasingCurve, QRect, QTimer
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QComboBox, QScrollArea, QFrame, QLabel,
    QSizePolicy, QSizeGrip, QGraphicsDropShadowEffect, QMenu,
    QProgressBar, QSlider, QDialog, QFileDialog
)
from PySide6.QtGui import (
    QPixmap, QIcon, QColor, QAction, QCursor, QKeyEvent, QImage, QPainter
)
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

# Application Constants
APP_NAME = "Download Free"
SAVE_DIR = os.path.join(os.path.expanduser("~"), ".downfree")

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(SAVE_DIR, "downloads.jsonl")
SESSION_FILE = os.path.join(SAVE_DIR, "session.json")

def set_save_dir(path):
    """Switch the download folder and refresh derived paths (per settings)."""
    global SAVE_DIR, HISTORY_FILE, SESSION_FILE
    SAVE_DIR = path
    HISTORY_FILE = os.path.join(SAVE_DIR, "downloads.jsonl")
    SESSION_FILE = os.path.join(SAVE_DIR, "session.json")
    os.makedirs(SAVE_DIR, exist_ok=True)

DEFAULT_SETTINGS = {
    "download_dir": SAVE_DIR,
    "grid_columns": 4,          # 3..7 columns, 0 = List
    "auto_update_ytdlp": False,
    "auto_retry": False,
    "auto_resume": False,
    "auto_scroll_top": False,
    "open_mode": "single",      # "single" or "double"
}

def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s

def save_settings(s):
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass

def engine_exe_path():
    """Locate bundled engine.exe or local dist/engine.exe."""
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    # Check local dist/engine.exe or bundled engine.exe
    candidates = [
        os.path.join(base_path, "dist", "engine.exe"),
        os.path.join(base_path, "engine.exe"),
        os.path.join(base_path, "bin", "engine.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def find_standalone_ytdlp():
    return engine_exe_path()

def _no_window_flags():
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

def ytdlp_backend():
    """Engine backend: exe if engine.exe exists, otherwise internal module."""
    if engine_exe_path():
        return "exe"
    if HAS_YTDLP:
        return "module"
    return "none"

def get_ytdlp_version():
    """Return current engine status."""
    if engine_exe_path():
        return "exe", "2.0 (Custom Engine)"
    if HAS_YTDLP:
        return "module", "2.0 (Custom Engine)"
    return "none", "Unavailable"

def fetch_latest_ytdlp_version():
    """No external yt-dlp update checks - everything managed via custom engine."""
    return ""

def _ver_parts(v):
    parts = []
    for p in str(v).split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return parts

def version_gt(a, b):
    pa, pb = _ver_parts(a), _ver_parts(b)
    for x, y in zip(pa, pb):
        if x != y:
            return x > y
    return len(pa) > len(pb)

def get_asset_path(filename):
    """Locate asset path for both dev environment and PyInstaller bundle."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def normalize_video_url(url):
    """Normalize video URLs across popular platforms for optimal extraction."""
    url = url.strip()
    m_shorts = re.search(r'youtube\.com/shorts/([a-zA-Z0-9_-]+)', url)
    if m_shorts:
        return f"https://www.youtube.com/watch?v={m_shorts.group(1)}"
    
    m_yt = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
    if m_yt:
        return f"https://www.youtube.com/watch?v={m_yt.group(1)}"
    
    url = re.sub(r'https?://m\.youtube\.com/', 'https://www.youtube.com/', url)

    # Strip playlist context params so only the single video is extracted.
    url = re.sub(r'[?&](list|index)=[^&#]*', '', url)
    url = re.sub(r'&{2,}', '&', url).rstrip('&?')
    return url

def is_playlist_url(url):
    """Detect playlist URLs (e.g. YouTube playlists) so they are rejected
    early instead of freezing the extraction."""
    u = url.strip().lower()
    if 'youtube.com/playlist' in u:
        return True
    has_list = re.search(r'[?&]list=[a-zA-Z0-9_-]+', u) is not None
    has_video = (re.search(r'(^|[?&])v=[a-zA-Z0-9_-]+', u) is not None
                 or 'youtu.be/' in u
                 or 'youtube.com/shorts/' in u)
    return has_list and not has_video

def clean_filename(title):
    """Sanitize title string for valid Windows filenames."""
    if not title:
        return f"video_{int(time.time())}"
    clean = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    return clean[:70] if clean else f"video_{int(time.time())}"


class ToggleSwitch(QPushButton):
    """Compact ON/OFF switch button (no emojis)."""
    def __init__(self, checked=False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(46, 24)
        self.setObjectName("ToggleSwitch")
        self.setText("ON" if checked else "OFF")
        self.toggled.connect(lambda c: self.setText("ON" if c else "OFF"))




class SettingsDialog(QDialog):
    """Frameless settings window opened with /setting."""
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self._settings = dict(settings)
        self.setFixedWidth(560)
        self.drag_pos = None

        root = QFrame()
        root.setObjectName("SettingsRoot")
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(root)

        # Header
        head = QFrame()
        head.setObjectName("SettingsHeader")
        hlay = QHBoxLayout(head)
        hlay.setContentsMargins(16, 0, 10, 0)
        title = QLabel("Settings")
        title.setObjectName("SettingsTitle")
        hlay.addWidget(title)
        hlay.addStretch()
        close_btn = QPushButton("x")
        close_btn.setObjectName("SettingsCloseBtn")
        close_btn.setFixedSize(22, 22)
        close_btn.clicked.connect(self.reject)
        hlay.addWidget(close_btn)
        lay.addWidget(head)

        body = QWidget()
        blay = QVBoxLayout(body)
        blay.setContentsMargins(20, 18, 20, 18)
        blay.setSpacing(14)

        # Download folder
        dir_row = QHBoxLayout()
        dir_lbl = QLabel("Download folder")
        dir_lbl.setObjectName("SettingsLabel")
        dir_lbl.setFixedWidth(170)
        self.dir_value = QLabel(self._settings.get("download_dir", SAVE_DIR))
        self.dir_value.setObjectName("SettingsValue")
        self.dir_value.setWordWrap(True)
        choose_btn = QPushButton("Choose")
        choose_btn.setObjectName("SettingsSmallBtn")
        choose_btn.clicked.connect(self.choose_folder)
        dir_row.addWidget(dir_lbl)
        dir_row.addWidget(self.dir_value, 1)
        dir_row.addWidget(choose_btn)
        blay.addLayout(dir_row)

        # Grid mode
        grid_row = QHBoxLayout()
        grid_lbl = QLabel("Grid mode")
        grid_lbl.setObjectName("SettingsLabel")
        grid_lbl.setFixedWidth(170)
        self.grid_combo = QComboBox()
        self.grid_combo.addItems(["3 Columns", "4 Columns", "5 Columns", "6 Columns", "7 Columns", "List"])
        gc = int(self._settings.get("grid_columns", 4))
        self.grid_combo.setCurrentIndex(gc - 3 if gc >= 3 else 5)
        grid_row.addWidget(grid_lbl)
        grid_row.addWidget(self.grid_combo, 1)
        blay.addLayout(grid_row)

        def row(label):
            r = QHBoxLayout()
            l = QLabel(label)
            l.setObjectName("SettingsLabel")
            l.setFixedWidth(170)
            r.addWidget(l)
            return r

        # Switches
        r = row("Auto retry download")
        self.sw_retry = ToggleSwitch(bool(self._settings.get("auto_retry")))
        r.addWidget(self.sw_retry)
        r.addStretch()
        blay.addLayout(r)

        r = row("Auto resume download")
        self.sw_resume = ToggleSwitch(bool(self._settings.get("auto_resume")))
        r.addWidget(self.sw_resume)
        r.addStretch()
        blay.addLayout(r)

        r = row("Auto scroll to new download")
        self.sw_scroll = ToggleSwitch(bool(self._settings.get("auto_scroll_top")))
        r.addWidget(self.sw_scroll)
        r.addStretch()
        blay.addLayout(r)

        # Open mode
        open_row = QHBoxLayout()
        open_lbl = QLabel("Open video with")
        open_lbl.setObjectName("SettingsLabel")
        open_lbl.setFixedWidth(170)
        open_row.addWidget(open_lbl)
        self.btn_single = QPushButton("One click")
        self.btn_single.setObjectName("ChoiceBtn")
        self.btn_single.setCheckable(True)
        self.btn_double = QPushButton("Double click")
        self.btn_double.setObjectName("ChoiceBtn")
        self.btn_double.setCheckable(True)
        if self._settings.get("open_mode", "single") == "double":
            self.btn_double.setChecked(True)
        else:
            self.btn_single.setChecked(True)
        self.btn_single.clicked.connect(lambda: self.btn_double.setChecked(False))
        self.btn_double.clicked.connect(lambda: self.btn_single.setChecked(False))
        open_row.addWidget(self.btn_single)
        open_row.addWidget(self.btn_double)
        open_row.addStretch()
        blay.addLayout(open_row)

        blay.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SettingsSmallBtn")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("SettingsSaveBtn")
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        blay.addLayout(btn_row)

        lay.addWidget(body, 1)

    def choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Choose Download Folder",
                                              self._settings.get("download_dir", SAVE_DIR))
        if d:
            self.dir_value.setText(d)

    def result_settings(self):
        s = dict(self._settings)
        s["download_dir"] = self.dir_value.text().strip() or SAVE_DIR
        gc = self.grid_combo.currentIndex()
        s["grid_columns"] = gc + 3 if gc < 5 else 0
        s["auto_retry"] = self.sw_retry.isChecked()
        s["auto_resume"] = self.sw_resume.isChecked()
        s["auto_scroll_top"] = self.sw_scroll.isChecked()
        s["open_mode"] = "double" if self.btn_double.isChecked() else "single"
        return s

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._smart_center)

    def _smart_center(self):
        """Center the dialog over the app window on whatever monitor it sits,
        using the app's live geometry and clamping to the monitor bounds."""
        self.adjustSize()
        p = self.parentWidget()
        if p is not None and p.isVisible():
            r = p.geometry()
            screen = QApplication.screenAt(r.center())
            if screen is None:
                screen = QApplication.primaryScreen()
            avail = screen.availableGeometry()
            cx, cy = r.center().x(), r.center().y()
        else:
            screen = QApplication.primaryScreen()
            avail = screen.availableGeometry()
            cx, cy = avail.center().x(), avail.center().y()
        x = cx - self.width() // 2
        y = cy - self.height() // 2
        x = max(avail.left() + 8, min(x, avail.right() - self.width() - 8))
        y = max(avail.top() + 8, min(y, avail.bottom() - self.height() - 8))
        self.move(x, y)
        self.raise_()
        self.activateWindow()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() == Qt.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()


class MediaExtractorWorker(QThread):
    """Extracts media metadata (title, thumbnail, duration) via yt-dlp."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, target_url, preferred_quality="Best Quality"):
        super().__init__()
        self.target_url = normalize_video_url(target_url)
        self.preferred_quality = preferred_quality
        self._is_running = True

    def run(self):
        try:
            if ytdlp_backend() == "none":
                raise Exception("yt-dlp is not available. Use the Install button below the link box.")
            data = self.try_ytdlp_extraction()
            if not self._is_running:
                return
            if data:
                self.finished.emit(data)
                return
            raise Exception("Unable to extract media. Please verify the URL is valid and public.")

        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))

    def try_ytdlp_extraction(self):
        try:
            if ytdlp_backend() == "exe":
                return self._extract_via_exe()
            if not HAS_YTDLP:
                raise Exception("yt-dlp is not available. Use the Install button below the link box.")
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': False,
                'js_runtimes': {'node': {}}
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.target_url, download=False)
                if not info:
                    return None

                title = info.get("title") or "Untitled Media"
                thumb = info.get("thumbnail") or ""
                dur = info.get("duration")
                extractor = info.get("extractor_key") or info.get("extractor") or "video"

                return {
                    "mode": "ytdlp",
                    "original_url": self.target_url,
                    "title": title,
                    "thumbnail": thumb,
                    "source": extractor,
                    "duration": dur,
                    "chosen_media": {
                        "quality": self.preferred_quality,
                        "extension": "mp3" if self.preferred_quality == "Audio (MP3)" else "mp4"
                    },
                    "preferred_quality": self.preferred_quality
                }
        except Exception as e:
            raise Exception(f"Extraction Error: {str(e)[:60]}")

    def _extract_via_exe(self):
        exe = find_standalone_ytdlp()
        out = subprocess.run(
            [exe, "--no-warnings", "--skip-download", "--no-playlist", "-J", self.target_url],
            capture_output=True, text=True, timeout=180,
            creationflags=_no_window_flags())
        if out.returncode != 0:
            raise Exception(f"yt-dlp error: {(out.stderr or out.stdout).strip()[:120]}")
        info = json.loads(out.stdout)

        title = info.get("title") or "Untitled Media"
        thumb = info.get("thumbnail") or ""
        dur = info.get("duration")
        extractor = info.get("extractor_key") or info.get("extractor") or "video"

        return {
            "mode": "ytdlp",
            "original_url": self.target_url,
            "title": title,
            "thumbnail": thumb,
            "source": extractor,
            "duration": dur,
            "chosen_media": {
                "quality": self.preferred_quality,
                "extension": "mp3" if self.preferred_quality == "Audio (MP3)" else "mp4"
            },
            "preferred_quality": self.preferred_quality
        }

    def stop(self):
        self._is_running = False


class VideoDownloadWorker(QThread):
    """Downloads video stream or runs yt-dlp with live progress hooks."""
    progress = Signal(int, str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, media_info, save_path, resume=False):
        super().__init__()
        self.media_info = media_info
        self.save_path = save_path
        self._resume = resume
        self._is_cancelled = False

    def run(self):
        try:
            self.download_via_ytdlp()

        except Exception as e:
            if os.path.exists(self.save_path):
                try: os.remove(self.save_path)
                except: pass
            self.error.emit(str(e))

    def download_via_ytdlp(self):
        pref_q = self.media_info.get("preferred_quality", "Best Quality")

        if pref_q == "Audio (MP3)":
            format_spec = 'bestaudio/best'
        elif pref_q == "1080p":
            format_spec = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
        elif pref_q == "720p":
            format_spec = 'bestvideo[height<=720]+bestaudio/best[height<=720]/best'
        elif pref_q == "480p":
            format_spec = 'bestvideo[height<=480]+bestaudio/best[height<=480]/best'
        elif pref_q == "360p":
            format_spec = 'bestvideo[height<=360]+bestaudio/best[height<=360]/best'
        else:
            format_spec = 'bestvideo+bestaudio/best'

        if ytdlp_backend() == "exe":
            self.download_via_exe(format_spec)
            return
        if not HAS_YTDLP:
            raise Exception("yt-dlp is not available. Use the Install button below the link box.")

        def progress_hook(d):
            if self._is_cancelled:
                raise Exception("Download cancelled")

            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed') or 0
                if speed >= 1024 * 1024:
                    speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                else:
                    speed_str = f"{speed / 1024:.0f} KB/s"

                percent = int((downloaded / total) * 100) if total > 0 else 50
                self.progress.emit(min(99, percent), speed_str)
            elif d['status'] == 'finished':
                self.progress.emit(100, "Processing...")

        # Base path without extension for yt-dlp output template
        base_path, _ = os.path.splitext(self.save_path)
        out_tmpl = f"{base_path}.%(ext)s"

        ydl_opts = {
            'format': format_spec,
            'outtmpl': out_tmpl,
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
            'continue': True,
            'http_chunk_size': 10485760,
            'retries': 10,
            'fragment_retries': 10,
            'buffersize': 1024 * 64,
            'js_runtimes': {'node': {}}
        }

        if pref_q == "Audio (MP3)":
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([self.media_info["original_url"]])

        # Find actual downloaded file
        actual_path = self.save_path
        if not os.path.exists(actual_path):
            for ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a']:
                check_path = f"{base_path}{ext}"
                if os.path.exists(check_path):
                    actual_path = check_path
                    break

        self.progress.emit(100, "Done")
        self.finished.emit({
            "path": actual_path,
            "size_bytes": os.path.getsize(actual_path) if os.path.exists(actual_path) else 0
        })

    def download_via_exe(self, format_spec):
        """Download using the standalone yt-dlp.exe with live progress parsing."""
        exe = find_standalone_ytdlp()
        base_path, _ = os.path.splitext(self.save_path)
        out_tmpl = f"{base_path}.%(ext)s"

        cmd = [exe, "--no-warnings", "--newline", "--progress", "--no-playlist",
               "-f", format_spec, "-o", out_tmpl,
               "--merge-output-format", "mp4", "--continue",
               "--retries", "3", self.media_info["original_url"]]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                creationflags=_no_window_flags())
        speed_str = ""
        for raw in proc.stdout:
            line = raw.strip()
            m = re.search(r'\[download\]\s+([\d.]+)%', line)
            if m:
                sp = re.search(r'at\s+([\d.]+)([KM]iB)/s', line)
                if sp:
                    n = float(sp.group(1))
                    speed_str = f"{n:.1f} MB/s" if sp.group(2) == "M" else f"{n:.0f} KB/s"
                self.progress.emit(min(99, int(float(m.group(1)))), speed_str)
            if self._is_cancelled:
                try: proc.terminate()
                except Exception: pass
                break
        proc.wait()

        if self._is_cancelled:
            if os.path.exists(self.save_path):
                try: os.remove(self.save_path)
                except Exception: pass
            return

        actual_path = self.save_path
        if not os.path.exists(actual_path):
            for ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a']:
                check_path = f"{base_path}{ext}"
                if os.path.exists(check_path):
                    actual_path = check_path
                    break

        if proc.returncode != 0 and not os.path.exists(actual_path):
            raise Exception("yt-dlp download failed")

        self.progress.emit(100, "Done")
        self.finished.emit({
            "path": actual_path,
            "size_bytes": os.path.getsize(actual_path) if os.path.exists(actual_path) else 0
        })

    def cancel(self):
        self._is_cancelled = True


class ThumbnailLoaderThread(QThread):
    """Background loader for rendering thumbnail images without freezing UI."""
    image_loaded = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.queue = []
        self.is_running = True

    def add_task(self, card):
        self.queue.append(card)
        if not self.isRunning():
            self.start()

    def add_tasks(self, cards):
        self.queue.extend(cards)
        if not self.isRunning():
            self.start()

    def run(self):
        while self.queue and self.is_running:
            card = self.queue.pop(0)
            thumb_source = card.thumbnail_path_or_url
            local_file = getattr(card, 'file_path', '') or ''
            qimg = None

            if thumb_source and os.path.exists(thumb_source):
                qimg = QImage(thumb_source)
            elif thumb_source and thumb_source.startswith("http") and not (local_file and os.path.exists(local_file)):
                # No local file yet (still downloading): fetch the online image.
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                        'Referer': 'https://www.youtube.com/',
                        'Accept': 'image/avif,image/webp,image/png,image/jpeg,*/*',
                    }
                    r = requests.get(thumb_source, headers=headers, timeout=8)
                    if r.status_code == 200 and r.content:
                        qimg = QImage()
                        if not qimg.loadFromData(r.content):
                            qimg = QImage.fromData(r.content)
                        if not qimg.isNull():
                            cache_name = f"thumb_{int(time.time()*1000)}.jpg"
                            cache_path = os.path.join(SAVE_DIR, cache_name)
                            with open(cache_path, "wb") as f:
                                f.write(r.content)
                            card.thumbnail_path_or_url = cache_path
                except Exception:
                    pass

            if qimg and not qimg.isNull():
                self.image_loaded.emit(card, qimg)
                continue

            # No usable thumbnail: generate a cover frame from the local file.
            if local_file and os.path.exists(local_file):
                stem = os.path.splitext(os.path.basename(local_file))[0]
                cover_path = os.path.join(SAVE_DIR, f"cover_{stem}.jpg")
                if not os.path.exists(cover_path):
                    try:
                        ff = shutil.which("ffmpeg")
                        if ff:
                            subprocess.run(
                                [ff, "-hide_banner", "-loglevel", "error", "-y",
                                 "-ss", "2", "-i", local_file, "-frames:v", "1",
                                 "-q:v", "3", cover_path],
                                timeout=120,
                                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                    except Exception:
                        pass
                if os.path.exists(cover_path):
                    qimg = QImage(cover_path)
                    if not qimg.isNull():
                        card.thumbnail_path_or_url = cover_path
                        self.image_loaded.emit(card, qimg)


class CustomTitleBar(QFrame):
    """Frameless Window Custom Title Bar with Mac-Style Control Buttons."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(40)
        self.setObjectName("TitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("AppIconLabel")
        self.icon_label.setFixedSize(16, 16)
        icon_path = get_asset_path("icon.ico")
        if os.path.exists(icon_path):
            self.icon_label.setPixmap(QIcon(icon_path).pixmap(16, 16))
        layout.addWidget(self.icon_label)

        layout.addStretch()

        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("AppTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.btn_min = QPushButton("")
        self.btn_min.setFixedSize(14, 14)
        self.btn_min.setObjectName("MacMinBtn")
        self.btn_min.setToolTip("Minimize")
        self.btn_min.clicked.connect(self.parent.showMinimized)

        self.btn_max = QPushButton("")
        self.btn_max.setFixedSize(14, 14)
        self.btn_max.setObjectName("MacMaxBtn")
        self.btn_max.setToolTip("Maximize")
        self.btn_max.clicked.connect(self.parent.toggle_max_normal)

        self.btn_close = QPushButton("")
        self.btn_close.setFixedSize(14, 14)
        self.btn_close.setObjectName("MacCloseBtn")
        self.btn_close.setToolTip("Close")
        self.btn_close.clicked.connect(self.parent.close)

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.parent.dragPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.parent.move(self.parent.pos() + event.globalPosition().toPoint() - self.parent.dragPos)
            self.parent.dragPos = event.globalPosition().toPoint()


class URLArea(QTextEdit):
    """Input text area for video URLs with Enter submit and history navigation."""
    submitted = Signal()
    history_nav = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Paste video link here, or type /setting for options")
        self.setFixedHeight(40)
        self.setObjectName("URLInput")

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.submitted.emit()
        elif event.key() == Qt.Key_Up:
            self.history_nav.emit(-1)
        elif event.key() == Qt.Key_Down:
            self.history_nav.emit(1)
        else:
            super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        if source.hasText():
            self.insertPlainText(source.text().strip())
        else:
            super().insertFromMimeData(source)


class VideoCard(QFrame):
    """Card item in masonry grid representing a downloaded video."""
    request_play = Signal(object)
    request_delete = Signal(object)
    request_retry = Signal(object, bool)

    def __init__(self, data):
        super().__init__()
        self.data = data
        self.thumbnail_path_or_url = data.get("thumbnail", "")
        self.title = data.get("title", "Untitled")
        self.source = str(data.get("source", "video")).capitalize()
        self.duration = data.get("duration")
        self.file_path = data.get("path", "")
        self.video_url = data.get("url", "")
        self.pixmap = None
        self.target_width = 320
        self.ratio = 16 / 9
        self._downloading = False
        self.play_mode = "single"
        self._retry_count = 0

        self.setObjectName("VideoCard")
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Thumbnail Container
        self.media_container = QFrame()
        self.media_container.setObjectName("MediaContainer")
        media_layout = QVBoxLayout(self.media_container)
        media_layout.setContentsMargins(0, 0, 0, 0)
        media_layout.setSpacing(0)

        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setObjectName("ThumbLabel")
        media_layout.addWidget(self.thumb_label)

        # Duration Badge
        if self.duration:
            dur_str = self.format_duration(self.duration)
            self.dur_badge = QLabel(dur_str, self.media_container)
            self.dur_badge.setObjectName("DurationBadge")
        else:
            self.dur_badge = None

        layout.addWidget(self.media_container)

        # Download Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("CardProgressBar")
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Info Box
        self.info_strip = QFrame()
        self.info_strip.setObjectName("CardInfoStrip")
        info_layout = QVBoxLayout(self.info_strip)
        info_layout.setContentsMargins(12, 10, 12, 12)
        info_layout.setSpacing(4)

        self.title_lbl = QLabel(self.title)
        self.title_lbl.setObjectName("CardTitle")
        self.title_lbl.setWordWrap(True)
        info_layout.addWidget(self.title_lbl)

        self.status_lbl = QLabel("Ready" if self.file_path and os.path.exists(self.file_path) else "Queued")
        self.status_lbl.setObjectName("CardStatus")
        info_layout.addWidget(self.status_lbl)

        layout.addWidget(self.info_strip)

        self.apply_ratio_size()

    def format_duration(self, seconds):
        try:
            s = int(seconds)
            m, s = divmod(s, 60)
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        except Exception:
            return ""

    @property
    def is_downloaded(self):
        return bool(self.file_path) and os.path.exists(self.file_path) and not self._downloading

    def update_width(self, new_width):
        self.target_width = new_width
        self.setFixedWidth(self.target_width)
        self.apply_ratio_size()

    def apply_ratio_size(self):
        target_h = int(self.target_width / self.ratio)
        self.media_container.setFixedHeight(target_h)
        if self.dur_badge:
            self.dur_badge.move(self.target_width - self.dur_badge.sizeHint().width() - 10, target_h - 26)
        self.update_thumb()

    def update_thumb(self):
        w = self.media_container.width()
        h = self.media_container.height()
        if w <= 0 or h <= 0:
            return
        if self.pixmap is None or self.pixmap.isNull():
            self.thumb_label.clear()
            return
        # object-fit: cover  (fill the fixed 16:9 area, center-crop, no distortion)
        p = self.pixmap
        scale = max(w / p.width(), h / p.height())
        sw, sh = max(1, int(p.width() * scale)), max(1, int(p.height() * scale))
        big = p.scaled(sw, sh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x, y = max(0, (sw - w) // 2), max(0, (sh - h) // 2)
        self.thumb_label.setPixmap(big.copy(x, y, min(w, sw), min(h, sh)))

    def set_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.apply_ratio_size()
        self.update()

    def set_progress(self, percent, speed_text):
        self.progress_bar.show()
        self.progress_bar.setValue(percent)
        self.status_lbl.setText(f"Downloading: {percent}% ({speed_text})")

    def set_completed(self, path):
        self.file_path = path
        self.data["path"] = path
        self.progress_bar.hide()
        self.status_lbl.setText("Downloaded")

    def set_error(self, err_text):
        self.progress_bar.hide()
        self.status_lbl.setText(f"Error: {err_text[:30]}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.play_mode == "single":
            self.request_play.emit(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.play_mode == "double":
            self.request_play.emit(self)
        super().mouseDoubleClickEvent(event)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #111;
                color: #ffffff;
                border: 1px solid #444;
                padding: 6px;
                border-radius: 8px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QMenu::item:selected {
                background-color: #1a281d;
                color: #00E676;
            }
        """)

        play_act = QAction("Play", self)
        play_act.triggered.connect(lambda: self.request_play.emit(self))
        menu.addAction(play_act)

        if not self.is_downloaded:
            if self._downloading:
                retry_act = QAction("Retry Download", self)
                retry_act.triggered.connect(lambda: self.request_retry.emit(self, False))
                menu.addAction(retry_act)
            else:
                resume_act = QAction("Resume Download", self)
                resume_act.triggered.connect(lambda: self.request_retry.emit(self, True))
                menu.addAction(resume_act)
                retry_act = QAction("Retry Download", self)
                retry_act.triggered.connect(lambda: self.request_retry.emit(self, False))
                menu.addAction(retry_act)
            menu.addSeparator()

        save_act = QAction("Save to Downloads Folder", self)
        save_act.triggered.connect(self.export_to_downloads)
        menu.addAction(save_act)

        folder_act = QAction("Open Containing Folder", self)
        folder_act.triggered.connect(self.open_folder)
        menu.addAction(folder_act)

        copy_link_act = QAction("Copy Video Link", self)
        copy_link_act.triggered.connect(self.copy_link)
        menu.addAction(copy_link_act)

        menu.addSeparator()

        del_act = QAction("Delete", self)
        del_act.triggered.connect(lambda: self.request_delete.emit(self))
        menu.addAction(del_act)

        menu.exec(QCursor.pos())

    def export_to_downloads(self):
        if self.file_path and os.path.exists(self.file_path):
            downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            dest = os.path.join(downloads_dir, os.path.basename(self.file_path))
            try:
                import shutil
                shutil.copy2(self.file_path, dest)
                self.status_lbl.setText("Saved to Downloads")
            except Exception:
                self.status_lbl.setText("Copy failed")

    def open_folder(self):
        target = self.file_path if (self.file_path and os.path.exists(self.file_path)) else SAVE_DIR
        if sys.platform == "win32":
            if os.path.isfile(target):
                os.startfile(os.path.dirname(target))
            else:
                os.startfile(target)
        else:
            subprocess.run(["xdg-open", os.path.dirname(target)])

    def copy_link(self):
        if self.video_url:
            QApplication.clipboard().setText(self.video_url)


class DownloadFreeApp(QMainWindow):
    """Main Application Window for Download Free."""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(900, 520)
        self.dragPos = QPoint()

        self.active_workers = []
        self.download_workers = []
        self.url_history = []
        self.history_idx = -1
        self.all_cards = []
        self.col_heights = []
        self.loaded_history_count = 0
        self.chunk_size = 30
        self._mode = "video"
        self._url_anim = None
        self._bubble_anim = None
        self._active_card = None

        # Settings + download folder
        self.settings = load_settings()
        dir_setting = self.settings.get("download_dir", "")
        if dir_setting and os.path.isdir(dir_setting):
            set_save_dir(dir_setting)
        self.grid_columns = int(self.settings.get("grid_columns", 4))

        self.thumb_loader = ThumbnailLoaderThread()
        self.thumb_loader.image_loaded.connect(self.on_thumbnail_loaded)

        icon_path = get_asset_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setup_ui()
        self.apply_theme()
        self.load_history()
        QTimer.singleShot(0, self.relayout_grid)
        QTimer.singleShot(50, self._position_bottom_bar)

    def setup_ui(self):
        central = QWidget()
        central.setObjectName("Central")
        self.setCentralWidget(central)

        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Title Bar
        self.title_bar = CustomTitleBar(self)
        self.main_layout.addWidget(self.title_bar)

        # UI Container
        self.ui_container = QWidget()
        self.ui_container_layout = QVBoxLayout(self.ui_container)
        self.ui_container_layout.setContentsMargins(12, 12, 12, 0)
        self.ui_container_layout.setSpacing(0)

        # Main Masonry Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.verticalScrollBar().setSingleStep(45)
        self.scroll.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.scroll.setObjectName("MainScroll")

        self.grid_widget = QWidget()
        self.grid_widget.setObjectName("GridWidget")
        self.grid_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        self.masonry_layout = QHBoxLayout(self.grid_widget)
        self.masonry_layout.setSpacing(8)
        self.masonry_layout.setContentsMargins(10, 10, 10, 100)
        self.masonry_layout.setAlignment(Qt.AlignTop | Qt.AlignCenter)

        self.cols = []
        init_cols = self.grid_columns if self.grid_columns else 1
        for _ in range(init_cols):
            col = QVBoxLayout()
            col.setSpacing(8)
            col.setContentsMargins(0, 0, 0, 0)
            col.setAlignment(Qt.AlignTop)
            self.masonry_layout.addLayout(col)
            self.cols.append(col)

        self.scroll.setWidget(self.grid_widget)
        self.ui_container_layout.addWidget(self.scroll, 1)

        # Floating translucent bottom bar (overlay, centered over the grid)
        self.bottom_bar = QFrame()
        self.bottom_bar.setObjectName("FloatPanel")
        self.bottom_bar.setFixedWidth(480)
        bar_layout = QVBoxLayout(self.bottom_bar)
        bar_layout.setContentsMargins(12, 8, 12, 8)
        bar_layout.setSpacing(6)

        shadow = QGraphicsDropShadowEffect(self.bottom_bar)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.bottom_bar.setGraphicsEffect(shadow)

        # Row 1: URL input and Settings button
        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        self.input_area = URLArea()
        self.input_area.submitted.connect(self.start_download)
        self.input_area.history_nav.connect(self.navigate_history)
        self.input_area.textChanged.connect(self.on_url_text_changed)
        url_row.addWidget(self.input_area, 1)

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setObjectName("SettingsQuickBtn")
        self.btn_settings.setFixedSize(36, 36)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setToolTip("Settings")
        self.btn_settings.clicked.connect(self.open_settings)
        url_row.addWidget(self.btn_settings)

        bar_layout.addLayout(url_row)

        # Row 2: Video / Audio options (collapsible & animated)
        self.options_panel = QWidget()
        self.options_panel.setObjectName("OptionsPanel")
        op_layout = QHBoxLayout(self.options_panel)
        op_layout.setContentsMargins(0, 0, 0, 0)
        op_layout.setSpacing(8)

        self.btn_video = QPushButton("Video")
        self.btn_video.setObjectName("ChoiceBtn")
        self.btn_video.setCheckable(True)
        self.btn_video.setChecked(True)
        self.btn_video.setFixedHeight(30)
        self.btn_video.clicked.connect(lambda: self.choose_video())
        op_layout.addWidget(self.btn_video)

        self.btn_audio = QPushButton("Audio")
        self.btn_audio.setObjectName("ChoiceBtn")
        self.btn_audio.setCheckable(True)
        self.btn_audio.setFixedHeight(30)
        self.btn_audio.clicked.connect(lambda: self.choose_audio())
        op_layout.addWidget(self.btn_audio)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "Best Quality", "1080p", "720p", "480p", "360p", "Audio (MP3)"
        ])
        self.quality_combo.setFixedWidth(130)
        self.quality_combo.setFixedHeight(30)
        op_layout.addWidget(self.quality_combo)

        op_layout.addStretch()

        self.btn_download = QPushButton("Download")
        self.btn_download.setObjectName("DownloadBtn")
        self.btn_download.setFixedWidth(110)
        self.btn_download.setFixedHeight(40)
        self.btn_download.clicked.connect(self.start_download)
        op_layout.addWidget(self.btn_download)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("StopBtn")
        self.btn_stop.setFixedWidth(80)
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.clicked.connect(self.stop_extraction)
        self.btn_stop.hide()
        op_layout.addWidget(self.btn_stop)

        bar_layout.addWidget(self.options_panel)
        self.options_panel.setMaximumHeight(0)
        self.options_panel.hide()

        self.bottom_bar.setParent(self.ui_container)
        self.bottom_bar.adjustSize()
        self.bottom_bar.show()
        self._position_bottom_bar()
        self.bottom_bar.raise_()

        # Status Label (transient messages)
        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.hide()
        self.status_label.setParent(self.ui_container)

        # Floating Player Bubble (appears at the clicked video)
        self.main_layout.addWidget(self.ui_container, 1)

        # Resizer Grip
        self.grip = QSizeGrip(self)
        self.main_layout.addWidget(self.grip, 0, Qt.AlignRight | Qt.AlignBottom)

    def apply_theme(self):
        """Black & Green Modern UI Theme (No emojis)."""
        sheet = """
            #Central {
                background-color: #050505;
                border-radius: 12px;
                border: 1px solid #1a1a1a;
            }
            QMainWindow { background-color: transparent; }

            /* Title Bar */
            #TitleBar {
                background-color: #0a0a0a;
                border-bottom: 1px solid #1c1c1c;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
            #AppTitle {
                color: #999;
                font-weight: 700;
                font-size: 13px;
                letter-spacing: 0.8px;
            }

            /* Traffic Light Buttons */
            #MacCloseBtn { background-color: #FF5F56; border-radius: 7px; border: 1px solid #E0443E; }
            #MacCloseBtn:hover { background-color: #FF3B30; }
            #MacMinBtn { background-color: #FFBD2E; border-radius: 7px; border: 1px solid #DEA123; }
            #MacMinBtn:hover { background-color: #E8A81C; }
            #MacMaxBtn { background-color: #00E676; border-radius: 7px; border: 1px solid #00C853; }
            #MacMaxBtn:hover { background-color: #00FF85; }

            /* Scroll Area & Masonry */
            #MainScroll {
                background-color: #080808;
                border: 1px solid #181818;
                border-radius: 10px;
            }
            #GridWidget { background-color: #080808; }

            /* Scrollbar */
            QScrollBar:vertical { background: transparent; width: 6px; margin: 0px; }
            QScrollBar::handle:vertical { background: #242424; min-height: 30px; border-radius: 3px; }
            QScrollBar::handle:vertical:hover { background: #333; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

            /* Video Cards */
            #VideoCard {
                background-color: #101010;
                border: 1px solid #1f1f1f;
                border-radius: 8px;
                overflow: hidden;
            }
            #VideoCard:hover {
                border: 1px solid #888;
                background-color: #151515;
            }
            #MediaContainer {
                background-color: #050505;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            #ThumbLabel {
                background-color: #050505;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            #DurationBadge {
                background-color: rgba(0, 0, 0, 0.85);
                color: #ffffff;
                font-size: 10px;
                font-weight: 600;
                padding: 2px 6px;
                border-radius: 4px;
            }
            #CardProgressBar {
                background-color: #101010;
                border: none;
            }
            #CardProgressBar::chunk {
                background-color: #00E676;
            }
            #CardInfoStrip {
                background-color: transparent;
            }
            #CardTitle {
                color: #e2e8f0;
                font-size: 12px;
                font-weight: 600;
                line-height: 1.3;
            }
            #CardStatus {
                color: #00E676;
                font-size: 11px;
                font-weight: 500;
            }

            /* Bottom Controls */
            #FloatPanel {
                background-color: rgba(10, 10, 10, 0.52);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 18px;
            }
            #OptionsPanel { background-color: transparent; }

            #URLInput {
                background-color: rgba(20, 20, 20, 0.45);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 14px;
                padding: 8px 14px;
                font-size: 13px;
            }
            #URLInput:focus {
                border: 1px solid #00E676;
                background-color: rgba(21, 21, 21, 0.75);
            }

            /* Settings Quick Button */
            #SettingsQuickBtn {
                background-color: rgba(20, 20, 20, 0.45);
                color: #9aa3af;
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
                font-size: 16px;
            }
            #SettingsQuickBtn:hover {
                border-color: #00E676;
                color: #00E676;
                background-color: rgba(25, 25, 25, 0.70);
            }

            /* Settings dialog */
            #SettingsRoot {
                background-color: #0c0c0c;
                border: 1px solid #222;
                border-radius: 14px;
            }
            #SettingsHeader {
                background-color: #0a0a0a;
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom: 1px solid #1c1c1c;
            }
            #SettingsTitle {
                color: #ffffff;
                font-size: 14px;
                font-weight: 700;
            }
            #SettingsCloseBtn {
                background-color: #FF5F56;
                color: #1a0000;
                border: none;
                border-radius: 11px;
                font-weight: 700;
            }
            #SettingsCloseBtn:hover {
                background-color: #FF3B30;
            }
            #SettingsLabel {
                color: #cbd5e1;
                font-size: 12px;
                font-weight: 600;
            }
            #SettingsValue {
                color: #00E676;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
                background-color: #101010;
                border: 1px solid #1f1f1f;
                border-radius: 8px;
            }
            #SettingsSmallBtn {
                background-color: #161616;
                color: #cbd5e1;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                font-weight: 600;
                font-size: 11px;
                padding: 6px 14px;
            }
            #SettingsSmallBtn:hover {
                border-color: #00E676;
                color: #00E676;
            }
            #SettingsSaveBtn {
                background-color: #00E676;
                color: #051a0b;
                border: none;
                border-radius: 8px;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 22px;
            }
            #SettingsSaveBtn:hover {
                background-color: #00FF85;
            }
            #ToggleSwitch {
                background-color: #242424;
                color: #9aa3af;
                border: 1px solid #333;
                border-radius: 12px;
                font-size: 9px;
                font-weight: 700;
            }
            #ToggleSwitch:checked {
                background-color: #00E676;
                color: #051a0b;
                border: 1px solid #00C853;
            }

            #ChoiceBtn {
                background-color: #101010;
                color: #9aa3af;
                border: 1px solid #242424;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                padding: 0 20px;
            }
            #ChoiceBtn:hover {
                border-color: #00E676;
                color: #00E676;
            }
            #ChoiceBtn:checked {
                background-color: #0d2414;
                color: #00E676;
                border: 1px solid #00E676;
            }

            QComboBox {
                background-color: #101010;
                color: #ffffff;
                border: 1px solid #1f1f1f;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QComboBox:hover { border-color: #00E676; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #00E676;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #101010;
                color: #ffffff;
                selection-background-color: #00E676;
                selection-color: #051a0b;
                border: 1px solid #1f1f1f;
                border-radius: 6px;
                outline: 0px;
            }

            #ToolBtn {
                background-color: #101010;
                color: #cbd5e1;
                border: 1px solid #1f1f1f;
                border-radius: 6px;
                font-weight: 600;
                font-size: 11px;
            }
            #ToolBtn:hover {
                background-color: #161616;
                border-color: #00E676;
                color: #00E676;
            }

            #DownloadBtn {
                background-color: #00E676;
                color: #051a0b;
                border: none;
                border-radius: 10px;
                font-weight: 700;
                font-size: 14px;
                letter-spacing: 0.5px;
            }
            #DownloadBtn:hover {
                background-color: #00FF85;
            }
            #DownloadBtn:disabled {
                background-color: #141414;
                color: #4a4a4a;
            }

            #StopBtn {
                background-color: #FF5F56;
                color: #1a0000;
                border: none;
                border-radius: 10px;
                font-weight: 700;
                font-size: 13px;
            }
            #StopBtn:hover {
                background-color: #FF3B30;
            }

            #StatusLabel {
                font-size: 12px;
                font-weight: 600;
            }
        """
        qapp = QApplication.instance()
        if qapp is not None:
            qapp.setStyleSheet(sheet)
        else:
            self.setStyleSheet(sheet)

    def update_column_count(self, num_cols):
        """Dynamically adjusts columns based on window resizing."""
        if not hasattr(self, 'cols') or len(self.cols) == num_cols:
            return

        while self.masonry_layout.count():
            item = self.masonry_layout.takeAt(0)
            layout = item.layout()
            if layout:
                while layout.count():
                    layout.takeAt(0)
                layout.deleteLater()

        self.cols = []
        self.col_heights = [0] * num_cols
        for _ in range(num_cols):
            col = QVBoxLayout()
            col.setSpacing(8)
            col.setContentsMargins(0, 0, 0, 0)
            col.setAlignment(Qt.AlignTop)
            self.masonry_layout.addLayout(col)
            self.cols.append(col)

        for card in self.all_cards:
            self.add_to_masonry(card, at_top=False)

    def _num_cols_for_width(self, width):
        gc = getattr(self, 'grid_columns', 4)
        return gc if gc else 1

    def relayout_grid(self):
        """Recompute grid columns/card widths after layout changes."""
        if not hasattr(self, 'cols') or not self.cols or not hasattr(self, 'scroll'):
            return
        view_w = self.scroll.viewport().width()
        if view_w <= 0:
            view_w = self.scroll.width()
        num_cols = self._num_cols_for_width(view_w)
        self.update_column_count(num_cols)
        if self.cols:
            available_w = view_w - 20 - (len(self.cols) - 1) * 8
            if self.grid_columns == 0:
                card_w = min(620, available_w)
            else:
                card_w = max(140, available_w // num_cols)
            for card in self.all_cards:
                card.update_width(card_w)
        self.grid_widget.adjustSize()
        self.grid_widget.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, '_resize_timer'):
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self.relayout_grid)
        self._resize_timer.start(30)
        self._position_bottom_bar()
    def _position_bottom_bar(self):
        if not hasattr(self, 'bottom_bar'):
            return
        self.bottom_bar.adjustSize()
        bw = self.bottom_bar.width()
        bh = self.bottom_bar.height()
        x = max(0, (self.ui_container.width() - bw) // 2)
        y = max(0, self.ui_container.height() - bh - 14)
        self.bottom_bar.move(x, y)
        self.bottom_bar.raise_()
        if hasattr(self, 'status_label'):
            sl = self.status_label
            sl.adjustSize()
            sl.move(max(0, (self.ui_container.width() - sl.width()) // 2), max(0, y - sl.height() - 8))
            sl.raise_()

    def play_card_media(self, card):
        """Open the video with the computer's default media player (e.g. VLC)."""
        media_path = card.file_path
        if not media_path or not os.path.exists(media_path):
            if card._downloading:
                self.show_status("Still downloading... please wait.", error=True)
            else:
                self.show_status("File is not downloaded yet.", error=True)
            return

        try:
            if sys.platform == "win32":
                os.startfile(media_path)
            else:
                subprocess.Popen(["xdg-open", media_path])
        except Exception as e:
            self.show_status(f"Could not open player: {e}", error=True)

    def close_current_player(self):
        """Nothing to close — media opens in the system player."""
        pass

    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.Accepted:
            new_settings = dlg.result_settings()
            self.apply_settings(new_settings)

    def apply_settings(self, new_settings):
        old_dir = self.settings.get("download_dir")
        self.settings = new_settings
        save_settings(new_settings)

        gc = int(new_settings.get("grid_columns", 4))
        if gc != self.grid_columns:
            self.grid_columns = gc
            self.relayout_grid()

        mode = new_settings.get("open_mode", "single")
        for card in self.all_cards:
            card.play_mode = mode

        new_dir = new_settings.get("download_dir")
        if new_dir and os.path.isdir(new_dir) and os.path.normcase(os.path.abspath(new_dir)) != os.path.normcase(os.path.abspath(old_dir)):
            set_save_dir(new_dir)
            self.reload_library()

        self.show_status("Settings saved")

    def reload_library(self):
        self.thumb_loader.queue.clear()
        for card in self.all_cards:
            for col in self.cols:
                if col.indexOf(card) != -1:
                    col.removeWidget(card)
            card.deleteLater()
        self.all_cards = []
        self.history_items = []
        self.loaded_history_count = 0
        if hasattr(self, 'cols'):
            self.col_heights = [0] * len(self.cols)
        self.load_history()
        self.relayout_grid()

    def toggle_max_normal(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.close_current_player()
        elif event.key() == Qt.Key_F9:
            if self.isMinimized() or not self.isVisible() or not self.isActiveWindow():
                self.showNormal()
                self.activateWindow()
            else:
                self.showMinimized()
        super().keyPressEvent(event)

    def paste_from_clipboard(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.input_area.setPlainText(text)

    def open_save_folder(self):
        if os.path.exists(SAVE_DIR):
            if sys.platform == "win32":
                os.startfile(SAVE_DIR)
            else:
                subprocess.run(["xdg-open", SAVE_DIR])

    def navigate_history(self, delta):
        if not self.url_history:
            return
        self.history_idx += delta
        if self.history_idx < 0:
            self.history_idx = 0
        if self.history_idx >= len(self.url_history):
            self.history_idx = len(self.url_history)
            self.input_area.clear()
            return
        self.input_area.setPlainText(self.url_history[self.history_idx])

    def start_download(self):
        url = self.input_area.toPlainText().strip()
        if not url:
            return

        low = url.lower()
        if low == "/setting" or low.startswith("/setting "):
            self.input_area.clear()
            self.open_settings()
            return

        if is_playlist_url(url):
            self.input_area.clear()
            self.show_status("Playlists are not supported yet. Paste a single video link.", error=True)
            return

        if not self.url_history or self.url_history[-1] != url:
            self.url_history.append(url)
        self.history_idx = len(self.url_history)

        self.btn_download.setEnabled(False)
        self.btn_download.setText("Fetching...")
        self.btn_stop.show()
        self.show_status("Searching for media...")

        pref_quality = "Audio (MP3)" if self._mode == "audio" else self.quality_combo.currentText()
        worker = MediaExtractorWorker(url, pref_quality)
        worker.finished.connect(self.on_api_success)
        worker.error.connect(self.on_api_error)
        worker.finished.connect(lambda: self.active_workers.remove(worker) if worker in self.active_workers else None)
        worker.error.connect(lambda: self.active_workers.remove(worker) if worker in self.active_workers else None)
        self.active_workers.append(worker)
        worker.start()

    def choose_video(self):
        self._mode = "video"
        self.btn_video.setChecked(True)
        self.btn_audio.setChecked(False)
        self.quality_combo.show()
        self.btn_download.setText("Download")

    def choose_audio(self):
        self._mode = "audio"
        self.btn_audio.setChecked(True)
        self.btn_video.setChecked(False)
        self.quality_combo.hide()
        self.btn_download.setText("Download MP3")
        if self.input_area.toPlainText().strip():
            self.start_download()

    def on_url_text_changed(self):
        if self._url_anim:
            self._url_anim.stop()
        text = self.input_area.toPlainText().strip()
        self.animate_options(bool(text))

    def animate_options(self, show):
        target = 80 if show else 0
        self._url_anim = QPropertyAnimation(self.options_panel, b"maximumHeight", self)
        self._url_anim.setDuration(200)
        self._url_anim.setStartValue(self.options_panel.maximumHeight())
        self._url_anim.setEndValue(target)
        self._url_anim.setEasingCurve(QEasingCurve.InOutCubic)
        if show:
            self.options_panel.show()
        else:
            self._url_anim.finished.connect(lambda: self.options_panel.hide())
        self._url_anim.valueChanged.connect(self._position_bottom_bar)
        self._url_anim.finished.connect(self._position_bottom_bar)
        self._url_anim.start()

    def reset_search_ui(self):
        self.btn_download.setEnabled(True)
        self.btn_download.setText("Download" if self._mode != "audio" else "Download MP3")
        self.btn_stop.hide()

    def stop_extraction(self):
        for w in self.active_workers:
            w.stop()
        self.active_workers.clear()
        self.reset_search_ui()
        self.show_status("Search stopped.")

    def show_status(self, text, error=False):
        if not hasattr(self, 'status_label'):
            return
        if error:
            self.status_label.setStyleSheet(
                "background-color:#1a0a0a;color:#ff6b6b;"
                "border:1px solid #ff5f56;border-radius:6px;padding:6px 10px;"
            )
        else:
            self.status_label.setStyleSheet(
                "background-color:#0d2414;color:#00E676;"
                "border:1px solid #1f6b3a;border-radius:6px;padding:6px 10px;"
            )
        self.status_label.setText(text)
        self.status_label.show()
        QTimer.singleShot(6000, self.status_label.hide)

    def on_api_error(self, err_msg):
        self.reset_search_ui()
        self.show_status(f"Error: {err_msg}", error=True)
        print(f"Extraction Error: {err_msg}")

    def on_api_success(self, data):
        self.reset_search_ui()
        self.input_area.clear()

        ext = data.get("chosen_media", {}).get("extension", "mp4")
        base_name = clean_filename(data["title"])
        filename = f"{base_name}_{int(time.time())}.{ext}"
        local_path = os.path.join(SAVE_DIR, filename)

        card_data = {
            "title": data["title"],
            "url": data["original_url"],
            "thumbnail": data["thumbnail"],
            "source": data["source"],
            "duration": data.get("duration"),
            "path": local_path,
            "filename": filename,
            "chosen_media": data.get("chosen_media", {}),
            "timestamp": int(time.time())
        }

        card = self.create_video_card(card_data)
        card._media_info = data
        self.all_cards.insert(0, card)
        self.add_to_masonry(card, at_top=True)
        if self.settings.get("auto_scroll_top"):
            self.scroll.verticalScrollBar().setValue(0)

        if card_data["thumbnail"]:
            self.thumb_loader.add_task(card)

        self._start_downloader(card, data, local_path, resume=False)

    def _start_downloader(self, card, media_info, save_path, resume=False):
        card._downloading = True
        downloader = VideoDownloadWorker(media_info, save_path, resume=resume)
        downloader.progress.connect(card.set_progress)
        downloader.finished.connect(lambda res: self.on_download_complete(card, res, card.data))
        downloader.error.connect(lambda err: self.on_download_error(card, err))
        downloader.finished.connect(lambda: self._remove_downloader(downloader, card))
        downloader.error.connect(lambda: self._remove_downloader(downloader, card))
        card._active_downloader = downloader
        self.download_workers.append(downloader)
        downloader.start()

    def retry_download(self, card, resume=False):
        dw = getattr(card, "_active_downloader", None)
        if dw is not None and dw.isRunning():
            dw.cancel()
            dw.terminate()
            dw.wait(1500)
            self._remove_downloader(dw, card)

        data = getattr(card, "_media_info", None)
        if not data:
            data = {
                "mode": "ytdlp",
                "original_url": card.video_url,
                "title": card.title,
                "thumbnail": card.thumbnail_path_or_url,
                "source": card.data.get("source", "video"),
                "duration": card.duration,
                "chosen_media": card.data.get("chosen_media", {}),
                "preferred_quality": "Best Quality",
            }
        filename = card.data.get("filename") or "video.mp4"
        save_path = card.data.get("path") or os.path.join(SAVE_DIR, filename)
        card.status_lbl.setText("Resuming..." if resume else "Retrying...")
        self._start_downloader(card, data, save_path, resume=resume)

    def _remove_downloader(self, downloader, card):
        if downloader in self.download_workers:
            self.download_workers.remove(downloader)
        if getattr(card, "_active_downloader", None) is downloader:
            card._active_downloader = None
        card._downloading = False

    def on_download_error(self, card, err):
        card._downloading = False
        card.set_error(err)
        retries = getattr(card, "_retry_count", 0) + 1
        card._retry_count = retries

        partial = card.file_path and os.path.exists(card.file_path) and os.path.getsize(card.file_path) > 0
        if retries <= 3:
            if self.settings.get("auto_resume") and partial:
                self.show_status("Resuming download automatically...")
                QTimer.singleShot(800, lambda: self.retry_download(card, resume=True))
                return
            if self.settings.get("auto_retry"):
                self.show_status("Retrying download automatically...")
                QTimer.singleShot(800, lambda: self.retry_download(card, resume=False))
                return
        self.show_status(f"Download failed: {err}", error=True)

    def on_download_complete(self, card, result, card_data):
        card.set_completed(result["path"])
        self.save_to_history(card_data)

    def save_to_history(self, item_data):
        try:
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(item_data) + "\n")
        except Exception as e:
            print("History save error:", e)

    def load_history(self):
        entries = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                entries.append(json.loads(line))
                            except: pass
            except Exception:
                return

        # Merge video files found on disk so every downloaded video shows up,
        # even if its history entry is missing/stale. Also pair them with any
        # matching thumbnail cached in the save folder.
        covered = set()
        for e in entries:
            p = e.get("path")
            if p:
                covered.add(os.path.normcase(os.path.abspath(p)))

        def cover_cache_path(video_path):
            stem = os.path.splitext(os.path.basename(video_path))[0]
            return os.path.join(SAVE_DIR, f"cover_{stem}.jpg")

        try:
            for f in sorted(os.scandir(SAVE_DIR),
                            key=lambda d: d.stat().st_mtime, reverse=True):
                try:
                    if not f.is_file():
                        continue
                except OSError:
                    continue
                ext = os.path.splitext(f.name)[1].lower()
                if ext not in ('.mp4', '.mkv', '.webm'):
                    continue
                ap = os.path.normcase(os.path.abspath(f.path))
                if ap in covered:
                    continue
                cover = cover_cache_path(f.path)
                entries.append(self._file_card_data(f, cover if os.path.exists(cover) else ""))
        except OSError:
            pass

        entries.sort(key=lambda e: e.get("timestamp") or 0, reverse=True)
        self.history_items = entries
        # Show everything on startup; chunked loading only matters for huge
        # libraries, so load all of them now.
        while self.loaded_history_count < len(entries):
            self.load_next_history_chunk()

    def _file_card_data(self, f, thumb_path=""):
        """Build minimal card data from a video file found in the save folder."""
        fname = f.name
        stem = os.path.splitext(fname)[0]
        m = re.search(r'_(1\d{9})$', stem)
        if m:
            title = stem[:m.start()].strip()
            ts = int(m.group(1))
        else:
            title = stem.strip()
            ts = int(f.stat().st_mtime)
        return {
            "title": title,
            "url": "",
            "thumbnail": thumb_path,
            "source": "downloaded",
            "duration": None,
            "path": f.path,
            "filename": fname,
            "chosen_media": {},
            "timestamp": ts,
        }

    def load_next_history_chunk(self):
        if not hasattr(self, 'history_items') or self.loaded_history_count >= len(self.history_items):
            return

        end_idx = min(self.loaded_history_count + self.chunk_size, len(self.history_items))
        chunk = self.history_items[self.loaded_history_count:end_idx]

        new_cards = []
        for item in chunk:
            card = self.create_video_card(item)
            self.all_cards.append(card)
            self.add_to_masonry(card, at_top=False)
            new_cards.append(card)

        self.loaded_history_count = end_idx
        self.thumb_loader.add_tasks(new_cards)

    def on_scroll(self, value):
        max_val = self.scroll.verticalScrollBar().maximum()
        if max_val > 0 and value >= max_val - 800:
            self.load_next_history_chunk()

    def create_video_card(self, card_data):
        card = VideoCard(card_data)
        card.play_mode = self.settings.get("open_mode", "single")
        card.request_play.connect(self.play_card_media)
        card.request_delete.connect(self.delete_card)
        card.request_retry.connect(self.retry_download)

        if hasattr(self, 'cols') and self.cols:
            num_cols = len(self.cols)
            available_w = self.scroll.width() - 36 - (num_cols - 1) * 12
            card_w = max(180, available_w // num_cols)
            card.update_width(card_w)

        return card

    def add_to_masonry(self, card, at_top=True):
        if not hasattr(self, 'col_heights') or len(self.col_heights) != len(self.cols):
            self.col_heights = [0] * len(self.cols)

        min_idx = 0
        min_h = self.col_heights[0]
        for i in range(1, len(self.cols)):
            if self.col_heights[i] < min_h:
                min_h = self.col_heights[i]
                min_idx = i

        col = self.cols[min_idx]
        if at_top:
            col.insertWidget(0, card)
        else:
            col.addWidget(card)

        self.col_heights[min_idx] += card.height()

    def on_thumbnail_loaded(self, card, qimage):
        pix = QPixmap.fromImage(qimage)
        card.set_pixmap(pix)

    def delete_card(self, card):
        if card in self.all_cards:
            self.all_cards.remove(card)

        dw = getattr(card, "_active_downloader", None)
        if dw is not None and dw.isRunning():
            dw.cancel()
            dw.terminate()
            dw.wait(1500)
            self._remove_downloader(dw, card)

        for i, col in enumerate(self.cols):
            if col.indexOf(card) != -1:
                col.removeWidget(card)
                if hasattr(self, 'col_heights') and i < len(self.col_heights):
                    self.col_heights[i] -= card.height()
                card.deleteLater()
                break

        if card.file_path and os.path.exists(card.file_path):
            try: os.remove(card.file_path)
            except: pass

        self.rewrite_history()

    def rewrite_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                for c in reversed(self.all_cards):
                    f.write(json.dumps(c.data) + "\n")
        except Exception:
            pass

    def closeEvent(self, event):
        for w in self.active_workers:
            w.stop()
            w.wait()
        for dw in self.download_workers:
            dw.cancel()
            dw.wait()
        for w in getattr(self, '_yt_workers', []):
            if w.isRunning():
                w.wait(1000)
        super().closeEvent(event)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DownloadFreeApp")
        except Exception:
            pass
    app = QApplication(sys.argv)
    icon_path = get_asset_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = DownloadFreeApp()
    window.show()
    sys.exit(app.exec())
