# Download Free

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
