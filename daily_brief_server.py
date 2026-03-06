"""Flask server for OpenClaw Academic Radar."""

import os
import glob
import json
import subprocess
import urllib.request

import yaml
from flask import Flask, request, jsonify, send_file
from openai import OpenAI

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
    config = yaml.safe_load(f)

PORT = config["server"]["port"]
REPORTS_DIR = os.path.join(BASE_DIR, config["paths"]["reports_dir"])
TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "")

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


def _classify_link(url: str) -> tuple[str, str]:
    lower = url.lower()
    for kw, tag, color in TAG_RULES:
        if kw in lower:
            return tag, color
    try:
        domain = lower.split("//")[1].split("/")[0].replace("www.", "")
        return domain.split(".")[0].capitalize(), DEFAULT_TAG_COLOR
    except Exception:
        return "Web", DEFAULT_TAG_COLOR


MODEL_PROVIDERS = {
    "gpt-5.4": {"base_url": "https://ohmyapi-2api.hf.space/v1", "env_key": "OHMYAPI_KEY"},
}


def _get_llm_client(model_ov="", url_ov="", key_ov=""):
    model_name = model_ov.strip() if model_ov and model_ov.strip() else "gpt-5.4"
    provider = MODEL_PROVIDERS.get(model_name)
    if provider:
        base_url = provider["base_url"]
        api_key = os.environ.get(provider["env_key"], "")
    else:
        base_url = url_ov.strip().rstrip("/") if url_ov and url_ov.strip() else "https://api.openai.com/v1"
        api_key = key_ov.strip() if key_ov and key_ov.strip() else ""
    return model_name, base_url, api_key


def _call_llm(messages: list, url_ov="", key_ov="", model_ov="") -> str:
    model_name, base_url, api_key = _get_llm_client(model_ov, url_ov, key_ov)
    if not api_key:
        return "⚠️ API Key not configured. Set the corresponding environment variable or add a custom model in Settings."
    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        completion = client.chat.completions.create(
            model=model_name, messages=messages, temperature=0.7, top_p=0.95, max_tokens=8192, stream=False
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"LLM API Error.\n\n**Model:** {model_name}\n**URL:** {base_url}\n**Error:** {e}"


def _fetch_url_with_playwright(url: str) -> str:
    """Use Playwright to fetch and extract text from a URL."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if not resp or not resp.ok:
                browser.close()
                return f"[Error: HTTP {resp.status if resp else 'unknown'}]"
            page.wait_for_timeout(2000)
            text = page.evaluate("""() => {
                document.querySelectorAll('script,style,nav,footer,iframe,noscript').forEach(el => el.remove());
                return document.body.innerText.replace(/\\n\\s*\\n/g, '\\n').trim();
            }""")
            browser.close()
            return text[:12000] if text else "[Empty page content]"
    except Exception as e:
        return f"[Playwright error: {e}]"


# ── Routes ──

@app.route("/")
@app.route("/latest")
def index():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, "daily_brief_*.html")), reverse=True)
    return send_file(files[0]) if files else ("No reports yet.", 404)


@app.route("/<path:filename>")
def serve_report(filename):
    fp = os.path.join(REPORTS_DIR, filename)
    return send_file(fp) if os.path.exists(fp) else ("Not Found", 404)


@app.route("/api/history")
def api_history():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, "daily_brief_*.html")), reverse=True)
    return jsonify([{"filename": os.path.basename(f), "date": os.path.basename(f).replace("daily_brief_", "").replace(".html", "")} for f in files])


ACADEMIC_DOMAINS = ["arxiv.org", "nips.cc", "neurips.cc", "icml.cc", "iclr.cc", "aclweb.org", "openreview.net"]


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "")
    source = request.args.get("source", "all")
    max_results = min(20, max(8, int(request.args.get("max_results", 8))))
    if not TAVILY_KEY:
        return jsonify({"error": "TAVILY_API_KEY not configured", "results": []}), 500
    body = {
        "api_key": TAVILY_KEY, "query": query,
        "search_depth": "advanced", "time_range": "month", "max_results": max_results,
    }
    if source == "academic":
        body["include_domains"] = ACADEMIC_DOMAINS
    try:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request("https://api.tavily.com/search", data=payload, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=30).read()
        data = json.loads(resp)
        if "detail" in data:
            return jsonify({"error": str(data["detail"]), "results": []}), 400
        results = []
        for r in data.get("results", []):
            tag, tag_color = _classify_link(r.get("url", ""))
            results.append({"title": r.get("title", ""), "link": r.get("url", ""), "snippet": r.get("content", "").replace("\n", " ").strip()[:300], "domain": tag, "tag_color": tag_color})
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)[:200], "results": []}), 500


@app.route("/api/web-fetch", methods=["POST"])
def api_web_fetch():
    """Fetch URL content using Playwright for web search feature."""
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"content": "", "error": "No URL provided"})
    content = _fetch_url_with_playwright(url)
    return jsonify({"content": content})


@app.route("/api/test-connection", methods=["POST"])
def api_test_connection():
    """Test LLM API connectivity."""
    data = request.json or {}
    model_name, base_url, api_key = _get_llm_client(
        data.get("model", ""), data.get("url", ""), data.get("key", "")
    )
    if not api_key:
        return jsonify({"ok": False, "error": "API Key is empty"})
    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Say 'ok' in one word."}],
            max_tokens=10, temperature=0,
        )
        return jsonify({"ok": True, "model": model_name, "response": resp.choices[0].message.content[:50]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


@app.route("/api/deep-read")
def api_deep_read():
    title = request.args.get("title", "")
    url_param = request.args.get("url", "")
    web_search = request.args.get("web_search", "false") == "true"

    extra_context = ""
    if web_search and url_param:
        extra_context = _fetch_url_with_playwright(url_param)
        if extra_context and not extra_context.startswith("["):
            extra_context = f"\n\n--- 以下是从论文页面抓取的内容 ---\n{extra_context[:6000]}"
        else:
            extra_context = ""

    prompt = f"请作为资深AI学术研究员，深度中文解析该论文。\n\n标题：{title}\n链接：{url_param}{extra_context}\n\n请按以下结构输出Markdown：\n### 🌟 核心总结\n### 🎯 研究背景\n### 💡 方法与创新\n### 📊 结论与启发"
    return jsonify({"content": _call_llm(
        [{"role": "user", "content": prompt}],
        request.args.get("url_ov", ""), request.args.get("key_ov", ""), request.args.get("model_ov", ""),
    )})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json or {}
    msgs = data.get("messages", [])
    web_search = data.get("web_search", False)

    if not any(m.get("role") == "system" for m in msgs):
        msgs.insert(0, {"role": "system", "content": "You are a helpful AI academic assistant. Answer questions about papers accurately."})

    if web_search and msgs:
        last_msg = msgs[-1].get("content", "")
        import re
        urls = re.findall(r'https?://[^\s<>"\']+', last_msg)
        if urls:
            fetched = _fetch_url_with_playwright(urls[0])
            if fetched and not fetched.startswith("["):
                msgs[-1]["content"] += f"\n\n--- Web content from {urls[0]} ---\n{fetched[:6000]}"

    return jsonify({"content": _call_llm(msgs, data.get("url_ov", ""), data.get("key_ov", ""), data.get("model_ov", ""))})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
