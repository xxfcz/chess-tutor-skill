#!/usr/bin/env python3.11
"""
train.py — 开局练习后端（闯关 + 默写）
=====================================
独立的小服务，与对弈服务（app.py）解耦，便于单独演示与测试。

启动：PORT=8090 python3.11 train.py
接口（全部 POST /，action 分发）：
  list                  列出全部开局
  drill_start  {id}     开始闯关：返回开局信息 + 第一手提示
  drill_move   {id, move} 走一步，引擎判定是否在第一梯队
  quiz_next    {id}     出一题：返回当前局面 + 4 个候选
  quiz_answer  {id, answer} 判题
  ideas        {id}     只返回教学要点
"""
from __future__ import annotations

import os
import sys
import json
import random
import threading

from flask import Flask, request, jsonify
import chess
import chess.engine

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from openings import OPENINGS, get as get_opening, by_family  # noqa: E402

ENGINE_PATH = "/usr/games/stockfish"
PAGE_PATH = os.path.join(HERE, "train_page.txt")
with open(PAGE_PATH, "r", encoding="utf-8") as _f:
    PAGE_HTML = _f.read()

app = Flask(__name__)

# ---------------- 引擎单例 ----------------
_engine = None
_lock = threading.Lock()


def engine():
    global _engine
    if _engine is None:
        _engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
        _engine.configure({"Hash": 128, "Threads": 2, "Skill Level": 20})
    return _engine


def eval_move_quality(board: chess.Board, move: chess.Move, depth=12):
    """
    判断这一步属于第几梯队。
    返回 {"rank": 1..3|None, "loss": cp, "best_san": str}
    rank=1 → 第一梯队（最佳或几乎最佳）
    """
    eng = engine()
    with _lock:
        info = eng.analyse(board, chess.engine.Limit(depth=depth), multipv=3)
    if isinstance(info, dict):
        info = [info]

    best_cp = None
    best_uci = None
    loss = None
    rank = None
    for i, item in enumerate(info):
        sc = item["score"].pov(board.turn).score(mate_score=100000)
        if sc is None:
            sc = 0
        pv = item.get("pv") or []
        if not pv:
            continue
        uci = pv[0].uci()
        if i == 0:
            best_cp = sc
            best_uci = uci
        if uci == move.uci():
            loss = best_cp - sc
            rank = i + 1

    # 不在前三但合法：算一次实际损失
    if rank is None:
        with _lock:
            after = board.copy()
            after.push(move)
            inf2 = eng.analyse(after, chess.engine.Limit(depth=depth))
        sc2 = inf2["score"].pov(board.turn).score(mate_score=100000) or 0
        loss = (best_cp or 0) - (-sc2)

    best_san = None
    if best_uci:
        try:
            best_san = board.san(chess.Move.from_uci(best_uci))
        except Exception:
            pass

    return {"rank": rank, "loss": round(float(loss or 0), 1), "best_san": best_san}


def cand_san(board, uci):
    try:
        return board.san(chess.Move.from_uci(uci))
    except Exception:
        return uci


# ---------------- 列表 ----------------
@app.route("/", methods=["GET"])
def index():
    return PAGE_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/", methods=["POST"])
def api():
    d = request.get_json(force=True, silent=True) or {}
    a = d.get("action")

    if a == "list":
        out = []
        for o in OPENINGS:
            b = chess.Board()
            sans = []
            for u in o["moves"]:
                m = chess.Move.from_uci(u)
                sans.append(b.san(m))
                b.push(m)
            out.append({
                "id": o["id"], "name": o["name"], "en": o["en"],
                "family": o["family"], "side": o["side"], "level": o["level"],
                "line": " ".join(sans),
                "nmoves": len(o["moves"]),
            })
        return jsonify(out)

    if a == "ideas":
        o = get_opening(d.get("id"))
        if not o:
            return jsonify({"error": "未找到该开局"}), 404
        b = chess.Board()
        sans = []
        for u in o["moves"]:
            m = chess.Move.from_uci(u)
            sans.append(b.san(m))
            b.push(m)
        return jsonify({"name": o["name"], "en": o["en"], "line": " ".join(sans),
                        "ideas": o["ideas"], "traps": o["traps"]})

    if a == "drill_start":
        o = get_opening(d.get("id"))
        if not o:
            return jsonify({"error": "未找到该开局"}), 404
        return jsonify({
            "id": o["id"], "name": o["name"], "side": o["side"],
            "target": len(o["moves"]),
            "fen": chess.Board().fen(),
            "student_turn": o["side"] == "white",
        })

    if a == "drill_move":
        return drill_move(d)

    if a == "quiz_next":
        return quiz_next(d)

    return jsonify({"error": "未知动作"}), 400


