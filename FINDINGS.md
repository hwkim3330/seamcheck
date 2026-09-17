# What the scan found

Full scan of the Vesuvius Challenge open dataset with `seamcheck.py`: **45 scrolls,
322 distinct segments, 1,246 distinct surface representations.** Raw results are in
`results_seamcheck.csv` and `results_windcheck.csv` — use them without running anything.

## Baseline: what "normal" looks like

This is the part most likely to be useful regardless of the tools. Across 1,246
representations, many scrolls, many scan sessions, grid sizes from 129×357 to 5276×18079:

| | value |
|---|---|
| median neighbour step | **20 voxels** (1,131 of 1,246); smaller clusters at 21, 22, 27, 28, **78** |
| max/median ratio, typical | **1.78×** |
| 90th percentile | 32.5× |

The step clusters match the scan resolutions in the dataset (1.129 µm to 45.5 µm). Because
the threshold is a multiple of *each segment's own* median, it crosses all of them without
tuning. That is the whole reason for using a relative measure.

## Verdicts

| verdict | count |
|---|---|
| `OK` | 815 |
| `SPARSE` — coverage < 50%, not judged | 144 |
| `WATCH` | 41 |
| `REVIEW` | 246 |

Of 322 distinct segments, **96 (30%)** have at least one representation flagged.

## A result we withdrew

An earlier version of this file reported that `auto_grown` segments flagged at 66% against
20% for the rest, and called it evidence that the checks measure real quality.

**That was wrong, and the cause was a bug in our own code.** `verdict()` tested the jump
ratio *before* testing coverage, so segments with many empty grid cells were judged instead
of set aside. Sparse segments have an unstable median, which inflates the ratio: measured,
the 20–50% coverage band reads 4.5× median against 1.7× for the 80%+ band — noise, not
defects. Auto-grown segments happen to be sparser.

With coverage checked first the gap disappears:

| | flagged before fix | after fix |
|---|---|---|
| `auto_grown` | 34% | **19%** |
| hand-curated `w###` | 26% | **25%** |

The retraction stays in rather than the claim being deleted. Anyone writing this kind of
check will hit the same bug.

## One group the fix does not explain

| class | representations judged | flagged | median ratio |
|---|---|---|---|
| `w###` (hand-curated) | 662 | 25% | 2.0× |
| `auto_grown` | 119 | 19% | 1.2× |
| other | 236 | 6% | 1.3× |
| **`z_dbg_gen`** | **85** | **100%** | **19.9×** |

Every one, at a median ratio an order of magnitude above every other class. Their directory
layout is a normal segment's — tifxyz, three OBJs, ink-detection outputs, 1,123 files — so
they are not obviously scratch data, but `dbg` in the name suggests they may be generated
for debugging rather than traced.

**We are not calling these defects.** Either those surfaces really are discontinuous, or the
check systematically misreads whatever produced them. Telling the two apart needs someone
who knows what `z_dbg_gen` is. Surfacing that question is what this scan is for.

## The clearest single case

The worst hand-curated segment, `20230702185753_v14`, jumps **3,940 voxels** where normal is
20, in 24,842 cells, and flags in four independent representations.

![worst](findings_worst.png)

Flagged cells sit almost entirely in the first eighth of the `v` axis. A tongue-shaped piece
at the top of the sheet is stitched to the main body. Splitting there and measuring each part
against the fitted scroll axis:

| | tongue (161k points) | main body (4.35M points) |
|---|---|---|
| median radius from axis | **6,254** | **3,175** |
| median azimuth | 125.8° | −25.1° |

**3,079 voxels apart in radius, 151° apart in angle** — grid neighbours on different wraps.
Three independent signals agree. A topology check sees none of them: the mesh stays manifold
across that seam.

## The two checks catch different things

Both run on the same segments, using a *small* representation of each:

| segment | grid | seamcheck | windcheck |
|---|---|---|---|
| `20230702185753` | 677×870 | 2.2× `OK` | **11.0× `REVIEW`** |
| `20231005123336` | 548×1493 | 2.2× `OK` | 2.9× `OK` |
| `20231210121321` | 1046×718 | 4.0× `OK` | 4.8× `OK` |

On the first, distance sees nothing while winding flags it. That is the case the two-check
design exists for.

It also shows that **a verdict belongs to a representation, not to a segment.** The same
segment reads 195× at 4516×1328 and 2.2× at 677×870, because the small file does not contain
the defective region at all. Any corpus-level claim has to say which representations it
scanned.

## Caveats

- Flags are coordinates to inspect, not verdicts on a trace.
- `SPARSE` representations are set aside, not judged.
- Verdicts are per representation, as above.
- `windcheck` cannot judge cells near the scroll axis, where radius → 0.
