import os
import anthropic
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import re

# ─── If running in Jupyter, keep IPython display ───────────────────────────
try:
    from IPython.display import HTML, display as ipy_display
    IN_JUPYTER = True
except ImportError:
    IN_JUPYTER = False

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ───────────────────────────────────────────────────────────────────────────
# SCRAPER
# ───────────────────────────────────────────────────────────────────────────

def fetch_website_contents(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["nav", "footer", "aside", "script", "style", "header"]):
        tag.decompose()
    elements = soup.find_all(["p", "h1", "h2", "h3", "h4", "li"])
    text = "\n".join(el.get_text(strip=True) for el in elements if el.get_text(strip=True))
    print(f"[DEBUG] Scraped {len(text)} characters, ~{len(text)//4} tokens")
    return text

# ───────────────────────────────────────────────────────────────────────────
# PROMPTS
# ───────────────────────────────────────────────────────────────────────────

system_prompt = """
You are a travel guide summarizer. Your job is to transform ONLY the provided source text into a decision-ready travel summary and itinerary.

HARD RULES (anti-hallucination):
- Use ONLY facts, places, restaurants, attractions, neighborhoods, transit options, and tips that appear in the Source Text.
- If a detail is not stated in the Source Text, write "Not specified in source" (do NOT guess).
- Do NOT add extra attractions "you know" about. No external knowledge.
- Do NOT fabricate opening hours, prices, distances, ticket rules, safety warnings, or seasonal advice unless explicitly stated.
- If the Source Text is thin or vague, output fewer items rather than inventing.
- When in doubt, prefer omission + "Not specified in source".

STYLE:
- Be crisp. Use bullet points. No marketing fluff.
- Keep each bullet to one line when possible.
- Cluster items geographically ONLY if the Source Text mentions neighborhoods/areas; otherwise group by "Theme".
- If the Source Text contains conflicting info, mention both and label as "Source conflict".

OUTPUT TEMPLATE (follow exactly; keep headings as written):

## City Snapshot
- Best time to visit: <from source or "Not specified in source">
- Vibe: 
  - <bullet 1 from source>
  - <bullet 2 from source>
- Getting around:
  - <how to move around, from source or "Not specified in source">
- Typical costs:
  - Budget: <from source or "Not specified in source">
  - Mid: <from source or "Not specified in source">
  - Splurge: <from source or "Not specified in source">

## Top Picks
### Must-dos (up to 5; fewer if source is limited)
For each item:
- <Place / attraction name> — <why it's worth it per source> (Time needed: <if stated; else "Not specified in source">)

### Neighborhoods / Areas (up to 3; only if mentioned in source)
- <Area> — <what it's good for per source>

### Food Highlights (only if mentioned in source)
- What to eat:
  - <dish/food> — <context per source>
- Where to try it:
  - <place name> — <why per source>

## Itinerary
Rules:
- Use ONLY items from the Source Text.
- Keep each day to 5–6 stops (moderate pace).
- If you cannot infer location clustering from the source, label sections "Theme-based grouping".

### Day 1
- Morning: <stop 1>, <stop 2>
- Lunch: <food suggestion from source or "Not specified in source">
- Afternoon: <stop 3>, <stop 4>
- Evening: <stop 5>
Notes: <reservation / timing / caution from source>

(Repeat pattern for all days covered by trip length)

## Practical Tips (from source only)
- Do:
  - <tip 1>
- Avoid:
  - <trap/avoidance tip 1>
- Logistics:
  - <tickets/passes/opening hours/closures only if stated>

## If you only do 3 things…
1) <thing 1>
2) <thing 2>
3) <thing 3>

## Source Coverage (honesty check)
- Key places/areas mentioned in source but not included above (if any): <list or "None">
- Anything the user asked for that the source did not provide: <list with "Not specified in source">

SOURCE TEXT (the only truth you may use):
<<<
{PASTE THE WEBSITE TEXT HERE}
>>>
"""

