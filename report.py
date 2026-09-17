#!/usr/bin/env python3
"""스캔 결과(all.jsonl)를 사람이 읽는 표로 만든다."""
import json, sys, statistics as st
from collections import Counter, defaultdict

rows=[json.loads(l) for l in open(sys.argv[1] if len(sys.argv)>1 else "all.jsonl")]
seen=set(); uniq=[]
for r in rows:                       # 같은 조각이 여러 표현으로 중복될 수 있다
    k=(r["name"], tuple(r["shape"]))
    if k in seen: continue
    seen.add(k); uniq.append(r)

print(f"# 이음새 전수 검사 결과\n")
print(f"검사한 표면 표현 {len(rows)}개 (중복 제거 {len(uniq)}개)")
byv=Counter(r["verdict"] for r in uniq)
print(f"판정: " + " · ".join(f"{k} {v}" for k,v in byv.most_common()))
rat=[r["ratio"] for r in uniq]
med=[r["median_step"] for r in uniq]
print(f"\n## 기준선")
print(f"- 정상 이웃 간격(중앙값): {min(med):.1f} ~ {max(med):.1f} 복셀 — 조각과 두루마리가 달라도 사실상 동일")
print(f"- 최대/중앙 배율: 중앙 {st.median(rat):.2f}x · 90% {sorted(rat)[int(len(rat)*0.9)]:.2f}x · 최대 {max(rat):.2f}x")
print(f"- 즉 임계값 5x 는 관측된 최악값의 {5/max(rat):.1f}배 여유")
cov=[r["coverage"] for r in uniq]
print(f"- 유효 격자 비율: 중앙 {st.median(cov)*100:.0f}% · 최소 {min(cov)*100:.0f}%")

bad=[r for r in uniq if r["verdict"]!="OK"]
print(f"\n## 사람이 다시 봐야 할 조각: {len(bad)}개")
for r in sorted(bad,key=lambda x:-x["ratio"]):
    print(f"- `{r['verdict']}` {r['name']} — 배율 {r['ratio']:.1f}x, 5배 초과 {r['flagged']:,}곳")
if not bad:
    print("- 없음. 공개된 조각은 이 기준으로 전부 연속이다.")
print(f"\n## 규모별")
big=sorted(uniq,key=lambda r:-(r['shape'][0]*r['shape'][1]))[:5]
for r in big:
    print(f"- {r['name'][:40]:<42} {r['shape'][0]}x{r['shape'][1]:<6} 배율 {r['ratio']:.2f}x")
