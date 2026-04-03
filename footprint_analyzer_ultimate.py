import hashlib
import json
import re
from collections import Counter
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Comment
from flask import Flask, render_template_string, request

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

HTML_TEMPLATE = """
<!doctype html>
<html lang="uk">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Footprint Analyzer Ultimate</title>
    <style>
        * { box-sizing: border-box; }
        body { margin:0; font-family: Arial, sans-serif; background:#0f172a; color:#e2e8f0; }
        .wrap { max-width: 1580px; margin: 0 auto; padding: 24px; }
        .card { background:#111827; border:1px solid #1f2937; border-radius:16px; padding:20px; margin-bottom:18px; }
        .grid-2 { display:grid; grid-template-columns: 1fr 1fr; gap:16px; }
        .grid-3 { display:grid; grid-template-columns: repeat(3, 1fr); gap:16px; }
        .grid-4 { display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; }
        .field { margin-bottom:14px; }
        label { display:block; margin-bottom:8px; color:#cbd5e1; font-weight:700; }
        input[type="url"], input[type="file"] {
            width:100%; padding:12px 14px; border-radius:12px; border:1px solid #334155;
            background:#0b1220; color:#e2e8f0;
        }
        button {
            background:#2563eb; border:none; color:#fff; padding:12px 18px; border-radius:12px;
            font-weight:700; cursor:pointer;
        }
        button:hover { background:#1d4ed8; }
        .muted { color:#94a3b8; }
        .error {
            background:#450a0a; border:1px solid #991b1b; color:#fecaca;
            padding:12px 14px; border-radius:12px; margin-bottom:16px;
        }
        .stat { background:#0b1220; border:1px solid #334155; border-radius:14px; padding:14px; }
        .stat .n { font-size:26px; font-weight:800; margin-top:6px; }
        .section-title { font-size:20px; margin:6px 0 14px; }
        .sub-title { font-size:16px; margin:0 0 12px; }
        .chips { display:flex; flex-wrap:wrap; gap:8px; }
        .chip {
            border-radius:999px; padding:7px 10px; font-size:13px; border:1px solid #334155;
            background:#1e293b; word-break:break-word;
        }
        .chip-yellow { background:#3f2f00; border-color:#ca8a04; color:#fde68a; }
        .chip-green { background:#052e16; border-color:#166534; color:#bbf7d0; }
        .chip-red { background:#3f0d12; border-color:#b91c1c; color:#fecaca; }
        .chip-blue { background:#172554; border-color:#1d4ed8; color:#bfdbfe; }
        .issue { border-left:4px solid #ea580c; padding-left:14px; margin-bottom:22px; }
        .sev-high { color:#fecaca; font-weight:700; }
        .sev-mid { color:#fde68a; font-weight:700; }
        .sev-low { color:#86efac; font-weight:700; }
        ul.clean { margin:0; padding-left:20px; }
        ul.clean li { margin-bottom:8px; }
        pre {
            white-space:pre-wrap; word-break:break-word; background:#020617;
            border:1px solid #1e293b; padding:14px; border-radius:12px; overflow:auto;
        }
        .paragraph {
            white-space: pre-wrap;
            line-height: 1.6;
            color: #dbe4f0;
        }
        .divider { height:1px; background:#1f2937; margin:18px 0; }
        .banner {
            background:#0b1220; border:1px solid #334155; border-radius:14px; padding:16px;
        }
        @media (max-width: 980px) {
            .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
<div class="wrap">
    <h1>Footprint Analyzer Ultimate</h1>
    <p class="muted">Максимально жорстка і логічна версія: відділяє реальні кастомні футпрінти від WordPress/плагін шуму, не плутає Yoast з темою, і пояснює результат людською мовою.</p>

    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}

    <form method="post" enctype="multipart/form-data" class="card">
        <div class="grid-2">
            <div>
                <h2>A</h2>
                <div class="field">
                    <label>URL A</label>
                    <input type="url" name="url_a" placeholder="https://example.com">
                </div>
                <div class="field">
                    <label>HTML файл A</label>
                    <input type="file" name="file_a" accept=".html,.htm,.txt">
                </div>
            </div>
            <div>
                <h2>B</h2>
                <div class="field">
                    <label>URL B</label>
                    <input type="url" name="url_b" placeholder="https://example.org">
                </div>
                <div class="field">
                    <label>HTML файл B</label>
                    <input type="file" name="file_b" accept=".html,.htm,.txt">
                </div>
            </div>
        </div>
        <button type="submit">Запустити аналіз</button>
    </form>

    {% if result %}
        <div class="card">
            <div class="section-title">Підсумок</div>
            <div class="grid-4">
                <div class="stat"><div>Загальна схожість</div><div class="n">{{ result.similarity }}%</div></div>
                <div class="stat"><div>Ризик спільного шаблону</div><div class="n">{{ result.template_risk }}%</div></div>
                <div class="stat"><div>Реальних проблем</div><div class="n">{{ result.real_issue_count }}</div></div>
                <div class="stat"><div>Шуму / типового WP</div><div class="n">{{ result.noise_count }}</div></div>
            </div>
        </div>

        <div class="grid-2">
            <div class="card"><div class="sub-title">Джерело A</div><div class="muted">{{ result.label_a }}</div></div>
            <div class="card"><div class="sub-title">Джерело B</div><div class="muted">{{ result.label_b }}</div></div>
        </div>

        <div class="card">
            <div class="section-title">Нормальний висновок</div>
            <div class="paragraph">{{ result.human_summary }}</div>
        </div>

        <div class="grid-2">
            <div class="card">
                <div class="section-title">Що реально палиться</div>
                {% if result.real_issues %}
                    {% for issue in result.real_issues %}
                        <div class="issue">
                            <div class="sub-title">{{ issue.title }}</div>
                            <div class="{{ issue.level_class }}">{{ issue.level }}</div>
                            <div class="divider"></div>
                            <div class="paragraph">{{ issue.explanation }}</div>
                            <div class="divider"></div>
                            <div><strong>Що саме знайдено:</strong></div>
                            <div class="chips" style="margin-top:10px;">
                                {% for item in issue.matches %}
                                    <span class="chip chip-yellow">{{ item }}</span>
                                {% endfor %}
                            </div>
                            {% if issue.preview_a or issue.preview_b %}
                            <div class="grid-2" style="margin-top:14px;">
                                {% if issue.preview_a %}
                                <div>
                                    <div class="sub-title">Фрагмент A</div>
                                    <pre>{{ issue.preview_a }}</pre>
                                </div>
                                {% endif %}
                                {% if issue.preview_b %}
                                <div>
                                    <div class="sub-title">Фрагмент B</div>
                                    <pre>{{ issue.preview_b }}</pre>
                                </div>
                                {% endif %}
                            </div>
                            {% endif %}
                            <div class="divider"></div>
                            <div><strong>Що робити:</strong></div>
                            <ul class="clean" style="margin-top:10px;">
                                {% for step in issue.steps %}
                                <li>{{ step }}</li>
                                {% endfor %}
                            </ul>
                        </div>
                    {% endfor %}
                {% else %}
                    <div class="muted">Сильних кастомних збігів не знайдено.</div>
                {% endif %}
            </div>

            <div class="card">
                <div class="section-title">Що можна ігнорити як шум</div>
                {% if result.noise_issues %}
                    {% for issue in result.noise_issues %}
                        <div class="issue" style="border-left-color:#475569;">
                            <div class="sub-title">{{ issue.title }}</div>
                            <div class="{{ issue.level_class }}">{{ issue.level }}</div>
                            <div class="divider"></div>
                            <div class="paragraph">{{ issue.explanation }}</div>
                            <div class="divider"></div>
                            <div class="chips">
                                {% for item in issue.matches %}
                                    <span class="chip chip-blue">{{ item }}</span>
                                {% endfor %}
                            </div>
                        </div>
                    {% endfor %}
                {% else %}
                    <div class="muted">Шумових збігів майже немає.</div>
                {% endif %}
            </div>
        </div>

        <div class="grid-2">
            <div class="card">
                <div class="section-title">Порядок виправлень</div>
                <ul class="clean">
                    {% for item in result.fix_priority %}
                    <li>{{ item }}</li>
                    {% endfor %}
                </ul>
            </div>
            <div class="card">
                <div class="section-title">Найважливіші збіги</div>
                <ul class="clean">
                    {% for item in result.top_matches %}
                    <li>{{ item }}</li>
                    {% endfor %}
                </ul>
            </div>
        </div>

        <div class="card">
            <div class="section-title">Сирий short summary</div>
            <div class="grid-2">
                <div><pre>{{ result.short_a }}</pre></div>
                <div><pre>{{ result.short_b }}</pre></div>
            </div>
        </div>
    {% endif %}
</div>
</body>
</html>
"""

