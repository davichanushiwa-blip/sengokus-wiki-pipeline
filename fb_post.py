#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fb_post.py v1.0　戰國魂攻城團｜Facebook 貼文文案產生器（半自動路線）
================================================================
用法：
  python3 fb_post.py articles/castle-ueda-sample.mdx
  python3 fb_post.py articles/xxx.mdx --out /workspace/facebook
  python3 fb_post.py articles/xxx.mdx --print-only   # 只印不存檔

做什麼：讀取文章 MDX 的 frontmatter 與結論段，組出符合 facebook-post-spec.md
        的四行貼文文案，存為 facebook/<slug>.txt；並對文案做 G1 違禁詞與
        G2 簡體字的迷你掃描（貼到 Meta Business Suite 前的最後一道網）。

不做什麼：不發佈、不連網、不碰任何 Token。發佈一律由你貼進 Meta Business Suite，
          排程在 wiki 上線後 30 分鐘。
依賴：僅 Python 標準庫；複用 brand_gate.py 的解析器與違禁詞表（單一來源）。
"""

import argparse
import re
import sys
from pathlib import Path

from brand_gate import (BANNED_REGEX, BANNED_TERMS, SIMPLIFIED_CHARS,
                        SIMPLIFIED_WORDS, parse_frontmatter)

VERSION = "1.0"
SITE_BASE = "https://wiki.sengokus.jp/articles"
HASHTAG_CASTLE = "#戰國 #日本史 #名城巡禮"
HASHTAG_DEFAULT = "#戰國魂の野望 #日本戰國 #攻略"


def strip_md(text):
    """去掉 Markdown 痕跡（粗體、連結、反引號），貼文是純文字。"""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.replace("`", "")


def first_sentence_with_digit(text):
    """從一段文字抓出含數字的第一句，作為貼文的「數字行」。"""
    for part in re.split(r"(?<=[。．！？])", strip_md(text)):
        p = part.strip()
        if p and re.search(r"\d", p):
            return p
    return ""


def build_post(fm, body, utm_series):
    """組出四行結構貼文。回傳 (post_text, notes)。"""
    notes = []
    title = fm.get("title", "")
    slug = fm.get("slug", "")
    tags = fm.get("tags") or []
    meta_desc = fm.get("metaDescription", "")

    # 反差句：取標題冒號後的副題，並提醒人工改寫
    hook = title.split("：", 1)[1].strip() if "：" in title else title
    notes.append("反差句目前取自標題副題，貼文前請改寫成問題式或數字對比式（勿與標題同句）")

    # 摘要：metaDescription + 結論段的數字行
    m = re.search(r"## 結論\s*\n(.*?)(?=\n## |\n> )", body, re.S)
    stat = first_sentence_with_digit(m.group(1)) if m else ""
    summary_lines = [strip_md(meta_desc)]
    if stat and not meta_desc.startswith(stat[:8]):
        summary_lines.append(stat)
        notes.append("已附加結論段數字行，請核對該數字在原文可查到")

    if "：" in title:
        notes.append("連結文案指向文章頁，讀者點進去後的三問區與 CTA 由管線統一注入")

    hashtags = HASHTAG_CASTLE if utm_series == "castle_pilgrimage" else HASHTAG_DEFAULT
    extra = [f"#{t}" for t in tags[1:3] if t]
    hashtags = " ".join([hashtags] + extra)

    url = f"{SITE_BASE}/{slug}/?utm_source=facebook&utm_medium=social&utm_campaign={utm_series}"
    lines = [hook, "", "\n".join(summary_lines), "", f"全文：{url}", "", hashtags]
    return "\n".join(lines), notes


def mini_scan(text):
    """貼文文字的 G1／G2 迷你掃描，回傳警告清單。"""
    warns = []
    for term in BANNED_TERMS:
        if term in text:
            warns.append(f"G1：出現違禁詞「{term}」")
    for pat, desc in BANNED_REGEX:
        for m in re.finditer(pat, text):
            warns.append(f"G1：命中{desc}「{m.group(0)}」")
    for w in SIMPLIFIED_WORDS:
        if w in text:
            warns.append(f"G2：出現簡體詞「{w}」")
    chars = sorted({c for c in text if c in SIMPLIFIED_CHARS})
    if chars:
        warns.append(f"G2：出現簡體字「{''.join(chars)}」")
    return warns


def main():
    ap = argparse.ArgumentParser(description="Facebook 貼文文案產生器")
    ap.add_argument("file", help="文章 MDX 路徑")
    ap.add_argument("--out", default="/workspace/facebook", help="輸出目錄")
    ap.add_argument("--print-only", action="store_true", help="只印不存檔")
    a = ap.parse_args()

    src = Path(a.file)
    if not src.exists():
        print(f"[X] 找不到檔案：{src}")
        sys.exit(1)
    text = src.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    if not fm:
        print("[X] 檔案沒有 frontmatter，先過 brand_gate 再來")
        sys.exit(1)

    utm_series = "castle_pilgrimage" if fm.get("category") == "fieldtrip" else "wiki_articles"
    post, notes = build_post(fm, body, utm_series)

    warns = mini_scan(post)

    print("=" * 56)
    print(f"Facebook 貼文文案 v{VERSION}　{src.name}")
    print("=" * 56)
    print(post)
    print("-" * 56)
    for n in notes:
        print(f"· {n}")
    if warns:
        for w in warns:
            print(f"[!] {w}")
        print("判定：先修正上面標 [!] 的項，再貼進 Meta Business Suite")
    else:
        print("判定：PASS　可貼進 Meta Business Suite（記得排程＝wiki 上線＋30 分鐘）")

    if not a.print_only:
        out_dir = Path(a.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{fm.get('slug', src.stem)}.txt"
        out_file.write_text(post + "\n", encoding="utf-8")
        print(f"已存：{out_file}")


if __name__ == "__main__":
    main()
