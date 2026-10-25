# HANDOFF — 交接快照

> **用途**：新会话 / 新机器接手时，读完这一篇就能开工，不必继承上一段对话的上下文。
> **维护约定**：每完成一批改动就更新「进度」「待办」两节，并随手 commit。**这比依赖对话记忆可靠。**

最后更新：2026-10-25

---

## 1. 三十秒上手

```bash
git clone git@github.com:xxfcz/chess-tutor-skill.git chess-coach
cd chess-coach
bash scripts/dev_up.sh --with-bridge
```

打开 `http://127.0.0.1:8080/`（对弈）、`?view=train`（练习）、`?view=narrate`（观战解说）。

> 依赖：Python 3.11 + `flask` / `python-chess`（脚本自动装）；**Stockfish 需自行安装**，缺了只是引擎讲解不可用，页面照样能开。
> 脚本幂等：重复跑不会起重复进程；`--restart` 才会先杀旧进程。

---

## 2. 项目是什么

`chess-coach` 是一个 **WorkBuddy 技能 + 配套网站**，四种形态：

| 形态 | 入口 | 说明 |
|---|---|---|
| 复盘画像 | 技能对话 + `scripts/analyze.py` / `profile.py` / `radar.py` | 贴 PGN，输出多维能力画像与训练计划 |
| 实时对弈陪练 | 网站 `/` | 学员执白，Stockfish 应招 + 逐步点评 |
| 观战解说 | 网站 `?view=narrate` + `play/bridge.py` | 桥轮询后端，增量写 `play/live_feed.jsonl` |
| 开局学习 | 网站 `?view=train` | 三种练法：演示 / 闯关 / 默写 |

**当前版本**：技能 v2.1.0。详见 `SKILL.md`（技能定义）与 `docs/README.md`（文档索引）。

> ⚠️ **定位变更（2026-10-24 已定）**：据 `docs/后端共享架构方案.md`，Python 版 chess-coach 的长期定位是**「规范与种子数据」真相源**，不是最终运行时代码。未来三端统一到 Node 后端（`chess.imex.de5.net`）+ 共享 `chess-core`。
> 所以：**教练口吻、分级阈值、12 开局 ideas/traps 这些"口径"可以放心在这里沉淀**；但不要在 Python 侧再堆重型新功能，避免将来移植成本翻倍。

---

## 3. 代码地图

```
chess-coach/
├── AGENTS.md                 # 开发者/代理总纲（先读这个）
├── SKILL.md                  # WorkBuddy 技能定义（四形态 + 接口表）
├── scripts/
│   ├── analyze.py            # PGN → 逐着分析
│   ├── profile.py            # 分析结果 → 能力画像
│   ├── radar.py              # 雷达图
│   ├── openings.py           # 12 个开局数据（ideas/traps/moves）
│   ├── step_notes.py         # 每个开局的逐着人话讲解（演示模式用）
│   ├── train_core.py         # 练习核心：demo_step / drill_move / quiz_next + 引擎单例
│   ├── train.py              # 练习命令行入口
│   ├── dev_up.sh             # ★ 一键起环境（本次新增）
│   └── sync_skill.sh         # 同步三份技能拷贝
├── play/                     # 网站（Flask）
│   ├── app.py                # 单入口 POST 分发 + ?view= 页面路由 + 静态组件路由
│   ├── board.css / board.js  # ★ 共用棋盘组件 CBoard（对弈/练习同源）
│   ├── board_page.txt        # 对弈页
│   ├── train_page.txt        # 练习页（演示/闯关/默写三 tab）
│   ├── narrate_page.txt      # 解说页
│   ├── bridge.py             # 观战桥（轮询 → live_feed.jsonl）
│   └── live_feed.jsonl       # 运行产物，git 忽略
├── docs/                     # 经验沉淀（见 docs/README.md）
│   ├── 后端共享架构方案.md     # ★ 三端后端复用决策（唯一真相）
│   └── HANDOFF.md            # ★ 本文
└── .workbuddy/memory/        # 平台记忆文件
```

---

## 4. 当前进度

### 已完成并验证

