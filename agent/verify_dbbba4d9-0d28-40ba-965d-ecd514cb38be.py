from api_dbbba4d9_0d28_40ba_965d_ecd514cb38be import scrape_data

data = scrape_data()
print(f'DATA_COUNT: {len(data)}')
assert len(data) > 0, "No data extracted! Check your selectors."

if len(data) > 0:
    print(f"��� SUCCESS: Extracted {len(data)} products")
    
    # Show sample data
    print("\nSample data:")
    for i, item in enumerate(data[:3]):
        print(f"  {i+1}. {item['title']} - {item['price']} ({item['url']})")
else:
    print("��� FAILED: No data extracted")