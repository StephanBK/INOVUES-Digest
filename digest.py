#!/usr/bin/env python3
"""
INOVUES Daily News Digest
Scrapes top industry websites + GNews for targeted intelligence.
Curates with Claude AI, sends branded HTML email.
"""

import os
import json
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]
GMAIL_APP_PASS    = os.environ["GMAIL_APP_PASS"]
RECIPIENTS        = os.environ.get("RECIPIENTS", GMAIL_USER).split(",")
GNEWS_API_KEY     = os.environ.get("GNEWS_API_KEY", "")

# ── Top industry news sources to scrape via GNews ─────────────────────────────
QUERIES = [
    # Competitors
    {"category": "Competitors",              "name": "Indow Window",             "q": "Indow Window"},
    {"category": "Competitors",              "name": "Alpen Windows",             "q": "Alpen High Performance Windows"},
    # Utilities
    {"category": "Utilities",               "name": "Con Edison",               "q": "Con Edison commercial energy rebate program"},
    {"category": "Utilities",               "name": "NYSERDA",                  "q": "NYSERDA building energy efficiency incentive"},
    {"category": "Utilities",               "name": "National Grid",             "q": "National Grid commercial building energy program"},
    {"category": "Utilities",               "name": "Eversource",               "q": "Eversource commercial energy efficiency rebate"},
    {"category": "Utilities",               "name": "PSEG",                     "q": "PSEG Long Island energy program commercial"},
    {"category": "Utilities",               "name": "NYPA",                     "q": "New York Power Authority commercial building energy"},
    # City & Policy
    {"category": "Policy & Regulations",    "name": "Local Law 97",             "q": "NYC Local Law 97 building compliance fine enforcement"},
    {"category": "Policy & Regulations",    "name": "NYC DOB",                  "q": "NYC Department of Buildings energy retrofit regulation"},
    {"category": "Policy & Regulations",    "name": "Boston BERDO",             "q": "Boston BERDO building energy reporting decarbonization"},
    {"category": "Policy & Regulations",    "name": "NYC Climate",              "q": "NYC building decarbonization emissions 2025"},
    # Market & Retrofits
    {"category": "Market & Retrofits",      "name": "Office Conversions NYC",   "q": "NYC office to residential hotel conversion 2025"},
    {"category": "Market & Retrofits",      "name": "Building Retrofits",       "q": "commercial building facade window energy retrofit NYC"},
    {"category": "Market & Retrofits",      "name": "Decarbonization Projects", "q": "commercial building decarbonization retrofit New York"},
    {"category": "Market & Retrofits",      "name": "Energy Upgrades",          "q": "commercial building energy upgrade renovation New England 2025"},
    # Industry News
    {"category": "Industry News",           "name": "GreenBiz",                 "q": "site:greenbiz.com building energy efficiency"},
    {"category": "Industry News",           "name": "Buildings Magazine",       "q": "site:buildings.com energy retrofit commercial"},
    {"category": "Industry News",           "name": "CoStar",                   "q": "site:costar.com NYC building renovation energy"},
    {"category": "Industry News",           "name": "Bisnow",                   "q": "site:bisnow.com NYC building retrofit energy"},
    {"category": "Industry News",           "name": "Treehugger/Energy",        "q": "commercial building energy efficiency retrofit window glazing 2025"},
    {"category": "Industry News",           "name": "ArchDaily",                "q": "site:archdaily.com facade retrofit energy"},
    {"category": "Industry News",           "name": "ENR",                      "q": "site:enr.com NYC building retrofit renovation"},
]

INOVUES_CONTEXT = """
INOVUES installs secondary window retrofit systems on commercial buildings in NYC and New England.
Their product overlays existing windows without full replacement, cutting energy loss and helping 
buildings comply with NYC Local Law 97 carbon limits. 
Key interests:
- LL97 fines, enforcement, compliance deadlines
- Utility rebate/incentive programs for window or facade upgrades
- Large commercial building renovation, retrofit, or conversion projects (especially NYC)
- Competitor moves (Indow Window, Alpen Windows)
- New building energy regulations or mandates
- Office-to-residential/hotel conversions (major retrofit opportunity)
- Any building that is upgrading facades, windows, or energy systems
"""

