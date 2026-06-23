from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any


class Turn:
    def __init__(self, role: str, content: str, turn_number: int = 0):
        self.role = role
        self.content = content
        self.turn_number = turn_number
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "turn_number": self.turn_number,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Turn:
        t = Turn(d["role"], d["content"], d.get("turn_number", 0))
        t.timestamp = d.get("timestamp", t.timestamp)
        return t


class Dossier:
    def __init__(self):
        self.sections: dict[str, str] = {
            "identity_resolution": "",
            "digital_footprint": "",
            "timeline": "",
            "professional_intelligence": "",
            "network_map": "",
            "writing_style_analysis": "",
            "business_intelligence": "",
            "technical_intelligence": "",
            "reputation_assessment": "",
            "behavioral_patterns": "",
            "influence_analysis": "",
            "opportunity_analysis": "",
            "verification": "",
            "unknowns": "",
        }
        self.confidence_scores: dict[str, int] = {}

    def update_section(self, section: str, content: str) -> None:
        if section in self.sections:
            if self.sections[section]:
                self.sections[section] += "\n\n" + content
            else:
                self.sections[section] = content

    def get_completed_sections(self) -> list[str]:
        return [k for k, v in self.sections.items() if v.strip()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections": self.sections,
            "confidence_scores": self.confidence_scores,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Dossier:
        ds = Dossier()
        if "sections" in d:
            for k in ds.sections:
                ds.sections[k] = d["sections"].get(k, "")
        if "confidence_scores" in d:
            ds.confidence_scores = d["confidence_scores"]
        return ds


class Investigation:
    def __init__(
        self,
        target_type: str,
        target_value: str,
        investigation_id: str | None = None,
    ):
        self.id = investigation_id or str(uuid.uuid4())[:8]
        self.target_type = target_type
        self.target_value = target_value
        self.status = "active"
        self.current_phase = "initializing"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.turns: list[Turn] = []
        self.dossier = Dossier()
        self.plan: list[str] = []
        self.current_step = 0
        self.messages: list[dict[str, str]] = []

    def add_turn(self, role: str, content: str) -> Turn:
        turn = Turn(role, content, len(self.turns) + 1)
        self.turns.append(turn)
        return turn

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_type": self.target_type,
            "target_value": self.target_value,
            "status": self.status,
            "current_phase": self.current_phase,
            "created_at": self.created_at,
            "turns": [t.to_dict() for t in self.turns],
            "dossier": self.dossier.to_dict(),
            "plan": self.plan,
            "current_step": self.current_step,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Investigation:
        inv = Investigation(
            d.get("target_type", "unknown"),
            d.get("target_value", ""),
            d.get("id"),
        )
        inv.status = d.get("status", "active")
        inv.current_phase = d.get("current_phase", "")
        inv.created_at = d.get("created_at", inv.created_at)
        inv.turns = [Turn.from_dict(t) for t in d.get("turns", [])]
        inv.dossier = Dossier.from_dict(d.get("dossier", {}))
        inv.plan = d.get("plan", [])
        inv.current_step = d.get("current_step", 0)
        return inv
