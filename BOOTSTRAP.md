# BOOTSTRAP：排程沙箱啟動程序（每此執行的第〇步）

> 本 repo 是「戰國魂 wiki 週更自動化」的唯一任務包來源。
> 排程沙箱每次都是全新環境，`/workspace` 是空的——**先完成本步，才准進入第七步流程**。

## 第〇步 自舉（在排程任務 prompt 中已內建）

```bash
# 1) 若 /workspace 已有任務檔（持續沙箱），跳過本步
if [ -f /workspace/wiki_publisher.py ]; then echo "已就緒，跳過自舉"; else

# 2) 淺克隆任務包到臨時目錄
git clone --depth 1 https://github.com/<OWNER>/sengokus-wiki-pipeline.git /tmp/taskpack
#    （私有 repo：排程沙箱若無 Git 憑證，改用 WorkBuddy 自訂連接器注入 GITHUB_TOKEN，
#      clone URL 換成 https://oauth2:${GITHUB_TOKEN}@github.com/<OWNER>/sengokus-wiki-pipeline.git）

# 3) 展開到 /workspace（含腳本／模板／雙隊列 CSV／封面風格基準／規格文件）
cp -r /tmp/taskpack/{*.py,*.md,*.mdx,*.csv,articles,covers,facebook,vercel,seo,.env.example} /workspace/ 2>/dev/null
mkdir -p /workspace/facebook /workspace/backups /workspace/covers/gen

# 4) 自檢：缺任一關鍵檔即停止並報告
for f in wiki_publisher.py brand_gate.py fb_post.py article-template.mdx \
         article-castle-template.mdx content-queue.csv castle-pilgrimage-queue.csv \
         castle-article-spec.md; do
  [ -f /workspace/$f ] || { echo "自舉失敗：缺 $f"; exit 1; }
done
echo "自舉完成"
fi
```

## 憑證（絕不入 repo）

| 憑證 | 來源 | 拿不到時 |
|---|---|---|
| `WIKI_API_TOKEN` | WorkBuddy 自訂連接器／任務環境變數注入 | 只做第一至四步（取題→起草→閘門→FB 文案），輸出 MDX 路徑與報告，不發文 |
| `GITHUB_TOKEN` | WorkBuddy 自訂連接器注入（僅私有 repo 讀取權限） | 若沙箱持續保留 /workspace，僅首次需要 |
| FB 憑證 | 不需要（fb_post.py 離線；自動發 FB 走 Vercel route，見 `vercel/FB-AUTO-SETUP.md`） | — |

## 內容清單

```
wiki_publisher.py          發文管線（env/check/publish/upload-image）
brand_gate.py              品牌閘門 G1–G10（紅線：不得修改）
fb_post.py                 FB 文案產生器（離線）
fb_token_setup.py          FB Page Token 換取工具（在你電腦跑，非沙箱）
article-template.mdx       攻略／歷史／新手骨架
article-castle-template.mdx 名城巡禮骨架（四幕＋三種解讀＋懸念）
castle-article-spec.md     巡禮寫作規格（寫前必讀）
content-queue.csv          W1–W8 選題（16 篇）
castle-pilgrimage-queue.csv 48 城巡禮排程（32 篇）
articles/                  既有 MDX（含示範稿與待簽核草稿）
covers/final/              封面風格基準（1280×720 WebP）
facebook/                  FB 文案範例
weekly-autopublish-runbook.md  六步流程＋失敗處置＋紅線（v1.2）
vercel/                    FB 全自動發文 route 與啟用清單
```

## 版本規則

- repo 是**單一來源**：本會話改了任何檔案 → push 到 repo → 排程下次執行自動拿到新版
- 排程沙箱**只讀**：產出的新 MDX／文案／快照在報告裡回傳路徑，由主會話審核後併回 repo
- 紅線沿用：不修改 brand_gate.py／wiki_publisher.py／BRAND_TRUST_SPEC，不新增 category
