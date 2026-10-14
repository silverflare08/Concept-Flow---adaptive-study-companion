"""Private, content-addressed cache for expensive local model responses."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from studybuddy.cancellation import check_cancelled

def cache_path(namespace: str, identity: object) -> Path:
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, default=str).encode()).hexdigest()
    return Path(os.getenv('CONCEPTFLOW_CACHE_DIR', 'data/cache')) / namespace / f'{digest}.json'

def read_cached(path: Path) -> str | None:
    check_cancelled()
    try:
        value = json.loads(path.read_text(encoding='utf-8')).get('answer')
        return value if isinstance(value, str) and value.strip() else None
    except (OSError, ValueError, AttributeError):
        return None

def save_cached(path: Path, answer: str) -> None:
    check_cancelled()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f'.{uuid4().hex}.tmp')
        temporary.write_text(json.dumps({'answer': answer}, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)
    except OSError:
        # Cache storage is an optimization; a read-only disk must not lose an answer.
        return
