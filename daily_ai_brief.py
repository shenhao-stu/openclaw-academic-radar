"""Generate the daily AI Academic Radar HTML report.

Supports custom topics via RADAR_TOPICS environment variable:
  RADAR_TOPICS='推理优化|LLM Inference RAG;安全性|LLM Security jailbreak'
  Format: Chinese Label|English Query, separated by semicolons.
"""

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta

# Auto-load .env from project root if present
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

import yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
    config = yaml.safe_load(f)

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

DEFAULT_TOPICS = [
    {"name": "🚀 推理与服务优化", "query": "LLM Inference RAG System optimization"},
    {"name": "🛡️ 系统安全性", "query": "LLM Agent Security jailbreak alignment"},
    {"name": "🧠 记忆与强化学习", "query": "LLM Memory Reinforcement Learning RLHF"},
    {"name": "📡 通信效率优化", "query": "LLM Communication Distributed Training efficiency"},
    {"name": "🎵 音频大模型与声码器", "query": "Audio LLM Vocoder Speech Generation"},
]

TAG_RULES = [
    ("arxiv", "arXiv", "bg-gray-100 text-gray-600 dark:bg-[#2c2c2c] dark:text-gray-400 border-gray-200 dark:border-[#333]"),
    ("neurips", "NeurIPS", "bg-purple-50 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400 border-purple-100 dark:border-purple-800/30"),
    ("nips", "NeurIPS", "bg-purple-50 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400 border-purple-100 dark:border-purple-800/30"),
    ("icml", "ICML", "bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400 border-blue-100 dark:border-blue-800/30"),
    ("iclr", "ICLR", "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30"),
    ("emnlp", "ACL", "bg-rose-50 text-rose-600 dark:bg-rose-900/20 dark:text-rose-400 border-rose-100 dark:border-rose-800/30"),
    ("acl", "ACL", "bg-rose-50 text-rose-600 dark:bg-rose-900/20 dark:text-rose-400 border-rose-100 dark:border-rose-800/30"),
    ("github", "GitHub", "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700"),
]
DEFAULT_TAG_COLOR = "bg-gray-100 text-gray-600 dark:bg-[#2c2c2c] dark:text-gray-400 border-gray-200 dark:border-[#333]"

CCF_AI_DIRS = ["AI"]


def parse_topics() -> list[dict]:
    env = os.environ.get("RADAR_TOPICS", "")
    if not env.strip():
        return DEFAULT_TOPICS
    topics = []
    for part in env.split(";"):
        part = part.strip()
        if "|" in part:
            name, query = part.split("|", 1)
            topics.append({"name": name.strip(), "query": query.strip()})
    return topics if topics else DEFAULT_TOPICS


def _classify_link(url: str) -> tuple:
    lower = url.lower()
    for kw, tag, color in TAG_RULES:
        if kw in lower:
            return tag, color
    try:
        domain = lower.split("//")[1].split("/")[0].replace("www.", "")
        return domain.split(".")[0].capitalize(), DEFAULT_TAG_COLOR
    except Exception:
        return "Web", DEFAULT_TAG_COLOR


ACADEMIC_DOMAINS = ["arxiv.org", "nips.cc", "neurips.cc", "icml.cc", "iclr.cc", "aclweb.org", "openreview.net"]


