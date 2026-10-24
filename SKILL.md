---
name: chess-coach
version: 2.1.0
display_name: 棋类 AI 教练（国际象棋）
display_name_en: Chess AI Coach
description_zh: "把国际象棋变成\"引擎事实 + 教练解释 + 训练闭环\"的私人教练技能，包含四种形态。形态一（复盘画像）：用户上传/粘贴 PGN，python-chess + Stockfish 逐着分析（走子分级/精度评级/多维能力画像）→ CheckPause 式教练点评与一周训练计划。形态二（实时对弈陪练）：启动 Flask + Stockfish 服务并发布为应用，学员在网页/手机点选落子、降强度引擎执黑应招，赛中实时 KPI、走前扫描提醒、失误点评；支持点历史步回看（后续着法灰化保留）、悔棋、AI 教练点评推送到页面。形态三（观战解说）：常驻桥把每步写入 feed，AI 教练可读取棋局并回写人话解说，用户在旁白页/对弈页直接看到。触发条件：上传/粘贴 PGN 或棋谱、要求复盘/分析棋局/生成棋力画像/要训练计划；或用户想下棋、要陪练、来一局、实战对弈、练棋；或说\"看看这盘\"\"讲讲这盘\"\"我刚才哪步不好\"等观战解说指令。或想学开局、练开局、推荐开局、找常见开局练习、提到具体开局名（意大利/西班牙/苏格兰/西西里/法兰西/卡罗康/伦敦/后翼弃兵/卡特兰）。不适用：中国象棋/围棋（需换引擎 Pikafish/KataGo，属路线 C 扩展）。"
description_en: "A private chess coach skill with three modes. Mode 1 (review & profiling): upload/paste a PGN, run python-chess + Stockfish move-by-move analysis (move labels, accuracy tiers, multi-dimensional profile) → CheckPause-style commentary and a one-week training plan. Mode 2 (live play): start a Flask + Stockfish service and publish it as an app; the student taps to move and a lowered-skill engine plays Black, with in-game KPIs, pre-move scan reminders, and Mistake/Blunder commentary; supports clicking any past move to review it (later moves stay visible but dimmed), undo, and pushing coach notes to the page. Mode 3 (spectating & narration): a resident bridge records every move into a feed, so the AI coach can read the current game and write back plain-language analysis that shows up on the board page and the narration page. Trigger on PGN uploads, review/profiling/training-plan requests, playing/sparring requests, or phrases like \"look at this game\" / \"walk me through it\". Not for Chinese chess or Go (different engines). Or requests to learn or practice chess openings (Italian, Spanish, Scotch, Sicilian, French, Caro-Kann, London, Queen's Gambit, Catalan)."
description: "把国际象棋变成\"引擎事实 + 教练解释 + 训练闭环\"的私人教练技能，四种形态。形态一（复盘画像）：上传/粘贴 PGN，逐着分析生成多维能力画像与训练计划。形态二（实时对弈）：Flask+Stockfish 服务发布为应用，网页/手机点选落子、引擎执黑应招，实时 KPI、走前扫描、失误点评；支持历史步回看（后续着法灰化保留）、悔棋、点评推送页面。形态三（观战解说）：常驻桥写入 feed，AI 教练读取棋局并回写人话解说。触发：上传 PGN、复盘/画像/训练计划、想下棋/陪练/来一局、或说\"看看这盘\"\"讲讲这盘\"。形态四（开局学习）：内置12条开局（e4/d4体系），提供演示（逐手 Stockfish 讲解，小白先看这个）、闯关实战、谱着默写、对弈页开局模式四种练法。触发：学开局/练开局/演示开局/推荐开局/找常见开局练习/意大利开局/伦敦体系等；或说“跟我下盘棋”“看看这盘棋”“我不会走先演示一遍”这类口语。不适用：中国象棋/围棋。"
---

# chess-coach — 棋类 AI 教练（路线 A）

把一份 PGN、或一局实时对弈，变成一条训练闭环：**诊断（逐着分析）→ 画像（多维评分）→ 开方（教练解释+训练计划）→ 复测（新对局对比）**。

