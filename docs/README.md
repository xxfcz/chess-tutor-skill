# docs/ — 开发要点与经验沉淀

面向接手本项目的开发者 / AI 代理，按主题拆分：

| 文档 | 内容 |
|---|---|
| [architecture.md](architecture.md) | 四种形态的架构、数据流、页面分发、引擎进程管理 |
| [dev-workflow.md](dev-workflow.md) | 如何运行 / 改完怎么生效 / 发布网页 / Playwright 实测 / 接口速查 |
| [engine-gotchas.md](engine-gotchas.md) | 引擎评分的 8 个踩坑（配色视角、is_best、谱内维度、并发锁…） |
| [board-ui.md](board-ui.md) | 共用棋盘组件 CBoard 的用法、主题与换底色、已修的布局坑 |
| [adding-openings.md](adding-openings.md) | 如何新增一条开局 + 配套演示文案 |
| [HANDOFF.md](HANDOFF.md) | **新会话接手快照**：30 秒上手 / 代码地图 / 进度 / 待办 / 已知坑 / 沙箱机制 |
| [session-usage.md](session-usage.md) | 会话 token 用量报告：统计口径、增长曲线、成本结论（配合 `scripts/usage_stats.py`） |
| [后端共享架构方案.md](后端共享架构方案.md) | 三项目后端复用决策：本项目定位为"规范与种子数据真相源" |

> 顶层 `AGENTS.md` 是入口总纲，`SKILL.md` 是技能层面的权威约定（触发词 + 工作流 + 接口）。
> 三者关系：**AGENTS.md（给开发者）→ SKILL.md（给技能运行时）→ 各 docs（经验细节）**。
