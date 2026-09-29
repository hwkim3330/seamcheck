#!/usr/bin/env python3
"""repair.jsonl 을 표로 만든다. 깃발 조각과 대조군을 나눠서 본다."""
import json, statistics as st
from collections import Counter

rows = [json.loads(l) for l in open("repair.jsonl") if l.strip()]
RANK = {"OK": 0, "SKIP": 0, "SPARSE": 1, "WATCH": 2, "REVIEW": 3}


def worst(parts, key):
    """조각이 여럿이면 가장 나쁜 판정으로 본다 — 하나라도 남아 있으면 안 고친 것이다."""
    if not parts:
        return "-"
    return max((p[key] for p in parts), key=lambda v: RANK.get(v, 0))


for grp in ("flagged", "control"):
    R = [r for r in rows if r["group"] == grp]
    if not R:
        continue
    kept = [r["kept_share"] for r in R]
    print(f"\n## {grp} — 표현 {len(R)}개, 조각 {len({r['name'] for r in R})}개")
    print(f"남긴 면적: 중앙 {st.median(kept)*100:.2f}% · 최소 {min(kept)*100:.1f}% · "
          f"99% 이상 남긴 표현 {sum(k >= .99 for k in kept)}/{len(R)}")
    for sig, bk, ak in (("거리", "before_verdict", "verdict"),
                        ("권취", "before_wind_verdict", "wind_verdict")):
        tr = Counter((r[bk], worst(r["parts"], ak)) for r in R)
        b = Counter(r[bk] for r in R)
        a = Counter(worst(r["parts"], ak) for r in R)
        print(f"{sig} 전: {dict(b)}")
        print(f"{sig} 후: {dict(a)}")
        better = sum(RANK.get(worst(r['parts'], ak), 0) < RANK.get(r[bk], 0) for r in R)
        worse = sum(RANK.get(worst(r['parts'], ak), 0) > RANK.get(r[bk], 0) for r in R)
        print(f"   좋아짐 {better} · 나빠짐 {worse} · 그대로 {len(R)-better-worse}")
    # 판정은 등급이라 거칠다. 권취의 연속값이 실제로 줄었는지 같이 본다.
    pairs = [(r["before_wind_ratio"], max(p["wind_ratio"] for p in r["parts"] if p["wind_ratio"] is not None))
             for r in R if r["before_wind_ratio"] is not None and r["parts"]
             and any(p["wind_ratio"] is not None for p in r["parts"])]
    if pairs:
        b = [x for x, _ in pairs]; a = [y for _, y in pairs]
        down = sum(y < x * 0.9 for x, y in pairs); up = sum(y > x * 1.1 for x, y in pairs)
        print(f"권취 최악 배율: 전 중앙 {st.median(b):.1f}x → 후 중앙 {st.median(a):.1f}x · "
              f"10% 넘게 줄어든 표현 {down}/{len(pairs)} · 늘어난 표현 {up}")
    multi = [r for r in R if len(r["parts"]) >= 2]
    print(f"둘 이상으로 갈라진 표현 {len(multi)}개")
    for r in sorted(multi, key=lambda r: -r["before_ratio"])[:8]:
        ps = " / ".join(f"{p['share']*100:.0f}% r{p['radius_median']:.0f}" for p in r["parts"][:4])
        print(f"   {r['name'][:40]:<41} {r['before_ratio']:6.1f}x → {ps}")

# 권취가 나빠진 경우 — 수리가 해를 끼쳤는지 따로 본다
bad = [r for r in rows if RANK.get(worst(r["parts"], "wind_verdict"), 0) > RANK.get(r["before_wind_verdict"], 0)]
if bad:
    print(f"\n권취 판정이 나빠진 표현 {len(bad)}개:")
    for r in bad[:10]:
        print(f"   {r['group']:<7} {r['name'][:40]:<41} {r['before_wind_verdict']}→"
              f"{worst(r['parts'],'wind_verdict')}  조각 {len(r['parts'])}  남김 {r['kept_share']*100:.1f}%")
