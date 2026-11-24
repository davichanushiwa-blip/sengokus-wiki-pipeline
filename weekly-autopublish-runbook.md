# 戰國魂 wiki 週更 Runbook（每週兩篇）

> 版本 v1.2 · 2026-11-21 · 適用於 `wiki.sengokus.jp` 自動發文管線
> 目標：每週穩定產出 **2 篇**符合品牌規格的文章，且**不失控上線**。
> v1.1 變更：新增「戰國名城巡禮」長期系列（`castle-pilgrimage-queue.csv`，48 城／32 篇排程），
> 週四固定出巡禮篇，結構依 `castle-article-spec.md`（四幕＋三種解讀＋懸念收尾）。
> v1.2 變更：新增 Facebook 半自動同步（決策：半自動＋wiki 上線 30 分鐘後發），
> 規格見 `facebook-post-spec.md`，文案由 `fb_post.py` 產生，你貼進 Meta Business Suite 排程。
> v1.3 變更：升級全自動——v0 已部署 `/api/wiki/facebook`（含校驗與刪文端點，PR #109），
> 首貼 201 驗證通過（2026-11-23）。主會話在 wiki 上線後直接呼叫 route 發 FB，不再走 Business Suite。
> v1.4 變更：新增週報系列——v0 提供 `GET /api/wiki/digest?days=7` 週報 API 與 `/battles/` 合戰公開頁（60 場，
> 已進 sitemap）；`digest_publish.py` 把週報包裝進全站統一規格（結論＋FAQ＋推薦＋三問區，閘門全過），
> 固定封面 `13-weekly-cover.webp` 每週復用。排程任務 **16278605**（週一 11:00）產週報草稿；
> 兩個排程任務的第〇步均已注入 `WIKI_API_TOKEN`（存於任務配置，建議日後在 Vercel 輪換同步）。

---

## 一、分層原則：自動化做到「草稿」，上線永遠留一道人工閘門

| 層級 | 誰做 | 做什麼 | 為什麼不能全自動 |
|---|---|---|---|
| **L1 自動** | 排程任務（每週一／四 09:00） | 取題 → 起草 MDX → G1–G10 → 生封面 → 上傳圖 → **送 `draft`** → 產出審核報告 | 這層無風險：`draft` 不上線、不進 sitemap、搜尋引擎看不到 |
| **L2 人工** | 老闆（5–10 分鐘） | 看審核報告＋後台目視 → 說「發」 | 廣告法與品牌是法律責任，`brand_gate.py` 的 G8 明文規定「不允許無人值守全自動發布」 |
| **L3 自動** | 排程任務／技術方 | 上線後 sitemap 更新、`llms.txt` 更新、百度推送、GA4 | 只做事後收錄，不改內容 |

**一句話**：產能自動化，責任不自動化。

---

## 二、每週節奏

| 時間 | 動作 | 耗時 |
|---|---|---|
| 週一 09:00 | 自動產出第 1 篇 `draft`（含封面、閘門報告） | 0（背景執行） |
| 週一 10:00 | 老闆審核 → 回「發第 1 篇」 | 5 分鐘 |
| 週一 10:05 | 執行 `publish --confirm --publish`，上線 | 1 分鐘 |
| 週四 09:00 | 自動產出第 2 篇 `draft` | 0 |
| 週四 10:00 | 老闆審核 → 上線 | 5 分鐘 |
| 週一／週四 10:10 | `python3 fb_post.py articles/<slug>.mdx` 產 FB 文案 | 0 |
| 週一／週四 10:15 | 貼進 Meta Business Suite → 排程 10:35 發佈 | 1 分鐘 |
| 週五 | 檢查 GA4／Search Console 收錄狀況 | 5 分鐘 |

> 若某一篇審核不通過：退回修改，隔天重送 `draft`，**該週就只發一篇**——寧可少發，不要發錯。

---

## 三、自動化任務做什麼（逐字指令）

