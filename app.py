import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--brand", required=True)
parser.add_argument("--url", required=True)
parser.add_argument("--question", required=True)
args = parser.parse_args()

print("brand:", args.brand)
print("url:", args.url)
print("question:", args.question)