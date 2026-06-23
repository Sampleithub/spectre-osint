from __future__ import annotations

import json
import os
from typing import Any

from app.config import config
from app.models.schemas import Investigation


class SessionStore:
    def __init__(self):
        os.makedirs(config.data_dir, exist_ok=True)

    def _path(self, investigation_id: str) -> str:
        return os.path.join(config.data_dir, f"{investigation_id}.json")

    def save(self, investigation: Investigation) -> None:
        path = self._path(investigation.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(investigation.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self, investigation_id: str) -> Investigation | None:
        path = self._path(investigation_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
        return Investigation.from_dict(data)

    def list_all(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        if not os.path.isdir(config.data_dir):
            return summaries
        for fname in sorted(os.listdir(config.data_dir), reverse=True):
            if fname.endswith(".json"):
                path = os.path.join(config.data_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data: dict[str, Any] = json.load(f)
                    summaries.append({
                        "id": data.get("id", ""),
                        "target_type": data.get("target_type", ""),
                        "target_value": data.get("target_value", ""),
                        "status": data.get("status", ""),
                        "current_phase": data.get("current_phase", ""),
                        "created_at": data.get("created_at", ""),
                        "turn_count": len(data.get("turns", [])),
                    })
                except Exception:
                    continue
        return summaries


store = SessionStore()
