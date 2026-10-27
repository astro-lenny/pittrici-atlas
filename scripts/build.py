"""Merge the Wikidata backbone (data/raw) with the curated tables (data/*.csv) into one
normalised database (data/build/), validate it, and render the web app:
docs/index.html (standalone page, served by GitHub Pages) and dist/artifact.html (body-only, for the Claude artifact).

Raises DatabaseUnusableError when the merged data cannot support the visualisation:
too few geolocated women artists, too few dated itineraries or relations, dangling
references, or hotspots without enough sites to zoom into.
"""
import csv, json, math, re, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, RAW, OUT = ROOT / "data", ROOT / "data/raw", ROOT / "data/build"
YEAR_MIN, YEAR_MAX = 1480, 1720
FEMALE = "Q6581072"
HOTSPOTS = ["bologna", "florence", "rome", "venice", "naples"]

# Usability thresholds: below these the app would show an anecdote, not a network.
MIN_WOMEN_GEOLOCATED = 40
MIN_WOMEN_ITINERARY = 15      # women with >= 2 distinct places over their life
MIN_RELATIONS = 150
MIN_SITES_PER_HOTSPOT = 3
MIN_HOTSPOTS = 3

# Kind priority when several stays cover the same year (higher wins).
KIND_RANK = {"visit": 9, "commission": 8, "burial": 8, "court": 7, "convent": 7, "workshop": 7,
             "member": 5, "training": 6, "residence": 4, "active": 3, "birth": 2, "death": 2}
WD_REL = {"P1066": ("teacher", True), "P802": ("teacher", False), "P22": ("parent", True),
          "P25": ("parent", True), "P3373": ("sibling", False), "P26": ("spouse", False),
          "P1038": ("relative", False), "P737": ("influence", True), "P1327": ("collaborator", False),
          "P463": ("member", False)}
# For "a P b": reversed=True means the edge runs b -> a (b taught/parented/influenced a).