NOISE_ID_PATTERNS = [
    "wp-", "global-styles", "classic-theme-styles", "emoji", "jet-", "cookie", "cky-",
    "fast-vid", "menu-item-", "cn-", "wp-block-library"
]

NOISE_COMMENTS = [
    "yoast seo plugin",
    "this site is optimized with the yoast seo plugin"
]

NOISE_META_PREFIXES = [
    "og:type=website",
    "twitter:card=summary_large_image",
    "robots=index, follow"
]

def normalize_text(value):
    return re.sub(r"\s+", " ", (value or "").strip())

def normalize_urlish(value):
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return "%s%s" % (parsed.netloc.lower(), parsed.path.rstrip("/") or "/")
    return value.lower()

def short_hash(text):
    text = normalize_text(text)
    if not text:
        return ""
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:14]

def safe_preview(text, size=650):
    text = normalize_text(text)
    if len(text) > size:
        return text[:size] + " ..."
    return text

def safe_set(value):
    if value is None:
        return set()
    if isinstance(value, set):
        return value
    if isinstance(value, (list, tuple)):
        return set(value)
    return set([str(value)])

def is_noise_id(value):
    v = value.lower()
    return any(x in v for x in NOISE_ID_PATTERNS)

def is_noise_comment(value):
    v = value.lower()
    return any(x in v for x in NOISE_COMMENTS)

