#!/usr/bin/env python3
"""
INOVUES Daily News Digest
Fetches news, curates with Claude AI, sends branded HTML email at 8 AM daily.
"""

import os
import json
import smtplib
import requests
import base64
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]
GMAIL_APP_PASS    = os.environ["GMAIL_APP_PASS"]
RECIPIENTS        = os.environ.get("RECIPIENTS", GMAIL_USER).split(",")
BRAVE_API_KEY     = os.environ.get("BRAVE_API_KEY", "")  # optional, falls back to RSS

TOPICS = [
    {
        "name": "NYC Local Law 97 & Energy Policy",
        "queries": ["NYC Local Law 97 compliance 2025", "New York City building energy policy"],
        "emoji": "⚡"
    },
    {
        "name": "Commercial Real Estate NYC",
        "queries": ["NYC commercial real estate news", "New York office building market 2025"],
        "emoji": "🏢"
    },
    {
        "name": "Facade & Building Envelope",
        "queries": ["commercial building facade retrofit", "curtain wall glazing industry news"],
        "emoji": "🪟"
    },
    {
        "name": "Energy Efficiency Incentives",
        "queries": ["building energy efficiency grants incentives NYC", "IRA commercial building retrofit incentives"],
        "emoji": "💡"
    },
    {
        "name": "NYC DOB & Building Regulations",
        "queries": ["NYC Department of Buildings regulations 2025", "NYC building code updates"],
        "emoji": "📋"
    },
]

INOVUES_CONTEXT = """
INOVUES is a NYC-based facade installation company specializing in secondary window 
retrofit systems for commercial buildings. Their core product helps building owners 
comply with NYC Local Law 97 (carbon emission limits), improve energy efficiency, 
and reduce heating/cooling costs. Their target customers are owners and managers of 
large commercial buildings in NYC. They compete on speed of installation, minimal 
disruption, and measurable energy savings.
"""

# ── Fetch News ─────────────────────────────────────────────────────────────────
def fetch_news_brave(query: str) -> list[dict]:
    """Fetch news using Brave Search API."""
    if not BRAVE_API_KEY:
        return []
    try:
        r = requests.get(
            "https://api.search.brave.com/res/v1/news/search",
            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
            params={"q": query, "count": 5, "freshness": "pd"},
            timeout=10
        )
        if r.status_code == 200:
            return r.json().get("results", [])
    except Exception:
        pass
    return []


def fetch_news_gnews(query: str) -> list[dict]:
    """Fallback: GNews free tier."""
    try:
        r = requests.get(
            "https://gnews.io/api/v4/search",
            params={
                "q": query,
                "lang": "en",
                "country": "us",
                "max": 5,
                "apikey": os.environ.get("GNEWS_API_KEY", ""),
            },
            timeout=10
        )
        if r.status_code == 200:
            articles = r.json().get("articles", [])
            return [{"title": a["title"], "url": a["url"], "description": a.get("description", ""), "age": a.get("publishedAt", "")} for a in articles]
    except Exception:
        pass
    return []


def fetch_all_news() -> dict:
    """Fetch raw news for all topics."""
    all_news = {}
    for topic in TOPICS:
        articles = []
        for query in topic["queries"]:
            results = fetch_news_brave(query) or fetch_news_gnews(query)
            for r in results:
                articles.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", r.get("url", "")),
                    "description": r.get("description", r.get("extra_snippets", [""])[0] if isinstance(r.get("extra_snippets"), list) else ""),
                    "source": r.get("source", {}).get("name", "") if isinstance(r.get("source"), dict) else r.get("source", ""),
                    "age": r.get("age", r.get("publishedAt", ""))
                })
        # Deduplicate by title
        seen = set()
        unique = []
        for a in articles:
            if a["title"] not in seen:
                seen.add(a["title"])
                unique.append(a)
        all_news[topic["name"]] = unique
    return all_news


