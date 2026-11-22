#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
戰國魂攻城團｜wiki 發文客戶端  wiki_publisher.py  v2.3
================================================================
搭配 brand_gate.py 使用：AI 起草 → 品牌閘門 → 人工簽核 → 編譯 JSON → POST。

API（使用者提供之 WorkBuddy 設定規格）：
  POST https://wiki.sengokus.jp/api/wiki/articles   新增／更新文章
  GET  https://wiki.sengokus.jp/api/wiki/articles   列出所有文章（不含內文）
  Header: Authorization: Bearer <WIKI_API_TOKEN>
          Content-Type: application/json

v2.0 三項已確認決策（2026-11-20）：
  01  body 為 JSON 結構  → 新增 compile_body()，把人讀的 MDX 正文編譯成
      中性 JSON blocks 後才送出；不是 Markdown／HTML 字串。
  02  category 第 5 類 key 定案為 fieldtrip（後台接受實地探訪／实地探访，自動轉 key）。
  03  內文備份 → 本地 .mdx 為唯一來源並進 Git；POST 成功另寫
      backups/<slug>.<UTC>.published.json 快照（含完整 body JSON）。

Token 安全（重要，v2.0 更正說明）：
  * 只從環境變數 WIKI_API_TOKEN 讀取，不接受命令列參數、不寫入檔案、
    不印在畫面或 log 裡、不進 Git。
  * WorkBuddy 官方文件並沒有一個通用的「設定 → 環境變數」頁面可讓使用者
    任意新增自訂變數。實際可行的三條路見設計書第拾章；最單純的是在
    「執行這支腳本的環境」設環境變數：
        export WIKI_API_TOKEN="..."          # 該次 shell
        寫入 ~/.zshrc 或專案 .env           # 長期（.env 必須進 .gitignore）
    若要讓 WorkBuddy Agent／定時任務長期持有憑證，做法是把 API 包成
    「自訂連接器」（auth_mode: token + token-schema.json 的 password 欄位），
    憑證由 WorkBuddy 存於本機 ~/.workbuddy，再以 ${WIKI_API_TOKEN} 注入。
  * 用 `python3 wiki_publisher.py env` 可自檢有沒有讀到，且不會印出值。
  * 【2026-11-20 首次真實發文實測補充】Token 要設「兩端」且值一致：
      [客戶端] 本機 env／.env／CI Secrets → 組成 Authorization: Bearer
      [伺服器端] Vercel 專案 Settings → Environment Variables → 同名
                 WIKI_API_TOKEN → 勾 Production → Redeploy（API 拿來比對）
    缺伺服器端會回 HTTP 503「伺服器尚未設定 WIKI_API_TOKEN。」——這不是
    Token 錯（那會回 401），而是比對根本沒開始。詳設計書第拾壹章。
    實測：G1–G10 全 PASS、draft payload 備妥、POST 回 503、不重試、
    不產生 backups/、Token 零洩漏。
  * 【第二次實測 2026-11-20】Token 已改為 20 字元，客戶端 env 自檢 PASS、
    無偏短警告；重新 list 仍回同一個 503。另以「不帶／錯誤／正確」三種
    Bearer 打 GET，三者回應完全相同 → 證明 API 在比對客戶端憑證之前就
    因自己讀不到 process.env.WIKI_API_TOKEN 而短路。結論：與 Token 值、
    長度、slug、欄位全無關係，100% 是 Vercel 部署環境變數未注入執行中的
    Function（最常見是改了變數卻沒 Redeploy，或只勾到 Preview／Development
    沒勾 Production，或設到別的 Project）。客戶端不必再改任何東西。
    ⚠ 此結論已被下方【第三次實測】推翻（真因是 Token 長度不足 32 字元），
    保留作歷程，勿再依此段排查。
  * 【統一規格 2026-11-20】使用者後台目視確認 blocks-v1 為真實 schema，
    並要求三問區與 CTA「要統一」。文案收斂到 brand_gate.BRAND_TRUST_SPEC
    單一來源；inject_brand_blocks() 不再讀 frontmatter，G4 新增「G4 統一」
    攔截任何自訂三問。任何文章／頁面／渠道都引用同一份規格。
  * 【第三次實測 2026-11-20｜真因更正】使用者指出 API 規格為
    「Token 至少 32 字元，太短就當成未設定」。這才是 503 的真正原因：
    先前兩端 12／20 字元，API 在比對前先做長度檢查，不合格就回
    「伺服器尚未設定 WIKI_API_TOKEN。」，錯誤訊息把「太短」與「未設定」
    混成同一句。v2.0／v2.1 寫的「與 Token 長度無關、要修 Redeploy」是錯的。
    兩端同步換成 40 字元後：env PASS → list 200（共 0 篇）→ check PASS
    → publish --confirm 回 201（id=2、status=draft）→ 寫入內文快照
    → 再 list 確認 1 篇。客戶端長度閾值已由 16 改為 32。
  * 【第四次實測 2026-11-20｜決策 02 驗證】三問標準文案經使用者確認定案。
    以 article-field-notes-sample.mdx（category=fieldtrip／L3 實地探訪）
    試發第二篇 draft：env 40 字元 → list 200（共 1 篇、slug 未撞）
    → check G1–G10 全 PASS（17 blocks 含 brand；G9 給 WARN：後台須先建
    好 fieldtrip（當時名稱 field-notes））→ publish --confirm 回 HTTP 400「請選擇文章分類」。
    API 端的 category 允許清單尚無第 5 類，故不認此值。
    客戶端已停止、不重試、不寫快照；再 list 仍 1 篇，無半寫入。
    處置：後台建立分類（2026-11-21 已定案英文 key=fieldtrip）再原檔重跑即可；
    不改 category 繞過、不擅自改用其他分類、不 --upsert。
    400 提示已改為可直接指向「後台分類未建立」。
  * 【第五次實測 2026-11-20｜並行驗證】使用者回「好的 沒問題 繼續」。
    重探仍回 400（後台分類未建）；改以既有 history 類
    新文章 article-okehazama-sample.mdx 試發：list 200 → check
    G1–G10 PASS（18 blocks 含 brand）→ publish --confirm 回 201
    （id=3、status=draft）→ 寫入第二份內文快照 → list 回 2 篇。
    快照 brand block 六項與 brand_gate.BRAND_TRUST_SPEC 逐項一致，
    且與第一篇舊快照不同，證實全站統一規格已端到端生效。
    同輪補上 .gitignore 與 Git 版本基線，MDX 正本與兩份快照皆進版控。