def is_noise_meta(value):
    v = value.lower()
    return any(v.startswith(x) for x in NOISE_META_PREFIXES)

def read_uploaded_file(file_storage):
    if not file_storage or not file_storage.filename:
        return None, None
    raw = file_storage.read()
    return raw.decode("utf-8", errors="ignore"), file_storage.filename

def fetch_url(url):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; HumanFootprintAnalyzerUltimate/1.0)"}
    resp = requests.get(url, timeout=25, headers=headers, allow_redirects=True)
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    return resp.text, resp.url

def get_input_side(url_value, file_storage, side_name):
    if (url_value or "").strip():
        html_text, final_url = fetch_url(url_value.strip())
        return html_text, "%s: %s" % (side_name, final_url), final_url
    file_text, filename = read_uploaded_file(file_storage)
    if file_text:
        return file_text, "%s: %s" % (side_name, filename), None
    raise ValueError("Для %s потрібно вказати URL або завантажити HTML файл." % side_name)

def extract_ids(soup):
    out = set()
    for tag in soup.find_all(True):
        v = tag.get("id")
        if v:
            out.add(normalize_text(v).lower())
    return out

def extract_classes(soup):
    out = set()
    for tag in soup.find_all(True):
        for c in tag.get("class", []):
            c = normalize_text(c).lower()
            if c:
                out.add(c)
    return out

def extract_theme_hints(html, soup):
    direct_theme = set()
    theme_assets = set()
    plugin_comments = set()

    low = html.lower()
    for m in re.findall(r"/wp-content/themes/([a-zA-Z0-9_\-]+)/", low):
        direct_theme.add("wp-theme:%s" % m)

    generator = soup.find("meta", attrs={"name": re.compile("^generator$", re.I)})
    if generator and generator.get("content"):
        content = normalize_text(generator.get("content"))
        if content:
            direct_theme.add("generator:%s" % content)

    for tag in soup.find_all(["script", "link"]):
        src = (tag.get("src") or tag.get("href") or "").lower()
        if "/themes/" in src:
            theme_assets.add("asset:%s" % normalize_urlish(src))

    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        text = normalize_text(str(c))
        if text and is_noise_comment(text):
            plugin_comments.add(text)

    return {
        "direct_theme": direct_theme,
        "theme_assets": theme_assets,
        "plugin_comments": plugin_comments,
    }

