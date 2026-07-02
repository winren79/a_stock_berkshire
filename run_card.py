"""Write reproducible run cards for daily signal-engine runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(name: str, path: Path) -> dict[str, Any]:
    exists = path.exists()
    item = {
        "name": name,
        "path": str(path),
        "exists": exists,
        "size_bytes": int(path.stat().st_size) if exists else 0,
        "sha256": _sha256(path) if exists else "",
    }
    return item


def write_run_card(
    summary: Any,
    output_dir: Path,
    artifacts: dict[str, Path],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_data = _jsonable(summary)
    artifact_rows = [_artifact(name, Path(path)) for name, path in artifacts.items()]
    card = {
        "schema_version": "run_card.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary_data,
        "warnings": warnings or [],
        "artifacts": artifact_rows,
    }

    json_path = output_dir / "run_card.json"
    md_path = output_dir / "run_card.md"
    json_path.write_text(json.dumps(card, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    lines = [
        f"# Run Card - {summary_data.get('run_at', '')}",
        "",
        f"- 数据源：{summary_data.get('source', '')}",
        f"- 情绪周期：{summary_data.get('market_emotion', '')}",
        f"- 获取数量：{summary_data.get('rows_fetched', '')}",
        f"- 入选数量：{summary_data.get('rows_selected', '')}",
        "",
        "## Warnings",
    ]
    if card["warnings"]:
        lines.extend(f"- {warning}" for warning in card["warnings"])
    else:
        lines.append("- 无")
    lines.extend(["", "## Artifacts"])
    lines.extend(f"- {item['name']}: `{item['path']}` sha256={item['sha256']}" for item in artifact_rows)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return card
