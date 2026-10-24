#!/usr/bin/env python3.11
"""
bridge.py — 常驻观战桥（路线 A 的“AI 教练近实时解说”支撑组件）
================================================================
- 每 INTERVAL 秒轮询后端 watch 接口（http://127.0.0.1:8080/）
- 把“新着法 / 教练点评 / KPI / 新局 / 终局”增量追加写入 live_feed.jsonl
- AI 教练（LLM 会话）读取 live_feed.jsonl 即可近实时跟随并解说
- 不改动前端协议；后端仍是纯 HTTP，桥只做“拉取 + 落盘”

运行：python3 bridge.py   （建议用后台/常驻方式运行）
"""
import time
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FEED = os.path.join(HERE, "live_feed.jsonl")
BACKEND = "http://127.0.0.1:8080/"
INTERVAL = 1.5


def phase_cn(phase):
    return {"opening": "开局", "middlegame": "中局", "endgame": "残局"}.get(phase, phase or "")


def piece_cn(san):
    """从 SAN 提取子力中文名。"""
    if not san:
        return "子"
    c = san[0]
    return {"N": "马", "B": "象", "R": "车", "Q": "后", "K": "王", "O": "易位"}.get(c, "兵")


def eval_phrase(cp):
    """把白方视角评估转成人话。"""
    if cp is None:
        return None
    a = abs(cp)
    if a >= 800:
        side = "白方" if cp > 0 else "黑方"
        return f"{side}已取得决定性优势"
    if a >= 300:
        side = "白方" if cp > 0 else "黑方"
        return f"{side}明显占优"
    if a >= 120:
        side = "白方" if cp > 0 else "黑方"
        return f"{side}略占上风"
    if a >= 50:
        return "白方稍好" if cp > 0 else "黑方稍好"
    return "双方大致均势"


def build_narration(move_rec, kpi, cp):
    """
    规则模板解说：结合阶段、着法、局势与 KPI 生成一句教练口吻的旁白。
    不调用 LLM，纯规则拼装，保证稳定、零成本。
    """
    san = move_rec.get("san") or ""
    color = "你" if move_rec.get("color") == "white" else "教练"
    p = piece_cn(san)
    is_capture = "x" in san
    is_check = "+" in san
    is_mat = "#" in san
    is_castle = san.startswith("O-O")

    parts = []
    if move_rec.get("color") == "white":
        if is_mat:
            parts.append(f"你走 {san} 直接成杀！")
        elif is_capture and is_check:
            parts.append(f"你 {san} 吃子带将，一石二鸟。")
        elif is_capture:
            parts.append(f"你走 {san} 主动交换，简化局面。")
        elif is_check:
            parts.append(f"你 {san} 将军，抢占先手。")
        elif is_castle:
            parts.append(f"你 {san} 及时易位，王安全了。")
        else:
            parts.append(f"你出{p}：{san}。")
    else:
        if is_capture:
            parts.append(f"教练 {san} 回吃，局面转入交换。")
        elif is_check:
            parts.append(f"教练 {san} 反将，注意应对。")
        else:
            parts.append(f"教练应以 {san}。")

    ep = eval_phrase(cp)
    if ep:
        parts.append(f"当前{ep}。")

    if kpi:
        moves = kpi.get("moves") or 0
        bad = (kpi.get("Mistake") or 0) + (kpi.get("Blunder") or 0)
        if moves >= 5:
            if bad == 0:
                parts.append(f"已下 {moves} 步零失误，保持这个扫描习惯。")
            else:
                parts.append(f"已下 {moves} 步，其中失误/大漏 {bad} 次，落子前多问一遍吃子与将军。")
    return "".join(parts)


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def append(rec):
    try:
        with open(FEED, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    except Exception as e:  # pragma: no cover
        print(f"[{now()}] write err {e}", flush=True)


def watch():
    try:
        req = urllib.request.Request(
            BACKEND,
            data=json.dumps({"action": "watch"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def main():
    last_len = -1
    last_over = False
    append({"event": "bridge_start", "ts": now()})
    while True:
        st = watch()
        # 未开局（后端刚重启/还没 new）
        if "error" in st and st.get("state") is None:
            if last_len != -1:
                append({"event": "no_game", "ts": now()})
                last_len = -1
                last_over = False
            time.sleep(INTERVAL)
            continue

        hist = st.get("history", []) or []
        fen = st.get("fen")
        n = len(hist)

        if last_len == -1:
            # 首次：只同步当前局面快照，不重复记录历史
            append({"event": "sync", "ts": now(), "fen": fen,
                    "turn": st.get("turn"), "moves": n})
            last_len = n
            last_over = bool(st.get("game_over"))
            time.sleep(INTERVAL)
            continue

        if n < last_len:
            # 检测到重置 → 新局
            append({"event": "new_game", "ts": now(), "fen": fen})
            last_len = n
            last_over = bool(st.get("game_over"))
            time.sleep(INTERVAL)
            continue

        if n > last_len:
            for h in hist[last_len:]:
                append({
                    "event": "move", "ts": now(),
                    "ply": h.get("ply"), "color": h.get("color"),
                    "san": h.get("san"), "uci": h.get("uci"),
                })
            lc = st.get("last_coaching")
            if lc:
                append({"event": "coaching", "ts": now(),
                        "label": lc.get("label"), "loss_cp": lc.get("loss_cp"),
                        "best": lc.get("best_move"), "reason": lc.get("reason"),
                        "phase": lc.get("phase"), "tailored": lc.get("tailored")})
            kpi = st.get("kpi")
            if kpi:
                append({"event": "kpi", "ts": now(), "kpi": kpi})
            # 规则模板解说（B 方案）：对最新一步生成一句教练旁白
            latest = hist[-1]
            narr = build_narration(latest, kpi, st.get("eval_white_cp"))
            if narr:
                append({"event": "narration", "ts": now(),
                        "text": narr, "ply": latest.get("ply")})
            last_len = n

        if st.get("game_over") and not last_over:
            append({"event": "game_over", "ts": now(), "result": st.get("result")})
            last_over = True

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
