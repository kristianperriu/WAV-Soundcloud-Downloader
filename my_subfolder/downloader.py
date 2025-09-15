import os
import re
import sys
import shutil
import platform
import yt_dlp
import tempfile

SC_COOKIES_FILE = 'soundcloud.com_cookies.txt'   # optional cookies/login

def find_ffmpeg() -> str:
    ff = shutil.which('ffmpeg')
    fp = shutil.which('ffprobe')
    if ff and fp:
        return ff
    prefix = sys.prefix
    cand = os.path.join(prefix, 'Library', 'bin') if platform.system() == 'Windows' else os.path.join(prefix, 'bin')
    ff = os.path.join(cand, 'ffmpeg' + ('.exe' if platform.system() == 'Windows' else ''))
    fp = os.path.join(cand, 'ffprobe' + ('.exe' if platform.system() == 'Windows' else ''))
    if os.path.isfile(ff) and os.path.isfile(fp):
        return ff
    raise RuntimeError("ffmpeg/ffprobe not found. Install it and make sure it is on PATH.")


def sanitize(name: str) -> str:
    return re.sub(r'[<>:\"/\\|?*\r\n]+', '', name).strip()
ffmpeg_dir = os.path.dirname(find_ffmpeg())



def download_soundcloud_playlist(url: str) -> str:
    """
    Download an entire SoundCloud playlist as WAV (44.1 kHz stereo).
    Returns the path to the folder containing all WAV files.
    """
    slug   = sanitize(url.rstrip('/').split('/')[-1])
    folder = os.path.join(tempfile.gettempdir(), slug)
    os.makedirs(folder, exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': False,
        'extract_flat': False,
        'prefer_ffmpeg': True,
        'keepvideo': False,
        'ffmpeg_location': ffmpeg_dir,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '0',
        }],
        'postprocessor_args': ['-ar', '44100', '-ac', '2'],
        'outtmpl': os.path.join(folder, '%(playlist_index)02d - %(title)s.%(ext)s'),
    }

    if SC_COOKIES_FILE and os.path.isfile(SC_COOKIES_FILE):
        ydl_opts['cookiefile'] = SC_COOKIES_FILE

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return folder