设计原则（来自 CheckPause / CS357 / Turning Points 数据集）：
**真相来自引擎 + 规则，解释来自 LLM。** LLM 不计算棋，只把结构化引擎数据翻译成有依据的教学语言。

---

## 形态一：离线上传 PGN 复盘画像（适合"赛后分析"）

### 何时用
- 用户上传 / 粘贴 PGN 棋谱，要求复盘、找错误、评等级
- 用户想要自己的"棋力画像"（战术/开局/中局/残局/计算/心理多维评分）
- 用户要一份针对性的训练计划
- 用户就某一步棋追问"为什么不行"（错题访谈）

### 工作流（收到 PGN 后按序执行）
1. **落盘**：把用户的 PGN 保存为临时文件（保留原始内容，多局 PGN 直接支持）。
   - 若用户给出 Lichess 用户名而非文件，提示导出：`https://lichess.org/api/user/<用户名>?max=20`（无需 token 即可取公开对局）。
2. **逐着分析**（引擎事实层）：
   ```bash
   python3.11 scripts/analyze.py <pgn文件> --player <学员名> --out <工作目录>/analysis.json
   ```
   - `--player` 匹配 PGN 的 White/Black 头；省略时默认分析白方。
   - 产出：每着的标签（Best/Good/Inaccuracy/Mistake/Blunder）、前后 FEN、引擎最佳着（SAN）、ACPL、精度%、五档评级。
3. **多维画像**：
   ```bash
   python3.11 scripts/profile.py <analysis.json> --out <工作目录>/profile.json
   ```
   - 产出：六维评分（开局/中局/残局/计算/战术/心理，0-100）+ 最弱三项 + 关键错误清单（含 FEN 与最佳着）。
4. **雷达图**：
   ```bash
   python3.11 scripts/radar.py <profile.json> --out <工作目录>/profile_radar.png
   ```
5. **教练层（LLM，即当前 agent）**：严格按 [references/prompts.md](references/prompts.md) 的模板生成：
   - 关键错误逐着点评（只评这一步、引用损失 cp 与最佳着、不剧透后续）
   - 错题访谈（定位：计算错 / 知识盲区 / 习惯问题）
   - 能力画像小传（3–5 句，用数字说话）
   - 一周训练计划（诊断→开方→练习→复测，含量化验收目标）
   - 产出 Markdown 报告，嵌入雷达图。
6. **复测闭环**：用户下次上传新对局时，重新跑 2–4 步，与记忆库中的上次画像对比，输出维度变化。

---

## 形态二：实时对弈陪练（适合"赛中练习 + 带 KPI 实战"）

### 何时用
- 用户说"来一局""陪我练棋""想下棋""实战一下""用教练下盘棋"
- 用户想用带 KPI 的实战验证画像（如"零送子"训练）

### 启动与发布

**方式 A：本地预览（本会话内快速看）**
```bash
cd play && python3.11 app.py          # 监听 0.0.0.0:8080，桥线程自动随服务启动
```
然后用 `present_files` 打开 `http://localhost:8080`。

**方式 B：发布为应用（**推荐**，手机可访问、可分享、跨会话可用）**
```bash
cd /root/.codebuddy/skills/sites/scripts
node publish.js --dir <技能play目录> --port 8080 --language python
```
- 返回 JSON：`{"shareLink": "...", "verified": true}`。
- 链接形如 `https://<appname>.app.workbuddy.host/?sharecode=XXXX`，**有效期约 5 年**（`DEFAULT_EXPIRE_SECONDS`）。
- **发布幂等**：同一 sandbox runtime 重复发布会复用同一 appName 与同一链接。
- ⚠️ **同一 runtime 只能发布一个服务**：appName 按 runtimeId 复用，第二次发布会**覆盖**前一次的 release 并 kill 掉旧服务。本项目已把三个页面合并为单应用（用 `?view=` 区分），**不要为练习功能单独再发布一次**。
- 发布脚本会：装依赖 → 起服务 → 就绪校验 → 创建 release。
- 沙箱重启后的自恢复靠 `/workspace/.cloudstudio` 的 `[[app]]` 配置（见下文「常驻桥」），不靠 publish。
- ⚠️ **端口必须与 app.py 默认端口一致**（当前 `8080`）。publish 对 python 项目不注入 `$PORT`，靠 app.py 自身默认值。

