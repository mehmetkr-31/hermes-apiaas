base = open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index.html").read()

# Make sure we're starting from a known state (the current layout in index.html):
# The current index.html has: announcement-card, ann-category-badge, item-heading, ann-excerpt, item-date, item-dept

working_html = base
working_html = working_html.replace('item-heading', 'ann-title')
working_html = working_html.replace('item-date', 'ann-date')
working_html = working_html.replace('item-dept', 'ann-department')
# These remain the same for working: announcement-card, ann-category-badge, ann-excerpt

broken_html = base
broken_html = broken_html.replace('announcement-card', 'ann-item')
broken_html = broken_html.replace('item-heading', 'ann-heading')
broken_html = broken_html.replace('ann-category-badge', 'ann-tag')
broken_html = broken_html.replace('ann-excerpt', 'ann-summary')
broken_html = broken_html.replace('item-date', 'ann-post-date')
broken_html = broken_html.replace('item-dept', 'ann-dept-label')

with open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index_working.html", "w") as f:
    f.write(working_html)

with open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index_broken.html", "w") as f:
    f.write(broken_html)

print("Files generated!")