# ── Claude Curation ────────────────────────────────────────────────────────────
def curate_with_claude(all_news: dict) -> dict:
    """Use Claude to select and summarize the most relevant stories."""
    
    news_dump = json.dumps(all_news, indent=2)
    
    prompt = f"""You are the news curator for INOVUES, a NYC commercial building facade retrofit company.

Company context:
{INOVUES_CONTEXT}

Here is today's raw news collected across topics:
{news_dump}

Your task:
1. For each topic, select the 2-4 most relevant and actionable stories for INOVUES
2. If a story is not relevant to INOVUES at all, exclude it
3. If a topic has no relevant news today, return an empty list for it
4. Write a 1-2 sentence summary for each selected story explaining WHY it matters to INOVUES
5. Assign a relevance score 1-10 (10 = critical for INOVUES business)

Return ONLY valid JSON in this exact format:
{{
  "date": "{datetime.now().strftime('%A, %B %d, %Y')}",
  "headline_summary": "A 1-sentence overall summary of today's most important news for INOVUES",
  "topics": [
    {{
      "name": "topic name",
      "emoji": "emoji",
      "stories": [
        {{
          "title": "story title",
          "url": "story url",
          "source": "publication name",
          "summary": "why this matters to INOVUES in 1-2 sentences",
          "score": 8
        }}
      ]
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
    content = response.json()["content"][0]["text"]
    
    # Strip markdown fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()
    
    return json.loads(content)


# ── Email HTML ─────────────────────────────────────────────────────────────────
def build_html(digest: dict) -> str:
    """Build the branded HTML email."""
    
    date_str = digest.get("date", datetime.now().strftime('%A, %B %d, %Y'))
    headline = digest.get("headline_summary", "Your daily INOVUES intelligence briefing.")
    topics = digest.get("topics", [])
    
    # Build topic sections
    topic_html = ""
    total_stories = 0
    
    for topic in topics:
        stories = topic.get("stories", [])
        if not stories:
            continue
        total_stories += len(stories)
        
        stories_html = ""
        for story in sorted(stories, key=lambda x: x.get("score", 0), reverse=True):
            score = story.get("score", 5)
            score_color = "#1B9FAF" if score >= 8 else "#5BB8C4" if score >= 6 else "#9AD4DB"
            stories_html += f"""
            <tr>
              <td style="padding: 16px 0; border-bottom: 1px solid #f0f0f0;">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td>
                      <a href="{story.get('url','#')}" style="font-size:15px; font-weight:600; color:#1a1a1a; text-decoration:none; line-height:1.4;">{story.get('title','')}</a>
                      <p style="margin:6px 0 0; font-size:13px; color:#555; line-height:1.6;">{story.get('summary','')}</p>
                      <p style="margin:6px 0 0; font-size:12px; color:#999;">{story.get('source','')}</p>
                    </td>
                    <td width="40" style="vertical-align:top; padding-left:12px; text-align:center;">
                      <div style="background:{score_color}; color:white; border-radius:50%; width:32px; height:32px; line-height:32px; text-align:center; font-size:12px; font-weight:700;">{score}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>"""
        
        topic_html += f"""
        <tr>
          <td style="padding: 28px 0 4px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="border-left: 3px solid #1B9FAF; padding-left: 12px;">
                  <span style="font-size:11px; font-weight:700; letter-spacing:1.5px; color:#1B9FAF; text-transform:uppercase;">{topic.get('emoji','')} {topic.get('name','')}</span>
                </td>
              </tr>
            </table>
            <table width="100%" cellpadding="0" cellspacing="0">
              {stories_html}
            </table>
          </td>
        </tr>"""
    
    if not topic_html:
        topic_html = """<tr><td style="padding:24px 0; color:#888; font-size:14px;">No significant news found for INOVUES today.</td></tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>INOVUES Daily Digest</title>