def extract_important_meta(soup):
    out = set()
    allowed = {"generator", "description", "og:site_name", "twitter:card", "robots", "theme-color", "og:type"}
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or meta.get("http-equiv") or "").strip().lower()
        content = normalize_text(meta.get("content") or "")
        if name and content and name in allowed:
            out.add("%s=%s" % (name, safe_preview(content, 120)))
    return out

def extract_comments(html):
    out = set()
    for m in re.findall(r"<!--(.*?)-->", html, flags=re.S):
        text = normalize_text(m)
        if text:
            out.add(safe_preview(text, 160))
    return out

def extract_forms(soup):
    forms = set()
    signatures = set()
    for form in soup.find_all("form"):
        action = normalize_urlish(form.get("action") or "[empty-action]")
        method = (form.get("method") or "get").lower()
        names = []
        types = []
        for inp in form.find_all(["input", "textarea", "select", "button"]):
            types.append((inp.get("type") or inp.name or "input").lower())
            if inp.get("name"):
                names.append(inp.get("name").lower())
        forms.add("%s %s :: %s" % (method, action, ",".join(sorted(set(types)))))
        if names:
            signatures.add("fields:%s" % ",".join(sorted(set(names))[:30]))
    return forms, signatures

def extract_internal_paths(soup, base_url=None):
    out = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:") or href.startswith("javascript:"):
            continue
        full = urljoin(base_url, href) if base_url else href
        p = urlparse(full)
        if p.path:
            out.add(p.path.rstrip("/") or "/")
    return out

def extract_asset_domains(soup, base_url=None):
    out = set()
    for tag in soup.find_all(["script", "link", "img", "iframe"]):
        src = tag.get("src") or tag.get("href")
        if not src:
            continue
        full = urljoin(base_url, src) if base_url else src
        p = urlparse(full)
        if p.netloc:
            out.add(p.netloc.lower())
    return out

def extract_inline_blocks(soup, kind):
    mapping = {}
    if kind == "js":
        for tag in soup.find_all("script"):
            if not tag.get("src"):
                text = normalize_text(tag.get_text(" ", strip=True))
                if text:
                    mapping["inline-js:%s" % short_hash(text[:1500])] = safe_preview(text, 650)
    else:
        for tag in soup.find_all("style"):
            text = normalize_text(tag.get_text(" ", strip=True))
            if text:
                mapping["inline-css:%s" % short_hash(text[:1500])] = safe_preview(text, 650)
    return mapping

def extract_dom_patterns(soup):
    tags = Counter()
    for tag in soup.find_all(True):
        tags[tag.name.lower()] += 1
    return set("%s:%s" % (k, v) for k, v in tags.most_common(20))

def extract_fingerprints(html, label, base_url=None):
    soup = BeautifulSoup(html, "html.parser")
    forms, form_signatures = extract_forms(soup)
    inline_js_map = extract_inline_blocks(soup, "js")
    inline_css_map = extract_inline_blocks(soup, "css")
    theme_data = extract_theme_hints(html, soup)

    fp = {
        "direct_theme": theme_data["direct_theme"],
        "theme_assets": theme_data["theme_assets"],
        "plugin_comments": theme_data["plugin_comments"],
        "important_meta": extract_important_meta(soup),
        "comments": extract_comments(html),
        "ids": extract_ids(soup),
        "classes": extract_classes(soup),
        "forms": forms,
        "form_signatures": form_signatures,
        "internal_paths": extract_internal_paths(soup, base_url),
        "asset_domains": extract_asset_domains(soup, base_url),
        "inline_scripts": set(inline_js_map.keys()),
        "inline_styles": set(inline_css_map.keys()),
        "dom_patterns": extract_dom_patterns(soup),
    }

    short_summary = {
        "direct_theme": sorted(list(fp["direct_theme"]))[:10],
        "theme_assets": sorted(list(fp["theme_assets"]))[:10],
        "plugin_comments": sorted(list(fp["plugin_comments"]))[:10],
        "important_meta": sorted(list(fp["important_meta"]))[:10],
        "ids": sorted(list(fp["ids"]))[:20],
        "form_signatures": sorted(list(fp["form_signatures"]))[:10],
        "asset_domains": sorted(list(fp["asset_domains"]))[:10],
    }

    return {
        "label": label,
        "fingerprints": fp,
        "inline_js_map": inline_js_map,
        "inline_css_map": inline_css_map,
        "short_summary": json.dumps(short_summary, ensure_ascii=False, indent=2),
    }

