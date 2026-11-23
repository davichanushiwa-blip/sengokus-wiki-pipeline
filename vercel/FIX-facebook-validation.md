# 紧急：`/api/wiki/facebook` 缺少参数校验（已造成 2 条误发贴文）

> 2026-11-23 13:26 实测记录。WorkBuddy 侧只按 v0 指定跑「拒绝路径」测试，结果**两条应当返回 400 的请求返回了 201 并真实发到专页**。

## 一、实测证据

| 测试 | 请求体 | 预期 | 实际 |
|---|---|---|---|
| 非法链接 | `{"message":"test","link":"https://evil.example.com/x"}` | 400 | **201**，postId `204162699682570_1480741387497567` |
| 缺 link | `{"message":"test"}` | 400 | **201**，postId `204162699682570_1480741437497562` |

需删除的贴文：
- https://www.facebook.com/204162699682570_1480741387497567
- https://www.facebook.com/204162699682570_1480741437497562

## 二、根因

route 只做了 Token 比对就直送 Graph API，缺少：

1. `link` 必填 + 域名白名单（必须 `wiki.sengokus.jp`）——当前任何外链都会被发出去，等于把专页变成任意链接的跳板
2. `message` 必填 + 长度上限（FB feed 上限 63206，建议 5000）
3. 请求体 JSON 解析失败时的显式 400

## 三、修复（三处，可直接贴进现有实现）

```ts
// 1) 解析失败显式 400（多数实现会静默把 body 当空对象）
let body: { message?: string; link?: string };
try { body = await request.json(); }
catch { return Response.json({ error: "invalid json" }, { status: 400 }); }

// 2) 必填与长度
const message = (body.message ?? "").trim();
const link = (body.link ?? "").trim();
if (!message || !link) return Response.json({ error: "message 与 link 为必填" }, { status: 400 });
if (message.length > 5000) return Response.json({ error: "message 超过 5000 字元" }, { status: 400 });

// 3) 域名白名单（关键：避免专页被用作外链跳板）
let u: URL;
try { u = new URL(link); } catch { return Response.json({ error: "link 格式错误" }, { status: 400 }); }
const ALLOWED = new Set(["wiki.sengokus.jp"]);
if (!ALLOWED.has(u.host)) return Response.json({ error: "link 必须指向 wiki.sengokus.jp" }, { status: 400 });
```

## 四、建议顺手加一个删除端点（便于清理与撤回）

```
DELETE /api/wiki/facebook?postId=<id>
→ 调 DELETE https://graph.facebook.com/v21.0/<postId>?access_token=<FB_PAGE_ACCESS_TOKEN>
→ 200 {"ok":true}
```

有了它，误发可一键撤回，不必每次进专页后台点删。

## 五、修复后的验收（WorkBuddy 侧会重跑）

| 请求 | 预期 |
|---|---|
| 无 Token / 错 Token | 401 |
| `{"message":"x","link":"https://evil.example.com/"}` | **400**（当前是 201） |
| `{"message":"x"}` | **400**（当前是 201） |
| `{"message":"<正式文案>","link":"https://wiki.sengokus.jp/articles/<slug>/"}` | 201 |

在修复上线前，WorkBuddy **不会**把排程升级为自动发 FB——否则排程一旦出现畸形 payload，同样会直接发出去，且无法撤回。
