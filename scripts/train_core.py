#!/usr/bin/env python3.11
"""train_core.py — 开局练习核心逻辑（供 train.py 独立服务与 play/app.py 共用）"""
from __future__ import annotations

import os
import sys
import random
import threading

import chess
import chess.engine

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from openings import OPENINGS, get as get_opening  # noqa: E402

ENGINE_PATH = "/usr/games/stockfish"
_engine = None
_lock = threading.Lock()


def engine():
    global _engine
    if _engine is None:
        _engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
        _engine.configure({"Hash": 128, "Threads": 2, "Skill Level": 20})
    return _engine


def close_engine():
    """显式关闭引擎进程（脚本退出/热重载前调用，避免留下僵尸 Stockfish）。"""
    global _engine
    if _engine is not None:
        try:
            _engine.quit()
        except Exception:
            pass
        _engine = None


import atexit  # noqa: E402
atexit.register(close_engine)


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

def drill_move(d):
    """
    闯关：学习者走一步 → 引擎判断质量 → 若在自己体系的谱内且属于第一梯队则通过。
    引擎（对手）自动应招。
    """
    o = get_opening(d.get("id"))
    if not o:
        return {"error": "未找到该开局"}
    fen = d.get("fen") or chess.Board().fen()
    move_uci = d.get("move")
    plies = int(d.get("ples") or d.get("plies") or 0)

    try:
        board = chess.Board(fen)
    except Exception:
        return {"error": "局面无效"}
    try:
        move = chess.Move.from_uci(move_uci)
    except Exception:
        return {"error": "着法格式错误"}
    if move not in board.legal_moves:
        return {"error": "非法着法"}

    student_white = o["side"] == "white"
    if board.turn != (chess.WHITE if student_white else chess.BLACK):
        return {"error": "现在不是你的回合"}

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

    return {
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
    }



def quiz_next(d):
    """出题：在当前主变某一步，问下一步该走什么。"""
    o = get_opening(d.get("id"))
    if not o:
        return {"error": "未找到该开局"}
    idx = int(d.get("idx") or 0)
    if idx < 0:
        idx = 0
    if idx >= len(o["moves"]):
        # 题目出完：返回结构完整的终止响应，避免调用方访问 options/hint 时崩
        return {"done": True, "idx": idx, "total": len(o["moves"]),
                "name": o["name"], "fen": None, "options": [],
                "answer": None, "hint": None}

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

    return {
        "done": False, "idx": idx, "total": len(o["moves"]),
        "fen": board.fen(), "options": opts, "answer": ans_san,
        "name": o["name"],
        "hint": o["ideas"][0] if idx == 0 else None,
    }


# ---------------- 演示模式（小白先看怎么走） ----------------

# 棋子中文名
_PIECE_CN = {
    chess.PAWN: "兵", chess.KNIGHT: "马", chess.BISHOP: "象",
    chess.ROOK: "车", chess.QUEEN: "后", chess.KING: "王",
}


def _cp_phrase(cp: float) -> str:
    """把白方视角的厘兵分转成人话。"""
    if cp is None:
        return "局面接近均势"
    if abs(cp) < 30:
        return "局面基本均势"
    side = "白方" if cp > 0 else "黑方"
    a = abs(cp)
    if a < 80:
        return f"{side}略好"
    if a < 200:
        return f"{side}明显占优"
    if a < 500:
        return f"{side}大幅领先"
    return f"{side}已胜势"


def _move_feature(board: chess.Board, move: chess.Move) -> list[str]:
    """
    从走法本身提取可观察事实（不含引擎判断），用小白能懂的话描述。
    """
    feats: list[str] = []
    piece = board.piece_at(move.from_square)
    if piece is None:
        return feats
    name = _PIECE_CN.get(piece.piece_type, "子")
    frm = chess.square_name(move.from_square)
    to = chess.square_name(move.to_square)

    # 中心控制
    CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
    BIG_CENTER = CENTER | {chess.C3, chess.D3, chess.E3, chess.F3,
                           chess.C6, chess.D6, chess.E6, chess.F6}
    if move.to_square in CENTER:
        feats.append(f"{name}直接落到中心格 {to}，正面争夺中心")
    elif move.to_square in BIG_CENTER:
        feats.append(f"{name}进入中心区域 {to}，参与中心的争夺")

    # 兵走两格
    if piece.piece_type == chess.PAWN and abs(move.to_square - move.from_square) in (16, -16):
        feats.append("兵一次推进两格，快速占领空间")

    # 出子（从初始位置出发的轻子）
    START = {chess.B1, chess.G1, chess.C1, chess.F1,
             chess.B8, chess.G8, chess.C8, chess.F8}
    if move.from_square in START and piece.piece_type in (
            chess.KNIGHT, chess.BISHOP):
        feats.append(f"这是出子——把{name}从初始位置调出来参战")

    # 攻击指向
    after = board.copy()
    after.push(move)
    targets = []
    for sq in after.attacks(move.to_square):
        p = after.piece_at(sq)
        if p is not None and p.color != piece.color:
            targets.append((_PIECE_CN.get(p.piece_type, "子"), sq))
    if targets:
        # 只报最有价值的一个
        ORDER = {chess.QUEEN: 5, chess.ROOK: 4, chess.BISHOP: 3,
                 chess.KNIGHT: 3, chess.PAWN: 1, chess.KING: 9}
        targets.sort(key=lambda t: -ORDER.get(
            after.piece_at(t[1]).piece_type, 0))
        pn, sq = targets[0]
        feats.append(f"落点斜指 {chess.square_name(sq)} 的{pn}，形成牵制/威胁")

    # 将军
    if after.is_check():
        feats.append("这一步直接将军，逼对方立即应对")

    # 王车易位之类
    if piece.piece_type == chess.KING and abs(move.to_square - move.from_square) == 2:
        feats.append("这是易位：王躲进角落、车被调出来，一举两得")

    return feats


