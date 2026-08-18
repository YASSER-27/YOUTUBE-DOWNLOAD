# -*- coding: utf-8 -*-
"""
Core standalone CLI engine wrapper for src.
Compatible with standard arguments for metadata extraction and media downloads.
"""

import sys
import os
import json
import warnings

# Suppress request/urllib3 warnings
warnings.filterwarnings('ignore')
os.environ['PYTHONWARNINGS'] = 'ignore'

# Ensure C:\ffmpeg\bin is in PATH
if os.path.exists(r'C:\ffmpeg\bin') and r'C:\ffmpeg\bin' not in os.environ.get('PATH', ''):
    os.environ['PATH'] = r'C:\ffmpeg\bin;' + os.environ.get('PATH', '')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from yt_dlp.YoutubeDL import YoutubeDL
import yt_dlp

def main():
    args = sys.argv[1:]
    if not args:
        print("Custom Engine CLI - Ready")
        return

    # Check for JSON dump mode
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

    ydl_opts = {
        'format': format_spec,
        'outtmpl': out_tmpl,
        'quiet': True if dump_json else False,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'http_chunk_size': 10485760,
        'retries': 10,
        'fragment_retries': 10,
        'buffersize': 1024 * 64,
        'js_runtimes': {'node': {}}
    }

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
