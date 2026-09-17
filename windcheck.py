#!/usr/bin/env python3
"""windcheck — 감긴 횟수로 시트 전환을 잡는다.

seamcheck 는 3D 거리가 튀는 곳을 본다. 그런데 두루마리에서 옆 장이 눌려
맞닿아 있으면, 추적이 그 장으로 건너뛰어도 거리는 거의 안 튄다. 그때
확실히 달라지는 것은 중심축 둘레로 몇 바퀴째인가 — 감긴 횟수다.

방법:
  1. 유효점의 제1주성분을 두루마리 축으로 잡는다(실측: z 와 0.99 일치).
  2. 축에 수직인 평면에서 각 격자점의 방위각을 잰다.
  3. 격자 가로 방향을 따라 각도를 펼친다(unwrap). 정상 조각에서는
     한 칸당 각도 변화가 매우 일정하다(실측 0.514°, 최대 0.66°).
  4. 그 변화가 중앙값의 여러 배로 튀면 다른 장으로 건너뛴 것이다.

Open Problem #6 이 요구하는 "권취수 주석 자동화"의 부산물로 권취수 자체도
함께 낸다. 두 문제(#3 위상 복구, #6 나선 적합)가 같은 계산을 쓴다.

사용:
    python windcheck.py path/to/tifxyz
    python windcheck.py --s3 PHerc1667 --json out.json
"""
from __future__ import annotations
import argparse, io, json, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seamcheck import S3, fetch, s3_segments, load_xyz


