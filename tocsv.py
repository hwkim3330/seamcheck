#!/usr/bin/env python3
"""
스캔 결과(jsonl) → 제출용 CSV.

저장소에 이 스크립트가 없어서 CSV 가 손으로 만들어졌고, 그 결과
results_windcheck.csv 가 wind.jsonl 보다 21분 오래된 채로 제출 문서에
들어갔다. 행 수도 문서 숫자도 실제 데이터와 어긋났다.
그래서 CSV 는 전부 여기서만 만든다.

    python3 tocsv.py wind.jsonl    results_windcheck.csv
    python3 tocsv.py rejudged.json results_seamcheck.csv

이음새 쪽 원본이 all.jsonl 이 아니라 rejudged.json 인 이유: verdict() 가
비율을 커버리지보다 먼저 보던 버그를 고친 뒤 판정을 다시 매겼고, 그 결과가
rejudged.json 이다. all.jsonl 에는 고치기 전 판정이 들어 있다. 측정값은
양쪽이 1,246행 전부 동일하다 — 다른 것은 판정 열뿐이다.
"""
import csv, json, sys

COLS = {
    "wind": ["name", "step_deg", "worst_ratio", "jumps", "jump_rate", "flips",
             "turns_median", "turns_max", "radius_median", "verdict"],
    "seam": ["name", "shape_v", "shape_u", "coverage", "median_step", "max_step",
             "ratio", "flagged", "severe", "edges", "verdict"],
}

# 제출된 CSV 와 같은 자리수로 적는다. 원시 float 을 그대로 쓰면 파일이
# 두 배로 커지고 사람이 못 읽는다.
ROUND = {"coverage": 4, "median_step": 2, "max_step": 1, "ratio": 2,
         "step_deg": 4, "worst_ratio": 1, "jump_rate": 6,
         "turns_median": 2, "turns_max": 2, "radius_median": 1}

def fmt(col, v):
    n = ROUND.get(col)
    return round(v, n) if (n is not None and isinstance(v, float)) else v

def load(src):
    """jsonl 이든 json 배열이든 읽는다."""
    txt = open(src).read().lstrip()
    if txt.startswith("["):
        return json.loads(txt)
    return [json.loads(l) for l in txt.splitlines() if l.strip()]

def main(src, dst):
    rows = load(src)
    kind = "wind" if "turns_median" in rows[0] else "seam"
    cols = COLS[kind]

    # 한 조각은 해상도가 다른 여러 표현을 갖는다. 그 행들은 서로 다른 측정이므로
    # 남겨야 한다. 지워야 하는 건 두루마리별 실행이 겹쳐 같은 표현을 두 번 잰 것뿐이다.
    # 그래서 이름이 아니라 '측정 동일성'으로 묶는다.
    #
    # (windcheck 의 name 은 경로의 마지막 조각이라 어느 표현인지가 담기지 않는다.
    #  그래서 크기 정보를 키에 함께 넣어야 표현이 구분된다.)
    key = (lambda r: (r["name"], tuple(r.get("shape", ()))) if kind == "seam"
           else (r["name"], r.get("rows"), r.get("radius_median"), r.get("step_deg")))
    uniq, skipped = {}, 0
    for r in rows:
        if not r.get("ok", True):
            skipped += 1
            continue
        # 같은 표현이 두 번 측정된 경우 나중 것을 쓴다. 뒤 실행이 더 완전하다
        # (실제로 같은 조각에서 변 수가 10만 → 144만으로 늘어난 경우가 있었다).
        uniq[key(r)] = r

    out = []
    for k in uniq:
        r = uniq[k]
        if kind == "seam":
            sv, su = (list(r.get("shape", [None, None])) + [None, None])[:2]
            r = {**r, "shape_v": sv, "shape_u": su}
        out.append({c: fmt(c, r.get(c)) for c in cols})

    with open(dst, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print(f"{src} {len(rows)}줄 → {dst} {len(out)}행 (실패 {skipped}건 제외)")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
