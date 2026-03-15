# INOVUES Daily News Digest

Automated daily intelligence briefing for INOVUES, delivered every morning at 8 AM EST.

Covers: NYC Local Law 97, Commercial Real Estate NYC, Facade & Building Envelope, Energy Efficiency Incentives, NYC DOB Regulations.

## Setup

### 1. Clone and install dependencies
```bash
git clone https://github.com/StephanBK/inovues-digest.git
cd inovues-digest
pip3 install -r requirements.txt --break-system-packages
```

### 2. Add the INOVUES logo
Place `logo.jpg` in the project root (the INOVUES 500x500 logo).

### 3. Configure environment
```bash
cp .env.example .env
nano .env
```

Fill in:
- `ANTHROPIC_API_KEY` — your Anthropic API key
- `GMAIL_USER` — Gmail address to send from
- `GMAIL_APP_PASS` — Google App Password (see below)
- `RECIPIENTS` — comma-separated recipient emails
- `GNEWS_API_KEY` — free key from https://gnews.io (optional but recommended)

### 4. Get a Gmail App Password
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification if not already on
3. Search for "App passwords"
4. Create one for "Mail" → copy the 16-character password
5. Paste into `.env` as `GMAIL_APP_PASS`

### 5. Test it
```bash
chmod +x run.sh
./run.sh
```

### 6. Schedule daily at 8 AM EST (UTC-4 in summer, UTC-5 in winter)
```bash
crontab -e
```
Add:
```
0 12 * * * /root/inovues-digest/run.sh >> /root/inovues-digest/digest.log 2>&1
```
(12:00 UTC = 8:00 AM EST)

## News Sources
- Brave Search API (preferred) — sign up at https://api.search.brave.com
- GNews API (fallback) — free tier at https://gnews.io

## Relevance Scoring
Each story is scored 1-10 by Claude based on relevance to INOVUES:
- **8-10**: Critical — directly affects INOVUES business or customers
- **5-7**: Relevant — useful market intelligence  
- **1-4**: Low — general background noise (usually excluded)
