base = open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index.html").read()

# We need index_working.html to match scraper_v1.py:
# .announcement-card
# .ann-title a
# .ann-category-badge
# .ann-excerpt
# time.ann-date
# .ann-department

working_html = base
working_html = working_html.replace('ann-item', 'announcement-card')
working_html = working_html.replace('ann-heading', 'ann-title')
working_html = working_html.replace('item-heading', 'ann-title')
working_html = working_html.replace('ann-tag', 'ann-category-badge')
working_html = working_html.replace('ann-summary', 'ann-excerpt')
working_html = working_html.replace('ann-post-date', 'ann-date')
working_html = working_html.replace('item-date', 'ann-date')
working_html = working_html.replace('ann-dept-label', 'ann-department')
working_html = working_html.replace('item-dept', 'ann-department')

# We need index_broken.html to match scraper_v2.py:
# .ann-item
# .item-heading a
# .ann-category-badge
# .ann-excerpt
# time.item-date
# .item-dept

broken_html = base
broken_html = broken_html.replace('announcement-card', 'ann-item')
broken_html = broken_html.replace('ann-title', 'item-heading')
broken_html = broken_html.replace('item-heading', 'item-heading')
broken_html = broken_html.replace('item-date', 'item-date')
broken_html = broken_html.replace('ann-date', 'item-date')
broken_html = broken_html.replace('ann-department', 'item-dept')
broken_html = broken_html.replace('item-dept', 'item-dept')

# Revert any badges and excerpts back to normal just in case my previous scripts broke them
broken_html = broken_html.replace('ann-tag', 'ann-category-badge')
broken_html = broken_html.replace('ann-summary', 'ann-excerpt')

with open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index_working.html", "w") as f:
    f.write(working_html)

with open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index_broken.html", "w") as f:
    f.write(broken_html)

with open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index_working_backup.html", "w") as f:
    f.write(working_html)

with open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index.html", "w") as f:
    f.write(working_html)

print("Files generated and normalized!")
