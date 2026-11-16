import sys
import os
import json
import time
import re
import shutil
import requests
import threading
import subprocess

# Guarantee project root is in sys.path so vendored packages (yt_dlp) always import
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from PyQt5.QtCore import (
        Qt, QThread, pyqtSignal as Signal, QUrl, QPoint, QByteArray, QSize,
        QPropertyAnimation, QEasingCurve, QRect, QTimer, pyqtProperty as Property
    )
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTextEdit, QPushButton, QComboBox, QScrollArea, QFrame, QLabel,
        QSizePolicy, QSizeGrip, QGraphicsDropShadowEffect, QMenu, QAction,
        QProgressBar, QSlider, QDialog, QFileDialog, QGridLayout, QCheckBox
    )
    from PyQt5.QtGui import (
        QPixmap, QIcon, QColor, QCursor, QKeyEvent, QImage, QPainter,
        QPen, QBrush, QFont, QLinearGradient
    )
    from PyQt5.QtSvg import QSvgRenderer
    QT_LIB = "PyQt5"
except ImportError:
    from PySide6.QtCore import (
        Qt, QThread, Signal, QUrl, QPoint, QByteArray, QSize,
        QPropertyAnimation, QEasingCurve, QRect, QTimer, Property
    )
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTextEdit, QPushButton, QComboBox, QScrollArea, QFrame, QLabel,
        QSizePolicy, QSizeGrip, QGraphicsDropShadowEffect, QMenu,
        QProgressBar, QSlider, QDialog, QFileDialog, QGridLayout, QCheckBox
    )
    from PySide6.QtGui import (
        QPixmap, QIcon, QColor, QAction, QCursor, QKeyEvent, QImage, QPainter,
        QPen, QBrush, QFont, QLinearGradient
    )
    from PySide6.QtSvg import QSvgRenderer
    QT_LIB = "PySide6"


SETTINGS_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.7 2.9-.2-.1a1.7 1.7 0 0 0-1.9.3l-.1.1h-3.4l-.1-.2a1.7 1.7 0 0 0-1.5-1 1.7 1.7 0 0 0-1.5 1l-.1.2H6l-.1-.2a1.7 1.7 0 0 0-1.5-1 1.7 1.7 0 0 0-1.5 1l-.1.2-1.7-2.9.1-.1A1.7 1.7 0 0 0 1.5 15l-.1-.2v-3.4l.2-.1a1.7 1.7 0 0 0 1-1.5 1.7 1.7 0 0 0-1-1.5l-.2-.1V4.8l.2-.1a1.7 1.7 0 0 0 1-1.5 1.7 1.7 0 0 0-1-1.5l-.2-.1 1.7-2.9.1.1a1.7 1.7 0 0 0 1.9.3l.1-.1h3.4l.1.2a1.7 1.7 0 0 0 1.5 1 1.7 1.7 0 0 0 1.5-1l.1-.2h3.4l.1.2a1.7 1.7 0 0 0 1.5 1 1.7 1.7 0 0 0 1.5-1l.1-.2 1.7 2.9-.1.1a1.7 1.7 0 0 0-.3 1.9l.1.1v3.4l-.2.1a1.7 1.7 0 0 0-1 1.5 1.7 1.7 0 0 0 1 1.5l.2.1v3.4z" transform="translate(2 2) scale(.83)"/></svg>'
VIDEO_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="13" height="14" rx="2"/><path d="m16 10 5-3v10l-5-3"/><path d="m8 9 4 3-4 3z" fill="currentColor" stroke="none"/></svg>'
AUDIO_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>'


def svg_icon(svg, color, size=18):
    svg_bytes = QByteArray(svg.replace("currentColor", color).encode("utf-8"))
    renderer = QSvgRenderer(svg_bytes)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def svg_pixmap(svg, color, size=18):
    return svg_icon(svg, color, size).pixmap(size, size)


def _event_global_pos(event):
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()

def _exec_modal(dialog):
    if hasattr(dialog, "exec_"):
        return dialog.exec_()
    return dialog.exec()

def _exec_menu(menu, pos):
    if hasattr(menu, "exec_"):
        return menu.exec_(pos)
    return menu.exec(pos)

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

# Import bundled yt_dlp
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
    """Switch the download folder and refresh derived paths."""
    global SAVE_DIR, HISTORY_FILE, SESSION_FILE
    SAVE_DIR = path
    HISTORY_FILE = os.path.join(SAVE_DIR, "downloads.jsonl")
    SESSION_FILE = os.path.join(SAVE_DIR, "session.json")
    os.makedirs(SAVE_DIR, exist_ok=True)

