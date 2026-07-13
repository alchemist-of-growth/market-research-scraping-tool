import asyncio
import json
from dotenv import load_dotenv
load_dotenv() # Load from .env

from scraper import scrape_product_page
from analyzer import analyze_website_strategy

async def test_flow():
    print("Starting full flow test against linear.app...")
    url = "https://linear.app"
    try:
        # 1. Scrape
        print("Scraping page data...")
        scraped_data = await scrape_product_page(url)
        print("Scrape complete.")
        
        # 2. Analyze
        print("Sending to Gemini for analysis (this might take a few seconds)...")
        analysis = await analyze_website_strategy(scraped_data)
        
        print("\n=== SUCCESS! Gemini Analysis Returned ===")
        print(json.dumps(analysis, indent=2))
        
    except Exception as e:
        print(f"\n--- FLOW TEST FAILED ---")
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_flow())
