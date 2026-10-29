# AGENTS.md — chess-coach（国际象棋 AI 教练 · 技能 + 对弈/练习网站）

> 本文件给接手本项目的 AI 代理 / 协作者阅读：先读完它和 `SKILL.md`，再动手改代码。
> 核心设计原则：**真相来自引擎 + 规则，解释来自 LLM（或规则模板）**。模型不自己算棋。
> **状态说明：本项目为只读参考，不再继续开发，请勿在此提交修改或新增功能。**

---

## 1. 它是什么

一个 WorkBuddy 技能，背后是一套能跑在网页上的国际象棋教练系统。四种形态共用同一套数据与引擎：

| 形态 | 入口 | 后端 | 说明 |
|---|---|---|---|
| 一 · PGN 复盘画像 | CLI / LLM 生成报告 | `scripts/*.py` | 上传 PGN → 逐着分析 → 六维画像 → 训练计划 |
| 二 · 实时对弈陪练 | 对弈页 `GET /` | `play/app.py` | 学员执白、降强度 Stockfish 执黑，赛中 KPI/点评 |
| 三 · 观战解说 | 旁白页 `GET /?view=narrate` | `play/app.py` + `play/bridge.py` | 桥把每步写入 `live_feed.jsonl`，AI 教练回写点评 |
| 四 · 开局学习 | 练习页 `GET /?view=train` | `play/app.py` + `scripts/train_core.py` | 演示 / 闯关 / 默写 / 对弈页开局模式 |

三个网页是**同一个 Flask 应用**，用 `?view=` 区分（网关只透传 `/`，所以所有动态接口收敛到 `POST /` 用 `action` 分发）。

## 2. 目录结构

```
chess-coach/
├── AGENTS.md                # 本文件
├── SKILL.md                 # 技能清单（触发词 + 工作流 + 接口速查，权威约定）
├── README.md                # 面向使用者的概览
├── references/prompts.md    # LLM 教练层提示词与设计原则
├── scripts/                 # 形态一与形态四的纯后端逻辑
│   ├── analyze.py           # 逐着分析（分级/精度/战术原因）
│   ├── profile.py           # 六维画像
│   ├── radar.py             # 雷达图
│   ├── openings.py          # ★ 开局库单一数据源（12 条）
│   ├── step_notes.py        # ★ 演示文案（与 openings.moves 逐手对应）
│   ├── train_core.py        # ★ 闯关/出题/演示讲解核心（play/app.py 共用）
│   ├── train.py             # 独立练习小服务（端口 8090，非必需）
│   └── sync_skill.sh        # 同步到 project/user 两处技能注册目录
├── play/                    # 形态二/三/四的 Web 应用
│   ├── app.py               # ★ 唯一后端：action 分发 + 引擎单例 + 桥线程
│   ├── bridge.py            # 常驻观战桥（轮询 watch → 写 feed → 规则解说）
│   ├── board_page.txt       # 对弈页 HTML
│   ├── narrate_page.txt     # 旁白页 HTML
│   ├── train_page.txt       # 练习页 HTML（演示/闯关/默写）
│   ├── board.css            # ★ 共用棋盘样式（CBoard）
│   ├── board.js             # ★ 共用棋盘渲染逻辑（CBoard，暴露全局）
│   └── requirements.txt     # flask + python-chess==1.999（publish 据此判型）
├── samples/                 # 演示样例 PGN + 生成器
└── report/                  # 演示产物（画像 json / 雷达图 / 报告 md）
```

★ = 改动时需特别小心的核心文件。

## 3. 本地运行

```bash
# 后端（对弈 + 练习 + 旁白，含桥线程自启）
cd play && python3.11 app.py        # 监听 0.0.0.0:8080

# 形态一：PGN 复盘
python3.11 scripts/analyze.py game.pgn --player 学员名 --out analysis.json
python3.11 scripts/profile.py analysis.json --out profile.json
python3.11 scripts/radar.py profile.json --out profile_radar.png

# 同步技能到注册目录（改完源码副本后必跑）
bash scripts/sync_skill.sh
```

依赖：`python-chess==1.999`（已验证兼容，别升 `1.11.x`，镜像没有）、`flask`、`matplotlib`、Stockfish 二进制在 `/usr/games/stockfish`。

## 4. 改完代码后怎么生效

