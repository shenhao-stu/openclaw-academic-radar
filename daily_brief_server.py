"""Flask server for OpenClaw Academic Radar."""

import os
import glob
import json
import re
import subprocess
import urllib.request

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
from flask import Flask, request, jsonify, send_file
from openai import OpenAI


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks (including unclosed ones) from model output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"^.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()

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


OHMYAPI_BASE_URL = os.environ.get("OHMYAPI_BASE_URL", "https://api.openai.com/v1")
OHMYAPI_MODEL_NAME = os.environ.get("OHMYAPI_MODEL_NAME", "gpt-5.4")

MODEL_PROVIDERS = {
    OHMYAPI_MODEL_NAME: {"base_url": OHMYAPI_BASE_URL, "env_key": "OHMYAPI_KEY"},
}


def _get_llm_client(model_ov="", url_ov="", key_ov=""):
    model_name = model_ov.strip() if model_ov and model_ov.strip() else OHMYAPI_MODEL_NAME
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


def _normalize_url(url: str) -> str:
    """Normalize URLs — convert arXiv HTML variants to PDF for full-text extraction."""
    # arxiv.org/abs/XXXX or /html/XXXX → /pdf/XXXX (get the actual paper content)
    url = re.sub(r'arxiv\.org/(?:abs|html)/([^\s?#]+?)(?:\.html)?([?#]|$)', r'arxiv.org/pdf/\1.pdf\2', url)
    return url


