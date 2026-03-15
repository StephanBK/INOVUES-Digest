#!/usr/bin/env python3
"""
INOVUES Daily News Digest
Monitors specific competitor/utility websites + GNews for targeted intelligence.
Curates with Claude AI, sends branded HTML email at 8 AM daily.
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

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]
GMAIL_APP_PASS    = os.environ["GMAIL_APP_PASS"]
RECIPIENTS        = os.environ.get("RECIPIENTS", GMAIL_USER).split(",")
GNEWS_API_KEY     = os.environ.get("GNEWS_API_KEY", "")

# ── Watch List ────────────────────────────────────────────────────────────────
WATCH_TARGETS = {
    "Competitors": [
        {"name": "Indow Window",                  "query": "Indow Window retrofit"},
        {"name": "Alpen High Performance Windows", "query": "Alpen Windows commercial"},
    ],
    "Utilities — NYC & New England": [
        {"name": "Con Edison",        "query": "Con Edison rebate incentive commercial building retrofit"},
        {"name": "National Grid",     "query": "National Grid rebate program commercial building energy"},
        {"name": "PSEG Long Island",  "query": "PSEG Long Island energy efficiency incentive program"},
        {"name": "NYSERDA",           "query": "NYSERDA commercial building energy efficiency program grant"},
        {"name": "Eversource",        "query": "Eversource commercial building rebate energy efficiency program"},
        {"name": "Avangrid / NYSEG",  "query": "Avangrid NYSEG commercial building energy incentive"},
        {"name": "Central Hudson",    "query": "Central Hudson commercial energy efficiency rebate"},
        {"name": "Orange & Rockland", "query": "Orange Rockland energy efficiency commercial program"},
        {"name": "NY Power Authority","query": "NYPA commercial building clean energy retrofit"},
        {"name": "Unitil",            "query": "Unitil commercial energy efficiency program New England"},
    ],
    "City Agencies": [
        {"name": "NYC Mayor's Office of Climate", "query": "NYC building emissions decarbonization retrofit 2025"},
        {"name": "NYC Dept of Buildings",         "query": "NYC Local Law 97 building retrofit compliance fine"},
        {"name": "Boston BERDO",                  "query": "Boston building energy retrofit decarbonization BERDO"},
    ],
    "Building Retrofits & Market": [
        {"name": "NYC Office Conversions",        "query": "NYC office to residential hotel conversion retrofit 2025"},
        {"name": "Commercial Building Retrofits",  "query": "commercial building facade window retrofit energy upgrade NYC"},
        {"name": "Building Decarbonization",       "query": "commercial building decarbonization retrofit New York New England"},
    ],
}

INOVUES_CONTEXT = """
INOVUES is a NYC-based facade installation company specializing in secondary window 
retrofit systems for commercial buildings. Their product helps building owners comply 
with NYC Local Law 97 (carbon emission limits), improve energy efficiency, and reduce 
heating/cooling costs. Target customers: owners and managers of large commercial 
buildings in NYC and New England. They compete on speed of installation, minimal 
disruption, and measurable energy savings.
Key business interests: LL97 enforcement updates, utility rebate/incentive programs 
for window retrofits, competitor product launches or marketing, building energy policy 
changes, large commercial building retrofit projects.
"""

# ── Fetch News via GNews ───────────────────────────────────────────────────────
def fetch_gnews(query: str, max_results: int = 5) -> list[dict]:
    if not GNEWS_API_KEY:
        return []
    try:
        r = requests.get(
            "https://gnews.io/api/v4/search",
            params={
                "q": query,
                "lang": "en",
                "country": "us",
                "max": max_results,
                "apikey": GNEWS_API_KEY,
            },
            timeout=10
        )
        if r.status_code == 200:
            return [
                {
                    "title": a["title"],
                    "url": a["url"],
                    "description": a.get("description", ""),
                    "source": a.get("source", {}).get("name", ""),
                    "publishedAt": a.get("publishedAt", ""),
                }
                for a in r.json().get("articles", [])
            ]
    except Exception as e:
        print(f"  GNews error for '{query}': {e}")
    return []


def fetch_all_news() -> dict:
    all_news = {}
    for category, targets in WATCH_TARGETS.items():
        all_news[category] = {}
        for target in targets:
            print(f"  Fetching: {target['name']}")
            articles = fetch_gnews(target["query"], max_results=4)
            all_news[category][target["name"]] = articles
    return all_news


# ── Claude Curation ────────────────────────────────────────────────────────────
def curate_with_claude(all_news: dict) -> dict:
    news_dump = json.dumps(all_news, indent=2)

    prompt = f"""You are the news curator for INOVUES, a NYC commercial building facade retrofit company.

Company context:
{INOVUES_CONTEXT}

Today's raw news monitored from competitors, utilities, and city agencies:
{news_dump}

Your task:
1. Review ALL articles and include ANYTHING that could interest INOVUES, including:
   - Building retrofit projects (office to hotel, office to residential, facade upgrades)
   - Utility rebate or incentive programs (even general ones)
   - Energy efficiency initiatives or mandates
   - Commercial real estate transformation projects
   - Competitor news, product launches, partnerships
   - Policy updates, new regulations, enforcement
   - Large building renovation or decarbonization projects
   - ANY news from the monitored sources (even if loosely related)
2. Be INCLUSIVE not exclusive — if in doubt, include it
3. Only skip articles that are completely unrelated (e.g. residential consumer tips, unrelated industries)
4. Group stories by category (Competitors / Utilities / City Agencies)
5. Write a 1-2 sentence insight explaining relevance or opportunity for INOVUES
6. Score 1-10 for INOVUES relevance (10 = direct sales opportunity, 1 = background awareness)
7. Write a punchy headline summary

