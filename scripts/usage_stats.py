#!/usr/bin/env python3.11
"""
usage_stats.py — 会话 token 用量统计
====================================
读 WorkBuddy/CodeBuddy 的会话 transcript（JSONL），汇总每次模型调用的
input/output/cache 用量，给出累计值、缓存命中率和逐轮趋势。

用法：
    python3 scripts/usage_stats.py                    # 自动找最近修改的 transcript
    python3 scripts/usage_stats.py <path.jsonl>       # 指定某个 transcript
    python3 scripts/usage_stats.py --all              # 列出所有 transcript 的汇总对比
    python3 scripts/usage_stats.py --trend 10         # 只看最近 10 次调用的趋势

注意：
  - 这是"token 用量"，不是"积分余额"。积分/账务在平台账户层，沙箱读不到。
  - 一个会话里同一次调用可能被记录多次（不同字段形态），脚本按
    (input, output, cache) 三元组在相邻记录间去重，避免重复计数。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

DEFAULT_GLOB = os.path.expanduser("~/.codebuddy/projects/*/*.jsonl")


def _iter_usage(obj):
    """递归找出所有含 input_tokens/output_tokens 的 dict。"""
    if isinstance(obj, dict):
        if "input_tokens" in obj and "output_tokens" in obj:
            yield {
                "input": obj.get("input_tokens") or 0,
                "output": obj.get("output_tokens") or 0,
                "cache": obj.get("cache_read_input_tokens") or 0,
            }
        for v in obj.values():
            yield from _iter_usage(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_usage(v)


def load_usage(path: str) -> list[dict]:
    """读一个 transcript，返回去重后的 usage 列表（按出现顺序）。"""
    rows: list[dict] = []
    seen_prev = None
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            for u in _iter_usage(obj):
                key = (u["input"], u["output"], u["cache"])
                # 同一行内常出现嵌套重复，相邻相同即视为同一次调用
                if key == seen_prev:
                    continue
                rows.append(u)
                seen_prev = key
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    tin = sum(r["input"] for r in rows)
    tout = sum(r["output"] for r in rows)
    tcache = sum(r["cache"] for r in rows)
    return {
        "calls": n,
        "input": tin,
        "output": tout,
        "cache": tcache,
        "total": tin + tout,
        "cache_rate": (tcache / tin * 100) if tin else 0.0,
        "avg_input": (tin / n) if n else 0.0,
    }


def fmt(n: float) -> str:
    return f"{int(n):,}"


def print_summary(s: dict, title: str = "用量汇总"):
    print(f"\n=== {title} ===")
    print(f"模型调用次数     : {s['calls']:,}")
    print(f"累计 input       : {fmt(s['input'])}")
    print(f"累计 output      : {fmt(s['output'])}")
    print(f"  其中缓存命中    : {fmt(s['cache'])}  （占 input 的 {s['cache_rate']:.1f}%）")
    print(f"累计 total       : {fmt(s['total'])}")
    print(f"平均每次 input   : {fmt(s['avg_input'])}")
    print(f"估算未缓存 input : {fmt(max(s['input'] - s['cache'], 0))}  ← 这部分才是较贵的")


def print_trend(rows: list[dict], k: int = 10):
    tail = rows[-k:]
    if not tail:
        print("\n（无调用记录）")
        return
    print(f"\n=== 最近 {len(tail)} 次调用趋势 ===")
    print(f"{'#':>4} {'input':>9} {'cache':>9} {'output':>7} {'命中率':>7}")
    base = len(rows) - len(tail)
    for i, r in enumerate(tail, start=base + 1):
        rate = (r["cache"] / r["input"] * 100) if r["input"] else 0.0
        print(f"{i:>4} {fmt(r['input']):>9} {fmt(r['cache']):>9} "
              f"{fmt(r['output']):>7} {rate:>6.1f}%")


def newest_transcript() -> str | None:
    files = [p for p in glob.glob(DEFAULT_GLOB) if os.path.getsize(p) > 0]
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def main():
    ap = argparse.ArgumentParser(description="会话 token 用量统计")
    ap.add_argument("path", nargs="?", help="transcript 路径（默认取最近修改的一个）")
    ap.add_argument("--all", action="store_true", help="汇总所有 transcript 并对比")
    ap.add_argument("--trend", type=int, default=0, metavar="N",
                    help="显示最近 N 次调用的趋势")
    args = ap.parse_args()

    if args.all:
        files = sorted(glob.glob(DEFAULT_GLOB), key=os.path.getmtime, reverse=True)
        if not files:
            print("没找到 transcript 文件")
            return 1
        print(f"{'文件':<28} {'调用':>5} {'input':>13} {'output':>9} {'合计':>13}")
        print("-" * 76)
        grand = {"input": 0, "output": 0, "cache": 0, "calls": 0, "total": 0,
                 "cache_rate": 0, "avg_input": 0}
        for f in files:
            rows = load_usage(f)
            if not rows:
                continue
            s = summarize(rows)
            name = Path(f).stem
            if len(name) > 26:
                name = name[:12] + "…" + name[-10:]
            print(f"{name:<28} {s['calls']:>5} {fmt(s['input']):>13} "
                  f"{fmt(s['output']):>9} {fmt(s['total']):>13}")
            for k in ("input", "output", "cache", "calls", "total"):
                grand[k] += s[k]
        if grand["input"]:
            grand["cache_rate"] = grand["cache"] / grand["input"] * 100
            grand["avg_input"] = grand["input"] / max(grand["calls"], 1)
        print_summary(grand, "全部会话合计")
        return 0

    path = args.path or newest_transcript()
    if not path:
        print("没找到 transcript 文件，请显式指定路径")
        return 1
    if not os.path.exists(path):
        print(f"文件不存在: {path}")
        return 1

    rows = load_usage(path)
    print(f"文件: {path}")
    print(f"大小: {os.path.getsize(path):,} 字节")
    print_summary(summarize(rows), "本会话用量")
    if args.trend > 0:
        print_trend(rows, args.trend)
    return 0


if __name__ == "__main__":
    sys.exit(main())
