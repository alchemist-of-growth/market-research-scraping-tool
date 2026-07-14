import os
import json
import base64
import google.generativeai as genai
import httpx
import logging
import re

logger = logging.getLogger(__name__)

# Prompt defining instructions for the Gemini model (kept for backwards compatibility and schema documentation)
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

def count_words(text):
    if not text:
        return 0
    cleaned = re.sub(r'<[^>]*>', '', text)
    words = cleaned.split()
    return len(words)

def count_sentences(text):
    if not text:
        return 0
    sentences = re.split(r'[.!?]+(?:\s+|$)', text.strip())
    sentences = [s for s in sentences if s.strip()]
    return len(sentences)

def has_citations(text):
    if not text:
        return False
    if '"' in text or "'" in text or '`' in text:
        return True
    lower_text = text.lower()
    if any(keyword in lower_text for keyword in ["cite", "according to", "source", "screenshot", "css", "variable", "color", "#", "heading", "paragraph"]):
        return True
    return False

def validate_field(val, field_name):
    if not val:
        return [f"{field_name} is empty or missing"]
    errors = []
    w_count = count_words(val)
    s_count = count_sentences(val)
    c_check = has_citations(val)
    if w_count < 50:
        errors.append(f"{field_name} word count is {w_count} (must be >= 50)")
    if s_count < 3:
        errors.append(f"{field_name} sentence count is {s_count} (must be >= 3)")
    if not c_check:
        errors.append(f"{field_name} does not cite original evidence (must cite copy/styles/headings/screenshots)")
    return errors

def get_agent_keys(agent_name):
    if agent_name == "Researcher Agent":
        return ["researcher_data"]
    elif agent_name == "Product Strategy Agent":
        return ["summary", "positioning_statement", "messaging_analysis", "product_positioning", "narrative_arc"]
    elif agent_name == "Visual Brand Auditor Agent":
        return ["design_critique", "messaging_audit"]
    elif agent_name == "SWOT & Battlecard Agent":
        return ["swot_analysis", "sales_battlecard"]
    return []

