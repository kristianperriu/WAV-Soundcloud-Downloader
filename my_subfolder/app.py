import streamlit as st
import os, zipfile, io, re
import yt_dlp
from downloader import find_ffmpeg, sanitize

st.set_page_config(page_title="SoundCloud Downloader", page_icon="🎧", layout="centered")

st.markdown(
    """
    <div style='text-align:center'>
        <h1 style='color:#ff5500'>🎧 WAV SoundCloud Downloader</h1>
        <p style='font-size:18px; color:#555'>
            Download SoundCloud tracks or entire playlists as high-quality WAV (44.1 kHz stereo).
        </p>
        <hr>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Download type toggle ---
mode = st.segmented_control(
    "Select download type:",
    options=["🎵 Single track", "📂 Playlist"],
    default="🎵 Single track"
)

# --- URL input & start button ---
sc_url = st.text_input(
    f"Enter {'track' if 'Single' in mode else 'playlist'} URL:",
    placeholder="https://soundcloud.com/artist/track-or-playlist"
)
start_download = st.button("⬇️ Start Download", type="primary")

# --- Session state for cancel ---
if "cancel" not in st.session_state:
    st.session_state.cancel = False
def cancel_download():
    st.session_state.cancel = True

# --- UI placeholders ---
progress_bar = st.progress(0)
status_text = st.empty()
cancel_placeholder = st.empty()

def download_worker(url: str, is_playlist: bool):
    """Download as WAV with accurate per-track index display and return slug + zip buffer."""
    ffmpeg_dir = os.path.dirname(find_ffmpeg())
    slug = sanitize(url.rstrip('/').split('/')[-1])
    out_folder = os.path.join(os.getcwd(), slug)
    os.makedirs(out_folder, exist_ok=True)

    # Prefetch playlist info to get total_tracks and id->index map
    total_tracks = 1
    id_to_index = {}
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            meta = ydl.extract_info(url, download=False)
        if is_playlist:
            entries = [e for e in (meta.get('entries') or []) if e]
            total_tracks = len(entries) or meta.get('n_entries') or 1
            for i, e in enumerate(entries, start=1):
                entry_id = e.get('id') or e.get('url')
                idx = e.get('playlist_index') or i
                if entry_id:
                    id_to_index[entry_id] = idx
        else:
            total_tracks = 1
    except Exception:
        total_tracks = 1
        id_to_index = {}

    def hook(d):
        if st.session_state.cancel:
            raise yt_dlp.utils.DownloadError("User cancelled the download.")

        info = d.get('info_dict', {}) or {}
        title = info.get('title', '')
        curr_id = info.get('id') or info.get('url')
        playlist_idx = info.get('playlist_index') or (id_to_index.get(curr_id) if curr_id else None)
        if not is_playlist:
            playlist_idx = 1
        if not playlist_idx:
            playlist_idx = 1

        percent = 0.0
        percent_str = d.get('_percent_str', '')
        if percent_str:
            clean = re.sub(r'\x1B\[[0-9;]*[A-Za-z]', '', percent_str).replace('%', '').strip()
            try:
                percent = float(clean)
            except ValueError:
                percent = 0.0
        else:
            dt, tt = d.get('downloaded_bytes'), d.get('total_bytes') or d.get('total_bytes_estimate')
            if dt and tt:
                percent = (dt / tt) * 100.0

        if d['status'] == 'downloading':
            status_text.text(f"🎶 {title} — {playlist_idx}/{total_tracks} ({percent:.1f}%)")
            progress_bar.progress(min(int(percent), 100))
        elif d['status'] == 'finished':
            status_text.text(f"✅ Finished: {title} — {playlist_idx}/{total_tracks}")

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': not is_playlist,
        'prefer_ffmpeg': True,
        'keepvideo': False,
        'ffmpeg_location': ffmpeg_dir,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '0',
        }],
        'postprocessor_args': ['-ar', '44100', '-ac', '2'],
        'outtmpl': os.path.join(
            out_folder,
            '%(playlist_index)02d - %(title)s.%(ext)s' if is_playlist else '%(title)s.%(ext)s'
        ),
        'progress_hooks': [hook],
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Zip everything inside a buffer
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in sorted(os.listdir(out_folder)):
            fpath = os.path.join(out_folder, fname)
            if os.path.isfile(fpath):
                zf.write(fpath, arcname=fname)
    zip_buffer.seek(0)
    return slug, zip_buffer   # slug = clean name for ZIP

# --- Start download ---
if start_download:
    if not sc_url:
        st.error("Please enter a SoundCloud URL.")
    elif "Single" in mode and "/sets/" in sc_url:
        st.error("❌ You selected Single track mode but provided a playlist URL. Please switch to Playlist mode.")
    else:
        st.session_state.cancel = False
        cancel_placeholder.button("❌ Cancel Download", on_click=cancel_download)

        try:
            slug, zip_buffer = download_worker(
                sc_url,
                is_playlist=("Playlist" in mode)
            )
            progress_bar.progress(100)
            status_text.text("✅ All tracks downloaded. Ready to save.")
            cancel_placeholder.empty()
            # ✅ Use the playlist/track slug as the ZIP file name
            st.download_button(
                label="📥 Download as ZIP",
                data=zip_buffer,
                file_name=f"{slug}.zip",
                mime="application/zip"
            )
        except yt_dlp.utils.DownloadError as e:
            cancel_placeholder.empty()
            if st.session_state.cancel:
                status_text.text("❌ Download cancelled.")
            else:
                status_text.text(f"⚠️ Download failed: {e}")

# ---------------------------------------------------------------------
# Donation & Contact Footer
# ---------------------------------------------------------------------
st.markdown(
    """
    <hr style="margin-top:3em;margin-bottom:2em;">

    <div style="text-align:center; font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
        <p style="font-size:16px; color:#555; max-width:500px; margin:0 auto 1.5em;">
            If you find this downloader useful, consider supporting the project with a small contribution.
            Your donations directly fund maintenance and future improvements.
        </p>
        <a href="https://www.paypal.me/KristianPerriu" target="_blank" rel="noopener">
            <button style="
                background-color:#0070ba;
                color:white;
                padding:8px 10px;
                border:none;
                border-radius:8px;
                font-size:18px;
                font-weight:600;
                cursor:pointer;
                box-shadow:0 4px 6px rgba(0,0,0,0.2);
            ">
                💳 Donate via PayPal
            </button>
        </a>
        <hr style="margin-top:2em;margin-bottom:2em;width:100%">
    </div>

    <div style="font-size:13px; color:#666; text-align:center; max-width:600px; margin:0 auto;">
        <strong>Copyright Notice:</strong><br>
        This tool is intended solely for downloading content that you own the rights to
        or that is freely and legally available. By using this service, you agree to comply
        with all applicable copyright and intellectual property laws.
        <br><br>
        <strong>Contact:</strong><br>
        <a href="mailto:kperriu@gmail.com" style="color:#0070ba;">kperriu@gmail.com</a>
    </div>
    """,
    unsafe_allow_html=True
)
