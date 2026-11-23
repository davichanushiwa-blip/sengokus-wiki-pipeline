// ============================================================================
// Vercel Route：Facebook 粉絲專頁自動發文（全自動升級用）
// ============================================================================
// 部署位置：wiki 站 repo 內（Next.js App Router）
//   正式實作已由 v0 完成：app/api/wiki/facebook/route.ts（/api/facebook/post 為別名）
//   本檔為參考實作，含完整參數校驗（見 /workspace/vercel/FIX-facebook-validation.md）
//
// 用途：沙箱／排程任務連不上 graph.facebook.com，所以 FB 發文由 Vercel
//       （海外節點）代發。排程任務在文章上線後打這個 route。
//
// 需在 Vercel Environment Variables 新增：
//   FB_PAGE_ACCESS_TOKEN = 長期 Page Access Token（fb_token_setup.py 產出，不會過期）
//   FB_PAGE_ID     = 粉絲專頁 ID
//   WIKI_API_TOKEN = 沿用現有值（此 route 用它做呼叫者鑑權，防濫用）
//
// 呼叫方式（排程任務在 wiki 文章上線後執行）：
//   curl -X POST https://wiki.sengokus.jp/api/facebook/post \
//     -H "Authorization: Bearer <WIKI_API_TOKEN>" \
//     -H "Content-Type: application/json" \
//     -d '{"message":"<貼文文案，含連結與標籤>","link":"https://wiki.sengokus.jp/articles/<slug>/"}'
//
// 回應：201 {"id":"<貼文ID>","permalink_url":"..."}
// 失敗：400（缺欄位）／401（鑑權失敗）／502（FB 端錯誤，原樣回傳 error.message）
//
// 安全設計：
//   1. 只收 POST，且必須帶與 Vercel 端一致的 Bearer Token
//   2. message 上限 5000 字元（FB feed 上限 63206，設低一點防濫用）
//   3. link 必須是 wiki.sengokus.jp 網域（FB 貼文一律引流回自家）
//   4. 不落地任何 FB 憑證到程式碼；Token 只從 process.env 讀
// ============================================================================

export const runtime = "nodejs";

const ALLOWED_LINK_HOST = "wiki.sengokus.jp";

export async function POST(request: Request) {
  // 1) 鑑權：與 wiki 發文 API 同一把 Token
  const auth = request.headers.get("authorization") ?? "";
  const token = auth.replace(/^Bearer\s+/i, "").trim();
  if (!token || token !== process.env.WIKI_API_TOKEN) {
    return Response.json({ error: "API Token 無效。" }, { status: 401 });
  }

  // 2) 參數檢查
  let body: { message?: string; link?: string };
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "invalid json" }, { status: 400 });
  }
  const message = (body.message ?? "").trim();
  const link = (body.link ?? "").trim();
  if (!message || !link) {
    return Response.json(
      { error: "message 與 link 為必填。" },
      { status: 400 }
    );
  }
  if (message.length > 5000) {
    return Response.json({ error: "message 超過 5000 字元。" }, { status: 400 });
  }
  let linkUrl: URL;
  try {
    linkUrl = new URL(link);
  } catch {
    return Response.json({ error: "link 格式錯誤。" }, { status: 400 });
  }
  if (linkUrl.host !== ALLOWED_LINK_HOST) {
    return Response.json(
      { error: `link 必須是 ${ALLOWED_LINK_HOST} 網域。` },
      { status: 400 }
    );
  }

  // 3) 發到粉絲專頁 feed（圖文：link 會自動帶出 OG 圖；有封面需求時可另傳 picture）
  const pageId = process.env.FB_PAGE_ID;
  const pageToken = process.env.FB_PAGE_ACCESS_TOKEN;
  if (!pageId || !pageToken) {
    return Response.json(
      { error: "伺服器未設定 FB_PAGE_ACCESS_TOKEN／FB_PAGE_ID。" },
      { status: 503 }
    );
  }

  const params = new URLSearchParams({ message, link, access_token: pageToken });
  const fbRes = await fetch(
    `https://graph.facebook.com/v21.0/${pageId}/feed`,
    { method: "POST", body: params }
  );
  const fbData = (await fbRes.json()) as {
    id?: string;
    error?: { message?: string };
  };

  if (!fbRes.ok || !fbData.id) {
    return Response.json(
      { error: fbData.error?.message ?? "Facebook 發文失敗" },
      { status: 502 }
    );
  }

  const permalink = `https://www.facebook.com/${fbData.id.replace("_", "/posts/")}`;
  return Response.json({ id: fbData.id, permalink_url: permalink }, { status: 201 });
}
