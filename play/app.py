#!/usr/bin/env python3.11
"""
play/app.py — 可视化对弈 + 实时教练（路线 A 的交互形态）
========================================================
- 学员执白、教练（Stockfish 降低强度）执黑
- 学员每走一步：后端用 Stockfish 评估该着 → CheckPause 式分级 → 更新 KPI
  → 仅在 Mistake/Blunder 时给出教练点评（含引擎最佳着、战术原因、针对画像弱点的提醒）
- 教练随后自动应招
- 复用 scripts/analyze.py 的分级 / 阶段 / 战术原因逻辑
- 加载 report/profile.json 的画像弱点，做个性化“走前扫描”提醒

运行：python3.11 app.py   （监听 0.0.0.0:8080）
"""
from __future__ import annotations

import os
import sys
import json
import time
import threading
from flask import Flask, request, jsonify

import chess
import chess.engine

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE_PATH = "/usr/games/stockfish"
PROFILE_PATH = os.path.join(HERE, "..", "report", "profile.json")
INDEX_HTML_PATH = os.path.join(HERE, "board_page.txt")
with open(INDEX_HTML_PATH, "r", encoding="utf-8") as _f:
    INDEX_HTML = _f.read()
NARRATE_HTML_PATH = os.path.join(HERE, "narrate_page.txt")
with open(NARRATE_HTML_PATH, "r", encoding="utf-8") as _f:
    NARRATE_HTML = _f.read()
TRAIN_HTML_PATH = os.path.join(HERE, "train_page.txt")
with open(TRAIN_HTML_PATH, "r", encoding="utf-8") as _f:
    TRAIN_HTML = _f.read()

app = Flask(__name__)

# ---------------- 分级 / 阶段 / 战术原因（与 analyze.py 一致）----------------
LABEL_THRESHOLDS = [("Blunder", 300), ("Mistake", 100), ("Inaccuracy", 40), ("Good", 0)]
BEST_LOSS_MAX = 10

PHASE_CN = {"opening": "开局", "middlegame": "中局", "endgame": "残局"}


def classify(loss_cp: float, is_best: bool) -> str:
    if is_best and loss_cp <= BEST_LOSS_MAX:
        return "Best"
    for label, thr in LABEL_THRESHOLDS:
        if loss_cp >= thr:
            return label
    return "Good"


def phase_of(board: chess.Board, ply: int) -> str:
    if ply <= 16:
        return "opening"
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    minors_rooks = sum(1 for p in board.piece_map().values()
                       if p.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK))
    if queens == 0 and minors_rooks <= 6:
        return "endgame"
    if ply >= 60 and minors_rooks <= 6:
        return "endgame"
    return "middlegame"


def is_hanging(board: chess.Board, square: chess.Square) -> bool:
    piece = board.piece_at(square)
    if piece is None:
        return False
    attackers = board.attackers(not piece.color, square)
    if not attackers:
        return False
    val = lambda sq: 1 if board.piece_at(sq).piece_type == chess.PAWN else {
        chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}.get(
        board.piece_at(sq).piece_type, 3)
    atk_min = min(val(sq) for sq in attackers)
    def_val = 99
    defenders = board.attackers(piece.color, square)
    if defenders:
        def_val = min(val(sq) for sq in defenders)
    return atk_min <= def_val


def tactical_reason(board_before, move, board_after, color, best_move, loss_cp):
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


def cp_of(score: chess.engine.Score, turn: chess.Color) -> float:
    s = score.pov(turn)
    val = s.score(mate_score=100000)
    return float(val) if val is not None else 0.0


# ---------------- 引擎单例 ----------------
_engine = None
_engine_lock = threading.Lock()


def get_engine():
    global _engine
    if _engine is None:
        _engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
        _engine.configure({"Hash": 128, "Threads": 2})
    return _engine


# ---------------- 画像（个性化提醒）----------------
PROFILE = {}


def load_profile():
    global PROFILE
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as fh:
            PROFILE = json.load(fh)
    except Exception:
        PROFILE = {}


def profile_weakness_text() -> str:
    weak = PROFILE.get("weakest", [])
    if not weak:
        return "（暂无画像数据）"
    return "、".join(f"{w['name']}({w['score']})" for w in weak)


