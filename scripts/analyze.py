#!/usr/bin/env python3.11
"""
analyze.py — 棋类 AI 教练 · 分析引擎（路线 A）
=============================================
基于 python-chess + Stockfish（服务端分析），把一份 PGN 拆成逐着的结构化数据：
  - 每着的引擎评估（前后局面 cp）
  - CheckPause 式走子分级：Best / Good / Inaccuracy / Mistake / Blunder
  - 阶段标注：opening / middlegame / endgame
  - 战术原因（轻量启发式）：漏算吃子、主动送子、判断/计算偏差
  - 每局 ACPL、精度%、五档评级（Optimal/Precise/Competent/Steady/Volatile）

用法：
  python3.11 analyze.py <pgn> [--engine /usr/games/stockfish] [--player NAME]
                          [--time 0.12] [--depth 16] [--out analysis.json]

说明：
  - --player 指定要辅导的一方（匹配 PGN 的 White/Black 头）。省略时默认分析白方。
  - 对手的着法仅作为评估上下文，不计入该方画像。
"""
from __future__ import annotations

import argparse
import chess
import chess.pgn
import chess.engine
import json
import io
import os
import sys
from datetime import datetime, timezone

# ---------- 分级阈值（cp loss，正=该方走差了）----------
# 参考 lichess / CheckPause 思路，按“损失分”划分
LABEL_THRESHOLDS = [
    ("Blunder", 300),     # 损失 >= 300cp
    ("Mistake", 100),     # 损失 >= 100cp
    ("Inaccuracy", 40),   # 损失 >= 40cp
    ("Good", 0),          # 损失 < 40cp（含接近最佳）
]
# 接近最佳（损失极小且等于引擎首选）单独标记为 Best
BEST_LOSS_MAX = 10


def classify(loss_cp: float, is_best: bool) -> str:
    if is_best and loss_cp <= BEST_LOSS_MAX:
        return "Best"
    for label, thr in LABEL_THRESHOLDS:
        if loss_cp >= thr:
            return label
    return "Good"


# ---------- 阶段判定 ----------
def phase_of(board: chess.Board, ply: int) -> str:
    # ply 从 1 开始（第一着）
    if ply <= 16:
        return "opening"
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    minors_rooks = 0
    for p in board.piece_map().values():
        if p.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK):
            minors_rooks += 1
    if queens == 0 and minors_rooks <= 6:
        return "endgame"
    if ply >= 60 and minors_rooks <= 6:
        return "endgame"
    return "middlegame"


# ---------- 战术原因（轻量启发式）----------
def is_hanging(board: chess.Board, square: chess.Square) -> bool:
    """square 上的子是否被对方攻击且基本无保护（粗略判断）。"""
    piece = board.piece_at(square)
    if piece is None:
        return False
    attackers = board.attackers(not piece.color, square)
    if not attackers:
        return False
    defenders = board.attackers(piece.color, square)
    atk_vals = [1 if board.piece_at(sq).piece_type == chess.PAWN
                else {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5,
                      chess.QUEEN: 9}.get(board.piece_at(sq).piece_type, 3)
                for sq in attackers]
    atk_min = min(atk_vals)
    def_val = 99
    if defenders:
        def_val = min(1 if board.piece_at(sq).piece_type == chess.PAWN
                      else {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5,
                            chess.QUEEN: 9}.get(board.piece_at(sq).piece_type, 3)
                      for sq in defenders)
    return atk_min <= def_val


def tactical_reason(board_before: chess.Board, move: chess.Move,
                    board_after: chess.Board, color: chess.Color,
                    best_move: chess.Move, loss_cp: float) -> str | None:
    """返回一个简短的战术原因（启发式），或 None。"""
    if loss_cp < 40:
        return None
    before_hanging = any(p.color == color and is_hanging(board_before, sq)
                         for sq, p in board_before.piece_map().items())
    after_hanging = any(p.color == color and is_hanging(board_after, sq)
                        for sq, p in board_after.piece_map().items())
    if (not before_hanging) and after_hanging:
        return "主动送子/漏算防御：走子后己方子力悬空被吃"
    if best_move and board_before.is_capture(best_move) and loss_cp >= 100:
        return "错失战术机会：可吃子/得子却未走"
    return "判断或计算偏差：未识别局面关键点"