def similarity_score(fp_a, fp_b):
    weights = {
        "direct_theme": 7,
        "theme_assets": 5,
        "inline_scripts": 4,
        "inline_styles": 3,
        "important_meta": 2,
        "form_signatures": 4,
        "ids": 2,
        "comments": 2,
        "asset_domains": 2,
        "internal_paths": 2,
        "dom_patterns": 2,
        "classes": 1,
    }
    inter = 0
    union = 0
    for key, weight in weights.items():
        a = safe_set(fp_a.get(key))
        b = safe_set(fp_b.get(key))
        inter += len(a & b) * weight
        union += len(a | b) * weight
    if union == 0:
        return 0
    return int(round((inter / float(union)) * 100))

def template_risk(fp_a, fp_b):
    score = 0
    if fp_a["direct_theme"] & fp_b["direct_theme"]:
        score += 35
    if fp_a["theme_assets"] & fp_b["theme_assets"]:
        score += 20
    if fp_a["inline_scripts"] & fp_b["inline_scripts"]:
        score += 20
    common_css = fp_a["inline_styles"] & fp_b["inline_styles"]
    if common_css:
        score += 10
    if fp_a["form_signatures"] & fp_b["form_signatures"]:
        score += 10
    custom_ids = [x for x in (fp_a["ids"] & fp_b["ids"]) if not is_noise_id(x)]
    if len(custom_ids) >= 2:
        score += 5
    return min(score, 100)

def make_issue(title, level, explanation, matches, steps, preview_a="", preview_b=""):
    cls = "sev-low"
    if level == "Критично":
        cls = "sev-high"
    elif level == "Увага":
        cls = "sev-mid"
    return {
        "title": title,
        "level": level,
        "level_class": cls,
        "explanation": explanation,
        "matches": matches,
        "steps": steps,
        "preview_a": preview_a,
        "preview_b": preview_b,
    }

