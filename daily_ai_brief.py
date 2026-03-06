"""Generate the daily AI Academic Radar HTML report.

Fetches papers from Tavily for each topic, renders them into
the HTML template, and writes the final report to reports/.
"""

import json
import os
import urllib.request
from datetime import datetime

import yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
    config = yaml.safe_load(f)

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

TAG_RULES = [
    ("arxiv",   "arXiv",   "bg-gray-100 text-gray-600 dark:bg-[#2c2c2c] dark:text-gray-400 border-gray-200 dark:border-[#333]"),
    ("neurips", "NeurIPS", "bg-purple-50 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400 border-purple-100 dark:border-purple-800/30"),
    ("nips",    "NeurIPS", "bg-purple-50 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400 border-purple-100 dark:border-purple-800/30"),
    ("icml",    "ICML",    "bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400 border-blue-100 dark:border-blue-800/30"),
    ("iclr",    "ICLR",    "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30"),
    ("emnlp",   "ACL",     "bg-rose-50 text-rose-600 dark:bg-rose-900/20 dark:text-rose-400 border-rose-100 dark:border-rose-800/30"),
    ("acl",     "ACL",     "bg-rose-50 text-rose-600 dark:bg-rose-900/20 dark:text-rose-400 border-rose-100 dark:border-rose-800/30"),
    ("github",  "GitHub",  "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700"),
    ("zhihu",   "Zhihu",   "bg-blue-50 text-blue-500 dark:bg-blue-900/20 dark:text-blue-400 border-blue-100 dark:border-blue-800/30"),
    ("csdn",    "CSDN",    "bg-orange-50 text-orange-600 dark:bg-orange-900/20 dark:text-orange-400 border-orange-100 dark:border-orange-800/30"),
    ("medium",  "Medium",  "bg-stone-100 text-stone-800 dark:bg-stone-800 dark:text-stone-300 border-stone-200 dark:border-stone-700"),
]
DEFAULT_TAG_COLOR = "bg-gray-100 text-gray-600 dark:bg-[#2c2c2c] dark:text-gray-400 border-gray-200 dark:border-[#333]"

TOPICS = [
    {"name": "🚀 推理与服务优化", "query": "LLM Inference RAG System optimization", "icon": "🚀"},
    {"name": "🛡️ 系统安全性", "query": "LLM Agent Security jailbreak alignment", "icon": "🛡️"},
    {"name": "🧠 记忆与强化学习", "query": "LLM Memory Reinforcement Learning RLHF", "icon": "🧠"},
    {"name": "📡 通信效率优化", "query": "LLM Communication Distributed Training efficiency", "icon": "📡"},
    {"name": "🎵 音频大模型与声码器", "query": "Audio LLM Vocoder Speech Generation", "icon": "🎵"},
]


def _classify_link(url: str) -> tuple:
    lower = url.lower()
    for keyword, tag, color in TAG_RULES:
        if keyword in lower:
            return tag, color
    try:
        domain = lower.split("//")[1].split("/")[0].replace("www.", "")
        return domain.split(".")[0].capitalize(), DEFAULT_TAG_COLOR
    except Exception:
        return "Web", DEFAULT_TAG_COLOR