# ── Fetch via GNews ────────────────────────────────────────────────────────────
def fetch_gnews(query: str, n: int = 6) -> list[dict]:
    if not GNEWS_API_KEY:
        return []
    try:
        r = requests.get(
            "https://gnews.io/api/v4/search",
            params={"q": query, "lang": "en", "country": "us", "max": n, "apikey": GNEWS_API_KEY},
            timeout=12
        )
        if r.status_code == 200:
            return [{"title": a["title"], "url": a["url"],
                     "description": a.get("description",""),
                     "source": a.get("source",{}).get("name",""),
                     "publishedAt": a.get("publishedAt","")} for a in r.json().get("articles",[])]
        else:
            print(f"    GNews {r.status_code} for: {query[:50]}")
    except Exception as e:
        print(f"    GNews error: {e}")
    return []


def fetch_all() -> list[dict]:
    raw = []
    for q in QUERIES:
        print(f"  [{q['category']}] {q['name']}")
        articles = fetch_gnews(q["q"])
        for a in articles:
            a["category"] = q["category"]
            a["source_name"] = q["name"]
            raw.append(a)
    # Deduplicate by URL
    seen, unique = set(), []
    for a in raw:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    print(f"  → {len(unique)} unique articles fetched")
    return unique


# ── Claude Curation ────────────────────────────────────────────────────────────
def curate_with_claude(articles: list[dict]) -> dict:
    articles_text = json.dumps(articles, indent=2)

    prompt = f"""You are the news curator for INOVUES.

{INOVUES_CONTEXT}

Here are today's articles fetched from industry sources:
{articles_text}

Instructions:
1. Include ANY article that touches on: building retrofits, window/facade upgrades, energy efficiency programs, LL97/BERDO compliance, office conversions, utility incentive programs, competitor activity, commercial real estate renovations, building decarbonization
2. Be INCLUSIVE — if there's any angle relevant to INOVUES, include it
3. Only exclude articles that are 100% unrelated (purely residential, unrelated industries, sports, politics unrelated to buildings)
4. For each included article write a sharp 1-2 sentence "INOVUES angle" — what does this mean for the business?
5. Score 1-10: 10=direct sales lead or urgent action, 7-9=strong opportunity, 4-6=useful intel, 1-3=background awareness
6. Write one punchy headline summary for the whole digest

Return ONLY valid JSON (no markdown):
{{
  "date": "{datetime.now().strftime('%A, %B %d, %Y')}",
  "headline_summary": "one punchy sentence",
  "categories": [
    {{
      "name": "category name",
      "emoji": "appropriate emoji",
      "stories": [
        {{
          "source_name": "source",
          "title": "title",
          "url": "url",
          "insight": "INOVUES angle in 1-2 sentences",
          "score": 7
        }}
      ]
    }}
  ]
}}

Group stories by their original category. Include all categories that have stories."""

    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": "claude-haiku-4-5", "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}]},
        timeout=90
    )
    r.raise_for_status()
    content = r.json()["content"][0]["text"].strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())


# ── Build HTML ─────────────────────────────────────────────────────────────────
def build_html(digest: dict) -> str:
    date_str   = digest.get("date", datetime.now().strftime('%A, %B %d, %Y'))
    headline   = digest.get("headline_summary", "Your daily INOVUES intelligence briefing.")
    categories = digest.get("categories", [])
    total      = sum(len(c.get("stories",[])) for c in categories)
    active     = sum(1 for c in categories if c.get("stories"))

    cats_html = ""
    for cat in categories:
        stories = cat.get("stories", [])
        if not stories:
            continue
        rows = ""
        for s in sorted(stories, key=lambda x: x.get("score",0), reverse=True):
            sc = s.get("score", 5)
            color = "#1B9FAF" if sc >= 8 else "#5BB8C4" if sc >= 6 else "#9AD4DB"
            rows += f"""
            <tr>
              <td style="padding:16px 0;border-bottom:1px solid #f4f4f4;">
                <table width="100%" cellpadding="0" cellspacing="0"><tr>
                  <td width="8" style="vertical-align:top;padding-top:5px;">
                    <div style="width:8px;height:8px;border-radius:50%;background:{color};"></div>
                  </td>
                  <td style="padding-left:12px;">
                    <p style="margin:0 0 2px;font-size:10px;color:#bbb;text-transform:uppercase;letter-spacing:0.8px;">{s.get('source_name','')}</p>
                    <a href="{s.get('url','#')}" style="font-size:15px;font-weight:600;color:#1a1a1a;text-decoration:none;line-height:1.4;">{s.get('title','')}</a>
                    <p style="margin:7px 0 0;font-size:13px;color:#555;line-height:1.6;border-left:2px solid #1B9FAF;padding-left:10px;font-style:italic;">{s.get('insight','')}</p>
                  </td>
                  <td width="34" style="vertical-align:top;padding-left:8px;text-align:right;">
                    <div style="background:{color};color:white;border-radius:4px;padding:3px 6px;font-size:11px;font-weight:700;display:inline-block;">{sc}</div>
                  </td>
                </tr></table>
              </td>
            </tr>"""

        cats_html += f"""
        <tr><td style="padding:24px 0 0;">
          <p style="margin:0 0 12px;font-size:10px;font-weight:700;letter-spacing:1.8px;color:#1B9FAF;text-transform:uppercase;">{cat.get('emoji','')} {cat.get('name','')}</p>
          <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
        </td></tr>"""

    if not cats_html:
        cats_html = '<tr><td style="padding:32px 0;color:#aaa;font-size:14px;text-align:center;">No stories found today — check back tomorrow.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#efefef;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#efefef;padding:32px 16px;">
