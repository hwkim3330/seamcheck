"""darkline — CT 로 매끄러운 시트 전환을 찾는다.

자동으로 자란 표면이 옆 감김으로 서서히 넘어갈 때, 격자는 고르게 이어져서 거리 기반 검사(seamcheck,
windcheck)로는 보이지 않는다(SwitchBench 사건 24곳에서 이웃 간격이 중앙값의 1.0~1.44배).
대신 표면이 한 장을 떠나 다음 장에 닿기 전, 장과 장 사이의 어두운 틈을 지나간다.
그래서 표면 위 CT 밝기가 '줄'로 꺼진다.

  1. 격자점마다 법선 방향 ±1 vx 밝기를 읽는다(레벨 2, 9.6 um). 패치 중앙값으로 나눈다.
  2. 행·열을 따라, 양쪽이 밝은데 가운데가 짧게 어두운 곳(골)을 찾는다.
  3. 골들이 이어져 일정 길이 이상의 줄을 이룰 때만 경보를 낸다 — 점 하나짜리 잡음은 버린다.

사람 검증 표면이나 정답 표시는 쓰지 않는다. 입력은 패치(x/y/z.tif, mask.tif)와 공개 CT 볼륨뿐.
"""
import os, sys
import numpy as np, tifffile
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ct

FEAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feat')


def load(pdir):
    X, Y, Z = (tifffile.imread(f'{pdir}/{c}.tif').astype(np.float64) for c in 'xyz')
    P = np.stack([X, Y, Z], -1)
    v = (X > 0) & (Y > 0) & (Z > 0) & np.isfinite(P).all(-1)
    if os.path.exists(f'{pdir}/mask.tif'):
        v &= tifffile.imread(f'{pdir}/mask.tif') > 0
    return P, v


def normals(P):
    du = np.zeros_like(P); dv = np.zeros_like(P)
    du[:, 1:-1] = P[:, 2:] - P[:, :-2]; du[:, 0] = P[:, 1] - P[:, 0]; du[:, -1] = P[:, -1] - P[:, -2]
    dv[1:-1] = P[2:] - P[:-2]; dv[0] = P[1] - P[0]; dv[-1] = P[-1] - P[-2]
    N = np.cross(du, dv); L = np.linalg.norm(N, axis=-1, keepdims=True)
    return N / np.maximum(L, 1e-9)


def brightness(pdir, name):
    """격자 모양의 표면 위 밝기 지도 (패치 중앙값 = 1). 계산해 둔 게 있으면 읽는다."""
    os.makedirs(FEAT, exist_ok=True)
    f = f'{FEAT}/{name}.npz'
    if os.path.exists(f):
        z = np.load(f); return z['B'], z['v']
    P, v = load(pdir); N = normals(P)
    idx = np.argwhere(v)
    t = np.array([-1.0, 0.0, 1.0])
    pts = (P[tuple(idx.T)][:, None, :] + N[tuple(idx.T)][:, None, :] * t[None, :, None]).reshape(-1, 3)
    ct.prefetch(pts)
    s = ct.sample(pts).reshape(len(idx), 3).mean(1)
    B = np.full(v.shape, np.nan, np.float32)
    B[tuple(idx.T)] = s
    med = np.nanmedian(B)
    B = B / max(med, 1.0)
    np.savez_compressed(f, B=B, v=v)
    return B, v


def dips(B, v, dark, bright, maxw, side):
    """행·열 방향으로 '양쪽 밝음 - 가운데 짧게 어두움'인 칸 표시."""
    H, W = B.shape
    D = np.zeros((H, W), bool)
    Bf = np.where(v, B, np.nan)
    for arr, out in ((Bf, D), (Bf.T, D.T)):
        for r in range(arr.shape[0]):
            row = arr[r]
            d = row < dark
            i = 0; n = len(row)
            while i < n:
                if not d[i]: i += 1; continue
                j = i
                while j < n and d[j]: j += 1
                if j - i <= maxw:
                    L = row[max(0, i - side):i]; R = row[j:j + side]
                    if len(L) and len(R) and np.nanmax(L) > bright and np.nanmax(R) > bright:
                        out[r, i:j] = True
                i = j
    return D


def detect(pdir, name, dark=0.55, bright=0.85, maxw=4, side=4, min_len=4, step=2):
    """경보 좌표 (x, y, z) 목록."""
    B, v = brightness(pdir, name)
    Bs = ndi.median_filter(np.nan_to_num(B, nan=1.0), size=3)
    Bs[~v] = np.nan
    D = dips(Bs, v, dark, bright, maxw, side)
    lab, k = ndi.label(D, structure=np.ones((3, 3)))
    P, _ = load(pdir)
    alarms = []
    for c in range(1, k + 1):
        rc = np.argwhere(lab == c)
        ext = max(np.ptp(rc[:, 0]), np.ptp(rc[:, 1])) + 1     # 줄 길이(격자 칸)
        if ext < min_len: continue
        for q in rc[::step]:
            alarms.append(P[q[0], q[1]].tolist())
    return alarms
