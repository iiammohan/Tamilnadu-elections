import csv
import re
import html as htmlmod

def clean(text):
    if not text:
        return ''
    return re.sub(r'\[web:\d+\]', '', text).strip()

def escape(text):
    return htmlmod.escape(text) if text else ''

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

PARTIES = [
    ('DMK', '#c41e3a', 'dmk'),
    ('AIADMK', '#0d8c3f', 'aiadmk'),
    ('NTK', '#cc3300', 'ntk'),
    ('TVK', '#5c2d91', 'tvk'),
]

def cell_html(text):
    if not text:
        return '<td class="manifesto-empty">\u2014</td>'
    return f'<td>{escape(text)}</td>'

def build_table(rows, table_id):
    lines = []
    lines.append('        <div class="manifesto-table-wrap">')
    lines.append(f'          <table class="manifesto-table" id="{table_id}">')
    lines.append('            <thead>')
    lines.append('              <tr>')
    lines.append('                <th class="mf-field-col">Category</th>')
    lines.append('                <th class="mf-policy-col">Policy Area</th>')
    for name, color, _ in PARTIES:
        lines.append(f'                <th><span class="party-dot" style="background:{color}"></span> {name}</th>')
    lines.append('              </tr>')
    lines.append('            </thead>')
    lines.append('            <tbody>')
    fields = list(dict.fromkeys(r['field'] for r in rows))
    for field in fields:
        field_rows = [r for r in rows if r['field'] == field]
        for i, r in enumerate(field_rows):
            lines.append('              <tr>')
            if i == 0:
                rowspan = f' rowspan="{len(field_rows)}"' if len(field_rows) > 1 else ''
                lines.append(f'                <td class="cat-cell"{rowspan}>{escape(field)}</td>')
            lines.append(f'                <td class="policy-cell">{escape(r["policy"])}</td>')
            lines.append(f'                {cell_html(r["dmk"])}')
            lines.append(f'                {cell_html(r["aiadmk"])}')
            lines.append(f'                {cell_html(r["ntk"])}')
            lines.append(f'                {cell_html(r["tvk"])}')
            lines.append('              </tr>')
    lines.append('            </tbody>')
    lines.append('          </table>')
    lines.append('        </div>')
    return '\n'.join(lines)

def build_cards(rows, cards_id):
    lines = []
    lines.append(f'        <div class="manifesto-cards" id="{cards_id}">')
    for r in rows:
        lines.append('          <div class="mf-card">')
        lines.append('            <div class="mf-card-header" onclick="this.parentElement.classList.toggle(\'open\')">')
        lines.append('              <div>')
        lines.append(f'                <div class="mf-card-field">{escape(r["field"])}</div>')
        lines.append(f'                <div class="mf-card-policy">{escape(r["policy"])}</div>')
        lines.append('              </div>')
        lines.append('              <span class="mf-card-toggle">\u25BC</span>')
        lines.append('            </div>')
        lines.append('            <div class="mf-card-body">')
        for name, color, key in PARTIES:
            text = r[key]
            if text:
                lines.append(f'              <div class="mf-party-row">')
                lines.append(f'                <div class="mf-party-label"><span class="party-dot" style="background:{color}"></span>{name}</div>')
                lines.append(f'                <div class="mf-party-text">{escape(text)}</div>')
                lines.append(f'              </div>')
            else:
                lines.append(f'              <div class="mf-party-row">')
                lines.append(f'                <div class="mf-party-label"><span class="party-dot" style="background:{color}"></span>{name}</div>')
                lines.append(f'                <div class="mf-party-text empty">No specific promise</div>')
                lines.append(f'              </div>')
        lines.append('            </div>')
        lines.append('          </div>')
    lines.append('        </div>')
    return '\n'.join(lines)

quant = process_csv('tn_2026_manifesto_quantifiable.csv')
ideo = process_csv('tn_2026_manifesto_ideological.csv')

# IMPORTANT: Check if DMK entry for "Curriculum / language / behavioural changes" needs the civic behaviour addition
# (This was added directly to index.html but the CSV may not have it)

quant_table = build_table(quant, 'manifestoQuantTable')
quant_cards = build_cards(quant, 'manifestoQuantCards')
ideo_table = build_table(ideo, 'manifestoIdeoTable')
ideo_cards = build_cards(ideo, 'manifestoIdeoCards')

manifesto_html = f'''  <!-- MANIFESTO TAB -->
  <section id="tab-manifesto" class="tab-content">
    <div class="manifesto-container">
      <h2 class="manifesto-heading">Party Manifestos \u2014 2026 Tamil Nadu Elections</h2>
      <p class="manifesto-intro">Comprehensive comparison of election promises from all four major parties across quantifiable policy commitments and ideological positions.</p>

      <div class="manifesto-subtabs">
        <button class="manifesto-subtab active" onclick="switchManifestoTab('quantifiable')">Quantifiable Promises</button>
        <button class="manifesto-subtab" onclick="switchManifestoTab('ideological')">Ideological Positions</button>
      </div>

      <div id="manifesto-quantifiable" class="manifesto-section active">
        <h3 class="manifesto-section-title">Quantifiable Promises &amp; Schemes</h3>
        <p class="manifesto-section-desc">Specific, measurable commitments \u2014 cash transfers, subsidies, infrastructure targets, employment numbers, and institutional schemes.</p>
{quant_table}
{quant_cards}
      </div>

      <div id="manifesto-ideological" class="manifesto-section">
        <h3 class="manifesto-section-title">Ideological &amp; Vision Statements</h3>
        <p class="manifesto-section-desc">Broad ideological positions, identity narratives, governance philosophy, and aspirational goals that are not directly quantifiable.</p>
{ideo_table}
{ideo_cards}
      </div>
    </div>
  </section>'''

with open('manifesto_generated.html', 'w', encoding='utf-8') as f:
    f.write(manifesto_html)

print(f"Generated: {len(manifesto_html)} chars")
print(f"Quant: {len(quant)} rows, Ideo: {len(ideo)} rows")
