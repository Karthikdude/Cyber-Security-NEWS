# 🛡️ Cyber-Security-NEWS

**Automated Cybersecurity News Aggregator** - Scrape, filter, score, and publish cybersecurity news to Telegram using AI.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange.svg)

---

## 🚀 Features

- **📰 8 News Sources** - Aggregates from top cybersecurity publications
- **🤖 AI-Powered Filtering** - Uses Google Gemini to filter and score articles
- **📱 Telegram Publishing** - Auto-publishes high-quality articles to groups/channels
- **🔄 Multi-Bot Support** - Use multiple bots for load distribution
- **📊 Multi-Group Support** - Publish to multiple Telegram groups simultaneously
- **💾 Optional Database** - Enable/disable article persistence
- **🔑 API Key Rotation** - Automatic rotation when rate limits hit
- **⏱️ GitHub Actions** - Scheduled daily runs at 4-6 PM IST

---
---

## 🔧 How It Works

### Pipeline Flow

```
1. SCRAPE      →  Fetch articles from 8 cybersecurity news sources
2. DEDUPE      →  Filter out already-processed articles (via DB or in-memory)
3. AI FILTER+SCORE →  40 articles per API call: filter & score (0-10) in ONE request
4. ENRICH      →  Fetch full article content for approved articles (score ≥6.0)
5. PUBLISH     →  Send approved articles to Telegram
6. SAVE        →  Mark as posted in database (if enabled)
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `main.py` | Orchestrates the entire pipeline: scrape → filter → score → publish |
| `core/ai.py` | Gemini integration with model fallback, key rotation, batch filtering |
| `core/db.py` | SQLite storage with optional disable mode (in-memory deduplication) |
| `core/publisher.py` | Telegram bot(s) publishing to multiple groups |
| `core/scraper_base.py` | Abstract base class with content enrichment using readability |
| `core/models.py` | `Article` dataclass with title, url, content, score, etc. |

---

## 🤖 Gemini AI Models (Free Tier)

The system uses **Google Gemini free tier** with automatic model fallback. No billing required!

### Available Models & Rate Limits

| Model | RPM | RPD | Best For |
|-------|-----|-----|----------|
| `gemini-2.5-flash` | 10 | 20 | Primary - fast & capable |
| `gemini-2.5-flash-lite` | 15 | 1,000 | High volume |
| `gemini-2.5-pro` | 5 | 100 | Complex reasoning |
| `gemini-3-flash-preview` | 15 | 1,000 | Latest features |
| `gemini-2.0-flash` | 15 | 200 | Good balance |
| `gemini-2.0-flash-lite` | 30 | 1,000 | High throughput |
| `gemma-3-27b-it` | 30 | 14,400 | Most capable Gemma |
| `gemma-3-12b-it` | 30 | 14,400 | Very capable |
| `gemma-3-4b-it` | 30 | 14,400 | Speed/quality balance |
| `gemma-3n-e4b-it` | 30 | 14,400 | Edge optimized |
| `gemma-3n-e2b-it` | 30 | 14,400 | Ultra-fast |
| `gemma-3-1b-it` | 30 | 14,400 | Lightweight |

> **RPM** = Requests Per Minute | **RPD** = Requests Per Day

### Smart Rotation Strategy

1. **Model Fallback**: When rate-limited, tries next model in list
2. **Key Rotation**: After exhausting all models, rotates to next API key
3. **Multiple Keys**: Supports up to 10 API keys (`GEMINI_API_KEY`, `GEMINI_API_KEY_2`, etc.)

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file (see `.env.example`):

```env
# Database (set to 'false' to disable persistence)
ENABLE_DATABASE=true

# Telegram - Simple format (single bot)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=-1001234567890,-1009876543210  # Comma-separated for multiple groups

# Telegram - Multi-bot format (optional)
# TELEGRAM_BOT_TOKEN_1=first_bot_token
# TELEGRAM_CHAT_IDS_1=-1001234567890,-1009876543210
# TELEGRAM_BOT_TOKEN_2=second_bot_token
# TELEGRAM_CHAT_IDS_2=-1005555555555

# Gemini API Keys (supports multiple for rate limit handling)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_API_KEY_2=your_second_key
GEMINI_API_KEY_3=your_third_key
# ... up to GEMINI_API_KEY_10
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_DATABASE` | `true` | Set to `false` to disable SQLite persistence |
| `TELEGRAM_BOT_TOKEN` | - | Single bot token (simple format) |
| `TELEGRAM_CHAT_ID` | - | Comma-separated group IDs |
| `TELEGRAM_BOT_TOKEN_N` | - | Numbered bot tokens (multi-bot format) |
| `TELEGRAM_CHAT_IDS_N` | - | Groups for bot N |
| `GEMINI_API_KEY` | - | Primary Gemini API key |
| `GEMINI_API_KEY_N` | - | Additional API keys (2-10) |

---

## 🚀 Installation

### Local Setup

```bash
# Clone the repository
git clone https://github.com/Karthikdude/Cyber-Security-NEWS
cd Cyber-Security-NEWS

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run
python main.py
```

### GitHub Actions (Automated)

The repository includes a workflow that runs daily at **4:00 PM IST** with a **2-hour timeout**.

1. Go to repository **Settings** → **Secrets and variables** → **Actions**
2. Add the following secrets:

| Secret Name | Value |
|-------------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token |
| `TELEGRAM_CHAT_ID` | Your group ID(s) |
| `GEMINI_API_KEY` | Primary Gemini key |
| `GEMINI_API_KEY_2` | Second key (optional) |
| `GEMINI_API_KEY_3` | Third key (optional) |
| ... | ... |

3. (Optional) Add variable `ENABLE_DATABASE` = `false` under **Variables** tab

---

## 📊 Scoring Criteria

Articles are scored 0-10 by Gemini AI:

| Score | Criteria | Action |
|-------|----------|--------|
| **9-10** | Critical 0-days, major breaches, industry shifts | ✅ Published |
| **7-8** | Important patches, new attack vectors, notable reports | ✅ Published |
| **6** | Significant routine updates | ✅ Published |
| **< 6** | Marketing, basic tips, low technical value | ❌ Skipped |

---

## 📡 News Sources

| Source | Type | Focus |
|--------|------|-------|
| The Hacker News | RSS | Breaking security news |
| Bleeping Computer | RSS | Malware, vulnerabilities |
| Threat Post | HTML | Threat intelligence |
| Infosecurity Magazine | RSS | Industry news |
| Security Affairs | RSS | APT, nation-state threats |
| CyberScoop | RSS | Policy, government security |
| CSO Online | RSS | Enterprise security |
| Cybersecurity News | RSS | General security news |

---

## 🔒 Security Notes

- **Never commit `.env`** - Contains sensitive API keys
- **Use GitHub Secrets** - For Actions deployments
- **Rotate keys regularly** - If you suspect exposure
- **Group IDs are negative** - Format: `-1001234567890`

---

## 📝 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🙏 Credits

Built with:
- [Google Gemini API](https://ai.google.dev/) - AI scoring
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram integration
- [readability-lxml](https://github.com/buriy/python-readability) - Content extraction
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
