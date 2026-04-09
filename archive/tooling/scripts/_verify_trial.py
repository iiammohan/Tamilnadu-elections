"""Quick verification of trial scrape output."""
import json
from collections import Counter

with open("public/data/tn2026_all_candidates.json") as f:
    data = json.load(f)

print(f"Total: {len(data)} candidates\n")

# Check keys
print("Fields:", list(data[0].keys()))
print()

ac_counts = Counter(c["ac_name"] for c in data)
for ac, count in ac_counts.items():
    print(f"  {ac}: {count} candidates")

print("\nSample candidates:")
for c in data[:5]:
    print(f"  {c['name']} | {c['party_name']} ({c['party_code']}) | age={c.get('age')} | gender={c.get('gender')}")

print("\nField completeness:")
for f in ["age", "gender", "photo_url", "party_code", "affidavit_pdf_url"]:
    filled = sum(1 for c in data if c.get(f))
    print(f"  {f}: {filled}/{len(data)}")

print("\nParty code distribution:")
party_counts = Counter(c["party_code"] for c in data)
for p, cnt in party_counts.most_common():
    print(f"  {p}: {cnt}")
