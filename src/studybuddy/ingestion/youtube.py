"""YouTube audio acquisition for timestamp-grounded local transcription."""

from __future__ import annotations

from pathlib import Path

from .web import is_youtube_url, validate_public_url


def download_youtube_audio(url: str, output_dir: str | Path) -> tuple[Path, str, str]:
    validate_public_url(url)
    if not is_youtube_url(url):
        raise ValueError("This is not a supported YouTube URL.")
    try:
        from yt_dlp import YoutubeDL
    except ImportError as error:
        raise RuntimeError("YouTube import requires yt-dlp. Install the ingestion dependencies.") from error
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "bestaudio/best",
        "outtmpl": str(destination / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": 500 * 1024 * 1024,
    }
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
        path = Path(downloader.prepare_filename(info))
    if not path.is_file():
        matches = list(destination.glob(f"{info['id']}.*"))
        if not matches:
            raise RuntimeError("YouTube audio was downloaded but its file could not be located.")
        path = matches[0]
    return path, info.get("title") or "YouTube lecture", info.get("webpage_url") or url
