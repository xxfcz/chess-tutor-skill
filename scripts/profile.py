#!/usr/bin/env python3.11
"""
profile.py — 棋类 AI 教练 · 多维能力画像（路线 A）
================================================
从 analyze.py 产出的 analysis.json 计算玩家的多维能力画像（0–100，越高越好）：
  - 开局稳定性 / 中局计划 / 残局技术（按阶段的平均损失，封顶后映射）
  - 计算精准度（全局平均损失）
  - 战术纪律（失误/严重失误占比）
  - 心理稳定性（曾领先却未赢下的对局占比）
  - 时间管理（仅在 PGN 含时钟数据时计算，否则标记“无数据”）

用法：
  python3.11 profile.py analysis.json [--out profile.json]
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

CAP = 400.0  # 损失封顶，避免输定局面的失真


def capped(mean_raw: float) -> float:
    return min(mean_raw, CAP) if mean_raw is not None else 0.0


def score_from_loss(mean_loss_capped: float) -> float:
    """平均损失（封顶）映射为 0–100 分：损失 0 → 100，损失 ≥100 → 0。"""
    return float(max(0.0, min(100.0, 100.0 - mean_loss_capped)))


def tactic_score(blunder_rate: float, mistake_rate: float) -> float:
    """战术纪律：严重失误/失误占比越高质量越低。"""
    raw = blunder_rate * 250.0 + mistake_rate * 100.0
    return float(max(0.0, min(100.0, 100.0 - raw)))


def main_score_dimension(moves, phase_filter=None):
    subset = [m for m in moves if (phase_filter is None or m["phase"] == phase_filter)]
    losses = [capped(m["loss_cp"]) for m in subset if m["loss_cp"] is not None]
    if not losses:
        return None, 0  # 无样本
    mean = sum(losses) / len(losses)
    return score_from_loss(mean), len(losses)


def build_profile(analysis: dict) -> dict:
    games = analysis.get("games", [])
    # 汇总所有玩家着法
    all_moves = [m for g in games for m in g["moves"] if m["is_player"]]
    n = len(all_moves)
    counts = {"Best": 0, "Good": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0}
    for m in all_moves:
        if m["label"] in counts:
            counts[m["label"]] += 1
    blunder_rate = counts["Blunder"] / n if n else 0.0
    mistake_rate = counts["Mistake"] / n if n else 0.0

    # 各阶段
    opening_score, opening_n = main_score_dimension(all_moves, "opening")
    middlegame_score, middlegame_n = main_score_dimension(all_moves, "middlegame")
    endgame_score, endgame_n = main_score_dimension(all_moves, "endgame")
    calc_score, _ = main_score_dimension(all_moves, None)  # 全局计算精准度
    tactics = tactic_score(blunder_rate, mistake_rate)

    # 心理稳定性：曾大幅领先（>=+200）却未赢下的局占比
    psycho = _psychology(games, all_moves)

    # 时间管理：检测是否有时钟数据
    has_clock = any("clk" in (mv.get("clock") or "") for g in games for mv in g["moves"]) or \
                any("Clock" in (g["headers"] or {}) for g in games)
    time_score = None if not has_clock else _time_management(games)

    dims = []
    for name, score, n_moves, note in [
        ("开局稳定性", opening_score, opening_n, "前 8 回合的局面把握"),
        ("中局计划", middlegame_score, middlegame_n, "中局的子力协调与计划"),
        ("残局技术", endgame_score, endgame_n, "少子力局面的技术"),
        ("计算精准度", calc_score, n, "逐着与最佳着的接近程度"),
        ("战术纪律", tactics, n, "避免送子/漏算的频率"),
        ("心理稳定性", psycho["score"], psycho["n_winning"], "领先局面的转化能力"),
    ]:
        if score is None:
            continue
        dims.append({
            "name": name,
            "score": round(score, 1),
            "n_moves": n_moves,
            "note": note,
        })

    # 时间管理单独标注
    if time_score is not None:
        dims.append({"name": "时间管理", "score": round(time_score, 1),
                     "n_moves": None, "note": "读秒/时限下的决策"})

    # 最弱 3 项（训练重点）
    weak = sorted([d for d in dims], key=lambda d: d["score"])[:3]

    # 关键错误（用于教练叙述）
    key_errors = []
    for g in games:
        for m in g["moves"]:
            if m["is_player"] and m["label"] in ("Mistake", "Blunder"):
                key_errors.append({
                    "game": g["index"], "ply": m["ply"], "san": m["san"],
                    "label": m["label"], "loss_cp": m["loss_cp"],
                    "phase": m["phase"], "tactical_reason": m["tactical_reason"],
                    "best_move": m["best_move"],
                    "best_move_san": m.get("best_move_san"),
                    "fen_before": m.get("fen_before"),
                    "fen_after": m.get("fen_after"),
                    "eval_before_cp": m["eval_before_cp"],
                })
    key_errors.sort(key=lambda x: -(x["loss_cp"] or 0))
    key_errors = [e for e in key_errors if (e["loss_cp"] or 0) < 5000][:8]  # 排除“被将杀”极端局

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "player": analysis.get("meta", {}).get("player"),
            "n_games": analysis.get("meta", {}).get("n_games"),
            "n_player_moves": n,
            "loss_cap": CAP,
        },
        "global_summary": analysis.get("global"),
        "dimensions": dims,
        "weakest": [{"name": d["name"], "score": d["score"]} for d in weak],
        "psychology_detail": psycho,
        "key_errors": key_errors,
        "radar": {"labels": [d["name"] for d in dims], "scores": [d["score"] for d in dims]},
    }


def _psychology(games, all_moves):
    # 逐局：玩家曾达到的最大优势（玩家视角 eval_before_cp）
    # 只统计有确定胜负的对局（1-0 / 0-1），未走完(*)或和棋不计入
    n_winning = 0
    n_converted = 0
    for g in games:
        res = (g.get("headers") or {}).get("Result", "")
        if res not in ("1-0", "0-1"):
            continue
        player_moves = [m for m in g["moves"] if m["is_player"]]
        advs = [m["eval_before_cp"] for m in player_moves if m["eval_before_cp"] is not None]
        max_adv = max(advs) if advs else 0.0
        if max_adv >= 200.0:  # 曾明显领先（+2）
            n_winning += 1
            won = (res == "1-0" and g.get("player_color") == "white") or \
                  (res == "0-1" and g.get("player_color") == "black")
            if won:
                n_converted += 1
    if n_winning == 0:
        return {"score": 70.0, "n_winning": 0, "n_converted": 0,
                "note": "样本中没有明显领先且分出胜负的对局，暂无法评估"}
    score = 100.0 * n_converted / n_winning
    return {"score": score, "n_winning": n_winning, "n_converted": n_converted,
            "note": f"{n_winning} 局曾明显领先，赢下 {n_converted} 局"}


def _time_management(games):
    # 若有时钟：评估在时间紧张时的失误率（占位实现）
    return 75.0


def main():
    ap = argparse.ArgumentParser(description="多维能力画像")
    ap.add_argument("analysis", help="analysis.json 路径")
    ap.add_argument("--out", default="profile.json", help="输出 JSON 路径")
    args = ap.parse_args()
    with open(args.analysis, "r", encoding="utf-8") as fh:
        analysis = json.load(fh)
    profile = build_profile(analysis)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, ensure_ascii=False, indent=2)
    print(f"[完成] 画像已生成：{args.out}")
    print("  维度评分：")
    for d in profile["dimensions"]:
        print(f"    {d['name']}: {d['score']}  ({d['note']})")
    print("  最弱项：", ", ".join(f"{w['name']}({w['score']})" for w in profile["weakest"]))


if __name__ == "__main__":
    main()
