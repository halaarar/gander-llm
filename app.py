import argparse
import json
import re
from urllib.parse import urlparse
import os
import requests
from dotenv import load_dotenv
load_dotenv() 
import sys
import time
import random
import html
from urllib.parse import quote_plus

def extract_urls(text: str) -> list[str]:
    """
    Return all http(s) URLs in reading order, with common trailing punctuation removed. 
    """
    raw = re.findall(r"https?://[^\s)>\]]+", text)
    cleaned = [u.rstrip(".,;:!?") for u in raw ]
    seen = {}
    for u in cleaned:
        if u not in seen:
            seen[u] = True
    return list(seen.keys())

def host_of(url: str) -> str:
    """
    Return the lowercased hostname of a URL, or empty string on failure.
    """
    try:
        host = urlparse(url).netloc.strip().lower()
        # Remove leading 'www.' to normalize common patterns
        if host.startswith("www."):
            host = host[4:]
        return host.lstrip(".")
    except Exception:
        return ""
    
def is_owned(host: str, brand_host: str) -> bool:
    """
    A URL is owned if its host equals the brand host
    or is a subdomain of the brand host.
    """
    if not host or not brand_host:
        return False
    if host == brand_host:
        return True
    return host.endswith("." + brand_host)
    


def partition_owned(urls: list[str], brand_site_url: str) -> tuple[list[str], list[str]]:
    """
    Split URLs into owned vs external using host equality or subdomain checks.
    """
    brand_host = host_of(brand_site_url)
    owned: list[str] = []
    external: list[str] = []
    for u in urls:
        h = host_of(u)
        if is_owned(h, brand_host):
            owned.append(u)
        else:
            external.append(u)
    # De-duplicate while preserving order
    owned = list(dict.fromkeys(owned))
    external = list(dict.fromkeys(external))
    return owned, external


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal CLI that prints a single JSON payload.")
    parser.add_argument("--brand", required=True, help="Brand name.")
    parser.add_argument("--url", required=True, help="Brand's website URL.")
    parser.add_argument("--question", required=True, help="End-user question.")
    parser.add_argument("--max-searches", type=int, default=0, help="Hard cap on web searches to perform.")
    parser.add_argument("--max-sources", type=int, default=0, help="Hard cap on sources to include.")
    
    parser.add_argument("--use-model", type=int, default=0, help="1 to call the model, 0 to use placeholder.")
    parser.add_argument("--model", default="gpt-4o", help="Model name to use if --use-model=1.")
    parser.add_argument("--output", help="If set, write the JSON to this file path.")
    parser.add_argument("--debug", action="store_true", help="Print errors to stderr.")
    parser.add_argument("--retries", type=int, default=2, help="Retries on 429/5xx.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds.")
    parser.add_argument("--provider", choices=["ollama", "openai"], default="ollama", help="Model provider: local Ollama (default) or OpenAI.") 
    parser.add_argument("--ollama-model", default="llama3.2", help="Ollama model name to use when --provider=ollama.")
    parser.add_argument("--ground", type=int, default=0, help="1 to ground the answer with web snippets.")
    parser.add_argument("--search-query", default=None, help="Override the auto search query.")
    parser.add_argument("--snippet-chars", type=int, default=600, help="Max characters per snippet.")
    parser.add_argument("--must-link-site", action="store_true", help="If set, ensure the brand URL appears once in the final answer.")
    parser.add_argument("--compact-prompt", type=int, default=1, help="1 to use compact instructions to save tokens; 0 for verbose.")

    return parser.parse_args()

def make_human_answer(brand: str, url: str, question: str) -> str:
    """
    Return a short, user-facing answer string for early testing.
    """
    return (
        f"Here is a quick answer about {brand}.\n\n"
        f"For details, see the official site: {url}\n"
        f"You might also compare third-party perspectives at https://example.org/review.\n"
    )

def extract_mentions(text: str, brand: str) -> list[str]:
    """
    Return each exact-case occurrence of the brand as a whole word.
    Deterministic and easy to explain.
    """
    if not brand:
        return []
    pattern = r"\b" + re.escape(brand) + r"\b"
    return re.findall(pattern, text)

import time
import random

