import csv
import re
import html

def clean(text):
    """Remove citation references and clean text."""
    if not text:
        return ''
    text = re.sub(r'\[web:\d+\]', '', text).strip()
    # Remove trailing periods if doubled
    text = re.sub(r'\.\s*$', '.', text)
    return text

def escape(text):
    """HTML-escape text."""
    return html.escape(text) if text else ''

def process_csv(filepath):
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

def cell_html(text):
    if not text:
        return '<td class="manifesto-empty">—</td>'
    return f'<td>{escape(text)}</td>'

def build_table(rows, table_id):
    """Build HTML table grouped by field."""
    lines = []
    lines.append(f'        <div class="manifesto-table-wrap">')
    lines.append(f'          <table class="manifesto-table" id="{table_id}">')
    lines.append(f'            <thead>')
    lines.append(f'              <tr>')
    lines.append(f'                <th class="mf-field-col">Category</th>')
    lines.append(f'                <th class="mf-policy-col">Policy Area</th>')
    lines.append(f'                <th><span class="party-dot" style="background:#c41e3a"></span> DMK</th>')
    lines.append(f'                <th><span class="party-dot" style="background:#0d8c3f"></span> AIADMK</th>')
    lines.append(f'                <th><span class="party-dot" style="background:#cc3300"></span> NTK</th>')
    lines.append(f'                <th><span class="party-dot" style="background:#5c2d91"></span> TVK</th>')
    lines.append(f'              </tr>')
    lines.append(f'            </thead>')
    lines.append(f'            <tbody>')

    # Group by field
    fields = list(dict.fromkeys(r['field'] for r in rows))
    for field in fields:
        field_rows = [r for r in rows if r['field'] == field]
        for i, r in enumerate(field_rows):
            lines.append(f'              <tr>')
            if i == 0:
                rowspan = f' rowspan="{len(field_rows)}"' if len(field_rows) > 1 else ''
                lines.append(f'                <td class="cat-cell"{rowspan}>{escape(field)}</td>')
            lines.append(f'                <td class="policy-cell">{escape(r["policy"])}</td>')
            lines.append(f'                {cell_html(r["dmk"])}')
            lines.append(f'                {cell_html(r["aiadmk"])}')
            lines.append(f'                {cell_html(r["ntk"])}')
            lines.append(f'                {cell_html(r["tvk"])}')
            lines.append(f'              </tr>')

    lines.append(f'            </tbody>')
    lines.append(f'          </table>')
    lines.append(f'        </div>')
    return '\n'.join(lines)

quant = process_csv('tn_2026_manifesto_quantifiable.csv')
ideo = process_csv('tn_2026_manifesto_ideological.csv')

quant_table = build_table(quant, 'manifestoQuantTable')
ideo_table = build_table(ideo, 'manifestoIdeoTable')

# Build complete manifesto section
manifesto_html = f'''  <!-- MANIFESTO TAB -->
  <section id="tab-manifesto" class="tab-content">
    <div class="manifesto-container">
      <h2 class="manifesto-heading">Party Manifestos — 2026 Tamil Nadu Elections</h2>
      <p class="manifesto-intro">Comprehensive comparison of election promises from all four major parties across quantifiable policy commitments and ideological positions.</p>

      <div class="manifesto-subtabs">
        <button class="manifesto-subtab active" onclick="switchManifestoTab('quantifiable')">Quantifiable Promises</button>
        <button class="manifesto-subtab" onclick="switchManifestoTab('ideological')">Ideological Positions</button>
      </div>

      <div id="manifesto-quantifiable" class="manifesto-section active">
        <h3 class="manifesto-section-title">Quantifiable Promises & Schemes</h3>
        <p class="manifesto-section-desc">Specific, measurable commitments — cash transfers, subsidies, infrastructure targets, employment numbers, and institutional schemes.</p>
{quant_table}
      </div>

      <div id="manifesto-ideological" class="manifesto-section">
        <h3 class="manifesto-section-title">Ideological & Vision Statements</h3>
        <p class="manifesto-section-desc">Broad ideological positions, identity narratives, governance philosophy, and aspirational goals that are not directly quantifiable.</p>
{ideo_table}
      </div>
    </div>
  </section>'''

with open('manifesto_generated.html', 'w', encoding='utf-8') as f:
    f.write(manifesto_html)

print(f"Generated manifesto HTML: {len(manifesto_html)} chars")
print(f"Quantifiable: {len(quant)} policy rows across {len(set(r['field'] for r in quant))} fields")
print(f"Ideological: {len(ideo)} policy rows across {len(set(r['field'] for r in ideo))} fields")
