import csv
import re

# Read TVK candidates (AC No -> Candidate)
tvk = {}
with open('tvk_tn_2026_full_list.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        ac = int(row['AC No'].strip())
        tvk[ac] = row['Candidate'].strip()

# Read NTK candidates (Constituency -> Candidate, need to map by constituency name)
ntk_by_name = {}
with open('ntk_tn_2026_clean_list.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = row['Constituency'].strip()
        ntk_by_name[name] = row['Candidate'].strip()

# Read data.js
with open('public/data.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract all entries to build AC->name mapping for NTK matching
ac_names = {}
for m in re.finditer(r'ac:(\d+),n:"([^"]+)"', content):
    ac_num = int(m.group(1))
    name = m.group(2)
    ac_names[ac_num] = name

# Build NTK by AC number (match by constituency name)
ntk = {}
unmatched_ntk = []
for ac_num, name in ac_names.items():
    # Try exact match first
    if name in ntk_by_name:
        ntk[ac_num] = ntk_by_name[name]
    else:
        # Try matching without parenthetical suffixes like (SC), (ST)
        clean_name = re.sub(r'\s*\(.*?\)', '', name).strip()
        found = False
        for ntk_name, candidate in ntk_by_name.items():
            clean_ntk = re.sub(r'\s*\(.*?\)', '', ntk_name).strip()
            if clean_name.lower() == clean_ntk.lower():
                ntk[ac_num] = candidate
                found = True
                break
        if not found:
            unmatched_ntk.append((ac_num, name))

print(f"TVK matched: {len(tvk)}/234")
print(f"NTK matched: {len(ntk)}/234")
if unmatched_ntk:
    print(f"\nUnmatched NTK ({len(unmatched_ntk)}):")
    for ac, name in sorted(unmatched_ntk):
        print(f"  AC {ac}: {name}")

# Apply TVK candidates
updated = content
for ac_num, candidate in tvk.items():
    # Escape special chars for the candidate name
    safe_candidate = candidate.replace('"', '\\"')
    pattern = f'ac:{ac_num},'
    old_tc = f'tc:""'
    new_tc = f'tc:"{safe_candidate}"'
    # Find the line with this AC and replace tc:"" with tc:"Name"
    lines = updated.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith(f'{{ac:{ac_num},') or f',ac:{ac_num},' in line or line.strip().startswith(f'ac:{ac_num},'):
            if f'ac:{ac_num},' in line:
                lines[i] = line.replace('tc:""', f'tc:"{safe_candidate}"', 1)
                break
    updated = '\n'.join(lines)

# Apply NTK candidates
for ac_num, candidate in ntk.items():
    safe_candidate = candidate.replace('"', '\\"')
    lines = updated.split('\n')
    for i, line in enumerate(lines):
        if f'ac:{ac_num},' in line:
            lines[i] = line.replace('nkc:""', f'nkc:"{safe_candidate}"', 1)
            break
    updated = '\n'.join(lines)

with open('public/data.js', 'w', encoding='utf-8') as f:
    f.write(updated)

# Verify
tvk_filled = len(re.findall(r'tc:"[^"]+[^"]"', updated))
ntk_filled = len(re.findall(r'nkc:"[^"]+[^"]"', updated))
tvk_empty = updated.count('tc:""')
ntk_empty = updated.count('nkc:""')
print(f"\nResult: TVK filled={tvk_filled}, empty={tvk_empty}")
print(f"Result: NTK filled={ntk_filled}, empty={ntk_empty}")
