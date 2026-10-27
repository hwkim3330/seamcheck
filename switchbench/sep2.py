import json, sys, numpy as np
sys.path.insert(0, '.')
import devscore
c = devscore._c
ev = [e for e in c['events'] if e['status'] == 'confirmed' and e['subset'] == 'v0']
ng = [g for g in c['negatives'] if g['status'] == 'confirmed' and g.get('subset') == 'v0']
F = {}
def f(n):
    if n not in F: z = np.load(f'feat2/{n}.npz'); F[n] = (z['C'], z['O'], z['v'])
    return F[n]
eC, eJ, nC, nJ = [], [], [], []
for e in ev:
    C, O, v = f(e['patch'])
    best_c, best_j = 9, 0
    for t in e['transitions']:
        a, b = np.array(t['rc_a']), np.array(t['rc_b']); d = np.sign(b - a)
        seg = [tuple(a + d * s) for s in range(-2, abs(b - a).max() + 3)]
        seg = [q for q in seg if 0 <= q[0] < v.shape[0] and 0 <= q[1] < v.shape[1] and v[q]]
        if len(seg) < 2: continue
        cs = [C[q] for q in seg]; os_ = [O[q] for q in seg]
        best_c = min(best_c, min(cs)); best_j = max(best_j, max(os_) - min(os_))
    eC.append(best_c); eJ.append(best_j)
for g in ng:
    C, O, v = f(g['patch'])
    vs = devscore.run_vertices(g)
    for i in range(0, len(vs) - 6, 6):
        seg = [q for q in vs[i:i + 6] if v[q]]
        if len(seg) < 2: continue
        nC.append(min(C[q] for q in seg)); nJ.append(max(O[q] for q in seg) - min(O[q] for q in seg))
eC, eJ, nC, nJ = map(np.array, (eC, eJ, nC, nJ))
print('구간 최소 C (장 위에 있는 정도): 사건 vs 정상 6칸 구간')
for q in (10, 25, 50, 75): print(f'  p{q} {np.percentile(eC,q):+.2f}  {np.percentile(nC,q):+.2f}')
for th in (-0.05, 0.0, 0.05): print(f'  C<{th}: 사건 {np.mean(eC<th):.0%}  정상 {np.mean(nC<th):.1%}')
print('구간 안 O 폭 (최대-최소): 사건 vs 정상')
for th in (6, 8, 10, 12): print(f'  >= {th}: 사건 {np.mean(eJ>=th):.0%}  정상 {np.mean(nJ>=th):.1%}')
both = lambda C_, J_: np.mean((C_ < 0.0) & (J_ >= 10))
print(f'C<0 & 폭>=10: 사건 {both(eC,eJ):.0%}  정상 {both(nC,nJ):.1%}')
