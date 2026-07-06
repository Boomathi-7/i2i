import re

with open('src/styles.css', 'r') as f:
    css = f.read()

def replace_color(match):
    c = match.group(0).lower()
    
    if c in ['#1f618d', '#2980b9', '#3b82f6', '#1d4ed8', '#1e40af']:
        return '#ffca00'
    if c in ['#154360', '#1a5276', '#1e3a8a']:
        return '#b18a00'
    if c in ['#d6eaf8', '#eaf2f8', '#eff6ff', '#bfdbfe', '#ccfbf1', '#e0f2fe', '#bae6fd']:
        return '#ffe700'
    if c in ['#f4f6f7', '#fdfefe', '#eaeded', '#e5e8e8', '#d5d8dc', '#f2f4f4', '#fafbfb', '#f1f5f9', '#f8fafc']:
        return '#ebebeb'
    if c in ['#7f8c8d', '#566573', '#808b96', '#5d6d7e', '#64748b', '#475569', '#334155', '#cbd5e1', '#e2e8f0', '#94a3b8', '#888', '#999']:
        return '#a3a3a3'
    if c in ['#1c2833', '#2c3e50', '#1b2631', '#111827', '#374151']:
        return '#1a1a1a'
        
    return c

new_css = re.sub(r'#[0-9a-fA-F]{3,6}', replace_color, css)

# Fix button text colors for contrast on yellow background
new_css = new_css.replace('color: #ffffff;', 'color: #1a1a1a;')

with open('src/styles.css', 'w') as f:
    f.write(new_css)

print("Done")
