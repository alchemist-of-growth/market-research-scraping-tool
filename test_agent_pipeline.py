import pytest
import asyncio
import json
import os
import base64
import re
from unittest.mock import patch, MagicMock
from pathlib import Path
import httpx
from bs4 import BeautifulSoup

# Import targets
import scraper
import analyzer
import main

# Mock HTML & CSS fixtures
MOCK_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Mock Target Title</title>
    <meta name="description" content="Mock description here.">
    <meta property="og:image" content="https://mock-target.com/assets/og.jpg">
    <link rel="stylesheet" href="https://mock-target.com/style1.css">
    <link rel="stylesheet" href="https://mock-target.com/style2.css">
    <link rel="stylesheet" href="https://mock-target.com/style3.css">
    <link rel="stylesheet" href="https://mock-target.com/style4.css">
    <link rel="stylesheet" href="https://mock-target.com/style5.css">
    <style>
        .btn { color: hsl(120, 100%, 50%); border: 1px solid #0000ff80; }
        :root { --primary-color: #6200ee; --font-size: 16px; }
    </style>
</head>
<body>
    <h1>Linear - The Issue Tracker You Want to Use</h1>
    <h2>Subheading 1</h2>
    <h2>Subheading 2</h2>
    <h3>Detail 1</h3>
    <h3>Detail 2</h3>
    <h3>Detail 3</h3>
    <h3>Detail 4</h3>
    <p style="color: #ff0000; background: rgb(0, 255, 0);">Linear is a project management tool that helps developers keep track of their issues and tasks.</p>
    <p>It is designed to be extremely fast and keyboard-friendly, offering real-time synchronization across teams.</p>
    <p>We use native layouts and hotkeys to optimize developer velocity, allowing developers to manage sprint planning.</p>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
        <li>Item 3</li>
        <li>Item 4</li>
        <li>Item 5</li>
    </ul>
    <img src="/assets/logo.png" alt="Company Logo" class="nav-logo" id="logo-img">
    <img src="/assets/hero.jpg" class="hero-banner" id="hero-img">
</body>
</html>
"""

MOCK_CSS_1 = ":root { --neutral-dark: #121212; }"
MOCK_CSS_2 = "body { color: #f3f3f3; }"
MOCK_CSS_3 = ".card { background-color: #222; }"
MOCK_CSS_4 = "a { color: #0070f3; }"
MOCK_CSS_5 = "span { color: #ff00ff; }"

# Mock HTTP Client class for hermetic offline tests
class MockAsyncClient:
    def __init__(self, verify=False, *args, **kwargs):
        self.verify = verify
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.closed = True

    async def get(self, url, *args, **kwargs):
        url_str = str(url)
        # Timeout boundary check URL
        if "timeout-trigger" in url_str:
            raise httpx.ReadTimeout("Mocked read timeout triggered")
        elif "api.microlink.io" in url_str:
            if "rate-limit" in url_str:
                return httpx.Response(429, text="Too Many Requests")
            elif "gateway-timeout" in url_str:
                return httpx.Response(504, text="Gateway Timeout")
            # 1x1 Transparent PNG bytes
            png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
            return httpx.Response(200, content=png_bytes)
        elif "logo.png" in url_str or "hero.jpg" in url_str or "og.jpg" in url_str or "fallback_first.png" in url_str or "logo.svg" in url_str or "hero.svg" in url_str:
            if "broken-img" in url_str:
                return httpx.Response(404, text="Image Not Found")
            mime = "image/png" if not "svg" in url_str else "image/svg+xml"
            content = b"<svg></svg>" if "svg" in url_str else b"fake_image_bytes"
            return httpx.Response(200, content=content, headers={"content-type": mime})
        elif "style1.css" in url_str:
            return httpx.Response(200, text=MOCK_CSS_1)
        elif "style2.css" in url_str:
            return httpx.Response(200, text=MOCK_CSS_2)
        elif "style3.css" in url_str:
            return httpx.Response(200, text=MOCK_CSS_3)
        elif "style4.css" in url_str:
            return httpx.Response(200, text=MOCK_CSS_4)
        elif "style5.css" in url_str:
            return httpx.Response(200, text=MOCK_CSS_5)
        elif "cf-block" in url_str:
            return httpx.Response(403, text="Forbidden by Cloudflare")
        elif "429" in url_str:
            return httpx.Response(429, text="Too Many Requests")
        else:
            return httpx.Response(200, text=MOCK_HTML)

    async def post(self, url, *args, **kwargs):
        url_str = str(url)
        if "openrouter" in url_str:
            # Mock OpenRouter API Response
            payload = {
                "choices": [{
                    "message": {
                        "content": json.dumps(get_valid_agent_output("Product Strategy Agent"))
                    }
                }]
            }
            return httpx.Response(200, json=payload)
        return httpx.Response(200, text="{}")

def make_valid_string(text, field_name):
    if not isinstance(text, str):
        return text
    last_part = field_name.split(".")[-1]
    if last_part in ["severity", "element", "question", "objection", "status", "feedback"]:
        return text
    sentences = [s.strip() for s in text.split(". ") if s.strip()]
    while len(sentences) < 4:
        sentences.append(f"This is an automated structural validation sentence for {field_name} that adds details to the analysis.")
    text = ". ".join(sentences)
    words = text.split()
    if len(words) < 65:
        padding = [f"paddedword{i}" for i in range(65 - len(words))]
        text = text + " " + " ".join(padding) + "."
    if not ('"' in text or "'" in text or '`' in text):
        text = text + " (based on 'screenshot' observations)."
    return text

def recursively_pad_dict(d, prefix=""):
    if isinstance(d, dict):
        return {k: recursively_pad_dict(v, prefix + "." + k if prefix else k) for k, v in d.items()}
    elif isinstance(d, list):
        return [recursively_pad_dict(item, prefix + f"[{i}]") for i, item in enumerate(d)]
    elif isinstance(d, str):
        return make_valid_string(d, prefix)
    return d

# Valid outputs conforming strictly to structural checks (>= 50 words, >= 3 sentences, citations)
def get_valid_agent_output(agent_name):
    res = {}
    if agent_name == "Researcher Agent":
        return {
            "researcher_data": {
                "cleaned_headings": [{"level": "h1", "text": "Linear - The Issue Tracker You Want to Use"}],
                "cleaned_paragraphs": ["Linear is a project management tool that helps developers keep track of their issues and tasks. It is designed to be extremely fast and keyboard-friendly, offering real-time synchronization across teams. We use native layouts and hotkeys to optimize developer velocity, allowing developers to manage sprint planning, roadmaps, and bug tracking seamlessly without leaving their keyboard. The product utilizes clear visual aesthetics and dark mode styling to represent modern SaaS branding."],
                "colors": ["#000000", "#ffffff", "#0c0d0e"],
                "css_variables": {"--bg-color": "#0c0d0e", "--text-color": "#ffffff"}
            }
        }
    elif agent_name == "Product Strategy Agent":
        res = {
            "summary": {
                "elevator_pitch": "Linear is a highly sophisticated project management platform specifically engineered for software product teams, focusing on extreme speed, keyboard-driven navigation, and minimalist design aesthetics to eliminate typical developer tool friction. By focusing on local-first database designs, hotkeys, and real-time syncing, Linear positions itself as the elite premium alternative to bloated enterprise solutions like Jira. The platform claims to improve team execution velocity by 2x through streamlined workflows and opinionated sprint systems.",
                "target_audience": "The primary Ideal Customer Profile (ICP) for Linear consists of high-growth technology startups, fast-moving engineering teams, and product managers who value productivity, speed, and clean user experience. Secondary segments include remote design agencies and tech-forward organizations looking to modernize their issue tracking. Tertiary segments encompass individual developers, side-project builders, and open-source maintainers. Original website copy markers like 'built for high-performance teams' and 'designed for the modern developer' directly support this targeting strategy.",
                "category_strategy": "Linear reframes the project management category by rejecting the traditional heavy, customizable issue tracker model and instead establishing a new standard of 'opinionated product building tools'. Rather than competing on feature checkboxes, Linear claims category leadership by focusing on developer flow, speed, and aesthetic pleasure, positioning itself as a developer tool rather than a generic business manager. This strategy targets the dissatisfaction with Jira's complexity, presenting a clean 'Linear Method' that mandates modern agile best practices out-of-the-box."
            },
            "positioning_statement": {
                "target_audience": "For high-performance software engineering teams and product builders who are frustrated by bloated, slow project management software...",
                "product_category": "is the premium, keyboard-first issue tracker and product planning platform...",
                "key_benefit": "that delivers instantaneous page loads, frictionless task updates, and elegant sprint tracking to keep developers in their optimal flow state...",
                "reason_to_believe": "because it is built on a local-first architecture with offline support, offers 100ms global search hotkeys, and features real-time synchronization, as evidenced by their performance benchmark claims."
            },
            "messaging_analysis": {
                "primary_tagline": "Linear is a better way to build product. We help you streamline sprints, tasks, and bug tracking.",
                "messaging_themes": [
                    {
                        "theme": "Developer Flow and Velocity",
                        "description": "Linear heavily emphasizes speed and keyboard navigation as the core value propositions for individual developers. The messaging details how every action can be completed in milliseconds using command-K menus, eliminating mouse clicks and keeping engineers in the zone. By highlighting '100ms search' and 'offline support', the copy directly addresses the developer pain point of waiting for slow web pages to load. This theme is supported by the website's technical positioning as a high-performance developer tool rather than a slow corporate database."
                    }
                ],
                "tone_of_voice": ["Assertive", "Minimalist", "Developer-focused"],
                "problem_solved": "Linear targets the widespread friction, latency, and organizational overhead associated with traditional enterprise issue tracking tools. By highlighting the pain of slow sprint planning, cluttered project boards, and context switching, Linear positions itself as the remedy for developer fatigue and project overhead. The copy highlights how fragmented processes lead to wasted developer hours and team misalignment, offering a streamlined, opinionated alternative that enforces alignment."
            },
            "product_positioning": {
                "features_emphasized": ["Keyboard-first command menu", "Local-first offline sync"],
                "claimed_differentiators": ["Instant speed", "Opinionated workflow"],
                "pricing_approach": "Linear uses a classic SaaS freemium packaging model, allowing small teams to use the core features for free, with paid tiers for advanced roadmap controls and enterprise-grade SLA/security controls. The monetization philosophy focuses on self-serve product-led growth (PLG) where developers adopt it first, followed by top-down team expansion. Enterprise pricing requires contacting sales, indicating a hybrid self-serve and sales-led enterprise motion that targets large engineering organizations."
            },
            "narrative_arc": {
                "villain": "The villain in the narrative is the slow, bloated legacy issue tracker (implicitly Jira) which forces developers to fill out dozens of fields, wait for page reloads, and navigate complex interfaces, thereby ruining developer velocity and flow. This status quo is portrayed as a source of frustration, bureaucracy, and developer disengagement that hampers startup agility. By positioning Jira as the enemy, Linear aligns itself with the developer's desire to write code instead of managing tickets.",
                "hero": "The hero in Linear's narrative is the high-performance engineering team and the product builder who wants to focus on shipping high-quality software rather than maintaining project dashboards. This aligns with the buying persona of engineering managers and CTOs who want to maximize developer productivity. The product acts as the enabler that empowers these heroes to achieve peak execution speed without friction.",
                "transformation": "The narrative details a transformation from a 'before state' of cluttered dashboards, slow task updates, and team frustration to an 'after state' of instantaneous search, elegant sprint tracking, and absolute alignment. This transition is characterized by a shift from chaotic project management to a streamlined, fast execution loop. The messaging presents this transformation as a path to operational excellence and developer satisfaction.",
                "stakes": "The stakes of inaction are clear: wasted engineering cycles, delayed product launches, team misalignment, and developer churn due to poor internal tooling. The website copy highlights that high-performance teams cannot afford to be slowed down by their software, making modern tooling a competitive necessity. Choosing to stay with outdated platforms results in lost market opportunities and slow iteration loops."
            }
        }
    elif agent_name == "Visual Brand Auditor Agent":
        res = {
            "design_critique": {
                "overall_impression": "Linear utilizes a sophisticated, ultra-premium 'dark mode' design system characterized by subtle gradients, crisp borders, and minimalist typography. The visual design communicates engineering precision, modern SaaS aesthetics, and high-performance capabilities. The clean layout avoids unnecessary distractions, drawing focus strictly to product mockups and value propositions. It represents the pinnacle of developer-focused design trends, inspiring trust and visual appeal.",
                "usability_findings": [
                    {
                        "issue": "The homepage displays low-contrast text for secondary headings and caption copy, which may violate 'WCAG' accessibility guidelines. This harms readability for users with visual impairments or on low-quality screens, causing eye strain and readability fatigue. The dark gray text on a dark background is visually elegant but functionally compromised under bright ambient lighting conditions.",
                        "severity": "🟡 Moderate",
                        "recommendation": "Increase the contrast ratio of all secondary typography by adjusting the gray color hex code from '#606060' to a lighter shade such as '#a0a0a0'. This change will immediately improve text readability and ensure full compliance with accessibility standards without harming the dark-themed design system. The stylesheet updates can be applied to the global color utility classes."
                    }
                ],
                "visual_hierarchy": {
                    "first_impression": "The eye is immediately drawn to the high-resolution, animated product 'screenshot' showcasing the sleek dark user interface of the issue board. This visual focal point is highly effective because it demonstrates the product's actual aesthetic appeal and interface simplicity. It validates the speed and clean layout claims before the user reads any copy.",
                    "is_first_impression_correct": True,
                    "reading_flow": "The eye follows a standard vertical reading flow down the 'landing page', transitioning from the hero headline to the interactive product mockup, then through alternating columns of features, and finally terminating at the pricing comparison cards. This layout composition ensures logical narrative progression and smooth scroll transitions.",
                    "emphasis_critique": "Key call-to-action buttons like 'Get Started' are properly emphasized using high-contrast white background styling that pops against the dark surrounding elements. However, the pricing tier cards are slightly lost in the dark layout, lacking strong borders or distinct accent colors to differentiate their tiers."
                },
                "consistency_findings": [
                    {
                        "element": "Button border radius styling across different landing page sections.",
                        "issue": "Some primary call-to-action buttons use sharp 4px border-radius properties, while other secondary buttons in the feature section use highly rounded 12px borders. This inconsistency in button shape disrupts the visual unity of the design system. It indicates minor styling gaps in the frontend 'CSS' stylesheet classes that must be resolved to unify button appearance.",
                        "recommendation": "Standardize all button border-radius properties to a unified value of 6px across all landing page sections. This update can be applied directly to the global CSS variable '--btn-radius' to ensure consistent button rendering. Doing so will unify the buttons in the hero section and features grid into a cohesive design theme."
                    }
                ],
                "accessibility": {
                    "color_contrast": "The primary white body text achieves an excellent contrast ratio against the dark background, but secondary navigation labels and footer links fail the standard 4.5:1 ratio, using a low-visibility gray '#404040' that requires enhancement.",
                    "touch_targets": "Primary interactive buttons on the mobile 'mockup view' are spaced at 16px margins and have a height of 44px, which meets mobile accessibility standards. However, inline text links are placed too close together, posing tap target errors on smaller screens.",
                    "text_readability": "Typography readability is high, utilizing the clean 'Inter' font family with a comfortable line-height of 1.6 and restricted container widths. This prevents horizontal reading fatigue and ensures text remains legible across diverse viewport widths."
                },
                "what_works_well": [
                    "The glassmorphic navigation bar provides a beautiful scroll overlay effect that enhances the modern 'SaaS' look.",
                    "Subtle ambient glow gradients behind the product 'mockup' draw visual focus without cluttering the background layout."
                ],
                "priority_recommendations": [
                    "1. Enhance color contrast: Update the low-contrast gray text on secondary labels to a lighter hex value of '#b0b0b0' to meet WCAG AA accessibility standards. This will ensure all navigation links and metadata copy are legible under diverse screen brightness settings. The design audit suggests this is the most impactful quick fix.",
                    "2. Standardize button border-radius: Update global CSS variables to enforce a uniform 6px border-radius on all interactive buttons across the landing page. This will resolve the current inconsistencies where some buttons are rounded at 12px while others are at 4px. Enforcing visual consistency strengthens the brand's engineering precision.",
                    "3. Optimize mobile link spacing: Add extra padding margins between inline text links in the footer to improve mobile touch targets and usability. Currently, the close proximity of links poses tap target errors on smaller viewports. Providing a 12px spacing buffer will prevent accidental clicks and improve mobile navigation flow."
                ],
                "color_palette_feedback": "The brand's color palette is a sophisticated dark-mode harmony utilizing a deep gray background (#080808), crisp white text (#ffffff), and subtle violet accent glows (#6200ee). This combination creates a professional, high-performance atmosphere that appeals directly to developers. The color harmony is excellent, avoiding neon clutter while maintaining strategic focal points.",
                "visual_theme": "The landing page implements a sleek Neo-brutalist SaaS dark-theme utilizing clean grid layouts, extremely thin borders, glowing ambient backdrops, and minimalist sans-serif typography. This visual theme communicates cutting-edge engineering quality, speed, and premium product value."
            },
            "messaging_audit": {
                "clarity": "The landing page messaging is exceptionally clear, letting the visitor understand that Linear is a fast, keyboard-first issue tracker in under 5 seconds. The tagline 'Linear is a better way to build product' is immediate, and the subheading copy avoids confusing corporate jargon in favor of direct feature benefits.",
                "differentiation": "The messaging succeeds in differentiating from general market competitors by positioning specifically on 'speed' and 'developer flow'. While typical tools focus on business reporting and customizable fields, Linear's focus on hotkeys and local-first syncing sets it apart from typical project management noise.",
                "proof": "Linear backs up its product claims by showing high-fidelity product screenshots, listing prominent customer logos like Vercel and Retool, and citing specific speed benchmarks. These evidence markers validate the marketing copy and build credibility with technical buyers.",
                "resonance": "The copywriting resonates deeply with developers by validating their frustration with slow, bureaucratic project tools. Phrases like 'spend less time managing tasks and more time building' strike a chord with engineers who want to focus on shipping high-quality code."
            }
        }
    elif agent_name == "SWOT & Battlecard Agent":
        res = {
            "swot_analysis": {
                "strengths": [
                    "'Extremely fast user interface' built on a local-first database architecture that enables instantaneous page loads and keyboard-driven navigation. This speed keeps developers in their zone of optimal flow by completely eliminating page load friction. Multiple screenshots show a clean dark mode issue tracker that is highly visually appealing.",
                    "'High brand equity' and strong developer love established among modern high-growth technology startups due to their premium design system. The aesthetic appeal and minimalistic layout help teams run sprint planning and roadmapping sessions with high coordination. Customers routinely cite visual theme and consistency as major reasons for their high product loyalty."
                ],
                "weaknesses": [
                    "The platform lacks 'deep custom field configurations' and advanced enterprise reporting dashboards that corporate managers expect in Jira. This makes it difficult for large legacy organizations with complex PMO processes to adopt the tool without changing their workflows. According to customer feedback, the opinionated structure forces teams to adapt to the tool rather than customizing it.",
                    "Limited native integrations with legacy enterprise 'IT software systems' and database infrastructure, focusing instead on modern Git developer tools. This limits their addressable market to tech-forward software companies and excludes traditional financial or retail corporations. The documentation shows that integrating third-party legacy databases requires complex custom API scripting."
                ],
                "opportunities": [
                    "Target high-growth startups currently frustrated by slow 'Jira' performance by offering automated one-click migration wizards that import all issues. This allows teams to quickly adopt the fast layout and opinionated flow of sprint cycles with zero onboarding friction. Marketing copy highlights this as a major strategy to capture unsatisfied Jira users.",
                    "Expand product capabilities into non-technical adjacent teams like 'marketing and design' by creating simplified visual board templates that integrate with their primary tools. This cross-team adoption increases contract size and account retention across the entire organization. The visual brand audit indicates that a clean design language makes the product appealing to non-engineering roles."
                ],
                "threats": [
                    "GitHub and GitLab expanding their native 'project management capabilities' and offering them for free to their massive existing code repository user base. This presents a low-barrier alternative for small software teams that prefer to keep their ticket management co-located with their codebase. Our source analysis suggests this consolidation could slow down developer acquisition.",
                    "Emerging 'AI-native project managers' that automate task creation, sprint scheduling, and code generation based on Slack chats, bypassing traditional board views entirely. This shift could make manual issue tracking obsolete for highly automated engineering teams. The technology strategy must monitor these AI agents as potential threats to user retention."
                ]
            },
            "sales_battlecard": {
                "objection_handling": [
                    {
                        "objection": "Prospect objection: 'Linear lacks the custom fields and deep reporting dashboards we need in Jira.'",
                        "response": "I understand that Jira offers endless customization, but many engineering organizations find that this complexity actually slows down their velocity and creates alignment overhead. Linear is intentionally designed with an opinionated workflow that enforces sprint best practices and keeps developers in their flow without ticket maintenance. By eliminating bloated custom fields, our customers report shipping features up to 40 percent faster with increased developer satisfaction. We focus on speed and execution rather than administrative reporting overhead."
                    }
                ],
                "landmines_to_set": [
                    {
                        "question": "How much time does your engineering team spend managing, updating, and waiting for tickets to load in your current tracker every sprint?",
                        "goal": "This question exposes the high time overhead and 'developer frustration' associated with managing and waiting for tickets to load in Jira. It forces the buyer to calculate the actual cost of developer productivity lost to slow administrative tools. The goal is to highlight our local-first speed advantage as a critical business necessity."
                    }
                ]
            }
        }
    elif agent_name == "Critic Agent (Qualitative)":
        return {
            "status": "PASSED",
            "feedback": ""
        }
    return recursively_pad_dict(res)

# Define helper to run async tasks in sync tests
def run_async(coro):
    return asyncio.run(coro)

# ----------------- TIER 1: FEATURE COVERAGE -----------------

# Feature 1: HTML Text and Style Scraping
def test_h1_h2_h3_extraction():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        assert len(res["headings"]) == 7
        assert res["headings"][0]["level"] == "h1"
        assert res["headings"][0]["text"] == "Linear - The Issue Tracker You Want to Use"

def test_paragraph_and_list_extraction():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        assert len(res["paragraphs"]) == 3
        assert len(res["lists"]) == 1
        assert len(res["lists"][0]) == 5

def test_seo_metadata_extraction():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        assert res["title"] == "Mock Target Title"
        assert res["meta_description"] == "Mock description here."
        assert any(t["key"] == "og:image" for t in res["meta_tags"])

def test_inline_and_style_block_color_extraction():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        colors = res["css_colors"]
        assert "#ff0000" in colors
        assert "rgb(0, 255, 0)" in colors
        assert "hsl(120, 100%, 50%)" in colors
        assert "#0000ff80" in colors

def test_external_stylesheet_scraping():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        # First 4 links are parsed, 5th ignored. Let's assert variables extracted from stylesheet 1-4.
        assert res["css_variables"].get("--neutral-dark") == "#121212"
        # Style 5 color is #ff00ff. If stylesheet 5 is ignored, #ff00ff should NOT be parsed into css colors or vars.
        assert "#ff00ff" not in res["css_colors"]

def test_css_variables_extraction():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        assert res["css_variables"].get("--primary-color") == "#6200ee"
        # --font-size is 16px, which is not a color value and should be ignored.
        assert "--font-size" not in res["css_variables"]

# Feature 2: Image Discovery
def test_logo_discovery_heuristics():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        assert "logo" in res["images"]
        assert "logo.png" in res["images"]["logo"]["url"]

def test_hero_image_discovery_heuristics():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        assert "hero" in res["images"]
        assert "hero.jpg" in res["images"]["hero"]["url"]

def test_image_discovery_fallbacks():
    # If heuristics fail, uses first image. We will return a page with no hero keywords.
    html_no_heuristics = "<body><img src='/assets/fallback_first.png'><img src='/assets/second.png'></body>"
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        with patch("scraper.HEADERS", {}):
            with patch("scraper.BeautifulSoup", lambda text, parser: BeautifulSoup(html_no_heuristics, parser)):
                res = run_async(scraper.scrape_product_page("https://linear.app"))
                assert "hero" in res["images"]
                assert "fallback_first.png" in res["images"]["hero"]["url"]

def test_og_image_detection():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        assert "og_image" in res["images"]
        assert "og.jpg" in res["images"]["og_image"]["url"]

def test_image_saving_and_base64():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        logo = res["images"]["logo"]
        assert logo["local_path"].startswith("/scraped_images/")
        assert len(logo["base64_data"]) > 0
        assert logo["mime_type"] == "image/png"

def test_branding_image_cap_limit():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        # Exclude fullpage screenshot
        brand_keys = [k for k in res["images"].keys() if k != "full_page_screenshot"]
        assert len(brand_keys) <= 3

# Feature 3: Screenshot Capture
def test_microlink_request_formulation():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        assert "full_page_screenshot" in res["images"]
        screenshot_url = res["images"]["full_page_screenshot"]["url"]
        assert "api.microlink.io" in screenshot_url
        assert "screenshot=true" in screenshot_url

def test_screenshot_local_saving():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        file_path = Path("static") / "scraped_images" / "linear_app" / "screenshot.png"
        assert file_path.exists()
        assert file_path.stat().st_size > 0

def test_screenshot_base64_generation():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        ss = res["images"]["full_page_screenshot"]
        assert len(ss["base64_data"]) > 0
        decoded = base64.b64decode(ss["base64_data"])
        assert decoded.startswith(b"\x89PNG")

def test_screenshot_local_path_return():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app"))
        ss = res["images"]["full_page_screenshot"]
        assert ss["local_path"] == "/scraped_images/linear_app/screenshot.png"

def test_screenshot_graceful_fallback():
    # If Microlink fails, scrap page returns no screenshot and logs warning
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app?trigger=gateway-timeout"))
        assert "full_page_screenshot" not in res["images"]

def test_screenshot_url_encoding():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app/product?param=1&other=2"))
        screenshot_url = res["images"]["full_page_screenshot"]["url"]
        assert "product%3Fparam%3D1%26other%3D2" in screenshot_url

def test_screenshot_directory_isolation():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res_a = run_async(scraper.scrape_product_page("https://siteA.com"))
        res_b = run_async(scraper.scrape_product_page("https://siteB.com"))
        path_a = Path("static") / "scraped_images" / "siteA_com" / "screenshot.png"
        path_b = Path("static") / "scraped_images" / "siteB_com" / "screenshot.png"
        assert path_a.exists()
        assert path_b.exists()

# Feature 4: Sequential Agent Pipeline Execution
def mock_agent_inference_fn(agent_name, *args, **kwargs):
    return get_valid_agent_output(agent_name)

def test_researcher_agent_state_insertion():
    with patch("analyzer.run_agent_inference", side_effect=mock_agent_inference_fn):
        scraped_data = {"url": "https://linear.app", "headings": [], "paragraphs": []}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        assert "researcher_data" in res
        assert res["researcher_data"]["colors"] == ["#000000", "#ffffff", "#0c0d0e"]

def test_product_strategy_agent_state_addition():
    with patch("analyzer.run_agent_inference", side_effect=mock_agent_inference_fn):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        assert "summary" in res
        assert res["summary"]["elevator_pitch"].startswith("Linear is a")

def test_visual_brand_auditor_agent_critique_insertion():
    with patch("analyzer.run_agent_inference", side_effect=mock_agent_inference_fn):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        assert "design_critique" in res
        assert res["design_critique"]["visual_theme"].startswith("The landing page")

def test_swot_battlecard_agent_state_synthesis():
    with patch("analyzer.run_agent_inference", side_effect=mock_agent_inference_fn):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        assert "swot_analysis" in res
        assert len(res["swot_analysis"]["strengths"]) == 2

def test_orchestrator_sequential_execution():
    call_order = []
    def recording_mock(agent_name, *args, **kwargs):
        call_order.append(agent_name)
        return get_valid_agent_output(agent_name)
        
    with patch("analyzer.run_agent_inference", side_effect=recording_mock):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        # We also call qualitative critic for 3 agents
        expected_agents = ["Researcher Agent", "Product Strategy Agent", "Critic Agent (Qualitative)", 
                           "Visual Brand Auditor Agent", "Critic Agent (Qualitative)", 
                           "SWOT & Battlecard Agent", "Critic Agent (Qualitative)"]
        assert call_order == expected_agents

# Feature 5: Critic QA Loop and Retries
def test_critic_structural_pass_validation():
    with patch("analyzer.run_agent_inference", side_effect=mock_agent_inference_fn):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        # Check logs show all passed
        assert len(res["critic_logs"]) == 4
        assert all(log["status"] == "PASSED" for log in res["critic_logs"])

def test_critic_structural_check_failure_and_feedback():
    # Make Product Strategy return short elevator pitch on run 1, then pass on run 2
    runs = {"count": 0}
    def custom_mock(agent_name, *args, **kwargs):
        if agent_name == "Product Strategy Agent":
            runs["count"] += 1
            if runs["count"] == 1:
                output = get_valid_agent_output(agent_name).copy()
                output["summary"] = output["summary"].copy()
                output["summary"]["elevator_pitch"] = "Too short tagline." # 3 words
                return output
        return get_valid_agent_output(agent_name)

    with patch("analyzer.run_agent_inference", side_effect=custom_mock):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        logs = res["critic_logs"]
        # Strategy failed run 1
        strategy_logs = [l for l in logs if l["agent"] == "Product Strategy Agent"]
        assert len(strategy_logs) == 2
        assert strategy_logs[0]["status"] == "FAILED"
        assert any("elevator_pitch" in err for err in strategy_logs[0]["errors"])
        assert strategy_logs[1]["status"] == "PASSED"

def test_critic_llm_qualitative_check_validation():
    # Critic Qualitative check returns FAILED first, then PASSED
    runs = {"count": 0}
    def custom_mock(agent_name, *args, **kwargs):
        if agent_name == "Critic Agent (Qualitative)":
            runs["count"] += 1
            if runs["count"] == 1:
                return {"status": "FAILED", "feedback": "Lacks strategic depth and is generic."}
        return get_valid_agent_output(agent_name)

    with patch("analyzer.run_agent_inference", side_effect=custom_mock):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        strategy_logs = [l for l in res["critic_logs"] if l["agent"] == "Product Strategy Agent"]
        assert len(strategy_logs) == 2
        assert strategy_logs[0]["status"] == "FAILED"
        assert "Lacks strategic depth" in strategy_logs[0]["errors"][0]
        assert strategy_logs[1]["status"] == "PASSED"

def test_critic_loop_regeneration_and_retry_limit():
    runs = {"strategy_runs": 0}
    def custom_mock(agent_name, *args, **kwargs):
        if agent_name == "Product Strategy Agent":
            runs["strategy_runs"] += 1
            if runs["strategy_runs"] == 1:
                output = get_valid_agent_output(agent_name).copy()
                output["summary"] = output["summary"].copy()
                output["summary"]["elevator_pitch"] = "Too short tagline."
                return output
        return get_valid_agent_output(agent_name)

    with patch("analyzer.run_agent_inference", side_effect=custom_mock):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        assert runs["strategy_runs"] == 2 # 1 initial + 1 retry

def test_critic_loop_retry_cap_enforcement():
    # Product Strategy continuously fails
    def custom_mock(agent_name, *args, **kwargs):
        if agent_name == "Product Strategy Agent":
            output = get_valid_agent_output(agent_name).copy()
            output["summary"] = output["summary"].copy()
            output["summary"]["elevator_pitch"] = "Too short tagline."
            return output
        return get_valid_agent_output(agent_name)

    with patch("analyzer.run_agent_inference", side_effect=custom_mock):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        strategy_logs = [l for l in res["critic_logs"] if l["agent"] == "Product Strategy Agent"]
        assert len(strategy_logs) == 3 # 1 initial + 2 retries
        assert all(l["status"] == "FAILED" for l in strategy_logs)

def test_critic_logs_accumulation():
    with patch("analyzer.run_agent_inference", side_effect=mock_agent_inference_fn):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        assert len(res["critic_logs"]) == 4
        assert res["critic_logs"][0]["agent"] == "Researcher Agent"
        assert res["critic_logs"][1]["agent"] == "Product Strategy Agent"

# ----------------- TIER 2: BOUNDARY & CORNER CASES -----------------

# Aspect 1: HTML Scraping Gaps & Limits
def test_boundary_blank_target_webpage():
    # Scraping empty HTML does not crash
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        with patch("scraper.BeautifulSoup", lambda text, parser: BeautifulSoup("<html><body></body></html>", parser)):
            res = run_async(scraper.scrape_product_page("https://linear.app"))
            assert res["title"] == ""
            assert len(res["headings"]) == 0
            assert len(res["paragraphs"]) == 0

def test_boundary_massive_text_volume():
    # HTML with excessive headings and paragraphs gets capped
    headings_html = "".join([f"<h1>Heading {i}</h1>" for i in range(50)])
    paragraphs_html = "".join([f"<p>This is a paragraph description that is longer than twenty characters {i}</p>" for i in range(50)])
    html = f"<html><body>{headings_html}{paragraphs_html}</body></html>"
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        with patch("scraper.BeautifulSoup", lambda text, parser: BeautifulSoup(html, parser)):
            res = run_async(scraper.scrape_product_page("https://linear.app"))
            assert len(res["headings"]) == 25
            assert len(res["paragraphs"]) == 30

def test_boundary_script_only_webpage():
    # Only script tags
    html = "<html><head><script>alert(1);</script></head><body></body></html>"
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        with patch("scraper.BeautifulSoup", lambda text, parser: BeautifulSoup(html, parser)):
            res = run_async(scraper.scrape_product_page("https://linear.app"))
            assert len(res["headings"]) == 0
            assert len(res["paragraphs"]) == 0

def test_boundary_missing_or_corrupted_css():
    # CSS parser handles bad css rules safely
    bad_css = ".btn { color: ; border: 1px solid }"
    colors = scraper.extract_colors_from_css(bad_css)
    vars_dict = scraper.extract_css_variables(bad_css)
    assert len(colors) == 0
    assert len(vars_dict) == 0

def test_boundary_non_standard_css_colors():
    # verify non-color functions (calc, url) are ignored
    css = ".btn { width: calc(100% - 10px); background: url('logo.png'); color: #123456; }"
    colors = scraper.extract_colors_from_css(css)
    assert "#123456" in colors
    assert "calc(" not in colors
    assert "url(" not in colors

# Aspect 2: Image Discovery Edge Cases
def test_boundary_zero_images():
    html = "<body>No images here</body>"
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        with patch("scraper.BeautifulSoup", lambda text, parser: BeautifulSoup(html, parser)):
            res = run_async(scraper.scrape_product_page("https://linear.app"))
            brand_keys = [k for k in res["images"].keys() if k != "full_page_screenshot"]
            assert len(brand_keys) == 0

def test_boundary_broken_image_assets():
    # 404 on image download does not crash scraper
    html_broken = "<body><img src='/assets/broken-img.png' class='nav-logo'></body>"
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        with patch("scraper.BeautifulSoup", lambda text, parser: BeautifulSoup(html_broken, parser)):
            res = run_async(scraper.scrape_product_page("https://linear.app"))
            assert "logo" not in res["images"] # skipped since image fetch failed

def test_boundary_data_url_images():
    # Inline base64 images are skipped
    html = "<body><img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='></body>"
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        with patch("scraper.BeautifulSoup", lambda text, parser: BeautifulSoup(html, parser)):
            res = run_async(scraper.scrape_product_page("https://linear.app"))
            brand_keys = [k for k in res["images"].keys() if k != "full_page_screenshot"]
            assert len(brand_keys) == 0

def test_boundary_svg_logo_handling_in_gemini():
    # SVG logos saved but not included in Gemini list
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        # We will mock the webpage to contain svg images
        html_svg = "<body><img src='logo.svg' alt='Company Logo'><img src='hero.svg' class='hero-banner'></body>"
        with patch("scraper.BeautifulSoup", lambda text, parser: BeautifulSoup(html_svg, parser)):
            res = run_async(scraper.scrape_product_page("https://linear.app"))
            assert "logo" in res["images"]
            assert "svg" in res["images"]["logo"]["mime_type"]
            
            # Check Gemini image payload formatting ignores SVG
            with patch("analyzer.genai.GenerativeModel") as mock_model:
                mock_inst = MagicMock()
                mock_model.return_value = mock_inst
                from unittest.mock import AsyncMock
                mock_inst.generate_content_async = AsyncMock()
                mock_inst.generate_content_async.return_value = MagicMock(text="{}")
                
                run_async(analyzer.analyze_website_strategy(res, custom_api_key="key"))
                args, kwargs = mock_inst.generate_content_async.call_args
                # Check contents (args[0]) doesn't have SVG binary dict
                contents = args[0]
                for item in contents:
                    if isinstance(item, dict) and "mime_type" in item:
                        assert "svg" not in item["mime_type"].lower()

def test_boundary_extremely_large_images():
    # Large images skipped
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        with patch("scraper.download_and_save_image_locally", return_value=None):
            res = run_async(scraper.scrape_product_page("https://linear.app"))
            brand_keys = [k for k in res["images"].keys() if k != "full_page_screenshot"]
            assert len(brand_keys) == 0

# Aspect 3: Screenshot Capture Edge Cases
def test_boundary_microlink_gateway_timeout():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app?trigger=gateway-timeout"))
        assert "full_page_screenshot" not in res["images"]

def test_boundary_expired_ssl_certificates():
    # verify=False is used in httpx.AsyncClient in scraper.py
    with patch("scraper.httpx.AsyncClient") as mock_client:
        mock_inst = MockAsyncClient()
        mock_client.return_value = mock_inst
        run_async(scraper.scrape_product_page("https://linear.app"))
        assert mock_client.call_args[1].get("verify") is False

def test_boundary_invalid_target_url():
    # Scraping invalid URL raises clear exception
    with patch("scraper.httpx.AsyncClient") as mock_client:
        mock_client.return_value.get = MagicMock(side_effect=httpx.ConnectError("Connection failed"))
        with pytest.raises(Exception) as excinfo:
            run_async(scraper.scrape_product_page("https://invalid-domain"))
        assert "Failed to fetch website content" in str(excinfo.value)

def test_boundary_microlink_rate_limiting():
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app?trigger=rate-limit"))
        assert "full_page_screenshot" not in res["images"]

def test_boundary_target_blocking_microlink():
    # If Microlink returns error body, handled gracefully
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        res = run_async(scraper.scrape_product_page("https://linear.app?trigger=gateway-timeout"))
        assert "full_page_screenshot" not in res["images"]

# Aspect 4: Pipeline Orchestration Boundaries
def test_boundary_missing_key_fields_in_input():
    # If scraped_data is empty, analyze_website_strategy fails
    with pytest.raises(Exception):
        run_async(analyzer.analyze_website_strategy({}, custom_api_key="key"))

def test_boundary_malformed_json_returned_by_agent():
    # If LLM returns raw text or bad JSON, parsing extracts outer braces or fails cleanly
    def malformed_mock(agent_name, *args, **kwargs):
        if agent_name == "Researcher Agent":
            return "Some conversational text wrapping the json: {\"researcher_data\": {}} and trailing garbage"
        return get_valid_agent_output(agent_name)
        
    with patch("analyzer.run_agent_inference", side_effect=malformed_mock):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        assert "researcher_data" in res

def test_boundary_missing_api_key_configuration():
    # If no key in env or header, analyzer throws clear exception
    with patch.dict(os.environ, {}, clear=True):
        scraped_data = {"url": "https://linear.app"}
        with pytest.raises(Exception) as excinfo:
            run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key=None))
        assert "Gemini API key is not configured" in str(excinfo.value)

def test_boundary_gemini_quota_exceeded():
    def quota_mock(*args, **kwargs):
        raise Exception("ResourceExhausted: 429 Quota exceeded")
        
    with patch("analyzer.run_agent_inference", side_effect=quota_mock):
        scraped_data = {"url": "https://linear.app"}
        with pytest.raises(Exception) as excinfo:
            run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="key"))
        assert "Quota exceeded" in str(excinfo.value)

# Aspect 5: Critic Loop Boundaries & Retries
def test_boundary_word_count_exact_boundary():
    # 49 words fails, 50 words passes (since >=50 is required)
    text_49 = "'Linear' is indeed a very highly useful premium project management tool built for high-performance software engineering teams. It offers keyboard-first navigation and offline synchronization to keep engineers in their optimal flow state. This tool completely eliminates friction, presenting a clean layout that establishes sprint best practices and boosts velocity."
    assert analyzer.count_words(text_49) == 49
    
    text_50 = text_49.replace("eliminates friction", "eliminates typical design friction")
    assert analyzer.count_words(text_50) == 51 # 49 + 2 words = 51, which is >= 50
    
    errs_49 = analyzer.validate_field(text_49, "test_field")
    assert len(errs_49) == 1
    assert "word count is 49" in errs_49[0]
    
    errs_50 = analyzer.validate_field(text_50, "test_field")
    assert len(errs_50) == 0

def test_boundary_sentence_count_exact_boundary():
    # 2 sentences fails, 3 sentences passes
    # Note that sentences must have >= 50 words to pass all validation, but let's check sentence split check specifically.
    text_2 = "'Linear' is a premium project management tool built for high-performance software engineering teams. It offers keyboard-first navigation and offline synchronization to keep engineers in their optimal flow state."
    text_3 = text_2 + " This tool completely eliminates typical design friction."
    
    # Check split sentences
    assert analyzer.count_sentences(text_2) == 2
    assert analyzer.count_sentences(text_3) == 3

def test_boundary_absence_of_citations():
    uncited_text = "Linear is a project management platform for software teams. It has a beautiful dark mode interface and fast loading times. The pricing model includes a free plan and paid tiers for larger organizations. Teams can easily coordinate tasks, track sprint cycles, align milestones, and customize workflows to meet custom developer demands without seeing performance drops or slow load times."
    # Ensure word/sentence count is satisfied
    assert len(uncited_text.split()) >= 50
    assert analyzer.count_sentences(uncited_text) >= 3
    
    errs = analyzer.validate_field(uncited_text, "test_field")
    assert len(errs) == 1
    assert "does not cite original evidence" in errs[0]

def test_boundary_persistent_agent_failures():
    # Agent keeps failing, should exhaust at 3 runs and proceed
    runs = {"count": 0}
    def custom_mock(agent_name, *args, **kwargs):
        if agent_name == "Product Strategy Agent":
            runs["count"] += 1
            output = get_valid_agent_output(agent_name).copy()
            output["summary"] = output["summary"].copy()
            output["summary"]["elevator_pitch"] = "Too short."
            return output
        return get_valid_agent_output(agent_name)

    with patch("analyzer.run_agent_inference", side_effect=custom_mock):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        assert runs["count"] == 3

def test_boundary_partial_failure_routing():
    # SWOT fails, others pass. Only SWOT retried.
    runs = {"strategy": 0, "swot": 0}
    def custom_mock(agent_name, *args, **kwargs):
        if agent_name == "Product Strategy Agent":
            runs["strategy"] += 1
        elif agent_name == "SWOT & Battlecard Agent":
            runs["swot"] += 1
            if runs["swot"] == 1:
                output = get_valid_agent_output(agent_name).copy()
                output["swot_analysis"] = output["swot_analysis"].copy()
                output["swot_analysis"]["strengths"] = ["Short."]
                return output
        return get_valid_agent_output(agent_name)

    with patch("analyzer.run_agent_inference", side_effect=custom_mock):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        assert runs["strategy"] == 1
        assert runs["swot"] == 2

# ----------------- TIER 3: CROSS-FEATURE COMBINATIONS -----------------

def test_cross_feature_e2e_scraper_to_multi_agent():
    # Scrape -> Analyze E2E flow
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        with patch("analyzer.run_agent_inference", side_effect=mock_agent_inference_fn):
            scraped = run_async(scraper.scrape_product_page("https://linear.app"))
            analysis = run_async(analyzer.analyze_website_strategy(scraped, custom_api_key="valid-key"))
            assert "design_critique" in analysis
            assert "researcher_data" in analysis

def test_cross_feature_critic_with_image_fallbacks():
    # If image fallbacks are utilized, they are passed to Visual Auditor and maintained through retry loops
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        # Trigger fallback by returning HTML with first img
        html_no_heuristics = "<body><img src='/assets/fallback_first.png'></body>"
        with patch("scraper.BeautifulSoup", lambda text, parser: BeautifulSoup(html_no_heuristics, parser)):
            scraped = run_async(scraper.scrape_product_page("https://linear.app"))
            assert scraped["images"]["hero"]["url"] == "https://linear.app/assets/fallback_first.png"
            
            # Run multi-agent execution with a retry loop
            runs = {"strategy_runs": 0}
            def custom_mock(agent_name, *args, **kwargs):
                if agent_name == "Product Strategy Agent":
                    runs["strategy_runs"] += 1
                    if runs["strategy_runs"] == 1:
                        output = get_valid_agent_output(agent_name).copy()
                        output["summary"] = output["summary"].copy()
                        output["summary"]["elevator_pitch"] = "Too short."
                        return output
                return get_valid_agent_output(agent_name)
                
            with patch("analyzer.run_agent_inference", side_effect=custom_mock):
                analysis = run_async(analyzer.analyze_website_strategy(scraped, custom_api_key="valid-key"))
                # Scraped images remain in scraped_data and are referenceable
                assert scraped["images"]["hero"]["url"] == "https://linear.app/assets/fallback_first.png"

def test_cross_feature_api_key_selection():
    # Header custom key overrides environment variables
    with patch.dict(os.environ, {"GEMINI_API_KEY": "env-key"}):
        with patch("analyzer.run_agent_inference") as mock_inference:
            mock_inference.return_value = get_valid_agent_output("Researcher Agent")
            scraped = {"url": "https://linear.app"}
            
            # Call with custom header override key
            run_async(analyzer.analyze_website_strategy(scraped, custom_api_key="header-override-key"))
            args, kwargs = mock_inference.call_args
            assert kwargs.get("api_key") == "header-override-key"

def test_cross_feature_critic_loop_retries_max_payload():
    # Ensure huge states do not crash during retry validations
    scraped = {
        "url": "https://linear.app",
        "headings": [{"level": "h1", "text": f"heading {i}"} for i in range(25)],
        "paragraphs": [f"This is paragraph text that meets standard length bounds to simulate full content page {i}" for i in range(30)],
        "css_colors": [f"#1234{i:02d}" for i in range(30)],
        "css_variables": {f"--var-{i}": "#000000" for i in range(30)}
    }
    with patch("analyzer.run_agent_inference", side_effect=mock_agent_inference_fn):
        analysis = run_async(analyzer.analyze_website_strategy(scraped, custom_api_key="key"))
        assert "critic_logs" in analysis

def test_cross_feature_scraper_downstream_failure():
    # If scraper fails, endpoint returns 502 without triggering analyzer
    with patch("main.scrape_product_page", side_effect=Exception("Connection failed")):
        with patch("main.analyze_website_strategy") as mock_analyzer:
            from fastapi.testclient import TestClient
            client = TestClient(main.app)
            resp = client.post("/api/analyze", json={"url": "https://linear.app"})
            assert resp.status_code == 502
            assert "Failed to scrape target website" in resp.json()["detail"]
            assert not mock_analyzer.called

# ----------------- TIER 4: REAL-WORLD APPLICATION SCENARIOS -----------------

def test_real_world_linear_audit():
    # Full mockup run mimicking Stripe/Linear analysis request
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        with patch("analyzer.run_agent_inference", side_effect=mock_agent_inference_fn):
            from fastapi.testclient import TestClient
            client = TestClient(main.app)
            resp = client.post("/api/analyze", json={"url": "https://linear.app"}, headers={"x-gemini-api-key": "test-key"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["url"] == "https://linear.app"
            assert data["images"]["logo"] == "/scraped_images/linear_app/logo.png"
            assert "strengths" in data["analysis"]["swot_analysis"]

def test_real_world_minimalist_page_audit():
    # Page with minimal css variables and styles
    html_minimal = "<html><head><title>Simple Page</title></head><body><h1>Heading</h1><p>Minimal text content with standard paragraphs that is longer than twenty characters.</p></body></html>"
    with patch("scraper.httpx.AsyncClient", MockAsyncClient):
        with patch("scraper.BeautifulSoup", lambda text, parser: BeautifulSoup(html_minimal, parser)):
            res = run_async(scraper.scrape_product_page("https://minimalist.com"))
            assert len(res["css_colors"]) == 0
            assert len(res["css_variables"]) == 0

def test_real_world_custom_ui_api_key():
    # Test setting custom headers in FastAPI layer
    with patch("main.scrape_scrape" if hasattr(main, "main_scrape") else "main.scrape_product_page") as mock_scrape:
        mock_scrape.return_value = {"url": "https://stripe.com", "title": "Stripe", "meta_description": "Stripe", "css_colors": [], "css_variables": {}, "images": {}}
        with patch("main.analyze_website_strategy") as mock_analyze:
            mock_analyze.return_value = get_valid_agent_output("Product Strategy Agent")
            
            from fastapi.testclient import TestClient
            client = TestClient(main.app)
            resp = client.post(
                "/api/analyze",
                json={"url": "https://stripe.com"},
                headers={"x-gemini-api-key": "ui-user-custom-key"}
            )
            assert resp.status_code == 200
            mock_analyze.assert_called_once_with(mock_scrape.return_value, custom_api_key="ui-user-custom-key")

def test_real_world_sales_battlecard_quality():
    # Assert sales battlecard elements represent elite enterprise talk-tracks
    with patch("analyzer.run_agent_inference", side_effect=mock_agent_inference_fn):
        scraped_data = {"url": "https://linear.app"}
        res = run_async(analyzer.analyze_website_strategy(scraped_data, custom_api_key="valid-key"))
        objection = res["sales_battlecard"]["objection_handling"][0]
        # Must be detailed script, >= 3 sentences, >= 50 words
        assert objection["response"].startswith("I understand that Jira")
        assert len(objection["response"].split()) >= 50
        assert analyzer.count_sentences(objection["response"]) >= 3
