"""전환 지점에서 '가장 가까운 장까지의 부호 있는 거리'가 뒤집히는가."""
import json, os, sys
import numpy as np
sys.path.insert(0, '.')
import ct, darkline, devscore
from scipy import ndimage as ndi
c = devscore._c
T = np.arange(-16, 17)
ev = [e for e in c['events'] if e['status'] == 'confirmed' and e['subset'] == 'v0']
pat = sorted({e['patch'] for e in ev})[:20]
spac = []
for n in pat:
    P, v = darkline.load(f'patches/{n}'); N = darkline.normals(P)
    idx = np.argwhere(v)
    pts = (P[tuple(idx.T)][:, None] + N[tuple(idx.T)][:, None] * T[None, :, None]).reshape(-1, 3)
    ct.prefetch(pts); pr = ct.sample(pts).reshape(len(idx), len(T))
    pr = ndi.gaussian_filter1d(pr, 1.5, axis=1)
    # 자기상관으로 장 간격
    z = pr - pr.mean(1, keepdims=True)
    ac = np.array([np.mean(z[:, :len(T) - k] * z[:, k:]) for k in range(1, 16)])
    k = 1 + np.argmax(ac[3:]) + 3; spac.append(k)
    O = np.full(v.shape, np.nan); O[tuple(idx.T)] = T[np.argmax(pr, 1)]
    rc = {tuple(r): i for i, r in enumerate(map(tuple, idx))}
    for e in [e for e in ev if e['patch'] == n]:
        for t in e['transitions']:
            a, b = np.array(t['rc_a']), np.array(t['rc_b']); d = np.sign(b - a)
            line = [tuple(a - d * s) for s in range(4, 0, -1)] + [tuple(a)] + [tuple(b)] + [tuple(b + d * s) for s in range(1, 5)]
            print(n[-30:], 'delta', e['delta_signs'], 'spacing', k, ' O:', ' '.join(f"{O[q]:+3.0f}" if q in rc else '  .' for q in line))
print('장 간격(vx) 중앙값', np.median(spac))