user_prompt_prefix = """
Summarize the SOURCE TEXT into the exact template you were instructed to use.

Trip length: 10 days
Pace: moderate
Interests: local food, scenic walks/viewpoints, culture/history (light museums okay)
Constraints: avoid long drives; top hikes; prefer clustered areas per day if the source names neighborhoods; budget: mid

Important:
- Use ONLY what's in the SOURCE TEXT. If something is missing, write "Not specified in source."
- Do not add attractions or facts from memory.
- If the source is thin, output fewer items rather than guessing.

SOURCE TEXT:
<<<
"""

# ───────────────────────────────────────────────────────────────────────────
# API CALL
# ───────────────────────────────────────────────────────────────────────────

def messages_for(website):
    return [{"role": "user", "content": user_prompt_prefix + website + "\n>>>"}]

def summarize(url):
    website = fetch_website_contents(url)
    msgs = messages_for(website)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        system=system_prompt,
        max_tokens=8192,
        messages=msgs
    )
    return response.content[0].text

# ───────────────────────────────────────────────────────────────────────────
# MARKDOWN → BEAUTIFUL HTML RENDERER
# ───────────────────────────────────────────────────────────────────────────

def markdown_to_html(md: str) -> str:
    """Convert the structured markdown output into styled HTML sections."""
    lines = md.split("\n")
    html_parts = []
    i = 0

    section_icons = {
        "City Snapshot": "🗺",
        "Top Picks": "⭐",
        "Itinerary": "📅",
        "Practical Tips": "💼",
        "If you only do 3 things": "🎯",
        "Source Coverage": "🔍",
    }

    def flush_list(items):
        if not items:
            return ""
        return "<ul>" + "".join(f"<li>{it}</li>" for it in items) + "</ul>"

    while i < len(lines):
        line = lines[i]

        # H2 section headers
        if line.startswith("## "):
            title = line[3:].strip()
            icon = next((v for k, v in section_icons.items() if k.lower() in title.lower()), "✦")
            html_parts.append(f'<div class="section-card"><div class="section-header"><span class="section-icon">{icon}</span><h2 class="section-title">{title}</h2></div><div class="section-body">')

        # H3 sub-headers (Day 1, Must-dos, etc.)
        elif line.startswith("### "):
            title = line[4:].strip()
            # Day headers get special treatment
            day_match = re.match(r"Day (\d+)", title)
            if day_match:
                html_parts.append(f'<div class="day-block"><div class="day-label">Day {day_match.group(1)}</div>')
            else:
                html_parts.append(f'<h3 class="sub-header">{title}</h3>')

        # Numbered list (If you only do 3 things)
        elif re.match(r"^\d+\)", line.strip()):
            num, text = line.strip().split(")", 1)
            html_parts.append(f'<div class="punch-item"><span class="punch-num">{num.strip()}</span><span class="punch-text">{text.strip()}</span></div>')

        # Bullet points
        elif line.strip().startswith("- "):
            content = line.strip()[2:]
            # Sub-bullets (indented)
            if line.startswith("  - ") or line.startswith("    - "):
                content = line.strip()[2:]
                html_parts.append(f'<div class="sub-bullet">· {content}</div>')
            # Morning/Lunch/Afternoon/Evening time blocks
            elif any(content.startswith(t) for t in ["Morning:", "Lunch:", "Afternoon:", "Evening:", "Notes:"]):
                label, _, rest = content.partition(":")
                html_parts.append(f'<div class="time-block"><span class="time-label">{label}</span><span class="time-content">{rest.strip()}</span></div>')
            # Do / Avoid / Logistics headers
            elif content.strip() in ["Do:", "Avoid:", "Logistics:"]:
                html_parts.append(f'<div class="tips-header">{content.strip()}</div>')
            # Regular bullets
            else:
                # Bold the first part if it has an em-dash
                if " — " in content:
                    name, _, detail = content.partition(" — ")
                    html_parts.append(f'<div class="bullet-item"><span class="bullet-name">{name}</span><span class="bullet-sep"> — </span><span class="bullet-detail">{detail}</span></div>')
                else:
                    html_parts.append(f'<div class="bullet-item">{content}</div>')

        # Close day blocks when we hit a blank line after time blocks
        elif line.strip() == "" and html_parts and 'class="time-block"' in html_parts[-1]:
            html_parts.append('</div>')  # close day-block

        # Plain text / paragraph
        elif line.strip() and not line.startswith("#"):
            html_parts.append(f'<p class="plain-text">{line.strip()}</p>')

        i += 1

    return "\n".join(html_parts)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Travel Guide</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Outfit:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --ink:       #1a1f2e;
    --ink-soft:  #3d4557;
    --ink-muted: #7a8499;
    --paper:     #f7f5f0;
    --paper-2:   #efecea;
    --fjord:     #2b5f6e;
    --fjord-lt:  #3d8296;
    --forest:    #2d5a3d;
    --gold:      #c8933a;
    --snow:      #ffffff;
    --border:    #dedad3;
  }

  body {
    background: var(--paper);
    color: var(--ink);
    font-family: 'Outfit', sans-serif;
    font-size: 15px;
    line-height: 1.65;
    padding: 0;
  }

  /* ── HERO ── */
  .hero {
    background: var(--fjord);
    background-image: 
      radial-gradient(ellipse at 0% 100%, rgba(45,90,61,0.5) 0%, transparent 55%),
      radial-gradient(ellipse at 100% 0%, rgba(200,147,58,0.15) 0%, transparent 50%);
    color: white;
    padding: 56px 40px 48px;
    position: relative;
    overflow: hidden;
  }

  .hero::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, var(--forest), var(--gold), var(--fjord-lt));
  }

  .hero-eyebrow {
    font-size: 11px;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: rgba(255,255,255,0.5);
    margin-bottom: 10px;
    font-weight: 500;
  }

  .hero-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: clamp(38px, 5vw, 62px);
    font-weight: 600;
    line-height: 1.05;
    color: #fff;
    margin-bottom: 14px;
  }

  .hero-title em {
    font-style: italic;
    color: rgba(255,255,255,0.75);
  }

  .hero-meta {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }

  .hero-badge {
    font-size: 12px;
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    padding: 4px 12px;
    border-radius: 2px;
    color: rgba(255,255,255,0.8);
    letter-spacing: 0.5px;
  }

  /* ── LAYOUT ── */
  .guide-body {
    max-width: 820px;
    margin: 0 auto;
    padding: 40px 24px 80px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  /* ── SECTION CARDS ── */
  .section-card {
    background: var(--snow);
    border: 1px solid var(--border);
    border-radius: 3px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  }

  .section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 20px;
    background: var(--paper-2);
    border-bottom: 1px solid var(--border);
  }

  .section-icon { font-size: 16px; }

  .section-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 18px;
    font-weight: 600;
    color: var(--fjord);
    letter-spacing: 0.3px;
  }

  .section-body {
    padding: 20px 24px;
  }

  /* ── SUB-HEADERS ── */
  .sub-header {
    font-family: 'Cormorant Garamond', serif;
    font-size: 15px;
    font-weight: 600;
    color: var(--forest);
    letter-spacing: 1px;
    text-transform: uppercase;
    font-size: 11px;
    margin: 20px 0 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
  }

  .sub-header:first-child { margin-top: 0; }

  /* ── BULLETS ── */
  .bullet-item {
    font-size: 14px;
    color: var(--ink-soft);
    padding: 5px 0 5px 14px;
    border-left: 2px solid var(--border);
    margin-bottom: 6px;
    line-height: 1.5;
  }

  .bullet-name {
    font-weight: 600;
    color: var(--ink);
  }

  .bullet-sep { color: var(--ink-muted); }

  .bullet-detail { color: var(--ink-soft); }

  .sub-bullet {
    font-size: 13px;
    color: var(--ink-muted);
    padding: 3px 0 3px 24px;
    margin-bottom: 3px;
  }

  /* ── TIPS HEADERS ── */
  .tips-header {
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--gold);
    font-weight: 600;
    margin: 16px 0 8px;
  }

  .tips-header:first-child { margin-top: 0; }

  /* ── DAY BLOCKS ── */
  .day-block {
    background: var(--paper);
    border: 1px solid var(--border);
    border-radius: 3px;
    margin-bottom: 14px;
    overflow: hidden;
  }

  .day-label {
    font-family: 'Cormorant Garamond', serif;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: white;
    background: var(--fjord);
    padding: 8px 16px;
  }

  .time-block {
    display: flex;
    gap: 12px;
    padding: 9px 16px;
    border-bottom: 1px solid var(--border);
    align-items: flex-start;
  }

  .time-block:last-child { border-bottom: none; }

  .time-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--fjord-lt);
    min-width: 80px;
    padding-top: 2px;
    flex-shrink: 0;
  }

  .time-content {
    font-size: 13px;
    color: var(--ink-soft);
    line-height: 1.5;
  }

  /* ── PUNCH LIST ── */
  .punch-item {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    padding: 14px 0;
    border-bottom: 1px solid var(--border);
  }

  .punch-item:last-child { border-bottom: none; }

  .punch-num {
    font-family: 'Cormorant Garamond', serif;
    font-size: 42px;
    font-weight: 600;
    color: var(--gold);
    opacity: 0.35;
    line-height: 1;
    flex-shrink: 0;
  }

  .punch-text {
    font-size: 15px;
    color: var(--ink);
    padding-top: 8px;
    line-height: 1.5;
    font-weight: 500;
  }

  /* ── PLAIN TEXT ── */
  .plain-text {
    font-size: 14px;
    color: var(--ink-soft);
    margin-bottom: 8px;
    line-height: 1.6;
  }

  /* ── SOURCE COVERAGE ── */
  .section-card:last-child .section-header {
    background: #f0f4f5;
  }

  .section-card:last-child .section-title {
    color: var(--ink-muted);
    font-size: 14px;
  }

  @media (max-width: 600px) {
    .hero { padding: 36px 20px 32px; }
    .guide-body { padding: 24px 16px 60px; }
    .time-block { flex-direction: column; gap: 4px; }
    .time-label { min-width: unset; }
  }
