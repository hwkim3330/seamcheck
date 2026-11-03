#!/usr/bin/env python3
"""v14 이음새 구간을 CT로 렌더링한다 — 수리 전후, 펼친 면과 단면.

tifxyz 격자는 이미 펼친 좌표라서 평탄화 계산이 따로 필요 없다. 격자를 4배로 촘촘히 보간하고, 점마다 표면
법선 방향으로 앞뒤 몇 겹의 CT 밝기를 읽어 한 장의 이미지로 만든다. CT 는 PHercParis4 20260411134726
레벨 2 (9.6 um/vx). tifxyz 좌표는 같은 볼륨의 레벨 0 (2.4 um) 이라 4 로 나눈다.

사용:  python render/render_seam.py P.npy valid.npy clean.npy --rows 300 640 --out render/
"""
import argparse, os, sys, time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "switchbench"))
import ct  # noqa: E402

UP = 4                  # 격자 한 칸(레벨 0 에서 20 복셀 = 레벨 2 에서 5 복셀)을 4 등분
LAYERS = np.arange(-6, 7)   # 법선 방향 오프셋, 레벨 2 복셀


def upsample(P, valid):
    """격자를 UP 배로 쌍선형 보간. 네 모서리가 모두 유효한 칸만."""
    H, W = valid.shape
    t = np.arange(UP) / UP
    a, b = np.meshgrid(t, t, indexing="ij")
    out = np.full(((H - 1) * UP, (W - 1) * UP, 3), np.nan, np.float32)
    ok = valid[:-1, :-1] & valid[1:, :-1] & valid[:-1, 1:] & valid[1:, 1:]
    for i in range(UP):
        for j in range(UP):
            u, v = a[i, j], b[i, j]
            q = (P[:-1, :-1] * (1 - u) * (1 - v) + P[1:, :-1] * u * (1 - v)
                 + P[:-1, 1:] * (1 - u) * v + P[1:, 1:] * u * v)
            q[~ok] = np.nan
            out[i::UP, j::UP] = q
    return out


def normals(Q):
    du = np.gradient(Q, axis=0); dv = np.gradient(Q, axis=1)
    n = np.cross(du, dv)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
    return n


def sample(xyz):
    """(N,3) 레벨 2 x,y,z 의 삼선형 보간. 조각 번호를 정수 하나로 묶어 한 번만 정렬한다."""
    C = ct.C
    zyx = xyz[:, ::-1].astype(np.float64)
    f = np.floor(zyx).astype(np.int64); w = zyx - f
    out = np.zeros(len(xyz), np.float32)
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                q = f + (dz, dy, dx)
                wt = ((w[:, 0] if dz else 1 - w[:, 0]) * (w[:, 1] if dy else 1 - w[:, 1])
                      * (w[:, 2] if dx else 1 - w[:, 2]))
                kk = q // C; ll = q % C
                code = (kk[:, 0] << 40) | (kk[:, 1] << 20) | kk[:, 2]
                order = np.argsort(code, kind="stable")
                cs = code[order]
                cuts = np.flatnonzero(np.diff(cs)) + 1
                vals = np.empty(len(xyz), np.float32)
                for s, e in zip(np.r_[0, cuts], np.r_[cuts, len(cs)]):
                    idx = order[s:e]
                    k = tuple(kk[idx[0]])
                    a = ct.load_chunk(k)
                    vals[idx] = a[ll[idx, 0], ll[idx, 1], ll[idx, 2]]
                out += (wt * vals).astype(np.float32)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("P"); ap.add_argument("valid"); ap.add_argument("clean")
    ap.add_argument("--rows", type=int, nargs=2, default=(300, 640))
    ap.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--fetch-only", action="store_true")
    a = ap.parse_args()
    r0, r1 = a.rows
    P = np.load(a.P)[r0:r1].astype(np.float64) / 4.0
    valid = np.load(a.valid)[r0:r1]
    clean = np.load(a.clean)[r0:r1]
    Q = upsample(P, valid)
    N = normals(Q)
    good = np.isfinite(Q[..., 0]) & np.isfinite(N[..., 0])
    pts, nrm = Q[good], N[good]
    print(f"rows {r0}-{r1}: render {Q.shape[0]}x{Q.shape[1]}, {good.sum():,} points, {len(LAYERS)} layers", flush=True)

    t = time.time()
    allp = np.concatenate([pts + nrm * LAYERS.min(), pts + nrm * LAYERS.max(), pts])
    nk, todo = ct.prefetch(allp, workers=64)
    print(f"chunks {nk:,} ({todo:,} new) fetched in {time.time() - t:.0f}s", flush=True)
    if a.fetch_only:
        return

    t = time.time()
    stack = np.zeros((len(LAYERS),) + Q.shape[:2], np.float32)
    for i, o in enumerate(LAYERS):
        img = np.zeros(Q.shape[:2], np.float32)
        img[good] = sample(pts + nrm * o)
        stack[i] = img
        print(f"  layer {o:+d} {time.time() - t:.0f}s", flush=True)
    os.makedirs(a.out, exist_ok=True)
    np.save(os.path.join(a.out, f"stack_{r0}_{r1}.npy"), stack)
    # 원래 격자 칸 -> 렌더 픽셀 마스크 (수리 후 남은 칸)
    keep = np.repeat(np.repeat(clean[:-1, :-1] & clean[1:, :-1] & clean[:-1, 1:] & clean[1:, 1:], UP, 0), UP, 1)
    np.save(os.path.join(a.out, f"keep_{r0}_{r1}.npy"), keep)
    np.save(os.path.join(a.out, f"good_{r0}_{r1}.npy"), good)
    print("saved", flush=True)


if __name__ == "__main__":
    main()
