"""ctswitch — SwitchBench 제출용. 설정은 v0 부분집합에서만 고른 값으로 고정(combo.py 의 가장 엄격한 점).

격자점마다 레벨-2 CT(9.6 um)를 법선 방향으로 읽어
  B   = 표면 위(±1 vx) 밝기 / 패치 중앙값            (feat_all.py → feat/)
  O   = ±6 vx 안에서 가장 밝은 곳의 부호 있는 거리   (feat2.py → feat2/)
  rng = 3x3 이웃 안 O 의 최대 - 최소
rng >= 10 이고 B(3x3 중앙값) < 0.6 인 칸들이 8-연결로 12칸 이상 이어진 덩어리를 경보로 낸다(두 칸마다 한 점).
입력은 패치와 공개 CT 뿐. 사람 검증 표면·정답 표시는 쓰지 않는다.

    python ctswitch.py alarms_ctswitch.json
"""
import json, sys
import numpy as np
from scipy import ndimage as ndi
sys.path.insert(0, '.')
import darkline

RANGE, DARK, MIN_LEN = 10, 0.6, 12

names = json.load(open('patch_names.json'))
out = {}
for n in names:
    z = np.load(f'feat2/{n}.npz'); b = np.load(f'feat/{n}.npz')
    v = z['v']
    O = np.where(v, z['O'], np.nan); B = np.where(b['v'], b['B'], np.nan)
    hi = ndi.maximum_filter(np.nan_to_num(O, nan=-99), 3); lo = ndi.minimum_filter(np.nan_to_num(O, nan=99), 3)
    rng = np.where(v, np.clip(hi - lo, 0, 12), 0)
    Bs = ndi.median_filter(np.nan_to_num(B, nan=1), 3)
    m = v & (rng >= RANGE) & (Bs < DARK)
    lab, k = ndi.label(m, np.ones((3, 3)))
    P, _ = darkline.load(f'patches/{n}')
    al = []
    for i, s in enumerate(ndi.find_objects(lab) if k else [], 1):
        if max(s[0].stop - s[0].start, s[1].stop - s[1].start) >= MIN_LEN:
            rc = np.argwhere(lab[s] == i) + [s[0].start, s[1].start]
            al += [[round(float(c), 2) for c in P[q[0], q[1]]] for q in rc[::2]]
    out[n] = al
json.dump({"detector": "ctswitch (seamcheck/switchbench, CT 9.6 um, v0-frozen)", "format": "xyz", "alarms": out},
          open(sys.argv[1], 'w'))
print('patches', len(out), 'with alarms', sum(1 for a in out.values() if a), 'alarms', sum(len(a) for a in out.values()))