用法：
  python3 wiki_publisher.py env                          自檢 Token（不印值）
  python3 wiki_publisher.py list                       列出所有文章
  python3 wiki_publisher.py check   article.mdx        檢查＋預覽 JSON payload
  python3 wiki_publisher.py publish article.mdx        預覽（預設，不發送）
  python3 wiki_publisher.py publish article.mdx --confirm              真的送（存草稿）
  python3 wiki_publisher.py publish article.mdx --confirm --publish    真的發佈
  python3 wiki_publisher.py publish article.mdx --confirm --upsert     覆寫同 slug 舊文

安全預設：
  * 沒有 --confirm 一律是 dry-run，不會發出任何請求。
  * 即使 MDX 寫 status: published，沒有 --publish 仍強制送 draft。
  * upsert 預設 false；409 slug 重複時不自動重試（避免重複發文）。
  * POST 失敗不重試，請先跑 list 確認是否已寫入，再決定要不要 --upsert。
  * 送出前會把編譯後的 JSON body 再掃一次違禁詞／簡體／Emoji（G10 複掃）。
================================================================
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone
import io
from urllib import request, error

import brand_gate

# 08  2026-11-21 第八次實測：後台編輯器欄位「內文（Markdown）」→ body 型別與格式
#     定案為 Markdown 字串；--body-format 預設 json → markdown（blocks-v1 保留相容）。
#     新增 upload-image 子命令：POST /api/wiki/images（multipart file、僅 WebP），
#     回傳 url／absoluteUrl，供 coverImage 使用。
VERSION = "2.7"
DEFAULT_BASE = "https://wiki.sengokus.jp/api/wiki/articles"
TOKEN_ENV = "WIKI_API_TOKEN"

# 只送這些欄位給 API；其餘 frontmatter 屬本地治理，不進請求
API_FIELDS = [
    "title", "slug", "category", "body", "status", "metaDescription",
    "metaTitle", "metaKeywords", "tags", "coverImage", "coverAlt",
    "publishedAt", "upsert",
]