排程任務的 prompt 必須包含以下六步，缺一不可：

1. **取題**：先讀 `/workspace/content-queue.csv`（W1–W8 遊戲攻略／歷史／新手）；該表無 pending 時，改讀 `/workspace/castle-pilgrimage-queue.csv`，取 `status=pending` 且 `publish_date` 最早的一行。兩表皆空才停止並報告「隊列已空，請補選題」。
   - 週四若同時有兩表可選，**優先取名城巡禮**（長期系列需要穩定節奏，斷更會影響整條路線的內鏈）。
2. **起草**：依隊列決定骨架——
   - 遊戲攻略／歷史／新手 → `/workspace/article-template.mdx`
   - 名城巡禮（`category: fieldtrip`）→ `/workspace/article-castle-template.mdx`，並逐項對照 `castle-article-spec.md`
   存為 `/workspace/articles/<slug>.mdx`。必須包含：frontmatter 全欄位、三問區（由 `BRAND_TRUST_SPEC` 注入，不可自寫）、FAQ 段、CTA。
3. **閘門**：`python3 brand_gate.py <file>`，必須 G1–G10 全 PASS。有 BLOCK 就改到過，最多改 3 輪；3 輪不過就停，輸出問題清單。
4. **封面**：用墨朱金品牌色產 1280×720 WebP（參考 `covers/final/` 風格），`upload-image` 上傳取 `url`。
5. **發草稿**：`publish <file> --confirm`（**不加 `--publish`**）。確認回 200/201 且 `status: draft`。
6. **報告**：輸出「標題／slug／字數／閘門結果／封面網址／後台連結／待你簽核」，並把 `content-queue.csv` 該行 `status` 改為 `drafted`。

**禁止事項（寫進 prompt）**：不加 `--publish`、不加 `--upsert`、不改 `brand_gate.py`、不改 `BRAND_TRUST_SPEC`、不自行新增 category、不在閘門未過時送出。

### 名城巡禮篇的額外三條

| 要求 | 具體做法 | 為什麼 |
|---|---|---|
| **四幕骨架不可省** | 結論→背景→矛盾→事件→三種解讀→個人觀點→下一次，缺一幕算未完成 | 這是「有深度又能留住普通觀眾」的唯一解：結論先給答案、矛盾段吊住、事件段給畫面 |
| **史料分級必標** | `［史料］`／`［軍記］`／`［通說］`／`［推論］`，每篇至少 3 處 | 歷史讀者退追的主因是把軍記物當正史；標了反而加分 |
| **兵力數字給區間** | 寫「約 7,000–8,000」而非「七千」，並在三種解讀段說明為何有區間 | 城郭研究的數字本就有爭議，寫死等於給自己埋雷 |

**證據不足時**：寫「目前可查到的說法有兩種」，不要補一個看起來合理的數字。寧可留白，不要編。

### Facebook 全自動同步（v1.3 升級，2026-11-23 首貼驗證通過）

文章在 wiki 上線後，`fb_post.py` 會自動組出 FB 貼文文案（反差句＋摘要＋帶 UTM 的文章連結＋標籤），
存到 `facebook/<slug>.txt`，並對文案做 G1／G2 迷你掃描。你的動作只有一個：
把文案貼進 Meta Business Suite、排程在 wiki 上線＋30 分鐘發佈。

| 邊界 | 規則 |
|---|---|
| 誰發佈 | 主會話在 wiki 上線後呼叫 `POST /api/wiki/facebook`（Bearer `WIKI_API_TOKEN`） |
| 校驗 | 服務端已做：連結白名單（sengokus.jp 系）、message/link 必填、長度上限（PR #109） |
| 文案來源 | 排程產 `facebook/<slug>.txt`；首行反差句仍建議人工改寫後再發 |
| 時點 | wiki 上線後即刻（原 30 分鐘錯開規則保留為手動補發時的建議） |
| 刪文 | `DELETE /api/wiki/facebook?postId=<id>`（僅限本專頁貼文） |
| 合規 | 貼文同樣禁絕對化用語與簡體；Meta 廣告政策對「最／第一」也敏感 |
| 失敗處置 | 401＝Token 問題；400＝payload 問題（查文案格式）；502/504＝FB 端，重試不超過一次；失敗不影響 wiki 上線 |