class DatabaseUnusableError(RuntimeError):
    pass


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def read_csv(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_int(v):
    return int(v) if v not in (None, "") else None


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def load_bindings(name):
    d = json.loads((RAW / name).read_text())
    return d["results"]["bindings"] if isinstance(d, dict) else d


def qid(uri):
    return uri.rsplit("/", 1)[1]


errors, warnings = [], []

# --- sources -----------------------------------------------------------------------------
sources = {r["id"]: r for r in read_csv("sources.csv")}

# --- places ------------------------------------------------------------------------------
places = {}
for r in read_csv("places.csv"):
    places[r["id"]] = {"id": r["id"], "name": r["name_en"], "name_it": r["name_it"], "kind": r["kind"],
                       "city": r["city"] or None, "lat": float(r["lat"]), "lon": float(r["lon"]),
                       "note": r["notes"], "origin": "curated"}
cities = [p for p in places.values() if p["kind"] == "city"]


def place_for(label, lat, lon):
    """Snap a Wikidata place to a curated city within 20 km, else register it as a new city."""
    best = min(cities, key=lambda c: km((lat, lon), (c["lat"], c["lon"])))
    if km((lat, lon), (best["lat"], best["lon"])) <= 20:
        return best["id"]
    pid = "wd-" + slug(label)
    if pid not in places:
        places[pid] = {"id": pid, "name": label, "name_it": label, "kind": "city", "city": None,
                       "lat": round(lat, 4), "lon": round(lon, 4), "note": "", "origin": "wikidata"}
        cities.append(places[pid])
    return pid


# --- persons -----------------------------------------------------------------------------
women_q = {qid(r["a"]["value"]) for r in load_bindings("wd_women.json")}
details = json.loads((RAW / "wd_details.json").read_text())
curated_persons = read_csv("persons.csv")
id_for_qid = {r["qid"]: r["id"] for r in curated_persons if r["qid"]}

persons = {}
for d in details:
    if d["inst"] and d["inst"] != "Q5":  # institutions (academies) are kept as organisations
        kind = "org"
    else:
        kind = "person"
    pid = id_for_qid.get(d["qid"]) or slug(d["label"])
    if pid in persons:
        pid = f"{pid}-{d['qid'].lower()}"
    persons[pid] = {"id": pid, "qid": d["qid"], "name": d["label"], "kind": kind,
                    "sex": "F" if d["sex"] == FEMALE else ("M" if d["sex"] else None),
                    "birth": d["birth"], "death": d["death"], "focus": d["qid"] in women_q,
                    "role": "artist" if d["qid"] in women_q else None, "note": "",
                    "_bp": d["birth_place"], "_dp": d["death_place"]}
pid_of_qid = {p["qid"]: p["id"] for p in persons.values()}

for r in curated_persons:
    pid = r["id"]
    p = persons.setdefault(pid, {"id": pid, "qid": r["qid"] or None, "name": r["name"], "kind": "person",
                                 "sex": None, "birth": None, "death": None, "focus": False,
                                 "role": None, "note": "", "_bp": None, "_dp": None})
    for k in ("name", "role", "note"):
        if r[k]:
            p[k] = r[k]
    for k in ("birth", "death"):
        if r[k]:
            p[k] = int(r[k])
    if r["sex"]:
        p["sex"] = r["sex"]
for p in persons.values():
    if p["kind"] == "org":
        p["role"] = "institution"
    elif not p["role"]:
        p["role"] = "artist"  # relations of women artists are overwhelmingly painters/engravers
    p["inferred_life"] = False
    if p["kind"] == "person" and p["birth"] is None and p["death"] is not None:
        p["birth"], p["inferred_life"] = p["death"] - 55, True
    if p["kind"] == "person" and p["birth"] is not None and p["death"] is None:
        p["death"], p["inferred_life"] = min(p["birth"] + 60, YEAR_MAX), True
    if p["birth"] and p["death"] and p["death"] < p["birth"]:
        errors.append(f"person {p['id']}: death {p['death']} before birth {p['birth']}")

# --- stays -------------------------------------------------------------------------------
stays = []


def check_sources(ids, where):
    for s in ids:
        if s not in sources:
            errors.append(f"{where}: unknown source '{s}'")


for i, r in enumerate(read_csv("stays.csv"), 2):
    where = f"stays.csv:{i}"
    if r["person"] not in persons:
        errors.append(f"{where}: unknown person '{r['person']}'"); continue
    if r["place"] not in places:
        errors.append(f"{where}: unknown place '{r['place']}'"); continue
    a, b = int(r["from"]), int(r["to"])
    if b < a:
        errors.append(f"{where}: to < from")
    srcs = [s for s in r["sources"].split(";") if s]
    if not srcs:
        errors.append(f"{where}: no source")
    check_sources(srcs, where)
    p = persons[r["person"]]
    if p["birth"] and a < p["birth"] - 1 or p["death"] and b > p["death"] + 1:
        warnings.append(f"{where}: stay {a}-{b} outside life {p['birth']}-{p['death']} of {p['id']}")
    stays.append({"person": r["person"], "place": r["place"], "from": a, "to": b, "kind": r["kind"],
                  "confidence": r["confidence"], "sources": srcs, "note": r["note"], "origin": "curated"})

for p in persons.values():  # birth and death places from Wikidata
    for key, kind, yr in (("_bp", "birth", p["birth"]), ("_dp", "death", p["death"])):
        loc = p.pop(key)
        if loc and yr and not p["inferred_life"]:
            stays.append({"person": p["id"], "place": place_for(loc["label"], loc["lat"], loc["lon"]),
                          "from": yr, "to": yr, "kind": kind, "confidence": "medium", "sources": ["WD"],
                          "note": "", "origin": "wikidata"})

has_curated = {s["person"] for s in stays if s["origin"] == "curated"}
for r in json.loads((RAW / "wd_loc.json").read_text()):  # P937 work locations
    pid = pid_of_qid.get(r["qid"])
    p = persons.get(pid)
    if not p or not p["birth"]:
        continue
    if pid in has_curated and not r["start"]:
        continue  # an undated work place would smear over a researched itinerary
    a = r["start"] or p["birth"] + 18
    b = r["end"] or p["death"] or a
    stays.append({"person": pid, "place": place_for(r["label"], r["lat"], r["lon"]), "from": a, "to": b,
                  "kind": "active", "confidence": "medium" if r["start"] else "low", "sources": ["WD"],
                  "note": "Wikidata work location" + ("" if r["start"] else " (undated; spread over career)"),
                  "origin": "wikidata"})

# --- relations ---------------------------------------------------------------------------
relations = {}


def add_rel(a, b, typ, frm, to, conf, srcs, note, origin):
    key = (a, b, typ) if typ not in ("sibling", "spouse", "relative", "friend", "collaborator") else (*sorted((a, b)), typ)
    if key in relations and relations[key]["origin"] == "curated" and origin != "curated":
        return
    relations[key] = {"a": key[0], "b": key[1], "type": typ, "from": frm, "to": to, "confidence": conf,
                      "sources": srcs, "note": note, "origin": origin, "inferred_dates": frm is None}


for r in load_bindings("wd_rel.json"):
    pa, pb = pid_of_qid.get(qid(r["a"]["value"])), pid_of_qid.get(qid(r["o"]["value"]))
    if not pa or not pb or pa == pb:
        continue
    typ, rev = WD_REL[qid(r["p"]["value"])]
    a, b = (pb, pa) if rev else (pa, pb)
    add_rel(a, b, typ, None, None, "medium", ["WD"], "", "wikidata")

for i, r in enumerate(read_csv("relations.csv"), 2):
    where = f"relations.csv:{i}"
    bad = [x for x in (r["a"], r["b"]) if x not in persons]
    if bad:
        errors.append(f"{where}: unknown person(s) {bad}"); continue
    srcs = [s for s in r["sources"].split(";") if s]
    if not srcs:
        errors.append(f"{where}: no source")
    check_sources(srcs, where)
    add_rel(r["a"], r["b"], r["type"], to_int(r["from"]), to_int(r["to"]), r["confidence"], srcs, r["note"], "curated")


LIFETIME_TYPES = {"parent", "sibling", "relative"}  # these simply last as long as both lives overlap


def infer_dates(rel):
    """Fill missing dates. dating = 'source' (dates from a cited source), 'lifetimes' (family ties:
    the span is the overlap of the two lives) or 'inferred' (estimated; drawn dashed).
    Returns False when the two lives never overlap, i.e. the relation is impossible as recorded."""
    a, b = persons[rel["a"]], persons[rel["b"]]
    lo = max(x for x in (a["birth"], b["birth"], YEAR_MIN) if x is not None)
    hi = min(x for x in (a["death"], b["death"], YEAR_MAX) if x is not None)
    if rel["from"] is not None and rel["to"] is not None:
        rel["dating"] = "source"
        return True
    if a["kind"] == "org":  # institutions have no lifetime
        lo = max(x for x in (b["birth"], YEAR_MIN) if x is not None)
        hi = min(x for x in (b["death"], YEAR_MAX) if x is not None)
    if lo > hi:  # check against the real lives, not the map window
        if max(x for x in (a["birth"], b["birth"]) if x is not None) > min(x for x in (a["death"], b["death"]) if x is not None):
            return False
        lo = hi = min(max(lo, YEAR_MIN), YEAR_MAX)  # real but outside the mapped years
        rel["dating"] = "lifetimes" if rel["type"] in LIFETIME_TYPES else "inferred"
        rel["from"], rel["to"] = lo, hi
        return True
    t = rel["type"]
    rel["dating"] = "lifetimes" if t in LIFETIME_TYPES else "inferred"
    if t == "teacher" and b["birth"]:
        frm = max(b["birth"] + 12, (a["birth"] or lo) + 18 if a["kind"] == "person" else lo)
        frm, to = frm, frm + 8
    elif t == "parent" and b["birth"]:
        frm, to = b["birth"], hi
    elif t == "spouse":
        frm, to = lo + 20, hi
    elif t == "member":
        frm, to = (a["birth"] or lo) + 25, hi
    elif t == "influence" and b["birth"]:
        frm, to = b["birth"] + 15, hi
    else:
        frm, to = lo, hi
    frm = rel["from"] if rel["from"] is not None else frm
    to = rel["to"] if rel["to"] is not None else to
    rel["from"], rel["to"] = max(lo, min(frm, hi)), max(lo, min(to, hi))  # stay inside both lives
    return True


impossible = [k for k, rel in relations.items() if not infer_dates(rel)]
for k in impossible:
    rel = relations.pop(k)
    why = "posthumous influence, not drawable" if rel["type"] == "influence" else "lifetimes do not overlap"
    warnings.append(f"dropped {rel['origin']} relation {rel['a']} -{rel['type']}-> {rel['b']}: {why} "
                    f"({persons[rel['a']]['birth']}-{persons[rel['a']]['death']} vs {persons[rel['b']]['birth']}-{persons[rel['b']]['death']})")
for rel in relations.values():
    rel["inferred_dates"] = rel["dating"] == "inferred"

# --- yearly positions --------------------------------------------------------------------
by_person = defaultdict(list)
for s in stays:
    by_person[s["person"]].append(s)


def rank(s):
    return (KIND_RANK.get(s["kind"], 1), s["origin"] == "curated", places[s["place"]]["kind"] == "site")


tracks = {}
for pid, ss in by_person.items():
    p = persons[pid]
    if not p["birth"]:
        continue
    life = range(max(p["birth"], YEAR_MIN), min(p["death"] or p["birth"] + 60, YEAR_MAX) + 1)
    segs, last = [], None
    for y in life:
        cover = [s for s in ss if s["from"] <= y <= s["to"]]
        if cover:
            best = max(cover, key=rank)
            cur = (best["place"], best["kind"], False)
        elif last:
            cur = (last[0], last[1], True)  # carried forward: no record for this year
        else:
            first = min(ss, key=lambda s: s["from"])
            cur = (first["place"], first["kind"], True)
        if segs and segs[-1][2:] == [cur[0], cur[1], cur[2]] and segs[-1][1] == y - 1:
            segs[-1][1] = y
        else:
            segs.append([y, y, cur[0], cur[1], cur[2]])
        last = cur
    tracks[pid] = segs

# --- states: which state each city belonged to, by year ---------------------------------
states = {r["id"]: r for r in read_csv("states.csv")}
city_states = []
for i, r in enumerate(read_csv("city_states.csv"), 2):
    where = f"city_states.csv:{i}"
    if r["place"] not in places:
        errors.append(f"{where}: unknown place '{r['place']}'"); continue
    if r["state"] not in states:
        errors.append(f"{where}: unknown state '{r['state']}'"); continue
    srcs = [x for x in r["sources"].split(";") if x]
    check_sources(srcs, where)
    city_states.append({"place": r["place"], "state": r["state"], "from": int(r["from"]), "to": int(r["to"]),
                        "confidence": r["confidence"], "sources": srcs, "note": r["note"]})
used = defaultdict(set)  # city -> years in which someone is there
for pid, segs in tracks.items():
    for a0, b0, pl, *_ in segs:
        c = places[pl]["city"] or pl
        used[c].update(range(a0, b0 + 1))
for c, ys in used.items():
    covered = {y for cs in city_states if cs["place"] == c for y in range(cs["from"], cs["to"] + 1)}
    gap = sorted(ys - covered)
    if gap:
        warnings.append(f"city {c}: no state recorded for {len(gap)} occupied years ({gap[0]}-{gap[-1]})")

# --- validation --------------------------------------------------------------------------
women = [p for p in persons.values() if p["focus"]]
women_geo = [p for p in women if p["id"] in tracks]
women_itin = [p for p in women_geo
              if len({places[s[2]]["city"] or s[2] for s in tracks[p["id"]]}) >= 2]
rel_ok = [r for r in relations.values() if r["a"] in tracks and r["b"] in tracks]
sites_per = Counter(p["city"] for p in places.values() if p["kind"] == "site")
present = defaultdict(set)
for pid, segs in tracks.items():
    for s in segs:
        present[places[s[2]]["city"] or s[2]].add(pid)
hot_ok = [h for h in HOTSPOTS if sites_per[h] >= MIN_SITES_PER_HOTSPOT and len(present[h]) >= 5]

report = {
    "women_artists": len(women), "women_geolocated": len(women_geo), "women_with_itinerary": len(women_itin),
    "persons_total": len(persons), "persons_on_map": len(tracks), "relations_total": len(relations),
    "relations_both_on_map": len(rel_ok), "relations_curated": sum(r["origin"] == "curated" for r in relations.values()),
    "relations_inferred_dates": sum(r["inferred_dates"] for r in relations.values()),
    "relations_dating": dict(Counter(r["dating"] for r in relations.values())),
    "relations_dropped_impossible": len(impossible),
    "stays_curated": sum(s["origin"] == "curated" for s in stays), "stays_wikidata": sum(s["origin"] == "wikidata" for s in stays),
    "places": len(places), "sites": sum(p["kind"] == "site" for p in places.values()),
    "hotspots_usable": hot_ok, "warnings": len(warnings),
}
checks = [
    (len(women_geo) >= MIN_WOMEN_GEOLOCATED, f"only {len(women_geo)} geolocated women artists (need {MIN_WOMEN_GEOLOCATED})"),
    (len(women_itin) >= MIN_WOMEN_ITINERARY, f"only {len(women_itin)} women with a multi-place itinerary (need {MIN_WOMEN_ITINERARY})"),
    (len(rel_ok) >= MIN_RELATIONS, f"only {len(rel_ok)} mappable relations (need {MIN_RELATIONS})"),
    (len(hot_ok) >= MIN_HOTSPOTS, f"only {len(hot_ok)} zoomable hotspots {hot_ok} (need {MIN_HOTSPOTS})"),
]
for w in warnings:
    print("warning:", w, file=sys.stderr)
failed = errors + [msg for ok, msg in checks if not ok]
if failed:
    raise DatabaseUnusableError("The database is not usable:\n  - " + "\n  - ".join(failed))

# --- outputs -----------------------------------------------------------------------------
OUT.mkdir(exist_ok=True)


def write(name, rows, cols):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ";".join(v) if isinstance(v, list) else v for k, v in r.items()})


