import re
from collections import Counter

with open('public/data.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract w21 winners
winners = re.findall(r'w21:"([^"]+)"', content)
pc = Counter(winners)

print("Current 2021 Winners in data.js:")
for party, count in sorted(pc.items(), key=lambda x: -x[1]):
    print(f"  {party}: {count}")
print(f"  TOTAL: {len(winners)}")

print("\nExpected 2021 TN Assembly Results:")
expected = {"DMK": 133, "AIADMK": 66, "INC": 18, "PMK": 5, "VCK": 4, "BJP": 4, "CPI(M)": 2, "CPI": 2}
for party, count in sorted(expected.items(), key=lambda x: -x[1]):
    actual = pc.get(party, 0)
    status = "OK" if actual == count else f"MISMATCH (got {actual})"
    print(f"  {party}: expected {count} -> {status}")

# List mismatched constituencies
print("\nDetailed check - constituencies where winner might be wrong:")
entries = re.findall(r'ac:(\d+),n:"([^"]+)",d:"([^"]+)".*?w21:"([^"]+)"', content)
# Known problematic patterns - parties that shouldn't have won in 2021
for ac, name, dist, w21 in entries:
    # Flag any party not in the known winners list
    if w21 not in expected:
        print(f"  AC {ac} {name}: winner={w21} (unexpected party)")
