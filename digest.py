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

TODAY    = datetime.now().strftime("%B %d, %Y")
WEEK_AGO = (datetime.now() - timedelta(days=7)).strftime("%B %d, %Y")

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

SEARCH_QUERIES = [
    {"category": "Competitors",           "source": "Indow Window",             "query": "Indow Window news updates 2025 2026"},
    {"category": "Competitors",           "source": "Alpen Windows",            "query": "Alpen High Performance Windows news 2025 2026"},
    {"category": "Utilities",             "source": "Con Edison",               "query": "Con Edison commercial building energy rebate program 2025 2026"},
    {"category": "Utilities",             "source": "NYSERDA",                  "query": "NYSERDA commercial building energy efficiency incentive 2025 2026"},
    {"category": "Utilities",             "source": "National Grid",            "query": "National Grid commercial building rebate energy 2025 2026"},
    {"category": "Utilities",             "source": "Eversource",               "query": "Eversource commercial building energy efficiency rebate 2025 2026"},
    {"category": "Utilities",             "source": "PSEG Long Island",         "query": "PSEG Long Island commercial energy incentive program 2026"},
    {"category": "Utilities",             "source": "NY Power Authority",       "query": "NYPA commercial building clean energy program 2026"},
    {"category": "Policy & Regulations",  "source": "NYC Local Law 97",         "query": "NYC Local Law 97 building compliance fine enforcement 2026"},
    {"category": "Policy & Regulations",  "source": "NYC Dept of Buildings",    "query": "NYC DOB building energy retrofit regulation 2026"},
    {"category": "Policy & Regulations",  "source": "Boston BERDO",             "query": "Boston BERDO building energy reporting compliance 2026"},
    {"category": "Industry Publications", "source": "The Real Deal NYC",        "query": "site:therealdeal.com building retrofit energy renovation"},
    {"category": "Industry Publications", "source": "GreenBiz",                 "query": "site:greenbiz.com commercial building energy efficiency retrofit"},
    {"category": "Industry Publications", "source": "ENR",                      "query": "site:enr.com building retrofit renovation energy efficiency"},
    {"category": "Industry Publications", "source": "Commercial Property Exec", "query": "site:cpexecutive.com building energy retrofit renovation"},
    {"category": "Industry Publications", "source": "Propmodo",                 "query": "site:propmodo.com building energy efficiency retrofit"},
    {"category": "Market Intelligence",   "source": "Office Conversions",       "query": "NYC office to residential hotel conversion project 2026"},
    {"category": "Market Intelligence",   "source": "Building Retrofits",       "query": "commercial building facade window energy retrofit NYC 2026"},
    {"category": "Market Intelligence",   "source": "Decarbonization",          "query": "commercial building decarbonization retrofit New York 2026"},
]


def search_with_claude(query: str) -> list[dict]:
    """Use Claude with web_search tool. Robustly parse whatever comes back."""
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
                "max_tokens": 1500,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{
                    "role": "user",
                    "content": f"Search the web for: {query}\n\nAfter searching, list the top 3-4 results you found as a JSON array with fields: title, url, snippet. Return ONLY the JSON array, nothing else."
                }]
            },
            timeout=45
        )
        r.raise_for_status()
        blocks = r.json().get("content", [])

        # Try to find a text block with JSON
        for block in blocks:
            if block.get("type") == "text":
                text = block["text"].strip()
                # Strip markdown fences
                if "```" in text:
                    parts = text.split("```")
                    for part in parts:
                        part = part.strip()
                        if part.startswith("json"):
                            part = part[4:].strip()
                        if part.startswith("["):
                            try:
                                return json.loads(part)
                            except:
                                pass
                # Try direct parse
                if "[" in text:
                    start = text.index("[")
                    end   = text.rindex("]") + 1
                    try:
                        return json.loads(text[start:end])
                    except:
                        pass

        # If no JSON found, extract from tool_result blocks
        for block in blocks:
            if block.get("type") == "tool_result":
                for sub in block.get("content", []):
                    if sub.get("type") == "text":
                        try:
                            data = json.loads(sub["text"])
                            results = []
                            for item in data.get("results", data if isinstance(data, list) else []):
                                results.append({
                                    "title":   item.get("title", ""),
                                    "url":     item.get("url", ""),
                                    "snippet": item.get("description", item.get("snippet", ""))
                                })
                            if results:
                                return results
                        except:
                            pass

    except Exception as e:
        print(f"    ⚠ Error: {e}")
    return []


