import argparse
import json

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

def main() -> None:
    args = parse_args()
    human_text = make_human_answer(args.brand, args.url, args.question)
    payload = {
        "human_response_markdown": human_text,
        "citations": [],
        "mentions": [],
        "owned_sources": [],
        "sources": [],
        "metadata": {
            "model": "placeholder",
            "budgets": {"max_searches": args.max_searches, "max_sources": args.max_sources},
            "usage": {"searches": 0, "sources_included": 0},
        },
        "inputs": {"brand": args.brand, "url": args.url, "question": args.question},
    }
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()