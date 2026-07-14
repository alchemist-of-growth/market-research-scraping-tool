import os
import json
import base64
import google.generativeai as genai
import httpx
import logging

logger = logging.getLogger(__name__)

# Prompt defining instructions for the Gemini model
SYSTEM_INSTRUCTION = """You are an elite product marketing director, veteran competitor intelligence analyst, and principal visual brand auditor.
Your job is to perform a deep-dive, forensic reverse-engineering of a competitor's product positioning, messaging narrative, category framing, market SWOT gaps, and visual identity by analyzing its scraped website text, metadata, CSS properties, and rendered full-page screenshot.

CRITICAL QUALITY CONSTRAINTS:
1. NO SUPERFICIAL OUTPUTS: Avoid generic summaries, marketing buzzwords, or brief single-clause answers. Every explanation, description, audit reasoning, and recommendation MUST be highly detailed, analytical, and written in the voice of a seasoned expert.
2. EVIDENCE-BASED AUDIT: Cite specific copy blocks, headings, buttons, value propositions, or visual anomalies from the scraped data to back up every single observation.
3. DETAIL REQUIREMENT: Each textual description (such as messaging theme descriptions, SWOT items, usability findings, and priorities) must be a fully developed, 3-to-5 sentence paragraph rich in strategic context and expert critique.
4. PROFESSIONAL TALK-TRACKS: The sales objection responses must be complete, highly polished talk-tracks that an elite enterprise sales representative can use directly in competitive deal situations.

Return a valid, parseable JSON document conforming strictly to the requested schema.
Do not wrap your output in markdown code blocks like ```json ... ```. Just return the raw JSON string.

Schema structure and guidelines:
{
  "summary": {
    "elevator_pitch": "A highly sophisticated, single-sentence competitor overview detailing their primary value mechanism and market angle.",
    "target_audience": "Deep definition of their primary, secondary, and tertiary ICP (Ideal Customer Profile) segments, referencing specific website copy markers.",
    "category_strategy": "Analytical breakdown of how they define, claim, or reframe their product category, explaining their positioning strategy in the broader market."
  },
  "positioning_statement": {
    "target_audience": "For [highly specific target persona / segment name]...",
    "product_category": "is the [precise category or category-reframe]...",
    "key_benefit": "that [the primary value mechanism, differentiator, and core emotional/rational benefit]...",
    "reason_to_believe": "because [specific proof points, technical claims, metrics, or trust indicators shown on the page]..."
  },
  "messaging_analysis": {
    "primary_tagline": "The exact main tagline/headline from the hero fold, with a brief critique of its clarity and hook.",
    "messaging_themes": [
      {
        "theme": "Strategic theme title (e.g. Developer Velocity, Enterprise Governance)",
        "description": "A detailed 3-5 sentence analysis of how they support this theme, listing key value pillars, specific benefits, and messaging techniques they deploy."
      }
    ],
    "tone_of_voice": ["E.g. Assertive", "Highly Technical", "Clinical"],
    "problem_solved": "A deep, analytical explanation of the friction, market inefficiency, or organizational pain they position themselves to solve."
  },
  "product_positioning": {
    "features_emphasized": ["Detailed feature description 1", "Detailed feature description 2"],
    "claimed_differentiators": ["Technical differentiator 1", "Strategic differentiator 2"],
    "pricing_approach": "Comprehensive analysis of their packaging structure, entry-level tiers, monetization philosophy, and enterprise self-serve vs sales-led motions."
  },
  "narrative_arc": {
    "villain": "Detailed description of the external status quo, enemy, or legacy workflow they position against (e.g., fragmented sheets, siloed dev loops).",
    "hero": "The hero in their narrative (the developer, the finance manager, or the product itself), explaining why this hero choice aligns with their buying persona.",
    "transformation": "A detailed contrast of the 'Before state' (complexity, friction) vs the 'After state' (seamless flow, automated growth).",
    "stakes": "The negative consequences of buyer inaction (wasted developer hours, churn, security vulnerability) as highlighted on their page."
  },
  "messaging_audit": {
    "clarity": "Detailed audit of whether the average landing page visitor can understand what they do in 5 seconds, citing copy clarity and jargon usage.",
    "differentiation": "Granular assessment of whether their messaging is uniquely distinct or blends into competitor noise, citing typical market patterns.",
    "proof": "Exhaustive list and analysis of how they back up claims (case studies, customer logos, numerical metrics, industry certifications).",
    "resonance": "Detailed evaluation of how effectively their copy taps into real customer frustration vs abstract developer/business benefits."
  },
  "swot_analysis": {
    "strengths": ["Strengths backed by evidence 1", "Strengths backed by evidence 2"],
    "weaknesses": ["Vulnerabilities and copy gaps 1", "Vulnerabilities and copy gaps 2"],
    "opportunities": ["Highly actionable, strategic positioning opportunities and copy gaps you can exploit to win prospects from them."],
    "threats": ["Deeply entrenched strengths, network effects, or product capabilities of theirs that present a threat to your positioning."]
  },
  "sales_battlecard": {
    "objection_handling": [
      {
        "objection": "Prospect objection: e.g. '[Competitor] has better native integrations' or '[Competitor] is cheaper'",
        "response": "An elite enterprise talk-track script (3-4 sentences) that sales reps can read or adapt to validate the customer, reframe the value comparison, and highlight your distinct advantage."
      }
    ],
    "landmines_to_set": [
      {
        "question": "A tactical, double-edged question prospects should ask them to expose their architectural or strategic limits.",
        "goal": "Detailed explanation of how this question shifts the buyer's focus to your distinct engineering/business model advantage."
      }
    ]
  },
  "design_critique": {
    "overall_impression": "A sophisticated visual critique summarizing the visual design system, styling patterns, brand aesthetic, and initial design reaction.",
    "usability_findings": [
      {
        "issue": "Usability issue (e.g. contrast, font readability, scroll fatigue, obscure CTAs) with a detailed explanation of why it harms user experience.",
        "severity": "🔴 Critical / 🟡 Moderate / 🟢 Minor",
        "recommendation": "Detailed actionable recommendation (2-3 sentences) on how to fix this issue visually or architecturally."
      }
    ],
    "visual_hierarchy": {
      "first_impression": "What visual element draws the eye first on the full-page screenshot, and why.",
      "is_first_impression_correct": "True/False with a detailed explanation of whether the visual focal point matches the primary CTA and key messaging.",
      "reading_flow": "The sequential visual path the user's eye follows down the screen, critiquing layout composition.",
      "emphasis_critique": "A critique on whether key elements like pricing cards, product demos, or testimonial sections are properly emphasized or lost in clutter."
    },
    "consistency_findings": [
      {
        "element": "Design system element (e.g. Buttons, Borders, Font weights, Color accents).",
        "issue": "Specific inconsistency (e.g. mix of sharp and rounded buttons, conflicting secondary color usage).",
        "recommendation": "Actionable recommendation on how to unify this in the style guide."
      }
    ],
    "accessibility": {
      "color_contrast": "Technical contrast review of main text blocks against backgrounds based on CSS variables and screenshots.",
      "touch_targets": "Critique of spacing and size of primary interactive targets (mobile layout estimation).",
      "text_readability": "Detailed audit of reading readability (line-height, container widths, typeface readability)."
    },
    "what_works_well": [
      "Detail of a visual system strength (e.g. beautiful glassmorphism gradients, elegant dark mode contrast) 1",
      "Detail of a visual system strength 2"
    ],
    "priority_recommendations": [
      "1. Crucial design change: Detailed description of what to change, how to change it, and the conversion impact it will have.",
      "2. Secondary design change: Detailed description of what to change, how to change it, and the visual benefit.",
      "3. Tertiary design change: Detailed description of what to change, how to change it, and the user flow benefit."
    ],
    "color_palette_feedback": "A professional analysis of their brand colors (citing specific hex codes/CSS vars), color harmony, tone compatibility, and visual mood.",
    "visual_theme": "Comprehensive description of their overall design system identity (e.g., sleek Neo-brutalist dark-mode, minimal SaaS clean UI)."
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
        
    # Auto-detect OpenRouter API Key prefix
    if api_key.startswith("sk-or-"):
        return await analyze_via_openrouter(scraped_data, api_key)
        
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
        
        # Find outermost curly braces to handle any extra text wrapper or trailing characters from the model
        response_text = response.text.strip()
        first_brace = response_text.find('{')
        last_brace = response_text.rfind('}')
        if first_brace != -1 and last_brace != -1:
            json_content = response_text[first_brace:last_brace+1]
        else:
            json_content = response_text
            
        # Parse output to ensure it is valid JSON
        try:
            parsed_json = json.loads(json_content)
            return parsed_json
        except Exception as json_err:
            logger.error(f"Failed to parse JSON response: {json_err}. Raw response text:\n{response_text}")
            raise json_err
    except Exception as e:
        logger.error(f"Gemini generation error: {e}")
        raise Exception(f"Failed to analyze product strategy via Gemini: {e}")

async def analyze_via_openrouter(scraped_data, api_key):
    """Sends website data and image assets to OpenRouter using Google Gemma 4 31B free model."""
    logger.info("Routing request to OpenRouter using google/gemma-4-31b-it:free")
    
    # 1. Prepare system instruction and user prompt
    prompt_text = generate_analysis_prompt(scraped_data)
    
    # 2. Build content array for user message
    content_parts = [
        {
            "type": "text",
            "text": prompt_text
        }
    ]
    
    # 3. Add base64 images to content parts
    images = scraped_data.get("images", {})
    for img_name, img_info in images.items():
        try:
            mime_type = img_info.get("mime_type", "image/png")
            if "svg" in mime_type.lower():
                continue
            base64_data = img_info.get("base64_data", "")
            if base64_data:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_data}"
                    }
                })
                logger.info(f"Appended image {img_name} to OpenRouter payload.")
        except Exception as e:
            logger.error(f"Failed to process image {img_name} for OpenRouter: {e}")
            
    # 4. Make HTTP request to OpenRouter API
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/alchemist-of-growth/market-research-scraping-tool",
        "X-Title": "Market Research Scraping Tool"
    }
    
    models_to_try = [
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-nano-12b-v2-vl:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
    ]
    
    payload = {
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_INSTRUCTION
            },
            {
                "role": "user",
                "content": content_parts
            }
        ],
        "response_format": {
            "type": "json_object"
        },
        "temperature": 0.2
    }
    
    last_error = None
    for model_name in models_to_try:
        logger.info(f"Attempting OpenRouter request using model: {model_name}")
        payload["model"] = model_name
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    response_text = result["choices"][0]["message"]["content"].strip()
                    
                    # Clean outer braces
                    first_brace = response_text.find('{')
                    last_brace = response_text.rfind('}')
                    if first_brace != -1 and last_brace != -1:
                        json_content = response_text[first_brace:last_brace+1]
                    else:
                        json_content = response_text
                        
                    parsed_json = json.loads(json_content)
                    logger.info(f"Successfully processed request using OpenRouter model: {model_name}")
                    return parsed_json
                else:
                    logger.warning(f"OpenRouter model {model_name} failed with status {response.status_code}: {response.text}")
                    last_error = response.text
        except Exception as e:
            logger.warning(f"Exception during OpenRouter execution for model {model_name}: {e}")
            last_error = str(e)
            
    raise Exception(f"OpenRouter returned error: {last_error}")
