---
license: mit
task_categories:
- tabular-classification
tags:
- vesuvius-challenge
- herculaneum
- papyrus
- quality-control
- connectomics-adjacent
size_categories:
- 1K<n<10K
---

# Seam continuity measurements across the Vesuvius Challenge open dataset

Every traced papyrus surface in the [Vesuvius Challenge open
dataset](https://scrollprize.org/data), measured for geometric continuity.
**45 scrolls · 322 segments · 1,246 surface representations.**

Produced by [seamcheck](https://github.com/hwkim3330/seamcheck) (MIT-0).

## Why this exists

In a `tifxyz` segment, two cells adjacent in the flattened grid must be adjacent in 3D.
If a trace slipped onto the next wrap of the scroll, the mesh stays perfectly manifold —
topology checks see nothing — but the 3D step across that seam jumps.

Nobody had published what a *normal* step looks like across the corpus, so nobody could
say what threshold means "suspicious". These are those numbers.

## Files

| file | rows | what |
|---|---|---|
| `results_seamcheck.csv` | 1,246 | 3D neighbour-step statistics per surface representation |
| `results_windcheck.csv` | 697 | winding number and angular continuity per representation |
| `results_repair.csv` | 627 | automatic seam repair: area kept, distance and winding verdicts before/after (442 flagged + 185 control) |

### `results_seamcheck.csv`

| column | meaning |
|---|---|
| `name` | segment identifier |
| `shape_v`, `shape_u` | grid dimensions |
| `coverage` | fraction of grid cells with valid 3D coordinates |
| `median_step` | median 3D distance between grid neighbours, in voxels |
| `max_step` | largest such distance |
| `ratio` | `max_step / median_step` — the headline number |
| `flagged` | cells stepping more than 5× the median |
| `severe` | cells stepping more than 10× |
| `verdict` | `OK` / `WATCH` / `REVIEW` / `SPARSE` (coverage < 50%, not judged) |

### `results_windcheck.csv`

Adds `turns_median` and `turns_max` — how many times the segment wraps the scroll axis.
That is the winding-number annotation Vesuvius Open Problem #6 asks to automate.

## The baseline

| | |
|---|---|
| median neighbour step | **20 voxels** for 1,131 of 1,246 representations |
| other clusters | 21, 22, 27, 28, **78** — these match the dataset's scan resolutions (1.129 µm – 45.5 µm) |
| typical `ratio` | **1.78×** |
| 90th percentile | 32.5× |

Because `ratio` is relative to each segment's own median, one threshold crosses every
resolution without tuning.

## Verdicts

`OK` 815 · `SPARSE` 144 · `WATCH` 41 · `REVIEW` 246.
96 of 322 distinct segments have at least one flagged representation.

## Read this before using the flags

- A flag is **a coordinate to inspect**, not a verdict on a trace.
- A verdict belongs to **a representation, not a segment**. The same segment reads 195× at
  4516×1328 and 2.2× at 677×870 — the small file simply does not contain the defective
  region.
- All 85 judged `z_dbg_gen` representations flag, at median 19.9× against 1.2–2.0× for
  every other class. We do **not** claim these are defects; we cannot tell from outside
  whether those surfaces are discontinuous or the check misreads how they were generated.
- An earlier version of this analysis reported a provenance effect (`auto_grown` segments
  flagging more). That was a bug in verdict ordering — sparse segments were being judged
  instead of set aside. With it fixed the effect vanishes. Details in the repo's
  `FINDINGS.md`.

## Source data

Vesuvius Challenge open dataset, CC BY 4.0.
