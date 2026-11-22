# Facebook 全自動發文：啟用清單

排程任務（#16097307）已加入 FB 文案產生步驟（半自動）。升級到全自動需完成以下 4 步。

## 已完成

- [x] Meta App 已建立（App ID／Secret 存本地 `.env`，gitignored）
- [x] `fb_token_setup.py`：在你電腦跑，短期 Token → 長期 Page Token
- [x] `vercel/app/api/facebook/post/route.ts`：發文 route 代碼（本目錄）
- [x] 排程任務已含 FB 文案產生（每次產稿後自動輸出 `facebook/<slug>.txt`）

## 待完成（按順序）

### 1. 產生 Page Access Token（你，約 5 分鐘）

1. 開 https://developers.facebook.com/tools/explorer/ → 右上選 App（1466447862289614）
2. 勾權限：`pages_show_list`、`pages_manage_posts`、`pages_read_engagement`
3. 產生短期 User Token（1–2 小時有效）
4. 把本專案帶回電腦，跑：
   ```
   python3 fb_token_setup.py --short-token "EAAx……"
   ```
   它會自動：換長期 Token → 列專頁 → 取 Page Token → 寫進 `.env` → 唯讀測試

### 2. 部署 route（你／技術方）

1. 把 `vercel/app/api/facebook/post/route.ts` 放進 wiki 站 repo 的對應路徑
2. Vercel → Settings → Environment Variables 新增：
   - `FB_PAGE_TOKEN`（fb_token_setup.py 產出）
   - `FB_PAGE_ID`（同一支腳本會列給你）
3. 部署到 Production

### 3. 驗證（我來）

- 用 `curl` 打 `https://wiki.sengokus.jp/api/facebook/post` 帶 Token + 測試文案
- 確認 201 且貼文出現在專頁（可用測試貼文，發完刪除）
- 驗證 401（錯 Token）／400（缺欄位）／400（非 wiki 網域連結）三種拒絕路徑

### 4. 排程升級（我來）

驗證通過後，把排程任務 #16097307 的第六步改成：

> 文案產生後，若文章已是 published 狀態（或你簽核上線時），呼叫
> `POST https://wiki.sengokus.jp/api/facebook/post`（帶 WIKI_API_TOKEN）
> 發出貼文，並把 permalink 寫進報告；FB 端失敗不阻斷、不重試超過一次。

## 紅線（沿用）

- FB 貼文同樣過 G1 違禁詞標準（Meta 廣告政策也查絕對化用語）
- 發文時間：wiki 上線 + 30 分鐘（先讓 wiki 被搜尋引擎抓首發）
- Token 不進 Git、不貼對話；App Secret 驗證全通後記得在 Meta 後台重設
  （舊值曾貼進對話）