</style>
</head>
<body>

<div class="hero">
  <div class="hero-eyebrow">✦ Travel Guide</div>
  <h1 class="hero-title">Norway<br/><em>10-Day Road Trip</em></h1>
  <div class="hero-meta">
    <span class="hero-badge">🗓 10 Days</span>
    <span class="hero-badge">🚗 Road Trip</span>
    <span class="hero-badge">💰 Mid Budget</span>
    <span class="hero-badge">🥾 Moderate Pace</span>
  </div>
</div>

<div class="guide-body">
  {CONTENT}
</div>

</body>
</html>
"""


def render_html(markdown_text: str, url: str = "") -> str:
    body_html = markdown_to_html(markdown_text)
    return HTML_TEMPLATE.replace("{CONTENT}", body_html)


def display_summary(url: str):
    print(f"Fetching and summarizing: {url}")
    md = summarize(url)

    html = render_html(md, url)

    if IN_JUPYTER:
        ipy_display(HTML(html))
    else:
        # Save to file and open in browser
        import webbrowser, tempfile, pathlib
        out = pathlib.Path(tempfile.mktemp(suffix=".html"))
        out.write_text(html, encoding="utf-8")
        print(f"[OUTPUT] Saved to {out}")
        webbrowser.open(f"file://{out}")

    return html


# ── Run ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    display_summary("https://www.crazytravelista.com/norway-10-day-itinerary/")
