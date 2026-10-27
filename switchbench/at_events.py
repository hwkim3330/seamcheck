"""SwitchBench 이벤트 지점에서 seamcheck 기준(이웃 간격 / 패치 중앙값)이 얼마인지 잰다."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from seamcheck import load_xyz, check, verdict, neighbour_steps

E = json.load(open(os.path.expanduser('~/scroll-audits/results/switchbench_natural_v1_leaderboard/corpus_events.json')))
by = {}
for e in E['events']: by.setdefault(e['patch'], []).append(e)
rows = []
for n in sorted(os.listdir('switchbench/patches')):
    P, valid = load_xyz(f'switchbench/patches/{n}')
    r = check(P, valid); v = verdict(r)
    H, W = valid.shape; S = np.zeros((H, W))
    for ax in (0, 1):
        d, m = neighbour_steps(P, valid, ax); d = np.where(m, d, 0)
        if ax == 0: S[:-1] = np.maximum(S[:-1], d); S[1:] = np.maximum(S[1:], d)
        else: S[:, :-1] = np.maximum(S[:, :-1], d); S[:, 1:] = np.maximum(S[:, 1:], d)
    med = r['median_step']; flat = P[valid]; idx = np.argwhere(valid)
    print(f"{n[:40]:42} {H}x{W} cov {r['coverage']:.2f} verdict {v:6} max ratio {r['ratio']:.1f}")
    for e in by.get(n, []):
        pts = np.array(e['points'])
        dmin = np.min(np.linalg.norm(flat[:, None, :] - pts[None, :, :], axis=2), axis=1)
        near = dmin < 104                      # 1 mm
        if not near.any(): print('   event: no grid cell within 1 mm', e['xyz']); continue
        loc = S[tuple(idx[near].T)] / med
        rows.append(loc.max())
        print(f"   event {e['xyz']}: cells {near.sum():5d}  max step {loc.max():.2f}x  p95 {np.percentile(loc,95):.2f}x")
print('events measured', len(rows), 'max-step ratio at events: median %.2f, max %.2f' % (np.median(rows), np.max(rows)))
