import argparse
import json
import re
from urllib.parse import urlparse

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


def main() -> None:
    args = parse_args()
    human_text = make_human_answer(args.brand, args.url, args.question)
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
            "model": "placeholder",
            "budgets": {"max_searches": args.max_searches, "max_sources": args.max_sources},
            "usage": {"searches": 0, "sources_included": sources_included},
        }
    }
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()