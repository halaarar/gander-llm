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
    
def registrable_domain(host: str) -> str:
    """
    Approximate the brand's base domain by using the host as-is.
    For this exercise, we treat 'gandergeo.com' as the brand domain and
    any subdomain like 'sub.gandergeo.com' as owned.
    """
    return host 


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

def call_model_answer(brand: str, url: str, question: str, model: str, timeout: int = 30, retries: int = 2) -> str:
    """
    Call a chat-style model with small retry/backoff on 429/5xx.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable")

    endpoint = "https://api.openai.com/v1/chat/completions"

    system_msg = (
        "You are a helpful assistant. Write a concise, user-facing answer in markdown. "
        "Do not include prompts, system messages, or developer notes. "
        "If you include links, keep them natural."
    )
    user_msg = (
        f"Brand: {brand}\nBrand site: {url}\nQuestion: {question}\n\n"
        "Answer like a normal chat assistant for an average user."
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

def call_ollama_answer(brand: str, url: str, question: str, model: str, timeout: int = 30, retries: int = 2) -> str:
    """
    Call a local Ollama model and return a concise, user-facing markdown answer.
    Uses the /api/generate endpoint for a simple prompt. No API key required.
    """
    endpoint = "http://localhost:11434/api/generate"
    # Simple, explicit prompt
    prompt = (
        "You are a helpful assistant. Write a concise, user-facing answer in markdown.\n"
        "Do not include system prompts or developer notes.\n"
        f"Brand: {brand}\n"
        f"Brand site: {url}\n"
        f"Question: {question}\n"
        "Answer clearly. If you include links, keep them natural.\n"
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


def main() -> None:
    args = parse_args()
    
    if args.use_model:
        try:
            if args.provider == "ollama":
                human_text = call_ollama_answer(
                    args.brand, args.url, args.question, args.ollama_model,
                    timeout=args.timeout, retries=args.retries
                )
                model_name = f"ollama:{args.ollama_model}"
            else:
                human_text = call_model_answer(
                    args.brand, args.url, args.question, args.model,
                    timeout=args.timeout, retries=args.retries
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



    mentions = extract_mentions(human_text, args.brand)


    all_urls = extract_urls(human_text)



    owned, external = partition_owned(all_urls, args.url)



    payload = {
        "human_response_markdown": human_text,
        "citations": all_urls,
        "mentions": mentions,
        "owned_sources": owned,
        "sources": external,
        "metadata": {
            "model": model_name,
            "budgets": {"max_searches": args.max_searches, "max_sources": args.max_sources},
            "usage": {
                "searches": 0, # no web searches yet
                "sources_included": 0}, # Did not include any source snippets in context
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