# ---------------------------------------------------------------
# body 編譯層（決策 01）
# ---------------------------------------------------------------
# 【唯一需要對齊後台的地方】
# 這裡輸出的是中性 block 結構（blocks-v1）。若後台編輯器其實用 Tiptap /
# ProseMirror / Lexical 或自有 schema，只要改 compile_body() 這一個函式，
# 閘門、模板、快照、簽核流程都不用動。第一篇請用 draft 發出並在後台目視
# 排版，把真實結構貼回來即可定案。
BODY_ADAPTER = "blocks-v1"


def _clean_inline(s):
    """保留文字，去掉 Markdown 的粗體標記與行內註解。"""
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    return s.replace("**", "").strip()


def compile_body(md, fm):
    """把人讀的 MDX 正文編譯成 JSON blocks（不是字串）。

    可辨識：## 標題、> 引言、| 表格 |、1. 有序清單、- [連結]()、
    **問：...** / 答：... 問答對、一般段落。
    最後由 inject_brand_blocks() 補上三問與統一 CTA。
    """
    blocks, lines = [], md.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        s = line.strip()

        if not s or s.startswith("<!--"):
            i += 1
            continue

        # 表格
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            header = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            blocks.append({"type": "table", "header": header, "rows": rows})
            continue

        # 標題
        m = re.match(r"^(#{2,4})\s+(.*)$", s)
        if m:
            blocks.append({"type": "heading", "level": len(m.group(1)), "text": _clean_inline(m.group(2))})
            i += 1
            continue

        # 引言
        if s.startswith(">"):
            blocks.append({"type": "quote", "text": _clean_inline(s.lstrip("> "))})
            i += 1
            continue

        # 問答對：**問：...** 接 「答：...」
        m = re.match(r"^\*\*問[：:](.+?)\*\*$", s)
        if m:
            q = _clean_inline(m.group(1))
            ans = ""
            if i + 1 < len(lines) and re.match(r"^答[：:]", lines[i + 1].strip()):
                ans = _clean_inline(re.sub(r"^答[：:]\s*", "", lines[i + 1].strip()))
                i += 1
            blocks.append({"type": "qa", "question": q, "answer": ans})
            i += 1
            continue

        # 有序清單
        m = re.match(r"^\d+\.\s+(.*)$", s)
        if m:
            items = []
            while i < len(lines):
                mm = re.match(r"^\s*\d+\.\s+(.*)$", lines[i])
                if not mm:
                    break
                items.append(_clean_inline(mm.group(1)))
                i += 1
            blocks.append({"type": "orderedList", "items": items})
            continue

        # 連結清單：- [文字](/path/)
        m = re.match(r"^[-*]\s+\[(.+?)\]\((.+?)\)\s*$", s)
        if m:
            items = []
            while i < len(lines):
                mm = re.match(r"^[-*]\s+\[(.+?)\]\((.+?)\)\s*$", lines[i].strip())
                if not mm:
                    break
                items.append({"text": _clean_inline(mm.group(1)), "href": mm.group(2)})
                i += 1
            blocks.append({"type": "links", "items": items})
            continue

        # 一般清單
        m = re.match(r"^[-*]\s+(.*)$", s)
        if m:
            items = []
            while i < len(lines):
                mm = re.match(r"^[-*]\s+(.*)$", lines[i].strip())
                if not mm:
                    break
                items.append(_clean_inline(mm.group(1)))
                i += 1
            blocks.append({"type": "list", "items": items})
            continue

        # 一般段落（合併到空行為止）
        para = [s]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{2,4}\s|>\s|\||\d+\.\s|[-*]\s|\*\*問[：:]|<!--)", lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        blocks.append({"type": "paragraph", "text": _clean_inline(" ".join(para))})

    return inject_brand_blocks(blocks)


def inject_brand_blocks(blocks):
    """API 沒有三問／CTA 欄位，由管線在 JSON 結構尾端注入【唯一且全站一致】的 brand block。

    文案一律取自 brand_gate.BRAND_TRUST_SPEC（單一來源），不讀 frontmatter，
    避免單篇自訂造成三問區不一致。改文案請改規格，不要改這裡。
    """
    spec = brand_gate.BRAND_TRUST_SPEC
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "brand",
        "heading": spec["heading"],
        "whatWeDo": spec["whatWeDo"],
        "whyTrust": spec["whyTrust"],
        "howToJoin": spec["howToJoin"],
        "cta": spec["cta"],
        "links": [dict(x) for x in spec["links"]],
    })
    return {"format": BODY_ADAPTER, "blocks": blocks}


