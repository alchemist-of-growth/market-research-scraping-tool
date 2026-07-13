# IntelScrape — Product Strategy & Branding Intelligence Tool

IntelScrape is a standalone, web-based tool that reverse-engineers a company's product strategy, positioning, GTM motions, target personas, and visual styling by scraping its landing page.

---

## Key Features

1. **Deep Branding Scrape**: Downloads inline and external stylesheets to parse color themes, variables, and tags.
2. **Local Image Saving**: Downloads branding logo, hero images, and Open Graph banners and saves them locally (`static/scraped_images/`) to avoid CORS errors.
3. **Strategic GTM Analysis**: Integrates with Google Gemini to identify value propositions, core differentiator parameters, marketing funnel models, and detailed target persona cards.
4. **Interactive Dashboard**: A glassmorphic dark-theme UI with tabbed strategic results, localStorage history cache, and Markdown/JSON export capabilities.

---

## Getting Started

### 1. Configure the Gemini API Key
To run strategic analysis, the backend needs a Gemini API Key. You can set it in a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```
*(Alternatively, you can leave it blank and paste your key directly into the settings modal in the web interface).*

### 2. Install Dependencies
```bash
python3 -m pip install -r requirements.txt
```

### 3. Run the App
```bash
python3 main.py
```
Open `http://localhost:8000/` in your browser.

---

## Public Deployment

This application is ready to host on free hosting plans like Render's free tier. Both the FastAPI server and frontend files are served together, making deployment simple.

For step-by-step deploy instructions, see [deploy_guide.md](file:///Users/nishantagarwal/.gemini/antigravity/brain/4288e423-ed23-454b-9df3-b0148c2ac4dd/deploy_guide.md).
