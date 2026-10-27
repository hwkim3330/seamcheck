"""패치마다 밝기 지도를 계산해 둔다.  python feat_all.py v0|new"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import darkline
c = json.load(open(os.path.expanduser('~/scroll-audits/results/switchbench_natural_v1_events.json')))
sub = {}
for e in c['events'] + c['negatives']: sub.setdefault(e['patch'], set()).add(e.get('subset'))
names = [n for n in json.load(open('patch_names.json')) if ('v0' if 'v0' in sub[n] else 'new') == sys.argv[1]]
t = time.time()
for i, n in enumerate(names, 1):
    darkline.brightness(f'patches/{n}', n)
    if i % 10 == 0: print(f'{i}/{len(names)} {time.time()-t:.0f}s', flush=True)
print('done', flush=True)
