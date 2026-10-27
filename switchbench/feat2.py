"""패치마다 법선 단면(-8..+8)에서 두 지도를 만든다.
  C: 장 위에 있는 정도 = I(0±1) - max(평균 I(-7..-5), 평균 I(+5..+7)), 패치 중앙값 I(0)으로 나눔
  O: ±6 안에서 가장 밝은 곳의 부호 있는 거리(vx)
"""
import json, os, sys, time
import numpy as np
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ct, darkline
T = np.arange(-8, 9)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feat2')


def compute(n):
    f = f'{OUT}/{n}.npz'
    if os.path.exists(f): return
    P, v = darkline.load(f'patches/{n}'); N = darkline.normals(P)
    idx = np.argwhere(v)
    pts = (P[tuple(idx.T)][:, None] + N[tuple(idx.T)][:, None] * T[None, :, None]).reshape(-1, 3)
    ct.prefetch(pts)
    pr = ndi.gaussian_filter1d(ct.sample(pts).reshape(len(idx), len(T)).astype(np.float64), 1.0, axis=1)
    on = pr[:, 7:10].mean(1)
    side = np.maximum(pr[:, 1:4].mean(1), pr[:, 13:16].mean(1))
    med = max(np.median(on), 1)
    C = np.full(v.shape, np.nan, np.float32); O = np.full(v.shape, np.nan, np.float32)
    C[tuple(idx.T)] = (on - side) / med
    w = pr[:, 2:15]                      # -6..+6
    O[tuple(idx.T)] = np.arange(-6, 7)[np.argmax(w, 1)]
    np.savez_compressed(f, C=C, O=O, v=v)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    c = json.load(open(os.path.expanduser('~/scroll-audits/results/switchbench_natural_v1_events.json')))
    sub = {}
    for e in c['events'] + c['negatives']: sub.setdefault(e['patch'], set()).add(e.get('subset'))
    names = [n for n in json.load(open('patch_names.json')) if ('v0' if 'v0' in sub[n] else 'new') == sys.argv[1]]
    t = time.time()
    for i, n in enumerate(names, 1):
        compute(n)
        if i % 20 == 0: print(f'{i}/{len(names)} {time.time()-t:.0f}s', flush=True)
    print('done')
