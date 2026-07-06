import re

with open('src/styles.css', 'r') as f:
    css = f.read()

def replace_color(match):
    c = match.group(0).lower()
    
    if c == '#ffca00':
        return '#6e8e75' # Soft Sage Green
    if c == '#b18a00':
        return '#4a6051' # Deep Pine
    if c == '#ffe700':
        return '#c0d6c5' # Light Sage (highlights)
    if c == '#ebebeb':
        return '#ebf0ec' # Pale Green Tinted Background
    if c == '#a3a3a3':
        return '#9cafa0' # Subtle Green-Gray (borders)
    if c == '#1a1a1a':
        return '#233027' # Dark muted green for text
        
    return c

new_css = re.sub(r'#[0-9a-fA-F]{3,6}', replace_color, css)

with open('src/styles.css', 'w') as f:
    f.write(new_css)

print("Done")
