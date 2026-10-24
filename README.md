# chess-coach — 棋类 AI 教练（路线 A · MVP）

> WorkBuddy 技能版"AI 教练"：上传 PGN → 多维能力画像 → 教练点评 → 一周训练计划 → 记忆库长期跟踪。
> 技术起点：[chessli2](https://github.com/pwenker/chessli2) 的"对局→弱点"骨架 + python-chess + Stockfish 服务端分析 + CheckPause 式 LLM 解释设计。

## 目录结构

```
chess-coach/
├── SKILL.md                 # 技能清单（工作流 + 记忆库落库规则）
├── README.md
├── references/
│   └── prompts.md           # LLM 教练层提示词库（CheckPause 式）
├── scripts/
│   ├── analyze.py           # 分析引擎：python-chess + Stockfish 逐着分析
│   ├── profile.py           # 画像引擎：六维能力评分 + 最弱项 + 关键错误
│   └── radar.py             # 雷达图生成
├── samples/
│   ├── sample_game.pgn      # 演示样例（合成对局，保证合法）
│   └── gen_sample.py        # 样例生成器（开发用）
└── report/                  # 演示产物（真实使用时按用户会话生成）
    ├── analysis.json
    ├── profile.json
    ├── profile_radar.png
    └── AI教练画像报告.md
```

## 快速开始

```bash
# 1. 依赖（沙箱内已验证）
sudo pip3 install python-chess matplotlib
sudo apt-get update && sudo apt-get install -y stockfish   # 引擎 → /usr/games/stockfish

# 2. 逐着分析（--player 指定学员，匹配 PGN 的 White/Black 头）
python3.11 scripts/analyze.py your_games.pgn --player YourName --out analysis.json

# 3. 多维画像
python3.11 scripts/profile.py analysis.json --out profile.json

# 4. 雷达图
python3.11 scripts/radar.py profile.json --out profile_radar.png

# 5. 教练层：按 references/prompts.md 由 LLM（agent）生成报告
```

## 分析口径（与主流工具对齐）

- **走子分级**（CheckPause 式）：Best（≤10cp 且为引擎首选）/ Good（<40）/ Inaccuracy（40–100）/ Mistake（100–300）/ Blunder（≥300）
- **精度评级**（五档，按 ACPL）：Optimal ≤10 · Precise 10–30 · Competent 30–60 · Steady 60–100 · Volatile >100
- **损失封顶**：ACPL 计算时单着损失封顶 400cp，避免"输定局面每步都被判大损失"的失真
- **六维画像**（0–100）：开局稳定性 / 中局计划 / 残局技术 / 计算精准度 / 战术纪律 / 心理稳定性（领先局面转化率；样本不足时记 70 并标注）

## 与两条后续路线的衔接

- **路线 B（Web 训练器）**：本技能的 `analysis.json` 可直接作为前端复盘界面的数据源（react-chessboard + Stockfish.wasm）。
- **路线 C（中国象棋平移）**：引擎换 Pikafish、PGN 换象棋谱，画像框架复用。
