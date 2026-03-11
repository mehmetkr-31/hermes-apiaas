import requests
import time
from typing import List, Optional
import sys

# API endpoint (Hacker News Scraper)
API_URL = "http://localhost:8001/"

def fetch_news():
    try:
        print("\n" + "="*60)
        print("  🕵️  HACKER NEWS LIVE DASHBOARD (via Weaver API)")
        print("="*60 + "\n")
        
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        news_items = response.json()
        
        # Sort by points (highest first)
        sorted_items = sorted(news_items, key=lambda x: (x.get('points') or 0), reverse=True)
        
        for i, item in enumerate(sorted_items[:15], 1):
            title = item.get('title', 'No Title')
            points = item.get('points', 0)
            url = item.get('url', '#')
            comments = item.get('comment_count', 0)
            
            # Color coding points
            point_color = "\033[92m" if points > 200 else "\033[93m" if points > 50 else "\033[0m"
            reset = "\033[0m"
            
            print(f"{i:2d}. {title}")
            print(f"    {point_color}★ {points} points{reset}  |  💬 {comments} comments")
            print(f"    🔗 {url[:80]}..." if len(url) > 80 else f"    🔗 {url}")
            print("-" * 40)
            
    except requests.exceptions.ConnectionError:
        print("\n  ❌ Hata: API sunucusu çalışmıyor!")
        print("  Lütfen şu komutu başka bir terminalde çalıştırın:")
        print("  cd agent && .venv/bin/python3 -m uvicorn scraper_generated:app --host 0.0.0.0 --port 8001")
    except Exception as e:
        print(f"\n  ❌ Beklenmedik bir hata oluştu: {e}")

if __name__ == "__main__":
    fetch_news()
