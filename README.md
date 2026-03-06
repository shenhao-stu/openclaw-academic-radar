# OpenClaw Academic Radar 🦞

An automated AI academic paper radar with Claude-style minimalist UI, designed for the Fudan University AI research community.

## Features

- **Daily Paper Radar** — Fetches latest papers from arXiv, NeurIPS, ICML, ICLR, ACL via Tavily search across 5 research topics
- **AI Deep Read** — Interactive chat-based paper analysis powered by configurable LLM backends
- **Multi-Model Support** — Switch between gpt-5.3-codex, minimax-m2.5, glm-5, or add custom models
- **Conference DDL Tracker** — Upcoming CCF-A/B conference deadlines at a glance
- **SOTA Leaderboard** — Current top models from LMSYS Arena
- **Dark Mode** — Full light/dark theme support with system preference detection
- **Bookmarks** — Save papers locally via localStorage

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/shenhao-stu/openclaw-academic-radar.git
cd openclaw-academic-radar
pip install -r requirements.txt

# 2. Set environment variables
cp .env.example .env
# Edit .env with your API keys

# 3. Generate today's report
export $(cat .env | xargs)
python daily_ai_brief.py

# 4. Start the server
python daily_brief_server.py
# Open http://localhost:8081
```

## Architecture

```
├── template.html          # HTML/CSS/JS template with placeholders
├── daily_ai_brief.py      # Report generator (Tavily → HTML)
├── daily_brief_server.py  # Flask server (API + static serving)
├── config.yaml            # Server configuration
├── requirements.txt       # Python dependencies
└── reports/               # Generated HTML reports (gitignored)
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TAVILY_API_KEY` | Tavily search API key |
| `OHMYAPI_KEY` | ohmyapi (gpt-5.3-codex) API key |
| `NVIDIA_API_KEY` | NVIDIA (minimax-m2.5) API key |
| `GLM_API_KEY` | Zhipu AI (glm-5) API key |

## GitHub Pages Deployment

The `gh-pages` branch supports automated daily deployment via GitHub Actions. See `.github/workflows/daily-report.yml` for the workflow configuration.

## License

MIT

---

Built by [OpenClaw](https://github.com/shenhao-stu) 🦞
