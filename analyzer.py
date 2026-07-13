import os
import json
import base64
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)

# Prompt defining instructions for the Gemini model
SYSTEM_INSTRUCTION = """You are an elite product marketing manager, competitor intelligence analyst, and visual brand auditor.
Your job is to reverse-engineer a competitor's product positioning, messaging themes, narrative structure, SWOT gaps, and visual identity by analyzing its scraped website text, metadata, CSS colors, and key visual assets.

You must return a valid, parseable JSON document conforming strictly to the requested schema.
Do not wrap your output in markdown code blocks like ```json ... ```. Just return the raw JSON string.

Schema structure:
{
  "summary": {
    "elevator_pitch": "One-sentence competitor overview describing what they do.",
    "target_audience": "Who they are primarily targeting based on the website copy.",
    "category_strategy": "How they define and position their product category (e.g. creating a new category, win existing, reframe, or niche)."
  },
  "positioning_statement": {
    "target_audience": "For [target audience]...",
    "product_category": "is the [category]...",
    "key_benefit": "that [key benefit/differentiator]...",
    "reason_to_believe": "because [reason to believe / proof points]..."
  },
  "messaging_analysis": {
    "primary_tagline": "Their main tagline/headline extracted from the hero section.",
    "messaging_themes": [
      {
        "theme": "Theme title (e.g. Security, Developer Speed)",
        "description": "How they support and explain this theme on the website."
      }
    ],
    "tone_of_voice": ["Adjective 1", "Adjective 2", "Adjective 3"],
    "problem_solved": "How they describe the core problem they solve for customers."
  },
  "product_positioning": {
    "features_emphasized": ["Feature 1", "Feature 2", "Feature 3"],
    "claimed_differentiators": ["Differentiator 1", "Differentiator 2"],
    "pricing_approach": "Summary of pricing model, tier structures, trials, or enterprise focus."
  },
  "narrative_arc": {
    "villain": "What problem or status quo they position against (legacy tools, manual work, complexity).",
    "hero": "Who is the hero in their story (customer, product, team).",
    "transformation": "What before/after transformation they promise.",
    "stakes": "What happens if the buyer does not act (wasted time, security breaches, loss of revenue)."
  },
  "messaging_audit": {
    "clarity": "Can a visitor understand what they do in 5 seconds? (High/Medium/Low) + reasoning.",
    "differentiation": "Is it distinct or generic? + reasoning.",
    "proof": "Do they back up claims with data, logos, or testimonials? + details.",
    "resonance": "Does it address real customer pain points? + details."
  },
  "swot_analysis": {
    "strengths": ["Competitor strength 1", "Competitor strength 2"],
    "weaknesses": ["Competitor weakness 1", "Competitor weakness 2"],
    "opportunities": ["Positioning gaps or underserved segments you can exploit against them."],
    "threats": ["Areas where they are exceptionally strong and you are vulnerable."]
  },
  "sales_battlecard": {
    "objection_handling": [
      {
        "objection": "If a prospect says: '[Competitor] does X too' or '[Competitor] is cheaper'",
        "response": "Actionable response sales reps should use to handle the objection and win the deal."
      }
    ],
    "landmines_to_set": [
      {
        "question": "A strategic question to suggest prospects ask the competitor that highlights their weaknesses.",
        "goal": "Why asking this question highlights your product's comparative advantage."
      }
    ]
  },
  "design_critique": {
    "overall_impression": "1-2 sentence first reaction — what works, what's the biggest opportunity.",
    "usability_findings": [
      {
        "issue": "Specific usability issue observed.",
        "severity": "🔴 Critical / 🟡 Moderate / 🟢 Minor",
        "recommendation": "Specific actionable recommendation to fix the issue."
      }
    ],
    "visual_hierarchy": {
      "first_impression": "What draws the eye first (e.g., Hero image, massive CTA, headline).",
      "is_first_impression_correct": "True/False with short reasoning.",
      "reading_flow": "How the eye moves through the layout.",
      "emphasis_critique": "Are the correct items emphasized?"
    },
    "consistency_findings": [
      {
        "element": "Design element (e.g., Typography, Spacing, Buttons, Color scheme).",
        "issue": "Any inconsistency observed.",
        "recommendation": "Actionable recommendation to resolve."
      }
    ],
    "accessibility": {
      "color_contrast": "Pass/fail estimation for key text.",
      "touch_targets": "Adequate touch targets for mobile (adequate/inadequate)?",
      "text_readability": "Critique on font size, spacing, and line height readability."
    },
    "what_works_well": [
      "Positive observation 1",
      "Positive observation 2"
    ],
    "priority_recommendations": [
      "1. Most impactful change — Why and how",
      "2. Second priority — Why and how",
      "3. Third priority — Why and how"
    ],
    "color_palette_feedback": "Analysis of the brand color selections based on the CSS colors and images provided.",
    "visual_theme": "Description of the visual identity (e.g., sleek dark-mode, minimalist, warm illustrations)."
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