def search_tavily(query: str, max_results: int = 8, time_range: str = "month") -> list:
    payload = json.dumps({
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "include_images": False,
        "include_answer": False,
        "max_results": max_results,
        "time_range": time_range,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8")).get("results", [])
    except Exception as e:
        print(f"Tavily API error: {e}")
        return []


def get_paper_html(paper: dict) -> str:
    link = paper.get("url", "")
    tag, tag_color = _classify_link(link)
    title_escaped = paper.get("title", "").replace("'", "\\'").replace('"', "&quot;")
    snippet = paper.get("content", "").replace("\n", " ")[:300].replace('"', "&quot;")

    return f'''
    <div class="p-6 bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2c2c2c] rounded-2xl flex flex-col hover:shadow-lg transition-all group">
        <div class="flex-1">
            <div class="mb-4">
                <span class="px-2 py-0.5 rounded text-[10.5px] font-bold border {tag_color}">{tag}</span>
            </div>
            <a href="{link}" target="_blank" class="text-[16px] font-bold text-gray-900 dark:text-gray-100 hover:text-indigo-600 block mb-3 font-serif line-clamp-2 leading-snug">{paper.get("title", "")}</a>
            <p class="text-[13.5px] text-gray-600 dark:text-gray-400 leading-relaxed mb-5 line-clamp-4">{paper.get("content", "")[:300]}...</p>
        </div>
        <div class="pt-4 border-t border-gray-100 dark:border-[#2c2c2c] flex justify-between items-center">
            <div class="flex gap-4">
                <a href="{link}" target="_blank" class="text-[13px] font-bold text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors flex items-center gap-1">原文 ↗</a>
                <button onclick="openDeepReadModal('{title_escaped}', '{link}')" class="text-[13px] font-bold text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 transition-colors flex items-center gap-1">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg> AI 精读
                </button>
            </div>
            <button onclick="toggleBookmark(this, event)" class="bookmark-btn text-gray-300 dark:text-gray-600 hover:text-amber-400 transition-colors" data-link="{link}" data-title="{title_escaped}" data-snippet="{snippet}" data-domain="{tag}">
                <svg class="w-5 h-5" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none"><path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path></svg>
            </button>
        </div>
    </div>
    '''


# ── Static content generators ───────────────────────────────────

TOP_MODELS_HTML = '''
<div class="space-y-3">
    <div class="flex items-center justify-between p-3.5 rounded-xl border border-gray-200 dark:border-[#333] bg-gradient-to-r from-blue-50/50 to-indigo-50/50 dark:from-[#1e2330] dark:to-[#1a1b26] hover:shadow-md transition">
        <div class="flex items-center gap-4">
            <span class="text-[15px] font-black text-transparent bg-clip-text bg-gradient-to-br from-blue-500 to-indigo-600 w-5">#1</span>
            <div><div class="font-bold text-[14px] text-gray-900 dark:text-white">claude-opus-4-6</div><div class="text-[11px] text-gray-500 font-medium">Anthropic</div></div>
        </div>
        <span class="px-2 py-0.5 bg-gradient-to-r from-blue-500 to-indigo-500 text-white text-[10px] font-bold rounded shadow-sm">SOTA</span>
    </div>
    <div class="flex items-center justify-between p-3.5 rounded-xl border border-gray-200 dark:border-[#333] bg-white dark:bg-[#1e1e1e] hover:shadow-md transition">
        <div class="flex items-center gap-4"><span class="text-[15px] font-black text-gray-400 dark:text-gray-500 w-5">#2</span><div><div class="font-bold text-[14px] text-gray-900 dark:text-white">claude-opus-4-6-thinking</div><div class="text-[11px] text-gray-500 font-medium">Anthropic</div></div></div>
    </div>
    <div class="flex items-center justify-between p-3.5 rounded-xl border border-gray-200 dark:border-[#333] bg-white dark:bg-[#1e1e1e] hover:shadow-md transition">
        <div class="flex items-center gap-4"><span class="text-[15px] font-black text-amber-500 w-5">#3</span><div><div class="font-bold text-[14px] text-gray-900 dark:text-white">gemini-3.1-pro-preview</div><div class="text-[11px] text-gray-500 font-medium">Google</div></div></div>
    </div>
    <div class="flex items-center justify-between p-3.5 rounded-xl border border-gray-200 dark:border-[#333] bg-white dark:bg-[#1e1e1e] hover:shadow-md transition">
        <div class="flex items-center gap-4"><span class="text-[15px] font-black text-gray-300 dark:text-gray-600 w-5">#4</span><div><div class="font-bold text-[14px] text-gray-900 dark:text-white">grok-4.20-beta1</div><div class="text-[11px] text-gray-500 font-medium">xAI</div></div></div>
    </div>
</div>
'''

CONFERENCES_HTML = '''
<div class="grid grid-cols-2 gap-3">
    <a href="https://iccbr2026.org/" target="_blank" class="p-3.5 rounded-xl border border-gray-200 dark:border-[#333] bg-white dark:bg-[#1e1e1e] hover:shadow-md transition group">
        <div class="flex items-center gap-2 mb-3"><span class="font-black text-[15px] text-gray-900 dark:text-gray-100 group-hover:text-indigo-600 transition-colors">ICCBR</span><span class="px-1.5 py-0.5 bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400 rounded text-[10px] font-bold">CCF-B</span></div>
        <div class="text-[11px] text-gray-500 font-medium mb-1.5">截止: 2026-03-20</div><div class="text-[13px] font-bold text-red-500">余 15 天</div>
    </a>
    <a href="https://ppsn2026.org/" target="_blank" class="p-3.5 rounded-xl border border-gray-200 dark:border-[#333] bg-white dark:bg-[#1e1e1e] hover:shadow-md transition group">
        <div class="flex items-center gap-2 mb-3"><span class="font-black text-[15px] text-gray-900 dark:text-gray-100 group-hover:text-indigo-600 transition-colors">PPSN</span><span class="px-1.5 py-0.5 bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400 rounded text-[10px] font-bold">CCF-B</span></div>
        <div class="text-[11px] text-gray-500 font-medium mb-1.5">截止: 2026-03-28</div><div class="text-[13px] font-bold text-red-500">余 23 天</div>
    </a>
    <a href="https://nips.cc/" target="_blank" class="p-3.5 rounded-xl border border-gray-200 dark:border-[#333] bg-white dark:bg-[#1e1e1e] hover:shadow-md transition group">
        <div class="flex items-center gap-2 mb-3"><span class="font-black text-[15px] text-gray-900 dark:text-gray-100 group-hover:text-indigo-600 transition-colors">NeurIPS</span><span class="px-1.5 py-0.5 bg-purple-50 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400 rounded text-[10px] font-bold">CCF-A</span></div>
        <div class="text-[11px] text-gray-500 font-medium mb-1.5">截止: 2026-05-07</div><div class="text-[13px] font-bold text-orange-500">余 62 天</div>
    </a>
    <a href="https://2026.emnlp.org/" target="_blank" class="p-3.5 rounded-xl border border-gray-200 dark:border-[#333] bg-white dark:bg-[#1e1e1e] hover:shadow-md transition group">
        <div class="flex items-center gap-2 mb-3"><span class="font-black text-[15px] text-gray-900 dark:text-gray-100 group-hover:text-indigo-600 transition-colors">EMNLP</span><span class="px-1.5 py-0.5 bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400 rounded text-[10px] font-bold">CCF-B</span></div>
        <div class="text-[11px] text-gray-500 font-medium mb-1.5">截止: 2026-05-25</div><div class="text-[13px] font-bold text-orange-500">余 81 天</div>
    </a>
</div>
'''


def main():
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Fetch news
    news_results = search_tavily(
        "AI startup fund release OR AI new model OR Anthropic OR OpenAI",
        max_results=4, time_range="day"
    )
    news_html = '<div class="space-y-4">'
    for r in news_results:
        news_html += f'''
        <a href="{r.get("url", "")}" target="_blank" class="block p-4 rounded-xl border border-claude-border dark:border-[#333] hover:bg-gray-50 dark:hover:bg-[#252525] transition-all group">
            <h4 class="font-bold text-[14px] text-claude-text dark:text-claude-darkText mb-2 group-hover:text-indigo-600 line-clamp-2">{r.get("title", "")}</h4>
            <p class="text-[12.5px] text-claude-muted line-clamp-2">{r.get("content", "")}</p>
        </a>'''
    news_html += "</div>"

    # Build tabs and paper grids
    tabs_html = ""
    papers_html = ""

    for i, meta in enumerate(TOPICS):
        tab_id = f"tab_{i}"
        active_cls = "text-[#4f46e5] border-[#4f46e5] font-semibold" if i == 0 else "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"

        tabs_html += f'''
        <button id="btn-{tab_id}" onclick="switchTab('{tab_id}')" data-query="{meta["query"]}" class="tab-btn whitespace-nowrap py-2 px-3 text-[13px] flex-shrink-0 focus:outline-none flex items-center transition-colors border-b-2 {active_cls} -mb-px">{meta["name"]}</button>'''

        hidden = "" if i == 0 else "hidden"
        papers_html += f'<div id="content-{tab_id}" class="tab-content {hidden}"><div class="grid grid-cols-1 md:grid-cols-2 gap-5 p-5">'

        query = f'{meta["query"]} (site:arxiv.org OR site:nips.cc OR site:icml.cc OR site:iclr.cc OR site:aclweb.org OR site:emnlp.org)'
        results = search_tavily(query, max_results=8)

        if not results:
            papers_html += '<div class="col-span-full text-[13px] text-gray-500 py-10 text-center">今日暂无收录论文</div>'
        else:
            for r in results:
                papers_html += get_paper_html(r)

        papers_html += f'''
        <div class="col-span-full mt-2 flex justify-center pb-4">
            <button onclick="document.getElementById('search-source-filter').value='all'; document.getElementById('filter-current-text').innerText='泛科技检索'; searchCustomTopic('{tab_id}');" class="px-6 py-2.5 bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#333] hover:border-gray-300 dark:hover:border-[#444] text-gray-600 dark:text-gray-300 text-[13px] font-medium rounded-full transition-all shadow-sm flex items-center gap-2">
                发现更多优质内容
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
            </button>
        </div>'''
        papers_html += "</div></div>"

    # Read template and render
    template_path = os.path.join(BASE_DIR, "template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    final_html = (
        template
        .replace("<!-- {{DATE}} -->", date_str)
        .replace("<!-- {{TOP_MODELS}} -->", TOP_MODELS_HTML)
        .replace("<!-- {{NEWS}} -->", news_html)
        .replace("<!-- {{CONFERENCES}} -->", CONFERENCES_HTML)
        .replace("<!-- {{TABS}} -->", tabs_html)
        .replace("<!-- {{PAPERS}} -->", papers_html)
    )

    reports_dir = os.path.join(BASE_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    out_path = os.path.join(reports_dir, f"daily_brief_{date_str}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_html)

    print(f"Report generated at {out_path}")


if __name__ == "__main__":
    main()
