"""Flask server for OpenClaw Academic Radar.

Serves generated HTML reports and provides API endpoints for
search, deep-read analysis, and multi-turn chat.
"""

import os
import glob
import json
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
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
OHMYAPI_KEY = os.environ.get("OHMYAPI_KEY", "")
GLM_API_KEY = os.environ.get("GLM_API_KEY", "")

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


def _classify_link(url: str) -> tuple[str, str]:
    """Return (tag_name, tag_tailwind_classes) for a URL."""
    lower = url.lower()
    for keyword, tag, color in TAG_RULES:
        if keyword in lower:
            return tag, color
    try:
        domain = lower.split("//")[1].split("/")[0].replace("www.", "")
        return domain.split(".")[0].capitalize(), DEFAULT_TAG_COLOR
    except Exception:
        return "Web", DEFAULT_TAG_COLOR


# ── Routes ──────────────────────────────────────────────────────


@app.route("/")
@app.route("/latest")
def index():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    html_files = sorted(
        glob.glob(os.path.join(REPORTS_DIR, "daily_brief_*.html")), reverse=True
    )
    if html_files:
        return send_file(html_files[0])
    return "No reports generated yet.", 404


@app.route("/<path:filename>")
def serve_report(filename):
    file_path = os.path.join(REPORTS_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    return "Not Found", 404


@app.route("/api/history")
def api_history():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    html_files = sorted(
        glob.glob(os.path.join(REPORTS_DIR, "daily_brief_*.html")), reverse=True
    )
    return jsonify(
        [
            {
                "filename": os.path.basename(f),
                "date": os.path.basename(f)
                .replace("daily_brief_", "")
                .replace(".html", ""),
            }
            for f in html_files
        ]
    )


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "")
    source = request.args.get("source", "all")

    if source == "academic":
        query += " (site:arxiv.org OR site:nips.cc OR site:icml.cc OR site:iclr.cc OR site:aclweb.org OR site:emnlp.org)"

    payload = json.dumps(
        {
            "api_key": TAVILY_KEY,
            "query": query,
            "search_depth": "advanced",
            "time_range": "month",
            "max_results": 8,
        }
    ).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=30).read()
        data = json.loads(resp).get("results", [])

        results = []
        for r in data:
            tag, tag_color = _classify_link(r.get("url", ""))
            results.append(
                {
                    "title": r.get("title", ""),
                    "link": r.get("url", ""),
                    "snippet": r.get("content", "").replace("\n", " ").strip()[:300],
                    "domain": tag,
                    "tag_color": tag_color,
                }
            )
        return jsonify(results)
    except Exception:
        return jsonify([])


@app.route("/api/deep-read")
def api_deep_read():
    title = request.args.get("title", "")
    url_param = request.args.get("url", "")
    prompt = (
        f"请作为一位资深的AI学术研究员，对该篇论文进行深度中文解析。\n\n"
        f"标题：{title}\n链接：{url_param}\n\n"
        f"请按以下结构使用 Markdown 输出：\n"
        f"### 🌟 核心总结\n### 🎯 研究背景\n### 💡 方法与创新\n### 📊 结论与启发"
    )
    content = _call_llm(
        [{"role": "user", "content": prompt}],
        request.args.get("url_ov", ""),
        request.args.get("key_ov", ""),
        request.args.get("model_ov", ""),
    )
    return jsonify({"content": content})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    req_data = request.json or {}
    messages = req_data.get("messages", [])

    if not any(m.get("role") == "system" for m in messages):
        messages.insert(
            0,
            {
                "role": "system",
                "content": (
                    "You are a helpful AI academic assistant. "
                    "Answer questions about papers accurately and concisely."
                ),
            },
        )

    content = _call_llm(
        messages,
        req_data.get("url_ov", ""),
        req_data.get("key_ov", ""),
        req_data.get("model_ov", ""),
    )
    return jsonify({"content": content})


# ── LLM Routing ─────────────────────────────────────────────────

MODEL_PROVIDERS = {
    "gpt-5.3-codex": {
        "base_url": "https://ohmyapi-2api.hf.space/v1",
        "env_key": "OHMYAPI_KEY",
    },
    "minimaxai/minimax-m2.5": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "env_key": "NVIDIA_API_KEY",
    },
    "glm-5": {
        "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
        "env_key": "GLM_API_KEY",
    },
}


def _call_llm(
    messages: list,
    url_ov: str = "",
    key_ov: str = "",
    model_ov: str = "",
) -> str:
    model_name = model_ov.strip() if model_ov and model_ov.strip() else "gpt-5.3-codex"

    provider = MODEL_PROVIDERS.get(model_name)
    if provider:
        base_url = provider["base_url"]
        api_key = os.environ.get(provider["env_key"], "")
    else:
        base_url = url_ov.strip().rstrip("/") if url_ov and url_ov.strip() else "https://api.openai.com/v1"
        api_key = key_ov.strip() if key_ov and key_ov.strip() else ""

    if not api_key:
        return f"⚠️ API Key 未配置。请在环境变量中设置对应的 Key，或在设置中配置自定义模型。"

    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.7,
            top_p=0.95,
            max_tokens=8192,
            stream=False,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return (
            f"调用大模型 API 失败。\n\n"
            f"**模型:** {model_name}\n"
            f"**URL:** {base_url}\n"
            f"**错误:** {str(e)}"
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
