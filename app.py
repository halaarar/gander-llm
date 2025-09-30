import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--brand", required=True)
parser.add_argument("--url", required=True)
parser.add_argument("--question", required=True)
parser.add_argument("--max-searches", type=int, default=0)
parser.add_argument("--max-sources", type=int, default=0)
args = parser.parse_args()

print("budgets:", {"max_searches": args.max_searches, "max_sources": args.max_sources})