def inject_brand_block_text(md):
    """相容用：--body-format markdown/html 時同樣只吃單一來源規格。"""
    spec = brand_gate.BRAND_TRUST_SPEC
    links = "　|　".join(f"[{x['text']}]({x['href']})" for x in spec["links"])
    block = (
        f"\n\n---\n\n## {spec['heading']}\n\n"
        f"**我們在做什麼**　{spec['whatWeDo']}\n\n"
        f"**憑什麼相信**　{spec['whyTrust']}\n\n"
        f"**怎麼加入**　{spec['howToJoin']}\n\n"
        f"**{spec['cta']}**　|　{links}\n"
    )
    return md.rstrip() + block


# ---------------------------------------------------------------
def die(msg, code=2):
    print(f"[停止] {msg}", file=sys.stderr)
    sys.exit(code)


def get_token():
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        die(f"未設定環境變數 {TOKEN_ENV}。\n"
            f"      請在「執行這支腳本的環境」設定（本機 export／~/.zshrc／.env），\n"
            f"      或包成 WorkBuddy 自訂連接器由表單填入。詳設計書第拾章。\n"
            f"      不要貼在對話或寫進程式碼。")
    return token


def cmd_env(args):
    """自檢 Token 是否讀得到，且不印出內容。"""
    raw = os.environ.get(TOKEN_ENV)
    print(f"環境變數名稱：{TOKEN_ENV}")
    if raw is None:
        print("狀態：未設定　→　請先設定後再跑 list／publish")
        return 1
    token = raw.strip()
    if not token:
        print("狀態：已設定但為空　→　請填入實際 Token")
        return 1
    masked = token[:2] + "*" * max(0, len(token) - 4) + token[-2:] if len(token) > 4 else "****"
    print(f"狀態：已讀到（長度 {len(token)}）　遮罩：{masked}")
    if raw != token:
        print("提醒：值的前後有空白，用戶端已自動去除；建議修正來源。")
    if len(token) < 32:
        print("警告：長度不足 32 字元。API 會把太短的 Token 當成「未設定」而回 503。")
        print("      請兩端同步換成 ≥32 字元，Vercel 改值後記得 Redeploy。")
        return 1
    print("來源：程式碼／對話／Git 皆不含此值（用戶端只從 os.environ 讀）。")
    print("下一步：python3 wiki_publisher.py list　（能回 200 即代表設定正確）")
    return 0


def api_call(method, base, token, payload=None):
    """呼叫 API。POST 失敗不重試，避免重複發文。"""
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(base, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"error": raw[:300]}
        return e.code, body
    except error.URLError as e:
        return 0, {"error": f"連線失敗：{e.reason}"}


def api_upload_image(base, token, file_path):
    """上傳封面圖：POST /api/wiki/images（multipart/form-data，僅接受 WebP）。

    回傳 (status, body)；成功 201 含 url／absoluteUrl／width／height。
    """
    p = Path(file_path)
    if not p.exists():
        return 0, {"error": f"檔案不存在：{p}"}
    data = p.read_bytes()
    boundary = "----WikiPublisherBoundary9f2c1a"
    parts = [
        ("file", p.name, "image/webp", data),
    ]
    buf = io.BytesIO()
    for name, filename, ctype, blob in parts:
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
        buf.write(f"Content-Type: {ctype}\r\n\r\n".encode())
        buf.write(blob + b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode())
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }
    # base 是发文端点（…/api/wiki/articles）；图片端点为其上级目录下的 images
    img_base = base.rstrip("/")
    if img_base.endswith("/articles"):
        img_base = img_base[: -len("/articles")]
    req = request.Request(img_base + "/images", data=buf.getvalue(), headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"error": raw[:300]}
        return e.code, body
    except error.URLError as e:
        return 0, {"error": f"連線失敗：{e.reason}"}


def cmd_upload_image(args):
    token = get_token()
    if not token:
        print("[中止] 環境變數 WIKI_API_TOKEN 未設定或為空；先跑 env 自檢。")
        return 1
    code, body = api_upload_image(DEFAULT_BASE, token, args.file)
    if code == 201:
        print("[成功] 圖片已上傳 (201)")
        print(json.dumps(body, ensure_ascii=False, indent=2))
        print("發文請把 coverImage 填入：", body.get("url") or body.get("absoluteUrl"))
        return 0
    print(f"[失敗] HTTP {code}", human_http_error(code, body) if isinstance(body, dict) else body)
    return 1


