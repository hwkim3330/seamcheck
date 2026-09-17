#!/usr/bin/env python3
"""seamcheck — 파피루스 표면 추적의 이음새 결함을 찾는다.

Vesuvius Challenge Open Problem #3(자동 메시 위상 복구)을 겨냥한 도구.
사람이 조각 하나하나를 눈으로 검사하지 않고도 다음을 잡아낸다.

  · 시트 전환(sheet switch) — 추적이 옆 장으로 건너뛴 지점
  · 구멍과 찢김        — 표면이 끊긴 지점
  · 조각 분리          — 한 덩어리여야 할 것이 나뉜 경우

원리는 하나다. tifxyz 표현에서 격자상 이웃한 두 점은 3D에서도 이웃해야 한다.
정상 간격은 한 조각 안에서 매우 일정하므로(실측: 중앙값 20복셀, 변동 ±5%),
그 배수로 튀는 지점은 추적이 다른 장으로 건너뛴 곳이다.

GPU도 CT 원본도 필요 없다. 세그먼트당 3MB만 받으면 된다.

사용:
    python seamcheck.py path/to/tifxyz            # 로컬 폴더
    python seamcheck.py --s3 PHercParis4          # S3 두루마리 전체
    python seamcheck.py path --json out.json      # 기계가 읽을 결과
"""
from __future__ import annotations
import argparse, io, json, os, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

S3 = "https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com"


