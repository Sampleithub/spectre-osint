from __future__ import annotations

import json
import socket
import dns.resolver
import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information about a person, company, email, or topic. Returns URLs and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {"type": "integer", "description": "Max results (1-10)", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch the readable text content from a URL. Use after web_search to get full page content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL to fetch"},
                    "max_chars": {"type": "integer", "description": "Max characters to return", "default": 5000},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_username",
            "description": "Check if a username exists on popular platforms. Returns which platforms have a profile for that username.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "The username to check"},
                },
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "whois_lookup",
            "description": "Look up WHOIS information for a domain name. Returns registrar, creation date, and registrant info if public.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "The domain name (e.g. example.com)"},
                },
                "required": ["domain"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dns_lookup",
            "description": "Look up DNS records (A, AAAA, MX, NS, TXT) for a domain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "The domain name"},
                },
                "required": ["domain"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_social",
            "description": "Search for a person's name across social media and professional platforms using web search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name to search for"},
                    "company": {"type": "string", "description": "Optional company name to narrow results"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_dossier",
            "description": "Submit a finding to be recorded in the investigation dossier. Call this whenever you discover a confirmed or highly likely fact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": [
                            "identity_resolution", "digital_footprint", "timeline",
                            "professional_intelligence", "network_map", "writing_style_analysis",
                            "business_intelligence", "technical_intelligence", "reputation_assessment",
                            "behavioral_patterns", "influence_analysis", "opportunity_analysis",
                            "verification", "unknowns",
                        ],
                        "description": "Which dossier section to update",
                    },
                    "content": {"type": "string", "description": "The finding text with source citations"},
                    "confidence": {"type": "integer", "description": "Confidence score 0-100", "default": 50},
                },
                "required": ["section", "content"],
            },
        },
    },
]


async def web_search(query: str, max_results: int = 5) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return json.dumps({"error": "No results found"})
        output = []
        for r in results:
            output.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })
        return json.dumps(output, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Search failed: {e}"})


async def web_fetch(url: str, max_chars: int = 5000) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = "\n".join(line for line in text.splitlines() if line.strip())
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[... truncated ...]"
        return json.dumps({"url": url, "content_length": len(text), "text": text})
    except Exception as e:
        return json.dumps({"error": f"Fetch failed: {e}"})


USERNAME_CHECK_SITES = {
    "GitHub": "https://github.com/{username}",
    "X (Twitter)": "https://x.com/{username}",
    "Reddit": "https://reddit.com/user/{username}",
    "Instagram": "https://instagram.com/{username}",
    "Medium": "https://medium.com/@{username}",
    "Dev.to": "https://dev.to/{username}",
    "Pinterest": "https://pinterest.com/{username}",
    "Twitch": "https://twitch.tv/{username}",
    "Mastodon.social": "https://mastodon.social/@{username}",
    "Keybase": "https://keybase.io/{username}",
    "SlideShare": "https://slideshare.net/{username}",
    "Wikipedia": "https://en.wikipedia.org/wiki/User:{username}",
}


async def check_username(username: str) -> str:
    results = []
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        for site, url_template in USERNAME_CHECK_SITES.items():
            url = url_template.format(username=username)
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    results.append({"platform": site, "url": url, "status": "found"})
                elif resp.status_code in (301, 302, 303):
                    results.append({"platform": site, "url": url, "status": "redirect", "location": resp.headers.get("location", "")})
                else:
                    results.append({"platform": site, "url": url, "status": "not_found"})
            except Exception as e:
                results.append({"platform": site, "url": url, "status": f"error: {e}"})
    found = [r for r in results if r["status"] == "found"]
    return json.dumps({"username": username, "total_checked": len(results), "found": len(found), "results": results}, indent=2)


async def whois_lookup(domain: str) -> str:
    try:
        import whois as whois_module
        w = whois_module.whois(domain)
        result = {
            "domain": domain,
            "registrar": w.registrar,
            "creation_date": str(w.creation_date) if w.creation_date else None,
            "expiration_date": str(w.expiration_date) if w.expiration_date else None,
            "name_servers": w.name_servers,
            "registrant_name": w.name,
            "registrant_org": w.org,
            "registrant_country": w.country,
            "emails": w.emails,
            "status": w.status,
        }
        return json.dumps({k: v for k, v in result.items() if v is not None}, indent=2, default=str)
    except ImportError:
        return json.dumps({"error": "python-whois not installed. Install with: pip install python-whois"})
    except Exception as e:
        return json.dumps({"error": f"WHOIS lookup failed: {e}"})


async def dns_lookup(domain: str) -> str:
    results = {}
    for record_type in ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]:
        try:
            answers = dns.resolver.resolve(domain, record_type, lifetime=10)
            results[record_type] = [str(r) for r in answers]
        except dns.resolver.NoAnswer:
            pass
        except dns.resolver.NXDOMAIN:
            return json.dumps({"error": f"Domain {domain} does not exist (NXDOMAIN)"})
        except Exception as e:
            results[record_type] = f"error: {e}"
    return json.dumps({"domain": domain, "records": results}, indent=2, default=str)


async def search_social(name: str, company: str | None = None) -> str:
    queries = [
        f'"{name}" LinkedIn profile',
        f'"{name}" Twitter OR X',
        f'"{name}" GitHub',
        f'"{name}" Facebook',
        f'"{name}" Reddit',
    ]
    if company:
        queries = [f"{q} {company}" for q in queries]
    results = []
    for q in queries:
        resp = await web_search(q, max_results=3)
        results.append({"query": q, "results": json.loads(resp)})
    return json.dumps({"name": name, "company": company, "searches": results}, indent=2, default=str)


TOOL_MAP = {
    "web_search": web_search,
    "web_fetch": web_fetch,
    "check_username": check_username,
    "whois_lookup": whois_lookup,
    "dns_lookup": dns_lookup,
    "search_social": search_social,
}
