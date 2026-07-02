"""File-backed hypothesis registry for short-term signal research."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "hypothesis_registry.v1", "hypotheses": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, registry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def record_daily_run(
    registry_path: Path,
    hypothesis_id: str,
    title: str,
    thesis: str,
    strategy_version: str,
    run_card_path: Path,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    registry = _load(registry_path)
    hypotheses = registry.setdefault("hypotheses", [])
    now = _now_utc()
    hypothesis = next((item for item in hypotheses if item.get("id") == hypothesis_id), None)
    if hypothesis is None:
        hypothesis = {
            "id": hypothesis_id,
            "title": title,
            "thesis": thesis,
            "status": "testing",
            "strategy_version": strategy_version,
            "created_at": now,
            "updated_at": now,
            "runs": [],
            "invalidation_notes": [],
        }
        hypotheses.append(hypothesis)
    else:
        hypothesis["title"] = title
        hypothesis["thesis"] = thesis
        hypothesis["strategy_version"] = strategy_version
        hypothesis["updated_at"] = now

    hypothesis.setdefault("runs", []).append(
        {
            "run_at": now,
            "run_card_path": str(run_card_path),
            "metrics": metrics,
        }
    )
    _save(registry_path, registry)
    return hypothesis
