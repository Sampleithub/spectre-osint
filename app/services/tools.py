from __future__ import annotations

import asyncio
import json
import socket
import ssl
from typing import Any

import dns.resolver
import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

USERNAME_SITES: dict[str, str] = {
    # Social / Professional
    "LinkedIn": "https://www.linkedin.com/in/{username}",
    "X (Twitter)": "https://x.com/{username}",
    "Instagram": "https://www.instagram.com/{username}",
    "Facebook": "https://www.facebook.com/{username}",
    "GitHub": "https://github.com/{username}",
    "Reddit": "https://www.reddit.com/user/{username}",
    "YouTube": "https://www.youtube.com/@{username}",
    "TikTok": "https://www.tiktok.com/@{username}",
    "Snapchat": "https://www.snapchat.com/add/{username}",
    "Pinterest": "https://www.pinterest.com/{username}",
    "Twitch": "https://www.twitch.tv/{username}",
    "Mastodon.social": "https://mastodon.social/@{username}",
    "Bluesky": "https://bsky.app/profile/{username}",
    "Threads": "https://www.threads.net/@{username}",
    "Discord": "https://discord.com/users/{username}",
    # Tech / Developer
    "Stack Overflow": "https://stackoverflow.com/users/{username}",
    "Medium": "https://medium.com/@{username}",
    "Dev.to": "https://dev.to/{username}",
    "Hashnode": "https://hashnode.com/@{username}",
    "Kaggle": "https://www.kaggle.com/{username}",
    "Replit": "https://replit.com/@{username}",
    "CodePen": "https://codepen.io/{username}",
    "HackerRank": "https://www.hackerrank.com/{username}",
    "LeetCode": "https://leetcode.com/{username}",
    "Codeforces": "https://codeforces.com/profile/{username}",
    "GitLab": "https://gitlab.com/{username}",
    "Bitbucket": "https://bitbucket.org/{username}",
    "SourceForge": "https://sourceforge.net/u/{username}",
    "NPM": "https://www.npmjs.com/~{username}",
    "PyPI": "https://pypi.org/user/{username}",
    "Docker Hub": "https://hub.docker.com/u/{username}",
    # Creative / Design
    "Behance": "https://www.behance.net/{username}",
    "Dribbble": "https://dribbble.com/{username}",
    "Figma": "https://www.figma.com/@{username}",
    "ArtStation": "https://www.artstation.com/{username}",
    "DeviantArt": "https://www.deviantart.com/{username}",
    "SoundCloud": "https://soundcloud.com/{username}",
    "Spotify": "https://open.spotify.com/user/{username}",
    # Academic
    "ResearchGate": "https://www.researchgate.net/profile/{username}",
    "Google Scholar": "https://scholar.google.com/citations?user={username}",
    "ORCID": "https://orcid.org/{username}",
    "Academia.edu": "https://independent.academia.edu/{username}",
    # News / Content
    "Medium": "https://medium.com/@{username}",
    "Substack": "https://substack.com/@{username}",
    "Product Hunt": "https://www.producthunt.com/@{username}",
    "Hacker News": "https://news.ycombinator.com/user?id={username}",
    "Wikipedia": "https://en.wikipedia.org/wiki/User:{username}",
    "Keybase": "https://keybase.io/{username}",
    "Linktree": "https://linktr.ee/{username}",
    "About.me": "https://about.me/{username}",
    # Forums / Communities
    "Fiverr": "https://www.fiverr.com/{username}",
    "Upwork": "https://www.upwork.com/freelancers/{username}",
    "SlideShare": "https://www.slideshare.net/{username}",
    "Scribd": "https://www.scribd.com/{username}",
    "Patreon": "https://www.patreon.com/{username}",
    "Buy Me a Coffee": "https://www.buymeacoffee.com/{username}",
    "Kickstarter": "https://www.kickstarter.com/profile/{username}",
    "IndieGoGo": "https://www.indiegogo.com/individual/{username}",
    # Crypto / Web3
    "Etherscan": "https://etherscan.io/address/{username}",
    "GitCoin": "https://gitcoin.co/{username}",
}

