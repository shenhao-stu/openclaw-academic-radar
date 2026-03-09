<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/flask-3.0+-black?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/tailwind-CDN-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind">
  <img src="https://img.shields.io/badge/playwright-green?logo=playwright&logoColor=white" alt="Playwright">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/github/actions/workflow/status/shenhao-stu/openclaw-academic-radar/daily-report.yml?label=daily%20report&logo=githubactions&logoColor=white" alt="CI">
  <img src="https://img.shields.io/github/stars/shenhao-stu/openclaw-academic-radar?style=social" alt="Stars">
</p>

<h1 align="center">🦞 OpenClaw Academic Radar</h1>

<p align="center">
  <strong>Automated AI research paper radar with Claude-style deep-read UI</strong><br>
  Daily aggregation · Interactive AI chat · Multi-model · Vision OCR · Dark mode
</p>

<p align="center">
  <a href="#-quick-start">🚀 Quick Start</a> •
  <a href="#-features">✨ Features</a> •
  <a href="#-github-pages-deployment-static-mode">🌐 Deploy</a> •
  <a href="#%EF%B8%8F-environment-variables">⚙️ Config</a>
</p>

---

## 📖 What Is This?

**OpenClaw Academic Radar** auto-aggregates the latest AI research papers, industry news, and conference deadlines into a beautiful dashboard. Two modes:

| Mode | Description | Deployment |
|------|-------------|------------|
| 🌐 **Static** (GitHub Pages) | Read-only daily report — papers, news, SOTA rankings, conference DDLs | GitHub Actions → `gh-pages` branch |
| 🖥️ **Interactive** (Flask server) | Full features: AI chat, paper search, deep read, vision OCR, PDF parse | `python daily_brief_server.py` |

> **Note:** GitHub Pages serves static HTML only. Interactive features (AI deep read, custom search, file upload, vision OCR) require the local Flask server.

### 📊 Feature Comparison

