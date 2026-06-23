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

YOUR JOB: Perform OSINT investigations using the tools available to you.

## WORKFLOW
1. Start with a quick scan — do 2-3 searches to get an overview
2. Use web_search, check_username, search_social as your primary tools
3. Use web_fetch on the most promising links
4. Use update_dossier to record confirmed findings
5. Give a summary of what you found

## RULES
- Do 2-3 tool calls, then summarize — don't go too deep on the first pass
- The user will ask "go deeper" if they want more
- Distinguish: Confirmed | Highly likely | Possible | Unknown
- Cite your sources (include URLs)
- Never fabricate evidence"""

DEEP_DIVE_INSTRUCTION = """The user wants you to go deeper. Do more searches, check more platforms, dig into details you missed. Use all your tools. Do 3-5 more tool calls before summarizing."""


async def process_turn(investigation: Investigation, user_message: str) -> str:
    investigation.add_turn("user", user_message)

    if not investigation.messages:
        investigation.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Quick OSINT scan on: {investigation.target_type} = {investigation.target_value}. Do 2-3 searches and give me a summary."},
        ]
        return await _run_agent_loop(investigation, max_rounds=4)

    investigation.messages.append({"role": "user", "content": user_message})

    is_deep_dive = any(w in user_message.lower() for w in ["deeper", "deep dive", "more", "dig", "further", "continue", "keep going"])
    max_rounds = 8 if is_deep_dive else 4
    if is_deep_dive:
        investigation.messages.append({"role": "user", "content": DEEP_DIVE_INSTRUCTION})

    if len(investigation.messages) > 40:
        investigation.messages = investigation.messages[:1] + investigation.messages[-30:]

    return await _run_agent_loop(investigation, max_rounds)


async def _run_agent_loop(investigation: Investigation, max_rounds: int = 4) -> str:
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

        if round_count >= max_rounds:
            investigation.messages.append({
                "role": "user",
                "content": "Summarize what you found so far. Keep it concise.",
            })

    investigation.messages.append({
        "role": "assistant",
        "content": "Quick scan complete. Ask me to go deeper for more detail.",
    })
    return "Quick scan complete. Ask me to go deeper for more detail."