def build_real_and_noise_issues(a_data, b_data):
    fp_a = a_data["fingerprints"]
    fp_b = b_data["fingerprints"]
    real_issues = []
    noise_issues = []

    common_direct_theme = sorted(fp_a["direct_theme"] & fp_b["direct_theme"])
    common_theme_assets = sorted(fp_a["theme_assets"] & fp_b["theme_assets"])
    if common_direct_theme or common_theme_assets:
        explanation = (
            "Тут уже прямий збіг теми або її публічних asset-шляхів. Це не Yoast і не типовий WordPress шум. "
            "Якщо бачиш wp-theme:..., або однакові /wp-content/themes/.../css/style.css і /js/script.js, це один з найсильніших футпрінтів у всьому звіті."
        )
        matches = (common_direct_theme + common_theme_assets)[:14]
        real_issues.append(make_issue(
            "Однакова тема або theme-assets",
            "Критично",
            explanation,
            matches,
            [
                "Перейменуй тему на одному з сайтів або зроби окрему копію теми з іншою назвою.",
                "У style.css зміни Theme Name, якщо створюєш окрему тему.",
                "По можливості винеси публічні css/js в нейтральні assets шляхи без назви теми.",
                "Перевір, щоб у фінальному HTML більше не світився /wp-content/themes/назва-теми/..."
            ]
        ))

    common_plugin_comments = sorted(fp_a["plugin_comments"] & fp_b["plugin_comments"])
    if common_plugin_comments:
        explanation = (
            "Це типовий plugin шум, а не доказ однакової теми. Наприклад Yoast часто залишає однакові comments на багатьох сайтах. "
            "Їх добре прибрати для чистоти, але не варто вважати головною проблемою."
        )
        noise_issues.append(make_issue(
            "Yoast / plugin comments",
            "Низький ризик",
            explanation,
            common_plugin_comments[:10],
            []
        ))

    common_js = sorted(fp_a["inline_scripts"] & fp_b["inline_scripts"])
    if common_js:
        first = common_js[0]
        explanation = (
            "Це вже схоже на однаковий кастомний JavaScript, а не на типовий код ядра WordPress. "
            "Якщо preview майже однаковий, значить у тебе на двох сайтах стоїть один і той самий inline script для меню, мови, попапу, FAQ або іншої логіки."
        )
        real_issues.append(make_issue(
            "Однаковий кастомний inline JavaScript",
            "Критично",
            explanation,
            common_js[:10],
            [
                "Знайди цей <script> у header.php, footer.php, functions.php або template-part.",
                "Краще винести код у зовнішній js-файл.",
                "Якщо логіка має лишитися, зміни структуру коду, назви змінних, порядок ініціалізації.",
                "Де можливо, перенеси дані в data-* атрибути замість window.* config."
            ],
            a_data["inline_js_map"].get(first, ""),
            b_data["inline_js_map"].get(first, "")
        ))

    common_css = sorted(fp_a["inline_styles"] & fp_b["inline_styles"])
    if common_css:
        first = common_css[0]
        custom_css = [x for x in common_css if "wp--preset" not in (a_data["inline_css_map"].get(x, "")[:220].lower())]
        wp_css = [x for x in common_css if x not in custom_css]

        if custom_css:
            explanation = (
                "Тут є однаковий inline CSS, і це не схоже лише на стандартний WordPress global styles блок. "
                "Швидше за все, дублюються кастомні стилі для секцій, меню, FAQ, hero або footer."
            )
            real_issues.append(make_issue(
                "Однаковий кастомний inline CSS",
                "Увага",
                explanation,
                custom_css[:10],
                [
                    "Знайди кастомні <style> блоки у шаблонах або ACF-блоках.",
                    "Винеси їх у зовнішній css-файл.",
                    "Зміни назви класів, порядок правил або структуру селекторів.",
                    "Окремо перевір hero, faq, menu, popup, footer."
                ],
                a_data["inline_css_map"].get(custom_css[0], ""),
                b_data["inline_css_map"].get(custom_css[0], "")
            ))

        if wp_css:
            explanation = (
                "Це схоже на стандартний WordPress global styles шум. Сам по собі такий збіг не є критичним доказом однакового шаблону."
            )
            noise_issues.append(make_issue(
                "Типовий WordPress inline CSS шум",
                "Низький ризик",
                explanation,
                wp_css[:10],
                []
            ))

    common_meta = sorted(fp_a["important_meta"] & fp_b["important_meta"])
    real_meta = [x for x in common_meta if not is_noise_meta(x)]
    noise_meta = [x for x in common_meta if is_noise_meta(x)]

    if real_meta:
        explanation = (
            "Тут збігаються не просто типові SEO прапорці, а конкретні важливі meta значення. "
            "Особливо варто дивитися на generator, description, og:site_name або інші брендовані поля."
        )
        real_issues.append(make_issue(
            "Однакові важливі meta",
            "Увага",
            explanation,
            real_meta[:12],
            [
                "Зроби унікальні description і social meta для кожного сайту.",
                "Якщо присутній generator — прибери його.",
                "Перевір og:site_name, twitter-card, theme-color та інші брендовані meta."
            ]
        ))

    if noise_meta:
        explanation = (
            "Це типові SEO значення, які часто збігаються на великій кількості сайтів. Наприклад og:type=website або twitter:card=summary_large_image — слабкі сигнали."
        )
        noise_issues.append(make_issue(
            "Типові SEO meta збіги",
            "Низький ризик",
            explanation,
            noise_meta[:12],
            []
        ))

    common_ids = sorted(fp_a["ids"] & fp_b["ids"])
    real_ids = [x for x in common_ids if not is_noise_id(x)]
    noise_ids = [x for x in common_ids if is_noise_id(x)]

    if real_ids:
        explanation = (
            "Тут збігаються саме кастомні id, а не службові WordPress id. "
            "Наприклад faq-1, mobilenav, menu-left-menu або інші власні назви показують, що на двох сайтах дуже схожа структура секцій або меню."
        )
        real_issues.append(make_issue(
            "Однакові кастомні DOM id",
            "Увага",
            explanation,
            real_ids[:20],
            [
                "Перейменуй ці id на унікальні для кожного сайту.",
                "Якщо id не критичний — заміни його на class або data-attribute.",
                "Не забудь оновити JS, який звертається до цих id."
            ]
        ))

    if noise_ids:
        explanation = (
            "Це службові WordPress або plugin id. Вони часто повторюються і не є головною причиною, чому сайт палиться."
        )
        noise_issues.append(make_issue(
            "Системні WordPress / plugin id",
            "Низький ризик",
            explanation,
            noise_ids[:20],
            []
        ))

    common_comments = sorted(fp_a["comments"] & fp_b["comments"])
    real_comments = [x for x in common_comments if not is_noise_comment(x)]
    if real_comments:
        explanation = (
            "Тут збігаються ручні або шаблонні comments, а не плагінові службові коментарі. "
            "Такі речі часто показують, що секції або блоки просто переносилися між сайтами."
        )
        real_issues.append(make_issue(
            "Однакові ручні HTML comments",
            "Увага",
            explanation,
            real_comments[:15],
            [
                "Знайди ці тексти через пошук по проекту.",
                "Видали comments із production HTML.",
                "Особливо перевір header, footer, faq, таблиці, ACF block templates."
            ]
        ))

    common_forms = sorted(fp_a["form_signatures"] & fp_b["form_signatures"])
    if common_forms:
        explanation = (
            "Форми мають однакові набори полів. Якщо це кастомні форми, це ще один сигнал, що використовувався один і той самий шаблон."
        )
        real_issues.append(make_issue(
            "Однакові signatures форм",
            "Увага",
            explanation,
            common_forms[:10],
            [
                "Зміни name полів, порядок полів або hidden inputs.",
                "Зміни action endpoint або структуру submit логіки, якщо це потрібно.",
                "Для різних проектів краще мати окремі шаблони форм."
            ]
        ))

    common_paths = sorted(fp_a["internal_paths"] & fp_b["internal_paths"])
    meaningful_paths = [x for x in common_paths if x not in ["/", "/ar", "/en"]]
    trivial_paths = [x for x in common_paths if x in ["/", "/ar", "/en"]]

    if meaningful_paths:
        explanation = (
            "Тут повторюються не базові шляхи, а більш змістовні slug/path. Це вже може показувати схожу карту сторінок."
        )
        real_issues.append(make_issue(
            "Однакові змістовні внутрішні шляхи",
            "Низький ризик",
            explanation,
            meaningful_paths[:20],
            [
                "Переглянь slug/path naming там, де це реально можна змінити.",
                "Не дублюй повністю однакову карту внутрішніх сторінок без потреби."
            ]
        ))

    if trivial_paths:
        explanation = (
            "Базові шляхи типу /, /ar, /en — слабкий сигнал. Їх не варто виносити в головні проблеми."
        )
        noise_issues.append(make_issue(
            "Тривіальні базові шляхи",
            "Низький ризик",
            explanation,
            trivial_paths[:10],
            []
        ))

    return real_issues, noise_issues