def search_tavily(query: str, max_results: int = 8, time_range: str = "month",
                   include_domains: list | None = None) -> list:
    body = {
        "api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic",
        "include_images": False, "include_answer": False,
        "max_results": max_results, "time_range": time_range,
    }
    if include_domains:
        body["include_domains"] = include_domains
    payload = json.dumps(body).encode("utf-8")
    try:
        req = urllib.request.Request("https://api.tavily.com/search", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("results", [])
    except Exception as e:
        print(f"Tavily error: {e}")
        return []


def _fetch_json(url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OpenClaw-Academic-Radar/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Fetch error {url}: {e}")
        return None


def _fetch_text(url: str, timeout: int = 15) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OpenClaw-Academic-Radar/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"Fetch error {url}: {e}")
        return ""


def fetch_ccf_deadlines() -> str:
    """Fetch upcoming AI conference deadlines (CCF-A/B) from ccfddl/ccf-deadlines."""
    now = datetime.now()
    upcoming = []

    for category in CCF_AI_DIRS:
        api_url = f"https://api.github.com/repos/ccfddl/ccf-deadlines/contents/conference/{category}"
        files_data = _fetch_json(api_url)
        if not files_data:
            print(f"Failed to fetch ccfddl/{category}")
            continue

        for item in files_data:
            if item.get("type") != "file" or not item["name"].endswith(".yml"):
                continue

            raw = _fetch_text(item["download_url"])
            if not raw:
                continue
            try:
                confs = yaml.safe_load(raw)
                if not isinstance(confs, list):
                    continue
                conf = confs[0]
                ccf_rank = conf.get("rank", {}).get("ccf", "")
                if ccf_rank not in ("A", "B"):
                    continue
                title = conf.get("title", item["name"].replace(".yml", "").upper())

                for c in sorted(conf.get("confs", []), key=lambda x: x.get("year", 0), reverse=True):
                    for tl in c.get("timeline", []):
                        dl_str = tl.get("deadline", "")
                        if not dl_str or dl_str == "TBD":
                            continue
                        try:
                            dl = datetime.strptime(dl_str[:19], "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            continue
                        if dl > now:
                            upcoming.append({
                                "title": title, "ccf": ccf_rank,
                                "deadline": dl_str[:10], "days": (dl - now).days,
                                "link": c.get("link", ""),
                            })
                            break
                    else:
                        continue
                    break
            except Exception as e:
                print(f"Parse error {item['name']}: {e}")

    upcoming.sort(key=lambda x: x["days"])
    upcoming = upcoming[:4]
    if not upcoming:
        return _fallback_conferences_html()

    rank_color = {
        "A": "bg-purple-50 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400",
        "B": "bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400",
    }
    html = '<div class="grid grid-cols-2 gap-2.5">'
    for c in upcoming:
        cls = rank_color.get(c["ccf"], rank_color["A"])
        days_cls = "text-red-500" if c["days"] <= 30 else "text-orange-500"
        html += f'''<a href="{c["link"]}" target="_blank" class="p-3 rounded-xl border border-gray-200 dark:border-[#333] bg-white dark:bg-[#1e1e1e] hover:shadow-sm transition group">
        <div class="flex items-center gap-2 mb-2"><span class="font-black text-[14px] text-gray-900 dark:text-gray-100 group-hover:text-indigo-600 transition-colors">{c["title"]}</span><span class="px-1.5 py-0.5 {cls} rounded text-[9px] font-bold">CCF-{c["ccf"]}</span></div>
        <div class="text-[10px] text-gray-400 mb-1">Deadline: {c["deadline"]}</div><div class="text-[12px] font-bold {days_cls}">{c["days"]} days left</div></a>'''
    html += '</div>'
    return html


def _fallback_conferences_html() -> str:
    return '<div class="text-[12px] text-gray-400 py-4 text-center">会议信息加载失败，请访问 <a href="https://ccfddl.com" target="_blank" class="text-indigo-500 hover:underline">ccfddl.com</a></div>'


def _fetch_sota_via_playwright() -> list:
    """Render arena.ai/leaderboard with Playwright and extract the Text tab rankings."""
    try:
        from playwright.sync_api import sync_playwright
        import re as _re

        ORG_MAP = {
            "claude": "Anthropic", "gemini": "Google", "gpt": "OpenAI",
            "grok": "xAI", "deepseek": "DeepSeek", "qwen": "Alibaba",
            "llama": "Meta", "mistral": "Mistral", "glm": "Zhipu",
            "kimi": "Moonshot", "ernie": "Baidu", "hunyuan": "Tencent",
            "minimax": "Minimax",
        }

        def _guess_org(name: str) -> str:
            nl = name.lower()
            for k, v in ORG_MAP.items():
                if k in nl:
                    return v
            return ""

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://arena.ai/leaderboard", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            rows = page.evaluate("""() => {
                const rows = document.querySelectorAll('tr');
                return Array.from(rows).map(r => r.innerText.replace(/\\t/g,'  ').replace(/\\n/g,'  ').trim());
            }""")
            browser.close()

        models = []
        seen_ranks = set()
        # Rows look like: "1  claude-opus-4-6  1504 9,170"
        # The first "Rank Model Score Votes" block is the Text leaderboard
        in_text_section = False
        for row in rows:
            row = row.strip()
            # The header row looks like "Rank      Model      Score      Votes" (extra spaces)
            if _re.match(r'^Rank\s+Model\s+Score\s+Votes$', row):
                if not in_text_section:
                    in_text_section = True
                    continue
                else:
                    break  # second header = different modality, stop
            if row in ("View all", "") or not in_text_section:
                continue
            # Parse "RANK  MODEL_NAME  SCORE  VOTES"
            m = _re.match(r'^(\d+)\s{2,}(.+?)\s{2,}(\d{3,4})\s', row)
            if m:
                rank = int(m.group(1))
                name = m.group(2).strip()
                score = int(m.group(3))
                if rank not in seen_ranks and 1 <= rank <= 5:
                    seen_ranks.add(rank)
                    models.append({"rank": rank, "name": name, "org": _guess_org(name), "score": score})
            if len(models) == 5:
                break

        models.sort(key=lambda x: x["rank"])
        return models

    except Exception as e:
        print(f"Playwright arena fetch error: {e}")
        return []


SOTA_CACHE_PATH = os.path.join(BASE_DIR, ".sota_cache.json")


def _load_sota_cache() -> list:
    """Load the last successfully fetched SOTA models from local cache."""
    try:
        with open(SOTA_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and len(data) >= 3:
            return data
    except Exception:
        pass
    return []


def _save_sota_cache(models: list) -> None:
    """Persist successfully fetched SOTA models to local cache."""
    try:
        with open(SOTA_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(models, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save SOTA cache: {e}")


def fetch_sota_models() -> str:
    """Fetch SOTA models from arena.ai leaderboard.

    Strategy:
    1. Render arena.ai/leaderboard with Playwright and parse the displayed table.
    2. On success, write results to .sota_cache.json so future fallbacks stay fresh.
    3. On failure, fall back to cached results (last successful fetch).
    4. If cache is also empty, use hardcoded bootstrap data.
    """
    print("Fetching SOTA models via Playwright...")
    models = _fetch_sota_via_playwright()

    if models:
        print(f"Playwright arena fetch: got {len(models)} models, top={models[0]['name']} ({models[0]['score']})")
        _save_sota_cache(models)
    else:
        print("Playwright arena fetch failed, trying cache...")
        models = _load_sota_cache()
        if models:
            print(f"Using cached SOTA data: top={models[0]['name']} ({models[0]['score']})")
        else:
            print("No cache found, using hardcoded bootstrap fallback")
            models = [
                {"rank": 1, "name": "claude-opus-4-6", "org": "Anthropic", "score": 1504},
                {"rank": 2, "name": "claude-opus-4-6-thinking", "org": "Anthropic", "score": 1502},
                {"rank": 3, "name": "gemini-3.1-pro-preview", "org": "Google", "score": 1500},
                {"rank": 4, "name": "grok-4.20-beta1", "org": "xAI", "score": 1491},
                {"rank": 5, "name": "gemini-3-pro", "org": "Google", "score": 1485},
            ]

    rank_colors = {
        1: "text-transparent bg-clip-text bg-gradient-to-br from-blue-500 to-indigo-600",
        2: "text-gray-400 dark:text-gray-500", 3: "text-amber-500",
        4: "text-gray-300 dark:text-gray-600", 5: "text-gray-300 dark:text-gray-600",
    }
    html = '<div class="space-y-2">'
    for m in models:
        bg = "bg-gradient-to-r from-blue-50/50 to-indigo-50/50 dark:from-[#1e2330] dark:to-[#1a1b26]" if m["rank"] == 1 else "bg-white dark:bg-[#1e1e1e]"
        badge = '<span class="px-2 py-0.5 bg-gradient-to-r from-blue-500 to-indigo-500 text-white text-[9px] font-bold rounded shadow-sm">SOTA</span>' if m["rank"] == 1 else f'<span class="text-[11px] text-gray-400 font-mono">{m["score"]}</span>'
        html += f'''<a href="https://arena.ai/leaderboard" target="_blank" class="flex items-center justify-between p-3 rounded-xl border border-gray-200 dark:border-[#333] {bg} hover:shadow-md hover:border-gray-300 dark:hover:border-[#444] transition-all cursor-pointer group">
            <div class="flex items-center gap-3"><span class="text-[14px] font-black {rank_colors.get(m["rank"], "text-gray-300")} w-5">#{m["rank"]}</span><div><div class="font-semibold text-[13px] text-gray-900 dark:text-white group-hover:text-indigo-600 transition-colors">{m["name"]}</div><div class="text-[10px] text-gray-400">{m["org"]}</div></div></div>{badge}</a>'''
    html += '</div>'
    return html


def get_paper_html(paper: dict) -> str:
    link = paper.get("url", "")
    tag, tag_color = _classify_link(link)
    title_escaped = paper.get("title", "").replace("'", "\\'").replace('"', "&quot;")
    snippet = paper.get("content", "").replace("\n", " ")[:300].replace('"', "&quot;")
    return f'''<div class="paper-card p-5 bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2c2c2c] rounded-2xl flex flex-col hover:shadow-lg transition-all group" data-tag="{tag}">
        <div class="flex-1"><div class="mb-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold border {tag_color}">{tag}</span></div>
            <a href="{link}" target="_blank" class="text-[15px] font-bold text-gray-900 dark:text-gray-100 hover:text-indigo-600 block mb-2 font-serif line-clamp-2 leading-snug">{paper.get("title", "")}</a>
            <p class="text-[13px] text-gray-500 dark:text-gray-400 leading-relaxed mb-4 line-clamp-3">{paper.get("content", "")[:280]}...</p></div>
        <div class="pt-3 border-t border-gray-100 dark:border-[#2c2c2c] flex justify-between items-center">
            <div class="flex gap-3"><a href="{link}" target="_blank" class="text-[12px] font-medium text-gray-500 hover:text-gray-900 transition-colors">原文 ↗</a>
                <button onclick="openDeepReadModal('{title_escaped}','{link}')" class="text-[12px] font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 transition-colors flex items-center gap-1">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>AI 精读</button></div>
            <button onclick="toggleBookmark(this,event)" class="bookmark-btn text-gray-300 dark:text-gray-600 hover:text-amber-400 transition-colors" data-link="{link}" data-title="{title_escaped}" data-snippet="{snippet}" data-domain="{tag}">
                <svg class="w-4.5 h-4.5" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none"><path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg></button></div></div>'''


def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    topics = parse_topics()

    news_results = search_tavily("latest AI news Anthropic OpenAI Google DeepMind 2026", max_results=4, time_range="week")
    if not news_results:
        news_results = search_tavily("artificial intelligence breakthrough research 2026", max_results=4, time_range="month")
    news_html = '<div class="space-y-3">'
    if not news_results:
        news_html += '<p class="text-[12px] text-gray-400 py-4 text-center">暂无最新资讯</p>'
    for r in news_results:
        news_html += f'<a href="{r.get("url", "")}" target="_blank" class="block p-3.5 rounded-xl border border-gray-200 dark:border-[#333] hover:bg-gray-50 dark:hover:bg-[#252525] transition-all group"><h4 class="font-semibold text-[13px] text-gray-900 dark:text-white mb-1.5 group-hover:text-indigo-600 line-clamp-2">{r.get("title", "")}</h4><p class="text-[11px] text-gray-400 line-clamp-2">{r.get("content", "")[:200]}</p></a>'
    news_html += "</div>"

    print("Fetching SOTA models from arena.ai...")
    top_models_html = fetch_sota_models()

    print("Fetching conference deadlines from ccfddl...")
    conferences_html = fetch_ccf_deadlines()

    tabs_html = ""
    papers_html = ""
    for i, meta in enumerate(topics):
        tab_id = f"tab_{i}"
        active = "text-[#4f46e5] border-[#4f46e5] font-semibold" if i == 0 else "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
        tabs_html += f'\n<button id="btn-{tab_id}" onclick="switchTab(\'{tab_id}\')" data-query="{meta["query"]}" class="tab-btn whitespace-nowrap py-2 px-4 text-[14px] flex-shrink-0 focus:outline-none flex items-center transition-colors border-b-2 {active} -mb-px">{meta["name"]}</button>'

        hidden = "" if i == 0 else "hidden"
        papers_html += f'<div id="content-{tab_id}" class="tab-content {hidden}"><div class="grid grid-cols-1 md:grid-cols-2 gap-5 p-5">'
        results = search_tavily(meta["query"], max_results=8, include_domains=ACADEMIC_DOMAINS)
        if not results:
            papers_html += '<div class="col-span-full text-[13px] text-gray-500 py-10 text-center">今日暂无收录论文</div>'
        else:
            for r in results:
                papers_html += get_paper_html(r)
        papers_html += f'''<div class="col-span-full mt-2 flex justify-center pb-4"><button onclick="loadMorePapers('{tab_id}')" class="px-5 py-2 bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#333] hover:border-gray-300 text-gray-500 text-[12px] font-medium rounded-full transition-all shadow-sm flex items-center gap-2">发现更多优质内容 <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg></button></div>'''
        papers_html += "</div></div>"

    template_path = os.path.join(BASE_DIR, "template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    model_name = os.environ.get("OHMYAPI_MODEL_NAME", "gpt-5.4")
    final_html = (
        template
        .replace("<!-- {{DATE}} -->", date_str)
        .replace("<!-- {{TOP_MODELS}} -->", top_models_html)
        .replace("<!-- {{NEWS}} -->", news_html)
        .replace("<!-- {{CONFERENCES}} -->", conferences_html)
        .replace("<!-- {{TABS}} -->", tabs_html)
        .replace("<!-- {{PAPERS}} -->", papers_html)
        .replace("{{DEFAULT_MODEL}}", model_name)
    )

    reports_dir = os.path.join(BASE_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    out_path = os.path.join(reports_dir, f"daily_brief_{date_str}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_html)
    print(f"Report generated: {out_path}")


if __name__ == "__main__":
    main()
