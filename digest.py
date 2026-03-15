#!/usr/bin/env python3
"""
INOVUES Weekly Intelligence Digest
Uses Claude with web search to find fresh content from targeted sources.
Sends branded HTML email every Monday at 8 AM EST.
"""

import os
import json
import smtplib
import requests
import time
from datetime import datetime, timedelta
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

# Date range: last 7 days
TODAY     = datetime.now().strftime("%B %d, %Y")
WEEK_AGO  = (datetime.now() - timedelta(days=7)).strftime("%B %d, %Y")

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
- Any building upgrading facades, windows, or energy systems
- New England building energy policy and programs
"""

# ── Search targets ─────────────────────────────────────────────────────────────
SEARCH_QUERIES = [
    # Competitors — LinkedIn + website
    {"category": "Competitors",           "source": "Indow Window",              "query": f'site:linkedin.com/company/indow-windows OR site:indowwindows.com news updates {WEEK_AGO}'},
    {"category": "Competitors",           "source": "Alpen Windows",             "query": f'site:linkedin.com/company/alpen-high-performance-products OR site:alpenwp.com news {WEEK_AGO}'},

    # Utilities — LinkedIn + press releases
    {"category": "Utilities",             "source": "Con Edison",                "query": f'Con Edison commercial building energy rebate program announcement {WEEK_AGO}'},
    {"category": "Utilities",             "source": "NYSERDA",                   "query": f'NYSERDA commercial building energy efficiency incentive program {WEEK_AGO}'},
    {"category": "Utilities",             "source": "National Grid",             "query": f'National Grid commercial building rebate energy efficiency {WEEK_AGO}'},
    {"category": "Utilities",             "source": "Eversource",                "query": f'Eversource commercial building energy efficiency program rebate {WEEK_AGO}'},
    {"category": "Utilities",             "source": "PSEG Long Island",          "query": f'PSEG Long Island commercial energy program incentive {WEEK_AGO}'},
    {"category": "Utilities",             "source": "NY Power Authority",        "query": f'NYPA New York Power Authority commercial building clean energy {WEEK_AGO}'},
    {"category": "Utilities",             "source": "Avangrid / NYSEG",          "query": f'Avangrid NYSEG commercial building energy program New York {WEEK_AGO}'},
    {"category": "Utilities",             "source": "Unitil",                    "query": f'Unitil commercial energy efficiency program New England {WEEK_AGO}'},

    # City agencies
    {"category": "Policy & Regulations",  "source": "NYC Local Law 97",          "query": f'NYC Local Law 97 building compliance fine enforcement update {WEEK_AGO}'},
    {"category": "Policy & Regulations",  "source": "NYC Dept of Buildings",     "query": f'NYC DOB building energy retrofit regulation announcement {WEEK_AGO}'},
    {"category": "Policy & Regulations",  "source": "Boston BERDO",              "query": f'Boston BERDO building energy reporting compliance update {WEEK_AGO}'},
    {"category": "Policy & Regulations",  "source": "NYC Climate Office",        "query": f'NYC Mayor climate office building decarbonization announcement {WEEK_AGO}'},

    # Industry publications
    {"category": "Industry Publications", "source": "The Real Deal NYC",         "query": f'site:therealdeal.com building retrofit energy renovation {WEEK_AGO}'},
    {"category": "Industry Publications", "source": "Bisnow",                    "query": f'site:bisnow.com NYC building energy retrofit facade renovation {WEEK_AGO}'},
    {"category": "Industry Publications", "source": "GreenBiz",                  "query": f'site:greenbiz.com commercial building energy efficiency retrofit {WEEK_AGO}'},
    {"category": "Industry Publications", "source": "ENR",                       "query": f'site:enr.com NYC building retrofit renovation energy {WEEK_AGO}'},
    {"category": "Industry Publications", "source": "Commercial Property Exec",  "query": f'site:cpexecutive.com building energy retrofit renovation {WEEK_AGO}'},
    {"category": "Industry Publications", "source": "Propmodo",                  "query": f'site:propmodo.com building energy efficiency retrofit {WEEK_AGO}'},

    # Market intelligence
    {"category": "Market Intelligence",   "source": "Office Conversions",        "query": f'NYC office to residential hotel conversion project announced {WEEK_AGO}'},
    {"category": "Market Intelligence",   "source": "Building Retrofits",        "query": f'commercial building facade window energy retrofit project NYC New England {WEEK_AGO}'},
    {"category": "Market Intelligence",   "source": "Decarbonization",           "query": f'commercial building decarbonization retrofit project announced New York {WEEK_AGO}'},
]


# ── Claude web search fetch ────────────────────────────────────────────────────
def search_with_claude(query: str) -> list[dict]:
    """Use Claude with web_search tool to find articles."""
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 1000,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{
                    "role": "user",
                    "content": f"""Search for this and return results as JSON array only, no other text:
