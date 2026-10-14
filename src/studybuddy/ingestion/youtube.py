"""YouTube audio acquisition for timestamp-grounded local transcription."""

from __future__ import annotations

from pathlib import Path
import json
import re
from html import unescape

from .web import is_youtube_url, validate_public_url, fetch_public_resource
from .video import TranscriptSpan
from studybuddy.cancellation import check_cancelled, GenerationStopped


def caption_spans(content: bytes, extension: str) -> list[TranscriptSpan]:
    """Parse real caption timestamps; never estimate them from text length."""
    spans = []
    if extension == "json3":
        for event in json.loads(content).get("events", []):
            text = " ".join("".join(segment.get("utf8", "") for segment in event.get("segs", [])).split())
            if text and "tStartMs" in event:
                start = event["tStartMs"] / 1000
                spans.append(TranscriptSpan(text, start, start + max(0, event.get("dDurationMs", 0)) / 1000))
    elif extension == "vtt":
        def seconds(value):
            parts = value.replace(",", ".").split(":")
            return sum(float(part) * 60 ** index for index, part in enumerate(reversed(parts)))
        for block in re.split(r"\n\s*\n", content.decode("utf-8", errors="replace")):
            match = re.search(r"([\d:.]+)\s+-->\s+([\d:.]+)[^\n]*\n(.*)", block, re.S)
            if match:
                text = " ".join(unescape(re.sub(r"<[^>]+>", "", match[3])).split())
                if text:
                    spans.append(TranscriptSpan(text, seconds(match[1]), seconds(match[2])))
    result = []
    for span in spans:
        if result and result[-1].text == span.text:
            previous = result[-1]
            result[-1] = TranscriptSpan(previous.text, previous.start_seconds, max(previous.end_seconds, span.end_seconds))
        else:
            result.append(span)
    return result


def fetch_youtube_captions(url: str) -> tuple[str, str, list[TranscriptSpan]] | None:
    """Use existing subtitles before spending CPU time on speech recognition."""
    validate_public_url(url)
    if not is_youtube_url(url):
        raise ValueError("This is not a supported YouTube URL.")
    check_cancelled()
    try:
        from yt_dlp import YoutubeDL
        with YoutubeDL({"skip_download": True, "noplaylist": True, "quiet": True,
                        "no_warnings": True, "socket_timeout": 15, "retries": 1}) as downloader:
            info = downloader.extract_info(url, download=False)
        for tracks in (info.get("subtitles", {}), info.get("automatic_captions", {})):
            original = info.get("language") or "en"
            languages = sorted(tracks, key=lambda key: (key != original, not key.startswith("en"), key))
            for language in languages:
                entries = [item for item in tracks[language] if item.get("ext") in {"json3", "vtt"}]
                entries.sort(key=lambda item: item["ext"] != "json3")
                for entry in entries[:1]:
                    check_cancelled()
                    resource = fetch_public_resource(entry["url"], max_bytes=10 * 1024 * 1024)
                    spans = caption_spans(resource.content, entry["ext"])
                    if spans:
                        return info.get("title") or "YouTube lecture", info.get("webpage_url") or url, spans
                # Try one language per track type rather than downloading translations.
                if entries:
                    break
    except GenerationStopped:
        raise
    except Exception:
        # Caption availability is optional; the audio route remains available.
        return None
    return None


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
