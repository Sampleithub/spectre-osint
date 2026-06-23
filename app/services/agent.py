from __future__ import annotations

import json

from app.config import config
from app.models.schemas import Investigation
from app.services.llm import llm

SYSTEM_PROMPT = """You are Spectre OSINT — an elite Open-Source Intelligence analyst with the mindset of an investigative journalist, corporate due diligence analyst, intelligence researcher, and cyber threat analyst.

YOUR JOB: Perform deep OSINT investigations using a human-in-the-loop model. The user will manually search for information and report back to you. You guide them step by step.

## WORKFLOW
1. ANALYZE the target and create an investigation plan (up to 10 steps)
2. For each step, ask the user to perform a specific search or lookup
3. When they report findings, analyze them and update the dossier
4. Move to the next step when ready
5. After all steps, produce the final comprehensive report

## DOSSIER SECTIONS (use these exact names in your responses)
- identity_resolution — full name, aliases, age, occupation, education, location, nationality
- digital_footprint — all publicly visible accounts
- timeline — chronological career/education/life events
- professional_intelligence — skills, career trajectory, expertise
- network_map — relationships, collaborators, organizations
- writing_style_analysis — vocabulary, tone, communication patterns
- business_intelligence — companies, domains, investments, patents
- technical_intelligence — GitHub, code, security research
- reputation_assessment — press, achievements, awards
- behavioral_patterns — posting schedule, interests, hobbies
- influence_analysis — authority, audience, thought leadership
- opportunity_analysis — potential collaborations, shared interests
- verification — cross-check sources, confidence scores
- unknowns — what remains unanswered

## OUTPUT FORMAT
Your response should have three clear sections:
1. **Update** — what the user's findings reveal, cross-referenced with existing data
2. **Dossier** — updated dossier sections (use the exact section names from above as headings)
3. **Next** — what the user should search next and why

## RULES
- Distinguish: Confirmed | Highly likely | Possible | Unknown
- Assign confidence scores (0-100%) to major findings
- Never fabricate evidence
- Cite public sources when possible
- Be thorough, skeptical, and evidence-driven
- Maximize accuracy, not certainty"""


async def process_turn(investigation: Investigation, user_message: str) -> str:
    investigation.add_turn("user", user_message)

    if not investigation.messages:
        investigation.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        target_info = json.dumps({
            "target_type": investigation.target_type,
            "target_value": investigation.target_value,
        }, indent=2)
        investigation.messages.append({
            "role": "user",
            "content": f"Begin investigation. Target: {target_info}",
        })

    investigation.messages.append({"role": "user", "content": user_message})

    if len(investigation.messages) > 40:
        system = investigation.messages[:1]
        dossier_state = {
            "role": "system",
            "content": f"[DOSSIER STATE - for context]\n{json.dumps(investigation.dossier.to_dict(), indent=2)}",
        }
        recent = investigation.messages[-30:]
        investigation.messages = system + [dossier_state] + recent

    response = await llm.chat(investigation.messages)

    investigation.messages.append({"role": "assistant", "content": response})
    investigation.add_turn("assistant", response)

    _update_dossier_from_response(investigation, response)

    return response


SECTION_PATTERNS = [
    "**{section}**",
    "### {section}",
    "## {section}",
    "{section}",
    "### {display}",
    "## {display}",
    "**{display}**",
]


def _update_dossier_from_response(investigation: Investigation, response: str) -> None:
    lines = response.split("\n")
    for section_key in investigation.dossier.sections:
        display_name = section_key.replace("_", " ").title()
        patterns = [
            f"**{section_key}**",
            f"### {section_key}",
            f"## {section_key}",
            section_key,
            f"### {display_name}",
            f"## {display_name}",
            f"**{display_name}**",
        ]
        for pattern in patterns:
            captured = _capture_section(lines, pattern)
            if captured:
                investigation.dossier.update_section(section_key, captured)
                break


def _capture_section(lines: list[str], marker: str) -> str | None:
    marker_lower = marker.lower().strip()
    for i, line in enumerate(lines):
        if marker_lower == line.lower().strip() or line.lower().strip().startswith(marker_lower):
            captured: list[str] = []
            for l in lines[i + 1:]:
                stripped = l.strip()
                if not stripped:
                    if captured:
                        break
                    continue
                if stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
                    break
                if stripped.startswith("### ") or stripped.startswith("## "):
                    break
                if stripped == "---":
                    break
                captured.append(stripped)
            if captured:
                return "\n".join(captured)
    return None
