# Download Free v1.0.1

desktop Media & Video Downloader built with **PySide6 (Qt)** and a **Custom Embedded Engine** (No external `yt-dlp` tool or Python package required).

It delivers blazing-fast extraction and downloads across all modern streaming formats (1080p Full HD, 4K, 720p, 480p, 360p, and Audio MP3) with built-in PO-Token and JS challenge solvers to bypass YouTube throttling and SABR rate-limiting experiments.

![Python](https://img.shields.io/badge/Python-3.11-blue) ![Qt](https://img.shields.io/badge/Qt-6.11-green) ![Engine](https://img.shields.io/badge/Custom_Engine-v2.0-brightgreen) ![License](https://img.shields.io/badge/License-Proprietary-orange)

---

## Key Highlights

-  **No yt-dlp Required**: Fully independent operation powered by the custom in-project `src` engine. Runs anywhere without installing external binaries or system packages.
-  **High Speed & All Qualities**:
  - Full HD **1080p**, 2K, **4K**, 720p, 480p, 360p video streams with automatic audio merging.
  - High-bitrate **Audio (MP3)** extraction (192 kbps).
  - Multi-threaded chunk streaming (`http_chunk_size`) that completely solves the 40%–50% throttling/drop issue.
-  **Anti-Throttling & Deciphering**:
  - Built-in **Proof of Origin (POT)** generation.
  - Built-in **JavaScript Challenge Solver (JSC)** for instant `n-sig` resolution.
-  **Modern Dark UI**:
  - Floating translucent control bar with macOS-style window controls.
  - Responsive masonry grid library (`~/.downfree`) with automatic cover generation.
  - Quick access Settings dialog with custom download directory, column layout (3–7 columns or List view), auto-retry, and auto-resume.


****
---

## Supported Platforms & Resolutions

| Format / Quality | Description | Encoding & Container |
| :--- | :--- | :--- |
| **Best Quality** | Highest available video stream up to 4K | MP4 (Video + Audio Merged) |
| **1080p** | Full HD (1920x1080) Crisp 60fps/30fps | MP4 (AVC / AV01 + AAC) |
| **720p** | HD (1280x720) High Definition | MP4 |
| **480p / 360p** | Standard Definition for low storage | MP4 |
| **Audio (MP3)** | Pure crystal-clear stereo audio | MP3 (192 kbps) |

Supported Platforms: **YouTube (Videos & Shorts), Facebook, Instagram Reels & Posts**.

---

## Installation & Setup

### Option 1: Using the Installer (Recommended for Users)
Download and run **`DownloadFree_Setup_v2.0.exe`** from the `Output/` folder. It installs everything automatically (including the engine and desktop shortcuts).

### Option 2: Running from Source
```bash
# 1. Install required Python packages
pip install -r requirements_1.0.1.txt

# 2. Run the application
python app_1.0.1.py
```

---

## Building Standalone Binaries

The project comes with automated one-click batch scripts:

1. **`build_src.bat`**: Compiles the internal `src/` modules into the standalone `dist\engine.exe`.
2. **`app_build.bat`**: Full automated build pipeline:
   - Builds `engine.exe` from `src`.
   - Builds the main windowed `Download Free.exe`.
   - Compiles the single-file setup installer `Output\DownloadFree_Setup_v2.0.exe` via Inno Setup.

---

## Project Structure

```text
├── app.py               # Main PySide6 UI and application logic
├── engine_cli.py        # Custom standalone engine CLI wrapper
├── engine.spec          # PyInstaller configuration for engine.exe
├── app.spec             # PyInstaller configuration for Download Free.exe
├── installer.iss        # Inno Setup 6 installer script
├── build_src.bat        # 1-click batch script for engine.exe
├── app_build.bat        # 1-click batch script for full application build
├── requirements.txt     # Python requirements
├── icon.ico             # Application branding icon
└── src/                 # Custom Engine modules
    ├── _video.py        # YouTube video extractor & resolution handler
    ├── _base.py         # YouTube Innertube client handler
    ├── pot/             # Proof of Origin Token manager
    ├── jsc/             # JS signature challenge solver
    ├── facebook.py      # Facebook extractor
    └── instagram.py     # Instagram extractor
```

---

## Updating the Engine in the Future

When streaming platforms update their algorithms, you can easily maintain and update the engine:
1. Update or tweak the extractor file inside `src/` (e.g., `_video.py` or `jsc/`).
2. Run `build_src.bat` to re-generate `engine.exe`.
3. Run `app_build.bat` to pack the new version.


---

# Download Free 1.0.0

A modern desktop YouTube / URL downloader and player built with **PySide6 (Qt)**.

It extracts videos and audio through the **downr.org** API (falling back to **yt-dlp**),
stores them in a local library (`~/.downfree`), and plays them back with a built-in
floating player.

[Download](https://github.com/YASSER-27/YOUTUBE-DOWNLOAD/releases/tag/1.0.0)

![Python](https://img.shields.io/badge/Python-3.11-blue) ![Qt](https://img.shields.io/badge/Qt-6.11-green)


## Features

- **Dark & green** frameless UI with a custom title bar (macOS-style buttons).
- **Paste & download**: drop a YouTube/social link, choose quality (Best / 720p / 360p / Audio MP3).
- **Video library grid** (`~/.downfree`): every downloaded file is shown automatically,
  even when its history entry is missing.
- **Built-in player**: floating bubble player that animates onto the clicked card,
  with play/pause, seek bar, time, fullscreen and a close button. Audio output follows
  the system default device instantly (headphones <-> speakers).
- **Software-rendered video surface** (QVideoSink + QPainter) instead of the native
  D3D11 widget — avoids black-screen playback issues on many machines.
- Background downloading with live progress on each card.
- Delete / open folder / open file context menus on every card.


<img width="1800" height="1126" alt="down" src="https://github.com/user-attachments/assets/9364762e-989a-4e1d-8dcb-1772777c8c9b" />


## Requirements

- Python 3.11+
- Windows (primary target), though the code is mostly cross-platform.
- System **ffmpeg** in `PATH` if you enable extraction via yt-dlp (optional).

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

## Build a standalone .exe

```bash
pip install pyinstaller
Remove-Item -Recurse -Force build, dist
pyinstaller app.spec --noconfirm
```

The output is `dist\Download Free.exe` (a single-file, windowed build).

> Note: the Qt WebEngine / QML / PDF modules are excluded in `app.spec` to keep the
> exe small (~50 MB), and unused Qt DLLs are filtered out explicitly.

## Data & storage

| Path                         | Purpose                                  |
| ---------------------------- | ---------------------------------------- |
| `~/.downfree/`               | Download folder (videos + thumb cache)   |
| `~/.downfree/downloads.jsonl`| Download history (one JSON per line)     |
| `~/.downfree/session.json`   | Last-used settings                       |

## Known limitation: AV1 / HEVC playback

Qt Multimedia's FFmpeg backend cannot decode **AV1** or **HEVC** on machines without
hardware support (known Qt issue, no software fallback). Videos saved as AV1/HEVC may
play with black screen / audio only.

The app mitigates this by preferring **H.264 / VP9** streams when choosing the download
quality (`select_media_stream`), so newly downloaded files play on the first click.
Legacy AV1 files may need to be re-downloaded in a compatible format.

## Project layout

- `app.py` — the entire application (UI, downloaders, player).
- `app.spec` — PyInstaller build configuration.
- `icon.ico` — application icon.
- `requirements.txt` — Python dependencies.
