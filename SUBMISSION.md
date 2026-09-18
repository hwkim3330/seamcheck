# Vesuvius Challenge — Progress Prize submission

**Repo:** https://github.com/hwkim3330/seamcheck · MIT-0
**Targets:** Open Problem #3 (automatic mesh topology repair); Open Problem #6
(automating winding-number annotation) as a by-product.

## What it is

Three checks that read a traced surface and say *where a human should look*. No GPU, no CT
volume, no model weights. About 3 MB per segment; a 630×687 segment analyses in well under
a second.

| tool | reads | catches | blind to |
|---|---|---|---|
| `seamcheck.py` | `tifxyz` | sheet switch that moves in 3D | a switch onto a touching wrap |
| `windcheck.py` | `tifxyz` | sheet switch that changes winding number | cells near the scroll axis |
| `meshcheck.py` | `.obj` | holes, mergers, split components | sheet switches — the mesh stays manifold |

## What is in this submission

1. **A corpus-wide baseline.** 45 scrolls, 322 segments, 1,246 surface representations
   scanned. Median neighbour step is 20 voxels for 1,131 of them, with clusters at 21, 22,
   27, 28 and 78 matching the dataset's scan resolutions. Typical max/median ratio 1.78×
   (median over the 1,102 representations with enough coverage to judge; 1.90× including the
   144 sparse ones).
   We could not find this measured anywhere, and it is what lets a single relative
   threshold work across every scroll without tuning.

2. **The results themselves**, as `results_seamcheck.csv` (1,246 rows) and
   `results_windcheck.csv` (697 rows). Usable without running the tools.

3. **Automatic winding numbers.** `windcheck` fits the scroll axis (first principal
   component; median alignment with z is 0.992, though it drops to 0.018 on segments too
   short to constrain a direction) and reports turns spanned per segment — median 0.79,
   max 29.6. That is the annotation Open Problem #6 asks to automate.

4. **A list of places to look.** 96 of 322 segments have at least one flagged
   representation. The clearest: `20230702185753_v14` jumps 3,940 voxels where normal is
   20. Splitting at the seam, the two sides sit 3,079 voxels apart in radius and 151° apart
   in azimuth — grid neighbours on different wraps. Topology sees none of it.

5. **One open question for someone who knows the pipeline.** All 85 judged `z_dbg_gen`
   representations flag, at median 19.9× against 1.2–2.0× for every other class. We do not
   claim these are defects; we cannot tell from outside whether those surfaces are
   discontinuous or the check misreads how they were made.

## What we got wrong, and left in

**The winding CSV shipped stale.** `results_windcheck.csv` was written by hand before the
last scan finished, so it carried 553 of 697 rows and the submission quoted a turns median
(0.96) that appears in no run of the tool — the closest match is a three-record smoke test.
There was no script in the repo that built the CSVs, which is how the two drifted apart.
`tocsv.py` now builds both, and it reproduces the 1,246-row seam CSV exactly, column for
column, from `rejudged.json`.

We first reported that `auto_grown` segments flagged at 66% against 20%, and called it
evidence the checks measure real quality. It was our own bug: `verdict()` tested the jump
ratio before testing coverage, so sparse segments were judged instead of set aside, and
sparse segments have an unstable median. With the order fixed, `auto_grown` and
hand-curated segments both flag at about the same rate and the effect vanishes.

The retraction is in `FINDINGS.md` rather than the claim being deleted, because anyone
writing this kind of check will hit the same bug.

## Reproduce

```bash
pip install numpy tifffile imagecodecs
python seamcheck.py --s3 PHercParis4 --json out
python windcheck.py --s3 PHerc1667  --json wind
python meshcheck.py surface.obj

# 스캔 결과(jsonl) → 제출된 CSV. 두 CSV 는 전부 이 스크립트로만 만든다.
python tocsv.py rejudged.json results_seamcheck.csv   # 1,246행
python tocsv.py wind.jsonl    results_windcheck.csv   # 697행
```

`results_seamcheck.csv` 의 판정이 `all.jsonl` 이 아니라 `rejudged.json` 에서 오는 이유는
아래 "What we got wrong" 에 적은 `verdict()` 순서 버그를 고친 뒤 판정을 다시 매겼기
때문입니다. 측정값 자체는 1,246행 전부 동일하고, 다른 것은 판정 열뿐입니다.
