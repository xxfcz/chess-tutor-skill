# 引擎与评分：踩过的坑（必读）

这些是开发中反复踩过、已修掉的真实坑。再加评估/演示逻辑时先回来对照。

## 1. 评分配色必须用「走子方视角」

`python-chess` 的 `score.pov(WHITE)` 会把黑方回合的局面也翻成"白方视角"，导致黑方回合的 `loss` 出现负数。

```python
# ✅ 正确：全程以"走子方视角"为基准
sc = info["score"].pov(board.turn).score(mate_score=100000)
# 展示时再乘 sign 转成白方视角
sign = 1 if board.turn == chess.WHITE else -1
cp_white = chosen_cp * sign
```

```python
# ❌ 错误：黑方回合直接用 pov(WHITE) 会让 loss 变负
sc = item["score"].pov(chess.WHITE).score(mate_score=100000)
```

`train_core.demo_step` 与 `app.py` 的 `eval_white` 都遵循同一约定：`pov(board.turn)` 算损失，展示时再乘 `sign`。

## 2. `is_best` 用评分差判定，而非名次

multipv 前三常有并列同分，名次排序不稳定。判定"是否最佳"应看与首选的评分差：

```python
loss = round(float((best_cp or 0) - (chosen_cp or 0)), 1)
if loss < 0: loss = 0.0
is_best = loss <= 3          # 用阈值，不比 top[0] == san
```

## 3. 所走的步不在引擎前三时，要补进候选列表

用户正在看的那一步若不在 multipv 前三，UI 会显示"候选前三里没有当前步"。在 `demo_step` 里把它单独补进去并标 `is_chosen: True`：

```python
if not any(t["is_chosen"] for t in top):
    top.append({"san": san, "cp_white": cp_white, "is_chosen": True})
```

## 4. 开局阶段 cp 差普遍偏小，单看绝对 cp 会误判

开局优势本就微小，`1.a3` 这种也得不了几分，但也不能算"好棋"。所以判定引入**是否在谱内**作为独立维度：

```python
if q["rank"] == 1 and q["loss"] <= 25:
    verdict = "excellent"
elif q["loss"] > 120:
    verdict = "bad"
elif q["loss"] > 50:
    verdict = "inaccuracy"
elif (not in_book) and q["rank"] is None:
    verdict = "offbook"   # 谱外但损失小：非主变，不算坏棋
```

## 5. 走子后局面评估要"走前/走后"分开算

- 计算"本步损失"：`(走前局面下首选的评分) - (走完这一步后局面的评分)`，两边都在各自走子方视角。
- 若所走步不在前三，需对"走后的局面"单独 `analyse` 一次，再翻回走子方视角。
- `loss` 出现负值时一定要 `if loss < 0: loss = 0.0` 兜底（浮点/排序边界会出现）。

## 6. 引擎并发必须加锁

`app.py` 的 `eval_white`/`coach_reply` 与 `train_core.engine()` 都走同一把 `_lock`。桥线程（1.5s 轮询）与用户实时落子会并发访问引擎，不加锁会争抢同一引擎实例导致崩溃或服务挂死。

## 7. 引擎进程要显式关闭

脚本退出 / 热重载前调 `close_engine()`（已 `atexit` 注册）。曾因管道方式退出时引擎没退出，留下僵尸 Stockfish 占资源。

## 8. 演示/复盘不要自动生成 AI 点评

演示模式是纯前端 + 引擎，不产生 `coach_note`。用户想要针对性点评要回会话说「讲讲这盘开局」，再由 LLM 读 `openings.py` 的 `ideas`/`traps` + 引擎数据写 `note`。页面底部有明确提示，别让用户误以为会自动收到点评。
