"""Approximate state borders that change over time, assembled from modern Italian provinces
(openpolis). Each province has a dated state history: data/province_changes.csv for the
provinces that changed hands, and data/province_states.csv for the rest (constant state).
Every period between two changes gets its own map; provinces of one state are merged into
one outline, and identical outlines are stored once.
Needs shapely:  <venv>/bin/python scripts/make_borders.py
Writes geo/borders.json; build.py embeds it."""
import csv, json
from pathlib import Path
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
Y0, Y1 = 1450, 1720
SNAPS = [1494, 1559, 1600, 1700]


def read(name):
    return list(csv.DictReader(open(ROOT / "data" / name, encoding="utf-8")))


provinces = {f["properties"]["prov_name"]: shape(f["geometry"]).buffer(0)
             for f in json.load(open(ROOT / "geo/limits_IT_provinces.geojson"))["features"]}
snap_rows = {r["province"]: r for r in read("province_states.csv")}
if set(snap_rows) != set(provinces):
    raise SystemExit(f"province_states.csv mismatch: {sorted(set(provinces) ^ set(snap_rows))}")

# dated history per province
hist = {}
for r in read("province_changes.csv"):
    if r["province"] not in provinces:
        raise SystemExit(f"province_changes.csv: unknown province {r['province']}")
    hist.setdefault(r["province"], []).append({"state": r["state"], "from": int(r["from"]), "to": int(r["to"]),
                                               "confidence": r["confidence"], "note": r["note"]})
problems = []
for name, r in snap_rows.items():
    snaps = [r[f"y{y}"] for y in SNAPS]
    if name not in hist:
        if len(set(snaps)) > 1:
            problems.append(f"{name}: changes between snapshots {snaps} but has no dated history")
        hist[name] = [{"state": snaps[0], "from": Y0, "to": Y1, "confidence": r["confidence"], "note": r["note"]}]
    h = sorted(hist[name], key=lambda x: x["from"])
    if h[0]["from"] != Y0 or h[-1]["to"] != Y1 or any(a["to"] != b["from"] for a, b in zip(h, h[1:])):
        problems.append(f"{name}: history does not cover {Y0}-{Y1} without gaps")
    for y, s in zip(SNAPS, snaps):  # the dated history must agree with the four snapshots
        at = next((x["state"] for x in h if x["from"] <= y < x["to"]), None)
        if at != s:
            problems.append(f"{name}: history gives {at} in {y}, snapshot table gives {s}")
    hist[name] = h
if problems:
    raise SystemExit("border data inconsistent:\n  " + "\n  ".join(problems))

breaks = sorted({Y0, Y1} | {x["from"] for h in hist.values() for x in h} | {x["to"] for h in hist.values() for x in h})


def rounded(geom):
    m = mapping(geom)
    polys = m["coordinates"] if m["type"] == "MultiPolygon" else [m["coordinates"]]
    return [[[[round(x, 3), round(y, 3)] for x, y in ring] for ring in poly] for poly in polys]


geoms, periods = {}, []
for a, b in zip(breaks, breaks[1:]):
    by_state = {}
    for name, h in hist.items():
        x = next(x for x in h if x["from"] <= a < x["to"])
        by_state.setdefault(x["state"], []).append({"name": name, "confidence": x["confidence"], "note": x["note"]})
    states = []
    for st, ps in sorted(by_state.items()):
        key = st + ":" + "|".join(sorted(p["name"] for p in ps))
        if key not in geoms:
            g = unary_union([provinces[p["name"]] for p in ps]).simplify(0.005, preserve_topology=True).buffer(0)
            geoms[key] = rounded(g)
        states.append({"state": st, "g": key, "provinces": ps})
    periods.append({"from": a, "to": b, "states": states})

out = {"periods": periods, "geoms": geoms, "shepherd": 1494}
txt = json.dumps(out, separators=(",", ":"))
(ROOT / "geo/borders.json").write_text(txt)
print(f"periods={len(periods)} distinct outlines={len(geoms)} KB={len(txt) // 1024}")
print(" ".join(f"{p['from']}-{p['to']}" for p in periods))
