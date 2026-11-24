#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
digest_publish.py — 週報「本週天下大事」發布管線
================================================
資料來源：GET /api/wiki/digest?days=7（Bearer WIKI_API_TOKEN，v0 提供）
輸出：articles/<slug>.mdx（status: draft）→ 品牌閘門 → （可選）發後台草稿

用法：
    python3 digest_publish.py                 # 產 MDX + 跑閘門（不發文）
    python3 digest_publish.py --publish-draft # 額外發後台草稿（仍需人工簽核上線）
    python3 digest_publish.py --days 14       # 改抓 14 天

設計原則（與 wiki_publisher.py 一致）：
  - POST 失敗不自動重試超過一次；不 upsert 已存在者除非 --upsert
  - Token 只從環境變數讀，不落任何檔案
  - category 預設 history（週報屬歷史戰役記錄；如後台新增 digest 分類可改 --category）
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

BASE_DIGEST = "https://wiki.sengokus.jp/api/wiki/digest"
BASE_ARTICLES = "https://wiki.sengokus.jp/api/wiki/articles"
DEFAULT_CATEGORY = "history"
DEFAULT_COVER = "/media/articles/13-weekly-cover.webp"  # 週報固定封面（首週上傳後沿用）
TOKEN_ENV = "WIKI_API_TOKEN"


def get_token():
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        sys.exit(
            f"[X] 未設定環境變數 {TOKEN_ENV}。\n"
            "    降級模式請用 --no-api：只產 MDX 與閘門，不發後台。"
        )
    return token


def fetch_digest(token, days):
    url = f"{BASE_DIGEST}?days={days}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:200]
        sys.exit(f"[X] 週報 API 回 {e.code}：{body}")
    except Exception as e:
        sys.exit(f"[X] 無法連線週報 API：{e}")


def build_frontmatter(d, category, cover):
    title = d["title"]
    slug = d["slug"]
    excerpt = d["excerpt"].replace("\n", " ")
    kw = "天下大事,週報,勢力排名,玩家合戰,戰國魂の野望"
    date = d["period"]["from"][:10]
    return f"""---
title: {title}
slug: {slug}
category: {category}
status: draft
metaTitle: {title}｜戰國魂攻城團
metaDescription: {excerpt}
metaKeywords: {kw}
tags:
  - 天下大事
  - 週報
  - 勢力排名
  - 玩家合戰
coverImage: {cover}
coverAlt: 戰國繪卷風格的每週天下大勢插畫
publishedAt: {date}T11:30:00+08:00
upsert: true
date: {date}
layer: L1
keywordLayer: long-tail
targetKeyword: 天下大事週報
canonical: https://wiki.sengokus.jp/articles/{slug}/
brand: 戰國魂攻城團
game: 戰國魂の野望
schemaType: Article
# 【全站統一三問區】文案唯一來源＝brand_gate.BRAND_TRUST_SPEC，單篇不得自訂
whatWeDo: 戰國魂攻城團以攻略百科、旬戰報與實地走訪，把日本戰國世界觀立體化；附屬遊戲《戰國魂の野望》為其中一環。
whyTrust: 內容以可查證的史料、遊戲規則條目與團員實地走訪紀錄為依據，標註推論與史實的界線，並附對應條目與路線供查核。
howToJoin: 於 wiki 首頁點選「立即進入戰國世界」建立武將，或加入攻城團實地走訪社群。
cta: 立即進入戰國世界
related:
  - battle-five-stages
  - economy-gold-rice
  - logistics-two-ku-famine
author: 史官
reviewedBy: 品牌守護者
reviewedAt: {date}
utm: utm_source=wiki&utm_medium=article&utm_campaign=weekly&utm_content={date}
lang: zh-Hant
hreflang: zh-Hant
bodyFormat: markdown
---

"""


