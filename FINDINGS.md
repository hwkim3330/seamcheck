# What the scan found

Scan of the Vesuvius Challenge open dataset with `seamcheck.py`, still running.
Numbers below are the state at 269 surface representations.

## Baseline: what "normal" looks like

This is the part that makes the check portable. Across 269 representations from
many scrolls, many scan sessions, and grid sizes from 129×357 to 5276×18079:

| | value |
|---|---|
| median neighbour step | **19.9 – 20.1 voxels** — essentially constant everywhere |
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

## Caveats

- Flagging is not proof. Each `REVIEW` is a coordinate to look at, not a verdict on
  the trace.
- The scan is incomplete; it covers the scrolls with the most segments first.
- `SPARSE` segments are reported separately rather than judged — low coverage makes
  the median unreliable.