Query: {query}

Return a JSON array of up to 4 results:
[{{"title": "...", "url": "...", "snippet": "...", "date": "..."}}]
If no results found return: []"""
                }]
            },
            timeout=30
        )
        r.raise_for_status()
        content_blocks = r.json().get("content", [])
        for block in content_blocks:
            if block.get("type") == "text":
                text = block["text"].strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                text = text.strip()
                if text.startswith("["):
                    return json.loads(text)
    except Exception as e:
        print(f"    Search error: {e}")
    return []


def fetch_all() -> list[dict]:
    all_articles = []
    seen_urls = set()

    for target in SEARCH_QUERIES:
        print(f"  [{target['category']}] {target['source']}")
        results = search_with_claude(target["query"])
        time.sleep(0.5)  # gentle rate limiting

        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_articles.append({
                    "category": target["category"],
                    "source_name": target["source"],
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": r.get("snippet", ""),
                    "date": r.get("date", ""),
                })

    print(f"  → {len(all_articles)} unique articles found")
    return all_articles


# ── Claude curation ────────────────────────────────────────────────────────────
def curate_with_claude(articles: list[dict]) -> dict:
    articles_text = json.dumps(articles, indent=2)

    prompt = f"""You are the intelligence analyst for INOVUES.

{INOVUES_CONTEXT}

Here are articles found this week ({WEEK_AGO} to {TODAY}):
{articles_text}

Instructions:
1. Include ANY article relevant to: building retrofits, window/facade upgrades, energy efficiency programs, LL97/BERDO compliance, office conversions, utility incentive programs, competitor activity, commercial real estate renovations, building decarbonization
2. Be INCLUSIVE — if there's any angle for INOVUES include it
3. Only skip articles completely unrelated to buildings/energy
4. For each article write a sharp "INOVUES angle" — business implication in 1-2 sentences
5. Score 1-10: 10=direct sales lead, 7-9=strong opportunity, 4-6=useful intel, 1-3=background awareness
6. Write one punchy headline summary for the whole digest

Return ONLY valid JSON (no markdown):
{{
  "date": "Week of {WEEK_AGO} — {TODAY}",
  "headline_summary": "one punchy sentence summarizing the week for INOVUES",
  "categories": [
    {{
      "name": "category name",
      "emoji": "emoji",
      "stories": [
        {{
          "source_name": "source",
          "title": "title",
          "url": "url",
          "insight": "INOVUES angle",
          "score": 7
        }}
      ]
    }}
  ]
}}"""

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
    date_str   = digest.get("date", f"Week of {WEEK_AGO}")
    headline   = digest.get("headline_summary", "Your weekly INOVUES intelligence briefing.")
    categories = digest.get("categories", [])
    total      = sum(len(c.get("stories", [])) for c in categories)
    active     = sum(1 for c in categories if c.get("stories"))

    cats_html = ""
    for cat in categories:
        stories = cat.get("stories", [])
        if not stories:
            continue
        rows = ""
        for s in sorted(stories, key=lambda x: x.get("score", 0), reverse=True):
            sc    = s.get("score", 5)
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
        cats_html = '<tr><td style="padding:32px 0;color:#aaa;font-size:14px;text-align:center;">No stories found this week.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#efefef;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#efefef;padding:32px 16px;">
<tr><td align="center"><table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

  <tr><td style="background:#1B9FAF;border-radius:12px 12px 0 0;padding:32px 40px;text-align:center;">
    <img src="cid:inovues_logo" alt="INOVUES" width="70" style="display:block;margin:0 auto 14px;">
    <p style="margin:0;font-size:10px;letter-spacing:2.5px;color:rgba(255,255,255,0.6);text-transform:uppercase;font-weight:600;">Weekly Intelligence Digest</p>
    <p style="margin:8px 0 0;font-size:18px;font-weight:700;color:white;">{date_str}</p>
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
    <p style="margin:0;font-size:10px;color:#444;">Delivered every Monday at 8 AM EST · Powered by Claude AI</p>
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
    print(f"🏢 INOVUES Weekly Digest — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"📅 Covering: {WEEK_AGO} → {TODAY}")
    print("🔍 Searching with Claude...")
    articles = fetch_all()

    print("🤖 Curating...")
    digest = curate_with_claude(articles)
    total = sum(len(c.get("stories", [])) for c in digest.get("categories", []))
    print(f"   → {total} stories selected")

    print("🎨 Building email...")
    html = build_html(digest)

    subject = f"INOVUES Weekly Intelligence — {datetime.now().strftime('%b %d, %Y')}"
    print("📬 Sending...")
    send_email(html, subject)
    print("✅ Done!")

if __name__ == "__main__":
    main()
