"""Crop and simplify Natural Earth land/rivers/lakes and openpolis Italian regions into
one compact basemap (geo/basemap.json) that the app embeds. Map tiles are not
allowed inside the artifact, so all geometry ships with the page."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "geo"
BBOX = (-11.0, 35.0, 20.5, 56.0)  # lon_min, lat_min, lon_max, lat_max: London-Madrid-Palermo
RIVERS = {"Tiber", "Tevere", "Arno", "Po", "Reno", "Adige", "Thames", "Seine", "Tagus", "Tajo",
          "Manzanares", "Brenta", "Piave", "Volturno", "Ombrone", "Serchio", "Tanaro", "Ticino",
          "Adda", "Oglio", "Mincio", "Rhône", "Rhine", "Loire", "Ebro", "Arc"}


def dp(pts, tol):
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0][:2], pts[-1][:2]
    dx, dy = x2 - x1, y2 - y1
    norm = (dx * dx + dy * dy) ** 0.5
    imax, dmax = 0, 0.0
    for i in range(1, len(pts) - 1):
        x, y = pts[i][:2]
        d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm if norm else ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
        if d > dmax:
            imax, dmax = i, d
    if dmax > tol:
        return dp(pts[:imax + 1], tol)[:-1] + dp(pts[imax:], tol)
    return [pts[0], pts[-1]]


def simplify_ring(ring, tol):
    # closed ring: split at the vertex farthest from the start so DP has a real chord
    k = max(range(len(ring)), key=lambda i: (ring[i][0] - ring[0][0]) ** 2 + (ring[i][1] - ring[0][1]) ** 2)
    return dp(ring[:k + 1], tol)[:-1] + dp(ring[k:], tol)


def touches(coords):
    xs = [p[0] for p in coords]; ys = [p[1] for p in coords]
    return not (max(xs) < BBOX[0] or min(xs) > BBOX[2] or max(ys) < BBOX[1] or min(ys) > BBOX[3])


def polys(geom):
    return geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]


def rnd(pts, nd):
    return [[round(p[0], nd), round(p[1], nd)] for p in pts]


def areas(path, tol, nd, min_pts=4, name_key=None):
    out = []
    for f in json.load(open(path))["features"]:
        for poly in polys(f["geometry"]):
            rings = [rnd(simplify_ring(r, tol), nd) for r in poly if touches(r)]
            rings = [r for r in rings if len(r) >= min_pts]
            if rings:
                out.append(rings)
    return out


def lines(path, tol, nd):
    out = []
    for f in json.load(open(path))["features"]:
        name = f["properties"].get("name") or f["properties"].get("name_en") or ""
        if name not in RIVERS:
            continue
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for part in parts:
            if touches(part):
                s = rnd(dp(part, tol), nd)
                if len(s) >= 2:
                    out.append({"n": name, "c": s})
    return out


base = {
    "bbox": BBOX,
    "land": areas(GEO / "ne_50m_land.geojson", 0.02, 3),
    "italy": areas(GEO / "limits_IT_regions.geojson", 0.0015, 4),  # finer: needed when zoomed into cities
    "lakes": areas(GEO / "ne_50m_lakes.geojson", 0.01, 3),
    "rivers": lines(GEO / "ne_10m_rivers_lake_centerlines.geojson", 0.002, 4),
}
txt = json.dumps(base, separators=(",", ":"))
(GEO / "basemap.json").write_text(txt)
print({k: len(v) for k, v in base.items() if k != "bbox"}, "KB:", len(txt) // 1024,
      "rivers:", sorted({r["n"] for r in base["rivers"]}))