def tailored_reminder(phase: str) -> str:
    """针对该步所在阶段，从画像弱点里挑一句提醒。"""
    mapping = {
        "endgame": "残局技术(51)",
        "middlegame": "中局计划(54)",
        "opening": "开局稳定性(85，你的强项，保持)",
    }
    name = mapping.get(phase)
    if not name:
        return ""
    if phase == "opening":
        return f"你在{PHASE_CN[phase]}很稳，正常发挥即可。"
    return f"注意：本步处于{PHASE_CN[phase]}，你的画像弱点是{name}——别在转换/交换后松手。"


# ---------------- 对局状态（演示：单局内存态）----------------
GAME = {"board": None, "history": [], "kpi": None, "last_coaching": None,
        "eval_white_cp": 0.0, "opening": None}

# 开局库（与 scripts/openings.py 共用一份数据）
_OPENINGS_PATH = os.path.join(HERE, "..", "scripts")
try:
    if _OPENINGS_PATH not in sys.path:
        sys.path.insert(0, _OPENINGS_PATH)
    from openings import OPENINGS, get as get_opening
except Exception:
    OPENINGS = []
    def get_opening(_id):
        return None

# 练习核心模块（train_core.py 在 scripts/ 下）
if _OPENINGS_PATH not in sys.path:
    sys.path.insert(0, _OPENINGS_PATH)


def new_game(clear_feed: bool = False):
    board = chess.Board()
    GAME["board"] = board
    GAME["history"] = []
    GAME["kpi"] = {"Best": 0, "Good": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0, "moves": 0}
    GAME["last_coaching"] = None
    GAME["eval_white_cp"] = 0.0
    if clear_feed:
        # 用户显式开新局：清空旁白 feed 并退出开局模式
        GAME["opening"] = None
        try:
            open(os.path.join(HERE, "live_feed.jsonl"), "w", encoding="utf-8").close()
        except Exception:
            pass
    return board


def eval_white(board: chess.Board, time=0.25, depth=14) -> tuple:
    """返回 (score_white_cp, best_move_uci)。"""
    with _engine_lock:
        eng = get_engine()
        eng.configure({"Skill Level": 20})
        info = eng.analyse(board, chess.engine.Limit(time=time, depth=depth))
        score = cp_of(info["score"], chess.WHITE)
        pv = info.get("pv")
        best = pv[0].uci() if pv else None
    return score, best


def coach_reply(board: chess.Board, skill=4, time=0.3, depth=10) -> str:
    with _engine_lock:
        eng = get_engine()
        eng.configure({"Skill Level": skill})
        res = eng.play(board, chess.engine.Limit(time=time, depth=depth))
    return res.move.uci()


def scan_reminder() -> str:
    return ("🔍 走前扫描（你的画像铁律）：① 有没有吃子？② 有没有将军？③ 走完后哪个子悬空了？"
            f" 本周重点弱点：{profile_weakness_text()}。")


def build_state(extra=None):
    board = GAME["board"]
    state = {
        "fen": board.fen(),
        "turn": "white" if board.turn == chess.WHITE else "black",
        "history": GAME["history"],
        "kpi": GAME["kpi"],
        "game_over": board.is_game_over(),
        "result": board.result() if board.is_game_over() else None,
        "reminder": scan_reminder(),
    }
    # 开局模式：把当前绑定的开局信息带上（前端展示）
    op = GAME.get("opening")
    if op:
        state["opening"] = {"id": op["id"], "name": op["name"], "target": len(op["moves"])}
    if extra:
        state.update(extra)
    return state


# ---------------- 路由（所有动态请求收敛到 POST /，避开网关对 /api/* 的 SPA 回退）----------------
@app.route("/", methods=["GET"])
def index():
    view = request.args.get("view", "board")
    if view == "narrate":
        return NARRATE_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}
    if view == "train":
        return TRAIN_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}
    return INDEX_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


# ---------------- 共用棋盘组件（对弈页 / 练习页复用）----------------
STATIC_FILES = {
    "board.css": "text/css; charset=utf-8",
    "board.js": "application/javascript; charset=utf-8",
}


@app.route("/<fname>")
def board_component(fname):
    """按需读取共用棋盘组件文件；每次请求都读盘，改完即生效、无需重启。"""
    if fname not in STATIC_FILES:
        from flask import abort
        abort(404)
    path = os.path.join(HERE, fname)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            body = fh.read()
    except OSError:
        from flask import abort
        abort(404)
    return body, 200, {"Content-Type": STATIC_FILES[fname],
                       "Cache-Control": "no-cache"}


