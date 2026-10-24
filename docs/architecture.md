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