def demo_step(d):
    """
    演示模式：返回第 idx 半回合（0 开始）的详解，不自增状态——前端维护进度。
    请求：{"id":..., "idx":0}
    返回逐步解释 + 引擎事实 + 走完后的局面。
    """
    o = get_opening(d.get("id"))
    if not o:
        return {"error": "未找到该开局"}

    from step_notes import NOTES

    moves = o["moves"]
    idx = int(d.get("idx") or 0)
    if idx < 0:
        idx = 0
    if idx >= len(moves):
        return {"done": True, "idx": idx, "total": len(moves),
                "name": o["name"], "san": None, "note": None,
                "fen": None, "last": True}

    # 重建到当前这一步之前的局面
    board = chess.Board()
    prev_sans = []
    for u in moves[:idx]:
        m = chess.Move.from_uci(u)
        prev_sans.append(board.san(m))
        board.push(m)

    move = chess.Move.from_uci(moves[idx])
    san = board.san(move)
    side = "白方" if board.turn == chess.WHITE else "黑方"

    # 引擎分析：现状评分 + 前三候选
    # 关键：全程用"走子方视角(pov)"计算，避免黑白回合符号反转导致 loss 为负。
    eng = engine()
    with _lock:
        info = eng.analyse(board, chess.engine.Limit(depth=14), multipv=3)
    if isinstance(info, dict):
        info = [info]

    sign = 1 if board.turn == chess.WHITE else -1   # 走子方视角 → 白方视角
    top: list[dict] = []
    best_cp = None      # 走子方视角下，首选着法的评分
    chosen_cp = None    # 走子方视角下，所走这步的评分
    for i, item in enumerate(info):
        pv = item.get("pv") or []
        if not pv:
            continue
        sc = item["score"].pov(board.turn).score(mate_score=100000)
        if sc is None:
            sc = 0
        uci = pv[0].uci()
        try:
            s_san = board.san(pv[0])
        except Exception:
            s_san = uci
        top.append({"san": s_san, "cp_white": sc * sign,
                    "is_chosen": uci == move.uci()})
        if i == 0:
            best_cp = sc
        if uci == move.uci():
            chosen_cp = sc

    # 没进前三：单独算一次"走后对方视角"的评分，再翻回走子方视角
    if chosen_cp is None:
        after_tmp = board.copy()
        after_tmp.push(move)
        with _lock:
            inf2 = eng.analyse(after_tmp, chess.engine.Limit(depth=14))
        if isinstance(inf2, list):
            inf2 = inf2[0]
        sc2 = inf2["score"].pov(after_tmp.turn).score(mate_score=100000) or 0
        chosen_cp = -sc2   # 对手视角取负 = 我方视角

    loss = round(float((best_cp or 0) - (chosen_cp or 0)), 1)
    if loss < 0:
        loss = 0.0
    # 判"是否最佳"用评分差而非名次：并列第一梯队时 loss≈0 也算最佳
    is_best = loss <= 3
    cp_white = chosen_cp * sign     # 展示用：白方视角
    best_san = top[0]["san"] if top else "—"

    # 所走这步若不在引擎前三，单独补进候选列表（标 is_chosen），便于对比
    if not any(t["is_chosen"] for t in top):
        top.append({"san": san, "cp_white": cp_white, "is_chosen": True})

    # 组合讲解：人写的一句 + 走法特征 + 引擎事实
    notes_for_op = NOTES.get(o["id"]) or []
    note = notes_for_op[idx] if idx < len(notes_for_op) else None
    if not note:
        note = f"{side}走 {san}。"

    # 走法特征要在"走之前"的局面上算
    feats = _move_feature(board, move)

    board.push(move)

    # 引擎说法（评分统一用白方视角描述，符合棋友习惯）
    if is_best:
        engine_say = f"引擎首选就是这一步，{_cp_phrase(cp_white)}。"
    elif loss <= 25:
        engine_say = (f"引擎首选是 {best_san}，这一步与它几乎等价"
                      f"（差 {loss:.0f} 分），{_cp_phrase(cp_white)}。")
    elif loss <= 80:
        engine_say = (f"引擎首选是 {best_san}，这一步略弱一点"
                      f"（差 {loss:.0f} 分），但在开局里完全可下，{_cp_phrase(cp_white)}。")
    else:
        engine_say = (f"引擎首选是 {best_san}，这一步差 {loss:.0f} 分，"
                      f"不是引擎眼中的最佳；不过作为开局主线，"
                      f"它有自己的战略道理（见下面的讲解）。")

    return {
        "done": False,
        "id": o["id"], "name": o["name"],
        "idx": idx, "total": len(moves),
        "ply": idx + 1,
        "move_no": idx // 2 + 1,
        "side": side,
        "san": san,
        "uci": move.uci(),
        "note": note,
        "features": feats,
        "engine_say": engine_say,
        "is_best": is_best,
        "loss": loss,
        "cp": cp_white,
        "cp_phrase": _cp_phrase(cp_white),
        "top": top,
        "fen": board.fen(),
        "last_move": [chess.square_name(move.from_square),
                      chess.square_name(move.to_square)],
        "prev_sans": prev_sans,
        "last": idx == len(moves) - 1,
        "ideas": o.get("ideas", []),
        "traps": o.get("traps", []),
    }