def drill_move(d):
    """
    闯关：学习者走一步 → 引擎判断质量 → 若在自己体系的谱内且属于第一梯队则通过。
    引擎（对手）自动应招。
    """
    o = get_opening(d.get("id"))
    if not o:
        return jsonify({"error": "未找到该开局"}), 404
    fen = d.get("fen") or chess.Board().fen()
    move_uci = d.get("move")
    plies = int(d.get("ples") or d.get("plies") or 0)

    try:
        board = chess.Board(fen)
    except Exception:
        return jsonify({"error": "局面无效"}), 400
    try:
        move = chess.Move.from_uci(move_uci)
    except Exception:
        return jsonify({"error": "着法格式错误"}), 400
    if move not in board.legal_moves:
        return jsonify({"error": "非法着法"}), 400

    student_white = o["side"] == "white"
    if board.turn != (chess.WHITE if student_white else chess.BLACK):
        return jsonify({"error": "现在不是你的回合"}), 400

    q = eval_move_quality(board, move)
    san = board.san(move)

    # 是否在本人谱内
    expected = None
    expected_idx = plies if student_white else plies - 1
    if 0 <= expected_idx < len(o["moves"]):
        expected = o["moves"][expected_idx]
    in_book = expected is not None and move.uci() == expected
    expected_san = None
    if expected:
        try:
            expected_san = board.san(chess.Move.from_uci(expected))
        except Exception:
            pass

    board.push(move)
    plies += 1

    verdict = "good"
    # 判定优先级：谱外且明显损分 → 差；谱外但损失小 → 提示"非主变"
    # 开局阶段 cp 差普遍偏小（开局优势本就微小），单看 cp 会过于宽松，
    # 因此把"是否在谱内"作为独立维度。
    if q["rank"] == 1 and q["loss"] <= 25:
        verdict = "excellent"
    elif q["loss"] > 120:
        verdict = "bad"
    elif q["loss"] > 50:
        verdict = "inaccuracy"
    elif (not in_book) and q["rank"] is None:
        verdict = "offbook"   # 谱外着法：不算坏棋，但不是本开局主变

    # 引擎应招：仅在未达目标长度、且对手还没走完主线时补手
    # （达到 target 就结束，不再多走一手，否则进度会超出 5/5）
    reply_san = None
    reached = plies >= len(o["moves"])
    if (not board.is_game_over()) and (not reached):
        book_reply = None
        ridx = plies  # 走完这一步后的下标
        if ridx < len(o["moves"]):
            candidate = chess.Move.from_uci(o["moves"][ridx])
            if candidate in board.legal_moves:
                book_reply = candidate
        if book_reply is not None:
            reply_san = board.san(book_reply)
            board.push(book_reply)
        else:
            eng = engine()
            with _lock:
                eng.configure({"Skill Level": 8})
                res = eng.play(board, chess.engine.Limit(depth=10))
            rm = res.move
            reply_san = board.san(rm)
            board.push(rm)
        plies += 1

    return jsonify({
        "fen": board.fen(),
        "plies": plies,
        "san": san,
        "reply": reply_san,
        "in_book": in_book,
        "expected_san": expected_san,
        "rank": q["rank"],
        "loss": q["loss"],
        "best_san": q["best_san"],
        "verdict": verdict,
        "game_over": board.is_game_over(),
        "reached_target": plies >= len(o["moves"]),
    })


def quiz_next(d):
    """出题：在当前主变某一步，问下一步该走什么。"""
    o = get_opening(d.get("id"))
    if not o:
        return jsonify({"error": "未找到该开局"}), 404
    idx = int(d.get("idx") or 0)
    if idx >= len(o["moves"]):
        return jsonify({"done": True})

    board = chess.Board()
    for u in o["moves"][:idx]:
        board.push(chess.Move.from_uci(u))

    answer = o["moves"][idx]
    ans_move = chess.Move.from_uci(answer)
    ans_san = board.san(ans_move)

    # 生成干扰项：同局面的其它合法着
    legal = [m for m in board.legal_moves if m.uci() != answer]
    random.shuffle(legal)
    distract = []
    for m in legal:
        s = board.san(m)
        if s in distract:
            continue
        distract.append(s)
        if len(distract) == 3:
            break

    opts = [ans_san] + distract
    random.shuffle(opts)

    return jsonify({
        "done": False, "idx": idx, "total": len(o["moves"]),
        "fen": board.fen(), "options": opts, "answer": ans_san,
        "name": o["name"],
        "hint": o["ideas"][0] if idx == 0 else None,
    })


if __name__ == "__main__":
    engine()
    port = int(os.environ.get("PORT", 8090))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