- **后端 `play/*.py` / `scripts/*.py`**：进程内 import 时读入，需**重启 `app.py`**（`pkill -f "app.py"` 后 `cd play && python3 app.py`）。
  - ⚠️ `pkill -f "app.py"` 会匹配到当前命令行本身，用 `pgrep -f app.py` 拿 pid 再 `kill`，或 `setsid python3 app.py`。
- **前端 `play/*.txt` / `board.* `**：`app.py` 在 import 时把页面文本整段读进内存（`.txt`），**改页面也必须重启 `app.py`** 才生效。
  - `board.css` / `board.js` 是运行时按请求从磁盘读取 + `no-cache`，**改组件文件即时生效、无需重启**。
- **技能注册**：`sync_skill.sh` 把源码 tar 覆盖到 `/workspace/.codebuddy/skills/chess-coach/` 与 `/root/.codebuddy/skills/chess-coach/`。客户端对 `.codebuddy/skills` 有 ~3s 防抖热重载，改完不用重启会话。

## 5. 发布为可分享网页

```bash
cd /root/.codebuddy/skills/sites/scripts
node publish.js --dir /root/.codebuddy/skills/chess-coach/play --port 8080 --language python
```

- 返回 `shareLink`（形如 `https://<app>.app.workbuddy.host/?sharecode=XXXX`），有效期约 5 年。
- **同一 runtime 只能发布一个服务**：本项目三个页面合并为单应用，**不要再为练习页单独发布一次**，否则会覆盖并 kill 旧服务。
- **端口必须与 `app.py` 默认 8080 一致**；publish 对 python 项目不注入 `$PORT`。
- 沙箱重启自恢复靠 `/workspace/.cloudstudio` 的 `[[app]]`（先 sync 再 `cd play && python app.py`）。

## 6. 关键约束与踩坑（务必先读 `docs/engine-gotchas.md`）

1. **引擎评分配色必须用「走子方视角」**：`score.pov(board.turn)` 全程为基准，展示时才乘 `sign` 转白方视角。一开始就用 `pov(WHITE)` 会让黑方回合 `loss` 变负。
2. **`is_best` 用评分差判定**（`loss <= 3`），别用"是否等于 `top[0]`"——multipv 前三常有并列同分。
3. **棋盘格子必须是正方形**：`.board` 要**同时**写 `grid-template-columns` 和 `grid-template-rows: repeat(8,1fr)`；漏掉 rows 会让没棋子的空行被压扁。
4. **棋子用实心字形 + 颜色区分**（白 `#fff`+黑描边、黑 `#16181d`），不要靠空心/实心字形差异——缺字体回退会把黑白都渲染成空心。
5. **棋盘是对弈/练习共用的单一组件** `CBoard`（`play/board.css` + `play/board.js`），改样式一处生效。
6. **开局阶段 cp 差普遍偏小**：判定引入「是否在谱内」作为独立维度（`rank is None and not in_book → offbook`），否则 `1.a3` 也会被当成"可行"。
7. **引擎并发加锁**：`app.py` 的 `eval_white`/`coach_reply` 与 `train_core.engine()` 都要走锁，避免桥线程与用户请求抢同一引擎实例崩溃。
8. **演示不自动生成 AI 点评**：演示是纯前端+引擎，结束不会写 `coach_note`；用户要点评需回会话说「讲讲这盘开局」。

## 7. 扩展指引

- **加一条开局**：只改 `scripts/openings.py` 的 `OPENINGS`，并同步在 `scripts/step_notes.py` 的 `NOTES` 里写等长文案（**长度必须与 `moves` 相等**，否则演示越界）。对弈页「开局模式」弹窗的列表是硬编码 `OPENS`（`board_page.txt` 内），记得同步。
- **加棋盘主题**：在 `board.js` 的 `THEMES` 里加一组 `{light, dark}`，按钮自动可见。
- **加演示讲解维度**：`train_core._move_feature`（代码推断）或 `step_notes`（人工文案）二选一，别混。

## 8. 不要做

- 不要为练习页单独再发布一个服务（同 runtime 唯一）。
- 不要把演示/合成数据（samples/）写入用户记忆库（见 SKILL.md 记忆库落库规则）。
- 不要改 `play/requirements.txt` 里的 `python-chess==1.999`（publish 据此判型且镜像无新版）。
- 不要删 `/workspace/.cloudstudio` 的 `[[app]]` 自恢复配置。