### 网页交互能力（全部已实现，告知用户怎么用）

| 玩法 | 操作 | 效果 |
|---|---|---|
| **落子** | 点自己的棋子 → 点高亮目标格 | 学员执白，降强度 Stockfish（Skill Level 4）执黑自动应招 |
| **KPI 统计** | 自动 | 面板累计 Best / Good / Inaccuracy / Mistake / Blunder / 总着数，目标默认"零送子" |
| **评估条** | 自动 | 白方视角局面优劣，实色条 + 数值 |
| **走前扫描提醒** | 自动（每回合） | 三问（吃子→将军→悬空）+ 该学员画像最弱弱点 |
| **失误点评** | 自动（仅 Mistake/Blunder） | 弹卡片：引擎首选着（SAN）+ 损失 cp + 战术原因 + 画像个性化提醒 |
| **评级角标** | 自动 | 着法记录里 `??`=Blunder（红）`?`=Mistake（橙）`★`=Best（绿） |
| **历史回看（预览）** | **点着法记录里任意一步** | 棋盘回退到那步；**后续着法保留但灰化**（opacity 0.32），仅供临时查看，不修改棋局；顶部出现蓝色提示带 |
| **回到当前** | 点提示带里的「回到当前」按钮 | 退出预览，回到最新局面 |
| **从历史重下（分支）** | 预览态下直接落子 | 该步之后的所有着法被新线**替换**（这是唯一会截断后续着法的交互） |
| **悔一步** | 点「↩️ 悔一步」 | 回退到你上一步走之前（撤掉你跟教练的两手）；KPI 精确回滚；若退到黑方回合，教练自动补手保证不卡死 |
| **开新局** | 点「🔄 开新局」 | 重置棋局 + 清空旁白 feed |
| **刷新页面** | 浏览器刷新 | **不重置棋局**，自动恢复进行中的局面（走 `watch` 而非 `new`） |

> **设计要点**：刷新不丢棋、点历史只预览不改局、只有落子才截断——这三条是防止"手滑毁棋"的关键保障。

---

## 形态三：观战与 AI 教练解说（我如何"看到"你的棋局）

### 架构：一条单向管道

```
用户落子 → 后端 GAME → 常驻桥(1.5s 轮询 watch) → live_feed.jsonl → 旁白页 / 对弈页
                                                      ↑
                                          AI 教练用 note 动作回写
```

### 常驻桥（`play/bridge.py`）
- **随服务启动**：`app.py` 以守护线程方式启动 `bridge.main()`，无需另起进程。
- **跨休眠自恢复**：`/workspace/.cloudstudio` 里配了 `[[app]]`（`port=8080`），沙箱重启时先跑 `scripts/sync_skill.sh` 恢复技能目录，再 `cd play && python app.py` 拉起 Flask，桥线程随之复活。
- **手工拉起**（需要立刻重启服务时）：
  ```bash
  cd /workspace/chess-coach/play && nohup python3 app.py > /tmp/chess_app.log 2>&1 &
  ```
- **写入内容**：`move`（着法）、`coaching`（失误点评）、`kpi`、`narration`（规则模板自动解说，含局势判断）、`sync` / `new_game` / `game_over`。

### 我看到棋局的方式
两种，配合使用：

| 方式 | 命令/动作 | 返回 | 是否改棋局 |
|---|---|---|---|
| **拉快照** | `POST / {"action":"watch"}` | 当前 FEN、回合、完整着法、KPI、评估、最近点评 | ❌ 只读 |
| **读进程** | 读 `live_feed.jsonl`，或 `POST / {"action":"feed"}` | 从开局到现在的**完整事件流**（含每步点评与自动解说） | ❌ 只读 |

