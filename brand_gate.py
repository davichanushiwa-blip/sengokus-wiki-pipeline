#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
戰國魂攻城團｜品牌閘門 brand_gate.py  v1.4
================================================================
用途：AI 起草文章後、進入人工簽核前，自動擋下會讓品牌走音走色的內容。
      可直接接在 pre-commit / GitHub Actions / CI 上，BLOCK 時 exit 1。

用法：
  python3 brand_gate.py article.mdx [more.mdx ...]
  python3 brand_gate.py --stdin < article.mdx
  python3 brand_gate.py --json article.mdx        # 供 CI 解析

依賴：僅 Python 標準庫，不需安裝任何套件。
      v1.1 新增 G9：直接檢驗 POST /api/wiki/articles 的欄位契約（標題／slug／
      分類／metaDescription／tags／封面／publishedAt／upsert 等值域）。
      v1.2 依 2026-11-20 三項決策：category 增設 fieldtrip（第 5 類，英文 key 依後台 2026-11-21 定案）、
      bodyFormat 定為 json、G9 同步 5 類；並由 wiki_publisher 在送出前
      對編譯後的 JSON body 再做一次 G10 複掃。
      v1.3 新增 BRAND_TRUST_SPEC 單一來源與「G4 統一」攔截。
      v1.4 分類 WARN 依第四次實測改寫：API 已實回 400「請選擇文章分類」。
