import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument("--brand", required=True)
parser.add_argument("--url", required=True)
parser.add_argument("--question", required=True)
parser.add_argument("--max-searches", type=int, default=0)
parser.add_argument("--max-sources", type=int, default=0)
args = parser.parse_args()

payload = {
    "human_response_markdown": "",
    "citations": [],
    "mentions": [],
    "owned_sources": [],
    "sources": [],
    "metadata": {
        "model": "placeholder",
        "budgets": {"max_searches": args.max_searches, "max_sources": args.max_sources},
        "usage": {"searches": 0, "sources_included": 0},
    },
}
print(json.dumps(payload, indent=2))