> 优先读 `feed`：它保留全过程，比 `watch` 的单帧快照信息全得多。

### 我如何把点评送达网页（关键能力）
**给 feed 写一条 `coach_note`**，对弈页与旁白页都会渲染出来：

```bash
curl -s -X POST "<应用地址>" -H "Content-Type: application/json" \
  -d '{"action":"note","text":"<点评正文>","source":"ai-coach"}'
```

- 对弈页：蓝色高亮卡片（🧑‍🏫 署名 + 时间戳），每步刷新 + 每 8 秒轮询
- 旁白页：同样样式，按时间流排列
- **不需要 LLM API key**——点评由当前 agent 亲自撰写后写入，这是绕开"无 key"限制的唯一可行通道

### 为什么不是 WebSocket / 不是我自动盯着
- **传输层不是瓶颈**。哪怕上了 WebSocket，我这个聊天会话也是**无状态、按需唤醒**的，没有常驻进程能 push 进会话。
- 所以"全自动实时点评"要么靠**规则模板**（bridge 的 `narration`，已在跑），要么需**独立 LLM API key** 让桥自己调模型（当前沙箱无此凭证）。
- 当前折中：**规则自动解说兜底每步，我的深度点评在用户呼唤时写入**。

---

## 形态四：开局学习（四种练法）

### 何时用
- 用户说"我想学开局""找些常见开局给我练""推荐开局""怎么开头"
- 用户问某个开局"怎么走""有什么陷阱""为什么这样下"
- 用户说"我不会走""先看看怎么下""给我演示一遍" → **直接进演示模式**

### 开局库（`scripts/openings.py`，单一数据源）

覆盖 **e4 王兵体系** 与 **d4 后兵体系**，共 12 条，每条含：主变（UCI）、关键想法（`ideas`）、易错点（`traps`）、难度（1 入门 / 2 进阶）、学习方（执白/执黑）。

| 体系 | 开局 | 学习方 |
|---|---|---|
| **e4** | 意大利开局 `1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5` | 执白 |
| | 意大利·双马防御 `...3.Bc4 Nf6` | 执白 |
| | 西班牙开局 `...3.Bb5 a6` | 执白 |
| | 四马开局 `...3.Nc3 Nf6` | 执白 |
| | 苏格兰开局 `...3.d4` | 执白 |
| | 西西里防御 `1...c5` | 执黑 |
| | 法兰西防御 `1...e6` | 执黑 |
| | 卡罗康防御 `1...c6` | 执黑 |
| | 开放性对局 `1...e5` | 执黑 |
| **d4** | 伦敦体系 `1.d4 d5 2.Nf3 Nf6 3.Bf4 e6` | 执白 |
| | 后翼弃兵 `1.d4 d5 2.c4 e6` | 执白 |
| | 卡特兰开局 `1.d4 Nf6 2.c4 e6 3.g3` | 执白 |

> **设计原则：练理解，不死背。** 每条开局都配 `ideas`（为什么这样走）和 `traps`（别踩什么坑），而不只是给一串着法。

### 四种练法

| 模式 | 在哪 | 怎么玩 |
|---|---|---|
| **演示（demo）** ⭐新手先看这个 | `?view=train` → 点开局卡片（默认进演示） | 逐步看双方怎么走：点「下一步」走一手，棋盘高亮起止格，下方给三块讲解——**这一步做了什么**（走法特征）、**人话说明**（这一步的战略意图）、**Stockfish 怎么说**（首选着、分差、局势评分、候选前三）。可「上一步」回退、可「重播」。全程只读，不会改动棋局 |
| **闯关（drill）** | `?view=train` → 闯关 | 跟引擎实战。每步由 Stockfish 判定：在谱内且第一梯队 → `✓ 最佳`；谱外但不太亏 → `◇ 非主变`（并提示谱内应走什么）；亏 >120cp → `✗ 不好`。**对手会按该开局的标准变化应招**，保证你体会到真实结构 |
| **默写（quiz）** | `?view=train` → 默写 | 系统在主线某一步出题，给 4 个候选（正确答案 + 3 个同局面的合法干扰项），选错立刻标出正解 |
| **对弈页开局模式** | 对弈页 → 「📖 开局模式」按钮 | 选一个开局后在正常对弈页里下，对手全程走谱内着法。适合"带着开局知识真打一局" |

