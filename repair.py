#!/usr/bin/env python3
"""repair — 시트 전환이 난 표면을 이음새에서 잘라, 깨끗한 조각들로 나눈다.

seamcheck 는 "여기서 옆 장으로 건너뛰었다"까지만 말한다. Open Problem #3 은
검출이 아니라 **자동 수리**를 묻는다. 이 도구가 그 다음 단계다.

원리는 검출과 같다. 격자상 이웃한 두 점은 3D 에서도 이웃해야 한다.
이웃 간격이 그 조각 자신의 중앙값의 k 배(기본 5배)를 넘는 격자 연결은
같은 장 위의 연결이 아니다. 그 연결만 끊고, 남은 연결로 덩어리를 나눈다.

  · 이음새가 표면을 가로지르면 → 두 장이 서로 다른 덩어리로 떨어진다
  · 튀는 점 몇 개뿐이면       → 그 점들만 작은 덩어리로 떨어져 버려진다
  · 멀쩡한 조각이면           → 끊을 연결이 없어 아무것도 안 바뀐다

마지막 성질이 중요하다. 수리 도구는 멀쩡한 걸 망가뜨리면 안 된다.
그래서 결과마다 **남긴 면적**을 같이 보고하고, 멀쩡한 조각에서도 돌려 확인한다.

각 덩어리는 원본과 같은 형식(x/y/z.tif + meta.json, 빈칸은 -1)으로 나간다.
원본 격자 좌표를 그대로 유지하므로 기존 도구(평탄화, 잉크 검출)에 바로 넣을 수 있다.

사용:
    python repair.py path/to/seg.tifxyz --out fixed/        # 로컬
    python repair.py https://...tifxyz --out fixed/         # S3 에서 바로
    python repair.py path --out fixed/ --k 5 --min-frac 0.02
"""
from __future__ import annotations
import argparse, io, json, os, sys

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seamcheck import load_xyz, check, verdict, fetch  # noqa: E402
import windcheck  # noqa: E402  — 수리 결과를 '다른 신호'로 확인한다


def bad_edges(P, valid, k: float):
    """이웃 간격이 k×중앙값을 넘는 격자 연결의 양 끝 칸 번호."""
    H, W = valid.shape
    idx = np.arange(H * W).reshape(H, W)
    per = []
    for axis in (0, 1):
        n = P.shape[axis]
        a = np.take(P, np.arange(n - 1), axis=axis)
        b = np.take(P, np.arange(1, n), axis=axis)
        m = np.take(valid, np.arange(n - 1), axis=axis) & np.take(valid, np.arange(1, n), axis=axis)
        d = np.linalg.norm(b - a, axis=-1)
        per.append((d, m, np.take(idx, np.arange(n - 1), axis=axis),
                    np.take(idx, np.arange(1, n), axis=axis)))
    # seamcheck 과 같은 기준 — 축별 중앙값 중 큰 쪽
    med = max(float(np.median(d[m])) for d, m, _, _ in per if m.any())
    ea, eb = [], []
    for d, m, ia, ib in per:
        bad = m & (d > med * k)
        ea.append(ia[bad]); eb.append(ib[bad])
    return np.concatenate(ea), np.concatenate(eb), med


def erase_seam(valid, ea, eb):
    """
    나쁜 연결마다 한쪽 끝 칸을 비운다.

    처음에는 연결만 끊고 덩어리를 나눴다. 그런데 v14 에서 24,528개를 끊고도
    덩어리가 하나로 남았고 배율도 36배 그대로였다. 끊은 연결의 양 끝이 다른
    경로로 이어져 있으면, 같은 조각 안에 이음새가 격자 이웃으로 그대로 남는다.
    tifxyz 에는 '연결을 지우는' 표현이 없다. 칸을 비워야만 끊긴다.

    어느 쪽 끝을 비울지는 나쁜 연결에 더 많이 걸린 칸을 고른다. 이음새 선을
    따라 한 줄만 비우게 되어, 양쪽을 다 비우는 것보다 버리는 면적이 작다.
    """
    deg = np.bincount(np.concatenate([ea, eb]), minlength=valid.size)
    pick = np.where(deg[ea] >= deg[eb], ea, eb)
    out = valid.copy().ravel()
    out[np.unique(pick)] = False
    return out.reshape(valid.shape), int(np.unique(pick).size)


def split(P, valid, k: float = 5.0, min_frac: float = 0.02, min_cells: int = 500):
    """이음새를 도려낸 뒤 덩어리로 나누고, 충분히 큰 것만 큰 순서로 돌려준다."""
    from scipy.ndimage import label
    ea, eb, med = bad_edges(P, valid, k)
    clean, erased = erase_seam(valid, ea, eb)
    lab, _ = label(clean)                 # 4-이웃. 남은 연결은 전부 k×중앙값 이하다
    lab = lab - 1                          # 배경 -1, 덩어리 0..
    ids, counts = np.unique(lab[lab >= 0], return_counts=True)
    order = np.argsort(-counts)
    total = int(valid.sum())
    # 가장 큰 덩어리는 크기와 상관없이 항상 남긴다. 작은 크기 기준은 수리로
    # 떨어져 나온 부스러기에만 적용한다. (처음엔 모든 덩어리에 적용했다가,
    # 끊을 곳이 하나도 없는 315칸짜리 멀쩡한 표현을 통째로 버렸다.)
    keep = [(int(ids[i]), int(counts[i])) for j, i in enumerate(order)
            if j == 0 or counts[i] >= max(min_cells, min_frac * total)]
    return lab, keep, med, int(ea.size), erased, total