write("persons.csv", persons.values(), ["id", "qid", "name", "kind", "sex", "birth", "death", "inferred_life", "focus", "role", "note"])
write("places.csv", places.values(), ["id", "name", "name_it", "kind", "city", "lat", "lon", "origin", "note"])
write("stays.csv", stays, ["person", "place", "from", "to", "kind", "confidence", "sources", "origin", "note"])
write("relations.csv", relations.values(), ["a", "b", "type", "from", "to", "dating", "inferred_dates", "confidence", "sources", "origin", "note"])
write("tracks.csv", [{"person": pid, "from": s[0], "to": s[1], "place": s[2], "kind": s[3], "carried": s[4]}
                     for pid, segs in tracks.items() for s in segs], ["person", "from", "to", "place", "kind", "carried"])

bundle = {
    "range": [YEAR_MIN, YEAR_MAX], "hotspots": HOTSPOTS, "report": report,
    "persons": [{k: p[k] for k in ("id", "qid", "name", "kind", "sex", "birth", "death", "focus", "role", "note", "inferred_life")}
                for p in persons.values() if p["id"] in tracks],
    "places": list(places.values()),
    "tracks": tracks,
    "stays": [s for s in stays if s["person"] in tracks],
    "relations": rel_ok,
    "sources": list(sources.values()),
    "basemap": json.loads((ROOT / "geo/basemap.json").read_text()),
    "osm": json.loads((ROOT / "geo/osm_cities.json").read_text()),
    "states": list(states.values()), "cityStates": city_states,
    "borders": json.loads((ROOT / "geo/borders.json").read_text()),
}
# professional family trees: curated + Wikidata teacher relations, plus Wikidata chains beyond the atlas
lin_raw = json.loads((RAW / "wd_lineage.json").read_text()) if (RAW / "wd_lineage.json").exists() else {"edges": [], "people": {}}
on_map = {p["id"] for p in bundle["persons"]}
lin_nodes, lin_edges = {}, {}


