#!/usr/bin/env python3
"""v14 수리 전후 그림 — 어디를 도려냈고, 무엇이 남았는가."""
import os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seamcheck import load_xyz  # noqa: E402
from repair import bad_edges, erase_seam  # noqa: E402
import windcheck  # noqa: E402

SRC = ("https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHercParis4/segments/"
       "20260602230115-20230702185753_v14/mesh/20260602230115-on-20260411134726-2.4um.tifxyz")

P, valid = load_xyz(SRC)
ea, eb, med = bad_edges(P, valid, 5.0)
clean, erased = erase_seam(valid, ea, eb)
cut = valid & ~clean

c, axis, e1, e2, _ = windcheck.scroll_axis(P[valid])
q = P - c
rad = np.hypot(q @ e1, q @ e2)

# 이웃 간격 지도 — 각 칸에서 오른쪽/아래 이웃까지의 3D 거리 중 큰 값
def step_map(mask):
    s = np.zeros(mask.shape)
    for axis_ in (0, 1):
        n = P.shape[axis_]
        a = np.take(P, np.arange(n - 1), axis=axis_); b = np.take(P, np.arange(1, n), axis=axis_)
        m = np.take(mask, np.arange(n - 1), axis=axis_) & np.take(mask, np.arange(1, n), axis=axis_)
        d = np.where(m, np.linalg.norm(b - a, axis=-1), 0)
        pad = [(0, 1), (0, 0)] if axis_ == 0 else [(0, 0), (0, 1)]
        s = np.maximum(s, np.pad(d, pad))
    return s / med

before, after = step_map(valid), step_map(clean)

# 결함이 몰린 곳을 확대한다
ys, xs = np.nonzero(cut)
y0, y1 = max(0, ys.min() - 60), min(valid.shape[0], ys.max() + 60)
if y1 - y0 > 900:                       # 너무 길면 가장 빽빽한 구간만
    h, e = np.histogram(ys, bins=40)
    mid = int((e[h.argmax()] + e[h.argmax() + 1]) / 2)
    y0, y1 = max(0, mid - 450), min(valid.shape[0], mid + 450)

fig, ax = plt.subplots(1, 3, figsize=(15, 6.2), constrained_layout=True)
kw = dict(aspect="auto", interpolation="nearest")
r = np.where(valid, rad, np.nan)
im0 = ax[0].imshow(r[y0:y1], cmap="viridis", **kw)
ax[0].imshow(np.ma.masked_where(~cut[y0:y1], cut[y0:y1]), cmap="autumn", **kw)
ax[0].set_title(f"radius from scroll axis\nred = {erased:,} cells erased along the seam")
fig.colorbar(im0, ax=ax[0], shrink=.8, label="voxels")

vmax = 10
im1 = ax[1].imshow(np.where(valid, before, np.nan)[y0:y1], cmap="magma", vmin=0, vmax=vmax, **kw)
ax[1].set_title(f"neighbour step / median — BEFORE\nmax {before.max():.0f}× (3D jump {before.max()*med:,.0f} voxels)")
im2 = ax[2].imshow(np.where(clean, after, np.nan)[y0:y1], cmap="magma", vmin=0, vmax=vmax, **kw)
ax[2].set_title(f"neighbour step / median — AFTER\nmax {after.max():.1f}×, {clean.sum()/valid.sum()*100:.1f}% of cells kept")
fig.colorbar(im2, ax=ax[1:], shrink=.8, label="× median step (clipped at 10)")
for a in ax:
    a.set_xlabel("u (grid column)"); a.set_ylabel(f"v (grid row, {y0}–{y1})")
    a.set_yticks([0, y1 - y0]); a.set_yticklabels([y0, y1])
fig.suptitle("20230702185753_v14 (PHercParis4, 2.4 µm) — seamcheck/repair.py", fontsize=13)
fig.savefig("repair_v14.png", dpi=110)
print("repair_v14.png", y0, y1, erased, f"{before.max():.1f}", f"{after.max():.2f}")
