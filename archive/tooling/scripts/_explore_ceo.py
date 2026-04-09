"""ECI: Dump raw HTML structure of one profile + check affidavit download."""
import requests, urllib3, re
from bs4 import BeautifulSoup
urllib3.disable_warnings()

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
})
BASE = 'https://affidavit.eci.gov.in'

# Get CSRF + filter to Sulur page 1
r = s.get(BASE, verify=False, timeout=30)
csrf = BeautifulSoup(r.text, 'lxml').find('meta', {'name': 'csrf-token'})['content']

r2 = s.post(f'{BASE}/CandidateCustomFilter', data={
    '_token': csrf,
    'electionType': '32-AC-GENERAL-3-60',
    'election': '32-AC-GENERAL-3-60 ',
    'states': 'S22', 'phase': '2', 'constId': '116',
}, verify=False, timeout=30)
soup2 = BeautifulSoup(r2.text, 'lxml')

# Get first profile URL  
profile_url = soup2.find('a', href=re.compile(r'show-profile'))['href']
print(f'Profile URL: {profile_url[:80]}')

# Fetch profile page
rp = s.get(profile_url, verify=False, timeout=30)
sp = BeautifulSoup(rp.text, 'lxml')

# Raw HTML dump of main content area
main = sp.find('div', class_=re.compile(r'container|content|main'))
if not main:
    main = sp.find('body')

# Print structure: tag, class, text for first-level divs
print('\n=== Page structure (depth 2) ===')
for child in sp.find('body').find_all(recursive=False):
    tag = child.name
    cls = child.get('class', [])
    txt = child.get_text(' ', strip=True)[:80]
    print(f'<{tag} class="{" ".join(cls)}">{txt}')

# Find the candidate card/details section
print('\n=== All divs with class containing "card" or "col" or "row" ===')
for div in sp.find_all('div', class_=re.compile(r'card|detail|profile|info')):
    cls = ' '.join(div.get('class', []))
    direct_text = ''
    for child in div.children:
        if hasattr(child, 'name') and child.name:
            ctxt = child.get_text(' ', strip=True)[:60]
            cname = child.name
            ccls = ' '.join(child.get('class', []))
            if ctxt:
                direct_text += f'\n    <{cname} class="{ccls}">{ctxt}'
    if direct_text:
        print(f'\n  <div class="{cls}">{direct_text}')

# Also check the listing table row structure for party extraction
print('\n=== Listing table row raw HTML (first row) ===')
table = soup2.find('table', id='data-tab')
if table:
    rows = table.find_all('tr')
    if len(rows) > 1:
        # Dump the raw HTML of first data row
        raw = str(rows[1])[:2000]
        print(raw)

# Check affidavit download: look for download URL patterns
print('\n=== Profile page: all links ===')
for a in sp.find_all('a', href=True):
    href = a['href']
    txt = a.text.strip()[:40]
    onclick = a.get('onclick', '')[:80]
    data_attrs = {k: v for k, v in a.attrs.items() if k.startswith('data-')}
    if href != '#' and 'javascript:void(0)' not in href:
        print(f'  href={href[:100]} text="{txt}" onclick="{onclick}" data={data_attrs}')
    elif onclick or data_attrs:
        print(f'  href={href[:30]} text="{txt}" onclick="{onclick}" data={data_attrs}')

# Check for any modals or hidden sections
print('\n=== Hidden/modal sections ===')
for div in sp.find_all('div', class_=re.compile(r'modal|hidden|collapse|tab-pane')):
    cls = ' '.join(div.get('class', []))
    txt = div.get_text(' ', strip=True)[:150]
    print(f'  <div class="{cls}">{txt[:120]}')