def lin_id(q):
    pid = pid_of_qid.get(q)
    if pid:
        if pid not in on_map:
            p = persons[pid]
            lin_nodes[pid] = {"id": pid, "qid": q, "name": p["name"], "birth": p["birth"], "death": p["death"], "sex": p["sex"], "desc": ""}
        return pid
    w = lin_raw["people"].get(q)
    if not w:
        return None
    lin_nodes.setdefault(q, {"id": q, "qid": q, "name": w["label"], "birth": w["birth"], "death": w["death"], "sex": w["sex"], "desc": w["desc"]})
    return q


for rel in list(relations.values()):
    if rel["type"] == "teacher":
        for x in (rel["a"], rel["b"]):
            if x not in on_map:
                p = persons[x]
                lin_nodes[x] = {"id": x, "qid": p["qid"], "name": p["name"], "birth": p["birth"], "death": p["death"], "sex": p["sex"], "desc": ""}
        lin_edges[(rel["a"], rel["b"])] = {"t": rel["a"], "p": rel["b"], "origin": rel["origin"], "dating": rel["dating"],
                                           "from": rel["from"], "to": rel["to"], "confidence": rel["confidence"],
                                           "sources": rel["sources"], "note": rel["note"]}
for t, x in lin_raw["edges"]:
    a, b = lin_id(t), lin_id(x)
    if a and b and (a, b) not in lin_edges:
        lin_edges[(a, b)] = {"t": a, "p": b, "origin": "wikidata-lineage", "dating": "none", "sources": ["WD"],
                             "confidence": "medium", "note": ""}