COMMON_PLATFORMS = [
    "LinkedIn", "X (Twitter)", "Instagram", "Facebook", "GitHub", "Reddit",
    "YouTube", "TikTok", "Snapchat", "Twitch", "Bluesky", "Threads",
    "Stack Overflow", "Medium", "Dev.to", "Kaggle", "CodePen",
    "HackerRank", "LeetCode", "GitLab", "Behance", "Dribbble",
    "ResearchGate", "ORCID", "Product Hunt", "Hacker News",
    "Wikipedia", "Keybase", "SlideShare", "Patreon",
]

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "scan_username",
            "description": "Check if a username exists on 50+ platforms. Runs all checks in parallel and returns accounts found.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "The username to search for across platforms"},
                },
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_email",
            "description": "Find digital footprints for an email address. Searches for associated accounts, breach data, and web mentions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "The email address to investigate"},
                },
                "required": ["email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_domain",
            "description": "Perform comprehensive domain recon: DNS records, WHOIS, subdomains via cert transparency, tech stack, SSL cert info.",
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
            "name": "scan_person",
            "description": "Search for a person by name across social media, news, professional platforms, and web mentions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name of the person"},
                    "context": {"type": "string", "description": "Optional context like company, location, or role to narrow results"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deep_search",
            "description": "Run multiple searches on a topic to get comprehensive coverage. Ideal for finding mentions, articles, and buried info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results per search", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch and extract readable text from a URL.",
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
            "name": "save_finding",
            "description": "Record a finding in the dossier with confidence score. Call this when you discover verified or highly likely information.",
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
                    },
                    "content": {"type": "string", "description": "The finding with source URLs"},
                    "confidence": {"type": "integer", "description": "Confidence 0-100", "default": 70},
                },
                "required": ["section", "content"],
            },
        },
    },
]


async def scan_username(username: str) -> str:
    results: list[dict[str, Any]] = []
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(15)

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        async def check(site: str, url: str) -> None:
            async with sem:
                try:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                    status = "found" if resp.status_code == 200 else "redirect" if resp.status_code in (301, 302, 303, 307) else "not_found"
                    entry: dict[str, Any] = {"platform": site, "url": url, "status": status}
                    if status == "redirect":
                        entry["redirects_to"] = resp.headers.get("location", "")
                    async with lock:
                        results.append(entry)
                except (httpx.TimeoutException, httpx.ConnectError):
                    async with lock:
                        results.append({"platform": site, "url": url, "status": "timeout"})
                except Exception as e:
                    async with lock:
                        results.append({"platform": site, "url": url, "status": "error", "detail": str(e)[:100]})

        tasks = [check(site, url_template.format(username=username)) for site, url_template in USERNAME_SITES.items()]
        await asyncio.gather(*tasks, return_exceptions=True)

    found = [r for r in results if r["status"] == "found"]
    return json.dumps({
        "username": username,
        "total_checked": len(results),
        "accounts_found": len(found),
        "found_on": found,
        "all_results": results,
    }, indent=2, default=str)


async def scan_email(email: str) -> str:
    results: dict[str, Any] = {"email": email}

    # Check Have I Been Pwned
    breach_data: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", headers={"hibp-api-key": ""})
            if resp.status_code == 200:
                breaches = resp.json()
                for b in breaches:
                    breach_data.append({"name": b.get("Name", ""), "domain": b.get("Domain", ""), "date": b.get("BreachDate", ""), "data_classes": b.get("DataClasses", [])})
        except Exception:
            pass

        # Web search for the email
        web_findings: list[dict[str, Any]] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(f'"{email}"', max_results=10):
                    web_findings.append({"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")})
        except Exception:
            pass

        # Check if image at Gravatar
        gravatar_url = f"https://www.gravatar.com/avatar/{hash(email)}?d=404"
        has_gravatar = False
        try:
            resp = await client.get(gravatar_url)
            has_gravatar = resp.status_code == 200
        except Exception:
            pass

    results["breaches"] = breach_data
    results["web_mentions"] = web_findings[:10]
    results["has_gravatar"] = has_gravatar
    return json.dumps(results, indent=2, default=str)