| Feature | 🌐 GitHub Pages | 🖥️ Flask Server |
|---------|:---:|:---:|
| 📰 Daily paper report | ✅ | ✅ |
| 🏆 SOTA model rankings | ✅ | ✅ |
| 📅 Conference DDLs | ✅ | ✅ |
| 📢 Industry news | ✅ | ✅ |
| 🌙 Dark mode | ✅ | ✅ |
| 🔍 Paper search | ❌ | ✅ |
| 🤖 AI deep read / chat | ❌ | ✅ |
| 📎 Image / PDF upload + OCR | ❌ | ✅ |
| ⚙️ Custom model config | ❌ | ✅ |
| 🌐 Web search (Playwright) | ❌ | ✅ |
| 🔖 Bookmarks | ❌ | ✅ |
| 🛠️ First-run setup dialog | — | ✅ |

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📰 **Paper Radar** | Daily papers from arXiv, NeurIPS, ICML, ICLR, ACL across customizable topics |
| 🤖 **AI Deep Read** | Interactive multi-turn chat for paper analysis |
| 🔄 **Multi-Model** | Built-in default model + unlimited custom models via Settings UI |
| 👁️ **Vision OCR** | Image and PDF parsing via vision model (local sglang/vLLM or cloud API) |
| 🏆 **SOTA Tracker** | Live model rankings from [arena.ai](https://arena.ai/leaderboard) |
| 📅 **Conference DDLs** | Upcoming CCF-A/B deadlines from [ccfddl](https://github.com/ccfddl/ccf-deadlines) (live) |
| 🎯 **Custom Topics** | Configure research topics via `RADAR_TOPICS` env var |
| 🏷️ **Tag Filter** | Filter by arXiv, NeurIPS, ICML, ICLR, ACL, GitHub, Web |
| ➕ **Load More** | Fetches more from current source (academic/web) without switching |
| 🔖 **Bookmarks** | Save papers locally via localStorage |
| 🌐 **Web Search** | Playwright fetches page content for LLM when URLs are in messages |
| 🌙 **Dark Mode** | Full light/dark/system theme support |

---

## 🚀 Quick Start

```bash
git clone https://github.com/shenhao-stu/openclaw-academic-radar.git
cd openclaw-academic-radar
pip install -r requirements.txt
python -m playwright install chromium

cp .env.example .env  # fill in your API keys
python daily_ai_brief.py       # generate today's report
python daily_brief_server.py   # serve at http://localhost:8081
```

---

## 📂 Project Structure

```
├── template.html           # 🎨 Frontend (Tailwind CSS + vanilla JS)
├── daily_ai_brief.py       # 📊 Report generator (Tavily search → HTML)
├── daily_brief_server.py   # 🖥️ Flask API server (local mode)
├── config.yaml             # ⚙️ Server configuration
├── requirements.txt        # 📦 Python dependencies
├── .env.example            # 🔑 Environment variable template
├── .github/workflows/      # 🤖 GitHub Actions (daily report + Pages deploy)
└── reports/                # 📄 Generated HTML (gitignored)
```

---

## ⚙️ Environment Variables

### 🔑 Required

| Variable | Description |
|----------|-------------|
| `TAVILY_API_KEY` | [Tavily](https://tavily.com) search API key |

### 🤖 LLM Provider (Flask server)

| Variable | Description | Default |
|----------|-------------|---------|
| `OHMYAPI_KEY` | API key for OpenAI-compatible provider | — |
| `OHMYAPI_BASE_URL` | OpenAI-compatible endpoint URL | `https://api.openai.com/v1` |
| `OHMYAPI_MODEL_NAME` | Default LLM model name | `gpt-5.4` |

### 👁️ Vision / OCR

> When `VISION_*` variables are **not set**, they automatically fall back to LLM provider settings (`OHMYAPI_BASE_URL`, `OHMYAPI_MODEL_NAME`, `OHMYAPI_KEY`).

| Variable | Description | Default |
|----------|-------------|---------|
| `VISION_BASE_URL` | sglang / vLLM endpoint | Falls back to `OHMYAPI_BASE_URL` |
| `VISION_MODEL` | Vision model name or path | Falls back to `OHMYAPI_MODEL_NAME` |
| `VISION_API_TOKEN` | API token for vision endpoint | Falls back to `OHMYAPI_KEY` |

### 🎯 Custom Topics

| Variable | Format | Example |
|----------|--------|---------|
| `RADAR_TOPICS` | `Label\|Query;Label\|Query` | `推理优化\|LLM Inference;安全性\|LLM Security` |

---

## 🌐 GitHub Pages Deployment (Static Mode)

The workflow in `.github/workflows/daily-report.yml` runs daily at **10:00 AM Beijing time** (UTC+8), generates the HTML report via Tavily, and pushes to the `gh-pages` branch.

### Setup

1. Go to **Settings → Secrets and variables → Actions**
   - **Secrets:** Add `TAVILY_API_KEY`
2. Go to **Settings → Pages** → Source: **Deploy from a branch** → Branch: `gh-pages` / `/ (root)`
3. *(Optional)* Add `RADAR_TOPICS` as a **Repository variable** for custom topics
4. Trigger manually from the **Actions** tab to test

> **Static mode limitations:** The GitHub Pages site is a read-only daily report. Features like AI deep read, paper search, file upload, and vision OCR are **not available** — they require the local Flask server (`python daily_brief_server.py`).
>
> **Local server first-run:** If `.env` is missing required keys, a setup dialog will appear on first load, letting you configure API keys directly from the browser.

---

## 👁️ Local Vision Model

The Vision / OCR feature can use a local OpenAI-compatible inference server (e.g. sglang or vLLM), or fall back to your LLM provider's API if no local server is configured.

```bash
# Example: start with sglang
conda activate sglang
SGLANG_DISABLE_CUDNN_CHECK=1 python -m sglang.launch_server \
  --model-path /path/to/Qwen3.5-2B \
  --port 30000 --host 0.0.0.0 --tp 1 \
  --mem-fraction-static 0.85 --disable-cuda-graph \
  --attention-backend triton --served-model-name Qwen/Qwen3.5-2B
```

Configure via env vars or the Vision / OCR settings popover in the chat UI.

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| 🌐 Web Search not working | Run `python -m playwright install chromium` |
| 📰 No papers shown | Check `TAVILY_API_KEY` is set and Tavily quota is available |
| 🤖 AI Deep Read fails | Add `OHMYAPI_KEY` or a custom model in Settings |
| 👁️ Vision test fails | Ensure `VISION_MODEL` matches the model loaded by your server |
| 🔌 Port 8081 in use | Change `port` in `config.yaml` or stop the conflicting process |

---

## ⭐ Star History

<a href="https://star-history.com/#shenhao-stu/openclaw-academic-radar&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=shenhao-stu/openclaw-academic-radar&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=shenhao-stu/openclaw-academic-radar&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=shenhao-stu/openclaw-academic-radar&type=Date" />
 </picture>
</a>

---

## 📄 License

MIT

---

<p align="center">Built with ❤️ by <a href="https://github.com/shenhao-stu">OpenClaw</a></p>
