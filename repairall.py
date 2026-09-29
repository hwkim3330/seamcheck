#!/usr/bin/env python3
"""repairall — 깃발 달린 조각 전부를 수리하고, 멀쩡한 조각으로 대조한다.

한 조각에서 잘 됐다고 수리 도구라고 부를 수는 없다. 두 가지를 같이 본다.

  깃발 조각 96개의 모든 표현 — 고쳐지는가, 얼마나 버리는가
  전부 OK 인 조각 중 40개     — **망가뜨리지 않는가** (대조군)

검증은 두 신호로 한다. 수리는 3D 거리로 하므로 거리로 다시 재면 깨끗한 게
당연하다. 권취(축 둘레 각도의 연속성)는 수리에 쓰지 않은 신호라 독립 확인이 된다.
권취 검사기는 수리 전후와 대조군에 **똑같이** 적용하고, 결과를 보고 고치지 않는다.

결과는 한 줄씩 repair.jsonl 에 쌓인다. 중간에 끊겨도 이어서 돈다.
"""
import json, os, random, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seamcheck import s3_segments, S3  # noqa: E402
from repair import repair  # noqa: E402

SCROLLS = """PHercParis4 PHerc1667 PHerc0814 PHerc1447 PHercMANBp PHerc0841 PHerc1203
PHerc1451 PHercMAN5 PHerc0172 PHerc0332 PHerc0009B PHerc0125 PHerc0139 PHerc0175A
PHerc0175B PHerc0191 PHerc0211 PHerc0257 PHerc0268 PHerc0306B PHerc0343 PHerc0343P
PHerc0358 PHerc0483A PHerc0483B PHerc0490A PHerc0490B PHerc0500P2 PHerc0800 PHerc0813
PHerc0826 PHerc0846A PHerc0846B PHerc1218 PHerc1299 PHerc1545 PHerc1667Cr1Fr3
PHerc51Cr4Fr8 PHercMANB PHercParis1Fr34 PHercParis1Fr39 PHercParis2Fr143
PHercParis2Fr47 PHercParis3""".split()

OUT = "repair.jsonl"


def main():
    rj = json.load(open("rejudged.json"))
    seg = defaultdict(set)
    for r in rj:
        seg[r["name"]].add(r["verdict"])
    flagged = {n for n, v in seg.items() if v & {"REVIEW", "WATCH"}}
    oks = sorted(n for n, v in seg.items() if v == {"OK"})
    control = set(random.Random(20260929).sample(oks, 40))   # 시드 고정 — 다시 뽑아도 같다

    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["src"] for l in open(OUT) if l.strip()}

    jobs = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for scroll, bases in zip(SCROLLS, ex.map(s3_segments, SCROLLS)):
            for b in bases:
                name = b.split("/segments/")[1].split("/")[0]
                grp = "flagged" if name in flagged else "control" if name in control else None
                src = f"{S3}/{b}"
                if grp and src not in done:
                    jobs.append((src, name, scroll, grp))
    print(f"할 일 {len(jobs)}개 (이미 한 것 {len(done)}개)", flush=True)

    out = open(OUT, "a")

    def one(job):
        src, name, scroll, grp = job
        r = repair(src, None, quiet=True)
        r.update(name=name, scroll=scroll, group=grp)
        return r

    # 큰 표현은 1.7GB 까지 쓴다. 동시에 둘만 돈다.
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(one, j): j for j in jobs}
        for i, f in enumerate(as_completed(futs), 1):
            j = futs[f]
            try:
                r = f.result()
            except Exception as e:
                print(f"[{i}/{len(jobs)}] 실패 {j[1][:40]}: {type(e).__name__}: {e}", flush=True)
                continue
            out.write(json.dumps(r) + "\n"); out.flush()
            p0 = r["parts"][0] if r["parts"] else {}
            print(f"[{i}/{len(jobs)}] {j[3]:<7} {j[1][:34]:<35} "
                  f"거리 {r['before_verdict']:<6}→{p0.get('verdict','-'):<6} "
                  f"권취 {r['before_wind_verdict']:<6}→{p0.get('wind_verdict','-'):<6} "
                  f"남김 {r['kept_share']*100:5.1f}%  조각 {len(r['parts'])}", flush=True)
    print("REPAIRDONE", flush=True)


if __name__ == "__main__":
    main()
