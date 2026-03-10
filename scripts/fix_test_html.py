import sys
import re

base_html = open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index.html").read()

# Let's standardize the base HTML so we can generate both versions from it
v1_replacements = {
    r'class="(announcement-card|ann-item)"': 'class="announcement-card"',
    r'class="(item-heading|ann-title|ann-heading)"': 'class="ann-title"',
    r'class="(ann-category-badge|ann-tag|badge-\w+)': lambda m: m.group(0) if 'badge-' in m.group(0) else 'class="ann-category-badge',
    r'class="ann-category-badge badge': 'class="ann-category-badge badge', # fix spacing if needed
    r'class="(ann-excerpt|ann-summary)"': 'class="ann-excerpt"',
    r'class="(item-date|ann-date|ann-post-date)"': 'class="ann-date"',
    r'class="(item-dept|ann-department|ann-dept-label)"': 'class="ann-department"'
}

working_html = base_html
for pattern, repl in v1_replacements.items():
    if callable(repl):
        working_html = re.sub(pattern, repl, working_html)
    else:
        working_html = re.sub(pattern, repl, working_html)
        
# For badge issue:
working_html = re.sub(r'class="ann-tag badge-', r'class="ann-category-badge badge-', working_html)
working_html = re.sub(r'class="ann-category-badge badge-', r'class="ann-category-badge badge-', working_html)

with open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index_working.html", "w") as f:
    f.write(working_html)

# Now v2 definition
v2_replacements = {
    r'class="announcement-card"': 'class="ann-item"',
    r'class="ann-title"': 'class="ann-heading"',
    r'class="ann-category-badge badge-': 'class="ann-tag badge-',
    r'class="ann-excerpt"': 'class="ann-summary"',
    r'class="ann-date"': 'class="ann-post-date"',
    r'class="ann-department"': 'class="ann-dept-label"'
}

broken_html = working_html
for pattern, repl in v2_replacements.items():
    broken_html = re.sub(pattern, repl, broken_html)

with open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index_broken.html", "w") as f:
    f.write(broken_html)

print("Recreated index_working.html and index_broken.html perfectly!")
