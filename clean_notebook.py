#!/usr/bin/env python3
import re

# Read the converted notebook script
with open('changeguardian_script.py.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove IPython magic commands
content = re.sub(r"get_ipython\(\)\.system\([^)]+\)\n", "", content)
content = re.sub(r"get_ipython\(\)[^\n]*\n", "", content)

# Write clean version
with open('changeguardian_clean.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Clean script created: changeguardian_clean.py")
