import csv
import re

def clean(text):
    """Remove citation references like [web:31][web:121] from text."""
    if not text:
        return ''
    return re.sub(r'\[web:\d+\]', '', text).strip()

def process_csv(filepath):
    """Read CSV and return list of {field, policy, dmk, aiadmk, ntk, tvk}."""
    rows = []
    with open(filepath, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                'field': r['Field'].strip(),
                'policy': r['Policy'].strip(),
                'dmk': clean(r.get('DMK', '')),
                'aiadmk': clean(r.get('AIADMK', '')),
                'ntk': clean(r.get('NTK', '')),
                'tvk': clean(r.get('TVK', '')),
            })
    return rows

quant = process_csv('tn_2026_manifesto_quantifiable.csv')
ideo = process_csv('tn_2026_manifesto_ideological.csv')

print(f"Quantifiable: {len(quant)} rows across {len(set(r['field'] for r in quant))} fields")
print(f"Ideological: {len(ideo)} rows across {len(set(r['field'] for r in ideo))} fields")

# Print fields
print("\nQuantifiable fields:")
for f in dict.fromkeys(r['field'] for r in quant):
    policies = [r['policy'] for r in quant if r['field'] == f]
    print(f"  {f}: {policies}")

print("\nIdeological fields:")
for f in dict.fromkeys(r['field'] for r in ideo):
    policies = [r['policy'] for r in ideo if r['field'] == f]
    print(f"  {f}: {policies}")