DEFAULT_SETTINGS = {
    "download_dir": SAVE_DIR,
    "grid_columns": 4,          # 3..7 columns, 0 = List
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

    candidates = [
        os.path.join(base_path, "engine.exe"),
        os.path.join(base_path, "dist", "engine.exe"),
        os.path.join(base_path, "bin", "engine.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "engine.exe"),
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
    """Engine backend: module if yt_dlp is imported, or exe if engine.exe exists."""
    if HAS_YTDLP:
        return "module"
    if engine_exe_path():
        return "exe"
    return "none"

def get_ytdlp_version():
    """Return current engine status."""
    if HAS_YTDLP:
        try:
            return "module", f"Integrated (v{yt_dlp.version.__version__})"
        except Exception:
            return "module", "Integrated Engine"
    if engine_exe_path():
        return "exe", "Standalone Engine"
    return "none", "Unavailable"

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
    url = re.sub(r'[?&](list|index)=[^&#]*', '', url)
    url = re.sub(r'&{2,}', '&', url).rstrip('&?')
    return url

def is_playlist_url(url):
    """Detect playlist URLs so they are rejected early."""
    u = url.strip().lower()
    if 'youtube.com/playlist' in u:
        return True
    has_list = re.search(r'[?&]list=[a-zA-Z0-9_-]+', u) is not None
    has_video = (re.search(r'(^|[?&])v=[a-zA-Z0-9_-]+', u) is not None
                 or 'youtu.be/' in u
                 or 'youtube.com/shorts/' in u)
    return has_list and not has_video

def clean_filename(title):
    """Sanitize title string for valid filenames."""
    if not title:
        return f"video_{int(time.time())}"
    clean = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    return clean[:70] if clean else f"video_{int(time.time())}"


class SettingsDialog(QDialog):
    """Clean, stable settings dialog with native drag support (No emojis)."""
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self._settings = dict(settings)
        self.setFixedWidth(520)
        self._drag_pos = None

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        self.root = QFrame(self)
        self.root.setObjectName("SettingsRoot")
        main_lay.addWidget(self.root)

        root_lay = QVBoxLayout(self.root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Header (Draggable)
        self.header = QFrame()
        self.header.setObjectName("SettingsHeader")
        hlay = QHBoxLayout(self.header)
        hlay.setContentsMargins(20, 14, 16, 14)

        title = QLabel("Settings")
        title.setObjectName("SettingsTitle")
        hlay.addWidget(title)
        hlay.addStretch()

        close_btn = QPushButton("x")
        close_btn.setObjectName("SettingsCloseBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        hlay.addWidget(close_btn)
        root_lay.addWidget(self.header)

        # Body
        body = QWidget()
        blay = QVBoxLayout(body)
        blay.setContentsMargins(24, 20, 24, 24)
        blay.setSpacing(18)

        # Download folder
        dir_lbl = QLabel("Download Location")
        dir_lbl.setObjectName("SettingsLabel")
        blay.addWidget(dir_lbl)

        dir_box = QHBoxLayout()
        dir_box.setSpacing(8)
        self.dir_value = QLabel(self._settings.get("download_dir", SAVE_DIR))
        self.dir_value.setObjectName("SettingsValue")
        self.dir_value.setWordWrap(True)
        choose_btn = QPushButton("Browse")
        choose_btn.setObjectName("SettingsActionBtn")
        choose_btn.setCursor(Qt.PointingHandCursor)
        choose_btn.clicked.connect(self.choose_folder)
        dir_box.addWidget(self.dir_value, 1)
        dir_box.addWidget(choose_btn)
        blay.addLayout(dir_box)

        # Grid mode
        grid_row = QHBoxLayout()
        grid_lbl = QLabel("Grid Columns")
        grid_lbl.setObjectName("SettingsLabel")
        grid_lbl.setFixedWidth(160)
        self.grid_combo = QComboBox()
        self.grid_combo.addItems(["3 Columns", "4 Columns", "5 Columns", "6 Columns", "7 Columns", "List View"])
        gc = int(self._settings.get("grid_columns", 4))
        self.grid_combo.setCurrentIndex(gc - 3 if gc >= 3 else 5)
        grid_row.addWidget(grid_lbl)
        grid_row.addWidget(self.grid_combo, 1)
        blay.addLayout(grid_row)

        # Engine Status
        eng_row = QHBoxLayout()
        eng_lbl = QLabel("Engine Mode")
        eng_lbl.setObjectName("SettingsLabel")
        eng_lbl.setFixedWidth(160)
        _, ver_str = get_ytdlp_version()
        eng_val = QLabel(ver_str)
        eng_val.setObjectName("SettingsValue")
        eng_row.addWidget(eng_lbl)
        eng_row.addWidget(eng_val, 1)
        blay.addLayout(eng_row)

        # Checkboxes for Automation
        self.cb_retry = QCheckBox("Auto retry download on network error")
        self.cb_retry.setChecked(bool(self._settings.get("auto_retry")))
        blay.addWidget(self.cb_retry)

        self.cb_resume = QCheckBox("Auto resume partial downloads")
        self.cb_resume.setChecked(bool(self._settings.get("auto_resume")))
        blay.addWidget(self.cb_resume)

        self.cb_scroll = QCheckBox("Auto scroll to new download")
        self.cb_scroll.setChecked(bool(self._settings.get("auto_scroll_top")))
        blay.addWidget(self.cb_scroll)

        # Open mode
        open_row = QHBoxLayout()
        open_lbl = QLabel("Open Media With")
        open_lbl.setObjectName("SettingsLabel")
        open_lbl.setFixedWidth(160)
        open_row.addWidget(open_lbl)
        self.btn_single = QPushButton("Single Click")
        self.btn_single.setObjectName("ChoiceBtn")
        self.btn_single.setCheckable(True)
        self.btn_double = QPushButton("Double Click")
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

        blay.addSpacing(10)

        # Footer Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SettingsCancelBtn")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("SettingsSaveBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        blay.addLayout(btn_row)

        root_lay.addWidget(body, 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = _event_global_pos(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            gpos = _event_global_pos(event)
            self.move(self.pos() + gpos - self._drag_pos)
            self._drag_pos = gpos

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
        s["auto_retry"] = self.cb_retry.isChecked()
        s["auto_resume"] = self.cb_resume.isChecked()
        s["auto_scroll_top"] = self.cb_scroll.isChecked()
        s["open_mode"] = "double" if self.btn_double.isChecked() else "single"
        return s

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._smart_center)

    def _smart_center(self):
        pw = self.parent() if self.parent() else self
        screen = pw.screen() if hasattr(pw, 'screen') and pw.screen() else QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            pw_geo = pw.geometry()
            x = pw_geo.x() + (pw_geo.width() - self.width()) // 2
            y = pw_geo.y() + (pw_geo.height() - self.height()) // 2
            x = max(avail.left() + 8, min(x, avail.right() - self.width() - 8))
            y = max(avail.top() + 8, min(y, avail.bottom() - self.height() - 8))
            self.move(x, y)


class MediaExtractorWorker(QThread):
    """Worker thread for media extraction with built-in or standalone engine."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, target_url, preferred_quality="Best Quality"):
        super().__init__()
        self.target_url = normalize_video_url(target_url)
        self.preferred_quality = preferred_quality
        self._is_running = True

    def run(self):
        try:
            data = None
            if HAS_YTDLP:
                data = self.try_ytdlp_extraction()
            elif engine_exe_path():
                data = self._extract_via_exe()
            else:
                raise Exception("Media downloader engine not ready. Please try again.")

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
                extractor = info.get("extractor_key") or info.get("extractor") or "Video"

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
            if engine_exe_path():
                return self._extract_via_exe()
            raise Exception(f"Extraction Error: {str(e)[:70]}")

    def _extract_via_exe(self):
        exe = find_standalone_ytdlp()
        if not exe:
            raise Exception("Engine not found")
        out = subprocess.run(
            [exe, "--no-warnings", "--skip-download", "--no-playlist", "-J", self.target_url],
            capture_output=True, text=True, timeout=180,
            creationflags=_no_window_flags())
        if out.returncode != 0:
            raise Exception(f"Extraction Error: {(out.stderr or out.stdout).strip()[:100]}")
        info = json.loads(out.stdout)

        title = info.get("title") or "Untitled Media"
        thumb = info.get("thumbnail") or ""
        dur = info.get("duration")
        extractor = info.get("extractor_key") or info.get("extractor") or "Video"

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
    """Downloads video stream or runs engine with live progress hooks."""
    progress = Signal(int, str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, media_info, save_path, resume=False):
        super().__init__()
        self.media_info = media_info
        self.save_path = save_path
        self._resume = resume
        self._is_cancelled = False
        self._proc = None

    def run(self):
        try:
            if HAS_YTDLP:
                self.download_via_ytdlp()
            elif engine_exe_path():
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
                self.download_via_exe(format_spec)
            else:
                raise Exception("Media downloader engine not ready. Please try again.")

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

        def progress_hook(d):
            if self._is_cancelled:
                raise Exception("Download cancelled")

            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed') or 0
                if speed >= 1024 * 1024:
                    speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                else:
                    speed_str = f"{speed / 1024:.0f} KB/s"

                percent = int((downloaded / total) * 100) if total > 0 else 50
                self.progress.emit(min(99, percent), speed_str)
            elif d.get('status') == 'finished':
                self.progress.emit(100, "Processing...")

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
        exe = find_standalone_ytdlp()
        base_path, _ = os.path.splitext(self.save_path)
        out_tmpl = f"{base_path}.%(ext)s"

        cmd = [exe, "--no-warnings", "--newline", "--progress", "--no-playlist",
               "-f", format_spec, "-o", out_tmpl,
               "--merge-output-format", "mp4", "--continue",
               "--retries", "3", self.media_info["original_url"]]

        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, encoding="utf-8", errors="replace",
                                      creationflags=_no_window_flags())
        speed_str = ""
        for raw in self._proc.stdout:
            line = raw.strip()
            m = re.search(r'\[download\]\s+([\d.]+)%', line)
            if m:
                sp = re.search(r'at\s+([\d.]+)([KM]i?B)/s', line)
                if sp:
                    n = float(sp.group(1))
                    unit = sp.group(2).upper()
                    speed_str = f"{n:.1f} MB/s" if "M" in unit else f"{n:.0f} KB/s"
                self.progress.emit(min(99, int(float(m.group(1)))), speed_str)
            if self._is_cancelled:
                try: self._proc.terminate()
                except Exception: pass
                break
        self._proc.wait()

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

        if self._proc.returncode != 0 and not os.path.exists(actual_path):
            raise Exception("Download failed")

        self.progress.emit(100, "Done")
        self.finished.emit({
            "path": actual_path,
            "size_bytes": os.path.getsize(actual_path) if os.path.exists(actual_path) else 0
        })

    def cancel(self):
        self._is_cancelled = True
        if self._proc:
            try: self._proc.terminate()
            except Exception: pass


class ThumbnailLoaderThread(QThread):
    """Background loader for rendering thumbnail images without freezing UI."""
    image_loaded = Signal(object, QImage)

    def __init__(self):
        super().__init__()
        self.queue = []
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._is_running = True

    def add_task(self, card):
        with self._condition:
            self.queue.append(card)
            self._condition.notify()
            should_start = not self.isRunning()
        if should_start:
            self.start()

    def add_tasks(self, cards):
        with self._condition:
            self.queue.extend(cards)
            if cards:
                self._condition.notify()
            should_start = bool(cards) and not self.isRunning()
        if should_start:
            self.start()

    def run(self):
        while True:
            with self._condition:
                while not self.queue and self._is_running:
                    self._condition.wait()
                if not self._is_running:
                    return
                card = self.queue.pop(0)

            thumb_source = card.thumbnail_path_or_url
            img = QImage()
            if thumb_source and thumb_source.startswith("http"):
                stem = clean_filename(card.title)
                cache_path = os.path.join(SAVE_DIR, f"thumb_{stem}.jpg")
                if os.path.exists(cache_path):
                    img.load(cache_path)
                else:
                    try:
                        resp = requests.get(thumb_source, timeout=8, headers={
                            "User-Agent": "Mozilla/5.0"
                        })
                        if resp.status_code == 200:
                            img.loadFromData(resp.content)
                            try:
                                with open(cache_path, "wb") as f:
                                    f.write(resp.content)
                                card.thumbnail_path_or_url = cache_path
                            except: pass
                    except: pass
            elif thumb_source and os.path.exists(thumb_source):
                img.load(thumb_source)

            # Generate cover frame if no thumbnail exists
            if img.isNull() and card.file_path and os.path.exists(card.file_path):
                stem = os.path.splitext(os.path.basename(card.file_path))[0]
                cover_path = os.path.join(SAVE_DIR, f"cover_{stem}.jpg")
                if os.path.exists(cover_path):
                    img.load(cover_path)
                else:
                    ffmpeg_bin = shutil.which("ffmpeg")
                    if ffmpeg_bin:
                        try:
                            subprocess.run(
                                [ffmpeg_bin, "-y", "-ss", "00:00:03", "-i", card.file_path,
                                 "-vframes", "1", "-q:v", "3", cover_path],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=10,
                                creationflags=_no_window_flags())
                            if os.path.exists(cover_path):
                                img.load(cover_path)
                                card.thumbnail_path_or_url = cover_path
                        except: pass

            if self._is_running:
                self.image_loaded.emit(card, img)

    def stop(self):
        with self._condition:
            self._is_running = False
            self.queue.clear()
            self._condition.notify_all()

    def clear_queue(self):
        with self._condition:
            self.queue.clear()


class CustomTitleBar(QFrame):
    """Clean desktop title bar (No emojis, no AI tags)."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(40)
        self.setObjectName("TitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)
        icon_path = get_asset_path("icon.ico")
        if os.path.exists(icon_path):
            self.icon_label.setPixmap(QIcon(icon_path).pixmap(16, 16))
        layout.addWidget(self.icon_label)

        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("AppTitle")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.btn_min = QPushButton("-")
        self.btn_min.setFixedSize(28, 24)
        self.btn_min.setObjectName("WindowCtrlBtn")
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.clicked.connect(self.parent.showMinimized)

        self.btn_max = QPushButton("[]")
        self.btn_max.setFixedSize(28, 24)
        self.btn_max.setObjectName("WindowCtrlBtn")
        self.btn_max.setCursor(Qt.PointingHandCursor)
        self.btn_max.clicked.connect(self.parent.toggle_max_normal)

        self.btn_close = QPushButton("x")
        self.btn_close.setFixedSize(28, 24)
        self.btn_close.setObjectName("WindowCloseBtn")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.parent.close)

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.parent.dragPos = _event_global_pos(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            gpos = _event_global_pos(event)
            self.parent.move(self.parent.pos() + gpos - self.parent.dragPos)
            self.parent.dragPos = gpos


class URLArea(QTextEdit):
    """Input text area for video URLs with Enter submit."""
    submitted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Paste video link here (YouTube, Instagram, Facebook)...")
        self.setFixedHeight(36)
        self.setObjectName("URLInput")

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.submitted.emit()
        else:
            super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        if source.hasText():
            self.insertPlainText(source.text().strip())
        else:
            super().insertFromMimeData(source)


class ShimmerLabel(QLabel):
    """Animated loading placeholder used while media details and art are fetched."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._shimmer_active = False
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._advance_shimmer)

    def set_shimmer_active(self, active):
        self._shimmer_active = active
        if active:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _advance_shimmer(self):
        self._phase = (self._phase + 18) % max(1, self.width() * 2)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._shimmer_active:
            return
        painter = QPainter(self)
        gradient = QLinearGradient(-self.width() + self._phase, 0, self._phase, 0)
        gradient.setColorAt(0.0, QColor("#111a29"))
        gradient.setColorAt(0.45, QColor("#273c59"))
        gradient.setColorAt(0.55, QColor("#dce8f7"))
        gradient.setColorAt(1.0, QColor("#111a29"))
        painter.fillRect(self.rect(), gradient)
        painter.end()


class VideoCard(QFrame):
    """Clean media card (16:9, responsive, sharp border, no emoji, no AI)."""
    request_play = Signal(object)
    request_delete = Signal(object)
    request_retry = Signal(object, bool)

    def __init__(self, data, initial_width=260):
        super().__init__()
        self.data = data
        self.thumbnail_path_or_url = data.get("thumbnail", "")
        self.title = data.get("title", "Untitled")
        self.source = str(data.get("source", "Video")).upper()
        self.duration = data.get("duration")
        self.file_path = data.get("path", "")
        self.video_url = data.get("url", "")
        self.pixmap = None
        self.target_width = initial_width
        self.ratio = 16 / 9
        self._downloading = False
        self._is_skeleton = bool(data.get("is_skeleton"))
        self.play_mode = "single"
        self._retry_count = 0

        self.setObjectName("VideoCard")
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 16:9 Thumbnail
        self.media_container = QFrame()
        self.media_container.setObjectName("MediaContainer")
        media_layout = QVBoxLayout(self.media_container)
        media_layout.setContentsMargins(0, 0, 0, 0)
        media_layout.setSpacing(0)

        self.thumb_label = ShimmerLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setObjectName("ThumbLabel")
        self.thumb_label.set_shimmer_active(self._is_skeleton)
        media_layout.addWidget(self.thumb_label)

        self.media_icon = QLabel(self.media_container)
        self.media_icon.setAlignment(Qt.AlignCenter)
        self.media_icon.setFixedSize(36, 36)
        self.media_icon.hide()

        # Source badge
        self.source_badge = QLabel(self.source, self.media_container)
        self.source_badge.setObjectName("SourceBadge")
        self.source_badge.move(8, 8)

        # Duration badge
        if self.duration:
            dur_str = self.format_duration(self.duration)
            self.dur_badge = QLabel(dur_str, self.media_container)
            self.dur_badge.setObjectName("DurationBadge")
        else:
            self.dur_badge = None

        self.download_overlay = QFrame(self.media_container)
        self.download_overlay.setObjectName("DownloadOverlay")
        self.download_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        overlay_layout = QVBoxLayout(self.download_overlay)
        overlay_layout.setContentsMargins(10, 8, 10, 8)
        overlay_layout.addStretch(1)
        self.download_percent = QLabel("0%")
        self.download_percent.setObjectName("DownloadPercent")
        self.download_percent.setAlignment(Qt.AlignCenter)
        overlay_layout.addWidget(self.download_percent)
        overlay_layout.addStretch(1)
        self.download_track = QProgressBar()
        self.download_track.setObjectName("DownloadTrack")
        self.download_track.setRange(0, 100)
        self.download_track.setValue(0)
        self.download_track.setTextVisible(False)
        self.download_track.setFixedHeight(5)
        overlay_layout.addWidget(self.download_track)
        self.download_overlay.hide()

        layout.addWidget(self.media_container)

        # Metadata info
        self.info_strip = QFrame()
        self.info_strip.setObjectName("CardInfoStrip")
        info_layout = QVBoxLayout(self.info_strip)
        info_layout.setContentsMargins(10, 8, 10, 10)
        info_layout.setSpacing(4)

        self.title_lbl = QLabel(self.title)
        self.title_lbl.setObjectName("CardTitle")
        self.title_lbl.setWordWrap(True)
        info_layout.addWidget(self.title_lbl)
        self.title_skeleton = ShimmerLabel()
        self.title_skeleton.setFixedHeight(12)
        self.title_skeleton.setObjectName("TitleSkeleton")
        self.title_skeleton.set_shimmer_active(self._is_skeleton)
        info_layout.addWidget(self.title_skeleton)
        self.title_lbl.setVisible(not self._is_skeleton)
        self.title_skeleton.setVisible(self._is_skeleton)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(6)

        is_audio = self.data.get("chosen_media", {}).get("extension") == "mp3" or self.file_path.endswith(".mp3")
        self.format_icon = QLabel()
        self.format_icon.setObjectName("FormatIcon")
        self.format_icon.setFixedSize(14, 14)
        self.format_icon.setPixmap(svg_pixmap(
            AUDIO_SVG if is_audio else VIDEO_SVG,
            "#ffb0a7" if is_audio else "#a9d3ff", 14
        ))
        status_row.addWidget(self.format_icon)
        self.format_tag = QLabel("MP3 Audio" if is_audio else "MP4 Video")
        self.format_tag.setObjectName("FormatTag")
        status_row.addWidget(self.format_tag)

        status_text = "Fetching details..." if self._is_skeleton else (
            "Ready" if self.file_path and os.path.exists(self.file_path) else "Queued"
        )
        self.status_lbl = QLabel(status_text)
        self.status_lbl.setObjectName("CardStatus")
        status_row.addWidget(self.status_lbl, 1)

        info_layout.addLayout(status_row)
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
        if self.target_width == new_width:
            return
        self.target_width = new_width
        self.setFixedWidth(self.target_width)
        self.apply_ratio_size()

    def apply_ratio_size(self):
        target_h = int(self.target_width / self.ratio)
        self.media_container.setFixedHeight(target_h)
        self.download_overlay.setGeometry(0, 0, self.target_width, target_h)
        self.media_icon.move((self.target_width - self.media_icon.width()) // 2,
                             (target_h - self.media_icon.height()) // 2)
        if self.dur_badge:
            self.dur_badge.move(self.target_width - self.dur_badge.sizeHint().width() - 8, target_h - 24)
        self.update_thumb()

    def update_thumb(self):
        w = self.media_container.width()
        h = self.media_container.height()
        if w <= 0 or h <= 0:
            return
        if self.pixmap is None or self.pixmap.isNull():
            self.thumb_label.clear()
            return
        p = self.pixmap
        scale = max(w / p.width(), h / p.height())
        sw, sh = max(1, int(p.width() * scale)), max(1, int(p.height() * scale))
        big = p.scaled(sw, sh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x, y = max(0, (sw - w) // 2), max(0, (sh - h) // 2)
        self.thumb_label.setPixmap(big.copy(x, y, min(w, sw), min(h, sh)))

    def set_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.thumb_label.set_shimmer_active(False)
        self.media_icon.hide()
        self.apply_ratio_size()
        self.update()

    def set_thumbnail_fallback(self):
        self.thumb_label.set_shimmer_active(False)
        self.thumb_label.clear()
        is_audio = (
            self.data.get("chosen_media", {}).get("extension") == "mp3"
            or self.file_path.endswith(".mp3")
        )
        self.media_icon.setPixmap(svg_pixmap(
            AUDIO_SVG if is_audio else VIDEO_SVG,
            "#ffb0a7" if is_audio else "#a9d3ff", 28
        ))
        self.media_icon.show()
        self.media_icon.raise_()

    def set_media_data(self, data):
        self.data = data
        self._is_skeleton = False
        self.title = data.get("title", "Untitled")
        self.source = str(data.get("source", "Video")).upper()
        self.duration = data.get("duration")
        self.file_path = data.get("path", "")
        self.video_url = data.get("url", "")
        self.thumbnail_path_or_url = data.get("thumbnail", "")
        self.pixmap = None

        self.source_badge.setText(self.source)
        self.title_lbl.setText(self.title)
        self.title_lbl.show()
        self.title_skeleton.set_shimmer_active(False)
        self.title_skeleton.hide()

        is_audio = data.get("chosen_media", {}).get("extension") == "mp3"
        self.format_icon.setPixmap(svg_pixmap(
            AUDIO_SVG if is_audio else VIDEO_SVG,
            "#ffb0a7" if is_audio else "#a9d3ff", 14
        ))
        self.format_tag.setText("MP3 Audio" if is_audio else "MP4 Video")
        self.status_lbl.setText("Queued")
        self.status_lbl.setStyleSheet("")
        self.download_overlay.hide()

        if self.duration:
            duration_text = self.format_duration(self.duration)
            if self.dur_badge is None:
                self.dur_badge = QLabel(duration_text, self.media_container)
                self.dur_badge.setObjectName("DurationBadge")
            else:
                self.dur_badge.setText(duration_text)
            self.dur_badge.show()
        elif self.dur_badge:
            self.dur_badge.hide()

        self.thumb_label.clear()
        self.thumb_label.set_shimmer_active(bool(self.thumbnail_path_or_url))
        if not self.thumbnail_path_or_url:
            self.set_thumbnail_fallback()
        self.apply_ratio_size()

    def set_progress(self, percent, speed_text):
        self.download_percent.setText(f"{percent}%")
        self.download_track.setValue(percent)
        self.download_overlay.show()
        self.download_overlay.raise_()
        self.status_lbl.setText(f"{percent}% ({speed_text})")
        self.status_lbl.setStyleSheet("color: #dce8f7; font-weight: 600;")

    def set_completed(self, path):
        self.file_path = path
        self.data["path"] = path
        self.download_overlay.hide()
        self.status_lbl.setText("Downloaded")
        self.status_lbl.setStyleSheet("color: #acd1ff; font-weight: 600;")

    def set_error(self, err_text):
        self.download_overlay.hide()
        self.status_lbl.setText(f"Error: {err_text[:25]}")
        self.status_lbl.setStyleSheet("color: #ff4d4d; font-weight: 600;")

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
                background-color: #1f1f1f;
                color: #f1f1f1;
                border: 1px solid #333333;
                padding: 6px;
                border-radius: 6px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
                font-size: 12px;
            }
            QMenu::item:selected {
                background-color: #536bc5;
                color: #ffffff;
            }
        """)

        play_act = QAction("Play Media", self)
        play_act.triggered.connect(lambda: self.request_play.emit(self))
        menu.addAction(play_act)

        if not self.is_downloaded and not self._downloading:
            retry_act = QAction("Retry Download", self)
            retry_act.triggered.connect(lambda: self.request_retry.emit(self, False))
            menu.addAction(retry_act)

        target = self.file_path or (self.data.get("path") if hasattr(self, "data") else None)
        if target and os.path.exists(target):
            folder_act = QAction("Open Containing Folder", self)
            def _open_folder():
                try:
                    if sys.platform == "win32":
                        subprocess.run(
                            f'explorer /select,"{os.path.normpath(target)}"',
                            creationflags=_no_window_flags())
                    else:
                        subprocess.run(["xdg-open", os.path.dirname(target)])
                except Exception as e:
                    self.status_lbl.setText(f"Folder error: {e}")
            folder_act.triggered.connect(_open_folder)
            menu.addAction(folder_act)

        if self.video_url:
            copy_act = QAction("Copy Link", self)
            def _copy():
                try:
                    QApplication.clipboard().setText(self.video_url)
                    self.status_lbl.setText("Link copied")
                    QTimer.singleShot(2000, lambda: self.status_lbl.setText(
                        "Downloaded" if self.is_downloaded else "Ready"
                    ))
                except Exception:
                    self.status_lbl.setText("Copy failed")
            copy_act.triggered.connect(_copy)
            menu.addAction(copy_act)

        del_act = QAction("Delete from Library", self)
        del_act.triggered.connect(lambda: self.request_delete.emit(self))
        menu.addAction(del_act)

        _exec_menu(menu, self.mapToGlobal(pos))


class DownloadFreeApp(QMainWindow):
    """Clean, robust desktop media downloader."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1000, 650)
        self.setMinimumSize(800, 540)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

        self.settings = load_settings()
        self.grid_columns = int(self.settings.get("grid_columns", 4))

        self.dragPos = QPoint()
        self.all_cards = []
        self.active_workers = []
        self.download_workers = []
        self._mode = "video"
        self._current_filter = "all"
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(600)
        self._preview_timer.timeout.connect(self.preview_input_url)
        self._preview_worker = None
        self._preview_card = None
        self._preview_url = ""
        self._download_after_preview = False
        self._layout_refresh_timer = QTimer(self)
        self._layout_refresh_timer.setSingleShot(True)
        self._layout_refresh_timer.timeout.connect(self.relayout_grid)

        self.thumb_loader = ThumbnailLoaderThread()
        self.thumb_loader.image_loaded.connect(self.on_thumbnail_loaded)

        self.setup_ui()
        self.apply_theme()
        self.load_history()
        self._layout_refresh_timer.start()

    def setup_ui(self):
        central = QWidget()
        central.setObjectName("Central")
        self.setCentralWidget(central)

        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Title bar
        self.title_bar = CustomTitleBar(self)
        self.main_layout.addWidget(self.title_bar)

        # Download controls.
        self.download_bar = QFrame()
        self.download_bar.setObjectName("DownloadBar")
        bar_lay = QHBoxLayout(self.download_bar)
        bar_lay.setContentsMargins(18, 10, 18, 10)
        bar_lay.setSpacing(8)

        self.btn_settings = QPushButton()
        self.btn_settings.setObjectName("TitleSettingsBtn")
        self.btn_settings.setIcon(svg_icon(SETTINGS_SVG, "#dce9ff", 18))
        self.btn_settings.setIconSize(QSize(18, 18))
        self.btn_settings.setFixedSize(40, 36)
        self.btn_settings.setToolTip("Settings")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.open_settings)
        bar_lay.addWidget(self.btn_settings)

        self.input_area = URLArea()
        self.input_area.submitted.connect(self.start_download)
        self.input_area.textChanged.connect(self.on_url_input_changed)
        bar_lay.addWidget(self.input_area, 1)

        self.btn_video = QPushButton()
        self.btn_video.setObjectName("FormatBtn")
        self.btn_video.setProperty("formatType", "video")
        self.btn_video.setIcon(svg_icon(VIDEO_SVG, "#b7d8ff", 17))
        self.btn_video.setIconSize(QSize(17, 17))
        self.btn_video.setCheckable(True)
        self.btn_video.setChecked(True)
        self.btn_video.setFixedSize(40, 36)
        self.btn_video.setToolTip("Video (MP4)")
        self.btn_video.setCursor(Qt.PointingHandCursor)
        self.btn_video.clicked.connect(lambda: self.choose_video())
        bar_lay.addWidget(self.btn_video)

        self.btn_audio = QPushButton()
        self.btn_audio.setObjectName("FormatBtn")
        self.btn_audio.setProperty("formatType", "audio")
        self.btn_audio.setIcon(svg_icon(AUDIO_SVG, "#ffc0b8", 17))
        self.btn_audio.setIconSize(QSize(17, 17))
        self.btn_audio.setCheckable(True)
        self.btn_audio.setFixedSize(40, 36)
        self.btn_audio.setToolTip("Audio (MP3)")
        self.btn_audio.setCursor(Qt.PointingHandCursor)
        self.btn_audio.clicked.connect(lambda: self.choose_audio())
        bar_lay.addWidget(self.btn_audio)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "Best Quality", "1080p", "720p", "480p", "360p", "Audio (MP3)"
        ])
        self.quality_combo.setFixedWidth(130)
        self.quality_combo.setFixedHeight(36)
        bar_lay.addWidget(self.quality_combo)

        self.btn_download = QPushButton("Download")
        self.btn_download.setObjectName("DownloadBtn")
        self.btn_download.setFixedWidth(110)
        self.btn_download.setFixedHeight(36)
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.clicked.connect(self.start_download)
        bar_lay.addWidget(self.btn_download)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("StopBtn")
        self.btn_stop.setFixedWidth(70)
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_extraction)
        self.btn_stop.hide()
        bar_lay.addWidget(self.btn_stop)

        self.main_layout.addWidget(self.download_bar)

        # Library is populated only from downloaded media.
        self.sec_header = QFrame()
        self.sec_header.setObjectName("SectionHeader")
        sec_lay = QHBoxLayout(self.sec_header)
        sec_lay.setContentsMargins(18, 8, 18, 8)
        sec_lay.setSpacing(10)

        self.sec_title = QLabel("Your Library")
        self.sec_title.setObjectName("SectionTitle")
        sec_lay.addWidget(self.sec_title)

        self.count_badge = QLabel("(0)")
        self.count_badge.setObjectName("CountBadge")
        sec_lay.addWidget(self.count_badge)

        sec_lay.addSpacing(16)

        # Filters
        self.filter_all = QPushButton("All")
        self.filter_all.setObjectName("FilterBtn")
        self.filter_all.setCheckable(True)
        self.filter_all.setChecked(True)
        self.filter_all.setCursor(Qt.PointingHandCursor)
        self.filter_all.clicked.connect(lambda: self.filter_library("all"))
        sec_lay.addWidget(self.filter_all)

        self.filter_vid = QPushButton("Videos")
        self.filter_vid.setObjectName("FilterBtn")
        self.filter_vid.setCheckable(True)
        self.filter_vid.setCursor(Qt.PointingHandCursor)
        self.filter_vid.clicked.connect(lambda: self.filter_library("video"))
        sec_lay.addWidget(self.filter_vid)

        self.filter_aud = QPushButton("Audio")
        self.filter_aud.setObjectName("FilterBtn")
        self.filter_aud.setCheckable(True)
        self.filter_aud.setCursor(Qt.PointingHandCursor)
        self.filter_aud.clicked.connect(lambda: self.filter_library("audio"))
        sec_lay.addWidget(self.filter_aud)

        sec_lay.addStretch()

        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_open_folder.setObjectName("FolderActionBtn")
        self.btn_open_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self.open_download_folder)
        sec_lay.addWidget(self.btn_open_folder)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.hide()
        sec_lay.addWidget(self.status_label)

        self.main_layout.addWidget(self.sec_header)

        # 4. Scroll Area with QGridLayout
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setObjectName("MainScroll")

        self.grid_widget = QWidget()
        self.grid_widget.setObjectName("GridWidget")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setContentsMargins(18, 6, 18, 24)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll.setWidget(self.grid_widget)
        self.main_layout.addWidget(self.scroll, 1)

        # Empty State
        self.empty_state = QWidget(self.scroll)
        self.empty_state.setObjectName("EmptyStateWidget")
        empty_lay = QVBoxLayout(self.empty_state)
        empty_lay.setAlignment(Qt.AlignCenter)
        empty_lay.setSpacing(8)

        empty_title = QLabel("Your library is empty")
        empty_title.setObjectName("EmptyTitle")
        empty_title.setAlignment(Qt.AlignCenter)

        empty_sub = QLabel("Paste any video or audio link above and click Download to save it.")
        empty_sub.setObjectName("EmptySub")
        empty_sub.setAlignment(Qt.AlignCenter)

        empty_lay.addWidget(empty_title)
        empty_lay.addWidget(empty_sub)
        self.empty_state.hide()

        # Resizer Grip
        self.grip = QSizeGrip(self)
        self.main_layout.addWidget(self.grip, 0, Qt.AlignRight | Qt.AlignBottom)

    def apply_theme(self):
        """Apply the midnight-blue downloader theme."""
        sheet = """
            #Central {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #14243a, stop:0.46 #090c11, stop:0.76 #101116, stop:1 #25151b);
                border-radius: 8px;
                border: 1px solid #2d3d53;
            }
            QMainWindow { background-color: transparent; }

            #TitleBar {
                background-color: #0c111b;
                border-bottom: 1px solid #28364b;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            #AppTitle {
                color: #edf2fb;
                font-size: 13px;
                font-weight: 600;
            }
            #TitleSettingsBtn {
                background-color: #172238;
                color: #d3e4fb;
                border: 1px solid #354a67;
                border-radius: 7px;
                font-size: 11px;
                font-weight: 600;
                padding: 0;
            }
            #TitleSettingsBtn:hover {
                color: #ffffff;
                background-color: #243755;
                border-color: #7d9ec6;
            }
            #WindowCtrlBtn {
                background-color: transparent;
                color: #9caac0;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }
            #WindowCtrlBtn:hover {
                background-color: #243148;
                color: #ffffff;
            }
            #WindowCloseBtn {
                background-color: transparent;
                color: #9caac0;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }
            #WindowCloseBtn:hover {
                background-color: #a9433d;
                color: #ffffff;
            }

            #DownloadBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #14243a, stop:0.52 #0b0f13, stop:1 #211519);
                border-bottom: 1px solid #293246;
            }
            #URLInput {
                background-color: rgba(18, 28, 44, 0.78);
                color: #edf2fb;
                border: 1px solid rgba(139, 173, 211, 0.35);
                border-radius: 7px;
                padding: 6px 12px;
                font-size: 13px;
            }
            #URLInput:focus {
                border-color: #8baed6;
                background-color: rgba(24, 39, 61, 0.92);
            }
            #URLInput QScrollBar:vertical,
            #URLInput QScrollBar:horizontal {
                width: 0px;
                height: 0px;
            }
            QScrollBar:vertical {
                background: #0b0f14;
                width: 6px;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #435879;
                border-radius: 3px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #7799c3;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }

            QScrollBar:horizontal {
                background: #0b0f14;
                height: 6px;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:horizontal {
                background: #435879;
                border-radius: 3px;
                min-width: 24px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #7799c3;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                background: none;
            }
            #FormatBtn {
                background-color: rgba(23, 33, 50, 0.72);
                color: #bac8dc;
                border: 1px solid rgba(130, 157, 189, 0.35);
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 0;
            }
            #FormatBtn:hover {
                color: #ffffff;
                border-color: #7d9ec6;
            }
            #FormatBtn:checked {
                background-color: #203653;
                color: #d8eaff;
                border: 1px solid #7295bc;
            }
            #FormatBtn[formatType="audio"]:checked {
                background-color: #3a211d;
                color: #ffd1c7;
                border-color: #d36a5e;
            }
            #DownloadBtn {
                background-color: #c85a4e;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                font-size: 13px;
            }
            #DownloadBtn:hover {
                background-color: #e0786c;
            }
            #DownloadBtn:disabled {
                background-color: #342522;
                color: #a8877e;
            }
            #StopBtn {
                background-color: #202838;
                color: #ffffff;
                border: 1px solid #465774;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            #StopBtn:hover {
                background-color: #a9433d;
                border-color: #d36a5e;
            }

            #SectionHeader {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #121f32, stop:0.52 #0c1016, stop:1 #1c1219);
                border-top: 1px solid #273246;
                border-bottom: 1px solid #273246;
            }
            #SectionTitle {
                color: #edf2fb;
                font-size: 14px;
                font-weight: 700;
            }
            #CountBadge {
                color: #9eacc2;
                font-size: 12px;
                font-weight: 600;
            }
            #FilterBtn {
                background: transparent;
                color: #9baac0;
                border: none;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
            }
            #FilterBtn:hover {
                color: #ffffff;
                background-color: #1e2c43;
            }
            #FilterBtn:checked {
                color: #ffffff;
                background-color: #2a3c58;
            }
            #FolderActionBtn {
                background-color: rgba(24, 34, 50, 0.78);
                color: #c2cee0;
                border: 1px solid rgba(130, 157, 189, 0.35);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
            }
            #FolderActionBtn:hover {
                color: #ffffff;
                border-color: #7799c3;
            }

            #MainScroll {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #111d2e, stop:0.55 #0a0d12, stop:1 #190f14);
            }
            #GridWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #111d2e, stop:0.55 #0a0d12, stop:1 #190f14);
            }

            #VideoCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(41, 58, 80, 0.58), stop:0.5 rgba(20, 27, 38, 0.68),
                    stop:1 rgba(49, 26, 34, 0.62));
                border: 1px solid rgba(163, 191, 224, 0.27);
                border-radius: 9px;
                overflow: hidden;
            }
            #VideoCard:hover {
                border-color: rgba(190, 218, 249, 0.62);
                background-color: rgba(44, 60, 82, 0.78);
            }
            #MediaContainer {
                background-color: rgba(9, 14, 23, 0.84);
                border-top-left-radius: 9px;
                border-top-right-radius: 9px;
            }
            #ThumbLabel {
                background-color: rgba(9, 14, 23, 0.84);
                border-top-left-radius: 9px;
                border-top-right-radius: 9px;
            }
            #SourceBadge {
                background-color: rgba(7, 11, 18, 0.7);
                color: #d7e3f2;
                font-size: 9px;
                font-weight: 700;
                padding: 2px 5px;
                border-radius: 3px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            #DurationBadge {
                background-color: rgba(7, 11, 18, 0.78);
                color: #ffffff;
                font-size: 9px;
                font-weight: 600;
                padding: 2px 6px;
                border-radius: 3px;
            }
            #CardInfoStrip {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(29, 42, 59, 0.72), stop:0.65 rgba(18, 25, 36, 0.58),
                    stop:1 rgba(43, 26, 34, 0.62));
            }
            #CardTitle {
                color: #edf2fb;
                font-size: 12px;
                font-weight: 600;
                line-height: 1.35;
            }
            #TitleSkeleton {
                background-color: #172131;
                border-radius: 4px;
            }
            #DownloadOverlay {
                background-color: rgba(3, 7, 13, 0.54);
                border-radius: 8px;
            }
            #DownloadPercent {
                color: #ffffff;
                background: transparent;
                font-size: 24px;
                font-weight: 700;
            }
            #DownloadTrack {
                background-color: rgba(225, 235, 248, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.7);
                border-radius: 3px;
            }
            #DownloadTrack::chunk {
                background-color: #ffffff;
                border-radius: 2px;
            }
            #FormatTag {
                color: #a9b8ce;
                font-size: 10px;
                font-weight: 600;
            }
            #FormatIcon {
                background: transparent;
            }
            #CardStatus {
                color: #acd1ff;
                font-size: 10px;
                font-weight: 600;
            }

            #EmptyTitle {
                color: #edf2fb;
                font-size: 15px;
                font-weight: 600;
            }
            #EmptySub {
                color: #9eacc2;
                font-size: 13px;
            }

            #SettingsRoot {
                background-color: #121b2c;
                border: 1px solid #394a64;
                border-radius: 6px;
            }
            #SettingsHeader {
                background-color: #0c111b;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border-bottom: 1px solid #29374a;
            }
            #SettingsTitle {
                color: #edf2fb;
                font-size: 14px;
                font-weight: 600;
            }
            #SettingsCloseBtn {
                background: transparent;
                color: #9eacc2;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }
            #SettingsCloseBtn:hover {
                background-color: #a9433d;
                color: #ffffff;
            }
            #SettingsLabel {
                color: #c7d4e5;
                font-size: 12px;
                font-weight: 600;
            }
            #SettingsValue {
                color: #edf2fb;
                font-size: 11px;
                padding: 6px 10px;
                background-color: #0c121d;
                border: 1px solid #30415b;
                border-radius: 4px;
            }
            #SettingsActionBtn {
                background-color: #202a3a;
                color: #ffffff;
                border: 1px solid #465774;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 6px 14px;
            }
            #SettingsActionBtn:hover {
                background-color: #2b3b53;
                border-color: #7799c3;
            }
            #SettingsCancelBtn {
                background-color: transparent;
                color: #aab8ca;
                border: 1px solid #3b4c65;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 6px 16px;
            }
            #SettingsCancelBtn:hover {
                color: #ffffff;
                background-color: #202a3a;
            }
            #SettingsSaveBtn {
                background-color: #c85a4e;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 700;
                padding: 6px 20px;
            }
            #SettingsSaveBtn:hover {
                background-color: #e0786c;
            }

            QCheckBox {
                color: #c7d4e5;
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #0c121d;
                border: 1px solid #465774;
                border-radius: 3px;
            }
            QCheckBox::indicator:hover {
                border-color: #8baed6;
            }
            QCheckBox::indicator:checked {
                background-color: #6f94be;
                border-color: #6f94be;
            }

            #ChoiceBtn {
                background-color: #0c121d;
                color: #aab8ca;
                border: 1px solid #30415b;
                border-radius: 4px;
                font-weight: 600;
                font-size: 11px;
                padding: 5px 14px;
            }
            #ChoiceBtn:hover {
                color: #ffffff;
                border-color: #7799c3;
            }
            #ChoiceBtn:checked {
                background-color: #203653;
                color: #d8eaff;
                border-color: #7295bc;
            }

            QComboBox {
                background-color: #111a29;
                color: #edf2fb;
                border: 1px solid #34445d;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QComboBox:hover { border-color: #7799c3; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #a9bdd5;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #111a29;
                color: #ffffff;
                selection-background-color: #536e91;
                selection-color: #ffffff;
                border: 1px solid #3a4b64;
                outline: 0px;
                padding: 4px;
            }

            #StatusLabel {
                font-size: 11px;
                font-weight: 600;
                border-radius: 4px;
                padding: 3px 8px;
            }
        """
        qapp = QApplication.instance()
        if qapp is not None:
            qapp.setStyleSheet(sheet)
        else:
            self.setStyleSheet(sheet)

    def filter_library(self, mode):
        self._current_filter = mode
        self.filter_all.setChecked(mode == "all")
        self.filter_vid.setChecked(mode == "video")
        self.filter_aud.setChecked(mode == "audio")

        visible_count = 0
        for card in self.all_cards:
            is_audio = card.data.get("chosen_media", {}).get("extension") == "mp3" or card.file_path.endswith(".mp3")
            show = True
            if mode == "video" and is_audio:
                show = False
            elif mode == "audio" and not is_audio:
                show = False

            card.setVisible(show)
            if show:
                visible_count += 1

        self.count_badge.setText(f"({visible_count})")
        self.relayout_grid()

    def _num_cols_for_width(self, width):
        gc = getattr(self, 'grid_columns', 4)
        if not gc:
            return 1
        max_cols = max(1, (width - 40 + 14) // (180 + 14))
        return min(gc, max_cols)

    def relayout_grid(self):
        # Determine viewport width reliably
        view_w = self.scroll.viewport().width()
        if view_w <= 100:
            view_w = max(600, self.width() - 40)

        num_cols = self._num_cols_for_width(view_w)

        # Detach items from layout without destroying widgets
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        visible_cards = []
        for card in self.all_cards:
            is_audio = (
                card.data.get("chosen_media", {}).get("extension") == "mp3"
                or card.file_path.endswith(".mp3")
            )
            show = (
                self._current_filter == "all"
                or (self._current_filter == "audio" and is_audio)
                or (self._current_filter == "video" and not is_audio)
            )
            card.setVisible(show)
            if show:
                visible_cards.append(card)
        if not visible_cards:
            self.empty_state.show()
            self._position_empty_state()
            return
        self.empty_state.hide()

        available_w = max(400, view_w - 40 - (num_cols - 1) * 14)
        card_w = max(180, available_w // num_cols)

        for idx, card in enumerate(visible_cards):
            card.update_width(card_w)
            row = idx // num_cols
            col = idx % num_cols
            self.grid_layout.addWidget(card, row, col, Qt.AlignTop)

    def _position_empty_state(self):
        if hasattr(self, 'empty_state') and self.empty_state.isVisible():
            sw = self.scroll.viewport().width()
            sh = self.scroll.viewport().height()
            self.empty_state.resize(sw, sh)
            self.empty_state.move(0, 0)

    def open_download_folder(self):
        try:
            if sys.platform == "win32":
                os.startfile(SAVE_DIR)
            else:
                subprocess.Popen(["xdg-open", SAVE_DIR])
        except Exception as e:
            self.show_status(f"Cannot open folder: {e}", error=True)

    def play_card_media(self, card):
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

    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if _exec_modal(dlg) == QDialog.Accepted:
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
        self._preview_timer.stop()
        self._preview_worker = None
        self._preview_card = None
        self._preview_url = ""
        self._download_after_preview = False
        self.thumb_loader.clear_queue()
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.all_cards = []
        self.load_history()

    def toggle_max_normal(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_empty_state()
        self._layout_refresh_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.relayout_grid)

    def on_url_input_changed(self):
        self._preview_timer.stop()
        url = self.input_area.toPlainText().strip()
        normalized = normalize_video_url(url) if url.lower().startswith(("http://", "https://")) else ""
        if self._preview_url and normalized != self._preview_url:
            self._preview_timer.stop()
            if self._download_after_preview:
                self.reset_search_ui()
            self._download_after_preview = False
            if self._preview_card and getattr(self._preview_card, "_preview_only", False):
                self.remove_pending_card(self._preview_card)
            elif self._preview_card and self._preview_card._is_skeleton:
                self.remove_pending_card(self._preview_card)
            self._preview_card = None
            self._preview_url = ""
            self._preview_worker = None

        if normalized and not is_playlist_url(url):
            self._preview_timer.start()

    def _create_pending_card(self, url):
        if self._current_filter != "all":
            self.filter_library("all")
        pending_data = {
            "title": "",
            "url": url,
            "thumbnail": "",
            "source": "LINK",
            "duration": None,
            "path": "",
            "chosen_media": {
                "extension": "mp3" if self._mode == "audio" else "mp4"
            },
            "is_skeleton": True,
        }
        view_w = max(600, self.scroll.viewport().width() or (self.width() - 40))
        num_cols = self._num_cols_for_width(view_w)
        available_w = max(400, view_w - 40 - (num_cols - 1) * 14)
        card = self.create_video_card(pending_data, max(180, available_w // num_cols))
        self.all_cards.insert(0, card)
        self.count_badge.setText(f"({len(self.all_cards)})")
        self.relayout_grid()
        if self.settings.get("auto_scroll_top"):
            self.scroll.verticalScrollBar().setValue(0)
        return card

    def preview_input_url(self):
        url = self.input_area.toPlainText().strip()
        if not url.lower().startswith(("http://", "https://")) or is_playlist_url(url):
            return
        normalized = normalize_video_url(url)
        if normalized == self._preview_url and self._preview_card:
            return

        card = self._create_pending_card(url)
        card._preview_only = True
        self._preview_card = card
        self._preview_url = normalized
        quality = "Audio (MP3)" if self._mode == "audio" else self.quality_combo.currentText()
        worker = MediaExtractorWorker(url, quality)
        worker.pending_card = card
        self._preview_worker = worker
        worker.finished.connect(
            lambda data, item=card, target=normalized, active_worker=worker:
                self.on_preview_success(data, item, target, active_worker)
        )
        worker.error.connect(
            lambda message, item=card, target=normalized, active_worker=worker:
                self.on_preview_error(message, item, target, active_worker)
        )
        worker.finished.connect(
            lambda: self.active_workers.remove(worker) if worker in self.active_workers else None
        )
        worker.error.connect(
            lambda: self.active_workers.remove(worker) if worker in self.active_workers else None
        )
        self.active_workers.append(worker)
        worker.start()

    def on_preview_success(self, data, card, target_url, worker):
        if self._preview_worker is worker:
            self._preview_worker = None
        current_url = self.input_area.toPlainText().strip()
        current_normalized = normalize_video_url(current_url) if current_url.lower().startswith(
            ("http://", "https://")
        ) else ""
        if card not in self.all_cards or self._preview_card is not card or current_normalized != target_url:
            if self._download_after_preview:
                self._download_after_preview = False
                self.reset_search_ui()
            self.remove_pending_card(card)
            return

        preview_data = {
            "title": data.get("title", "Untitled Media"),
            "url": data.get("original_url", target_url),
            "thumbnail": data.get("thumbnail", ""),
            "source": data.get("source", "Video"),
            "duration": data.get("duration"),
            "path": "",
            "chosen_media": data.get("chosen_media", {}),
        }
        card.set_media_data(preview_data)
        card._media_info = data
        card._preview_only = True
        card.status_lbl.setText("Ready")
        if card.thumbnail_path_or_url:
            self.thumb_loader.add_task(card)
        if self._download_after_preview:
            self._download_after_preview = False
            self.reset_search_ui()
            self.start_download_from_preview(card)

    def on_preview_error(self, message, card, target_url, worker):
        if self._preview_worker is worker:
            self._preview_worker = None
        if self._preview_card is card and self._preview_url == target_url:
            if self._download_after_preview:
                self._download_after_preview = False
                self.reset_search_ui()
            self._preview_card = None
            self._preview_url = ""
            self.remove_pending_card(card)
            self.show_status(f"Preview unavailable: {message}", error=True)
        else:
            self.remove_pending_card(card)

    def start_download_from_preview(self, card):
        data = getattr(card, "_media_info", None)
        if not data:
            return
        data = dict(data)
        chosen_media = dict(data.get("chosen_media", {}))
        chosen_media["extension"] = "mp3" if self._mode == "audio" else "mp4"
        data["chosen_media"] = chosen_media
        data["preferred_quality"] = (
            "Audio (MP3)" if self._mode == "audio" else self.quality_combo.currentText()
        )

        filename = f"{clean_filename(data.get('title'))}_{int(time.time())}.{chosen_media['extension']}"
        local_path = os.path.join(SAVE_DIR, filename)
        card_data = {
            "title": data.get("title", "Untitled Media"),
            "url": data.get("original_url", card.video_url),
            "thumbnail": data.get("thumbnail", ""),
            "source": data.get("source", "Video"),
            "duration": data.get("duration"),
            "path": local_path,
            "filename": filename,
            "chosen_media": chosen_media,
            "timestamp": int(time.time()),
        }
        existing_pixmap = card.pixmap
        card.set_media_data(card_data)
        card._media_info = data
        card._preview_only = False
        self._preview_card = None
        self._preview_url = ""
        if existing_pixmap:
            card.set_pixmap(existing_pixmap)
        elif card.thumbnail_path_or_url:
            self.thumb_loader.add_task(card)
        self.input_area.clear()
        self.reset_search_ui()
        self._start_downloader(card, data, local_path, resume=False)

    def choose_video(self):
        self._preview_timer.stop()
        self._mode = "video"
        self.btn_video.setChecked(True)
        self.btn_audio.setChecked(False)
        self.quality_combo.show()
        self.btn_download.setText("Download")
        self._refresh_preview_for_format_change()

    def choose_audio(self):
        self._preview_timer.stop()
        self._mode = "audio"
        self.btn_audio.setChecked(True)
        self.btn_video.setChecked(False)
        self.quality_combo.hide()
        self.btn_download.setText("Download MP3")
        self._refresh_preview_for_format_change()

    def _refresh_preview_for_format_change(self):
        if self._download_after_preview:
            self.reset_search_ui()
        if self._preview_worker:
            self._preview_worker = None
        if self._preview_card:
            self.remove_pending_card(self._preview_card)
        self._preview_card = None
        self._preview_url = ""
        self._download_after_preview = False
        if self.input_area.toPlainText().strip().lower().startswith(("http://", "https://")):
            self._preview_timer.start()

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

        self._preview_timer.stop()
        normalized_url = normalize_video_url(url)
        if self._preview_url == normalized_url and self._preview_card:
            if self._preview_card._is_skeleton:
                self._download_after_preview = True
                self.btn_download.setEnabled(False)
                self.btn_download.setText("Fetching...")
                self.btn_stop.show()
                self.show_status("Searching for media...")
                return
            if getattr(self._preview_card, "_preview_only", False):
                self.start_download_from_preview(self._preview_card)
                return

        self.btn_download.setEnabled(False)
        self.btn_download.setText("Fetching...")
        self.btn_stop.show()
        self.show_status("Searching for media...")

        pref_quality = "Audio (MP3)" if self._mode == "audio" else self.quality_combo.currentText()
        pending_card = self._create_pending_card(url)

        worker = MediaExtractorWorker(url, pref_quality)
        worker.pending_card = pending_card
        worker.finished.connect(
            lambda data, card=pending_card: self.on_api_success(data, card)
        )
        worker.error.connect(
            lambda err_msg, card=pending_card: self.on_api_error(err_msg, card)
        )
        worker.finished.connect(lambda: self.active_workers.remove(worker) if worker in self.active_workers else None)
        worker.error.connect(lambda: self.active_workers.remove(worker) if worker in self.active_workers else None)
        self.active_workers.append(worker)
        worker.start()

    def reset_search_ui(self):
        self.btn_download.setEnabled(True)
        self.btn_download.setText("Download" if self._mode != "audio" else "Download MP3")
        self.btn_stop.hide()

    def stop_extraction(self):
        for w in list(self.active_workers):
            w.stop()
            self.remove_pending_card(getattr(w, "pending_card", None))
        self.active_workers.clear()
        self._preview_worker = None
        self._preview_card = None
        self._preview_url = ""
        self._download_after_preview = False
        self.reset_search_ui()
        self.show_status("Search stopped.")

    def remove_pending_card(self, card):
        if card is None or card not in self.all_cards:
            return
        self.all_cards.remove(card)
        self.grid_layout.removeWidget(card)
        card.deleteLater()
        self.count_badge.setText(f"({len(self.all_cards)})")
        self.relayout_grid()

    def show_status(self, text, error=False):
        if not hasattr(self, 'status_label'):
            return
        if error:
            self.status_label.setStyleSheet("background-color:#2a1714; color:#ff9b91; border:1px solid #d36a5e;")
        else:
            self.status_label.setStyleSheet("background-color:#172130; color:#b9d8fa; border:1px solid #587399;")
        self.status_label.setText(text)
        self.status_label.show()
        QTimer.singleShot(6000, self.status_label.hide)

    def on_api_error(self, err_msg, pending_card=None):
        self.reset_search_ui()
        self.remove_pending_card(pending_card)
        self.show_status(f"Error: {err_msg}", error=True)

    def on_api_success(self, data, pending_card=None):
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

        # Calculate card width on current size
        view_w = max(600, self.scroll.viewport().width() or (self.width() - 40))
        num_cols = self._num_cols_for_width(view_w)
        available_w = max(400, view_w - 40 - (num_cols - 1) * 14)
        card_w = max(180, available_w // num_cols)

        if pending_card in self.all_cards:
            card = pending_card
            card.set_media_data(card_data)
        else:
            card = self.create_video_card(card_data, card_w)
            self.all_cards.insert(0, card)
        card._media_info = data
        self.relayout_grid()

        self.count_badge.setText(f"({len(self.all_cards)})")

        if self.settings.get("auto_scroll_top"):
            self.scroll.verticalScrollBar().setValue(0)

        if card_data["thumbnail"]:
            self.thumb_loader.add_task(card)

        self._start_downloader(card, data, local_path, resume=False)

    def _start_downloader(self, card, media_info, save_path, resume=False):
        card._downloading = True
        card.set_progress(0, "Starting")
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
                "source": card.data.get("source", "Video"),
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
                if ext not in ('.mp4', '.mkv', '.webm', '.mp3'):
                    continue
                ap = os.path.normcase(os.path.abspath(f.path))
                if ap in covered:
                    continue
                cover = cover_cache_path(f.path)
                entries.append(self._file_card_data(f, cover if os.path.exists(cover) else ""))
        except OSError:
            pass

        entries.sort(key=lambda e: e.get("timestamp") or 0, reverse=True)

        initial_view_width = max(600, self.width() - 40)
        num_cols = self._num_cols_for_width(initial_view_width)
        card_w = max(180, (initial_view_width - 40 - (num_cols - 1) * 14) // num_cols)

        for item in entries:
            card = self.create_video_card(item, card_w)
            self.all_cards.append(card)

        self.count_badge.setText(f"({len(self.all_cards)})")
        self.relayout_grid()

        # Load thumbnails in background
        self.thumb_loader.add_tasks(self.all_cards)

    def _file_card_data(self, f, thumb_path=""):
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
            "source": "MEDIA",
            "duration": None,
            "path": f.path,
            "filename": fname,
            "chosen_media": {},
            "timestamp": ts,
        }

    def create_video_card(self, card_data, initial_width):
        card = VideoCard(card_data, initial_width=initial_width)
        card.play_mode = self.settings.get("open_mode", "single")
        card.request_play.connect(self.play_card_media)
        card.request_delete.connect(self.delete_card)
        card.request_retry.connect(self.retry_download)
        return card

    def on_thumbnail_loaded(self, card, qimage):
        if qimage.isNull():
            card.set_thumbnail_fallback()
            return
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

        card.deleteLater()
        if card.file_path and os.path.exists(card.file_path):
            try: os.remove(card.file_path)
            except: pass

        self.rewrite_history()
        self.count_badge.setText(f"({len(self.all_cards)})")
        self.relayout_grid()

    def rewrite_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                for c in reversed(self.all_cards):
                    if getattr(c, "_preview_only", False) or c._is_skeleton:
                        continue
                    f.write(json.dumps(c.data) + "\n")
        except Exception:
            pass

    def closeEvent(self, event):
        self._preview_timer.stop()
        for w in self.active_workers:
            w.stop()
            w.wait()
        for dw in self.download_workers:
            dw.cancel()
            dw.wait()
        self.thumb_loader.stop()
        self.thumb_loader.wait()
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
    sys.exit(app.exec_() if hasattr(app, "exec_") else app.exec())
