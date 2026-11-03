"""coh 가 SwitchBench 사건 자리에서 높아지는지 — v0(조정용) 부분집합에서만 본다."""
import json, os, sys
import numpy as np
sys.path.insert(0, '.')
import devscore as D

sub = sys.argv[1] if len(sys.argv) > 1 else 'v0'
c = D._c
def coh(n):
    f = f'feat3/{n}.npz'
    if not os.path.exists(f): return None
    z = np.load(f); return z['coh']

def near(C, rc, r=2):
    r0, c0 = rc
    w = C[max(0, r0 - r):r0 + r + 1, max(0, c0 - r):c0 + r + 1]
    w = w[np.isfinite(w)]
    return float(w.max()) if w.size else np.nan

ev, ng = [], []
for e in c['events']:
    if e['status'] != 'confirmed' or e['subset'] != sub: continue
    C = coh(e['patch'])
    if C is None: continue
    vals = [near(C, tuple(np.round((np.array(t['rc_a']) + t['rc_b']) / 2).astype(int))) for t in e['transitions']]
    ev.append(np.nanmax(vals) if np.isfinite(vals).any() else np.nan)
for g in c['negatives']:
    if g['status'] != 'confirmed' or g.get('subset') != sub: continue
    C = coh(g['patch'])
    if C is None: continue
    ng += [near(C, v, 2) for v in D.run_vertices(g)]
ev, ng = np.array(ev), np.array(ng)
ev, ng = ev[np.isfinite(ev)], ng[np.isfinite(ng)]
print(f'{sub}: events {len(ev)}  negative vertices {len(ng)}')
print('event coh (max within 2 cells) pct 25/50/75:', np.percentile(ev, [25, 50, 75]).round(2))
print('negative vertex coh pct 50/90/99:', np.percentile(ng, [50, 90, 99]).round(2))
for t in (0.5, 0.6, 0.7):
    print(f'  thr {t}: events >= {np.mean(ev >= t):.2f}   negatives >= {np.mean(ng >= t):.3f}')
