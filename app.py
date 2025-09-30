import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--brand", required=True)
args = parser.parse_args()

print(args.brand)