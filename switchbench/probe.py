"""가설 확인: 시트 전환 지점에서는 표면 위 CT 밝기가 꺼지는가?

패치마다 격자점의 법선을 구하고, 법선 방향 -16..+16 vx 밝기 단면을 읽는다.
  · on   : 표면 위 밝기(±1 vx 평균) / 패치 중앙값
  · off  : 단면에서 가장 밝은 곳이 표면에서 얼마나 떨어졌나(vx)
SwitchBench 사건 전이점(1 mm 안)과 확인된 무전환 구간 꼭짓점의 분포를 비교한다.
"""
import json, os, sys
import numpy as np, tifffile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ct

CORPUS = os.path.expanduser('~/scroll-audits/results/switchbench_natural_v1_events.json')
T = np.arange(-16, 17)


def load(n):
    X, Y, Z = (tifffile.imread(f'patches/{n}/{c}.tif').astype(np.float64) for c in 'xyz')
    P = np.stack([X, Y, Z], -1)
    v = (X > 0) & (Y > 0) & (Z > 0) & np.isfinite(P).all(-1)
    if os.path.exists(f'patches/{n}/mask.tif'):
        v &= tifffile.imread(f'patches/{n}/mask.tif') > 0
    return P, v


def normals(P, v):
    du = np.zeros_like(P); dv = np.zeros_like(P)
    du[:, 1:-1] = P[:, 2:] - P[:, :-2]; dv[1:-1] = P[2:] - P[:-2]
    N = np.cross(du, dv); L = np.linalg.norm(N, axis=-1, keepdims=True)
    return np.where(L > 0, N / np.maximum(L, 1e-9), 0)


def profiles(P, v, N, idx):
    pts = P[tuple(idx.T)][:, None, :] + N[tuple(idx.T)][:, None, :] * T[None, :, None]
    pts = pts.reshape(-1, 3)
    ct.prefetch(pts)
    return ct.sample(pts).reshape(len(idx), len(T))


if __name__ == '__main__':
    c = json.load(open(CORPUS))
    import tifffile as tf
    ev_p = {e['patch'] for e in c['events'] if e['status'] == 'confirmed'}
    ng_p = {g['patch'] for g in c['negatives'] if g['status'] == 'confirmed'}
    both = sorted(ev_p & ng_p, key=lambda n: tf.imread(f'patches/{n}/x.tif').size)
    names = both[:int(sys.argv[1]) if len(sys.argv) > 1 else 12]
    ev_on, ng_on, ev_off, ng_off = [], [], [], []
    for n in names:
        P, v = load(n); N = normals(P, v)
        idx = np.argwhere(v)
        prof = profiles(P, v, N, idx)
        med = np.median(prof[:, 15:18].mean(1))
        on = prof[:, 15:18].mean(1) / max(med, 1)
        off = np.abs(T[np.argmax(prof, 1)])
        rc = {tuple(r): i for i, r in enumerate(map(tuple, idx))}
        evs = [e for e in c['events'] if e['patch'] == n and e['status'] == 'confirmed']
        for e in evs:
            for t in e['transitions']:
                a, b = np.array(t['rc_a']), np.array(t['rc_b'])
                # 전이 구간 사이 + 양끝 2칸
                steps = max(abs(b - a).max(), 1)
                cells = {tuple(np.round(a + (b - a) * s / steps).astype(int)) for s in range(steps + 1)}
                vals = [on[rc[q]] for q in cells if q in rc]
                if vals: ev_on.append(min(vals)); ev_off.append(max(off[rc[q]] for q in cells if q in rc))
        for g in (x for x in c['negatives'] if x['patch'] == n and x['status'] == 'confirmed'):
            a, b = np.array(g['rc0']), np.array(g['rc1']); steps = max(abs(b - a).max(), 1)
            for s in range(0, steps + 1, 3):
                q = tuple(np.round(a + (b - a) * s / steps).astype(int))
                if q in rc: ng_on.append(on[rc[q]]); ng_off.append(off[rc[q]])
        print(n[:40], 'events', len(evs), 'neg samples so far', len(ng_on), flush=True)
    ev_on, ng_on = np.array(ev_on), np.array(ng_on)
    print('\n표면 위 밝기 / 패치 중앙값 (사건 전이 구간의 최솟값 vs 무전환 꼭짓점)')
    for q in (10, 25, 50, 75, 90):
        print(f'  p{q:<3} 사건 {np.percentile(ev_on, q):.2f}   무전환 {np.percentile(ng_on, q):.2f}')
    for th in (0.5, 0.6, 0.7, 0.8):
        print(f'  < {th}: 사건 {np.mean(ev_on < th):.0%}  무전환 꼭짓점 {np.mean(ng_on < th):.1%}')
