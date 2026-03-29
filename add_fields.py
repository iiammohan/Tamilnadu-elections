import re

with open('public/data.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Add tc:"" (TVK candidate) and nkc:"" (NTK candidate) before w21 in each entry
updated = content.replace(',w21:', ',tc:"",nkc:"",w21:')

with open('public/data.js', 'w', encoding='utf-8') as f:
    f.write(updated)

count = updated.count('tc:""')
print(f'Added tc and nkc fields to {count} entries')
