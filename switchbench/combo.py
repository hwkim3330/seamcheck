"""거리 폭(3x3 안 O 최대-최소) + 표면 밝기(B) + 줄 길이 — v0 에서만 조정."""
import json, sys, itertools, numpy as np
from scipy import ndimage as ndi
sys.path.insert(0, '.')
import devscore, darkline
c = devscore._c
sub = {}
for e in c['events'] + c['negatives']: sub.setdefault(e['patch'], set()).add(e.get('subset'))
names = [n for n in json.load(open('patch_names.json')) if 'v0' in sub[n]]
D = {}
for n in names:
    z = np.load(f'feat2/{n}.npz'); b = np.load(f'feat/{n}.npz')
    O = np.where(z['v'], z['O'], np.nan); B = np.where(b['v'], b['B'], np.nan)
    R = ndi.maximum_filter(np.nan_to_num(O, nan=-99), 3); r2 = ndi.minimum_filter(np.nan_to_num(O, nan=99), 3)
    rng = np.where(z['v'], np.clip(R - r2, 0, 12), 0)
    Bs = ndi.median_filter(np.nan_to_num(B, nan=1), 3)
    P, _ = darkline.load(f'patches/{n}')
    D[n] = (rng, Bs, z['v'], P)
best = []
for R_, dark, L in itertools.product((10, 12), (0.6, 0.7, 0.8, 1.01), (3, 5, 8, 12)):
    al = {}
    for n, (rng, Bs, v, P) in D.items():
        m = v & (rng >= R_) & (Bs < dark)
        lab, k = ndi.label(m, np.ones((3, 3)))
        out = []
        if k:
            sl = ndi.find_objects(lab)
            for i, s in enumerate(sl, 1):
                ext = max(s[0].stop - s[0].start, s[1].stop - s[1].start)
                if ext >= L:
                    rc = np.argwhere(lab[s] == i) + [s[0].start, s[1].start]
                    out += [P[q[0], q[1]].tolist() for q in rc[::2]]
        al[n] = out
    sc = devscore.score(al, subset='v0')
    print(f"range>={R_} B<{dark} len>={L}: {sc['hits']}/{sc['events']}  FA {sc['fa100']:.2f}/100mm", flush=True)