def wrap_body(d, raw):
    """把週報 API 的 body 包進全站統一結構：結論 → 原文 → 常見問題 → 同主題推薦。"""
    counts = d.get("counts", {})
    events = counts.get("events", "—")
    battles = counts.get("battles", "—")
    excerpt = d.get("excerpt", "").strip()
    return f"""## 結論

{excerpt} 本週共 {events} 件大事、{battles} 場玩家合戰，全部由遊戲內 AI 大名與玩家即時打出；單場戰果可在合戰記錄頁逐條查核。

{raw.strip()}

## 常見問題

**問：這些事件是真人打出來的嗎？**
答：是。排名、領國與合戰結果全部來自遊戲世界日誌，由 AI 大名與玩家在同一個伺服器即時產生，沒有預寫劇本。

**問：單場合戰的細節在哪裡看？**
答：到[合戰記錄頁](/battles/)，最近 60 場的「國名合戰：A 家對 B 家」逐場可查。

**問：週報多久更新一次？**
答：每週更新一次，固定涵蓋過去 7 天的世界大事、勢力排名與玩家合戰。

**問：我也想讓名字出現在週報裡，怎麼加入？**
答：於 wiki 首頁點選「立即進入戰國世界」建立武將，出陣作戰即可留下戰績。

## 同主題推薦

- [野戰五階段：從布陣到天下布武](/battle/)
- [金米經濟：秋收春荒與物價波動](/economy/)
- [合戰記錄：最近 60 場](/battles/)
"""


def write_snapshot(slug, digest, note):
    import datetime
    os.makedirs("backups", exist_ok=True)
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = f"backups/{slug}.{ts}.draft.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"slug": slug, "title": digest["title"], "note": note,
                   "counts": digest.get("counts"), "period": digest.get("period"),
                   "facebookMessage": digest.get("facebookMessage")}, f, ensure_ascii=False, indent=2)
    print(f"[備份] 已寫入 {path}")


def main():
    ap = argparse.ArgumentParser(description="週報「本週天下大事」發布管線")
    ap.add_argument("--days", type=int, default=7, help="抓取天數（預設 7）")
    ap.add_argument("--category", default=DEFAULT_CATEGORY, help=f"分類（預設 {DEFAULT_CATEGORY}）")
    ap.add_argument("--cover", default=DEFAULT_COVER, help="固定封面路徑")
    ap.add_argument("--publish-draft", action="store_true", help="發後台草稿（仍為 draft，不上線）")
    ap.add_argument("--upsert", action="store_true", help="slug 已存在時更新（預設不更新）")
    ap.add_argument("--no-api", action="store_true", help="降級：不連任何 API，只產 MDX 與閘門")
    args = ap.parse_args()

    if args.no_api:
        sys.exit("[X] --no-api 需要本地快照來源，本工具依賴週報 API，請改在有網路環境執行。")

    token = get_token()
    print(f"[1/4] 抓取週報（days={args.days}）…")
    d = fetch_digest(token, args.days)
    counts = d.get("counts", {})
    print(f"      {d['title']}｜{counts.get('events','?')} 件大事、{counts.get('battles','?')} 場合戰")

    print("[2/4] 產生 MDX …")
    mdx_path = f"articles/{d['slug']}.mdx"
    os.makedirs("articles", exist_ok=True)
    with open(mdx_path, "w", encoding="utf-8") as f:
        f.write(build_frontmatter(d, args.category, args.cover))
        f.write(wrap_body(d, d["body"]) + "\n")
    print(f"      {mdx_path}")

    print("[3/4] 品牌閘門 G1–G10 …")
    r = subprocess.run([sys.executable, "wiki_publisher.py", "check", mdx_path])
    if r.returncode != 0:
        sys.exit("[X] 閘門未過，已停止。請依清單修正（不得繞過閘門）。")

    fb = d.get("facebookMessage", "")
    if fb:
        os.makedirs("facebook", exist_ok=True)
        with open(f"facebook/{d['slug']}.txt", "w", encoding="utf-8") as f:
            f.write(fb + "\n")
        print(f"[FB]  文案已存 facebook/{d['slug']}.txt（上線後由主會話呼叫發文 API）")

    if not args.publish_draft:
        write_snapshot(d["slug"], d, "draft-not-published")
        print("\n[完成] MDX 與 FB 文案已就緒（未發後台）。簽核後：")
        print(f"  python3 wiki_publisher.py publish {mdx_path} --confirm --upsert   # 上線（--publish 由人工決定）")
        return

    print("[4/4] 發後台草稿 …")
    env = dict(os.environ)
    cmd = [sys.executable, "wiki_publisher.py", "publish", mdx_path, "--confirm"]
    if args.upsert:
        cmd.append("--upsert")
    r = subprocess.run(cmd, env=env)
    if r.returncode == 0:
        write_snapshot(d["slug"], d, "draft-published")
        print("\n[完成] 後台草稿已建立（status: draft）。上線與 FB 發佈待人工簽核。")
    else:
        sys.exit("[X] 發後台失敗（不自動重試）。詳見上方 wiki_publisher 輸出。")


if __name__ == "__main__":
    main()
