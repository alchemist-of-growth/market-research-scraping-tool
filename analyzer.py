import os
import json
import base64
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)

# Prompt defining instructions for the Gemini model
SYSTEM_INSTRUCTION = """You are an elite product marketing manager, GTM strategist, and visual brand auditor.
Your job is to reverse-engineer a company's product strategy, positioning, and visual identity by analyzing its scraped website text, metadata, CSS colors, and key visual assets.

You must return a valid, parseable JSON document conforming strictly to the requested schema.
Do not wrap your output in markdown code blocks like ```json ... ```. Just return the raw JSON string.

Schema structure:
{
  "positioning": {
    "elevator_pitch": "One-sentence core value proposition.",
    "core_category": "The industry category this product dominates.",
    "differentiation": "What makes this product stand out from competitors."
  },
  "target_personas": [
    {
      "role": "Title of target persona (e.g. Tech Lead, Head of Growth).",
      "pain_points": ["Pain point 1", "Pain point 2"],
      "value_delivered": "How the product solves their problems specifically."
    }
  ],
  "value_propositions": [
    {
      "title": "Value prop header.",
      "description": "Short explanation of the benefit.",
      "supporting_features": ["Feature A", "Feature B"]
    }
  ],
  "gtm_strategy": {
    "gtm_motion": "Core motion: e.g. PLG (Product-Led Growth), Enterprise sales, Developer-centric self-serve, etc.",
    "pricing_strategy": "Summary of pricing tiers, trial presence, or transparency.",
    "conversion_tactics": ["Key call-to-actions", "Social proof triggers used"]
  },
  "messaging_strategy": {
    "hero_tagline": "The main tagline reverse-engineered or extracted.",
    "tone_of_voice": ["Adjective 1", "Adjective 2"],
    "communication_framework": "A summary of how they communicate (e.g., benefit-first, feature-first, problem-solution)."
  },
  "design_branding": {
    "color_palette_feedback": "Analysis of the brand color selections based on the CSS colors and images provided.",
    "visual_theme": "Description of the visual identity (e.g., sleek dark-mode, minimalist, warm illustrations).",
    "ux_ui_critique": "A professional analysis of page layout, sections, navigation flow, and conversion readability."
  }
}
"""

def generate_analysis_prompt(scraped_data):
    """Formats scraped website text and CSS data into a prompt for Gemini."""
    prompt = f"""Analyze this website data:
URL: {scraped_data.get('url')}
Title: {scraped_data.get('title')}
Meta Description: {scraped_data.get('meta_description')}

--- HEADINGS ---
"""
    for h in scraped_data.get("headings", []):
        prompt += f"- [{h['level'].upper()}] {h['text']}\n"
        
    prompt += "\n--- PARAGRAPHS & HIGHLIGHTS ---\n"
    for p in scraped_data.get("paragraphs", []):
        prompt += f"- {p}\n"
        
    prompt += "\n--- LIST ITEMS ---\n"
    for item_list in scraped_data.get("lists", []):
        prompt += f"- List: {', '.join(item_list)}\n"
        
    prompt += "\n--- CSS STYLE COLOR METADATA ---\n"
    prompt += f"CSS Extracted Colors: {', '.join(scraped_data.get('css_colors', []))}\n"
    
    css_vars = scraped_data.get("css_variables", {})
    if css_vars:
        prompt += "CSS Variables (Colors):\n"
        for k, v in css_vars.items():
            prompt += f"  {k}: {v}\n"
            
    prompt += "\nEvaluate the typography, design layout, imagery styles, UX flow, GTM strategy, value propositions, messaging pillars, and target personas using the provided data and the attached visual assets (like Logo, Hero image, or Open Graph banner)."
    return prompt

async def analyze_website_strategy(scraped_data, custom_api_key=None):
    """Sends website data and image assets to Gemini to reverse-engineer GTM and product strategy."""
    # Resolve API Key: Custom header key has priority, then backend env variable
    api_key = custom_api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise Exception("Gemini API key is not configured. Please set it in Settings (UI) or environment variables.")
        
    genai.configure(api_key=api_key)
    
    # We use gemini-3.1-flash-lite as it is highly efficient, multimodal, and has JSON mode support
    model = genai.GenerativeModel(
        model_name="gemini-3.1-flash-lite",
        system_instruction=SYSTEM_INSTRUCTION
    )
    
    # Construct the multimodal request contents
    prompt_text = generate_analysis_prompt(scraped_data)
    contents = [prompt_text]
    
    # Append image parts if available
    images = scraped_data.get("images", {})
    for img_name, img_info in images.items():
        try:
            mime_type = img_info.get("mime_type", "image/png")
            if "svg" in mime_type.lower():
                logger.info(f"Skipping SVG image {img_name} for Gemini payload as SVGs are unsupported.")
                continue
                
            base64_data = img_info.get("base64_data", "")
            if base64_data:
                img_bytes = base64.b64decode(base64_data)
                contents.append({
                    "mime_type": mime_type,
                    "data": img_bytes
                })
                logger.info(f"Appended image {img_name} to Gemini payload.")
        except Exception as e:
            logger.error(f"Failed to process image {img_name} for analyzer: {e}")
            
    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.2
    }
    
    try:
        response = await model.generate_content_async(
            contents,
            generation_config=generation_config
        )
        
        # Clean up any potential markdown fences in the response text
        response_text = response.text.strip()
        if response_text.startswith("```"):
            # If model ignored system instructions and wrapped in codeblock, strip it
            response_text = re.sub(r"^```(?:json)?\n", "", response_text)
            response_text = re.sub(r"\n```$", "", response_text)
            
        # Parse output to ensure it is valid JSON
        parsed_json = json.loads(response_text)
        return parsed_json
    except Exception as e:
        logger.error(f"Gemini generation error: {e}")
        raise Exception(f"Failed to analyze product strategy via Gemini: {e}")
