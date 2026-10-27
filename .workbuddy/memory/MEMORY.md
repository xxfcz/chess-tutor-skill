# 项目长期记忆（chess-tutor-skill / chess-coach）

## 仓库地址

| 项目 | 说明 | 仓库 |
|---|---|---|
| ai-chess-wxapp | 微信小程序「黑白格大师」 | https://github.com/xxfcz/ai-chess-wxapp.git |
| ai-chess-server | 自建后端，对外 `chess.imex.de5.net` | https://github.com/xxfcz/ai-chess-server.git |
| ai-chess-web | H5 / Web（本地 `E:\projects\ai-chess`），计划中的 L0 宿主 | https://github.com/xxfcz/ai-chess-web.git |
| chess-tutor-skill | 本仓库，chess-coach（含与 AI Agent 对弈方向） | https://github.com/xxfcz/chess-tutor-skill.git |
| chess_tutor-stefan | 开源参考（GPL-3.0，仅借鉴思路） | https://github.com/xxfcz/chess_tutor-stefan.git |
| chess-Iamsdt | 开源参考 Chess King | https://github.com/xxfcz/chess-Iamsdt.git |
| edmozley/chess | 开源参考（MIT） | https://github.com/edmozley/chess.git |

## 架构定论

- 目标形态：**两个前端（小程序 + H5/Web）、一个 Node.js 后端**，主力逻辑落在自有服务器 `chess.imex.de5.net`。
- `chess.imex.de5.net` 已是小程序线上后端（`remote-engine.js` → `POST {endpoint}/v1`）。探针实测：Stockfish 15.1、**8 进程引擎池**、uptime 稳定。`/v1` 契约不可破坏。
- 共享 L0 基座可行：以 `ai-chess-web/src/chess`（TS）为骨架，吸收小程序 `utils/` 领域逻辑；小程序消费 tsc 编译产物。**先做 L0 本身，在 ai-chess-web 仓库长大**。
- 复用边界：`chess-core`（纯 JS/TS，无 wx/DOM）共享；服务端独有=Stockfish 进程、LLM 调用、Web 托管；微信 UI 层与 wx 绑定层各自实现。
- Python 版 chess-coach 定位=**规范与种子数据**（prompts.md 提示词、分级口径、openings.py 12 开局），不双向分叉。
- 场景平台化：Session / Actor / Intervention / Content 四要素 → Scene = 配置组合（新增场景不改代码）。

## 硬约束

- 微信：新增子域/子路径须到 mp 后台加「request 合法域名」，否则开发者工具绿、真机红。
- LLM/Agent 一律"引擎给候选、模型只挑"（`===DEMO===` 协议思路），**禁止 LLM 自己出着**。
- stefan 为 GPL-3.0，**不可复用代码**，只借鉴 `tacticDetection` 漏着诊断等思路。

## 文档索引

- `docs/后端共享架构方案.md`：自有三项目如何收敛到单 Node.js 后端。
- `docs/开源项目对比与八问重答.md`：外部开源项目头对头对比 + 可取之处清单 + 八问重答（含仓库速查表）。
- `docs/云端自主开发计划书-首夜.md`：可行月球性边界、模块拆分与验收标准、自包含云端任务 prompt。

## 后端 `/v1` 契约要点（2026-10-27 实测，勿再猜）

- `POST https://chess.imex.de5.net/v1`，公网可直连，实测 1.5–3s 返回 200。
- 请求体：`{ fen, depth, maxThinkingTime, variants, searchmoves?, taskId? }`
- **MultiPV 的参数名是 `variants`（1–5），不是 `multipv` / `multiPV` / `MultiPV`**——用错会只回 1 条线。实测 `variants:3` 正确返回 rank1/2/3 三条 `lines`。
- **`maxThinkingTime` 默认仅 50ms**（会截断深度：请求 depth 12 只跑到 8）。需显式设 300–1500。
- `depth` 默认 12，范围 1–30。`depth` 与 `maxThinkingTime` 先到先停。
- 响应顶层是单个对象；`lines[]` 是 MultiPV 数组（`rank/multipv/uci/san/scoreCp/scoreMate/pv/pvSan`）。
- **判错看 `body.type === 'error'`**，不要只看 HTTP 状态码。错误码：`INVALID_FEN` / `ILLEGAL_POSITION` / `GAME_OVER` / `PARAM_OUT_OF_RANGE` / `BUSY` / `RATE_LIMITED` / `QUEUE_FULL` / `ENGINE_UNAVAILABLE` / `ANALYZE_TIMEOUT`；后三者应回落本地引擎。
- 限流 60/min、burst 20，带 `Retry-After`。
- 线上实况：Stockfish **15.1**、pool **8**、`/v1/stats` 与 `/docs/json` 均 404（生产关闭）。仓库 `docs/03-API契约.md` 写的是 SF 17 / pool 4 —— **线上与文档存在版本差，只记录勿擅改**。
- 后端本身是 **TypeScript + Fastify**（`ai-chess-server`，含 `src/{domain,protocol,engine,http,services}`、`deploy/`Caddyfile+systemd），非 Python。

## 云端自主开发约定

- 云端任务运行时**本机已关机**，所有 `E:\` 路径失效 → 一律 `git clone` GitHub。
- `scripts/openings.py` / `step_notes.py` **已在 chess-tutor-skill 的 GitHub HEAD**，可直接 clone 取用。
- 新写的分析文档若未 commit 则云端读不到 → **关键结论必须内联进任务 prompt**。
- 产出留存：优先推分支 `feat/l0-core` 到 `ai-chess-web`；push 失败则导出 patch + 文件树并在 REPORT.md 顶部标注"未推送"。
- 收工总闸门：`pnpm typecheck` ✅ / `pnpm test` ✅ / `pnpm build` ✅ + REPORT.md。