</head>
<body style="margin:0; padding:0; background:#f4f4f4; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4; padding: 32px 16px;">
  <tr>
    <td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%;">
        
        <!-- Header -->
        <tr>
          <td style="background:#1B9FAF; border-radius:12px 12px 0 0; padding: 32px 40px; text-align:center;">
            <img src="cid:inovues_logo" alt="INOVUES" width="80" style="display:block; margin: 0 auto 16px;">
            <p style="margin:0; font-size:11px; letter-spacing:2px; color:rgba(255,255,255,0.7); text-transform:uppercase; font-weight:600;">Daily Intelligence Digest</p>
            <p style="margin:8px 0 0; font-size:22px; font-weight:700; color:white;">{date_str}</p>
          </td>
        </tr>
        
        <!-- Headline summary -->
        <tr>
          <td style="background:#0e7a87; padding: 16px 40px; border-radius:0;">
            <p style="margin:0; font-size:14px; color:rgba(255,255,255,0.9); line-height:1.6; font-style:italic;">"{headline}"</p>
          </td>
        </tr>
        
        <!-- Stats bar -->
        <tr>
          <td style="background:white; padding: 14px 40px; border-bottom: 1px solid #eee;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="font-size:12px; color:#999;">{total_stories} stories across {len([t for t in topics if t.get('stories')])} topics</td>
                <td style="text-align:right; font-size:12px; color:#999;">Relevance scored by AI ●</td>
              </tr>
            </table>
          </td>
        </tr>
        
        <!-- Body -->
        <tr>
          <td style="background:white; padding: 8px 40px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              {topic_html}
            </table>
          </td>
        </tr>
        
        <!-- Footer -->
        <tr>
          <td style="background:#1a1a1a; border-radius:0 0 12px 12px; padding: 24px 40px; text-align:center;">
            <p style="margin:0 0 6px; font-size:12px; color:#666; letter-spacing:1px; text-transform:uppercase;">INOVUES · Adaptive Glazing Shields</p>
            <p style="margin:0; font-size:11px; color:#444;">This digest is generated automatically every morning at 8 AM EST.</p>
          </td>
        </tr>
        
      </table>
    </td>
  </tr>
</table>

</body>
</html>"""
    
    return html


# ── Send Email ─────────────────────────────────────────────────────────────────
def send_email(html: str, subject: str):
    """Send the digest email via Gmail SMTP."""
    
    msg = MIMEMultipart("related")
    msg["From"]    = f"INOVUES Digest <{GMAIL_USER}>"
    msg["To"]      = ", ".join(RECIPIENTS)
    msg["Subject"] = subject
    
    # Attach HTML
    msg_alt = MIMEMultipart("alternative")
    msg.attach(msg_alt)
    msg_alt.attach(MIMEText(html, "html"))
    
    # Attach logo as inline image
    logo_path = Path(__file__).parent / "logo.jpg"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            img = MIMEImage(f.read(), _subtype="jpeg")
            img.add_header("Content-ID", "<inovues_logo>")
            img.add_header("Content-Disposition", "inline", filename="logo.jpg")
            msg.attach(img)
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASS)
        server.sendmail(GMAIL_USER, RECIPIENTS, msg.as_string())
    
    print(f"✅ Digest sent to {', '.join(RECIPIENTS)}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"🦞 INOVUES Digest starting — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    print("📰 Fetching news...")
    all_news = fetch_all_news()
    
    total_raw = sum(len(v) for v in all_news.values())
    print(f"   Found {total_raw} raw articles")
    
    print("🤖 Curating with Claude...")
    digest = curate_with_claude(all_news)
    
    print("🎨 Building email...")
    html = build_html(digest)
    
    date_short = datetime.now().strftime("%b %d")
    subject = f"INOVUES Daily Digest — {date_short}"
    
    print("📬 Sending email...")
    send_email(html, subject)
    
    print("✅ Done!")


if __name__ == "__main__":
    main()
