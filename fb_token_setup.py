#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fb_token_setup.py v1.0　戰國魂攻城團｜Facebook Page Access Token 換取工具
================================================================
在哪裡跑：
  ★ 必須在「連得上 graph.facebook.com 的環境」執行（你自己的電腦、或 Vercel）。
    WorkBuddy 沙箱的網路出口到不了 Facebook（2026-11-21 實測 curl／fetch 皆逾時），
    所以這支腳本不是在對話環境跑的。

前置條件：
  1. App 已建好（App ID／Secret 已寫進本目錄的 .env）
  2. 你有一個粉絲專頁，且你是管理員
  3. 到 https://developers.facebook.com/tools/explorer/ 選你的 App，
     勾三個權限產生短期 User Access Token（約 1–2 小時有效）：
       pages_show_list
       pages_manage_posts
       pages_read_engagement

用法（在你自己的電腦上，本目錄整包帶過去）：
  python3 fb_token_setup.py --short-token "EAAx....."

它會做四件事：
  ① 用 App ID＋Secret 把短期 User Token 換成約 60 天的長期 User Token
  ② 列出你管理的所有粉絲專頁（名稱／ID）
  ③ 取得所選專頁的 Page Access Token（用長期 User Token 換出的 Page Token 不會過期）
  ④ 把 FB_PAGE_TOKEN／FB_PAGE_ID 寫回 .env，並做一次唯讀測試

安全規則（與 wiki Token 同一套）：
  · Token 只存 .env，絕不進 Git、絕不貼進對話、絕不寫進任何備份檔
  · 輸出一律遮罩：只顯示前 8 碼
  · App Secret 目前曾貼進對話，全部設定完成並驗證可用後，
    建議到 App 設定 → 基本 → 「重設應用程式密鑰」，再把新值更新到 .env
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

VERSION = "1.0"
GRAPH = "https://graph.facebook.com/v21.0"
REQUIRED_PERMS = ["pages_show_list", "pages_manage_posts", "pages_read_engagement"]


def mask(token):
    return token[:8] + "…（已遮罩）" if token else "(空)"


def load_env(path=".env"):
    env = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def save_env(path, updates):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    out, done = [], set()
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in updates:
            out.append(f"{key}={updates[key]}")
            done.add(key)
        else:
            out.append(line)
    for k, v in updates.items():
        if k not in done:
            out.append(f"{k}={v}")
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def api(path, params):
    url = f"{GRAPH}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "sengokus-fb-token-setup/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"[X] Graph API 回 {e.code}：{body[:300]}")
        if e.code == 400 and "code" in body:
            print("    常見原因：Token 過期／權限未勾／App 沒加該權限。回 Explorer 重新產生 Token 再試。")
        sys.exit(1)
    except Exception as e:
        print(f"[X] 連不上 Graph API：{e}")
        print("    本腳本必須在能存取 Facebook 的網路環境執行（你自己的電腦或 Vercel）。")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="換取 Facebook Page Access Token")
    ap.add_argument("--short-token", required=True, help="Graph API Explorer 產生的短期 User Token")
    ap.add_argument("--env", default=".env", help=".env 路徑（預設當前目錄）")
    a = ap.parse_args()

    env = load_env(a.env)
    app_id, app_secret = env.get("FB_APP_ID"), env.get("FB_APP_SECRET")
    if not app_id or not app_secret:
        print(f"[X] {a.env} 缺 FB_APP_ID／FB_APP_SECRET")
        sys.exit(1)
    print(f"App ID：{app_id}")

    # ① 換長期 User Token
    print("\n① 把短期 User Token 換成長期……")
    r = api("oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": a.short_token,
    })
    long_token = r["access_token"]
    print(f"    長期 User Token：{mask(long_token)}")

    # ② 列專頁
    print("\n② 列出你管理的粉絲專頁……")
    pages = api("me/accounts", {
        "fields": "name,id,access_token",
        "access_token": long_token,
    }).get("data", [])
    if not pages:
        print("[X] 沒有列出任何專頁。確認你是專頁管理員，且 Explorer 有勾 pages_show_list。")
        sys.exit(1)
    for i, p in enumerate(pages, 1):
        print(f"    {i}. {p['name']}（id={p['id']}）")
    idx = 1
    if len(pages) > 1:
        idx = int(input("要接哪一個專頁？輸入編號："))

    page = pages[idx - 1]
    page_token = page["access_token"]
    print(f"\n③ 取得 Page Access Token：{mask(page_token)}")

    # ④ 唯讀測試＋寫回 .env
    print("\n④ 唯讀測試……")
    info = api(page["id"], {"fields": "name,fan_count", "access_token": page_token})
    print(f"    專頁「{info.get('name')}」可讀，粉絲數 {info.get('fan_count')}")

    save_env(a.env, {"FB_PAGE_TOKEN": page_token, "FB_PAGE_ID": page["id"]})
    print(f"\n已寫回 {a.env}：FB_PAGE_TOKEN／FB_PAGE_ID")
    print("\n下一步（由 WorkBuddy 接手）：")
    print("  · 把 .env 的 FB_PAGE_TOKEN 交給發文管線（仍不進 Git、不貼進對話）")
    print("  · 實際發文請在能連 Facebook 的環境跑（Vercel Function 或你的電腦）")
    print("  · 發文端點：POST /{FB_PAGE_ID}/feed?message=貼文&link=文章連結&access_token=FB_PAGE_TOKEN")
    print("  · 全部驗證可用後，記得去 App 設定重設應用程式密鑰（舊密鑰曾貼進對話）")


if __name__ == "__main__":
    main()