def scroll_axis(pts: np.ndarray):
    """유효점의 제1주성분을 축으로 쓴다. 두루마리는 축 방향으로 가장 길다."""
    c = pts.mean(0)
    A = pts[:: max(1, len(pts) // 20000)] - c
    _, s, vt = np.linalg.svd(A, full_matrices=False)
    axis = vt[0] / np.linalg.norm(vt[0])
    share = float((s ** 2 / np.sum(s ** 2))[0])
    e1 = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(e1, axis)) > 0.9:
        e1 = np.array([0.0, 1.0, 0.0])
    e1 = e1 - axis * np.dot(e1, axis)
    e1 /= np.linalg.norm(e1)
    return c, axis, e1, np.cross(axis, e1), share


def check(P, valid, k=6.0) -> dict:
    pts = P[valid]
    if len(pts) < 500:
        return dict(ok=False, reason="점이 너무 적다")
    c, axis, e1, e2, share = scroll_axis(pts)

    q = P - c
    ang = np.arctan2(q @ e2, q @ e1)          # (H,W) 방위각
    rad = np.hypot(q @ e1, q @ e2)            # 축까지 거리

    # 축 근처에서는 각도가 원리적으로 불안정하다. 두루마리 안쪽 끝(심지)은
    # 반지름이 0 에 가까워, 20복셀 이동이 수백 도로 나온다. 실측에서 반지름
    # 3복셀짜리 점이 428도를 만들었다. 시트 전환이 아니라 좌표계의 한계다.
    # 그래서 반지름이 충분한 곳에서만 판정한다.
    r_ok = rad > max(200.0, float(np.median(rad[valid])) * 0.15)
    usable = valid & r_ok

    H, W = valid.shape
    steps = []
    turns = []
    for y in range(H):
        xs = np.nonzero(usable[y])[0]
        if xs.size < 50:
            continue
        # 빈칸을 사이에 둔 두 점은 이웃이 아니다. 끊긴 구간을 나눠 각각 처리하고,
        # 구간 경계를 넘는 차이는 절대 증분에 넣지 않는다. (이걸 섞으면 66도짜리
        # 가짜 튐이 생겨 배율이 수백 배로 폭발한다 — 첫 판에서 겪은 오경보의 원인.)
        cuts = np.nonzero(np.diff(xs) != 1)[0] + 1
        for seg in np.split(xs, cuts):
            if seg.size < 50:
                continue
            a = np.unwrap(ang[y, seg])
            steps.append(np.diff(a))
            turns.append((a.max() - a.min()) / (2 * np.pi))

    if not steps:
        return dict(ok=False, reason="축에서 충분히 떨어진 가로 구간이 없다")

    alld = np.concatenate(steps)
    med = float(np.median(np.abs(alld)))
    if med <= 0:
        return dict(ok=False, reason="각도 변화가 0")

    # 정상 대비 몇 배로 튀는 칸
    big = int((np.abs(alld) > med * k).sum())
    worst = float(np.abs(alld).max() / med)
    # 되감김: 진행 방향이 뒤집히는 곳
    # 부호 뒤집힘은 증분이 중앙값의 1/4 을 넘을 때만 센다. 0 근처의 흔들림은
    # 되감김이 아니라 측정 잡음이다.
    sig = alld[np.abs(alld) > med * 0.25] if False else alld
    strong = np.abs(alld) > med * 0.25
    sgn = np.sign(np.where(strong, alld, 0.0))
    nz = sgn[sgn != 0]
    flips = int((nz[:-1] * nz[1:] < 0).sum()) if nz.size > 1 else 0

    return dict(ok=True, axis=[round(float(x), 3) for x in axis], axis_share=round(share, 3),
                radius_used=round(float(usable.sum() / max(valid.sum(), 1)), 3),
                radius_median=round(float(np.median(rad[valid])), 1),
                step_deg=round(med * 180 / np.pi, 4),
                worst_ratio=round(worst, 1), jumps=big,
                jump_rate=big / alld.size, flips=flips, flip_rate=flips / alld.size,
                turns_median=round(float(np.median(turns)), 2),
                turns_max=round(float(np.max(turns)), 2), rows=len(steps))


def verdict(r: dict) -> str:
    if not r.get("ok"):
        return "SKIP"
    if r["worst_ratio"] >= 20 or r["jump_rate"] > 1e-3:
        return "REVIEW"
    if r["worst_ratio"] >= 8 or r["flip_rate"] > 0.02:
        return "WATCH"
    return "OK"


def run_one(src, name):
    P, v = load_xyz(src)
    r = check(P, v)
    r.update(name=name, verdict=verdict(r))
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?")
    ap.add_argument("--s3", metavar="SCROLL")
    ap.add_argument("--json", metavar="FILE")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    jobs = []
    if a.s3:
        for b in s3_segments(a.s3):
            jobs.append((f"{S3}/{b}", b.split("/segments/")[1].split("/")[0]))
    elif a.path:
        jobs.append((a.path, os.path.basename(a.path.rstrip("/"))))
    else:
        ap.print_help(); return 2

    print(f"{'조각':<34}{'칸당각도':>9}{'최악':>8}{'튐':>7}{'되감김':>8}{'바퀴':>7}  판정", flush=True)
    res = []
    jl = open((a.json or "windcheck") + ".jsonl", "a")
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(run_one, s, n): n for s, n in jobs}
        for f in as_completed(futs):
            n = futs[f]
            try:
                r = f.result()
            except Exception as e:
                print(f"{n[:32]:<34}  실패: {type(e).__name__}", flush=True); continue
            res.append(r); jl.write(json.dumps(r) + "\n"); jl.flush()
            if r.get("ok"):
                print(f"{r['name'][:32]:<34}{r['step_deg']:>8.3f}°{r['worst_ratio']:>7.1f}x"
                      f"{r['jumps']:>7,}{r['flips']:>8,}{r['turns_max']:>7.2f}  {r['verdict']}", flush=True)
            else:
                print(f"{r['name'][:32]:<34}  건너뜀: {r.get('reason')}", flush=True)
    bad = [r for r in res if r["verdict"] in ("REVIEW", "WATCH")]
    print(f"\n검사 {len(res)}개 · 봐야 할 것 {len(bad)}개")
    for r in sorted(bad, key=lambda x: -x.get("worst_ratio", 0))[:10]:
        print(f"  {r['verdict']:<7} {r['name'][:34]:<36} 최악 {r['worst_ratio']}x · 튐 {r['jumps']:,}")
    if a.json:
        json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