def human_http_error(code, body):
    msg = body.get("error", "") if isinstance(body, dict) else str(body)
    if code == 400 and "分類" in msg:
        return ("欄位有誤。API 回覆：" + msg
                + "　→ 代表 API 端的 category 允許清單還沒有這個值"
                  "（決策 02 第 5 類 key=fieldtrip；若剛合併 PR，請確認已部署到正式站）。"
                  "請先到後台新增分類／讓後端把值加進允許清單並 Redeploy，"
                  "再原檔重跑 list → check → publish --confirm；"
                  "不要改用其他 category 繞過，也不要 --upsert。")
    hints = {
        400: "欄位有誤。請跑 check 看 G9 契約與 JSON 編譯結果；API 回覆：" + msg,
        401: ("Token 錯或過期（API 原文：" + msg + "）。請確認客戶端 " + TOKEN_ENV
              + " 與 Vercel 伺服器端設的值完全一致，並跑 env 自檢。"),
        409: "Slug 重複。這是冪等保護，不是錯誤——若要覆寫舊文章才加 --upsert（會覆蓋已發布內容，高風險）。",
        503: ("API 規定 " + TOKEN_ENV + " 至少 32 字元；長度不足會被當成「未設定」，"
              "因此回「伺服器尚未設定 WIKI_API_TOKEN。」——錯誤訊息把「太短」與"
              "「未設定」混在一起，別只查「有沒有設」。"
              "請確認【兩端】都用同一組 ≥32 字元的 Token，Vercel 改值後要 Redeploy；"
              "若已 ≥32 仍 503，再依序查 Production 勾選／正確 Project／變數名。"
              "API 原文：" + msg),
    }
    return hints.get(code, f"HTTP {code}：{msg}")


# ---------------------------------------------------------------
# MDX → API payload
# ---------------------------------------------------------------
def split_frontmatter(text):
    m = re.match(r"^---\s*\n.*?\n---\s*\n?(.*)$", text, re.S)
    return (m.group(1) if m else text).strip()


def as_bool(v, default=False):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def build_payload(path, text, allow_publish=False, force_upsert=None,
                  body_format="markdown", body_stringify=False):
    findings, fm = brand_gate.check(path, text)
    blocks = [f for f in findings if f[0] == "BLOCK"]
    if blocks:
        return None, findings, fm, None

    md = split_frontmatter(text)
    if body_format == "json":   # blocks-v1（2026-11-20 決策 01）；2026-11-21 後台定案 Markdown，此路徑保留為歷史／相容
        body = compile_body(md, fm)
        if body_stringify:
            body = json.dumps(body, ensure_ascii=False)
    else:
        body = inject_brand_block_text(md)

    status = fm.get("status", "draft")
    if status == "review":          # 本地審稿態 → API 只能存草稿
        status = "draft"
    if not allow_publish:           # 安全預設：沒 --publish 一律草稿
        status = "draft"

    payload = {
        "title": fm["title"],
        "slug": fm["slug"],
        "category": fm["category"],
        "body": body,
        "status": status,
        "metaDescription": fm.get("metaDescription", ""),
        "metaTitle": fm.get("metaTitle", ""),
        "metaKeywords": fm.get("metaKeywords", ""),
        "tags": fm.get("tags", []) if isinstance(fm.get("tags"), list) else [],
        "coverImage": fm.get("coverImage", ""),
        "coverAlt": fm.get("coverAlt", ""),
        "publishedAt": fm.get("publishedAt", ""),
        "upsert": force_upsert if force_upsert is not None else as_bool(fm.get("upsert", False)),
    }
    # 空值不送，避免 API 視為欄位有誤
    payload = {k: v for k, v in payload.items()
               if v not in ("", [], None) or k in ("title", "slug", "category", "body", "status")}
    return payload, findings, fm, body_format


def final_scan(payload):
    """G10：把真正送出去的 JSON body 序列化後再掃一次，避免編譯層漏網。"""
    serialized = json.dumps(payload.get("body"), ensure_ascii=False)
    findings = []
    brand_gate.scan_text("送出前 JSON body", serialized, findings)
    return [f for f in findings if f[0] == "BLOCK"]


