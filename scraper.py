import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import base64
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Realistic headers to bypass basic scraper protections
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

def extract_colors_from_css(css_text):
    """Extract color hexes, rgb, and hsl strings from CSS text."""
    colors = set()
    # Hex colors (3, 4, 6, or 8 characters)
    hex_pattern = r'#(?:[0-9a-fA-F]{3,4}){1,2}\b'
    # rgb/rgba/hsl/hsla patterns
    fn_pattern = r'(?:rgba?|hsla?)\([^)]+\)'
    
    for match in re.findall(hex_pattern, css_text):
        colors.add(match.lower())
    for match in re.findall(fn_pattern, css_text):
        # Clean up whitespace inside functions
        cleaned = re.sub(r'\s+', ' ', match)
        colors.add(cleaned.lower())
        
    return list(colors)

def extract_css_variables(css_text):
    """Extract custom CSS properties (variables) representing colors/themes."""
    vars_dict = {}
    # Matches --variable-name: value;
    var_pattern = r'(--[a-zA-Z0-9_-]+)\s*:\s*([^;}\n]+)'
    for name, value in re.findall(var_pattern, css_text):
        cleaned_val = value.strip().lower()
        # Filter for values that look like colors (hex, rgb, hsl, or common names)
        if (cleaned_val.startswith('#') or 
            cleaned_val.startswith('rgb') or 
            cleaned_val.startswith('hsl') or 
            cleaned_val in ['black', 'white', 'transparent']):
            vars_dict[name.strip()] = cleaned_val
    return vars_dict

from pathlib import Path

