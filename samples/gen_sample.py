#!/usr/bin/env python3.11
"""
gen_sample.py — 生成合法的样例对局（仅供技能演示）
白方 = Student（70% 随机合法着法 + 偏好吃子/将军，30% 走引擎最佳），黑方 = Stockfish。
这样可以得到合法、带真实失误、像俱乐部玩家的对局，喂给 analyze.py 演示画像。
"""
import chess
import chess.engine
import chess.pgn
import random

ENGINE = "/usr/games/stockfish"
OUT = "samples/sample_game.pgn"


VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
        chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


def safe_random(board):
    """随机着法，但过滤掉“立刻送子”的臭棋，保持局面均衡。"""
    moves = list(board.legal_moves)
    safe = []
    for m in moves:
        board.push(m)
        bad = False
        for cap in board.legal_moves:
            if board.is_capture(cap):
                victim = board.piece_at(cap.to_square)
                attacker = board.piece_at(cap.from_square)
                if victim and attacker and VAL[victim.piece_type] > VAL[attacker.piece_type]:
                    bad = True
                    break
        board.pop()
        if not bad:
            safe.append(m)
    return random.choice(safe) if safe else random.choice(moves)


def noisy_move(board, engine, depth, rand_p):
    """接近最佳 + 噪声的陪练着法（双方都用，保持局面均衡）。"""
    moves = list(board.legal_moves)
    if random.random() < rand_p:
        return safe_random(board)
    try:
        infos = engine.analyse(board, chess.engine.Limit(time=0.06, depth=depth), multipv=4)
    except Exception:
        infos = None
    if infos:
        top = [i["pv"][0] for i in infos if i.get("pv")]
        if top:
            r = random.random()
            if r < 0.82 or len(top) == 1:
                return top[0]
            elif r < 0.94 and len(top) >= 2:
                return top[1]
            elif len(top) >= 3:
                return top[2]
            else:
                return top[-1]
    return random.choice(moves)


def white_move(board, engine):
    return noisy_move(board, engine, depth=10, rand_p=0.05)


def black_move(board, engine):
    return noisy_move(board, engine, depth=12, rand_p=0.04)


def play_game(seed):
    random.seed(seed)
    engine = chess.engine.SimpleEngine.popen_uci(ENGINE)
    engine.configure({"Hash": 64, "Threads": 1})
    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = f"Sample Coaching Game (seed {seed})"
    game.headers["Site"] = "Local"
    game.headers["Date"] = "2026.10.10"
    game.headers["Round"] = str(seed)
    game.headers["White"] = "Student"
    game.headers["Black"] = "Opponent"
    game.headers["WhiteElo"] = "1350"
    game.headers["BlackElo"] = "2000"
    node = game
    ply = 0
    try:
        while not board.is_game_over() and ply < 80:
            ply += 1
            if board.turn == chess.WHITE:
                mv = white_move(board, engine)
            else:
                mv = black_move(board, engine)
            board.push(mv)
            node = node.add_variation(mv)
        result = board.result()
    finally:
        engine.quit()
    game.headers["Result"] = result
    return game


def main():
    games = [play_game(s) for s in (1, 2, 3)]
    with open(OUT, "w", encoding="utf-8") as fh:
        for g in games:
            fh.write(str(g) + "\n\n")
    print(f"[完成] 生成 {len(games)} 局合法对局 -> {OUT}")


if __name__ == "__main__":
    main()
