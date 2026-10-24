# 如何扩展：新增开局与演示文案

开局数据集中在**单一数据源** `scripts/openings.py`（`OPENINGS` 列表），练习页三种模式、对弈页开局模式都从它读。新增一条开局通常只改这一个文件，再配套写演示文案。

## 1. 在 `scripts/openings.py` 加一条

```python
{
    "id": "my_opening",          # 唯一标识，用于接口 id 参数
    "name": "我的开局",           # 中文名
    "en": "My Opening",          # 英文名
    "family": "e4",              # e4 / d4（决定列表分组）
    "side": "white",             # 学习者执白 / 执黑
    "level": 1,                  # 1=入门 2=进阶
    "moves": ["e2e4", "e7e5", ...],   # 标准主变（UCI，纯小写）
    "ideas": ["为什么这样走…", ...],   # 关键想法（教学，不背谱）
    "traps": ["别踩的坑…", ...],      # 易错点
}
```

注意 `moves` 用 **UCI**（如 `e2e4`），不是 SAN；`side` 决定哪一方按主变走。`moves` 长度就是闯关/默写的题目数。

## 2. 配套写演示文案 `scripts/step_notes.py`

`step_notes.py` 里 `NOTES` 按 `id` 给出**每手一句**的人话讲解，**列表长度必须与对应开局的 `moves` 长度相等**，否则演示步进会越界报错。文案里可用 `**加粗**`，组件会自动转成 `<b>`。

```python
NOTES = {
    "my_opening": [
        "第 1 手讲解…",
        "第 2 手讲解…",
        # ……与 moves 一一对应
    ],
}
```

校验脚本（开发时手跑一遍）：

```python
for o in OPENINGS:
    assert len(NOTES.get(o["id"], [])) == len(o["moves"]), o["id"]
```

## 3. 若要让对弈页「开局模式」也能选它

对弈页 `board_page.txt` 里的 `OPENS` 数组是**硬编码**的开局列表（含 id/中文名/体系），新增后需手动同步加一行，`handle_open` 才找得到。

## 4. 本地验证

```bash
# 列表是否包含
curl -s -X POST localhost:8080 -H 'Content-Type: application/json' \
  -d '{"action":"list"}' | python3 -c 'import sys,json;print([o["id"] for o in json.load(sys.stdin)])'
# 演示第 0 手
curl -s -X POST localhost:8080 -H 'Content-Type: application/json' \
  -d '{"action":"demo_step","id":"my_opening","idx":0}'
```

## 设计原则：练理解，不死背

每条开局都配 `ideas`（为什么这样走）和 `traps`（别踩什么坑），而不只是给一串着法。闯关判定里 `offbook`（谱外但不太亏）会提示"谱内应走什么"，引导理解结构而非机械记忆。
