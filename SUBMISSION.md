# Vesuvius Challenge — Progress Prize submission (draft)

**Repo:** https://github.com/hwkim3330/seamcheck · MIT-0
**Targets:** Open Problem #3 (automatic mesh topology repair) and, as a by-product,
Open Problem #6 (automating winding-number annotation).

## What it is

Three checks that read a traced surface and say *where a human should look*. None of
them needs a GPU, a CT volume, or model weights. Three TIFFs — about 3 MB — per segment.

| tool | reads | catches | blind to |
|---|---|---|---|
| `seamcheck.py` | `tifxyz` | sheet switch that moves in 3D | a switch onto a touching wrap |
| `windcheck.py` | `tifxyz` | sheet switch that changes winding number | anything near the scroll axis |
| `meshcheck.py` | `.obj` | holes, mergers, split components | sheet switches — the mesh stays manifold |

## Why a distance check works at all

Across 400+ surface representations from many scrolls, scan sessions, and grid sizes
from 129×357 to 5276×18079, the median neighbour step is **19.9–20.1 voxels**. The
pipeline samples on a uniform ~20-voxel grid, so a threshold written as a multiple of
each segment's own median transfers everywhere without tuning. The worst *clean*
segment observed is 3.06×; the 5× threshold sits comfortably above it.

That baseline is, as far as we could find, not published anywhere. It is the part of
this submission most likely to be useful to others regardless of the tools.

## What it found

3 distinct segments flagged, each independently in four different representations:

| segment | ratio across representations | largest step |
|---|---|---|
| `20230702185753_v14` | **195.7 / 195.3 / 195.3 / 34.9** | 3,940 voxels |
| `20231005123336_v2` | 24.5 / 16.8 / 16.8 / 14.0 | 491 voxels |
| `20231210121321_v8` | 14.8 / 13.7 / 13.7 / 13.6 | 297 voxels |

The worst one, confirmed three independent ways: a 3,940-voxel step where normal is 20;
a **3,079-voxel radius gap** between the two sides of the seam; a **151° azimuth gap**.
A tongue-shaped piece at the top of the sheet is stitched to a body that lies on a
different wrap. The mesh is manifold across that seam, so topology checks see nothing.

## Winding numbers, free

`windcheck` fits the scroll axis (first principal component; measured 0.99 alignment
with z) and reports how many turns each segment spans — median 1.11, max 29.6 in the
scanned set. That is the annotation Open Problem #6 asks to automate.

## Honest limits

- Flags are coordinates to inspect, not verdicts.
- `seamcheck` cannot see a switch onto a wrap that is physically touching; that is why
  `windcheck` exists. `windcheck` cannot judge cells near the axis, where radius → 0 and
  a 20-voxel move becomes hundreds of degrees.
- Two false-positive storms were found and fixed during development, both documented in
  the README rather than quietly removed: differencing across grid gaps, and including
  near-axis cells.
- The corpus scan is still running and covers the largest scrolls first.

## Reproduce

```bash
pip install numpy tifffile imagecodecs
python seamcheck.py --s3 PHercParis4 --json out
python windcheck.py --s3 PHerc1667  --json wind
python meshcheck.py surface.obj
```
