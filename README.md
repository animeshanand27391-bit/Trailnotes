# Trailnotes
My digital passport
🥾 trailnotes

Paste any travel blog URL. Get a clean, structured city guide — in seconds.

trailnotes scrapes travel blogs and passes the content to Claude (Anthropic) to extract a decision-ready guide: city snapshot, top picks, day-by-day itinerary, practical tips, and a 3-thing punch list. Output renders as a beautiful HTML page (in browser or Jupyter).

✨ What It Does
InputOutputAny travel blog URLStructured HTML travel guidee.g. Nomadic Matt, Crazy Travelista, Condé NastCity snapshot · Top picks · Itinerary · Tips
Anti-hallucination by design — Claude is instructed to use only what's in the source text. If something isn't mentioned, it says so instead of guessing.

📸 Output Sections

✈️ City Snapshot — best time to visit, vibe, getting around, cost ranges
⭐ Top Picks — must-dos, neighborhoods, food highlights
📅 Itinerary — day-by-day plan (morning / lunch / afternoon / evening)
💼 Practical Tips — do this, avoid that, logistics
🎯 If You Only Do 3 Things… — the essential punch list
🔍 Source Coverage — honesty check on what the source did/didn't cover


🚀 Quickstart
1. Clone the repo
bashgit clone https://github.com/YOUR_USERNAME/trailnotes.git
cd trailnotes
2. Install dependencies
bashpip install anthropic requests beautifulsoup4 python-dotenv
3. Set your API key
Create a .env file in the root:
ANTHROPIC_API_KEY=your_key_here
Get a key at console.anthropic.com.
4. Run it
In a Jupyter notebook:
pythonfrom travel_summarizer_pretty import display_summary
display_summary("https://www.nomadicmatt.com/travel-guides/japan-travel-tips/")
From the terminal:
bashpython travel_summarizer_pretty.py
Swap in your URL at the bottom of the file. The guide opens automatically in your browser.

⚙️ Customization
At the top of travel_summarizer_pretty.py, edit the user prompt to match your trip:
pythonUSER_PROMPT_PREFIX = """
Trip length: 3 days
Pace: chill          # chill / moderate / packed
Interests: food, architecture, nightlife
Constraints: no long walks, budget: mid
...

🗂️ Project Structure
trailnotes/
├── travel_summarizer_pretty.py   # main script — scraper + Claude + HTML renderer
├── .env                          # your API key (never commit this)
├── .gitignore
└── README.md

🔒 .gitignore
Make sure your .env is never committed:
.env
__pycache__/
*.pyc

🧠 How It Works
URL → BeautifulSoup scraper → clean text → Claude (claude-sonnet-4-6)
    → structured markdown → HTML renderer → rendered guide
The scraper strips nav, footer, ads, and scripts — extracting only paragraph and heading content. The full text is passed to Claude with a strict system prompt that forbids hallucination and enforces the output template. The markdown response is then parsed into a styled HTML page with a Nordic-inspired design.

📦 Dependencies
PackagePurposeanthropicClaude API clientrequestsHTTP page fetchingbeautifulsoup4HTML parsing & cleaningpython-dotenv.env key loading

📄 License
MIT — use it, fork it, extend it.

Built with Claude · Scrapes responsibly · No hallucinations by design