> **学习路径建议**：演示（看懂）→ 默写（记住）→ 闯关（下出来）→ 对弈页开局模式（真打）。纯小白从演示开始，不要一上来就闯关。

#### 演示模式的讲解怎么来的

三块内容来源不同，不要混为一谈：

| 讲解块 | 数据来源 | 说明 |
|---|---|---|
| **人话说明**（`note`） | `scripts/step_notes.py` | 人工撰写，每手一句，讲战略意图；与 `openings.moves` 一一对应（长度必须相等） |
| **这一步做了什么**（`features`） | 代码从走法推断 | 是否占中心 / 是否出子 / 是否指向前置弱点 / 是否将军 / 是否易位 |
| **Stockfish 怎么说**（`engine_say`） | 引擎 `multipv=3` | 首选着、与首选的分数差（`loss`）、白方视角评分（`cp`）、候选前三 |

**演示结束 ≠ 我会自动点评。** 演示是纯前端 + 引擎，不产生 `coach_note`。用户想要 AI 教练的针对性点评，需要回到会话里说「讲讲这盘开局」——我再读 `openings.py` 的 `ideas`/`traps` 和引擎数据给出人话点评。页面底部有这句提示，别让用户以为会自动收到点评。

### 关键实现约束
- **开局阶段 cp 差普遍偏小**（开局优势本就微小），单看绝对 cp 会把 `1.a3` 也判成"可行"。因此判定引入**是否在谱内**作为独立维度：`rank is None and not in_book → offbook`。
- 闯关的对手应招**优先走谱内**（`ridx < len(seq)` 时强制），走出主线后才交回引擎自由应对。
- 达到主线长度即结束，**不再多补一手**（否则进度会显示成 `6/5`）。
- `train_core.py` 为共用核心（闯关评定 / 出题 / 演示讲解），`train.py` 是独立小服务（端口 8090），也可完全通过主应用的 `POST /` 调用（action 前缀 `train_`，同时兼容无前缀名）。
- **演示评分必须用「走子方视角」计算**：`score.pov(board.turn)` 全程为基准，展示时再乘 `sign` 转成白方视角。若一开始就用 `pov(WHITE)`，黑方回合会出现 `loss` 为负数（已踩过这个坑）。
- **`is_best` 用评分差判定**（`loss <= 3`），不能用"是否等于 `top[0]`"：multipv 前三常有并列同分，名次排序不稳定。
- 演示里若所走这步不在引擎前三，要**把它补进候选列表并标 `is_chosen`**，否则用户看到"候选前三"里没有自己正在看的那一步。
- 棋盘棋子用**实心字形 + 颜色区分**（白子 `#fff` + 黑色描边、黑子 `#16181d`），不要依赖空心/实心字形差异——部分环境缺字体回退，会把黑白都渲染成空心。
- **棋盘是对弈页/练习页共用的单一组件**（`play/board.css` + `play/board.js`，暴露全局 `CBoard`）：
  - 渲染入口：`CBoard.render(el, fen, {sel, tgts, hl, coords, onClick})`；`parseFen` 也从组件取。
  - Flask 路由 `/<fname>`（白名单 `board.css`/`board.js`）按需读盘下发，改完即生效、无需重启。
  - **格子必须是正方形**：`.board` 要同时写 `grid-template-columns` 和 `grid-template-rows: repeat(8,1fr)`——曾漏掉 rows 导致无棋子的空行被压扁。
  - 底色主题用 CSS 变量 `--cb-light`/`--cb-dark`（默认经典绿 `#eee9d8`/`#6f9a5e`）；页面头部的「🎨 底色」按钮调 `CBoard.cycleTheme()` 循环 4 套主题（经典绿/蓝灰/胡桃木/石板灰），`localStorage(cb-theme)` 记忆、两页同步生效。
  - 坐标标注半透明配色（浅格黑 40%、深格白 75%），适配任意底色主题；练习页开、对弈页也开（`coords:false` 可关）。
