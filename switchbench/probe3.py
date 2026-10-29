"""서서히 넘어가는 전환: 수직 방향 어긋남을 여러 칸에 걸쳐 쌓으면 보이는가 (모양만, CT 없음).
각 칸에서 '크게 매끄럽게 만든 표면'과의 법선 방향 차이 h 를 구하고, 전이 구간 양끝 바깥 k 칸의 h 차이를 본다."""
import json, sys, numpy as np
from scipy import ndimage as ndi
sys.path.insert(0, '.')
import devscore, darkline
c = devscore._c
ev = [e for e in c['events'] if e['status'] == 'confirmed' and e['subset'] == 'v0']
ng = [g for g in c['negatives'] if g['status'] == 'confirmed' and g.get('subset') == 'v0']
H = {}
def hmap(n, sig=6):
    if (n, sig) in H: return H[(n, sig)]
    P, v = darkline.load(f'patches/{n}'); N = darkline.normals(P)
    w = v.astype(float); Ps = np.zeros_like(P)
    for k in range(3):
        Ps[..., k] = ndi.gaussian_filter(np.where(v, P[..., k], 0), sig) / np.maximum(ndi.gaussian_filter(w, sig), 1e-6)
    h = np.where(v, ((P - Ps) * N).sum(-1), np.nan)
    H[(n, sig)] = (h, v); return h, v
for sig in (4, 8, 16):
    eJ, nJ = [], []
    for e in ev:
        h, v = hmap(e['patch'], sig); best = 0
        for t in e['transitions']:
            a, b = np.array(t['rc_a']), np.array(t['rc_b']); d = np.sign(b - a)
            for k in (2, 4):
                qa, qb = tuple(a - d * k), tuple(b + d * k)
                if all(0 <= q[i] < v.shape[i] for q in (qa, qb) for i in (0, 1)) and v[qa] and v[qb]:
                    best = max(best, abs(h[qb] - h[qa]))
        eJ.append(best)
    for g in ng:
        h, v = hmap(g['patch'], sig); vs = devscore.run_vertices(g)
        for i in range(0, len(vs) - 10, 10):
            qa, qb = vs[i], vs[i + 8]
            if v[qa] and v[qb]: nJ.append(abs(h[qb] - h[qa]))
    eJ, nJ = np.array(eJ), np.array(nJ)
    print(f'매끄럽게 sigma={sig}칸: 전환 중앙값 {np.median(eJ):.1f}vx, 정상 중앙값 {np.median(nJ):.1f}vx | ' +
          '  '.join(f'>={t}: {np.mean(eJ>=t):.0%}/{np.mean(nJ>=t):.1%}' for t in (4, 6, 8, 12)))
