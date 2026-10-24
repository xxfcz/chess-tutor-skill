#!/usr/bin/env python3.11
"""
radar.py — 把 profile.json 的多维评分画成雷达图（PNG）。
用法：python3.11 radar.py profile.json [--out report/profile_radar.png]
"""
import argparse
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np

# 挂载系统中文字体（Noto Sans CJK；ttc 首个 face 为 JP，含全部汉字字形）
_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
try:
    fm.fontManager.addfont(_CJK)
    matplotlib.rcParams["font.family"] = "Noto Sans CJK JP"
except Exception:
    pass
matplotlib.rcParams["axes.unicode_minus"] = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--out", default="report/profile_radar.png")
    args = ap.parse_args()
    with open(args.profile, encoding="utf-8") as fh:
        p = json.load(fh)
    dims = p.get("dimensions", [])
    labels = [d["name"] for d in dims]
    scores = [d["score"] for d in dims]
    if not labels:
        print("[跳过] 无维度数据")
        return

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    scores2 = scores + scores[:1]
    angles2 = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], color="grey", size=8)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, size=11)

    ax.plot(angles2, scores2, color="#2b6cb0", linewidth=2, label="当前能力")
    ax.fill(angles2, scores2, color="#2b6cb0", alpha=0.25)
    # 参考线：60 分（称职线）
    ax.plot(angles2, [60] * len(angles2), color="#e53e3e", linewidth=1, linestyle="--", alpha=0.6)

    ax.set_title("棋手多维能力画像 (0-100, 越高越好; 红虚线=称职线 60)", size=13, pad=20)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"[完成] 雷达图 -> {args.out}")


if __name__ == "__main__":
    main()