def call_model_answer(brand: str, url: str, question: str, model: str,
                      timeout: int = 30, retries: int = 2, context: str = "", compact: bool = True) -> str:
    """
    Call a chat-style model with small retry/backoff on 429/5xx.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable")

    endpoint = "https://api.openai.com/v1/chat/completions"


    if compact:
        system_msg = "You are helpful. Answer in concise markdown."
    else:
        system_msg = ("You are a helpful assistant. Write a concise, user-facing answer in markdown. "
                    "Do not include prompts, system messages, or developer notes. "
                    "If you include links, keep them natural.")

    context_block = f"Context from sources:\n---\n{context}\n---\n" if context else ""
    user_msg = (
        f"{context_block}"
        f"Brand: {brand}\n"
        f"Brand site: {url}\n"
        f"Question: {question}\n\n"
        "If the context is insufficient, stay high-level and avoid invented details."
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    attempt = 0
    while True:
        attempt += 1
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        if resp.status_code in (429, 500, 502, 503, 504):
            if attempt > max(0, retries):
                resp.raise_for_status()
            # Exponential backoff with jitter: 0.5, 1, 2 sec (plus a tiny random)
            sleep_s = min(2.0, 0.5 * (2 ** (attempt - 1))) + random.random() * 0.1
            time.sleep(sleep_s)
            continue

        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Model returned empty content")
        return content.strip()

def call_ollama_answer(brand: str, url: str, question: str, model: str,
                       timeout: int = 30, retries: int = 2, context: str = "", compact: bool = True) -> str:
    """
    Call a local Ollama model and return a concise, user-facing markdown answer.
    Uses the /api/generate endpoint for a simple prompt. No API key required.
    """
    endpoint = "http://localhost:11434/api/generate"

    context_block = f"Context from sources:\n---\n{context}\n---\n" if context else ""
    if compact:
        lead = "Answer concisely in markdown."
    else:
        lead = ("You are a helpful assistant. Write a concise, user-facing answer in markdown. "
                "Do not include system prompts or developer notes.")
    prompt = (
        f"{lead}\n"
        f"{context_block}"
        f"Brand: {brand}\n"
        f"Brand site: {url}\n"
        f"Question: {question}\n"
        "If the context is insufficient, stay high-level and avoid invented details.\n"
    )


    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }

    attempt = 0
    while True:
        attempt += 1
        resp = requests.post(endpoint, json=payload, timeout=timeout)
        # Ollama returns 200 on success; on failure, raise
        if resp.status_code in (500, 502, 503, 504):
            if attempt > max(0, retries):
                resp.raise_for_status()
            sleep_s = min(2.0, 0.5 * (2 ** (attempt - 1))) + random.random() * 0.1
            time.sleep(sleep_s)
            continue

        resp.raise_for_status()
        data = resp.json()
        content = data.get("response", "")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama returned empty content")
        return content.strip()

def ddg_search(query: str, timeout: int = 15) -> list[str]:
    """
    DuckDuckGo HTML search. Return a small list of *real* result URLs, not DDG redirects.
    - Decodes /l/?uddg= redirect targets
    - Filters out duckduckgo.com links
    - De-duplicates while preserving order
    """
    url = "https://duckduckgo.com/html/?q=" + quote_plus(query)
    headers = {"User-Agent": "curl/8"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    text = resp.text

    # Collect all hrefs (simple approach)
    candidates = re.findall(r'href="(https?://[^"]+)"', text)

    cleaned = []
    seen = set()
    for u in candidates:
        # If it is a DDG redirect like .../l/?uddg=ENCODED, extract target
        if "duckduckgo.com/l/?" in u or "duckduckgo.com/l/?".replace("/", "%2F") in u:
            m = re.search(r"[?&]uddg=([^&]+)", u)
            if m:
                try:
                    target = requests.utils.unquote(m.group(1))
                    u = target
                except Exception:
                    pass

        # Drop any duckduckgo.com host links
        if host_of(u).endswith("duckduckgo.com"):
            continue

        # Keep only real http(s) links
        if not u.startswith("http://") and not u.startswith("https://"):
            continue

        if u not in seen:
            seen.add(u)
            cleaned.append(u)

    return cleaned[:10]

def fetch_snippet(source_url: str, max_chars: int = 600, timeout: int = 15) -> str:
    """
    Fetch the page and return a compact snippet.
    Token optimization tactic: strip tags, collapse whitespace, hard length cap.
    """
    headers = {"User-Agent": "curl/8"}
    r = requests.get(source_url, headers=headers, timeout=timeout)
    r.raise_for_status()
    html_text = r.text

    # extract <title> and meta description if present
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        title = html.unescape(m.group(1)).strip()

    desc = ""
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html_text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        desc = html.unescape(m.group(1)).strip()

    # crude text fallback: remove tags and collapse whitespace
    text_only = re.sub(r"<[^>]+>", " ", html_text)
    text_only = re.sub(r"\s+", " ", html.unescape(text_only)).strip()

    parts = []
    if title:
        parts.append(f"TITLE: {title}")
    if desc:
        parts.append(f"DESCRIPTION: {desc}")
    if not desc and text_only:
        parts.append(f"BODY: {text_only[:max_chars]}")

    snippet = " ".join(parts)
    snippet = snippet[:max_chars]  # enforce hard cap
    return snippet

def build_context(snippets: list[tuple[str, str]]) -> str:
    """
    Join (url, snippet) pairs into a compact context block.
    Token optimization tactic: bullet list, no duplicated whitespace.
    """
    lines = []
    for url, snip in snippets:
        lines.append(f"- {url}\n  {snip}")
    return "\n".join(lines)

def main() -> None:
    args = parse_args()
    searches_used = 0
    sources_used = 0
    context_text = ""
    context_urls = []


    # Grounding pipeline guarded by budgets
    if args.ground and args.max_searches > 0 and args.max_sources > 0:
        # 1 search only (we respect the hard cap)
        q = args.search_query or f"{args.brand} {args.question}"
        results = ddg_search(q, timeout=args.timeout)
        searches_used = 1 if results else 0

    # Grounding pipeline guarded by budgets
    if args.ground and args.max_searches > 0 and args.max_sources > 0:
        q = args.search_query or f"{args.brand} {args.question}"
        results = ddg_search(q, timeout=args.timeout)

        # Count a search only if we actually got results
        searches_used = 1 if results else 0

        # Prefer brand-owned URLs first when we have results
        chosen = []
        if results:
            brand_host = host_of(args.url)
            owned_first, external_next = [], []
            seen = set()
            for u in results:
                if u in seen:
                    continue
                seen.add(u)
                if is_owned(host_of(u), brand_host):
                    owned_first.append(u)
                else:
                    external_next.append(u)
            ordered = owned_first + external_next
            chosen = ordered[: args.max_sources]
        else:
            # Fallback: no results. Use the brand site itself as context (does not count as a search).
            if args.max_sources > 0 and args.url:
                chosen = [args.url]

    # fetch trimmed snippets
    pairs = []
    for u in chosen:
        try:
            sn = fetch_snippet(u, max_chars=args.snippet_chars, timeout=args.timeout)
        except Exception:
            continue
        if sn:
            pairs.append((u, sn))

    context_urls = [u for (u, _snip) in pairs]
    sources_used = len(pairs)
    if pairs:
        context_text = build_context(pairs)



        # fetch trimmed snippets
        pairs = []

        for u in chosen:
            try:
                sn = fetch_snippet(u, max_chars=args.snippet_chars, timeout=args.timeout)
            except Exception:
                continue
            if sn:
                pairs.append((u, sn))
        context_urls = [u for (u, _snip) in pairs]
        sources_used = len(pairs)
        if pairs:
            context_text = build_context(pairs)


    use_compact = bool(args.compact_prompt)

    if args.use_model:
        try:
            if args.provider == "ollama":
                human_text = call_ollama_answer(
                    args.brand, args.url, args.question, args.ollama_model,
                    timeout=args.timeout, retries=args.retries, context=context_text, compact=use_compact
                )
                model_name = f"ollama:{args.ollama_model}"
            else:
                human_text = call_model_answer(
                    args.brand, args.url, args.question, args.model,
                    timeout=args.timeout, retries=args.retries, context=context_text, compact=use_compact
                )
                model_name = args.model
        except Exception as e:
            if args.debug:
                print(f"[model-error] {e}", file=sys.stderr)
            human_text = make_human_answer(args.brand, args.url, args.question)
            model_name = f"{args.provider} (fallback: placeholder)"
    else:
        human_text = make_human_answer(args.brand, args.url, args.question)
        model_name = "placeholder"


    if args.must_link_site and args.url and args.url not in human_text:
        human_text = human_text.rstrip() + f"\n\nFor details, see {args.url}\n"

    mentions = extract_mentions(human_text, args.brand)

    # URLs that appear in the final answer only
    citations = extract_urls(human_text)

    # Everything used to form the answer: answer links plus grounded context URLs
    used_urls = list(dict.fromkeys(citations + context_urls))

    owned, external = partition_owned(used_urls, args.url)



    payload = {
        "human_response_markdown": human_text,
        "citations": citations,
        "mentions": mentions,
        "owned_sources": owned,
        "sources": external,
        "metadata": {
            "model": model_name,
            "budgets": {"max_searches": args.max_searches, "max_sources": args.max_sources},
            "usage": {
                "searches": searches_used,
                "sources_included": sources_used
            },
        }
    }

    blob = json.dumps(payload, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(blob)
        print(args.output)
    else:
        print(blob)


if __name__ == "__main__":
    main()