語言：報告為繁體中文（品牌語境）；程式碼標識符為英文。
================================================================
"""

import re
import sys
import json
import argparse
from pathlib import Path

VERSION = "1.7"

# ---------------------------------------------------------------
# G1｜廣告法違禁詞（取自 v2.0 規範包 2-1 節，並補常見變體）
#     重點：frontmatter 的 title / description / og* / schema* 也一併掃，
#     因為實站已查出「最真實」藏在 meta 與 JSON-LD，會被 AI 當範本複製。
# ---------------------------------------------------------------
BANNED_TERMS = [
    # 絕對化：「最」系列
    "最真實", "最具規模", "全日本最具規模", "最好", "最佳", "最大", "最高", "最低",
    "最便宜", "最先進", "最優惠", "最專業", "最強", "最完整", "最詳細", "最齊全",
    "最權威", "最划算", "最頂尖", "最優質", "最迅速", "最安全",
    # 「第一／唯一」系列（單獨的「第一」「唯一」改由正則處理，避免「第一個冬季」誤報）
    "全國第一", "業界第一", "行業第一", "全日本第一", "唯一指定", "唯一授權",
    "獨一無二", "絕無僅有",
    # 「頂級」系列
    "頂級", "極品", "極致", "絕佳", "萬能", "永久", "無敵", "天花板",
    # 權威背書
    "國家級", "世界級", "全球首發", "國家領導人推薦", "特供", "專供", "國宴專用",
    # 保證承諾
    "100%", "百分百", "零風險", "絕對安全", "穩賺不賠", "保本保息",
    "包治百病", "藥到病除", "無效退款", "史無前例", "前無古人", "無人能及",
]
BANNED_REGEX = [
    (r"最[好佳大高低便宜先進優惠專業強完整詳細真實齊全權威划算頂尖優質迅速安全]", "「最＋形容詞」絕對化用語"),
    # 只擋「排名宣稱」的第一／唯一；「第一個冬季」「第一階段」「唯一可行做法」屬正常敘述，放行
    (r"第一(?!個|步|旬|時間|人稱|階段|層|回合|年|日|次|頁|版|季|戰|城|隊|軍|線|批|波|週|夜|月)",
     "「第一」排名宣稱"),   # 週／夜／月屬時間敘述（如「第一週該做的事」），2026-11-21 試跑補入
    (r"唯一(?!可行|能|會|需要|不|的?做法是|的?方法是)", "「唯一」絕對化宣稱"),
    (r"全(?:國|台|港|日|球|業界|行業)第[一1]", "全域第一"),
    (r"\d{1,3}%\s*(?:有效|滿意|成功|保證)", "百分比保證"),
]

# ---------------------------------------------------------------
# G2｜繁體一致性：明確的簡體專用字／詞
#     避開繁體同形字（后／于／里／准／划／据 等改以「詞」比對）
# ---------------------------------------------------------------
SIMPLIFIED_CHARS = set(
    "顾纹颜们关图视觉转动这来时会个为对说与专门业务团队号问处实开点无"
    "数据应该将还万级优势历战争国书华语击简连选审签线资讯频广营销费测试"
    "验护则规认从众么过经军粮阵鉴录盖优标质档产键观数击"
)
SIMPLIFIED_WORDS = [
    "后台", "后来", "之后", "最后", "往后", "今后", "数据", "计划", "规划", "策划",
    "规则", "质量", "网络", "对应", "观察", "关键", "产生", "标准", "档案",
    "调整", "覆盖", "颜色", "纹理", "简体", "视频", "发布", "点击", "页面", "优化",
    "登录", "注册", "信息", "内容", "设置", "文件", "图标", "链接", "推荐", "相关",
]

# ---------------------------------------------------------------
# G3｜品牌階層與專名（決策 A 定案）
# ---------------------------------------------------------------
FORBIDDEN_NAMES = [
    ("戰國攻城團", "舊母品牌名，應為「戰國魂攻城團」"),
    ("战国魂攻城团", "簡體母品牌名，應為繁體「戰國魂攻城團」"),
    ("战国魂の野望", "簡體附屬遊戲名，應為「戰國魂の野望」"),
]
REQUIRED_BRAND = "戰國魂攻城團"
REQUIRED_GAME = "戰國魂の野望"
# Schema.Organization.name 現況為「攻城團」，新文章不得沿用為對外主名
SCHEMA_OLD_ORG = "攻城團"

# ---------------------------------------------------------------
# G5｜frontmatter 必填欄位
# ---------------------------------------------------------------
REQUIRED_FIELDS = [
    # 送進 POST /api/wiki/articles 的欄位
    "title", "slug", "category", "status", "metaTitle", "metaDescription",
    "metaKeywords", "tags", "coverImage", "coverAlt", "publishedAt", "upsert",
    # 本地治理欄位（不送 API，供簽核與 GEO 追蹤）
    "date", "layer", "keywordLayer", "targetKeyword", "canonical",
    "brand", "game", "schemaType", "whatWeDo", "whyTrust", "howToJoin", "cta",
    "related", "author", "reviewedBy", "reviewedAt", "utm", "lang", "hreflang",
    "bodyFormat",
]
ALLOWED_STATUS = {"draft", "review", "published"}  # review 為本地審稿態，送 API 時轉 draft
ALLOWED_LAYER = {"L1", "L2", "L3"}
ALLOWED_KW_LAYER = {"core", "business", "long-tail", "dimension"}
# 決策 02（2026-11-20 確認；2026-11-21 後台定案 key=fieldtrip）：第 5 類對應 L3 實地探訪層。
# 後台另接受中文名稱（實地探訪／实地探访），API 會自動轉成英文 key 再存。
ALLOWED_CATEGORY = {"history", "mechanics", "beginner", "video", "fieldtrip"}
# 決策 01（已確認）：body 為 JSON 結構，由 wiki_publisher.compile_body() 編譯。
# 2026-11-21 定案：後台編輯器欄位即「內文（Markdown）」，body 預設 markdown；
# json（blocks-v1，決策 01）保留為相容／歷史路徑。
ALLOWED_BODY_FORMAT = {"json", "markdown"}

# ---------------------------------------------------------------
# 【全站統一規格】三問區＋CTA 的唯一來源（2026-11-20 使用者目視後要求「要統一」）
# 任何頁面／文章／渠道都引用這一份；單篇 frontmatter 不得自訂，管線也不從 fm 取值。
# 改這裡一處，全站同步；G4 會攔下任何不一致的 frontmatter。
# ---------------------------------------------------------------
BRAND_TRUST_SPEC = {
    "heading": "關於戰國魂攻城團",
    "whatWeDo": "戰國魂攻城團以攻略百科、旬戰報與實地走訪，把日本戰國世界觀立體化；附屬遊戲《戰國魂の野望》為其中一環。",
    "whyTrust": "內容以可查證的史料、遊戲規則條目與團員實地走訪紀錄為依據，標註推論與史實的界線，並附對應條目與路線供查核。",
    "howToJoin": "於 wiki 首頁點選「立即進入戰國世界」建立武將，或加入攻城團實地走訪社群。",
    "cta": "立即進入戰國世界",
    "links": [
        {"text": "查看天下地圖", "href": "/realm/"},
        {"text": "全部常見問題", "href": "/faq/"},
    ],
}
CTA_TEXT = BRAND_TRUST_SPEC["cta"]

# G6 需要出現的結構標記（頁面模板會吃這些區塊自動產生 Schema 與三問側欄）
REQUIRED_SECTIONS = ["## 結論", "## 常見問題", "## 同主題推薦"]

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")


# ---------------------------------------------------------------
def parse_frontmatter(text):
    """極簡 frontmatter 解析器：支援 `key: value` 與 `- item` 清單。"""
    if not text.startswith("---"):
        return None, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return None, text
    fm, body = {}, m.group(2)
    key = None
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and key:
            fm.setdefault(key, [])
            if isinstance(fm[key], list):
                fm[key].append(item.group(1).strip())
            continue
        kv = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if kv:
            key, val = kv.group(1), kv.group(2).strip()
            fm[key] = [] if val == "" else val.strip('"').strip("'")
    return fm, body


def scan_text(label, text, findings):
    """對一段文字跑 G1 / G2 / G7，回報命中。"""
    for term in BANNED_TERMS:
        if term in text:
            idx = text.find(term)
            findings.append(("BLOCK", "G1 違禁詞", f"{label} 出現「{term}」：…{text[max(0,idx-18):idx+len(term)+18]}…"))
    for pat, desc in BANNED_REGEX:
        for m in re.finditer(pat, text):
            findings.append(("BLOCK", "G1 違禁詞", f"{label} 命中{desc}「{m.group(0)}」"))
    for w in SIMPLIFIED_WORDS:
        if w in text:
            findings.append(("BLOCK", "G2 繁體", f"{label} 出現簡體詞「{w}」"))
    hit = sorted({c for c in text if c in SIMPLIFIED_CHARS})
    if hit:
        findings.append(("BLOCK", "G2 繁體", f"{label} 出現簡體字：{''.join(hit)}"))
    if EMOJI_RE.search(text):
        findings.append(("BLOCK", "G7 圖示", f"{label} 含 Emoji，網站一律改用 SVG 圖示"))


def check_api_contract(fm, body, findings):
    """G9：POST /api/wiki/articles 的欄位契約（依 WorkBuddy 設定提供的規格）。"""
    title = str(fm.get("title", ""))
    if len(title) > 80:
        findings.append(("BLOCK", "G9 API 契約", f"title {len(title)} 字，API 上限 80 字"))
    slug = str(fm.get("slug", ""))
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        findings.append(("BLOCK", "G9 API 契約", f"slug「{slug}」不合規則（只允許小寫英文、數字、連字號）"))
    if fm.get("category") not in ALLOWED_CATEGORY:
        findings.append(("BLOCK", "G9 API 契約",
                         f"category「{fm.get('category')}」不在允許的 5 類 {sorted(ALLOWED_CATEGORY)}"))
    if fm.get("category") == "fieldtrip":
        findings.append(("WARN", "G9 API 契約",
                         "fieldtrip 為決策 02 第 5 類；後台已建好，若仍回 400 請確認 PR #102 是否已部署到正式站"))
    if not body.strip():
        findings.append(("BLOCK", "G9 API 契約", "body 不可為空（frontmatter 之後的本文）"))
    status = fm.get("status")
    if status not in ALLOWED_STATUS:
        findings.append(("BLOCK", "G9 API 契約", f"status「{status}」須為 draft／review／published"))
    md = str(fm.get("metaDescription", ""))
    if len(md) > 200:
        findings.append(("BLOCK", "G9 API 契約", f"metaDescription {len(md)} 字，API 上限 200 字"))
    if status == "published" and not md.strip():
        findings.append(("BLOCK", "G9 API 契約", "status: published 時 metaDescription 必填"))
    tags = fm.get("tags", [])
    if not isinstance(tags, list):
        findings.append(("BLOCK", "G9 API 契約", "tags 須為清單格式"))
    else:
        if len(tags) > 10:
            findings.append(("BLOCK", "G9 API 契約", f"tags {len(tags)} 個，API 上限 10 個"))
        for t in tags:
            if len(str(t)) > 20:
                findings.append(("BLOCK", "G9 API 契約", f"tag「{t}」超過 20 字"))
    cover, alt = str(fm.get("coverImage", "")), str(fm.get("coverAlt", ""))
    if cover and not re.match(r"^(https://|/)", cover):
        findings.append(("BLOCK", "G9 API 契約", "coverImage 須以 https:// 或 / 開頭"))
    if bool(cover) != bool(alt):
        findings.append(("BLOCK", "G9 API 契約", "coverImage 與 coverAlt 必須同時填寫"))
    pa = str(fm.get("publishedAt", ""))
    if pa and not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$", pa):
        findings.append(("BLOCK", "G9 API 契約", f"publishedAt「{pa}」須為 ISO 8601 且帶時區"))
    upsert = str(fm.get("upsert", "false")).strip().lower()
    if upsert not in ("true", "false"):
        findings.append(("BLOCK", "G9 API 契約", "upsert 須為 true 或 false"))
    if upsert == "true" and status == "published":
        findings.append(("WARN", "G9 API 契約", "upsert:true 且 published 會直接覆寫已上線文章，請確認是刻意為之"))
    if status == "published":
        findings.append(("WARN", "G9 API 契約", "API 的 published 會直接上線、沒有後台審核態；請確認已過真人簽核"))


def check(path, text):
    findings = []
    fm, body = parse_frontmatter(text)

    # ---- G5 frontmatter ----
    if fm is None:
        findings.append(("BLOCK", "G5 結構", "缺少 frontmatter（檔案須以 --- 開頭）"))
        return findings, {}
    missing = [k for k in REQUIRED_FIELDS if k not in fm or fm[k] in ("", [])]
    for k in missing:
        findings.append(("BLOCK", "G5 結構", f"frontmatter 缺少必填欄位 `{k}`"))

    # ---- G1/G2/G7：frontmatter 所有字串值（含 meta / og）都要掃 ----
    for k, v in fm.items():
        vals = v if isinstance(v, list) else [v]
        for val in vals:
            if isinstance(val, str):
                scan_text(f"frontmatter.{k}", val, findings)
    scan_text("本文", body, findings)

    # ---- G3 品牌階層 ----
    for old, why in FORBIDDEN_NAMES:
        if old in text:
            findings.append(("BLOCK", "G3 專名", f"出現舊／簡體名稱「{old}」：{why}"))
    if REQUIRED_BRAND not in text:
        findings.append(("BLOCK", "G3 專名", f"全文未出現母品牌「{REQUIRED_BRAND}」（每個頁面都要能回答「你是誰」）"))
    if REQUIRED_GAME not in text:
        findings.append(("WARN", "G3 專名", f"未出現附屬遊戲「{REQUIRED_GAME}」，確認是否為世界觀／遊戲相關文章"))
    if fm.get("brand") and fm["brand"] != REQUIRED_BRAND:
        findings.append(("BLOCK", "G3 專名", f"frontmatter.brand 應為「{REQUIRED_BRAND}」，目前為「{fm['brand']}」"))
    if fm.get("game") and fm["game"] != REQUIRED_GAME:
        findings.append(("BLOCK", "G3 專名", f"frontmatter.game 應為「{REQUIRED_GAME}」"))
    # 防止沿用實站 Schema 的舊 Organization.name
    if re.search(r'["\']?name["\']?\s*[:=]\s*["\']' + SCHEMA_OLD_ORG, text):
        findings.append(("BLOCK", "G3 專名", f"Schema 沿用舊 Organization.name「{SCHEMA_OLD_ORG}」，應改為母品牌全稱"))

    # ---- G4 三問 + CTA（全站統一規格）----
    # 三問文案由 BRAND_TRUST_SPEC 單一來源注入；frontmatter 若填寫，必須與規格逐字一致。
    for k in ("whatWeDo", "whyTrust", "howToJoin"):
        v = fm.get(k)
        if not v or (isinstance(v, str) and len(v) < 10):
            findings.append(("BLOCK", "G4 三問", f"`{k}` 未填或過短，條目頁無法獨立回答三問"))
        elif v != BRAND_TRUST_SPEC[k]:
            findings.append(("BLOCK", "G4 統一", f"`{k}` 與全站統一規格不一致。三問區由 brand_gate.BRAND_TRUST_SPEC 注入，單篇不得自訂；請改規格或比對修正"))
    if fm.get("cta") != CTA_TEXT:
        findings.append(("BLOCK", "G4 轉化", f"CTA 統一為「{CTA_TEXT}」，目前為「{fm.get('cta','(空)')}」"))

    # ---- G6 GEO 結構 ----
    for sec in REQUIRED_SECTIONS:
        if sec not in body:
            findings.append(("BLOCK", "G6 GEO", f"本文缺少必要區塊「{sec}」"))
    rel = fm.get("related", [])
    if isinstance(rel, list) and not (3 <= len(rel) <= 6):
        findings.append(("BLOCK", "G6 GEO", f"同主題推薦需 3–6 篇，目前 {len(rel)} 篇"))
    elif not isinstance(rel, list):
        findings.append(("BLOCK", "G6 GEO", "`related` 須為清單格式（每行 `  - slug`）"))
    first_para = next((p.strip() for p in body.split("\n\n") if p.strip() and not p.strip().startswith("#")), "")
    if first_para and len(first_para) > 260:
        findings.append(("WARN", "G6 GEO", "首段偏長，倒金字塔結論建議壓在 120 字內，方便 AI 引用"))
    if not re.search(r"\d", first_para):
        findings.append(("WARN", "G6 GEO", "首段缺具體數字，AI 引用意願較低；建議補兵力／旬數／點數等可驗證數據"))
    if fm.get("schemaType") != "Article":
        findings.append(("WARN", "G6 GEO", "schemaType 建議為 Article（問答段另由模板產生 FAQPage）"))
    if fm.get("lang") != "zh-Hant":
        findings.append(("BLOCK", "G6 GEO", "lang 須為 zh-Hant"))
    if not fm.get("coverAlt"):
        findings.append(("BLOCK", "G6 GEO", "coverAlt（主圖替代文字）不可為空"))

    # ---- G8 發布閘門：未簽核不得發布 ----
    status = fm.get("status")
    if status not in ALLOWED_STATUS:
        findings.append(("BLOCK", "G8 簽核", f"status 須為 draft/review/published，目前為「{status}」"))
    if not fm.get("reviewedBy") or not fm.get("reviewedAt"):
        findings.append(("BLOCK", "G8 簽核", "缺人工簽核人／簽核時間：本管線不允許無人值守全自動發布"))
    if status == "published" and (not fm.get("reviewedBy") or not fm.get("reviewedAt")):
        findings.append(("BLOCK", "G8 簽核", "status=published 但未簽核，禁止上線"))

    for k, allowed, label in [
        ("layer", ALLOWED_LAYER, "世界觀層"),
        ("keywordLayer", ALLOWED_KW_LAYER, "關鍵詞層"),
        ("category", ALLOWED_CATEGORY, "文章分類"),
        ("bodyFormat", ALLOWED_BODY_FORMAT, "內文格式（2026-11-21 後台定案 markdown；json 為舊決策 01，保留相容）"),
    ]:
        if fm.get(k) and fm[k] not in allowed:
            findings.append(("BLOCK", "G5 結構", f"{label} `{k}` 值「{fm[k]}」不在允許清單 {sorted(allowed)}"))

    check_api_contract(fm, body, findings)

    return findings, fm


def render_report(path, findings, fm):
    lines = []
    lines.append("=" * 64)
    lines.append(f"戰國魂攻城團｜品牌閘門 v{VERSION}　{path}")
    lines.append("=" * 64)
    groups = ["G1 違禁詞", "G2 繁體", "G3 專名", "G4 三問", "G4 統一", "G4 轉化",
              "G5 結構", "G6 GEO", "G7 圖示", "G8 簽核", "G9 API 契約"]
    blocks = [f for f in findings if f[0] == "BLOCK"]
    warns = [f for f in findings if f[0] == "WARN"]
    for g in groups:
        hit = [f for f in findings if f[1] == g and f[0] == "BLOCK"]
        mark = "BLOCK" if hit else " PASS"
        lines.append(f"[{mark}] {g}" + (f"　{len(hit)} 項" if hit else ""))
    lines.append("-" * 64)
    if blocks:
        lines.append(f"攔截 {len(blocks)} 項（不得進入簽核／部署）：")
        for i, (_, g, msg) in enumerate(blocks, 1):
            lines.append(f"  {i:2d}. [{g}] {msg}")
    if warns:
        lines.append(f"提醒 {len(warns)} 項（不攔截，建議修正）：")
        for _, g, msg in warns:
            lines.append(f"   · [{g}] {msg}")
    lines.append("-" * 64)
    verdict = "BLOCK　退回 AI 重寫" if blocks else "PASS　可進入人工簽核"
    lines.append(f"判定：{verdict}")
    if fm:
        lines.append(f"文章：{fm.get('title','(無標題)')}　|　狀態：{fm.get('status')}　|　簽核：{fm.get('reviewedBy') or '未簽核'}")
    return "\n".join(lines), (1 if blocks else 0)


def main():
    ap = argparse.ArgumentParser(description="戰國魂攻城團品牌閘門")
    ap.add_argument("files", nargs="*", help="要檢查的 .mdx 檔案")
    ap.add_argument("--stdin", action="store_true", help="從標準輸入讀取")
    ap.add_argument("--json", action="store_true", help="輸出 JSON 供 CI 使用")
    args = ap.parse_args()

    targets = []
    if args.stdin:
        targets.append(("<stdin>", sys.stdin.read()))
    for f in args.files:
        p = Path(f)
        if not p.exists():
            print(f"[ERROR] 找不到檔案：{f}", file=sys.stderr)
            return 2
        targets.append((str(p), p.read_text(encoding="utf-8")))
    if not targets:
        ap.print_help()
        return 2

    all_json, exit_code = [], 0
    for path, text in targets:
        findings, fm = check(path, text)
        blocks = [f for f in findings if f[0] == "BLOCK"]
        warns = [f for f in findings if f[0] == "WARN"]
        if args.json:
            all_json.append({
                "file": path, "verdict": "BLOCK" if blocks else "PASS",
                "blocked": len(blocks), "warned": len(warns),
                "issues": [{"level": l, "group": g, "message": m} for l, g, m in findings],
            })
        else:
            report, code = render_report(path, findings, fm)
            print(report)
            if len(targets) > 1:
                print()
        exit_code = max(exit_code, 1 if blocks else 0)

    if args.json:
        print(json.dumps(all_json if len(all_json) > 1 else all_json[0], ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