<tr><td align="center"><table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

  <tr><td style="background:#1B9FAF;border-radius:12px 12px 0 0;padding:32px 40px;text-align:center;">
    <img src="cid:inovues_logo" alt="INOVUES" width="70" style="display:block;margin:0 auto 14px;">
    <p style="margin:0;font-size:10px;letter-spacing:2.5px;color:rgba(255,255,255,0.6);text-transform:uppercase;font-weight:600;">Intelligence Digest</p>
    <p style="margin:8px 0 0;font-size:20px;font-weight:700;color:white;">{date_str}</p>
  </td></tr>

  <tr><td style="background:#158c99;padding:14px 40px;">
    <p style="margin:0;font-size:13px;color:rgba(255,255,255,0.9);line-height:1.6;font-style:italic;">"{headline}"</p>
  </td></tr>

  <tr><td style="background:white;padding:11px 40px;border-bottom:1px solid #eee;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="font-size:12px;color:#bbb;">{total} stories · {active} categories</td>
      <td style="text-align:right;font-size:12px;color:#bbb;">Relevance scored 1–10 by AI</td>
    </tr></table>
  </td></tr>

  <tr><td style="background:white;padding:4px 40px 36px;">
    <table width="100%" cellpadding="0" cellspacing="0">{cats_html}</table>
  </td></tr>

  <tr><td style="background:#1a1a1a;border-radius:0 0 12px 12px;padding:20px 40px;text-align:center;">
    <p style="margin:0 0 4px;font-size:11px;color:#555;letter-spacing:1px;text-transform:uppercase;">INOVUES · Adaptive Glazing Shields</p>
    <p style="margin:0;font-size:10px;color:#444;">Delivered daily at 8 AM EST · Powered by Claude AI</p>
  </td></tr>

</table></td></tr></table>
</body></html>"""


# ── Send Email ─────────────────────────────────────────────────────────────────
def send_email(html: str, subject: str):
    msg = MIMEMultipart("related")
    msg["From"]    = f"INOVUES Intelligence <{GMAIL_USER}>"
    msg["To"]      = ", ".join(RECIPIENTS)
    msg["Subject"] = subject

    alt = MIMEMultipart("alternative")
    msg.attach(alt)
    alt.attach(MIMEText(html, "html"))

    logo_path = Path(__file__).parent / "logo.jpg"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            img = MIMEImage(f.read(), _subtype="jpeg")
            img.add_header("Content-ID", "<inovues_logo>")
            img.add_header("Content-Disposition", "inline", filename="logo.jpg")
            msg.attach(img)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASS)
        server.sendmail(GMAIL_USER, RECIPIENTS, msg.as_string())
    print(f"✅ Sent to {', '.join(RECIPIENTS)}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"🏢 INOVUES Digest — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("📰 Fetching news...")
    articles = fetch_all()

    print("🤖 Curating with Claude...")
    digest = curate_with_claude(articles)

    total = sum(len(c.get("stories",[])) for c in digest.get("categories",[]))
    print(f"   → {total} stories selected")

    print("🎨 Building email...")
    html = build_html(digest)

    subject = f"INOVUES Intelligence — {datetime.now().strftime('%b %d, %Y')}"
    print("📬 Sending...")
    send_email(html, subject)
    print("✅ Done!")

if __name__ == "__main__":
    main()