async def scan_domain(domain: str) -> str:
    results: dict[str, Any] = {"domain": domain}

    # DNS records
    dns_records: dict[str, Any] = {}
    for record_type in ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]:
        try:
            answers = dns.resolver.resolve(domain, record_type, lifetime=10)
            dns_records[record_type] = [str(r) for r in answers]
        except dns.resolver.NoAnswer:
            pass
        except dns.resolver.NXDOMAIN:
            return json.dumps({"domain": domain, "error": "Domain does not exist"})
        except Exception as e:
            dns_records[record_type] = f"error: {e}"
    results["dns"] = dns_records

    # SSL certificate info
    ssl_info: dict[str, Any] = {}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                ssl_info["issuer"] = dict(cert.get("issuer", []))
                ssl_info["subject"] = dict(cert.get("subject", []))
                ssl_info["valid_from"] = cert.get("notBefore", "")
                ssl_info["valid_to"] = cert.get("notAfter", "")
                ssl_info["SANs"] = cert.get("subjectAltName", [])
    except Exception as e:
        ssl_info["error"] = str(e)[:100]
    results["ssl_cert"] = ssl_info

    # Subdomains via Certificate Transparency
    subdomains: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"https://crt.sh/?q=%25.{domain}&output=json")
            if resp.status_code == 200:
                entries = resp.json()
                seen = set()
                for entry in entries:
                    name = entry.get("name_value", "")
                    for sub in name.split("\n"):
                        sub = sub.strip().lower()
                        if sub.endswith(f".{domain}") and sub not in seen:
                            seen.add(sub)
                            subdomains.append(sub)
    except Exception:
        pass
    results["subdomains"] = sorted(set(subdomains))[:50]

    # WHOIS
    try:
        import whois as whois_module
        w = whois_module.whois(domain)
        results["whois"] = {
            "registrar": w.registrar,
            "creation_date": str(w.creation_date) if w.creation_date else None,
            "expiration_date": str(w.expiration_date) if w.expiration_date else None,
            "name_servers": w.name_servers,
            "registrant_org": w.org,
            "registrant_country": w.country,
            "emails": w.emails,
        }
    except ImportError:
        results["whois"] = "python-whois not installed"
    except Exception as e:
        results["whois"] = f"error: {e}"

    # Technology stack check
    tech: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(f"https://{domain}", headers={"User-Agent": "Mozilla/5.0"})
            headers = resp.headers
            if "server" in headers: tech.append(f"Server: {headers['server']}")
            if "x-powered-by" in headers: tech.append(f"Powered by: {headers['x-powered-by']}")
            cf = headers.get("cf-ray", "")
            if cf: tech.append("Cloudflare")
            soup = BeautifulSoup(resp.text, "html.parser")
            html = resp.text.lower()
            if "wp-content" in html: tech.append("WordPress")
            if "react" in html or "reactjs" in html: tech.append("React")
            if "next.js" in html or "_next" in html: tech.append("Next.js")
            if "laravel" in html: tech.append("Laravel")
            if "django" in html: tech.append("Django")
            if "shopify" in html: tech.append("Shopify")
    except Exception:
        pass
    results["technology"] = tech if tech else ["Unknown"]

    return json.dumps(results, indent=2, default=str)


async def scan_person(name: str, context: str | None = None) -> str:
    searches = [
        f'"{name}" LinkedIn',
        f'"{name}" site:twitter.com OR site:x.com',
        f'"{name}" GitHub',
        f'"{name}" site:reddit.com',
        f'"{name}" site:medium.com',
        f'"{name}" site:news.ycombinator.com',
        f'"{name}" site:youtube.com',
        f'"{name}" site:instagram.com',
        f'"{name}" site:facebook.com',
        f'"{name}" site:angel.co OR site:crunchbase.com',
        f'"{name}" news articles',
    ]
    if context:
        searches = [f'{s} {context}' for s in searches]

    all_results: list[dict[str, Any]] = []
    sem = asyncio.Semaphore(3)

    async def search_ddg(query: str) -> list[dict[str, Any]]:
        async with sem:
            try:
                with DDGS() as ddgs:
                    return [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")} for r in ddgs.text(query, max_results=5)]
            except Exception:
                return []

    tasks = [search_ddg(q) for q in searches]
    results_list = await asyncio.gather(*tasks)

    for query, results in zip(searches, results_list):
        all_results.append({"query": query, "results": results})

    return json.dumps({"name": name, "context": context, "searches": all_results}, indent=2, default=str)


async def deep_search(query: str, max_results: int = 5) -> str:
    all_results: list[dict[str, Any]] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                all_results.append({"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")})
    except Exception as e:
        return json.dumps({"error": f"Search failed: {e}"})
    return json.dumps({"query": query, "results": all_results}, indent=2, default=str)


async def web_fetch(url: str, max_chars: int = 5000) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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


TOOL_MAP: dict[str, Any] = {
    "scan_username": scan_username,
    "scan_email": scan_email,
    "scan_domain": scan_domain,
    "scan_person": scan_person,
    "deep_search": deep_search,
    "web_fetch": web_fetch,
}
