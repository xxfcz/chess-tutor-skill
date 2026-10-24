#!/usr/bin/env python3.11
"""
openings.py — 开局库（e4 王兵体系 + d4 后兵体系）
=================================================
一份数据，三种练习模式共用：
  1. 闯关（drill）   —— 跟引擎实战，每步验证是否在第一梯队着法内
  2. 默写（quiz）     —— 系统出题，选出正确应对
  3. 对弈页开局模式  —— 强制走开局变化，实战体会

每条开局的字段：
  id      唯一标识
  name    中文名
  en      英文名
  family  e4 / d4
  side    学习者执哪方（white/black）
  moves   标准主变（UCI 列表）—— 默写与强制变化用
  ideas   关键想法（教学要点，非背谱）
  traps   常见陷阱/易错点
  level   1=入门 2=进阶
"""
from __future__ import annotations

OPENINGS = [
    # ==================== e4 王兵体系 ====================
    {
        "id": "italian",
        "name": "意大利开局",
        "en": "Italian Game",
        "family": "e4",
        "side": "white",
        "level": 1,
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"],
        "ideas": [
            "目标是 f7 —— 黑方唯一没有子力保护的兵，也是王翼最软的点。",
            "c4 象直指 f7，配合 Nf3 形成双人对 f7 的压力。",
            "先出轻子、早易位，不要急着 d4（那是意大利的进阶变化）。",
        ],
        "traps": [
            "别急着 Ng5 抢攻 —— 会被 ...h6 赶回去，白浪费时间。",
            "Bb5 在这个局面是另一体系（西班牙），别混着下。",
        ],
    },
    {
        "id": "italian_two_knights",
        "name": "意大利 · 双马防御",
        "en": "Two Knights Defense",
        "family": "e4",
        "side": "white",
        "level": 2,
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6"],
        "ideas": [
            "黑方走 Nf6 反击 e4，你要决定：守 e4 还是抢攻 f7。",
            "d3 是稳健线（守 e4，转入慢节奏），Ng5 是激战线。",
            "记住原则：对手反击你的中心时，优先考虑巩固而不是对攻。",
        ],
        "traps": [
            "Ng5 之后黑方有 ...d5! 弃兵反击，属于高风险线，新手慎入。",
            "别为了抢攻把 e4 白送 —— e4 一丢，中心就拱手相让。",
        ],
    },
    {
        "id": "spanish",
        "name": "西班牙开局",
        "en": "Ruy Lopez",
        "family": "e4",
        "side": "white",
        "level": 2,
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"],
        "ideas": [
            "Bb5 间接攻击 c6 马（因为 c6 马在守 e5），压迫黑方中心。",
            "威胁不是马上吃 c6，而是让黑方不得不分心应付。",
            "稳健、局面型，适合练'慢慢积累优势'的思路。",
        ],
        "traps": [
            "别以为 Bb5 是要立刻 Bxc6 —— 那会送给黑方双象优势。",
            "注意黑方 ...a6 后你要决定撤象还是交换，这是关键分岔。",
        ],
    },
    {
        "id": "four_knights",
        "name": "四马开局",
        "en": "Four Knights Game",
        "family": "e4",
        "side": "white",
        "level": 1,
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "b1c3", "g8f6"],
        "ideas": [
            "双方对称出马，最容易理解的对称结构。",
            "重点不是抢攻，是练'平稳局面下如何找计划'。",
            "对称局面里，谁先打破对称谁先拿到主动权。",
        ],
        "traps": [
            "对称不等于可以随便走 —— 一个走神就会被 ...Nxe4 白吃一兵。",
        ],
    },
    {
        "id": "scotch",
        "name": "苏格兰开局",
        "en": "Scotch Game",
        "family": "e4",
        "side": "white",
        "level": 1,
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "d2d4"],
        "ideas": [
            "立刻 d4 打开中心，局面变得开放、直接。",
            "适合喜欢明确计算的棋手，不玩虚的。",
            "打开中心后，出子速度决定一切。",
        ],
        "traps": [
            "开放局面里，一步慢就会被打反击，务必每步检查将军与吃子。",
        ],
    },
    # ---- 黑方应对 1.e4 ----
    {
        "id": "sicilian",
        "name": "西西里防御（黑方）",
        "en": "Sicilian Defense",
        "family": "e4",
        "side": "black",
        "level": 2,
        "moves": ["e2e4", "c7c5", "g1f3", "d7d6"],
        "ideas": [
            "不下对称的 e5，而是从侧翼 c5 攻击 d4 格，避开正面冲突。",
            "这是胜率最高的黑方应手之一，代价是局面更复杂、更考验计算。",
            "核心思想：用 c 兵换掉白方 d 兵，拿到半开放 c 线。",
        ],
        "traps": [
            "复杂体系，需要记一些主线，否则容易在中局迷路。",
        ],
    },
    {
        "id": "french",
        "name": "法兰西防御（黑方）",
        "en": "French Defense",
        "family": "e4",
        "side": "black",
        "level": 1,
        "moves": ["e2e4", "e7e6", "d2d4", "d7d5"],
        "ideas": [
            "e6 准备 d5，建立坚固的中心。",
            "结构稳、计划清楚：先守后攻，从后翼反击。",
            "适合喜欢稳健、不爱乱战的棋风。",
        ],
        "traps": [
            "c8 象容易被自己的兵困住，这是法兰西的老问题，要提前安排。",
        ],
    },
    {
        "id": "caro_kann",
        "name": "卡罗康防御（黑方）",
        "en": "Caro-Kann Defense",
        "family": "e4",
        "side": "black",
        "level": 1,
        "moves": ["e2e4", "c7c6", "d2d4", "d7d5"],
        "ideas": [
            "c6 准备 d5，和法兰西目标一样，但象的出路更通畅。",
            "非常稳固，是'不想冒险'的好选择。",
            "残局结构通常对黑方友好。",
        ],
        "traps": [
            "出子偏慢，别拖太久被白方抢先发起攻势。",
        ],
    },
    {
        "id": "open_game_e5",
        "name": "开放性对局（黑方 1...e5）",
        "en": "Open Game",
        "family": "e4",
        "side": "black",
        "level": 1,
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6"],
        "ideas": [
            "最经典的对称应对，直接对抗中心。",
            "局面开放、出子快，适合练基本功。",
            "缺点是容易陷入白方熟悉的意大利/西班牙套路。",
        ],
        "traps": [
            "别被动防守 —— 对称局面里被动就等于慢性失血。",
        ],
    },
    # ==================== d4 后兵体系 ====================
    {
        "id": "london",
        "name": "伦敦体系",
        "en": "London System",
        "family": "d4",
        "side": "white",
        "level": 1,
        "moves": ["d2d4", "d7d5", "g1f3", "g8f6", "c1f4", "e7e6"],
        "ideas": [
            "结构极其稳固，几乎不依赖对手怎么走，是'万能开局'。",
            "Bf4 先出象到外面（黑方的象往往被困在 c8），这是关键。",
            "适合没时间背谱、想要一个稳定可复制的体系。",
        ],
        "traps": [
            "过于程式化，容易被高手针对性布置，要懂得变通。",
        ],
    },
    {
        "id": "queens_gambit",
        "name": "后翼弃兵",
        "en": "Queen's Gambit",
        "family": "d4",
        "side": "white",
        "level": 2,
        "moves": ["d2d4", "d7d5", "c2c4", "e7e6"],
        "ideas": [
            "c4 不是真弃兵，黑方若 ...dxc4 可以用 e3/Bxc4 拿回来。",
            "目标是让黑方在中心做选择：吃（放弃中心）还是守（被压制）。",
            "经典局面型开局，练'用兵结构施压'。",
        ],
        "traps": [
            "别把 c4 当真的弃掉 —— 拿不回来才是真亏。",
        ],
    },
    {
        "id": "catalan",
        "name": "卡特兰开局",
        "en": "Catalan Opening",
        "family": "d4",
        "side": "white",
        "level": 2,
        "moves": ["d2d4", "g8f6", "c2c4", "e7e6", "g2g3"],
        "ideas": [
            "g3 + Bg2 构筑长斜线，象在 g2 上长期压制后翼。",
            "慢热型体系，靠长期局面压力取胜，不靠战术。",
            "很适合练'耐心'与'局面感觉'。",
        ],
        "traps": [
            "节奏慢，如果对手猛攻，你得知道何时转守。",
        ],
    },
]


def get(opening_id: str):
    for o in OPENINGS:
        if o["id"] == opening_id:
            return o
    return None


def by_family(family: str | None = None, side: str | None = None):
    out = OPENINGS
    if family:
        out = [o for o in out if o["family"] == family]
    if side:
        out = [o for o in out if o["side"] == side]
    return out


if __name__ == "__main__":
    print(f"共 {len(OPENINGS)} 条开局\n")
    for fam in ("e4", "d4"):
        print(f"【{fam} 体系】")
        for o in by_family(fam):
            side = "执白" if o["side"] == "white" else "执黑"
            print(f"  [{o['level']}] {o['name']:16s} {o['en']:24s} {side}  {len(o['moves'])} 半回合")
        print()
