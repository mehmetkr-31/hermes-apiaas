import sys
import re

content = open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index_broken.html").read()

replacements = {
    "ann-item": "announcement-card",
    "ann-heading": "ann-title",
    "ann-tag": "ann-category-badge",
    "ann-summary": "ann-excerpt",
    "ann-post-date": "ann-date",
    "ann-dept-label": "ann-department"
}

for k, v in replacements.items():
    content = content.replace(k, v)

with open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index_working.html", "w") as f:
    f.write(content)

print("Reconstructed index_working.html")