def validate_agent_output(agent_name, state):
    errors = []
    if agent_name == "Researcher Agent":
        res_data = state.get("researcher_data", {})
        if not res_data:
            errors.append("researcher_data is missing or empty")
            
    elif agent_name == "Product Strategy Agent":
        summary = state.get("summary", {})
        errors.extend(validate_field(summary.get("elevator_pitch"), "summary.elevator_pitch"))
        errors.extend(validate_field(summary.get("target_audience"), "summary.target_audience"))
        errors.extend(validate_field(summary.get("category_strategy"), "summary.category_strategy"))
        
        pos = state.get("positioning_statement", {})
        errors.extend(validate_field(pos.get("target_audience"), "positioning_statement.target_audience"))
        errors.extend(validate_field(pos.get("product_category"), "positioning_statement.product_category"))
        errors.extend(validate_field(pos.get("key_benefit"), "positioning_statement.key_benefit"))
        errors.extend(validate_field(pos.get("reason_to_believe"), "positioning_statement.reason_to_believe"))
        
        msg = state.get("messaging_analysis", {})
        errors.extend(validate_field(msg.get("problem_solved"), "messaging_analysis.problem_solved"))
        for i, theme in enumerate(msg.get("messaging_themes", [])):
            errors.extend(validate_field(theme.get("description"), f"messaging_analysis.messaging_themes[{i}].description"))
            
        prod = state.get("product_positioning", {})
        errors.extend(validate_field(prod.get("pricing_approach"), "product_positioning.pricing_approach"))
        
        narrative = state.get("narrative_arc", {})
        errors.extend(validate_field(narrative.get("villain"), "narrative_arc.villain"))
        errors.extend(validate_field(narrative.get("hero"), "narrative_arc.hero"))
        errors.extend(validate_field(narrative.get("transformation"), "narrative_arc.transformation"))
        errors.extend(validate_field(narrative.get("stakes"), "narrative_arc.stakes"))
        
    elif agent_name == "Visual Brand Auditor Agent":
        design = state.get("design_critique", {})
        errors.extend(validate_field(design.get("overall_impression"), "design_critique.overall_impression"))
        errors.extend(validate_field(design.get("color_palette_feedback"), "design_critique.color_palette_feedback"))
        errors.extend(validate_field(design.get("visual_theme"), "design_critique.visual_theme"))
        
        vh = design.get("visual_hierarchy", {})
        errors.extend(validate_field(vh.get("first_impression"), "design_critique.visual_hierarchy.first_impression"))
        errors.extend(validate_field(vh.get("reading_flow"), "design_critique.visual_hierarchy.reading_flow"))
        errors.extend(validate_field(vh.get("emphasis_critique"), "design_critique.visual_hierarchy.emphasis_critique"))
        
        acc = design.get("accessibility", {})
        errors.extend(validate_field(acc.get("color_contrast"), "design_critique.accessibility.color_contrast"))
        errors.extend(validate_field(acc.get("touch_targets"), "design_critique.accessibility.touch_targets"))
        errors.extend(validate_field(acc.get("text_readability"), "design_critique.accessibility.text_readability"))
        
        for i, finding in enumerate(design.get("usability_findings", [])):
            errors.extend(validate_field(finding.get("issue"), f"design_critique.usability_findings[{i}].issue"))
            errors.extend(validate_field(finding.get("recommendation"), f"design_critique.usability_findings[{i}].recommendation"))
            
        for i, finding in enumerate(design.get("consistency_findings", [])):
            errors.extend(validate_field(finding.get("issue"), f"design_critique.consistency_findings[{i}].issue"))
            errors.extend(validate_field(finding.get("recommendation"), f"design_critique.consistency_findings[{i}].recommendation"))
            
        for i, rec in enumerate(design.get("priority_recommendations", [])):
            errors.extend(validate_field(rec, f"design_critique.priority_recommendations[{i}]"))
            
        audit = state.get("messaging_audit", {})
        errors.extend(validate_field(audit.get("clarity"), "messaging_audit.clarity"))
        errors.extend(validate_field(audit.get("differentiation"), "messaging_audit.differentiation"))
        errors.extend(validate_field(audit.get("proof"), "messaging_audit.proof"))
        errors.extend(validate_field(audit.get("resonance"), "messaging_audit.resonance"))
        
    elif agent_name == "SWOT & Battlecard Agent":
        swot = state.get("swot_analysis", {})
        for key in ["strengths", "weaknesses", "opportunities", "threats"]:
            for i, val in enumerate(swot.get(key, [])):
                errors.extend(validate_field(val, f"swot_analysis.{key}[{i}]"))
                
        battlecard = state.get("sales_battlecard", {})
        for i, obj in enumerate(battlecard.get("objection_handling", [])):
            errors.extend(validate_field(obj.get("response"), f"sales_battlecard.objection_handling[{i}].response"))
            
        for i, lm in enumerate(battlecard.get("landmines_to_set", [])):
            errors.extend(validate_field(lm.get("goal"), f"sales_battlecard.landmines_to_set[{i}].goal"))
            
    return errors

def parse_json_from_response(response_text):
    first_brace = response_text.find('{')
    last_brace = response_text.rfind('}')
    if first_brace != -1 and last_brace != -1:
        json_content = response_text[first_brace:last_brace+1]
    else:
        json_content = response_text
    return json.loads(json_content)

async def call_gemini_api(agent_name, system_instruction, prompt, scraped_data, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-3.1-flash-lite",
        system_instruction=system_instruction
    )
    
    contents = [prompt]
    images = scraped_data.get("images", {})
    for img_name, img_info in images.items():
        try:
            mime_type = img_info.get("mime_type", "image/png")
            if "svg" in mime_type.lower():
                continue
            base64_data = img_info.get("base64_data", "")
            if base64_data:
                img_bytes = base64.b64decode(base64_data)
                contents.append({
                    "mime_type": mime_type,
                    "data": img_bytes
                })
        except Exception as e:
            logger.error(f"Failed to process image {img_name} for agent {agent_name}: {e}")
            
    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.2
    }
    
    response = await model.generate_content_async(
        contents,
        generation_config=generation_config
    )
    
    response_text = response.text.strip()
    return parse_json_from_response(response_text)