- `renderBoard(el, fen, sel, tgts, hl, onClick)` 是练习页三个模式（演示/闯关/默写）共用的包装函数，底层走 `CBoard.render`，改样式一处生效，不必分别改。

---

## 用户可以对我发的指令（原样可用）

用户在网页下棋的同时，可以随时对我说下面这些话，我据此拉取棋局并回应：

| 用户可能说 | 我会做什么 |
|---|---|
| **"看看这盘" / "看看局面"** | 读 feed + watch，报告当前局面、评估、着法进度、KPI |
| **"讲讲这盘" / "分析一下"** | 逐段讲解着法思路，指出关键转折与失误，并把成文点评 `note` 推送到页面 |
| **"我哪步下得不好" / "找找我的失误"** | 筛出 Blunder/Mistake，按损失 cp 排序，逐条给出最佳着与原因 |
| **"这步为什么不行"** | 针对指定着法做错题访谈（计算错 / 知识盲区 / 习惯问题） |
| **"我该重点练什么"** | 结合画像弱点 + 本局表现，给出聚焦训练建议 |
| **"来一局" / "陪我练"** | 启动/确认服务，给出对弈链接 |
| **"重新开始" / "重开一局"** | 调用 `new`（或告知用户在页面点「开新局」） |
| **"悔一步" / "回到第 N 步"** | 调用 `undo`（或告知用户点着法记录/悔一步按钮） |
| **"难度调低/调高"** | 改 `app.py` 中 `coach_reply` 的 `skill` 参数后重发布 |
| **"我想学开局" / "推荐开局" / "有哪些常见开局"** | 列开局库（分 e4 / d4 两大体系），按用户水平推荐 2–3 条，给链接 `?view=train` |
| **"给我练意大利开局" / "练练开局"** | 启动/确认服务，指出闯关或默写入口，并讲该开局的 `ideas` 与 `traps` |
| **"这个开局为什么这么走"** | 读 `openings.py` 中该条目的 `ideas` / `traps`，用人话解释战略意图，不背谱 |

> **执行纪律**：收到"看看/讲讲/哪步不好"这类指令时，**必须先读 feed 或 watch 拿真实数据**，禁止凭空评论；点评要引用真实的 `loss_cp`、最佳着、着法序号。

---

## 接口速查（`POST /`，用 `action` 分发）

网关只透传 `/`，所有接口收敛到根路径，用 JSON body 里的 `action` 区分：

| action | 参数 | 作用 |
|---|---|---|
| `new` | `reset_feed`(bool，可选) | 开新局；`reset_feed:true` 时同时清空 feed |
| `watch` | — | 返回当前棋局完整状态（只读） |
| `feed` | — | 返回 `live_feed.jsonl` 全部记录 |
| `note` | `text`, `source` | 追加一条 `coach_note` 到 feed（AI 点评写入通道） |
| `legal` | `square`, `fen`(可选) | 某格合法目标；传 `fen` 时按该局面（预览态用） |
| `move` | `move`(UCI) | 学员落子 → 评分 → 教练应招 |
| `undo` | `to_ply` | 悔棋截断到第 `to_ply` 着（真改棋局，KPI 回滚） |
| `peek` | `to_ply` | **只读**返回第 `to_ply` 着之后的局面（预览用，不动棋局） |
| `open` | `id` | 进入开局模式：开新局 + 绑定开局库，对手按标准变化应招 |
| `list` / `train_list` | — | 列出开局库（含主变 SAN、难度、学习方）|
| `ideas` / `train_ideas` | `id` | 某开局的关键想法与易错点 |
| `drill_start` | `id` | 开始闯关：返回初始局面与目标手数 |
| `drill_move` | `id`,`fen`,`move`,`plies` | 闯关走一步：引擎评分 + 谱内判定 + 对手应招 |
| `quiz_next` | `id`,`idx` | 默写出题：返回局面与 4 个候选 |
| `demo_step` | `id`,`idx` | **演示**：返回第 `idx` 手（0 起）的讲解、走法特征、引擎评述与走完后的局面；`idx` 越界返回 `done:true`。别名 `train_demo` |

