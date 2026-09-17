# What the scan found

Scan of the Vesuvius Challenge open dataset with `seamcheck.py`, still running.
Numbers below are the state at 269 surface representations.

## Baseline: what "normal" looks like

This is the part that makes the check portable. Across 612 representations from many scrolls, scan sessions, and grid sizes from
129×357 to 5276×18079:

| | value |
|---|---|
| median neighbour step | **20 voxels** for 544 of 612 representations; a second cluster at **78** |
| max/median ratio, typical segment | 1.35× |
| max/median ratio, 90th percentile | 2.17× |
| worst clean segment | 3.06× |

The pipeline samples surfaces on a uniform ~20-voxel grid, so one threshold expressed
as a multiple of each segment's own median transfers to every segment without tuning.
A 5× threshold sits 1.6× above the worst clean segment observed.

## Verdicts

| verdict | count |
|---|---|
| `OK` | 227 |
| `SPARSE` (coverage < 50%) | 19 |
| `WATCH` | 11 |
| `REVIEW` | 12 |

The 12 `REVIEW` rows are **3 distinct segments**, each flagged independently in four
different representations:

| segment | ratio across its representations | largest step |
|---|---|---|
| `20260602230115-20230702185753_v14` | **195.7 / 195.3 / 195.3 / 34.9** | 3,940 voxels |
| `20260603222816-20231005123336_v2` | 24.5 / 16.8 / 16.8 / 14.0 | 491 voxels |
| `20260604223808-20231210121321_v8` | 14.8 / 13.7 / 13.7 / 13.6 | 297 voxels |

Normal is 20 voxels. 3,940 is a 200× jump, and there are 24,842 such cells in that
segment. The same segment flags at grid resolutions 20× apart (4516×1328 and 239×68),
so this is a property of the surface, not of one parameterisation.

## The worst one, located

![worst](findings_worst.png)

Flagged cells are not scattered. In `20230702185753_v14` they fall almost entirely in
the first eighth of the `v` axis (row histogram `[1,9,0,0,0,0,0,0,0,0,0,0,0,0,0,0]`),
and the map shows why: a tongue-shaped piece at the top is stitched to the main body.
The two are neighbours in the grid and 3,940 voxels apart in space.

A topology check sees nothing here. The mesh is manifold across that seam.

### Confirmed by a second, independent measurement

Distance flagged it. Position around the scroll axis confirms it. Splitting the segment at
the flagged boundary (`v = 557`) and measuring each part against the fitted axis:

| | tongue (161k points) | main body (4.35M points) |
|---|---|---|
| median radius from axis | **6,254** | **3,175** |
| median azimuth | 125.8° | −25.1° |

The two parts sit **3,079 voxels apart in radius** and 151° apart in angle. They are
adjacent cells in the grid and they are on different wraps of the scroll — the tongue
belongs to a layer roughly twice as far out.

Three signals agree: the 3,940-voxel step, the 3,079-voxel radius gap, and the 151°
azimuth gap. Topology sees none of them.

## The two checks catch different things — measured

Running both on the same three flagged segments, using a *small* representation of each:

| segment | grid | seamcheck | windcheck |
|---|---|---|---|
| `20230702185753` | 677×870 | 2.2× `OK` | **11.0× `REVIEW`** |
| `20231005123336` | 548×1493 | 2.2× `OK` | 2.9× `OK` |
| `20231210121321` | 1046×718 | 4.0× `OK` | 4.8× `OK` |

Two things fall out of this.

**A verdict belongs to a representation, not to a segment.** The same physical segment
reads 195× in its 4516×1328 parameterisation and 2.2× in its 677×870 one. The small
representation does not contain the defective region at all — the tongue is only present
in the larger one. "Clean" there means "that part is not in this file", which is not the
same claim. Any corpus-level statement has to name the representation it scanned.

**Winding catches what distance misses.** On the 677×870 representation, `seamcheck` sees
nothing (2.2×, well inside normal) while `windcheck` flags it at 11.0×. That is the case
the two-check design exists for: a discontinuity in which wrap you are on, without a
matching jump in 3D distance.

## Caveats

- Flagging is not proof. Each `REVIEW` is a coordinate to look at, not a verdict on
  the trace.
- The scan is incomplete; it covers the scrolls with the most segments first.
- Verdicts are per representation. A segment can read clean in one parameterisation and
  badly in another simply because the two cover different parts of the surface.
- `SPARSE` segments are reported separately rather than judged — low coverage makes
  the median unreliable.

## A result we withdrew

An earlier version of this file reported that segments named `auto_grown` flagged at 66%
against 20% for the rest, and called it evidence that the checks measure real quality.

**That was wrong, and the cause was a bug in our own code.** `verdict()` tested the jump
ratio *before* testing coverage, so segments with many empty grid cells were judged
instead of being set aside. Sparse segments have an unstable median, which inflates the
ratio — measured, the 20–50% coverage band has a median ratio of 4.5× against 1.7× for
the 80%+ band, not because they are worse but because the baseline is noisy. Auto-grown
segments happen to be sparser.

With coverage checked first, the gap disappears:

| | flagged (before fix) | flagged (after fix) |
|---|---|---|
| `auto_grown` | 34% | **22%** |
| hand-curated `w###` | 26% | **22%** |

Identical. There is no provenance effect in this data. We are leaving the retraction in
rather than deleting the claim, because the bug is one anybody writing this kind of check
will hit.

## One group that the fix does not explain

Segments whose names contain `z_dbg_gen` behave unlike everything else, and the coverage
fix does not touch them:

| class | representations judged | flagged | median ratio |
|---|---|---|---|
| `w###` (hand-curated) | 806 | 22% | 1.9× |
| `auto_grown` | 174 | 22% | 1.2× |
| other | 277 | 6% | 1.3× |
| **`z_dbg_gen`** | **105** | **100%** | **19.3×** |

Every single one, at a median ratio an order of magnitude above every other class. Their
directory layout is a normal segment's — tifxyz, three OBJs, ink-detection outputs, 1,123
files — so they are not obviously scratch data, but `dbg` in the name suggests they may be
generated for debugging rather than traced.

We are not calling these defects. Either those surfaces really are discontinuous, or the
check systematically misreads whatever produced them. Distinguishing the two needs someone
who knows what `z_dbg_gen` is; that question is the concrete thing this scan surfaces.