def read_feed():
    feed_path = os.path.join(HERE, "live_feed.jsonl")
    recs = []
    try:
        with open(feed_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return recs


@app.route("/", methods=["POST"])
def api_dispatch():
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action")
    if action == "new":
        # 仅当显式要求重置时才清空 feed（点"新局"按钮），页面刷新走 watch 恢复
        new_game(clear_feed=bool(data.get("reset_feed")))
        return jsonify(build_state())
    if action == "watch":
        # 只读观战：返回当前棋局状态，不重置 GAME（供 AI 教练拉取解说）
        if GAME["board"] is None:
            return jsonify({"error": "尚未开局，请先在网页开新局", "state": None})
        return jsonify(build_state({"last_coaching": GAME.get("last_coaching"),
                                    "eval_white_cp": GAME.get("eval_white_cp", 0.0)}))
    if action == "feed":
        # 返回实时旁白数据源（live_feed.jsonl），供只读页面轮询渲染
        return jsonify(read_feed())
    if action == "note":
        # AI 教练点评写入通道：外部（LLM 会话）把点评追加进 feed，旁白页立即可见
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify({"error": "text 不能为空"}), 400
        rec = {
            "event": "coach_note",
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "text": text,
            "source": data.get("source") or "ai-coach",
        }
        mv = data.get("moves")
        if mv is not None:
            rec["moves"] = mv
        try:
            with open(os.path.join(HERE, "live_feed.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            return jsonify({"error": f"写入失败：{e}"}), 500
        return jsonify({"ok": True, "record": rec})
    if action == "legal":
        board = GAME["board"]
        if board is None:
            return jsonify({"targets": []})
        # 预览态：前端可传 fen，按该局面查询合法着法
        peek_fen = data.get("fen")
        if peek_fen:
            try:
                board = chess.Board(peek_fen)
            except Exception:
                pass
        square = data.get("square", "")
        try:
            sq = chess.parse_square(square)
        except Exception:
            return jsonify({"targets": []})
        targets = []
        for mv in board.legal_moves:
            if mv.from_square == sq:
                t = chess.square_name(mv.to_square)
                if mv.promotion:
                    t += chess.piece_symbol(mv.promotion)
                targets.append(t)
        return jsonify({"targets": targets})
    if action == "move":
        return handle_move(data.get("move") or "")
    if action == "open":
        # 进入开局模式：开新局并绑定开局库，对手按标准变化应招
        return handle_open(data.get("id"))
    # ---------- 开局练习（train）----------
    if action in ("list", "ideas", "drill_start", "drill_move", "quiz_next",
                  "train_list", "train_ideas", "demo_step", "train_demo"):
        return handle_train(action, data)
    if action == "undo":
        return handle_undo(data.get("to_ply"))
    if action == "peek":
        # 纯浏览：只读返回第 to_ply 步之后的局面，不改动棋局状态
        return handle_peek(data.get("to_ply"))
    return jsonify({"error": "未知动作"}), 400


def handle_peek(to_ply):
    """
    只读预览：返回第 to_ply 着之后的局面，不修改 GAME。
    用于"点历史某步临时看一眼"，后续着法仍保留在棋盘记录中。
    """
    board = GAME["board"]
    if board is None:
        return jsonify({"error": "对局未开始"}), 400
    try:
        target = int(to_ply)
    except (TypeError, ValueError):
        return jsonify({"error": "to_ply 必须是整数"}), 400
    hist = GAME["history"]
    if target < 0:
        target = 0
    if target > len(hist):
        target = len(hist)

    # 用 FEN 自带的历史着法回放（board.fen() 含 move_stack 信息需重新构建）
    replay = chess.Board()
    for rec in hist[:target]:
        try:
            replay.push(chess.Move.from_uci(rec["uci"]))
        except Exception:
            break

    return jsonify({
        "fen": replay.fen(),
        "turn": "white" if replay.turn == chess.WHITE else "black",
        "ply": target,
        "san": hist[target - 1]["san"] if target > 0 else None,
        "total": len(hist),
    })


def handle_train(action, data):
    """开局练习：闯关 / 默写 / 列表 / 要点。复用 scripts/train_core.py。"""
    try:
        import train_core as tc
    except Exception as e:
        return jsonify({"error": f"练习模块加载失败：{e}"}), 500

    if action in ("train_list", "list"):
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
                "line": " ".join(sans), "nmoves": len(o["moves"]),
            })
        return jsonify(out)

    if action in ("train_ideas", "ideas"):
        o = get_opening(data.get("id") or "")
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

    if action == "drill_start":
        o = get_opening(data.get("id") or "")
        if not o:
            return jsonify({"error": "未找到该开局"}), 404
        return jsonify({
            "id": o["id"], "name": o["name"], "side": o["side"],
            "target": len(o["moves"]),
            "fen": chess.Board().fen(),
            "student_turn": o["side"] == "white",
        })

    if action == "drill_move":
        return jsonify(tc.drill_move(data))

    if action == "quiz_next":
        return jsonify(tc.quiz_next(data))

    # 演示模式：小白先逐步看怎么走，每步由 Stockfish 生成讲解
    if action in ("demo_step", "train_demo"):
        r = tc.demo_step(data)
        code = 404 if (isinstance(r, dict) and r.get("error")) else 200
        return jsonify(r), code

    return jsonify({"error": "未知练习动作"}), 400


def handle_open(opening_id):
    """进入开局模式：开新局，绑定开局库，对手按标准变化应招。"""
    o = get_opening(opening_id or "")
    if not o:
        return jsonify({"error": "未找到该开局"}), 404
    if o.get("side") != "white":
        return jsonify({"error": "对弈页开局模式目前只支持执白的开局"}), 400

    new_game(clear_feed=False)
    GAME["opening"] = o

    # 预览整条主变（供前端展示）
    b = chess.Board()
    sans = []
    for u in o["moves"]:
        m = chess.Move.from_uci(u)
        sans.append(b.san(m))
        b.push(m)

    return jsonify(build_state({
        "last_coaching": None,
        "eval_white_cp": 0.0,
        "opening": {
            "id": o["id"], "name": o["name"], "en": o["en"],
            "line": " ".join(sans),
            "ideas": o["ideas"], "traps": o["traps"],
            "target": len(o["moves"]),
        },
    }))


def handle_undo(to_ply):
    """
    悔棋到指定步数（to_ply 表示悔棋后保留的着法数，0 = 回到开局）。
    - 回滚棋盘与着法记录
    - 依据每步记录的 label 精确回滚 KPI
    - 回滚后若又轮到白方，回合自然正确（白方走完教练才应）
    """
    board = GAME["board"]
    if board is None:
        return jsonify({"error": "对局未开始"}), 400
    try:
        target = int(to_ply)
    except (TypeError, ValueError):
        return jsonify({"error": "to_ply 必须是整数"}), 400

    hist = GAME["history"]
    if target < 0:
        target = 0
    if target > len(hist):
        return jsonify({"error": "目标步数超出当前着法数"}), 400
    if target == len(hist):
        return jsonify(build_state({"last_coaching": GAME.get("last_coaching"),
                                    "eval_white_cp": GAME.get("eval_white_cp", 0.0)}))

    # 1) 从当前局面回退到 target
    for _ in range(len(hist) - target):
        if board.move_stack:
            board.pop()

    # 2) 回滚 KPI：撤销被砍掉的着法里的白方分级
    for rec in hist[target:]:
        lb = rec.get("label")
        if lb and rec.get("color") == "white":
            if GAME["kpi"].get(lb, 0) > 0:
                GAME["kpi"][lb] -= 1
                GAME["kpi"]["moves"] = max(0, GAME["kpi"]["moves"] - 1)

    # 3) 截断着法记录
    GAME["history"] = hist[:target]
    GAME["last_coaching"] = None

    # 3.5) 若悔到"你刚走完、教练未应"的中间态，补上教练应手，
    #      保证交还给用户时永远轮到白方，不会卡住。
    if (not board.is_game_over()) and board.turn == chess.BLACK:
        c_uci = None
        op = GAME.get("opening")
        if op:
            idx = len(GAME["history"])
            seq = op.get("moves") or []
            if idx < len(seq):
                cand = chess.Move.from_uci(seq[idx])
                if cand in board.legal_moves:
                    c_uci = cand.uci()
        if c_uci is None:
            c_uci = coach_reply(board)
        c_move = chess.Move.from_uci(c_uci)
        c_san = board.san(c_move)
        board.push(c_move)
        GAME["history"].append({
            "uci": c_uci, "san": c_san, "color": "black",
            "ply": len(GAME["history"]) + 1,
        })

    # 4) 重算评估（供评估条与解说使用）
    if not board.is_game_over():
        try:
            GAME["eval_white_cp"] = round(eval_white(board)[0], 1)
        except Exception:
            GAME["eval_white_cp"] = 0.0

    return jsonify(build_state({"last_coaching": None,
                                "eval_white_cp": GAME.get("eval_white_cp", 0.0),
                                "undone_to": target}))


def handle_move(move_uci: str):
    board = GAME["board"]

    if board is None or board.is_game_over():
        return jsonify({"error": "对局未开始或已结束，请先开新局"}), 400
    if board.turn != chess.WHITE:
        return jsonify({"error": "现在不是你的回合"}), 400

    try:
        move = chess.Move.from_uci(move_uci)
    except Exception:
        return jsonify({"error": "着法格式错误"}), 400
    if move not in board.legal_moves:
        return jsonify({"error": "非法着法"}), 400

    ply = len(GAME["history"]) + 1
    phase = phase_of(board, ply)

    # —— 学员着法评估（在推子前记录前置局面与引擎首选）——
    board_before = board.copy()
    score_before, best_uci = eval_white(board)
    best_move = chess.Move.from_uci(best_uci) if best_uci else None
    best_san = board.san(best_move) if best_move else None
    san = board.san(move)
    board.push(move)
    GAME["history"].append({
        "uci": move.uci(), "san": san, "color": "white", "ply": ply,
    })

    if board.is_game_over():
        loss_cp = 0.0
        label = "Best"
        reason = None
    else:
        score_after = eval_white(board)[0]
        loss_cp = score_before - score_after
        is_best = (best_move is not None and move == best_move)
        label = classify(loss_cp, is_best)
        reason = tactical_reason(board_before, move, board, chess.WHITE,
                                 best_move, loss_cp)

    # 更新 KPI
    GAME["kpi"][label] = GAME["kpi"].get(label, 0) + 1
    GAME["kpi"]["moves"] += 1
    # 回填本步分级，供悔棋时精确回滚
    GAME["history"][-1]["label"] = label
    GAME["history"][-1]["loss_cp"] = round(loss_cp, 1)

    coaching = None
    if label in ("Mistake", "Blunder"):
        coaching = {
            "label": label,
            "loss_cp": round(loss_cp, 1),
            "phase": PHASE_CN.get(phase, phase),
            "best_move": best_san,
            "reason": reason,
            "tailored": tailored_reminder(phase),
            "san": san,
        }

    # —— 教练应招 ——
    coach_san = None
    if not board.is_game_over() and board.turn == chess.BLACK:
        c_uci = None
        # 开局模式：优先走开局库的标准应对，保证能体会该开局的真实结构
        op = GAME.get("opening")
        if op:
            seq = op.get("moves") or []
            idx = len(GAME["history"])
            # 仅当主线里确实还有下一手时才强制谱着；走完主线就交给引擎正常下
            if idx < len(seq):
                cand = chess.Move.from_uci(seq[idx])
                if cand in board.legal_moves:
                    c_uci = cand.uci()
        if c_uci is None:
            c_uci = coach_reply(board)
        c_move = chess.Move.from_uci(c_uci)
        coach_san = board.san(c_move)
        board.push(c_move)
        GAME["history"].append({
            "uci": c_uci, "san": coach_san, "color": "black",
            "ply": len(GAME["history"]) + 1,
        })

    # 当前评估（白方视角）用于评估条
    cur_eval = eval_white(board)[0] if not board.is_game_over() else (
        100000.0 if board.result() == "1-0" else (-100000.0 if board.result() == "0-1" else 0.0))

    GAME["last_coaching"] = coaching
    GAME["eval_white_cp"] = round(cur_eval, 1)
    extra = {
        "coaching": coaching,
        "last_student_move": san,
        "last_student_move_uci": move.uci(),
        "coach_move": coach_san,
        "eval_white_cp": round(cur_eval, 1),
    }
    return jsonify(build_state(extra))


if __name__ == "__main__":
    load_profile()
    # 预热引擎
    try:
        get_engine()
    except Exception as e:
        print(f"[警告] 引擎启动失败：{e}")
    # 启动常驻观战桥（后台守护线程，随本进程常驻；跨休眠由 autostart 保证复活）
    try:
        import threading
        import bridge
        bt = threading.Thread(target=bridge.main, daemon=True)
        bt.start()
        print("[信息] 观战桥线程已启动")
    except Exception as e:
        print(f"[警告] 观战桥启动失败：{e}")
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