三个页面（同一个链接，用 `view` 参数区分）：
- `GET /` —— 对弈页
- `GET /?view=narrate` —— 实时旁白页
- `GET /?view=train` —— 开局练习页

---

## 依赖与环境

| 依赖 | 说明 | 安装 |
|---|---|---|
| python-chess | 锁 `1.999`（镜像可获取且已验证兼容；`1.11.2` 在该镜像不存在） | `pip install python-chess==1.999` |
| Stockfish | 引擎二进制，默认路径 `/usr/games/stockfish` | 下载官方预编译二进制 |
| flask | 形态二/三后端 | `pip install flask` |
| matplotlib | 雷达图（需 Noto Sans CJK 字体） | `pip install matplotlib` |

`play/requirements.txt`：`flask` + `python-chess==1.999`（必须保留，publish 靠它判定为 python 项目）。

> **手机端**：后端跑在沙箱云端，手机只渲染网页，无需装引擎。前提：① 手机能访问发布链接；② 沙箱存活。

---

## 技能存放位置与加载机制（常见疑问）

技能有**两个合法位置**，客户端都会扫描（已核对客户端实现）：

| 作用域 | 路径 | 特点 |
|---|---|---|
| **project** | `<工作目录>/.codebuddy/skills/chess-coach/`，即 `/workspace/.codebuddy/skills/chess-coach/` | 跟着项目走，换沙箱/重建项目仍在；**本项目的首选位置** |
| **user** | `/root/.codebuddy/skills/chess-coach/` | 全局注册，同沙箱内所有项目可见；沙箱重建会丢 |
| 开发副本 | `/workspace/chess-coach/` | 源码与调试主目录 |

> 扫描顺序：先 project 后 user，**同名技能以 project 优先**（重复的会被跳过）。所以只要 `/workspace/.codebuddy/skills/chess-coach/` 存在，即使全局目录丢了也能被发现。

| 问题 | 答案 |
|---|---|
| **新会话会自动加载吗** | 技能以 **元数据（`name` + `description`）常驻注入**所有会话；**正文按需加载**——只有当我判断任务匹配 description 里的触发词时，才读 SKILL.md 全文执行 |
| **为什么上次新会话说"找不到技能"** | 当时 `/workspace/.codebuddy/skills/` 尚未建立，且 description 缺"开局"类触发词；两者都已修复 |
| **怎样确保被触发** | 说关键词即可：`学开局`/`练开局`/`意大利开局`/`伦敦体系`、`复盘 PGN`、`来一局`/`陪练`、`看看这盘`；或直接点名"用 chess-coach 技能" |
| **改动后要做什么** | 改 `/workspace/chess-coach/` 后同步三处（见下方命令），否则新会话仍读旧版 |
| **改完要重启吗** | 不需要。客户端对 `.codebuddy/skills` 有文件监听（约 3 秒防抖热重载） |

**同步命令**（改完源码副本后执行）：

```bash
cp /workspace/chess-coach/SKILL.md /workspace/.codebuddy/skills/chess-coach/SKILL.md
cp /workspace/chess-coach/SKILL.md /root/.codebuddy/skills/chess-coach/SKILL.md
```

> 若整份技能有改动（脚本也变了），用整目录覆盖：`cp -r /workspace/chess-coach/. /workspace/.codebuddy/skills/chess-coach/`。
> 另有 `CODEBUDDY_SESSION_SKILL_DIRS` 环境变量可追加临时技能目录，一般用不到。

---

## 跨会话访问（重要，需如实告知用户）

