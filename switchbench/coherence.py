"""층 일관성 — 표면이 장을 따라가는지, 장을 비스듬히 뚫고 지나가는지 CT 로 가른다.

표면이 한 장 위에 있으면 법선 방향으로 2 복셀만 움직여도 보이는 무늬(섬유)가 바뀐다. 장 두께 안에서 위아래로
섬유층이 다르고, 조금 더 가면 장 사이 틈이 나오기 때문이다. 표면이 장을 비스듬히 가로지르면 펼친 면에 등고선
같은 고리 무늬가 나오고, 2 복셀 옮겨도 그 무늬가 거의 그대로 옆으로만 밀린다.

  coh = (corr(층 0, 층 -2) + corr(층 0, 층 +2)) / 2, 국소 창 안의 정규화 상관

v14 이음새 구간(9.6 um, 격자 칸 1개 = 1.25 vx/픽셀로 보간)에서 중앙값:
  제대로 추적된 섬유 구간 0.27 / 0.31, seamcheck 가 도려낸 칸 0.76, 같은 표면의 깃발 없는 고리 구간 0.71.

패치(격자 칸 = 20 vx)는 UP 배로 보간해 2.5 vx/픽셀로 렌더링하고, 칸마다 coh 를 평균해 격자 지도로 저장한다.
    python coherence.py            # feat3/<패치>.npz (coh, v)
"""
import json, os, sys, time
import numpy as np
from scipy.ndimage import uniform_filter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ct, darkline

HERE = os.path.dirname(os.path.abspath(__file__))
FEAT = os.path.join(HERE, 'feat3')
OFF = 2.0


def upsample(P, v, up):
    H, W = v.shape
    t = np.arange(up) / up
    out = np.full(((H - 1) * up, (W - 1) * up, 3), np.nan)
    ok = v[:-1, :-1] & v[1:, :-1] & v[:-1, 1:] & v[1:, 1:]
    for i, a in enumerate(t):
        for j, b in enumerate(t):
            q = (P[:-1, :-1] * (1 - a) * (1 - b) + P[1:, :-1] * a * (1 - b)
                 + P[:-1, 1:] * (1 - a) * b + P[1:, 1:] * a * b)
            q[~ok] = np.nan
            out[i::up, j::up] = q
    return out, ok


def lcorr(a, b, w):
    ma, mb = uniform_filter(a, w), uniform_filter(b, w)
    va = uniform_filter(a * a, w) - ma * ma; vb = uniform_filter(b * b, w) - mb * mb
    return (uniform_filter(a * b, w) - ma * mb) / np.sqrt(np.maximum(va * vb, 1e-6))


def coherence_map(P, v, up, win):
    """격자 (H, W) 의 coh 지도와 렌더 픽셀 단위 지도."""
    Q, ok = upsample(P, v, up)
    du = np.gradient(Q, axis=0); dv = np.gradient(Q, axis=1)
    N = np.cross(du, dv); N /= np.linalg.norm(N, axis=-1, keepdims=True) + 1e-9
    g = np.isfinite(Q[..., 0]) & np.isfinite(N[..., 0])
    p, n = Q[g], N[g]
    L = []
    for o in (-OFF, 0.0, OFF):
        img = np.zeros(Q.shape[:2], np.float32)
        img[g] = ct.sample(p + n * o)
        L.append(img)
    nz = g & (L[0] > 0) & (L[1] > 0) & (L[2] > 0)       # 0 = 마스크 밖
    c = (lcorr(L[1], L[0], win) + lcorr(L[1], L[2], win)) / 2
    c = np.where(nz, c, np.nan)
    H, W = v.shape
    cell = np.full((H, W), np.nan, np.float32)
    blk = c.reshape(H - 1, up, W - 1, up)
    with np.errstate(all='ignore'):
        m = np.nanmean(blk, axis=(1, 3))
    cell[:-1, :-1] = np.where(ok, m, np.nan)
    return cell, c


def run(name, up=8, win=15):
    os.makedirs(FEAT, exist_ok=True)
    f = f'{FEAT}/{name}.npz'
    if os.path.exists(f):
        return
    P, v = darkline.load(f'{HERE}/patches/{name}')
    cell, _ = coherence_map(P, v, up, win)
    np.savez_compressed(f, coh=cell, v=v)


if __name__ == '__main__':
    names = json.load(open(f'{HERE}/patch_names.json'))
    t = time.time()
    for i, n in enumerate(names, 1):
        run(n)
        if i % 20 == 0: print(f'{i}/{len(names)} {time.time() - t:.0f}s', flush=True)
    print('done', flush=True)