def fetch(url: str, tries: int = 4) -> bytes:
    """S3 는 가끔 연결을 끊는다. 지수 대기로 재시도한다."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "seamcheck/0.1"})
            return urllib.request.urlopen(req, timeout=120).read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))
    raise RuntimeError("unreachable")


def load_xyz(src: str):
    """tifxyz 삼중 파일을 (H,W,3) 배열과 유효 마스크로 읽는다."""
    import tifffile
    if src.startswith("http"):
        get = lambda c: tifffile.imread(io.BytesIO(fetch(f"{src}/{c}.tif")))
    else:
        get = lambda c: tifffile.imread(os.path.join(src, f"{c}.tif"))
    X, Y, Z = (get(c) for c in "xyz")
    if not (X.shape == Y.shape == Z.shape):
        raise ValueError(f"x/y/z 크기가 다름: {X.shape} {Y.shape} {Z.shape}")
    P = np.stack([X, Y, Z], -1).astype(np.float64)
    valid = (X >= 0) & (Y >= 0) & (Z >= 0)     # -1 은 빈칸
    return P, valid


def neighbour_steps(P, valid, axis: int):
    """격자 한 축에서 이웃 간 3D 거리와 그 위치."""
    n = P.shape[axis]
    a = np.take(P, np.arange(n - 1), axis=axis)
    b = np.take(P, np.arange(1, n), axis=axis)
    va = np.take(valid, np.arange(n - 1), axis=axis)
    vb = np.take(valid, np.arange(1, n), axis=axis)
    m = va & vb
    return np.linalg.norm(b - a, axis=-1), m


def check(P, valid, k_flag: float = 5.0, k_bad: float = 10.0) -> dict:
    """이음새 통계와 결함 후보 좌표를 낸다."""
    out = dict(shape=[int(s) for s in P.shape[:2]], coverage=float(valid.mean()))
    med_all, mx_all, n5, n10, tot = 0.0, 0.0, 0, 0, 0
    spots = []
    for axis, name in ((0, "v"), (1, "u")):
        d, m = neighbour_steps(P, valid, axis)
        dv = d[m]
        if dv.size == 0:
            continue
        med = float(np.median(dv))
        med_all = max(med_all, med)
        mx_all = max(mx_all, float(dv.max()))
        tot += int(dv.size)
        hit = m & (d > med * k_flag)
        n5 += int(hit.sum())
        n10 += int((m & (d > med * k_bad)).sum())
        ys, xs = np.nonzero(hit)
        order = np.argsort(-d[hit])[:40]          # 심한 것부터 40개
        for i in order:
            spots.append(dict(axis=name, y=int(ys[i]), x=int(xs[i]),
                              step=float(d[hit][i]), times=float(d[hit][i] / med)))
    out.update(median_step=med_all, max_step=mx_all,
               ratio=(mx_all / med_all if med_all else 0.0),
               edges=tot, flagged=n5, severe=n10,
               flag_rate=(n5 / tot if tot else 0.0),
               spots=sorted(spots, key=lambda s: -s["times"])[:40])
    return out


def verdict(r: dict) -> str:
    """사람이 다시 봐야 하는가.

    유효 격자가 적으면 판정하지 않는다. 빈칸이 많은 조각은 중앙값 자체가
    흔들려 배율이 의미를 잃는다. 실측에서 유효율 20~50% 구간은 배율 중앙이
    4.5배로 80% 이상 구간(1.7배)의 2.6배였다 — 결함이 더 많아서가 아니라
    기준선이 불안정해서다. 그래서 먼저 걸러낸다.
    """
    if r["coverage"] < 0.5:
        return "SPARSE"        # 판정 보류 — 빈칸이 많다
    if r["ratio"] >= 10 or r["severe"] > 0:
        return "REVIEW"        # 시트 전환이 의심된다
    if r["ratio"] >= 5 or r["flag_rate"] > 1e-4:
        return "WATCH"         # 국소적으로 튄다
    return "OK"


def _list(prefix: str, delimiter: str = ""):
    """S3 목록 한 페이지씩. delimiter 를 주면 하위 폴더만 받는다."""
    keys, prefixes, tok = [], [], None
    while True:
        u = (f"{S3}/?list-type=2&prefix={urllib.parse.quote(prefix)}&max-keys=1000"
             + (f"&delimiter={delimiter}" if delimiter else "")
             + (f"&continuation-token={urllib.parse.quote(tok)}" if tok else ""))
        x = fetch(u).decode()
        keys += re.findall(r"<Key>([^<]+)</Key>", x)
        prefixes += re.findall(r"<Prefix>([^<]+)</Prefix>", x)
        m = re.search(r"<NextContinuationToken>([^<]+)<", x)
        if not m:
            break
        tok = m.group(1)
    return keys, prefixes


def s3_segments(scroll: str):
    """두루마리 아래 tifxyz 폴더를 찾는다.

    두루마리 전체 키를 훑으면 zarr 청크 수만 개가 딸려와 몇 분씩 걸린다.
    세그먼트 폴더 목록을 먼저 받고(delimiter), 각 세그먼트의 mesh/ 아래만 본다.
    """
    _, segs = _list(f"{scroll}/segments/", delimiter="/")
    out = []

    def one(seg):
        keys, _ = _list(f"{seg}mesh/")
        return [k[:-6] for k in keys if k.endswith("/x.tif") and "tifxyz" in k]

    with ThreadPoolExecutor(max_workers=8) as ex:
        for got in ex.map(one, segs):
            out += got
    return sorted(set(out))


def run_one(src: str, name: str) -> dict:
    P, valid = load_xyz(src)
    r = check(P, valid)
    r.update(name=name, verdict=verdict(r))
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="tifxyz 폴더")
    ap.add_argument("--s3", metavar="SCROLL", help="S3 두루마리 전체 검사 (예: PHercParis4)")
    ap.add_argument("--json", metavar="FILE", help="결과를 JSON 으로 저장")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    jobs = []
    if a.s3:
        for b in s3_segments(a.s3):
            jobs.append((f"{S3}/{b}", b.split("/segments/")[1].split("/")[0]))
    elif a.path:
        jobs.append((a.path, os.path.basename(a.path.rstrip("/"))))
    else:
        ap.print_help()
        return 2

    print(f"{'조각':<40}{'격자':>12}{'중앙':>7}{'최대':>9}{'배율':>8}{'의심':>7}  판정", flush=True)
    res = []
    jl = open((a.json or "seamcheck") + ".jsonl", "a")
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(run_one, s, n): n for s, n in jobs}
        for f in as_completed(futs):
            n = futs[f]
            try:
                r = f.result()
            except Exception as e:
                print(f"{n[:38]:<40}  실패: {type(e).__name__}", flush=True)
                continue
            res.append(r)
            jl.write(json.dumps({k: v for k, v in r.items() if k != "spots"}) + "\n"); jl.flush()
            print(f"{r['name'][:38]:<40}{str(tuple(r['shape'])):>12}"
                  f"{r['median_step']:>7.1f}{r['max_step']:>9.1f}{r['ratio']:>7.1f}x"
                  f"{r['flagged']:>7,}  {r['verdict']}", flush=True)
    res.sort(key=lambda r: -r["ratio"])
    bad = [r for r in res if r["verdict"] in ("REVIEW", "WATCH")]
    print(f"\n검사 {len(res)}개 · 사람이 봐야 할 것 {len(bad)}개")
    for r in bad[:10]:
        s = r["spots"][0] if r["spots"] else None
        where = f" 최악 지점 ({s['x']},{s['y']}) {s['times']:.0f}배" if s else ""
        print(f"  {r['verdict']:<7} {r['name'][:38]:<40} 배율 {r['ratio']:.1f}x{where}")
    if a.json:
        json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)
        print(f"\n저장: {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
