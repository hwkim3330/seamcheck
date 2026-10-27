import json, os, sys, itertools
sys.path.insert(0, '.')
import darkline, devscore
c = devscore._c
sub = {}
for e in c['events'] + c['negatives']: sub.setdefault(e['patch'], set()).add(e.get('subset'))
names = [n for n in json.load(open('patch_names.json')) if 'v0' in sub[n]]
res = []
for dark, bright, maxw, min_len in itertools.product((0.45, 0.55, 0.65), (0.8, 0.9), (3, 5), (3, 5, 8)):
    al = {n: darkline.detect(f'patches/{n}', n, dark, bright, maxw, 4, min_len) for n in names}
    s = devscore.score(al, subset='v0')
    res.append((dark, bright, maxw, min_len, s['hits'], s['events'], s['fa'], s['fa100']))
    print(f"dark {dark} bright {bright} maxw {maxw} len {min_len}: recall {s['hits']}/{s['events']}  FA {s['fa']} ({s['fa100']:.2f}/100mm)", flush=True)
json.dump(res, open('tune_v0.json', 'w'))
