#!/usr/bin/env python3
"""meshcheck — 추적된 표면 메시의 위상 결함을 센다.

seamcheck 가 "추적이 옆 장으로 건너뛰었나"를 본다면, 이쪽은 "메시 자체가
성한가"를 본다. 둘은 서로를 대신하지 못한다. 시트 전환은 위상이 멀쩡한 채로
일어나고, 구멍과 병합은 3D 거리가 멀쩡한 채로 일어난다.

세는 것:
  · 경계 모서리   면 하나만 공유 → 구멍이거나 바깥 테두리
  · 비다양체 모서리 면 셋 이상 공유 → 두 장이 붙어버린 곳(merger)
  · 연결 조각     한 덩어리여야 하는데 나뉜 경우, 그리고 작은 파편

77만 면짜리 메시를 4초에 처리한다. 의존성은 표준 라이브러리뿐이다.

사용:
    python meshcheck.py surface.obj
    python meshcheck.py *.obj --json out.json
"""
from __future__ import annotations
import argparse, json, sys, time
from collections import Counter, defaultdict


def read_obj(path: str):
    """OBJ 에서 정점 수와 삼각형만 뽑는다. 다각형은 부채꼴로 쪼갠다."""
    nv = 0
    faces = []
    with open(path, "rb") as fh:
        for line in fh:
            if line[:2] == b"v ":
                nv += 1
            elif line[:2] == b"f ":
                idx = []
                for tok in line.split()[1:]:
                    i = int(tok.split(b"/")[0])
                    idx.append(i - 1 if i > 0 else nv + i)
                for k in range(1, len(idx) - 1):
                    faces.append((idx[0], idx[k], idx[k + 1]))
    return nv, faces


def edges_of(f):
    a, b, c = f
    for u, v in ((a, b), (b, c), (c, a)):
        yield (u, v) if u < v else (v, u)


def analyse(path: str) -> dict:
    t0 = time.time()
    nv, F = read_obj(path)
    if not F:
        raise ValueError("면이 없다")

    count = Counter()
    face_of = defaultdict(list)
    for fi, f in enumerate(F):
        for e in edges_of(f):
            count[e] += 1
            face_of[e].append(fi)

    per = Counter(count.values())
    boundary = per[1]
    manifold = per[2]
    nonman = sum(n for k, n in per.items() if k > 2)

    # 면 인접으로 연결 조각 세기
    seen = bytearray(len(F))
    comps = []
    for s in range(len(F)):
        if seen[s]:
            continue
        stack = [s]
        seen[s] = 1
        n = 0
        while stack:
            f = stack.pop()
            n += 1
            for e in edges_of(F[f]):
                for g in face_of[e]:
                    if not seen[g]:
                        seen[g] = 1
                        stack.append(g)
        comps.append(n)
    comps.sort(reverse=True)

    total_e = len(count)
    r = dict(
        name=path.split("/")[-1], vertices=nv, faces=len(F), edges=total_e,
        boundary_edges=boundary, boundary_rate=boundary / total_e,
        nonmanifold_edges=nonman, nonmanifold_rate=nonman / total_e,
        components=len(comps), largest_share=comps[0] / len(F),
        fragments_under_10=sum(1 for c in comps if c < 10),
        seconds=round(time.time() - t0, 2),
    )
    r["verdict"] = verdict(r)
    return r


def verdict(r: dict) -> str:
    if r["nonmanifold_edges"] > 0:
        return "MERGER"        # 두 장이 붙었다
    if r["components"] > 1 and r["largest_share"] < 0.99:
        return "SPLIT"         # 조각이 나뉘었다
    if r["boundary_rate"] > 0.05:
        return "HOLES"         # 경계가 너무 많다
    return "OK"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("obj", nargs="+")
    ap.add_argument("--json", metavar="FILE")
    a = ap.parse_args()

    print(f"{'메시':<34}{'정점':>10}{'면':>10}{'경계':>9}{'비다양체':>9}{'조각':>7}  판정")
    res = []
    for p in a.obj:
        try:
            r = analyse(p)
        except Exception as e:
            print(f"{p.split('/')[-1][:32]:<34}  실패: {type(e).__name__}: {e}")
            continue
        res.append(r)
        print(f"{r['name'][:32]:<34}{r['vertices']:>10,}{r['faces']:>10,}"
              f"{r['boundary_rate']*100:>8.2f}%{r['nonmanifold_edges']:>9,}"
              f"{r['components']:>7,}  {r['verdict']}")
    bad = [r for r in res if r["verdict"] != "OK"]
    print(f"\n검사 {len(res)}개 · 사람이 봐야 할 것 {len(bad)}개")
    if a.json:
        json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)
        print(f"저장: {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
