"""Download OpenStreetMap streets, waterways, water areas and parks for the historic centres
of the hotspot cities (Overpass API) and simplify them into geo/osm_cities.json.
This is OSM data (ODbL, (c) OpenStreetMap contributors), rendered by the app itself: the
artifact cannot load map tiles, and bulk-copying OSM tiles is against the tile usage policy."""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path



def dp(pts, tol):  # Douglas-Peucker, as in make_basemap.py
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = (dx * dx + dy * dy) ** 0.5
    imax, dmax = 0, 0.0
    for i in range(1, len(pts) - 1):
        x, y = pts[i]
        d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm if norm else ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
        if d > dmax:
            imax, dmax = i, d
    if dmax > tol:
        return dp(pts[:imax + 1], tol)[:-1] + dp(pts[imax:], tol)
    return [pts[0], pts[-1]]


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "geo/osm_cities.json"
UA = {"User-Agent": "artists-network-research/0.1 (research prototype)"}
CITIES = {  # south, west, north, east: historic centre plus the curated sites
    "bologna": (44.484, 11.326, 44.504, 11.358),
    "florence": (43.745, 11.238, 43.784, 11.274),
    "rome": (41.855, 12.448, 41.912, 12.502),
    "venice": (45.428, 12.308, 45.452, 12.352),
    "naples": (40.830, 14.226, 40.862, 14.262),
}
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
             "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
ROADS = "motorway|trunk|primary|secondary|tertiary|unclassified|residential|pedestrian|living_street"
MAJOR = {"motorway", "trunk", "primary", "secondary", "tertiary"}


def overpass(bbox, footways):
    b = ",".join(map(str, bbox))
    roads = ROADS + ("|footway" if footways else "")
    q = f"""[out:json][timeout:90];
(way["highway"~"^({roads})$"]({b});
 way["waterway"~"^(river|canal)$"]({b});
 way["natural"="water"]({b});
 way["leisure"~"^(park|garden)$"]({b}););
out geom;"""
    body = urllib.parse.urlencode({"data": q}).encode()
    for attempt in range(6):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=UA), timeout=180) as r:
                return json.load(r)["elements"]
        except Exception as e:  # busy public servers: rotate and back off
            print("retry", url, e, file=sys.stderr); time.sleep(15 * (attempt + 1))
    raise RuntimeError("Overpass unavailable")


def coords(el):
    pts = [[round(g["lon"], 5), round(g["lat"], 5)] for g in el.get("geometry", [])]
    return dp(pts, 0.00003) if len(pts) > 2 else pts


data = json.loads(OUT.read_text()) if OUT.exists() else {}
for city, bbox in CITIES.items():
    if city in data and "--refresh" not in sys.argv:
        continue
    els = overpass(bbox, footways=(city == "venice"))  # Venice's calli are mapped as footways
    roads, water_l, water_a, parks = [], [], [], []
    for el in els:
        t, c = el.get("tags", {}), coords(el)
        if len(c) < 2:
            continue
        if "highway" in t:
            roads.append({"m": int(t["highway"] in MAJOR), "c": c})
        elif "waterway" in t:
            water_l.append(c)
        elif t.get("natural") == "water" and c[0] == c[-1]:
            water_a.append(c)
        elif c[0] == c[-1]:
            parks.append(c)
    data[city] = {"bbox": bbox, "roads": roads, "waterLines": water_l, "water": water_a, "parks": parks}
    print(city, {k: len(v) for k, v in data[city].items() if k != "bbox"}, file=sys.stderr)
    OUT.write_text(json.dumps(data, separators=(",", ":")))
    time.sleep(10)  # be polite to the public Overpass instance
print("KB:", OUT.stat().st_size // 1024)