Return ONLY valid JSON, no markdown fences:
{{
  "date": "{datetime.now().strftime('%A, %B %d, %Y')}",
  "headline_summary": "One punchy sentence summarizing today's most important intelligence for INOVUES",
  "categories": [
    {{
      "name": "Competitors",
      "emoji": "🎯",
      "stories": [
        {{
          "source_name": "Indow Window",
          "title": "article title",
          "url": "article url",
          "insight": "What this means for INOVUES in 1-2 sentences",
          "score": 8
        }}
      ]
    }},
    {{
      "name": "Utilities — NYC & New England",
      "emoji": "⚡",
      "stories": []
    }},
    {{
      "name": "City Agencies",
      "emoji": "🏛️",
      "stories": []
    }}
  ]
}}"""

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-haiku-4-5",
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=60
    )
    response.raise_for_status()
    content = response.json()["content"][0]["text"].strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())


# ── Build HTML Email ───────────────────────────────────────────────────────────
def build_html(digest: dict) -> str:
    date_str = digest.get("date", datetime.now().strftime('%A, %B %d, %Y'))
    headline = digest.get("headline_summary", "Your daily INOVUES intelligence briefing.")
    categories = digest.get("categories", [])

    total_stories = sum(len(c.get("stories", [])) for c in categories)
    active_cats   = sum(1 for c in categories if c.get("stories"))

    categories_html = ""
    for cat in categories:
        stories = cat.get("stories", [])
        if not stories:
            continue
        stories_html = ""
        for s in sorted(stories, key=lambda x: x.get("score", 0), reverse=True):
            score = s.get("score", 5)
            dot_color = "#1B9FAF" if score >= 8 else "#5BB8C4" if score >= 6 else "#9AD4DB"
            stories_html += f"""
            <tr>
              <td style="padding:16px 0; border-bottom:1px solid #f4f4f4;">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td width="8" style="vertical-align:top; padding-top:6px;">
                      <div style="width:8px;height:8px;border-radius:50%;background:{dot_color};"></div>
                    </td>
                    <td style="padding-left:12px;">
                      <p style="margin:0 0 2px;font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.8px;">{s.get('source_name','')}</p>
                      <a href="{s.get('url','#')}" style="font-size:15px;font-weight:600;color:#1a1a1a;text-decoration:none;line-height:1.4;">{s.get('title','')}</a>
                      <p style="margin:6px 0 0;font-size:13px;color:#555;line-height:1.6;border-left:2px solid #1B9FAF;padding-left:10px;">{s.get('insight','')}</p>
                    </td>
                    <td width="36" style="vertical-align:top;text-align:right;padding-left:8px;">
                      <div style="background:{dot_color};color:white;border-radius:4px;width:28px;height:22px;line-height:22px;text-align:center;font-size:11px;font-weight:700;">{score}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>"""

        categories_html += f"""
        <tr>
          <td style="padding:24px 0 0;">
            <p style="margin:0 0 12px;font-size:11px;font-weight:700;letter-spacing:1.5px;color:#1B9FAF;text-transform:uppercase;">{cat.get('emoji','')} {cat.get('name','')}</p>
            <table width="100%" cellpadding="0" cellspacing="0">{stories_html}</table>
          </td>
        </tr>"""

    if not categories_html:
        categories_html = '<tr><td style="padding:24px 0;color:#888;font-size:14px;">No significant intelligence found today.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0f0f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f0f0;padding:32px 16px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

      <!-- Header -->
      <tr><td style="background:#1B9FAF;border-radius:12px 12px 0 0;padding:32px 40px;text-align:center;">
        <img src="cid:inovues_logo" alt="INOVUES" width="72" style="display:block;margin:0 auto 14px;">
        <p style="margin:0;font-size:10px;letter-spacing:2.5px;color:rgba(255,255,255,0.65);text-transform:uppercase;font-weight:600;">Intelligence Digest</p>
        <p style="margin:8px 0 0;font-size:20px;font-weight:700;color:white;">{date_str}</p>
      </td></tr>

      <!-- Headline -->
      <tr><td style="background:#158c99;padding:14px 40px;">
        <p style="margin:0;font-size:13px;color:rgba(255,255,255,0.88);line-height:1.6;font-style:italic;">"{headline}"</p>
      </td></tr>

      <!-- Stats bar -->
      <tr><td style="background:white;padding:12px 40px;border-bottom:1px solid #eee;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="font-size:12px;color:#aaa;">{total_stories} stories · {active_cats} categories</td>
            <td style="text-align:right;font-size:12px;color:#aaa;">AI-scored relevance</td>
          </tr>
        </table>
      </td></tr>

      <!-- Body -->
      <tr><td style="background:white;padding:4px 40px 36px;">
        <table width="100%" cellpadding="0" cellspacing="0">{categories_html}</table>
      </td></tr>

      <!-- Footer -->
      <tr><td style="background:#1a1a1a;border-radius:0 0 12px 12px;padding:22px 40px;text-align:center;">
        <p style="margin:0 0 4px;font-size:11px;color:#555;letter-spacing:1px;text-transform:uppercase;">INOVUES · Adaptive Glazing Shields</p>
        <p style="margin:0;font-size:10px;color:#444;">Delivered daily at 8 AM EST · Powered by Claude AI</p>
      </td></tr>

    </table>
  </td></tr>
</table>
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
    all_news = fetch_all_news()

    print("🤖 Curating with Claude...")
    digest = curate_with_claude(all_news)

    print("🎨 Building email...")
    html = build_html(digest)

    subject = f"INOVUES Intelligence — {datetime.now().strftime('%b %d, %Y')}"
    print("📬 Sending...")
    send_email(html, subject)
    print("✅ Done!")

if __name__ == "__main__":
    main()
