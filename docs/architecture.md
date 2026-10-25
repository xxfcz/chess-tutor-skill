# 架构总览

chess-coach 把一份 PGN 或一局实时对弈变成训练闭环：**诊断（逐着分析）→ 画像（多维评分）→ 开方（教练解释 + 训练计划）→ 复测**。

设计铁律：**真相来自引擎 + 规则，解释来自 LLM（或规则模板）。** 模型不自己算棋，只把结构化引擎数据翻译成有依据的教学语言。

## 数据流

```
PGN / 实时落子
   │
   ├─ 形态一 PGN ──► analyze.py ──► profile.py ──► radar.py ──► LLM 报告
   │
   └─ 形态二/三/四 网页 ──► app.py ──┬─► Stockfish（_engine_lock 串行）
                                     ├─► train_core.py（闯关/出题/演示讲解）
                                     └─► bridge.py（轮询 watch → live_feed.jsonl）
                                                        ↑ AI 教练用 note 回写点评
```

## 四个形态如何共享

| 共享物 | 被谁用 |
|---|---|
| `scripts/openings.py` | 练习页（演示/闯关/默写）+ 对弈页开局模式 + 形态一出题 |
| `scripts/train_core.py` | `play/app.py`（经 `handle_train`）与独立 `train.py` 共用 |
| `play/board.css` + `play/board.js`（`CBoard`） | 对弈页与练习页的**全部棋盘** |
| Stockfish 引擎单例 | `app.py` 与 `train_core.py` 各自维护，互相加锁 |
| `live_feed.jsonl` | 桥写入、旁白页/对弈页渲染、AI 教练读取 |

## 三种页面的分发

所有动态请求都收敛到 `POST /`，用 JSON body 的 `action` 字段分发（`api_dispatch`）：

- `GET /` → 对弈页
- `GET /?view=narrate` → 实时旁白页
- `GET /?view=train` → 开局练习页

> 网关只透传 `/`，所以**不要**新开 `/api/*` 之类的路径做接口；新接口加在 `action` 白名单里。

## 引擎进程管理

- `play/app.py` 与 `scripts/train_core.py` 各自有引擎单例，`tc.engine()` 用模块级 `_lock` 串行化。
- `atexit` 注册 `close_engine()` 显式退出；服务停止前务必让引擎进程退出，否则会留僵尸 Stockfish。
- 桥线程（`bridge.main`）是守护线程，随 `app.py` 启动，1.5s 轮询一次 `watch`，把增量落盘到 `live_feed.jsonl`。

## 练习讲解的生成机制（四路拼装，演示模式零 LLM 成本）

很多人会以为"只用 Stockfish 也能出这些中文评论"——**不是**。Stockfish 在演示流程里只产出数字（首选着法、前三候选、各自评分）。卡片里所有可读文本来自另外三路，与引擎无关。**整个演示讲解路径不调用任何语言模型**；唯一的 LLM 环节是"AI 点评"，需用户回 WorkBuddy 触发（见 `play/bridge.py` + `references/prompts.md`）。

四路来源与卡片字段映射：

| 卡片字段 | 来源 | 是否 Stockfish |
|---|---|---|
| `★ 引擎首选` | `train_core.py` `demo_step()` 的 `is_best`（`loss ≤ 3` 判首选） | 判据来自引擎分 |
| 逐着讲解（如"中心兵占位，打开象和后路"） | `scripts/step_notes.py` `NOTES[id][idx]`（**手写的逐着文案**） | ❌ 纯手写 |
| `这一步做了什么` | `train_core.py` `_move_feature()`（`board`+`move` 推规则：中心格/推进几格/是否吃子） | ❌ 规则生成 |
| `Stockfish 怎么说` | `engine_say` 模板，套 `_cp_phrase(cp)` | 文本由分数字填 |
| `候选前三` | `eng.analyse(..., multipv=3)`，`depth=14` | ✅ 纯引擎 |
| `整条开局的思路` | `scripts/openings.py` 该开局的 `ideas` 字段 | ❌ 纯手写 |
| `易错点` | `scripts/openings.py` 该开局的 `traps` 字段 | ❌ 纯手写 |

拼装逻辑在 `train_core.py` 的 `demo_step()`：引擎事实（`top`/`loss`/`cp`）+ 手写 `note` + 规则 `feats` + 模板 `engine_say`，缝成一张卡返回前端。

> 推论：即使**没有引擎**，只要 `openings.py` 的 `ideas/traps` 与 `step_notes.py` 的 `NOTES` 在，卡片照样能出——只是"候选前三"和"首选"判断会失效。
> 这些手写文案正是 `docs/后端共享架构方案.md` 定义的"**规范与种子数据真相源**"：跨端口径一致、将来移植进 Node 后端，不应在 Python 侧继续分叉。
