"""Local vision ingestion for printed text, handwriting, figures and diagrams."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import CitationAnchor, EvidenceKind, SourceSegment, SourceType


def describe_study_image(path: str | Path) -> str:
    """Extract visible text and learning content using a local Ollama vision model."""
    image_path = Path(path)
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    endpoint = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
    model = os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:2b")
    prompt = (
        "/no_think\nTranscribe all readable printed or handwritten text. Then describe visible "
        "diagrams, equations, charts, labels and arrows. Preserve reading order, headings, "
        "numbers and mathematical symbols. Mark unclear handwriting as [unclear]; do not "
        "guess missing words or invent solutions. Do not add facts."
    )
    payload = json.dumps({
        "model": model, "stream": False,
        "messages": [{"role": "user", "content": prompt, "images": [encoded]}],
        # qwen3-vl can otherwise spend the response budget on hidden reasoning and
        # return an empty learner-facing transcription.
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 2400},
    }).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=180) as response:  # nosec B310 - configured local Ollama endpoint
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        if error.code == 404:
            raise RuntimeError(f"Vision model '{model}' is missing. Run: ollama pull {model}") from error
        raise RuntimeError(f"The local vision model failed: {detail[:300]}") from error
    except URLError as error:
        raise RuntimeError("Local vision is unavailable. Start Ollama and try again.") from error
    description = body.get("message", {}).get("content", "").strip()
    if not description:
        raise RuntimeError("The local vision model could not read this image.")
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
