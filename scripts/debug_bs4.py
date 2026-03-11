from bs4 import BeautifulSoup
import sys

html = open("/Users/mehmetkar/HERMES/hermes-apiaas/mock-site/index_broken.html").read()
soup = BeautifulSoup(html, "html.parser")
cards = soup.select(".ann-item")
print(f"Found {len(cards)} cards")

for i, card in enumerate(cards):
    title_el    = card.select_one(".item-heading a")
    excerpt_el  = card.select_one(".ann-excerpt")
    date_el     = card.select_one("time.item-date")
    dept_el     = card.select_one(".item-dept")
    badge_el    = card.select_one(".ann-category-badge")
    print(f"Card {i}: title_el={title_el}, excerpt_el={excerpt_el}, date_el={date_el}, dept_el={dept_el}, badge_el={badge_el}")
