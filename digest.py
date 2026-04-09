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
SENT_URLS_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sent_urls.log")

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

    # ── CATEGORY 1: Competitor Intelligence ──────────────────────────────────
    {"category": "Competitor Intelligence", "source": "Indow Window",             "query": "Indow Window news updates 2026"},
    {"category": "Competitor Intelligence", "source": "Alpen Windows",            "query": "Alpen High Performance Windows news 2026"},
    {"category": "Competitor Intelligence", "source": "Ubiquitous Energy",        "query": "site:ubiquitousenergy.com news 2026"},
    {"category": "Competitor Intelligence", "source": "Andluca Technologies",     "query": "site:andluca.com smart window news 2026"},
    {"category": "Competitor Intelligence", "source": "Facade Tectonics",         "query": "site:facadetectonics.com facade building news 2026"},
    {"category": "Competitor Intelligence", "source": "FGIA",                     "query": "site:fgiaonline.org window door skylight industry news 2026"},
    {"category": "Competitor Intelligence", "source": "National Glass Association","query": "site:glass.org commercial glazing window news 2026"},
    {"category": "Competitor Intelligence", "source": "glassonweb",               "query": "site:glassonweb.com commercial window glazing news 2026"},
    {"category": "Competitor Intelligence", "source": "IGS Magazine",             "query": "site:igsmag.com window glazing industry news 2026"},
    {"category": "Competitor Intelligence", "source": "Secondary Window Market",  "query": "commercial secondary window retrofit system competitor 2026"},

    # ── CATEGORY 2: Market & Industry News ───────────────────────────────────
    {"category": "Market & Industry News",  "source": "GreenBiz",                 "query": "site:greenbiz.com commercial building energy efficiency retrofit 2026"},
    {"category": "Market & Industry News",  "source": "ENR",                      "query": "site:enr.com building retrofit renovation energy efficiency 2026"},
    {"category": "Market & Industry News",  "source": "Commercial Property Exec", "query": "site:cpexecutive.com building energy retrofit renovation 2026"},
    {"category": "Market & Industry News",  "source": "Propmodo",                 "query": "site:propmodo.com building energy efficiency retrofit 2026"},
    {"category": "Market & Industry News",  "source": "Retrofit Magazine",        "query": "site:retrofitmag.com commercial building renovation 2026"},
    {"category": "Market & Industry News",  "source": "BuildingGreen",            "query": "site:buildinggreen.com commercial building retrofit energy 2026"},
    {"category": "Market & Industry News",  "source": "New Buildings Institute",  "query": "site:newbuildings.org commercial building energy policy 2026"},
    {"category": "Market & Industry News",  "source": "IMT",                      "query": "site:imt.org building energy efficiency policy 2026"},
    {"category": "Market & Industry News",  "source": "USGBC",                    "query": "site:usgbc.org commercial building green certification 2026"},
    {"category": "Market & Industry News",  "source": "Living Future Institute",  "query": "site:living-future.org building performance standard 2026"},
    {"category": "Market & Industry News",  "source": "Cleantech Group",          "query": "site:cleantech.com building energy efficiency startup 2026"},
    {"category": "Market & Industry News",  "source": "Greentown Labs",           "query": "site:greentownlabs.com building energy climatetech 2026"},
    {"category": "Market & Industry News",  "source": "Breakthrough Energy",      "query": "site:breakthroughenergy.org building decarbonization 2026"},
    {"category": "Market & Industry News",  "source": "Shadow Ventures",          "query": "site:shadowventures.com AEC built environment news 2026"},
    {"category": "Market & Industry News",  "source": "NAESCO",                   "query": "site:naesco.org energy service building retrofit 2026"},
    {"category": "Market & Industry News",  "source": "PACENation",               "query": "site:pacenation.us PACE financing commercial building 2026"},
    {"category": "Market & Industry News",  "source": "Alliance To Save Energy",  "query": "site:ase.org commercial building energy efficiency 2026"},
    {"category": "Market & Industry News",  "source": "Better Buildings DOE",     "query": "site:betterbuildingssolutioncenter.energy.gov commercial retrofit 2026"},
    {"category": "Market & Industry News",  "source": "BE-Ex NY",                 "query": "site:beexny.org building energy NYC 2026"},
    {"category": "Market & Industry News",  "source": "Urban Green Council",      "query": "site:urbangreencouncil.org NYC building energy 2026"},
    {"category": "Market & Industry News",  "source": "NESEA",                    "query": "site:nesea.org northeast building energy efficiency 2026"},
    {"category": "Market & Industry News",  "source": "Saint-Gobain NOVA",        "query": "site:sgnova.com building materials construction startup 2026"},
    {"category": "Market & Industry News",  "source": "Greenbuild",               "query": "site:greenbuildexpo.com green building news 2026"},
    {"category": "Market & Industry News",  "source": "Office Conversions",       "query": "NYC office to residential hotel conversion project 2026"},
    {"category": "Market & Industry News",  "source": "Facade Retrofits",         "query": "commercial building facade window energy retrofit NYC 2026"},
    {"category": "Market & Industry News",  "source": "Decarbonization",          "query": "commercial building decarbonization retrofit New York 2026"},

    # ── CATEGORY 3: Commercial Real Estate News ───────────────────────────────
    {"category": "Commercial Real Estate News", "source": "Bisnow",              "query": "site:bisnow.com commercial real estate NYC building 2026"},
    {"category": "Commercial Real Estate News", "source": "CoStar",              "query": "site:costar.com commercial real estate market NYC 2026"},
    {"category": "Commercial Real Estate News", "source": "The Real Deal",       "query": "site:therealdeal.com commercial building NYC 2026"},
    {"category": "Commercial Real Estate News", "source": "BOMA International",  "query": "site:boma.org commercial building owner manager news 2026"},
    {"category": "Commercial Real Estate News", "source": "BOMA New York",       "query": "site:bomany.org NYC commercial real estate building 2026"},
    {"category": "Commercial Real Estate News", "source": "JLL",                 "query": "site:jll.com commercial real estate market NYC office 2026"},
    {"category": "Commercial Real Estate News", "source": "CBRE",                "query": "site:cbre.com commercial real estate NYC market report 2026"},
    {"category": "Commercial Real Estate News", "source": "NYC Climate Office",  "query": "site:nyc.gov commercial building climate energy retrofit 2026"},

    # ── CATEGORY 4: Deals Announced ──────────────────────────────────────────
    {"category": "Deals Announced", "source": "NYC Commercial Sales",            "query": "commercial building acquisition sale closed NYC 2026"},
    {"category": "Deals Announced", "source": "New England Commercial Sales",    "query": "commercial property sale deal closed New England 2026"},
    {"category": "Deals Announced", "source": "CRE Transactions",               "query": "commercial real estate transaction acquisition announced 2026"},

    # ── CATEGORY 5: Utility News ─────────────────────────────────────────────
    {"category": "Utility News", "source": "Con Edison",                         "query": "Con Edison commercial building energy rebate incentive 2026"},
    {"category": "Utility News", "source": "NYSERDA",                            "query": "NYSERDA commercial building energy efficiency incentive 2026"},
    {"category": "Utility News", "source": "National Grid",                      "query": "National Grid commercial building rebate energy program 2026"},
    {"category": "Utility News", "source": "Eversource",                         "query": "Eversource commercial building energy efficiency rebate 2026"},
    {"category": "Utility News", "source": "PSEG Long Island",                   "query": "PSEG Long Island commercial energy incentive program 2026"},
    {"category": "Utility News", "source": "NY Power Authority",                 "query": "NYPA commercial building clean energy program 2026"},
    {"category": "Utility News", "source": "Duke Energy",                        "query": "Duke Energy commercial building energy efficiency rebate 2026"},
    {"category": "Utility News", "source": "Southern Company",                   "query": "Southern Company commercial building energy efficiency 2026"},
    {"category": "Utility News", "source": "Dominion Energy",                    "query": "Dominion Energy commercial building rebate program 2026"},
    {"category": "Utility News", "source": "PG&E",                               "query": "PGE Pacific Gas Electric commercial building rebate 2026"},
    {"category": "Utility News", "source": "MassCEC",                            "query": "MassCEC Massachusetts commercial building clean energy 2026"},
    {"category": "Utility News", "source": "NEEP",                               "query": "NEEP northeast energy efficiency commercial building 2026"},
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
                    "content": f"Search the web for: {query}\n\nIMPORTANT: Only include results published within the last 7 days (after {WEEK_AGO}). Skip anything older.\n\nList the top 3-4 recent results as a JSON array with fields: title, url, snippet. Return ONLY the JSON array, nothing else."
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

    # Load previously sent URLs to avoid duplicates across weeks
    if os.path.exists(SENT_URLS_LOG):
        with open(SENT_URLS_LOG, "r") as f:
            seen_urls = set(line.strip() for line in f if line.strip())
    prev_count = len(seen_urls)

    for target in SEARCH_QUERIES:
        print(f"  [{target['category']}] {target['source']}")
        results = search_with_claude(target["query"])
        time.sleep(15)  # 15s gap — avoids all 429s even back to back

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

        print(f"    -> {len(results)} results")

    print(f"  TOTAL: {len(all_articles)} unique articles")
    return all_articles

