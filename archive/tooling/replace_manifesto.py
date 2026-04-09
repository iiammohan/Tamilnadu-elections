with open('public/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

with open('manifesto_generated.html', 'r', encoding='utf-8') as f:
    new_manifesto = f.read()

# Find and replace the old manifesto section
start_marker = '  <!-- MANIFESTO TAB -->'
end_marker = '  <!-- PARTIES TAB -->'

start_idx = html.find(start_marker)
end_idx = html.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("ERROR: Could not find manifesto section markers")
else:
    new_html = html[:start_idx] + new_manifesto + '\n\n' + html[end_idx:]
    with open('public/index.html', 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(f"Replaced manifesto section ({end_idx - start_idx} chars -> {len(new_manifesto)} chars)")