def fetch_all() -> list[dict]:
    all_articles = []
    seen_urls    = set()

    for target in SEARCH_QUERIES:
        print(f"  [{target['category']}] {target['source']}")
        results = search_with_claude(target["query"])
        time.sleep(2)

        for res in results:
            url = res.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_articles.append({
                    "category":    target["category"],
                    "source_name": target["source"],
                    "title":       res.get("title", ""),
                    "url":         url,
                    "snippet":     res.get("snippet", ""),
                })

        print(f"    → {len(results)} results")

    print(f"\n  TOTAL: {len(all_articles)} unique articles")
    return all_articles


def curate_with_claude(articles: list[dict]) -> dict:
    articles_text = json.dumps(articles, indent=2)

    prompt = f"""You are the intelligence analyst for INOVUES.

{INOVUES_CONTEXT}

Here are articles found this week ({WEEK_AGO} to {TODAY}):
{articles_text}

Instructions:
1. Include ANY article relevant to: building retrofits, window/facade upgrades, energy efficiency programs, LL97/BERDO compliance, office conversions, utility incentive programs, competitor activity, commercial real estate renovations, building decarbonization
2. Be INCLUSIVE — if there is any angle for INOVUES, include it
3. Only skip articles that are 100% unrelated to buildings or energy
4. For each article write a sharp "INOVUES angle" — what is the business implication in 1-2 sentences
5. Score 1-10: 10=direct sales lead or urgent action, 7-9=strong opportunity, 4-6=useful intel, 1-3=background awareness
6. Write one punchy headline summary for the whole digest
7. You MUST include at least 5 stories — if fewer than 5 are clearly relevant, include the next most relevant ones anyway

Return ONLY valid JSON (no markdown fences):
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
          "insight": "INOVUES angle in 1-2 sentences",
          "score": 7
        }}
      ]
    }}
  ]
}}"""

    for attempt in range(3):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-haiku-4-5", "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}]},
                timeout=90
            )
            if r.status_code == 429:
                print(f"  Rate limited, waiting 30s... (attempt {attempt+1}/3)")
                time.sleep(30)
                continue
            r.raise_for_status()
            break
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(30)
    content = r.json()["content"][0]["text"].strip()
    if "```" in content:
        parts = content.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                try:
                    return json.loads(part)
                except:
                    pass
    if "{" in content:
        start = content.index("{")
        end   = content.rindex("}") + 1
        return json.loads(content[start:end])
    return json.loads(content)


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
        cats_html = '<tr><td style="padding:32px 0;color:#aaa;font-size:14px;text-align:center;">No stories found this week — check logs for errors.</td></tr>'

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


def main():
    print(f"🏢 INOVUES Weekly Digest — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"📅 Covering: {WEEK_AGO} → {TODAY}")
    print("🔍 Searching with Claude web search...")
    articles = fetch_all()

    print("\n🤖 Curating with Claude...")
    digest = curate_with_claude(articles)
    total  = sum(len(c.get("stories", [])) for c in digest.get("categories", []))
    print(f"   → {total} stories selected")

    print("🎨 Building email...")
    html = build_html(digest)

    subject = f"INOVUES Weekly Intelligence — {datetime.now().strftime('%b %d, %Y')}"
    print("📬 Sending...")
    send_email(html, subject)
    print("✅ Done!")

if __name__ == "__main__":
    main()