# ---------------------------------------------------------------
def write_snapshot(payload, api_body, backup_dir, source_path):
    """決策 03：POST 成功後寫一份內文快照（GET 不含內文，這份就是備份）。"""
    d = Path(backup_dir)
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = d / f"{payload['slug']}.{ts}.published.json"
    doc = {
        "_meta": {
            "snapshotAt": ts,
            "sourceMdx": str(source_path),
            "adapter": BODY_ADAPTER,
            "apiResponse": api_body,
            "note": "內文備份；含完整 body JSON。不含 Token。請連同 .mdx 一起進 Git。",
        },
        "payload": payload,
    }
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def preview_payload(payload):
    """預覽時只秀 body 的結構摘要，不把整篇 JSON 倒出來。"""
    p = dict(payload)
    b = p.get("body")
    if isinstance(b, dict):
        types = {}
        for blk in b.get("blocks", []):
            types[blk.get("type", "?")] = types.get(blk.get("type", "?"), 0) + 1
        p["body"] = {
            "format": b.get("format"),
            "blocks": f"{len(b.get('blocks', []))} 個（略）",
            "組成": types,
            "含三問與 CTA": any(x.get("type") == "brand" for x in b.get("blocks", [])),
        }
    elif isinstance(b, str) and b.lstrip().startswith("{"):
        p["body"] = b[:120].replace("\n", " ") + " …（JSON 字串，略）"
    elif isinstance(b, str):
        p["body"] = b[:160].replace("\n", " ") + " …（略，共 %d 字）" % len(b)
    return p


# ---------------------------------------------------------------
def cmd_list(args):
    token = get_token()
    code, body = api_call("GET", args.base_url, token)
    if code != 200:
        die(human_http_error(code, body))
    items = body if isinstance(body, list) else (
        body.get("articles") or body.get("data") or body.get("items") or []
    )
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    print(f"共 {len(items)} 篇文章（GET 不含內文）")
    print("-" * 78)
    print(f"{'slug':<38} {'status':<12} title")
    print("-" * 78)
    for it in items:
        if not isinstance(it, dict):
            continue
        print(f"{str(it.get('slug',''))[:37]:<38} {str(it.get('status',''))[:11]:<12} {it.get('title','')}")
    print("-" * 78)
    print("提示：發文前先跑一次 list，確認 slug 沒撞、也確認上一篇有沒有真的寫入。")
    return 0


def run_gate(path):
    text = Path(path).read_text(encoding="utf-8")
    findings, fm = brand_gate.check(path, text)
    report, code = brand_gate.render_report(path, findings, fm)
    print(report)
    return text, findings, fm, code


def cmd_check(args):
    exit_code = 0
    for path in args.files:
        text, findings, fm, code = run_gate(path)
        payload, _, _, _ = build_payload(
            path, text, allow_publish=args.publish,
            body_format=args.body_format, body_stringify=args.body_stringify,
        )
        if payload is None:
            print("→ 閘門未通過，不產生 payload。\n")
            exit_code = 1
            continue
        bad = final_scan(payload)
        if bad:
            print(f"→ 送出前複掃（G10）攔下 {len(bad)} 項，不產生 payload：")
            for _, g, m in bad[:10]:
                print(f"   · [{g}] {m}")
            exit_code = 1
            continue
        print("[G10 送出前複掃] PASS　編譯後 JSON body 無違禁詞／簡體／Emoji")
        print("\n轉換後的 API payload（不含 Token；body 為 JSON 結構）：")
        print(json.dumps(preview_payload(payload), ensure_ascii=False, indent=2))
        print(f"\n送出後狀態：{payload['status']}　|　upsert={payload.get('upsert', False)}"
              f"　|　body 型別={type(payload['body']).__name__}")
        print("（check 為乾跑，未發出任何請求）\n")
    return exit_code