bundle["lineage"] = {"nodes": list(lin_nodes.values()), "edges": list(lin_edges.values())}
report["lineage_edges"], report["lineage_extra_people"] = len(lin_edges), len(lin_nodes)

links = json.loads((RAW / "wd_links.json").read_text()) if (RAW / "wd_links.json").exists() else {}
for bp in bundle["persons"]:
    l = links.get(bp["qid"] or "", {})
    bp["links"], bp["desc"] = l.get("links", []), l.get("desc", {})
(OUT / "report.json").write_text(json.dumps(report, indent=2))
GEOMETRY = {"basemap", "osm", "borders"}  # the data export leaves out map geometry (it lives in geo/)
(OUT / "network.json").write_text(json.dumps({k: v for k, v in bundle.items() if k not in GEOMETRY}, ensure_ascii=False))
tpl = (ROOT / "app/template.html").read_text()
tpl = tpl.replace("/*__LEAFLET_CSS__*/", (ROOT / "app/vendor/leaflet.css").read_text())
page = tpl.replace("/*__DATA__*/null", json.dumps(bundle, ensure_ascii=False, separators=(",", ":")))
(ROOT / "dist").mkdir(exist_ok=True)
(ROOT / "dist/artifact.html").write_text(page)  # the artifact viewer adds doctype, head and body itself
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs/index.html").write_text(
    '<!doctype html>\n<html lang="en">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' + page)
(ROOT / "docs/.nojekyll").write_text("")
print(json.dumps(report, indent=2))
