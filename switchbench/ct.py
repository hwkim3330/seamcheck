"""PHercParis4 CT 볼륨(20260411134726, 레벨 2 = 9.6 um/vx)을 조각 단위로 받아 캐시하고 점마다 읽는다.

좌표는 SwitchBench 패치와 같은 (x, y, z) 레벨-2 복셀. zarr 은 (z, y, x) 순서, 128^3 무압축 uint8 조각.
"""
import os, threading
import numpy as np
import httpx

BASE = ("https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHercParis4/volumes/"
        "20260411134726-2.400um-0.2m-78keV-masked.zarr/2")
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ct_cache")
C = 128
_client = httpx.Client(timeout=120, limits=httpx.Limits(max_connections=64))
_lock = threading.Lock()
_mem = {}


def chunk_path(k):
    return os.path.join(CACHE, f"{k[0]}_{k[1]}_{k[2]}.u8")


def fetch_chunk(k):
    """k = (cz, cy, cx). 없으면 받아서 디스크에 둔다. 빈 조각(404)은 0 으로."""
    p = chunk_path(k)
    if os.path.exists(p): return
    os.makedirs(CACHE, exist_ok=True)
    for attempt in range(5):
        try:
            r = _client.get(f"{BASE}/{k[0]}/{k[1]}/{k[2]}")
            data = r.content if r.status_code == 200 else (b"" if r.status_code in (403, 404) else None)
            if data is None: raise RuntimeError(r.status_code)
            tmp = p + ".tmp"; open(tmp, "wb").write(data); os.replace(tmp, p)
            return
        except Exception:
            if attempt == 4: raise


def load_chunk(k):
    a = _mem.get(k)
    if a is None:
        fetch_chunk(k)
        b = open(chunk_path(k), "rb").read()
        a = np.frombuffer(b, np.uint8).reshape(C, C, C) if b else np.zeros((C, C, C), np.uint8)
        with _lock:
            if len(_mem) > 3000: _mem.clear()
            _mem[k] = a
    return a


def sample(xyz):
    """(N,3) x,y,z 점의 삼선형 보간 밝기 (float32)."""
    p = np.asarray(xyz, np.float64)
    zyx = p[:, ::-1]
    f = np.floor(zyx).astype(np.int64); w = zyx - f
    out = np.zeros(len(p), np.float64)
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                q = f + [dz, dy, dx]
                wt = (w[:, 0] if dz else 1 - w[:, 0]) * (w[:, 1] if dy else 1 - w[:, 1]) * (w[:, 2] if dx else 1 - w[:, 2])
                kk = q // C; ll = q % C
                keys, inv = np.unique(kk, axis=0, return_inverse=True)
                vals = np.empty(len(p))
                for j, k in enumerate(map(tuple, keys)):
                    m = inv.ravel() == j
                    a = load_chunk(k)
                    vals[m] = a[ll[m, 0], ll[m, 1], ll[m, 2]]
                out += wt * vals
    return out.astype(np.float32)


def prefetch(xyz, workers=32):
    """점들이 걸치는 조각을 병렬로 미리 받는다."""
    import concurrent.futures as cf
    p = np.asarray(xyz, np.float64)[:, ::-1]
    f = np.floor(p).astype(np.int64)
    ks = set()
    for d in ((0, 0, 0), (1, 1, 1), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1)):
        ks.update(map(tuple, np.unique((f + d) // C, axis=0)))
    todo = [k for k in ks if not os.path.exists(chunk_path(k))]
    with cf.ThreadPoolExecutor(workers) as ex:
        list(ex.map(fetch_chunk, todo))
    return len(ks), len(todo)