---

## 四、人工審核清單（5 分鐘版）

打開後台該篇草稿，只看六項：

- [ ] 標題是否講清楚「讀者能得到什麼」
- [ ] 首段有沒有具體數字（兵力／旬數／點數）
- [ ] 表格與問答有沒有正常渲染（不是 `[object Object]`）
- [ ] 三問區與 CTA 是否出現且文案與其他篇一致
- [ ] 有沒有絕對化用語（最／第一／唯一／零風險）沒被 G1 抓到
- [ ] 封面圖與內容是否對得上
- [ ]（巡禮篇加驗）四幕齊、三種解讀有三個不同立場、結尾懸念指向排程上的下一座城

全過 → 回「**發**」，我執行 `publish --confirm --publish`。
有任何一項不過 → 指出來，我改 MDX 後重送草稿。

---

## 五、失敗處理

| 現象 | 原因 | 處置 |
|---|---|---|
| `env` 讀不到 Token | 自動化環境無憑證 | 只產出 MDX + 報告，**不發文**，通知補憑證 |
| `list` 回 503 | Token < 32 字元（API 視為未設定） | 換 ≥32 字元的 Token，兩端同值 |
| `list` 回 401 | 兩端 Token 不一致 | 對齊 Vercel 與客戶端 |
| `publish` 回 400「請選擇文章分類」 | category 不在允許清單 | 只用 `history/mechanics/beginner/video/fieldtrip` |
| `publish` 回 409 | slug 已存在 | 改 slug，不自動 `--upsert` |
| 閘門 BLOCK | 內容違規 | 修正後重跑，不繞過 |
| 後台顯示 `[object Object]` | body 送了物件 | 確認 `--body-format markdown`（預設） |
| 巡禮篇「三種解讀」寫成同一立場 | 起草時只找到一種史料 | 退回重寫：補軍記物說法＋學界質疑，或改寫成「目前只有一種記載」並在標題降低承諾 |
| 該城查不到可靠兵力 | 小城史料少 | 不硬寫數字，改用距離、標高、正面寬度等現場可驗證的數據撐首段 |
| Token 401 但指紋與 Vercel 一致 | 從 env.txt 提取時用 `tr -d '"'` 誤刪了 Token 內部的合法 `"` 字元 | 提取規則：`sed -n 's/^WIKI_API_TOKEN=//p' | sed 's/^"//; s/"$//' | tr -d ' \r\n'`——只去首尾引號，保留內部字元；`python3 wiki_publisher.py env` 應顯示長度 40 |

---

## 六、月度複盤（每月最後一個週五）

- 產出篇數 vs 計畫（應為 8 篇）
- 閘門攔截率（攔截數／總數）—— 太高表示起草品質差，需改 prompt
- 收錄率（Search Console 已收錄／已發布）
- AI 引用數（豆包／DeepSeek 搜品牌詞是否出現 wiki 條目）
- 加入轉換（wiki → 遊戲註冊的點擊數）
- 名城巡禮進度（已發／32 篇）、路線篇的內部連結點擊占比
- 巡禮篇的「下一站」點擊率（懸念收尾有沒有效，看這個數字）

依結果調整下一季 `content-queue.csv` 的選題方向。

---

## 七、紅線（任何情況都不破）

1. 不無人值守 `--publish`
2. 不跳過 G1–G10
3. 不改 `BRAND_TRUST_SPEC`（三問文案已定案）
4. 不用 Emoji、不用簡體、不用絕對化用語
5. POST 失敗不自動重試，先 `list` 確認是否已寫入
6. 文章上線前必須有人看過