def cmd_publish(args):
    if not args.confirm:
        print("[乾跑模式] 未加 --confirm，以下只預覽，不會發出請求。\n")
    token = get_token() if args.confirm else None

    exit_code = 0
    for path in args.files:
        print("=" * 70)
        text, findings, fm, gate_code = run_gate(path)
        payload, _, fm2, fmt = build_payload(
            path, text, allow_publish=args.publish,
            force_upsert=True if args.upsert else None,
            body_format=args.body_format, body_stringify=args.body_stringify,
        )
        if payload is None:
            print("→ 閘門 BLOCK，跳過此篇（未發出請求）。\n")
            exit_code = 1
            continue
        bad = final_scan(payload)
        if bad:
            print(f"→ 送出前複掃（G10）BLOCK {len(bad)} 項，未發出請求。")
            exit_code = 1
            continue

        print(f"\n目標：{args.base_url}")
        print(f"slug={payload['slug']}　status={payload['status']}　upsert={payload.get('upsert', False)}"
              f"　簽核={fm2.get('reviewedBy') or '無'}　body={type(payload['body']).__name__}")
        if not args.confirm:
            print(json.dumps(preview_payload(payload), ensure_ascii=False, indent=2))
            print("→ 乾跑結束。確認無誤後加 --confirm 才會真的送出。\n")
            continue

        code, body = api_call("POST", args.base_url, token, payload)
        if code in (200, 201):
            label = "新增成功 (201)" if code == 201 else "更新成功 (200)"
            print(f"[成功] {label}")
            print(json.dumps(body, ensure_ascii=False, indent=2))
            if body.get("url"):
                print(f"網址：{body['url']}")
            snap = write_snapshot(payload, body, args.backup_dir, path)
            print(f"[備份] 已寫入內文快照：{snap}")
            print("       請把來源 .mdx 與此快照一起 git add（決策 03）。")
        else:
            print(f"[失敗] {human_http_error(code, body)}")
            print("已停止，不自動重試。請先跑 list 確認是否已寫入，再決定是否 --upsert。")
            exit_code = 1
        print()
    return exit_code


def main():
    ap = argparse.ArgumentParser(
        description="戰國魂攻城團 wiki 發文客戶端（先過品牌閘門、編譯 JSON，才 POST）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--base-url", default=os.environ.get("WIKI_API_BASE", DEFAULT_BASE),
                    help="API 端點（可用環境變數 WIKI_API_BASE 指向測試環境）")
    ap.add_argument("--body-format", default="markdown", choices=["json", "markdown", "html"],
                    help="body 格式；2026-11-21 後台定案 markdown（預設），json 為舊決策 01 相容保留")
    ap.add_argument("--body-stringify", action="store_true",
                    help="把 JSON 結構轉成字串再送（僅 --body-format json 時使用）")
    ap.add_argument("--backup-dir", default="backups",
                    help="POST 成功後的內文快照目錄（決策 03，預設 backups/）")

    # 共用參數也註冊到子命令，讓「放在子命令前或後」都能用。
    # default=SUPPRESS 確保子命令不會用預設值覆蓋掉主命令已解析的值。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-url", default=argparse.SUPPRESS)
    common.add_argument("--body-format", default=argparse.SUPPRESS, choices=["json", "markdown", "html"])
    common.add_argument("--body-stringify", action="store_true", default=argparse.SUPPRESS)
    common.add_argument("--backup-dir", default=argparse.SUPPRESS)

    sub = ap.add_subparsers(dest="cmd", required=True)

    p_env = sub.add_parser("env", parents=[common], help="自檢 Token 有沒有讀到，不印出值")
    p_env.set_defaults(func=cmd_env)

    p_list = sub.add_parser("list", parents=[common], help="GET 列出所有文章（不含內文）")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_check = sub.add_parser("check", parents=[common], help="只跑閘門＋G10 複掃＋預覽 payload，不發送")
    p_check.add_argument("files", nargs="+")
    p_check.add_argument("--publish", action="store_true", help="預覽 status: published 的情境")
    p_check.set_defaults(func=cmd_check)

    p_pub = sub.add_parser("publish", parents=[common], help="發文（預設乾跑，需 --confirm 才真的 POST）")
    p_pub.add_argument("files", nargs="+")
    p_pub.add_argument("--confirm", action="store_true", help="真的發出 POST；未加一律乾跑")
    p_pub.add_argument("--publish", action="store_true", help="允許 status: published 直接上線")
    p_pub.add_argument("--upsert", action="store_true", help="覆寫同 slug 舊文（高風險）")
    p_pub.set_defaults(func=cmd_publish)

    p_img = sub.add_parser("upload-image", parents=[common],
                           help="上傳封面圖到 /api/wiki/images（僅 WebP），回傳 coverImage 用的 url")
    p_img.add_argument("file", help="WebP 檔案路徑")
    p_img.set_defaults(func=cmd_upload_image)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
