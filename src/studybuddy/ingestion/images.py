"""Local vision ingestion for printed text, handwriting, figures and diagrams."""

from __future__ import annotations

import base64
import json
import os
import io
import hashlib
from studybuddy.local_cache import cache_path, read_cached, save_cached
from PIL import Image, ImageOps, ImageEnhance
from studybuddy.cancellation import cancellable, check_cancelled
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import CitationAnchor, EvidenceKind, SourceSegment, SourceType

def usable_transcription(value: str) -> bool:
    from studybuddy.text_quality import has_runaway_repetition
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return (bool(lines) and not has_runaway_repetition(value)
            and (len(lines) < 20 or len(set(lines)) / len(lines) > 0.25))


def prepare_vision_image(path: str | Path) -> bytes:
    """Normalize camera orientation, contrast and image size for local vision."""
    with Image.open(path) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        image.thumbnail((2400, 2400))
        image = ImageOps.autocontrast(image, cutoff=0.5)
        image = ImageEnhance.Sharpness(image).enhance(1.3)
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

@cancellable
def describe_study_image(path: str | Path) -> str:
    """Extract visible text and learning content using a local Ollama vision model."""
    image_path = Path(path)
    prepared = prepare_vision_image(image_path)
    encoded = base64.b64encode(prepared).decode("ascii")
    endpoint = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
    # The generic 2b tag resolves to the thinking variant, which can exhaust
    # its output budget without returning any user-visible transcription.
    model = os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:2b-instruct")
    if model == "qwen3-vl:2b":
        model = "qwen3-vl:2b-instruct"
    prompt = (
        "Transcribe all readable printed or handwritten text. Then describe visible "
        "diagrams, equations, charts, labels and arrows. Preserve reading order, headings, "
        "numbers and mathematical symbols. Mark unclear handwriting as [unclear]; do not "
        "guess missing words or invent solutions. Do not add facts."
        " Put each equation on its own line. Keep table rows separate. "
        "Copy subscripts, superscripts, set braces and Greek letters exactly; never replace "
        "an unreadable symbol with a guessed letter or digit. Use [unclear symbol] where needed."
    )
    cached_path = cache_path('vision', {'version': 3, 'model': model, 'endpoint': endpoint,
                                      'prompt': prompt, 'image': hashlib.sha256(prepared).hexdigest()})
    cached = read_cached(cached_path)
    if cached is not None and usable_transcription(cached):
        return cached
    payload = json.dumps({
        "model": model, "stream": False, "keep_alive": "10m",
        "messages": [{"role": "user", "content": prompt, "images": [encoded]}],
        # qwen3-vl can otherwise spend the response budget on hidden reasoning and
        # return an empty learner-facing transcription.
        "options": {"temperature": 0, "repeat_penalty": 1.1, "num_ctx": 8192, "num_predict": 2048},
    }).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=300) as response:  # nosec B310 - configured local Ollama endpoint
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        if error.code == 404:
            raise RuntimeError(f"Vision model '{model}' is missing. Run: ollama pull {model}") from error
        raise RuntimeError(f"The local vision model failed: {detail[:300]}") from error
    except URLError as error:
        raise RuntimeError("Local vision is unavailable. Start Ollama and try again.") from error
    description = body.get("message", {}).get("content", "").strip()
    if not usable_transcription(description) or body.get('done_reason') == 'length':
        # Some local instruction models use the first output budget for internal
        # reasoning. Retry once with a short transcription-only request.
        check_cancelled()
        retry = json.loads(payload)
        retry["messages"][0]["content"] = "Read the text in this image. Return only its transcription. Mark unreadable words [unclear]. Do not repeat lines."
        retry['options']['num_predict'] = 4096
        retry['options']['repeat_penalty'] = 1.15
        request = Request(endpoint, data=json.dumps(retry).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=300) as response:
                retry_body = json.loads(response.read().decode("utf-8"))
            description = retry_body.get("message", {}).get("content", "").strip()
        except (HTTPError, URLError, TimeoutError) as error:
            raise RuntimeError("The photo reader did not respond. Check Ollama and retry the photo.") from error
        if not usable_transcription(description) or retry_body.get('done_reason') == 'length':
            raise RuntimeError("The image reader could not produce a complete, non-repeating transcription. Try a clearer photo or crop the page into smaller sections.")
    save_cached(cached_path, description)
    return description


def ingest_image(
    path: str | Path, *, source_id: str, source_name: str, source_uri: str | None = None,
    describe_image=describe_study_image,
) -> list[SourceSegment]:
    description = describe_image(Path(path))
    return [SourceSegment(
        text=description,
        citation=CitationAnchor(
            source_id=source_id, source_name=source_name, source_type=SourceType.IMAGE,
            source_uri=source_uri, section="image",
        ),
        evidence_kind=EvidenceKind.VISION,
        image_path=str(path),
    )]
