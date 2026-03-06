<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/flask-3.0+-black?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/tailwind-CDN-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/github/actions/workflow/status/shenhao-stu/openclaw-academic-radar/daily-report.yml?label=daily%20report" alt="CI">
</p>

<h1 align="center">🦞 OpenClaw Academic Radar</h1>

<p align="center">
  <strong>Automated AI research paper radar with Claude-style UI</strong><br>
  Daily aggregation · Interactive AI deep-read · Multi-model chat · Dark mode
</p>

---

## Overview

OpenClaw Academic Radar automatically aggregates the latest AI research papers, industry news, and conference deadlines into a single, beautifully rendered dashboard. It features an interactive **AI Deep Read** chat interface for paper analysis, powered by configurable LLM backends.

## Features

| Feature | Description |
|---------|-------------|
| **Paper Radar** | Daily papers from arXiv, NeurIPS, ICML, ICLR, ACL across customizable topics |
| **Load More** | "发现更多" keeps current source (academic/web), fetches up to 20 results |
| **Tag Filter** | Filter by arXiv, NeurIPS, ICML, ICLR, ACL, GitHub, Web |
| **AI Deep Read** | Interactive chat-based paper analysis with multi-turn conversation |
| **Multi-Model** | Built-in gpt-5.4, glm-5 + unlimited custom models via settings UI |
| **SOTA Tracker** | Live model rankings from [arena.ai](https://arena.ai/leaderboard) |
| **Conference DDLs** | Upcoming CCF-A/B deadlines from [ccfddl.github.io](https://ccfddl.github.io/) |
| **Custom Topics** | Configure research topics via `RADAR_TOPICS` environment variable |
| **Dark Mode** | Full light/dark/system theme support |
| **Bookmarks** | Save papers locally via localStorage |
| **File Attach** | Paste paper text/abstracts, images (PNG/JPG), or PDF metadata into chat |
| **Web Search** | Playwright fetches page content for LLM when URLs are in messages |

## Quick Start

```bash
git clone https://github.com/shenhao-stu/openclaw-academic-radar.git
cd openclaw-academic-radar
pip install -r requirements.txt

# Playwright (for Web Search): Python package uses its own browser install.
# If you already ran `npx playwright install`, browsers may be shared.
python -m playwright install chromium

cp .env.example .env  # Edit with your API keys
export $(cat .env | xargs)

python daily_ai_brief.py   # Generate report
python daily_brief_server.py  # Serve at http://localhost:8081
```

## Project Structure

```
├── template.html           # Frontend template (Tailwind CSS + vanilla JS)
├── daily_ai_brief.py       # Report generator (Tavily search → HTML)
├── daily_brief_server.py   # Flask API server
├── config.yaml             # Server configuration
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── .github/workflows/      # GitHub Actions (gh-pages branch)
└── reports/                # Generated HTML (gitignored)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TAVILY_API_KEY` | ✅ | [Tavily](https://tavily.com) search API key |
| `OHMYAPI_KEY` | For gpt-5.4 | ohmyapi provider key |
| `GLM_API_KEY` | For glm-5 | Zhipu AI provider key |
| `RADAR_TOPICS` | Optional | Custom topics: `Label\|Query;Label\|Query` |

## GitHub Pages Deployment

The `gh-pages` branch includes a GitHub Actions workflow that:
1. Runs daily at **10:00 AM Beijing time** (UTC+8)
2. Generates the HTML report via Tavily API
3. Deploys to GitHub Pages automatically

### Setup

1. Go to **Settings → Secrets** and add `TAVILY_API_KEY`
2. Go to **Settings → Pages** and set source to **GitHub Actions**
3. Optionally trigger manually from the **Actions** tab

## GitHub Secrets Required

| Secret | Purpose |
|--------|---------|
| `TAVILY_API_KEY` | Paper search (required for report generation) |

> **Note:** LLM API keys (`OHMYAPI_KEY`, `GLM_API_KEY`) are only needed for the Flask server's AI Deep Read feature. The static GitHub Pages deployment only requires `TAVILY_API_KEY`.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Web Search not working | Ensure `python -m playwright install chromium` ran successfully |
| No papers shown | Check `TAVILY_API_KEY` is set; verify Tavily API quota |
| AI Deep Read fails | Configure `OHMYAPI_KEY` or `GLM_API_KEY`, or add custom model in Settings |
| Port 8081 in use | Change `port` in `config.yaml` or stop the conflicting process |

## License

MIT

---

<p align="center">Built with ❤️ by <a href="https://github.com/shenhao-stu">OpenClaw</a></p>
