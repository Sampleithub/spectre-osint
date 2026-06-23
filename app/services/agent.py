from __future__ import annotations

import asyncio
import json
from typing import Any

from openai import RateLimitError

from app.config import config
from app.models.schemas import Investigation
from app.services.llm import llm
from app.services.tools import TOOL_DEFINITIONS, TOOL_MAP

SYSTEM_PROMPT = """You are Spectre OSINT — an elite Open-Source Intelligence analyst.

YOUR JOB: Perform deep OSINT investigations autonomously using the tools available to you.

## WORKFLOW
1. ANALYZE the target and plan your investigation
2. Use web_search to find information
3. Use web_fetch to read details from promising pages
4. Use check_username to find accounts on social platforms
5. Use search_social to find a person across platforms
6. Use whois_lookup and dns_lookup for domain intelligence
7. Use update_dossier to record confirmed findings
8. Report your findings to the user with analysis

## DOSSIER SECTIONS (use update_dossier to fill these)
- identity_resolution — full name, aliases, age, occupation, education, location
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

## RULES
- Use at least 3-4 searches before concluding
- Cross-reference information across multiple sources
- Distinguish: Confirmed | Highly likely | Possible | Unknown
- Always cite your sources (include URLs)
- Never fabricate evidence
- Be thorough — dig deeper with follow-up searches
- When you have enough data, present a comprehensive summary"""


async def process_turn(investigation: Investigation, user_message: str) -> str:
    investigation.add_turn("user", user_message)

    if not investigation.messages:
        investigation.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Begin OSINT investigation on: {investigation.target_type} = {investigation.target_value}"},
        ]
        return await _run_agent_loop(investigation)

    investigation.messages.append({"role": "user", "content": user_message})
    investigation.add_turn("user", user_message)

    if len(investigation.messages) > 40:
        system = investigation.messages[:1]
        recent = investigation.messages[-30:]
        investigation.messages = system + recent

    return await _run_agent_loop(investigation)


async def _run_agent_loop(investigation: Investigation) -> str:
    max_rounds = 15
    round_count = 0

    while round_count < max_rounds:
        round_count += 1

        for attempt in range(3):
            try:
                response = await llm.client.chat.completions.create(
                    model=llm.model,
                    messages=investigation.messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                )
                break
            except RateLimitError:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

        msg = response.choices[0].message

        if not msg.tool_calls:
            investigation.messages.append({"role": "assistant", "content": msg.content or ""})
            investigation.add_turn("assistant", msg.content or "")
            return msg.content or ""

        investigation.messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            if tool_name == "update_dossier":
                section = args.get("section", "")
                content = args.get("content", "")
                confidence = args.get("confidence", 50)
                if section and content:
                    investigation.dossier.update_section(section, content)
                    if confidence:
                        investigation.dossier.confidence_scores[section] = confidence
                    result = json.dumps({"status": "updated", "section": section, "confidence": confidence})
                else:
                    result = json.dumps({"error": "Missing section or content"})
            else:
                fn = TOOL_MAP.get(tool_name)
                if fn is None:
                    result = json.dumps({"error": f"Unknown tool: {tool_name}"})
                else:
                    try:
                        result = await fn(**args)
                        if len(result) > 3000:
                            result = result[:3000] + "\n\n[... truncated ...]"
                    except Exception as e:
                        result = json.dumps({"error": str(e)})

            investigation.messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result if isinstance(result, str) else json.dumps(result),
            })

        if round_count >= max_rounds - 2:
            investigation.messages.append({
                "role": "user",
                "content": "You have enough data. Summarize your findings now and submit to dossier. Do not do more searches.",
            })

    investigation.messages.append({
        "role": "assistant",
        "content": "Investigation reached maximum depth. Here is what I found so far.",
    })
    return "Investigation reached maximum depth."