def curate_with_claude(articles: list[dict]) -> dict:
    articles_text = json.dumps(articles, indent=2)

    prompt = f"""You are the intelligence analyst for INOVUES.

{INOVUES_CONTEXT}

Here are articles found this week ({WEEK_AGO} to {TODAY}):
{articles_text}

Instructions:
1. Sort every article into EXACTLY one of these 5 categories (use these exact names):
   - "Competitor Intelligence" - window/glazing/facade competitors, adjacent window tech, industry product news
   - "Market & Industry News" - building energy, decarbonization, retrofits, green building standards, policy, office conversions
   - "Commercial Real Estate News" - CRE market trends, vacancy, landlord/owner news, building transactions context
   - "Deals Announced" - commercial building sales and acquisitions only
   - "Utility News" - utility rebate programs, incentives, energy rate changes, utility company news
2. Be INCLUSIVE - if there is any angle for INOVUES, include it. Only skip articles 100% unrelated to buildings or energy.
3. For each article write a sharp "INOVUES angle" - what is the business implication in 1-2 sentences.
4. Score 1-10: 10=direct sales lead or urgent action, 7-9=strong opportunity, 4-6=useful intel, 1-3=background awareness.
5. Write one punchy headline summary for the whole digest.
6. You MUST include at least 5 stories total across all categories.
7. Only include categories that have at least 1 story. Omit empty categories entirely.
8. Use these emojis: Competitor Intelligence=🔍, Market & Industry News=🏗️, Commercial Real Estate News=🏢, Deals Announced=🤝, Utility News=⚡

Return ONLY valid JSON (no markdown fences):
{{
  "date": "Week of {WEEK_AGO} - {TODAY}",
  "headline_summary": "one punchy sentence summarizing the week for INOVUES",
  "categories": [
    {{
      "name": "exact category name from the list above",
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
    
    def try_parse(s):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # Repair common Claude JSON issues
        import re
        s = re.sub(r',\s*}', '}', s)  # trailing comma before }
        s = re.sub(r',\s*]', ']', s)  # trailing comma before ]
        s = s.replace('\n', ' ')       # newlines inside strings
        # Fix unescaped quotes inside string values
        # Try progressively more aggressive fixes
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # Last resort: extract each story manually won't work, 
        # so truncate at the last valid closing brace
        for end_pos in range(len(s) - 1, 0, -1):
            if s[end_pos] == '}':
                try:
                    return json.loads(s[:end_pos + 1])
                except json.JSONDecodeError:
                    continue
        return None

    # Try markdown fenced JSON first
    if "```" in content:
        parts = content.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                result = try_parse(part)
                if result:
                    return result

    # Try raw JSON extraction
    if "{" in content:
        start = content.index("{")
        end = content.rindex("}") + 1
        result = try_parse(content[start:end])
        if result:
            return result

    # Final attempt on full content
    result = try_parse(content)
    if result:
        return result

    # If all parsing fails, return a minimal valid digest
    print(f"WARNING: Could not parse Claude response. Raw content length: {len(content)}")
    return {
        "date": f"Week of {WEEK_AGO} — {TODAY}",
        "headline_summary": "Digest curation encountered a parsing issue — showing raw results.",
        "categories": []
    }


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

    # Use port 587 with STARTTLS (ports 25/465 blocked by Hetzner/Railway)
    print("Connecting to smtp.gmail.com:587 via STARTTLS")
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.ehlo("localhost")
        server.starttls()
        server.ehlo("localhost")
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

    # Log all URLs we just sent so they won't appear in future digests
    sent_urls = set()
    for cat in digest.get("categories", []):
        for story in cat.get("stories", []):
            if story.get("url"):
                sent_urls.add(story["url"])
    with open(SENT_URLS_LOG, "a") as f:
        for url in sent_urls:
            f.write(url + "\n")
    print(f"   → Logged {len(sent_urls)} URLs to prevent future duplicates")

    print("✅ Done!")

if __name__ == "__main__":
    main()