def build_human_summary(a_data, b_data, real_issues, noise_issues):
    fp_a = a_data["fingerprints"]
    fp_b = b_data["fingerprints"]

    common_direct_theme = sorted(fp_a["direct_theme"] & fp_b["direct_theme"])
    common_theme_assets = sorted(fp_a["theme_assets"] & fp_b["theme_assets"])
    js_hits = sorted(fp_a["inline_scripts"] & fp_b["inline_scripts"])
    real_comments = [x for x in sorted(fp_a["comments"] & fp_b["comments"]) if not is_noise_comment(x)]
    custom_ids = [x for x in sorted(fp_a["ids"] & fp_b["ids"]) if not is_noise_id(x)]

    lines = []

    if common_direct_theme or common_theme_assets:
        theme_bits = (common_direct_theme + common_theme_assets)[:4]
        lines.append("1. Найсильніший збіг — тема або її assets. Скрипт прямо бачить theme-збіги: %s." % ", ".join(theme_bits))

    if js_hits:
        lines.append("2. Далі йде однаковий inline JavaScript. Це виглядає як однаковий кастомний код, а не як випадковий WordPress шум.")

    if real_comments:
        lines.append("3. Є однакові ручні comments: %s. Це вже схоже на сліди шаблону або копіювання блоків." % ", ".join(real_comments[:5]))

    if custom_ids:
        lines.append("4. Повторюються кастомні id: %s. Це означає, що однаковими є не тільки стилі, а й структура секцій." % ", ".join(custom_ids[:8]))

    if noise_issues:
        lines.append("5. Частина збігів — це шум WordPress/плагінів. Наприклад Yoast comments, global styles або системні id не варто ставити в один ряд із реально кастомними збігами.")

    if not lines:
        lines.append("Сильних кастомних збігів майже немає. Більшість знайденого схоже на типовий шум або слабкі сигнали.")

    return "\n\n".join(lines)