def _is_pdf_url(url: str) -> bool:
    """Return True if the URL points to a PDF (by extension or known PDF-serving paths)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path.endswith(".pdf"):
        return True
    # arXiv /pdf/ path always serves PDF
    if "arxiv.org/pdf/" in url.lower():
        return True
    return False


def _parse_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from raw PDF bytes using PyMuPDF, with vision OCR fallback for image pages."""
    import base64 as b64mod
    from concurrent.futures import ThreadPoolExecutor, as_completed

    MIN_TEXT_CHARS = 80

    def _vision_ocr_page(pix_bytes: bytes) -> str:
        b64 = b64mod.b64encode(pix_bytes).decode("utf-8")
        try:
            client = OpenAI(base_url=VISION_BASE_URL, api_key=VISION_API_TOKEN)
            msgs = [{"role": "user", "content": [
                {"type": "text", "text": "Extract ALL text from this page. Output plain text only."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]}]
            resp = client.chat.completions.create(
                model=VISION_MODEL, messages=msgs, max_tokens=1536, temperature=0.1,
            )
            return _strip_think(resp.choices[0].message.content or "")
        except Exception as e:
            return f"[Vision error: {e}]"

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "[PyMuPDF not installed. Run: pip install pymupdf]"

    import io
    doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    total_pages = len(doc)
    max_pages = min(total_pages, 10)
    all_text = [""] * max_pages
    vision_tasks = {}

    for i in range(max_pages):
        page = doc[i]
        text = page.get_text("text").strip()
        if len(text) >= MIN_TEXT_CHARS:
            all_text[i] = f"--- Page {i+1} ---\n{text}"
        else:
            pix = page.get_pixmap(dpi=150)
            vision_tasks[i] = pix.tobytes("png")

    if vision_tasks:
        with ThreadPoolExecutor(max_workers=min(3, len(vision_tasks))) as pool:
            futures = {pool.submit(_vision_ocr_page, img): i for i, img in vision_tasks.items()}
            for fut in as_completed(futures):
                idx = futures[fut]
                all_text[idx] = f"--- Page {idx+1} (OCR) ---\n{fut.result()}"

    doc.close()
    return "\n\n".join(t for t in all_text if t)


def _fetch_pdf_url(url: str) -> str:
    """Download a PDF from a URL and extract its text via PyMuPDF."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            pdf_bytes = resp.read()
        text = _parse_pdf_bytes(pdf_bytes)
        return text if text else "[Empty PDF content]"
    except Exception as e:
        return f"[PDF fetch error: {e}]"


def _fetch_url_with_playwright(url: str) -> str:
    """Fetch and extract content from a URL.
    PDF URLs are downloaded and parsed with PyMuPDF.
    HTML pages are rendered with Playwright.
    """
    url = _normalize_url(url)
    if _is_pdf_url(url):
        return _fetch_pdf_url(url)
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

def _build_live_page(report_path: str) -> str:
    """Serve a report using the latest template.html with data from the report.

    Reports are generated from template.html with data injected into <main>.
    When template.html is updated (new JS, HTML changes), old reports become
    stale. This function extracts <main>...</main> from the report and injects
    it into the current template so all UI/JS changes are always reflected.
    """
    template_path = os.path.join(BASE_DIR, "template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    with open(report_path, "r", encoding="utf-8") as f:
        report = f.read()

    MAIN_OPEN = '<main class="max-w-[1400px]'
    MAIN_CLOSE = "</main>"

    report_main_start = report.find(MAIN_OPEN)
    report_main_end = report.find(MAIN_CLOSE, report_main_start)
    tmpl_main_start = template.find(MAIN_OPEN)
    tmpl_main_end = template.find(MAIN_CLOSE, tmpl_main_start)

    if all(x != -1 for x in (report_main_start, report_main_end, tmpl_main_start, tmpl_main_end)):
        report_main = report[report_main_start:report_main_end + len(MAIN_CLOSE)]
        result = template[:tmpl_main_start] + report_main + template[tmpl_main_end + len(MAIN_CLOSE):]
        date_str = os.path.basename(report_path).replace("daily_brief_", "").replace(".html", "")
        result = result.replace("<!-- {{DATE}} -->", date_str)
        result = result.replace("{{DEFAULT_MODEL}}", OHMYAPI_MODEL_NAME)
        # Inject report list for history navigation (live server uses /api/history,
        # but also embed it so the JS can read it without an extra fetch)
        files = sorted(glob.glob(os.path.join(REPORTS_DIR, "daily_brief_*.html")), reverse=True)
        report_list = json.dumps([
            {"filename": os.path.basename(f),
             "date": os.path.basename(f).replace("daily_brief_", "").replace(".html", "")}
            for f in files
        ])
        result = result.replace("<!-- {{REPORT_LIST_JSON}} -->", report_list)
        return result

    return report


@app.route("/")
@app.route("/latest")
def index():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, "daily_brief_*.html")), reverse=True)
    if not files:
        return "No reports yet.", 404
    return _build_live_page(files[0])


@app.route("/<path:filename>")
def serve_report(filename):
    fp = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(fp):
        return "Not Found", 404
    if filename.endswith(".html"):
        return _build_live_page(fp)
    return send_file(fp)


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
    """Fetch URL content: PDF URLs via PyMuPDF, HTML pages via Playwright."""
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"content": "", "error": "No URL provided"})
    normalized = _normalize_url(url)
    is_pdf = _is_pdf_url(normalized)
    content = _fetch_url_with_playwright(url)
    return jsonify({"content": content, "is_pdf": is_pdf, "url": normalized})


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
            messages=[{"role": "user", "content": "Reply with exactly one word: ok"}],
            max_tokens=16, temperature=0,
        )
        raw = resp.choices[0].message.content or ""
        clean = _strip_think(raw) or "ok"
        return jsonify({"ok": True, "model": model_name, "response": clean[:30]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


VISION_BASE_URL = os.environ.get("VISION_BASE_URL", "") or OHMYAPI_BASE_URL
VISION_MODEL = os.environ.get("VISION_MODEL", "") or OHMYAPI_MODEL_NAME
VISION_API_TOKEN = os.environ.get("VISION_API_TOKEN", "") or os.environ.get("OHMYAPI_KEY", "EMPTY")


def _resolve_vision(data: dict) -> tuple[str, str, str]:
    """Return (base_url, model, api_token) with optional client-side overrides."""
    url = (data.get("vision_url") or "").strip() or VISION_BASE_URL
    model = (data.get("vision_model") or "").strip() or VISION_MODEL
    token = (data.get("vision_token") or "").strip() or VISION_API_TOKEN
    return url, model, token


@app.route("/api/vision-test", methods=["POST"])
def api_vision_test():
    """Quick connectivity test — validates model name against server's model list."""
    data = request.json or {}
    url, model, token = _resolve_vision(data)
    try:
        client = OpenAI(base_url=url, api_key=token)
        available = client.models.list()
        served = [m.id for m in available.data]
        if model not in served:
            return jsonify({
                "ok": False,
                "error": f"Model '{model}' not found. Available: {', '.join(served)}",
            })
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=4, temperature=0,
        )
        reply = (resp.choices[0].message.content or "").strip()[:30]
        return jsonify({"ok": True, "model": model, "response": reply})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


@app.route("/api/vision", methods=["POST"])
def api_vision():
    """Process image via local vision model."""
    data = request.json or {}
    image_b64 = data.get("image", "")
    prompt = data.get("prompt", "Describe this image in detail. If it contains text, extract the text content.")
    if not image_b64:
        return jsonify({"content": "", "error": "No image data"})
    url, model, token = _resolve_vision(data)
    try:
        client = OpenAI(base_url=url, api_key=token)
        messages = [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
        ]}]
        resp = client.chat.completions.create(
            model=model, messages=messages, max_tokens=2048, temperature=0.3,
        )
        raw = resp.choices[0].message.content or ""
        return jsonify({"content": _strip_think(raw)})
    except Exception as e:
        return jsonify({"content": "", "error": f"Vision model error: {e}"})


