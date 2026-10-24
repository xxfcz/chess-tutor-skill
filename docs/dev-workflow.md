# 开发工作流与测试

## 启动与改代码生效规则

| 改动对象 | 是否需要重启 `app.py` | 说明 |
|---|---|---|
| `play/*.py`、`scripts/*.py` | **必须重启** | import 时读入内存 |
| `play/*.txt`（页面 HTML） | **必须重启** | 启动时被整段读入 `INDEX_HTML` 等变量 |
| `play/board.css` / `play/board.js` | **不用重启** | 运行时按请求从磁盘读 + `no-cache` |
| 技能注册目录 | 不用重启会话 | 客户端对 `.codebuddy/skills` 有 ~3s 防抖热重载 |

重启命令（注意 `pkill -f "app.py"` 会误伤当前命令行，用 pid 方式）：

```bash
kill $(pgrep -f "app.py") 2>/dev/null; sleep 1
cd /workspace/chess-coach/play && (setsid python3 app.py > /tmp/chess_app.log 2>&1 &)
```

改完源码副本后同步技能目录：

```bash
bash /workspace/chess-coach/scripts/sync_skill.sh
```

## 发布为可分享网页

```bash
cd /root/.codebuddy/skills/sites/scripts
node publish.js --dir /root/.codebuddy/skills/chess-coach/play --port 8080 --language python
```

- 返回 `shareLink`，形如 `https://<app>.app.workbuddy.host/?sharecode=XXXX`，有效期约 5 年。
- **同一 runtime 只能发布一个服务**：本项目三个页面合并为单应用，**不要为练习页再发布一次**（会覆盖并 kill 旧服务）。
- 端口必须等于 `app.py` 默认 `8080`；publish 对 python 项目不注入 `$PORT`。
- 沙箱重启自恢复：`/workspace/.cloudstudio` 的 `[[app]]` 先跑 `sync_skill.sh` 再起 `app.py`。

## 浏览器实测（Playwright）

棋盘/落子/演示这类改动，用无头浏览器验证最稳。参考脚本放在仓库外，关键断言：

- 棋盘 64 格 `getBoundingClientRect().height` 的 min/max 应相等（验证不是扁格子）。
- 对弈页：点 `e2 → e4`，断言 `.sq.hl` 含 `e2`/`e4`，`.sq[data-sq="e4"] .pc` 存在，`status` 回到"轮到你"。
- 演示页：点「下一步」后 `#mcard .msg` 有文案、`#mprog` 更新、`#mboard .sq.hl` 有起止格。
- 闯关页：点 `e2` 出现 `.sq.sel[data-sq="e2"]`，走 `e4` 后判定为"最佳"、进度 `+1`。
- 默写页：`#qboard .sq` 为 64 个、`#qopts .qo` 为 4 个。
- 换底色：点「🎨 底色」后 `getComputedStyle(document.documentElement).getPropertyValue('--cb-light')` 改变，刷新后 `localStorage('cb-theme')` 仍生效。

运行前确认 `NODE_PATH` 指向全局 `playwright`（如 `NODE_PATH=$(npm root -g)`）。

## 接口速查（`POST /`，`action` 分发）

| action | 作用 |
|---|---|
| `new` / `watch` / `feed` | 开新局 / 读当前局面（只读）/ 读完整事件流 |
| `note` | 追加 `coach_note`（AI 点评写入通道） |
| `legal` / `move` / `undo` / `peek` | 合法目标 / 学员落子 / 悔棋截断 / 只读预览某步 |
| `open` | 进入对弈页开局模式 |
| `list` / `ideas` | 列开局库 / 取关键想法与易错点 |
| `drill_start` / `drill_move` | 开始/进行闯关 |
| `quiz_next` | 默写出题 |
| `demo_step`（别名 `train_demo`） | 演示第 idx 手讲解；越界返回 `done:true` |

三个页面（`view` 参数区分）：`/` 对弈、`/?view=narrate` 旁白、`/?view=train` 练习。

## 记忆库落库纪律

- 只写入真实学员数据（维度评分、最弱项、计划要点、日期），实现跨会话跟踪。
- 演示/合成数据（`samples/`）**绝不**写入用户记忆库。
- 复测后**更新**已有条目而非新建，保留维度变化曲线。
