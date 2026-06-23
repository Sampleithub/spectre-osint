from __future__ import annotations

import asyncio
import json

from openai import RateLimitError

from app.config import config
from app.models.schemas import Investigation
from app.services.llm import llm
from app.services.tools import TOOL_DEFINITIONS, TOOL_MAP

SYSTEM_PROMPT = """You are Spectre OSINT — an elite Open-Source Intelligence analyst.

YOUR JOB: Find EVERY digital footprint for a target using your tools.

## CAPABILITIES
- scan_username(username) — Checks 50+ platforms for a username, returns all accounts found
- scan_email(email) — Checks breaches, Gravatar, and web mentions for an email
- scan_domain(domain) — Full domain recon: DNS, SSL, subdomains (via crt.sh), WHOIS, tech stack
- scan_person(name, context) — Searches social media, news, and professional sites for a person
- deep_search(query) — Broad web search for any topic
- web_fetch(url) — Read full page content
- save_finding(section, content, confidence) — Record findings in the dossier

## WORKFLOW
1. Start with the most relevant scan tool for the target type
2. Review results, identify promising leads
3. Use deep_search or web_fetch to dig deeper on specific findings
4. Call save_finding to record verified information
5. Present a comprehensive, organized summary

## OUTPUT FORMAT
Give your response in three sections:
**Summary** — What you found. Key facts only.
**Digital Footprint** — Organized list of all accounts, profiles, and mentions found with URLs.
**Next Steps** — What to investigate next or what's still unknown.

## RULES
- Always run at least one comprehensive scan before concluding
- Distinguish: Confirmed | Highly likely | Possible | Unknown
- Include URLs for every finding
- Be thorough — check multiple angles
- Never fabricate evidence"""


def _is_deep_dive_request(msg: str) -> bool:
    keywords = ["deeper", "deep dive", "more", "dig", "further", "continue", "keep going", "again", "another", "additional", "scan", "check"]
    return any(w in msg.lower() for w in keywords)


async def process_turn(investigation: Investigation, user_message: str) -> str:
    investigation.add_turn("user", user_message)

    if not investigation.messages:
        investigation.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Investigate this target and find all digital footprints: {investigation.target_type} = {investigation.target_value}"},
        ]
        return await _run_agent_loop(investigation, max_rounds=6)

    investigation.messages.append({"role": "user", "content": user_message})

    is_deep = _is_deep_dive_request(user_message)
    max_rounds = 8 if is_deep else 5

    if len(investigation.messages) > 40:
        investigation.messages = investigation.messages[:1] + investigation.messages[-30:]

    return await _run_agent_loop(investigation, max_rounds)


async def _run_agent_loop(investigation: Investigation, max_rounds: int = 6) -> str:
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

            if tool_name == "save_finding":
                section = args.get("section", "")
                content = args.get("content", "")
                confidence = args.get("confidence", 70)
                if section and content:
                    investigation.dossier.update_section(section, content)
                    if confidence:
                        investigation.dossier.confidence_scores[section] = confidence
                    result = json.dumps({"status": "saved", "section": section, "confidence": confidence})
                else:
                    result = json.dumps({"error": "Missing section or content"})
            else:
                fn = TOOL_MAP.get(tool_name)
                if fn is None:
                    result = json.dumps({"error": f"Unknown tool: {tool_name}"})
                else:
                    try:
                        result = await fn(**args)
                        if len(result) > 4000:
                            result = result[:4000] + "\n\n[... truncated ...]"
                    except Exception as e:
                        result = json.dumps({"error": str(e)})

            investigation.messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result if isinstance(result, str) else json.dumps(result),
            })

        if round_count >= max_rounds - 1:
            investigation.messages.append({
                "role": "user",
                "content": "You have enough data. Summarize all findings now with the digital footprint. Use save_finding for key entries.",
            })

    investigation.messages.append({
        "role": "assistant",
        "content": "Investigation complete. All findings have been saved to the dossier.",
    })
    return "Investigation complete. All findings have been saved to the dossier."
