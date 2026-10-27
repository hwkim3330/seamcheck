"""개발용 채점 — SwitchBench 키트 README 의 규칙을 그대로 옮긴 것(공식 수치는 키트로 다시 낸다).

  · 맞힘: 확인된 사건의 전이점(rc_a·rc_b 중점) 또는 중심에서 1 mm 안에 그 패치 경보가 있으면
  · 오경보: 경보를 0.5 mm 로 중복 제거 → 확인된 무전환 구간 꼭짓점 1 mm 안이면 1회
            (단, 그 패치의 어떤 후보 사건이든 1 mm 안이면 세지 않음). 구간마다 따로 센다. /100 mm
"""
import json, os
import numpy as np, tifffile

VX = 104.16666666666667      # 1 mm
CORPUS = os.path.expanduser('~/scroll-audits/results/switchbench_natural_v1_events.json')
_c = json.load(open(CORPUS))


def grid(n):
    X, Y, Z = (tifffile.imread(f'patches/{n}/{k}.tif').astype(np.float64) for k in 'xyz')
    return np.stack([X, Y, Z], -1)


def event_points(e, G):
    pts = []
    for t in e['transitions']:
        a, b = G[tuple(t['rc_a'])], G[tuple(t['rc_b'])]
        pts.append((a + b) / 2)
    pts.append(np.mean(pts, 0))
    return np.array(pts)


def run_vertices(g):
    a, b = np.array(g['rc0']), np.array(g['rc1']); s = max(abs(b - a).max(), 1)
    return [tuple(np.round(a + (b - a) * i / s).astype(int)) for i in range(s + 1)]


def score(alarms, subset=None, patches=None):
    ev = [e for e in _c['events'] if e['status'] == 'confirmed' and (subset is None or e['subset'] == subset)]
    ng = [g for g in _c['negatives'] if g['status'] == 'confirmed' and (subset is None or g.get('subset') == subset)]
    if patches is not None:
        ev = [e for e in ev if e['patch'] in patches]; ng = [g for g in ng if g['patch'] in patches]
    G = {}
    hits = 0; per = []
    for e in ev:
        n = e['patch']; A = np.array(alarms.get(n) or [], float).reshape(-1, 3)
        G.setdefault(n, grid(n))
        pts = event_points(e, G[n])
        h = len(A) and np.min(np.linalg.norm(A[:, None] - pts[None], axis=2)) <= VX
        hits += bool(h); per.append((n, bool(h)))
    fa = 0; mm = 0.0
    cand = {}
    for e in _c['events']:
        if e['patch'] in G or True:
            cand.setdefault(e['patch'], []).append(e)
    for g in ng:
        n = g['patch']; mm += g['len_mm']
        A = np.array(alarms.get(n) or [], float).reshape(-1, 3)
        if not len(A): continue
        keep = []
        for a in A:
            if all(np.linalg.norm(a - k) > 0.5 * VX for k in keep): keep.append(a)
        A = np.array(keep)
        G.setdefault(n, grid(n))
        cp = np.concatenate([event_points(e, G[n]) for e in cand.get(n, [])]) if cand.get(n) else np.zeros((0, 3))
        V = np.array([G[n][q] for q in run_vertices(g)])
        for a in A:
            if np.min(np.linalg.norm(V - a, axis=1)) <= VX and (not len(cp) or np.min(np.linalg.norm(cp - a, axis=1)) > VX):
                fa += 1
    return dict(hits=hits, events=len(ev), recall=hits / max(len(ev), 1), fa=fa, mm=mm,
                fa100=100 * fa / max(mm, 1e-9), per=per)