@app.route("/api/parse-pdf", methods=["POST"])
def api_parse_pdf():
    """Parse PDF: accepts file upload or a JSON {url} to fetch remotely.
    Uses PyMuPDF for native text extraction, vision OCR fallback for image pages.
    """
    # Support JSON body with url field
    if request.is_json:
        data = request.json or {}
        url = data.get("url", "").strip()
        if url:
            content = _fetch_pdf_url(url)
            return jsonify({"content": content, "source": "url"})
        return jsonify({"content": "", "error": "No url provided in JSON body"})

    f = request.files.get("file")
    if not f:
        return jsonify({"content": "", "error": "No file uploaded"})

    vis_url_ov = (request.form.get("vision_url") or "").strip()
    vis_model_ov = (request.form.get("vision_model") or "").strip()
    vis_token_ov = (request.form.get("vision_token") or "").strip()

    # Override module-level vision settings if provided by client
    global VISION_BASE_URL, VISION_MODEL, VISION_API_TOKEN
    _orig = (VISION_BASE_URL, VISION_MODEL, VISION_API_TOKEN)
    if vis_url_ov:
        VISION_BASE_URL = vis_url_ov
    if vis_model_ov:
        VISION_MODEL = vis_model_ov
    if vis_token_ov:
        VISION_API_TOKEN = vis_token_ov

    try:
        pdf_bytes = f.read()
        content = _parse_pdf_bytes(pdf_bytes)
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"content": "", "error": str(e)[:300]})
    finally:
        VISION_BASE_URL, VISION_MODEL, VISION_API_TOKEN = _orig


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

    if not any(m.get("role") == "system" for m in msgs):
        msgs.insert(0, {"role": "system", "content": (
            "You are a helpful AI academic assistant. "
            "When web page content is appended to the user's message after '--- Web content from', "
            "use it as the primary source to answer the question. "
            "Never claim you cannot access URLs — if content is provided in the message, use it directly."
        )})

    return jsonify({"content": _call_llm(msgs, data.get("url_ov", ""), data.get("key_ov", ""), data.get("model_ov", ""))})


@app.route("/api/config-status")
def api_config_status():
    """Return which required env vars are configured (non-empty)."""
    env_vars = {
        "TAVILY_API_KEY": bool(os.environ.get("TAVILY_API_KEY", "").strip()),
        "OHMYAPI_KEY": bool(os.environ.get("OHMYAPI_KEY", "").strip()),
        "OHMYAPI_BASE_URL": os.environ.get("OHMYAPI_BASE_URL", "https://api.openai.com/v1"),
    }
    all_required_ok = env_vars["TAVILY_API_KEY"] and env_vars["OHMYAPI_KEY"]
    return jsonify({"configured": all_required_ok, "vars": env_vars})


@app.route("/api/update-config", methods=["POST"])
def api_update_config():
    """Write env vars to .env file and reload them into the process."""
    data = request.json or {}
    updates = data.get("vars", {})
    if not updates:
        return jsonify({"ok": False, "error": "No variables provided"})

    env_path = os.path.join(BASE_DIR, ".env")
    existing = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()

    for k, v in updates.items():
        v = str(v).strip()
        if v:
            existing[k] = v
            os.environ[k] = v

    with open(env_path, "w") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

    global TAVILY_KEY, OHMYAPI_BASE_URL, OHMYAPI_MODEL_NAME, MODEL_PROVIDERS
    global VISION_BASE_URL, VISION_MODEL, VISION_API_TOKEN
    TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "")
    OHMYAPI_BASE_URL = os.environ.get("OHMYAPI_BASE_URL", "https://api.openai.com/v1")
    OHMYAPI_MODEL_NAME = os.environ.get("OHMYAPI_MODEL_NAME", "gpt-5.4")
    MODEL_PROVIDERS.clear()
    MODEL_PROVIDERS[OHMYAPI_MODEL_NAME] = {"base_url": OHMYAPI_BASE_URL, "env_key": "OHMYAPI_KEY"}
    VISION_BASE_URL = os.environ.get("VISION_BASE_URL", "") or OHMYAPI_BASE_URL
    VISION_MODEL = os.environ.get("VISION_MODEL", "") or OHMYAPI_MODEL_NAME
    VISION_API_TOKEN = os.environ.get("VISION_API_TOKEN", "") or os.environ.get("OHMYAPI_KEY", "EMPTY")

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True, threaded=True)
