import os
import logging
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
from dotenv import load_dotenv

from pathlib import Path

# Load local environment variables (if any)
load_dotenv()

# Load home directory .env (common location for user API credentials)
home_env = Path.home() / ".env"
if home_env.exists():
    load_dotenv(dotenv_path=home_env)


from scraper import scrape_product_page
from analyzer import analyze_website_strategy

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Product Intelligence & Strategy Scraping Tool",
    description="Analyze websites to reverse-engineer product positioning, GTM motions, target personas, and design styling."
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str

@app.post("/api/analyze")
async def analyze_url(request: AnalyzeRequest, x_gemini_api_key: Optional[str] = Header(None)):
    target_url = request.url.strip()
    if not target_url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")
        
    logger.info(f"Received analysis request for URL: {target_url}")
    
    # 1. Scrape the page
    try:
        scraped_data = await scrape_product_page(target_url)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to scrape target website: {str(e)}")
        
    # 2. Run strategic analysis
    try:
        analysis_result = await analyze_website_strategy(
            scraped_data, 
            custom_api_key=x_gemini_api_key
        )
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    # 3. Assemble and return results (including colors and image URLs for frontend visuals)
    # We remove large base64 image data from the response to save network bandwidth, 
    # but keep the image metadata (url) so the frontend can render them directly from the web!
    client_images = {}
    for name, img_info in scraped_data.get("images", {}).items():
        client_images[name] = img_info.get("local_path") or img_info.get("url")
        
    response_payload = {
        "url": scraped_data["url"],
        "title": scraped_data["title"],
        "meta_description": scraped_data["meta_description"],
        "colors": scraped_data["css_colors"],
        "css_variables": scraped_data["css_variables"],
        "images": client_images,
        "analysis": analysis_result
    }
    
    return response_payload

# Ensure the static files directory exists
os.makedirs("static", exist_ok=True)

# Mount static directory for frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Bind to PORT environment variable (Render standard) or default to 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