- [x] 四形态功能齐全（复盘 / 对弈 / 解说 / 开局学习）
- [x] **演示模式**：逐步点「下一步」，每步 Stockfish 讲解，含 12 开局逐着人话文案
- [x] **共用棋盘组件 CBoard**：对弈页 + 练习页三模式全部复用 `board.css`/`board.js`
- [x] **扁格子 bug 修复**：练习页 `.board` 补 `grid-template-rows:repeat(8,1fr)`
- [x] **换底色主题**：经典绿 / 蓝灰 / 胡桃木 / 石板灰，`localStorage` 记忆
- [x] 坐标标注（练习页底行列字母、最左列行号）
- [x] `AGENTS.md` + `docs/` 六篇沉淀
- [x] 推送到 `git@github.com:xxfcz/chess-tutor-skill.git`（Deploy Key 方式）
- [x] 拉取并合并你提交的 `docs/后端共享架构方案.md`
- [x] `scripts/dev_up.sh` 一键起环境（本次新增）

### 线上

- 发布链接：`https://aa5c7af03b07c3740.app.workbuddy.host/?sharecode=NV23SHXFSC`
- **重复发布同一项目会复用同一链接**，所以它本质上就是"固定"的。
- ⚠️ 自定义域名 `chess.app.workbuddy.host` **不可用**：平台 `publish.js` 无域名参数，该子域返回「链接已失效」。详见第 6 节。

---

## 5. 待办 / 悬而未决

| 项 | 状态 | 说明 |
|---|---|---|
| **Node 后端 + chess-core 落地** | 待你拍板 | `docs/后端共享架构方案.md` §8 两个问题：是否启动 `chess-core` 提取 + Node 骨架？LLM 教练是否迁到自有服务器？ |
| **`chess.imex.de5.net` 做实** | 未开始 | 目标：`/v1` 兼容 + `/api/coach`，先跑通「小程序不动、后端换 Node」 |
| **12 开局数据可移植化** | 建议 | 把 `openings.py` 的 ideas/traps 导出成 JSON，为 Node 化铺路（口径不分叉） |
| **bridge 常驻机制** | 半自动 | 目前要手动 `dev_up.sh --with-bridge`；bridge 挂了不会自动重启（无 supervisor） |
| **演示模式提速** | 可选 | 现在每步 depth=14 约 1–2s。需要更快就降 depth 到 10 或加局面缓存 |

---

## 6. 已知坑（踩过的，别再踩）

> 完整版见 `docs/engine-gotchas.md`。这里只列最容易反复踩的。

1. **引擎评分必须用 `pov(board.turn)`** —— 用 `pov(WHITE)` 会在黑方回合把正负号搞反，`loss` 变负数。
2. **`is_best` 别用 `top[0].san == san` 判** —— 分数并列时第一名可能是别的着法。用 `loss <= 3`。
3. **页面 `.txt` 是启动时读进内存的** —— 改 `board_page.txt` / `train_page.txt` / `narrate_page.txt` 后**必须重启 app.py**；但 `board.css`/`board.js` 是按需读盘，改完刷新即可。
4. **棋子别靠空心/实心字形区分** —— 部分环境字体回退会把黑白都渲染成空心。用**实心字形 + 颜色描边**。
5. **`pkill -f "python3 app.py"` 会误杀自己的 shell** —— 用 `dev_up.sh --restart`，或按 PID 杀。
6. **bridge 依赖后端内存态** —— `app.py` 重启后 `state` 变 null，bridge 读到 `尚未开局`。先开一局再看 feed。
7. **发布脚本没有域名参数** —— 别浪费时间找 `--domain`，不存在。

---

## 7. 会话/沙箱须知

沙箱是**对话级**的：换会话就是新沙箱，`/workspace` 里未提交的文件、正在跑的进程、SSH key 都不跟过去。

| 东西 | 跨会话 | 恢复方式 |
|---|---|---|
| 代码 | ✅ | `git clone` / `git pull` |
| 发布网站 | ✅ | 直接用 shareLink（独立常驻服务） |
| 运行环境 | ❌ | `bash scripts/dev_up.sh --with-bridge` |
| SSH key | ❌ | 重新 `ssh-keygen` + 去 GitHub 加 Deploy Key，或改用 PAT |

**所以：开工先 clone，收工先 commit。** 上下文可以随便丢，仓库不能。

---

## 8. 下一步建议

如果你是接手者，按这个顺序：

1. 读 `AGENTS.md`（总纲）→ 读本文 → 按需翻 `docs/`
2. `bash scripts/dev_up.sh --with-bridge` 起环境，把三个页面点一遍确认功能
3. 看第 5 节待办，**先确认 Node 化是否启动**——这决定后续所有工作的方向
4. 如果只是修 bug / 调 UI：直接在 Python 侧改，别忘了 `sync_skill.sh` 同步三份拷贝