async def download_and_save_image_locally(client, url, domain, img_name):
    """Download an image, save it locally inside static/scraped_images/{domain}/, 
    and return base64 string, local web path, and mime type."""
    try:
        response = await client.get(url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            if "image" in content_type:
                # Map content-type to file extension
                ext = "png"
                if "svg" in content_type:
                    ext = "svg"
                elif "webp" in content_type:
                    ext = "webp"
                elif "gif" in content_type:
                    ext = "gif"
                elif "jpeg" in content_type or "jpg" in content_type:
                    ext = "jpg"
                
                # Setup local directories inside static
                save_dir = Path("static") / "scraped_images" / domain
                save_dir.mkdir(parents=True, exist_ok=True)
                
                file_path = save_dir / f"{img_name}.{ext}"
                file_path.write_bytes(response.content)
                logger.info(f"Saved image locally: {file_path}")
                
                encoded = base64.b64encode(response.content).decode("utf-8")
                local_web_path = f"/scraped_images/{domain}/{img_name}.{ext}"
                
                return {
                    "url": url,
                    "mime_type": content_type,
                    "base64_data": encoded,
                    "local_path": local_web_path
                }
    except Exception as e:
        logger.warning(f"Failed to download/save image {url}: {e}")
    return None

async def scrape_product_page(url):
    """Scrapes a product website and returns structure, content, styles, and images."""
    parsed_url = urlparse(url)
    if not parsed_url.scheme:
        url = "https://" + url

    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.get(url, headers=HEADERS, timeout=15.0, follow_redirects=True)
            if response.status_code != 200:
                raise Exception(f"HTTP error: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to fetch URL {url}: {e}")
            raise Exception(f"Failed to fetch website content: {e}")

        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. Page Metadata
        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)
            
        meta_desc = ""
        og_image = ""
        og_title = ""
        meta_tags = []
        
        for tag in soup.find_all("meta"):
            name = tag.get("name", "").lower()
            prop = tag.get("property", "").lower()
            content = tag.get("content", "")
            
            if name == "description" or prop == "og:description":
                meta_desc = content
            if prop == "og:image" or name == "twitter:image":
                og_image = content
            if prop == "og:title" or name == "twitter:title":
                og_title = content
                
            if content and (name or prop):
                meta_tags.append({"key": name or prop, "value": content})
                
        # Fallback for title
        if not title:
            title = og_title or (soup.h1.get_text(strip=True) if soup.h1 else "")
            
        # 2. Text Structure (Headings, Paragraphs, Lists)
        headings = []
        for level in ["h1", "h2", "h3"]:
            for h in soup.find_all(level):
                headings.append({
                    "level": level,
                    "text": h.get_text(strip=True)
                })
                
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 20]
        
        lists = []
        for lst in soup.find_all(["ul", "ol"]):
            items = [li.get_text(strip=True) for li in lst.find_all("li") if len(li.get_text(strip=True)) > 5]
            if items:
                lists.append(items[:10]) # Cap list items per list
                
        # 3. CSS Styles & Colors
        css_content = []
        # Check inline styles
        for tag in soup.find_all(style=True):
            css_content.append(tag["style"])
        # Check style blocks
        for style_tag in soup.find_all("style"):
            if style_tag.string:
                css_content.append(style_tag.string)
                
        # Check external stylesheets (first 4 link tags only to avoid slow runs)
        stylesheet_tags = soup.find_all("link", rel="stylesheet")
        for link_tag in stylesheet_tags[:4]:
            href = link_tag.get("href", "")
            if href:
                css_url = urljoin(url, href)
                try:
                    css_resp = await client.get(css_url, headers=HEADERS, timeout=5.0)
                    if css_resp.status_code == 200:
                        css_content.append(css_resp.text)
                        logger.info(f"Scraped external stylesheet: {css_url}")
                except Exception as e:
                    logger.warning(f"Could not scrape external style {css_url}: {e}")
                
        full_css_text = "\n".join(css_content)
        colors = extract_colors_from_css(full_css_text)[:30] # Limit to top 30
        css_vars = extract_css_variables(full_css_text)
        
        # 4. Image Discovery (Logo & Hero)
        logo_url = None
        hero_url = None
        
        # Search for logo in images
        for img in soup.find_all("img"):
            # Handle standard src or lazy loaded sources
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
            alt = img.get("alt", "").lower()
            class_list = " ".join(img.get("class", [])).lower()
            img_id = img.get("id", "").lower()
            
            if not src or src.startswith("data:image"):
                continue
                
            # Logo heuristics
            if not logo_url:
                if "logo" in alt or "logo" in class_list or "logo" in img_id or "logo" in src.lower():
                    logo_url = urljoin(url, src)
                    
            # Hero heuristics (large size, containing hero class, or first image)
            if not hero_url:
                if "hero" in class_list or "hero" in img_id or "banner" in class_list or "banner" in src.lower():
                    hero_url = urljoin(url, src)
        
        # Fallback for logo: look for files named logo.svg / logo.png in the html
        if not logo_url:
            for a_tag in soup.find_all("a"):
                for img in a_tag.find_all("img"):
                    src = img.get("src") or img.get("data-src") or ""
                    if src and "logo" in src.lower():
                        logo_url = urljoin(url, src)
                        break
                if logo_url: break
                
        # Fallback for hero (use first image if hero heuristic fails)
        if not hero_url:
            all_imgs = []
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                if src and not src.startswith("data:image"):
                    all_imgs.append(src)
            if all_imgs:
                hero_url = urljoin(url, all_imgs[0])
                
        # Resolve OG image URL
        if og_image:
            og_image = urljoin(url, og_image)
            
        # Compile candidate list of images to fetch (remove duplicates and empty)
        images_to_fetch = []
        seen_images = set()
        
        for name, img_uri in [("logo", logo_url), ("hero", hero_url), ("og_image", og_image)]:
            if img_uri and img_uri not in seen_images:
                # Basic validation
                parsed_img = urlparse(img_uri)
                if parsed_img.scheme in ["http", "https"]:
                    images_to_fetch.append((name, img_uri))
                    seen_images.add(img_uri)
                    
        # Get clean domain for folder name
        domain_folder = parsed_url.hostname.replace("www.", "").replace(".", "_")
        
        # Download images and save locally
        scraped_images = {}
        for img_name, img_uri in images_to_fetch[:3]: # Cap at 3 images max
            logger.info(f"Downloading branding image asset ({img_name}): {img_uri}")
            img_data = await download_and_save_image_locally(client, img_uri, domain_folder, img_name)
            if img_data:
                scraped_images[img_name] = img_data
                
        # Capture full page screenshot via Microlink cloud API
        import urllib.parse
        try:
            encoded_url = urllib.parse.quote(url)
            screenshot_api_url = f"https://api.microlink.io?url={encoded_url}&screenshot=true&fullPage=true&meta=false&embed=screenshot.url"
            logger.info(f"Fetching full-page screenshot from Microlink: {screenshot_api_url}")
            
            # Download and save full page screenshot
            response_ss = await client.get(screenshot_api_url, headers=HEADERS, timeout=35.0, follow_redirects=True)
            if response_ss.status_code == 200:
                save_dir = Path("static") / "scraped_images" / domain_folder
                save_dir.mkdir(parents=True, exist_ok=True)
                file_path = save_dir / "screenshot.png"
                file_path.write_bytes(response_ss.content)
                logger.info(f"Saved full page screenshot locally: {file_path}")
                
                encoded = base64.b64encode(response_ss.content).decode("utf-8")
                local_web_path = f"/scraped_images/{domain_folder}/screenshot.png"
                
                scraped_images["full_page_screenshot"] = {
                    "url": screenshot_api_url,
                    "mime_type": "image/png",
                    "base64_data": encoded,
                    "local_path": local_web_path
                }
        except Exception as e:
            logger.warning(f"Failed to capture full-page screenshot via Microlink: {e}")
            
        # Clean text layout summary (paragraphs limit to first 30 for token efficiency)
        scraped_data = {
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "meta_tags": meta_tags[:20],
            "headings": headings[:25],
            "paragraphs": paragraphs[:30],
            "lists": lists[:15],
            "css_colors": colors,
            "css_variables": css_vars,
            "images": scraped_images
        }
        
        return scraped_data