def axis_fit(points):
    """두루마리 축 — 점들의 첫 주성분. 조각이 어느 장에 있는지 보려고 쓴다."""
    c = points.mean(0)
    _, _, vt = np.linalg.svd(points - c, full_matrices=False)
    return c, vt[0]


def radius_about(points, c, ax):
    """축으로부터의 거리. 같은 장이면 비슷하고, 옆 장이면 크게 다르다."""
    v = points - c
    return np.linalg.norm(v - np.outer(v @ ax, ax), axis=1)


def write_tifxyz(dst, P, mask, meta):
    import tifffile
    os.makedirs(dst, exist_ok=True)
    for i, ch in enumerate("xyz"):
        a = P[..., i].astype(np.float32).copy()
        a[~mask] = -1.0
        tifffile.imwrite(os.path.join(dst, f"{ch}.tif"), a, compression="zlib")
    m = dict(meta or {})
    pts = P[mask]
    if pts.size:
        m["bbox"] = [pts.min(0).tolist(), pts.max(0).tolist()]
    m["format"] = "tifxyz"
    m.setdefault("type", "seg")
    m["repaired_by"] = "seamcheck/repair.py"
    json.dump(m, open(os.path.join(dst, "meta.json"), "w"), indent=2)


def read_meta(src):
    try:
        if src.startswith("http"):
            return json.loads(fetch(f"{src}/meta.json").decode())
        return json.load(open(os.path.join(src, "meta.json")))
    except Exception:
        return {}


def repair(src, out=None, k=5.0, min_frac=0.02, quiet=False):
    P, valid = load_xyz(src)
    before = check(P, valid)
    before["verdict"] = verdict(before)
    lab, keep, med, cut, erased, total = split(P, valid, k=k, min_frac=min_frac)
    # 독립 검증. 수리는 3D 거리로 했으니 3D 거리로 다시 재면 깨끗한 게 당연하다.
    # 권취(축 둘레 각도의 연속성)는 다른 신호라, 이게 같이 좋아져야 진짜로 고친 것이다.
    wb = windcheck.check(P, valid); wb_v = windcheck.verdict(wb)

    # 한 축을 전체 표면에서 맞추고, 덩어리마다 그 축으로부터의 반경을 잰다.
    # 두 덩어리의 반경이 크게 다르면 서로 다른 장(wrap)이라는 증거다.
    c, ax = axis_fit(P[valid][:: max(1, total // 200000)])

    parts = []
    for rank, (cid, n) in enumerate(keep):
        mask = lab == cid
        r = check(P, mask)
        r["verdict"] = verdict(r)
        rad = radius_about(P[mask][:: max(1, n // 50000)], c, ax)
        w = windcheck.check(P, mask)
        parts.append(dict(rank=rank, cells=n, share=n / total,
                          ratio=r["ratio"], max_step=r["max_step"], verdict=r["verdict"],
                          wind_ratio=w.get("worst_ratio"), wind_verdict=windcheck.verdict(w),
                          coverage=r["coverage"], radius_median=float(np.median(rad))))
        if out:
            write_tifxyz(os.path.join(out, f"part{rank:02d}.tifxyz"), P, mask, read_meta(src))

    kept = sum(p["cells"] for p in parts)
    res = dict(src=src, shape=list(valid.shape), cells=total, median_step=med,
               cut_edges=cut, erased_cells=erased,
               before_ratio=before["ratio"], before_verdict=before["verdict"],
               before_wind_ratio=wb.get("worst_ratio"), before_wind_verdict=wb_v,
               parts=parts, kept_share=kept / total if total else 0.0,
               dropped_cells=total - kept)
    if not quiet:
        print(f"원본  {tuple(valid.shape)}  거리 {before['ratio']:.1f}x {before['verdict']:<6}"
              f"  권취 {wb.get('worst_ratio')}x {wb_v:<6} · 나쁜 연결 {cut:,} · 도려낸 칸 {erased:,}")
        for p in parts:
            print(f"  조각{p['rank']:02d}  {p['cells']:>10,}칸 ({p['share']*100:5.1f}%)  "
                  f"거리 {p['ratio']:5.1f}x {p['verdict']:<6}  권취 {p['wind_ratio']}x {p['wind_verdict']:<6}"
                  f"  축 반경 {p['radius_median']:>7.0f}")
        print(f"  남긴 면적 {res['kept_share']*100:.1f}%  · 버린 칸 {res['dropped_cells']:,}")
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="tifxyz 폴더 또는 URL")
    ap.add_argument("--out", help="고친 조각을 쓸 폴더")
    ap.add_argument("--k", type=float, default=5.0, help="끊는 기준 (중앙값의 몇 배)")
    ap.add_argument("--min-frac", type=float, default=0.02, help="남길 최소 조각 비율")
    ap.add_argument("--json", help="결과를 JSON 으로")
    a = ap.parse_args()
    r = repair(a.src, a.out, a.k, a.min_frac)
    if a.json:
        json.dump(r, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