def build_fix_priority(real_issues):
    if not real_issues:
        return ["Критичних кастомних збігів мало. Перевір generator/comments для чистоти."]
    return ["%s. %s" % (idx, issue["title"]) for idx, issue in enumerate(real_issues[:6], start=1)]

def build_top_matches(a_data, b_data):
    fp_a = a_data["fingerprints"]
    fp_b = b_data["fingerprints"]
    lines = []

    theme = sorted((fp_a["direct_theme"] & fp_b["direct_theme"]) | (fp_a["theme_assets"] & fp_b["theme_assets"]))
    if theme:
        lines.append("theme/assets: %s" % ", ".join(theme[:8]))

    js = sorted(fp_a["inline_scripts"] & fp_b["inline_scripts"])
    if js:
        lines.append("inline js: %s" % ", ".join(js[:8]))

    ids = [x for x in sorted(fp_a["ids"] & fp_b["ids"]) if not is_noise_id(x)]
    if ids:
        lines.append("custom ids: %s" % ", ".join(ids[:10]))

    comments = [x for x in sorted(fp_a["comments"] & fp_b["comments"]) if not is_noise_comment(x)]
    if comments:
        lines.append("manual comments: %s" % ", ".join(comments[:10]))

    return lines or ["Сильних кастомних збігів не знайдено."]

@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    result = None

    if request.method == "POST":
        try:
            html_a, label_a, base_a = get_input_side(request.form.get("url_a", ""), request.files.get("file_a"), "A")
            html_b, label_b, base_b = get_input_side(request.form.get("url_b", ""), request.files.get("file_b"), "B")

            a_data = extract_fingerprints(html_a, label_a, base_a)
            b_data = extract_fingerprints(html_b, label_b, base_b)

            real_issues, noise_issues = build_real_and_noise_issues(a_data, b_data)

            result = {
                "label_a": a_data["label"],
                "label_b": b_data["label"],
                "similarity": similarity_score(a_data["fingerprints"], b_data["fingerprints"]),
                "template_risk": template_risk(a_data["fingerprints"], b_data["fingerprints"]),
                "real_issues": real_issues,
                "noise_issues": noise_issues,
                "real_issue_count": len(real_issues),
                "noise_count": len(noise_issues),
                "human_summary": build_human_summary(a_data, b_data, real_issues, noise_issues),
                "fix_priority": build_fix_priority(real_issues),
                "top_matches": build_top_matches(a_data, b_data),
                "short_a": a_data["short_summary"],
                "short_b": b_data["short_summary"],
            }

        except requests.RequestException as exc:
            error = "Не вдалося отримати одну зі сторінок по URL: %s" % exc
        except Exception as exc:
            error = str(exc)

    return render_template_string(HTML_TEMPLATE, error=error, result=result)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
