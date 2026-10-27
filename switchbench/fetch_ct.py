"""SwitchBench 패치 표면이 걸치는 CT 조각을 미리 받는다.  python fetch_ct.py v0|new"""
import json, os, sys, time
import numpy as np, tifffile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ct

which = sys.argv[1]
c = json.load(open(os.path.expanduser('~/scroll-audits/results/switchbench_natural_v1_events.json')))
sub = {}
for e in c['events'] + c['negatives']: sub.setdefault(e['patch'], set()).add(e.get('subset'))
names = [n for n in json.load(open('patch_names.json')) if ('v0' if 'v0' in sub[n] else 'new') == which]
keys = set()
for n in names:
    X, Y, Z = (tifffile.imread(f'patches/{n}/{k}.tif') for k in 'xyz')
    v = (X > 0) & (Y > 0) & (Z > 0)
    P = np.stack([Z[v], Y[v], X[v]], 1)          # 조각 키는 (z, y, x)
    for d in (-16, 0, 16):
        keys.update(map(tuple, np.unique(((P + d) // 128).astype(int), axis=0)))
todo = [k for k in keys if not os.path.exists(ct.chunk_path(k))]
print(f'{which}: patches {len(names)} chunks {len(keys)} todo {len(todo)}', flush=True)
import concurrent.futures as cf
t = time.time()
with cf.ThreadPoolExecutor(48) as ex:
    for i, _ in enumerate(ex.map(ct.fetch_chunk, todo), 1):
        if i % 1000 == 0:
            print(f'  {i}/{len(todo)}  {i * 2 / 1024 / ((time.time() - t) / 60):.1f} GB/min', flush=True)
print('done', flush=True)
