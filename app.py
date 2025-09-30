import argparse
import json
import re
from urllib.parse import urlparse
import os
import requests

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

def call_model_answer(brand: str, url: str, question: str, model: str) -> str:
    """
    Call a chat-style model and return a clean, user-facing markdown answer.

    Reads the API key from the OPENAI_API_KEY environment variable.
    If anything fails, raises an exception so the caller can fall back.
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
        f"Brand: {brand}\n"
        f"Brand site: {url}\n"
        f"Question: {question}\n\n"
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

    resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Expect the first choice to contain the message content
    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Model returned empty content")
    return content.strip()



def main() -> None:
    args = parse_args()
    
    if args.use_model:
        try:
            human_text = call_model_answer(args.brand, args.url, args.question, args.model)
            model_name = args.model
        except Exception as e:
            # Fall back to placeholder so the CLI still works
            human_text = make_human_answer(args.brand, args.url, args.question)
            model_name = f"{args.model} (fallback: placeholder)"
    else:
        human_text = make_human_answer(args.brand, args.url, args.question)
    model_name = "placeholder"


    mentions = extract_mentions(human_text, args.brand)


    all_urls = extract_urls(human_text)



    owned, external = partition_owned(all_urls, args.url)

    sources_included = len(owned) + len(external)


    payload = {
        "human_response_markdown": human_text,
        "citations": all_urls,
        "mentions": mentions,
        "owned_sources": owned,
        "sources": external,
        "metadata": {
            "model": model_name,
            "budgets": {"max_searches": args.max_searches, "max_sources": args.max_sources},
            "usage": {"searches": 0, "sources_included": sources_included},
        }
    }
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()