| 情况 | 能否访问 | 说明 |
|---|---|---|
| 同一沙箱内新开对话 | ✅ 能 | 链接有效期约 5 年，服务在沙箱活着时持续可访问 |
| 沙箱休眠/被回收 | ⚠️ 暂时不能 | 链接仍在，但后端进程停了；重新跑 publish 即可恢复（幂等，回到同一链接） |
| 沙箱重建 | ❌ 链接失效 | runtimeId 变了，appName 随之变化，会得到新链接 |

**恢复命令**（沙箱重启后）：
```bash
cd /root/.codebuddy/skills/sites/scripts
node publish.js --dir /root/.codebuddy/skills/chess-coach/play --port 8080 --language python
```

> 链接是**公开分享链接**（带 `sharecode`），任何拿到链接的人都能访问与对弈。如需收回，用 `sites` 技能的 unpublish 能力取消发布。

---

## 关键约束

- **引擎事实先行**：走子由 Stockfish 决定，LLM 不自行算棋。点评分级/战术原因复用 `scripts/analyze.py` 的 `classify / tactical_reason / phase_of`。
- **引擎并发加锁**：`app.py` 中 `eval_white` / `coach_reply` 内置 `_engine_lock`，避免桥线程与用户请求争抢同一引擎实例导致崩溃。
- **难度可调**：改 `coach_reply` 的 `skill`（`4`=可战胜、`8`=较强、`20`=满血）后重发布。

## 不适用

- 中国象棋 / 围棋（需换引擎：Pikafish / KataGo，属路线 C 扩展）
- 用户没有任何棋谱数据且拒绝导出 PGN → 先引导导出

## 记忆库落库规则（重要）

- **只写入真实学员数据**：画像 + 训练计划确认后，将精简版（维度评分、最弱项、计划要点、日期）存入 WorkBuddy 记忆库，实现跨会话跟踪。
- **演示/合成数据不落库**：`samples/` 生成的 "Student" 绝不写入用户记忆库。
- 每次复测后**更新**记忆库条目而非新建，保留"维度变化曲线"。

## 输出物清单

| 文件 | 内容 |
|---|---|
| `scripts/analyze.py` | 逐着分析引擎（分级/精度/最佳着/战术原因） |
| `scripts/profile.py` | 六维画像（0-100 + 最弱三项 + 关键错误） |
| `scripts/radar.py` | 能力雷达图（中文字体） |
| `play/app.py` | 后端：`action` 分发 + 引擎单例 + 桥线程 + undo/peek/note/feed |
| `play/bridge.py` | 常驻观战桥：轮询 watch，写 feed，生成规则解说 |
| `play/board_page.txt` | 对弈页（落子/KPI/评估/点评/历史回看/悔棋/点评卡片） |
| `play/narrate_page.txt` | 实时旁白页（只读解说流） |
| `play/train_page.txt` | 开局练习页（选开局 / 闯关 / 默写 三个 tab） |
| `scripts/openings.py` | 开局库单一数据源（12 条，含 `ideas` / `traps`） |
| `scripts/step_notes.py` | **逐步讲解文案**（演示模式用，与 `openings.moves` 逐手对应） |
| `scripts/train_core.py` | 闯关评定 / 出题 / 演示讲解核心（`drill_move` / `quiz_next` / `demo_step`），主应用与独立服务共用 |
| `scripts/train.py` | 独立练习小服务（端口 8090，非必需） |
| `scripts/sync_skill.sh` | 把源码同步到 project / user 两处注册目录，并校验三处一致 |
| `play/requirements.txt` | 依赖声明（publish 据此判定项目类型） |
| `report/*.json` `report/*.png` | 画像数据与雷达图 |

## 提示词库

教练层语气、结构与约束见 [references/prompts.md](references/prompts.md)。核心纪律：
- 引擎数据永远先行，解释必须引用真实 `loss_cp` / `label` / 最佳着；
- 逐着点评绝不剧透后续变化；
- 无法从数据确认的内容显式声明，不编造变例。