# ---------- 评估 ----------
def cp_of(score: chess.engine.Score, turn: chess.Color) -> float:
    """把 Score 转成以 turn 视角为中心的 cp（含将杀处理）。"""
    s = score.pov(turn)
    val = s.score(mate_score=100000)
    if val is None:
        return 0.0
    return float(val)


def analyze_pgn(path: str, engine_path: str, player: str | None,
                time_limit: float, depth_limit: int) -> dict:
    engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    try:
        engine.configure({"Hash": 128, "Threads": 2})
        limit = chess.engine.Limit(time=time_limit, depth=depth_limit)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            pgn_text = fh.read()

        games_out = []
        stream = io.StringIO(pgn_text)
        reader = chess.pgn.read_game(stream)
        game_index = 0
        while reader is not None:
            game_index += 1
            headers = dict(reader.headers)
            white = headers.get("White", "")
            black = headers.get("Black", "")
            if player:
                if player.lower() == white.lower():
                    player_color = chess.WHITE
                elif player.lower() == black.lower():
                    player_color = chess.BLACK
                else:
                    player_color = None
            else:
                player_color = chess.WHITE

            board = reader.board()
            moves = []
            ply = 0
            for node in reader.mainline():
                ply += 1
                move = node.move
                mover = board.turn
                is_player_move = (player_color is not None and mover == player_color)
                eval_before = None
                best_move = None
                loss_cp = None
                label = None
                reason = None
                eval_after = None
                if is_player_move:
                    info_before = engine.analyse(board, limit)
                    score_before = info_before["score"]
                    eval_before = cp_of(score_before, mover)
                    pv = info_before.get("pv")
                    best_move = pv[0] if pv else None
                    board_after_tmp = board.copy()
                    board_after_tmp.push(move)
                    if board_after_tmp.is_game_over():
                        if board_after_tmp.is_checkmate():
                            eval_after = 100000.0 if mover else -100000.0
                        else:
                            eval_after = 0.0
                    else:
                        info_after = engine.analyse(board_after_tmp, limit)
                        eval_after = cp_of(info_after["score"], mover)
                    loss_cp = eval_before - eval_after
                    is_best = (best_move is not None and move == best_move)
                    label = classify(loss_cp, is_best)
                    reason = tactical_reason(board, move, board_after_tmp, mover,
                                             best_move, loss_cp)
                    fen_before = board.fen()
                    fen_after = board_after_tmp.fen()
                    best_san = board.san(best_move) if best_move else None
                else:
                    fen_before = fen_after = best_san = None
                san = board.san(move)
                uci = move.uci()
                moves.append({
                    "ply": ply,
                    "san": san,
                    "uci": uci,
                    "color": "white" if mover == chess.WHITE else "black",
                    "is_player": is_player_move,
                    "phase": phase_of(board, ply),
                    "label": label,
                    "loss_cp": round(loss_cp, 1) if loss_cp is not None else None,
                    "eval_before_cp": round(eval_before, 1) if eval_before is not None else None,
                    "eval_after_cp": round(eval_after, 1) if eval_after is not None else None,
                    "best_move": best_move.uci() if best_move else None,
                    "best_move_san": best_san,
                    "fen_before": fen_before,
                    "fen_after": fen_after,
                    "tactical_reason": reason,
                })
                board.push(move)

            player_moves = [m for m in moves if m["is_player"]]
            summary = _game_summary(player_moves) if player_moves else None
            games_out.append({
                "index": game_index,
                "headers": headers,
                "player_color": ("white" if player_color == chess.WHITE else "black") if player_color is not None else None,
                "player_name": player or (white if player_color == chess.WHITE else black),
                "n_moves_total": len(moves),
                "moves": moves,
                "summary": summary,
            })
            reader = chess.pgn.read_game(stream)
    finally:
        engine.quit()

    all_player_moves = [m for g in games_out for m in g["moves"] if m["is_player"]]
    global_summary = _game_summary(all_player_moves) if all_player_moves else None
    return {
        "meta": {
            "engine": f"Stockfish ({engine_path})",
            "time_limit": time_limit,
            "depth_limit": depth_limit,
            "player": player,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "n_games": len(games_out),
        },
        "games": games_out,
        "global": global_summary,
    }


