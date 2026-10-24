# 棋盘 UI 组件（CBoard）

对弈页与练习页（演示/闯关/默写）共用同一套棋盘 UI，避免两边样式漂移。组件文件：

- `play/board.css` — 棋盘样式（CSS 变量驱动）
- `play/board.js` — 渲染逻辑（暴露全局 `CBoard`）

由 `play/app.py` 的白名单路由 `/<fname>`（`board.css` / `board.js`）按需从磁盘读取下发，并带 `no-cache`，所以**改组件文件即时生效、无需重启 `app.py`**；对照之下 `.txt` 页面是启动读入内存的，改了要重启。

## 渲染入口

```js
CBoard.render(el, fen, {
  sel:   'e2',            // 选中格（落子前选中的起点）
  tgts:  ['e4', 'e3'],    // 合法目标格（可含升变后缀 'e8q'，自动按基格匹配）
  hl:    ['e2', 'e4'],    // 高亮格（上一步起止）
  coords: true,           // 坐标标注（默认开；false 关闭）
  onClick: (sqName) => {} // 点击回调
});
```

`parseFen` 也挂在组件上：`CBoard.parseFen(fen)`。练习页的 `renderBoard(el, fen, sel, tgts, hl, onClick)` 只是包了一层 `CBoard.render`，改底层样式一处生效。

## 主题（换底色）

主题用 CSS 变量控制，默认在 `board.css` 的 `:root`：

```css
--cb-light: #eee9d8;   /* 浅格 */
--cb-dark:  #6f9a5e;   /* 深格 */
--cb-sel:   #3b82f6;   /* 选中框 */
--cb-last:  #f6e05e;   /* 上一步高亮 */
--cb-dot:   rgba(20,24,29,.38);  /* 合法落点 */
--cb-border:#11151c;   /* 边框 */
```

页面头部的「🎨 底色」按钮调 `CBoard.cycleTheme()`，循环 4 套预设（经典绿 / 蓝灰 / 胡桃木 / 石板灰），用 `localStorage('cb-theme')` 记忆，**对弈页与练习页同步生效**。加主题只需在 `board.js` 的 `THEMES` 里加一组 `{light, dark}`。

坐标标注用半透明配色（浅格黑 40%、深格白 75%），适配任意底色主题，不写死颜色。

## 已修的布局坑

- **格子必须正方形**：`.board` 要**同时**写 `grid-template-columns: repeat(8,1fr)` 与 `grid-template-rows: repeat(8,1fr)`。只写 columns 时，行高按内容自适应 → 没棋子的空行被压扁（用户报的"中部格子扁"就是这个）。
- **棋子用实心字形 + 颜色区分**：白子 `#fff` + 黑色描边、黑子 `#16181d` + 白色描边，不依赖空心/实心字形差异——部分环境缺字体回退会把黑白都渲染成空心。
- **合法落点**：空格画实心点、有子的格画环（`cap` 类），颜色统一用 `--cb-dot`，在浅/深格上都可见（早期版本在大漏对比下用了蓝色，已统一）。