async def call_openrouter_api(agent_name, system_instruction, prompt, scraped_data, api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/alchemist-of-growth/market-research-scraping-tool",
        "X-Title": "Market Research Scraping Tool"
    }
    
    content_parts = [{"type": "text", "text": prompt}]
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
        except Exception as e:
            logger.error(f"Failed to process image {img_name} for OpenRouter {agent_name}: {e}")
            
    models_to_try = [
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-nano-12b-v2-vl:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
    ]
    
    payload = {
        "messages": [
            {
                "role": "system",
                "content": system_instruction
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
        payload["model"] = model_name
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    response_text = result["choices"][0]["message"]["content"].strip()
                    return parse_json_from_response(response_text)
                else:
                    last_error = response.text
        except Exception as e:
            last_error = str(e)
            
    raise Exception(f"OpenRouter returned error: {last_error}")

async def run_agent_inference(agent_name, system_instruction, prompt, scraped_data, api_key):
    if api_key.startswith("sk-or-"):
        return await call_openrouter_api(agent_name, system_instruction, prompt, scraped_data, api_key)
    else:
        return await call_gemini_api(agent_name, system_instruction, prompt, scraped_data, api_key)

async def run_critic_qualitative_check(agent_name, state, api_key):
    keys = get_agent_keys(agent_name)
    content_to_check = {k: state[k] for k in keys if k in state}
    
    instruction = "You are the Critic Agent. Review the qualitative depth, tone, and logical consistency of the competitor analysis draft."
    prompt = f"""
Verify the following draft section for professional tone, strategic depth, and logical consistency.
Agent: {agent_name}
Draft Content: {json.dumps(content_to_check, indent=2)}

If the content is shallow, uses generic marketing buzzwords, or lacks analytical depth, return a JSON response with status FAILED and a constructive feedback explanation.
Otherwise, if it is high quality and meets all requirements, return status PASSED.

Response schema:
{{
  "status": "PASSED" or "FAILED",
  "feedback": "Detailed constructive feedback if FAILED, otherwise empty."
}}
"""
    try:
        res = await run_agent_inference(
            agent_name="Critic Agent (Qualitative)",
            system_instruction=instruction,
            prompt=prompt,
            scraped_data={},
            api_key=api_key
        )
        if res.get("status") == "FAILED":
            return [res.get("feedback", "Qualitative check failed.")]
        return []
    except Exception as e:
        logger.warning(f"Qualitative Critic check failed to run: {e}")
        return []

async def analyze_website_strategy(scraped_data, custom_api_key=None):
    """Sends website data and image assets to sequential agents to reverse-engineer GTM and product strategy."""
    api_key = custom_api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise Exception("Gemini API key is not configured. Please set it in Settings (UI) or environment variables.")
    if not scraped_data or not scraped_data.get("url"):
        raise Exception("scraped_data is empty or missing target url")
        
    state = {
        "researcher_data": {},
        "summary": {},
        "positioning_statement": {},
        "messaging_analysis": {},
        "product_positioning": {},
        "narrative_arc": {},
        "messaging_audit": {},
        "swot_analysis": {},
        "sales_battlecard": {},
        "design_critique": {},
        "critic_logs": []
    }
    
    agents = [
        {
            "name": "Researcher Agent",
            "instruction": "You are the Researcher Agent. Clean and structure the raw website data (headings, paragraphs, lists, colors, CSS variables) into a structured JSON under 'researcher_data'.",
            "prompt_builder": lambda s: f"Analyze and structure the scraped website data:\n{json.dumps(scraped_data)}"
        },
        {
            "name": "Product Strategy Agent",
            "instruction": "You are the Product Strategy Agent. Generate summary, positioning_statement, messaging_analysis, product_positioning, and narrative_arc. Each description must be a detailed 3-5 sentence paragraph (>=50 words, >=3 sentences) citing original website copy.",
            "prompt_builder": lambda s: f"Generate strategy nodes based on researcher data:\n{json.dumps(s.get('researcher_data'))}"
        },
        {
            "name": "Visual Brand Auditor Agent",
            "instruction": "You are the Visual Brand Auditor Agent. Critique the design system, usability, visual hierarchy, consistency, accessibility, and overall aesthetics based on the CSS styles, variables, and full-page screenshot. Also audit messaging clarity, differentiation, proof, and resonance. Each description must be a detailed 3-5 sentence paragraph (>=50 words, >=3 sentences) citing specific CSS properties/colors or original copy.",
            "prompt_builder": lambda s: f"Generate visual brand audit and messaging audit based on style data and screenshot reference."
        },
        {
            "name": "SWOT & Battlecard Agent",
            "instruction": "You are the SWOT & Battlecard Agent. Synthesize strategic and visual findings into a SWOT analysis (strengths, weaknesses, opportunities, threats) and sales battlecard with objection handling talk-tracks. Each description must be a detailed 3-5 sentence paragraph (>=50 words, >=3 sentences). Objection responses must be direct, polished sales scripts.",
            "prompt_builder": lambda s: f"Generate SWOT and sales battlecard based on state:\n{json.dumps({k: v for k, v in s.items() if k not in ['critic_logs', 'swot_analysis', 'sales_battlecard']})}"
        }
    ]
    
    for agent in agents:
        agent_name = agent["name"]
        retry_limit = 2
        run_index = 1
        
        while run_index <= 1 + retry_limit:
            # Build prompt
            if run_index == 1:
                prompt = agent["prompt_builder"](state)
            else:
                last_log = [l for l in state["critic_logs"] if l["agent"] == agent_name][-1]
                agent_keys = get_agent_keys(agent_name)
                prev_content = {k: state[k] for k in agent_keys if k in state}
                prompt = f"""
You previously generated the following content:
{json.dumps(prev_content, indent=2)}

However, the Critic Agent rejected it with the following feedback:
{'; '.join(last_log.get('errors', []))}

Please regenerate the content, making sure to fully address the feedback and satisfy all constraints.
"""
            
            try:
                agent_output = await run_agent_inference(
                    agent_name=agent_name,
                    system_instruction=agent["instruction"],
                    prompt=prompt,
                    scraped_data=scraped_data,
                    api_key=api_key
                )
                
                # Merge output into state
                for k, v in agent_output.items():
                    if k in state and k != "critic_logs":
                        state[k] = v
                        
                # Validate output
                errors = validate_agent_output(agent_name, state)
                
                # Perform LLM qualitative check if programmatic check passes and agent is not Researcher
                if not errors and agent_name != "Researcher Agent":
                    qual_errors = await run_critic_qualitative_check(agent_name, state, api_key)
                    errors.extend(qual_errors)
                    
                if not errors:
                    state["critic_logs"].append({
                        "agent": agent_name,
                        "run": run_index,
                        "status": "PASSED",
                        "errors": []
                    })
                    break
                else:
                    state["critic_logs"].append({
                        "agent": agent_name,
                        "run": run_index,
                        "status": "FAILED",
                        "errors": errors
                    })
                    logger.warning(f"{agent_name} failed validation on run {run_index}: {errors}")
                    run_index += 1
            except Exception as e:
                err_msg = f"Error during execution of {agent_name}: {str(e)}"
                logger.error(err_msg)
                if "ResourceExhausted" in str(e) or "Quota exceeded" in str(e):
                    raise e
                state["critic_logs"].append({
                    "agent": agent_name,
                    "run": run_index,
                    "status": "FAILED",
                    "errors": [err_msg]
                })
                run_index += 1
                
        if run_index > 1 + retry_limit:
            logger.error(f"Maximum retry limit ({retry_limit}) exceeded for {agent_name}. Proceeding with best-effort state.")
            
    return state

async def analyze_via_openrouter(scraped_data, api_key):
    """Fallback function kept for compatibility, calls Unified OpenRouter API call."""
    return await call_openrouter_api("General Agent", SYSTEM_INSTRUCTION, generate_analysis_prompt(scraped_data), scraped_data, api_key)