def _game_summary(player_moves: list) -> dict:
    # ACPL 采用损失封顶（CAP），避免输定局面里“每步都被判大损失”造成的失真
    CAP = 400.0
    raw_losses = [m["loss_cp"] for m in player_moves if m["loss_cp"] is not None]
    losses = [min(l, CAP) for l in raw_losses]
    acpl = sum(losses) / len(losses) if losses else 0.0
    # 精度%：常用近似 accuracy = 100 * (1 - acpl/(acpl+200))
    accuracy = 100.0 * (1 - acpl / (acpl + 200.0)) if acpl is not None else 100.0
    counts = {"Best": 0, "Good": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0}
    for m in player_moves:
        if m["label"] in counts:
            counts[m["label"]] += 1
    tier = _tier_of(acpl)
    return {
        "n_player_moves": len(player_moves),
        "acpl": round(acpl, 1),
        "accuracy": round(accuracy, 1),
        "tier": tier,
        "counts": counts,
        "phase_moves": _phase_breakdown(player_moves),
    }


def _phase_breakdown(player_moves):
    out = {}
    for m in player_moves:
        out.setdefault(m["phase"], {"n": 0, "loss_sum": 0.0})
        out[m["phase"]]["n"] += 1
        if m["loss_cp"] is not None:
            out[m["phase"]]["loss_sum"] += m["loss_cp"]
    for k, v in out.items():
        v["avg_loss"] = round(v["loss_sum"] / v["n"], 1) if v["n"] else 0.0
    return out


def _tier_of(acpl: float) -> str:
    # CheckPause 五档（按 ACPL）
    if acpl <= 10:
        return "Optimal"
    elif acpl <= 30:
        return "Precise"
    elif acpl <= 60:
        return "Competent"
    elif acpl <= 100:
        return "Steady"
    else:
        return "Volatile"


def main():
    ap = argparse.ArgumentParser(description="Stockfish PGN 分析引擎")
    ap.add_argument("pgn", help="PGN 文件路径")
    ap.add_argument("--engine", default="/usr/games/stockfish", help="Stockfish 可执行路径")
    ap.add_argument("--player", default=None, help="要辅导的玩家名（匹配 White/Black）")
    ap.add_argument("--time", type=float, default=0.12, help="每局面分析用时(秒)")
    ap.add_argument("--depth", type=int, default=16, help="分析最大深度")
    ap.add_argument("--out", default="analysis.json", help="输出 JSON 路径")
    args = ap.parse_args()

    if not os.path.exists(args.engine):
        print(f"[错误] 找不到 Stockfish：{args.engine}", file=sys.stderr)
        sys.exit(2)

    result = analyze_pgn(args.pgn, args.engine, args.player, args.time, args.depth)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    g = result["global"]
    if g:
        print(f"[完成] 已分析 {result['meta']['n_games']} 局，玩家 {result['meta']['player'] or '白方'}")
        print(f"  ACPL={g['acpl']}  精度={g['accuracy']}%  评级={g['tier']}")
        print(f"  Best={g['counts']['Best']} Good={g['counts']['Good']} "
              f"Inaccuracy={g['counts']['Inaccuracy']} Mistake={g['counts']['Mistake']} "
              f"Blunder={g['counts']['Blunder']}")
    print(f"[输出] {args.out}")


if __name__ == "__main__":
    main()
