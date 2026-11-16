# -*- coding: utf-8 -*-
"""
Core standalone CLI engine wrapper for media extraction and downloads.
Compatible with standard arguments for metadata extraction and media downloads.
"""

import sys
import os
import json
import warnings

# Suppress request/urllib3 warnings
warnings.filterwarnings('ignore')
os.environ['PYTHONWARNINGS'] = 'ignore'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Static ffmpeg support if available
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

# Ensure standard ffmpeg paths if present
if os.path.exists(r'C:\ffmpeg\bin') and r'C:\ffmpeg\bin' not in os.environ.get('PATH', ''):
    os.environ['PATH'] = r'C:\ffmpeg\bin;' + os.environ.get('PATH', '')

from yt_dlp.YoutubeDL import YoutubeDL
import yt_dlp

def main():
    args = sys.argv[1:]
    if not args:
        print("Engine CLI - Ready")
        return

    dump_json = False
    format_spec = 'bestvideo+bestaudio/best'
    out_tmpl = '%(title)s.%(ext)s'
    url = None

    i = 0
    while i < len(args):
        a = args[i]
        if a in ('-J', '--dump-json', '--dump-single-json'):
            dump_json = True
        elif a in ('-f', '--format') and i + 1 < len(args):
            format_spec = args[i + 1]
            i += 1
        elif a in ('-o', '--output') and i + 1 < len(args):
            out_tmpl = args[i + 1]
            i += 1
        elif not a.startswith('-'):
            url = a
        i += 1

    if not url:
        print("Error: No URL provided.")
        sys.exit(1)

    def _progress_hook(d):
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed') or 0
            if speed >= 1024 * 1024:
                sp_str = f"{speed / (1024 * 1024):.1f}MB/s"
            else:
                sp_str = f"{speed / 1024:.0f}KB/s"
            pct = (downloaded / total * 100) if total > 0 else 0
            print(f"[download] {pct:.1f}% at {sp_str}", flush=True)
        elif d.get('status') == 'finished':
            print("[download] 100% at 0KB/s", flush=True)

    ydl_opts = {
        'format': format_spec,
        'outtmpl': out_tmpl,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'http_chunk_size': 10485760,
        'retries': 10,
        'fragment_retries': 10,
        'buffersize': 1024 * 64,
        'js_runtimes': {'node': {}}
    }

    if not dump_json:
        ydl_opts['progress_hooks'] = [_progress_hook]

    if format_spec == 'bestaudio/best':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192'
        }]

    if dump_json:
        ydl_opts['skip_download'] = True
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print(json.dumps(info))
        return

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

if __name__ == '__main__':
    main()
