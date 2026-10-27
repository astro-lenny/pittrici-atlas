"""Teacher-pupil chains for the professional family trees: starting from the women artists,
walk up to UP generations of teachers and DOWN generations of pupils on Wikidata
(P1066 "student of" and P802 "student", read in both directions).
Writes data/raw/wd_lineage.json: {edges: [[teacher, pupil]], people: {qid: {...}}}."""
import json, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
UA = {"User-Agent": "artists-network-research/0.1 (research prototype)", "Accept": "application/sparql-results+json"}
UP, DOWN, MAX_PEOPLE = 4, 3, 2500


def sparql(q):
    body = urllib.parse.urlencode({"query": q}).encode()
    for attempt in range(6):
        try:
            req = urllib.request.Request("https://query.wikidata.org/sparql", data=body, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)["results"]["bindings"]
        except Exception as e:
            print("retry", attempt, e, file=sys.stderr); time.sleep(20 * (attempt + 1))
    raise RuntimeError("Wikidata query service unavailable")


def api(params):
    url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]}), timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(30 * (attempt + 1))
    raise RuntimeError("Wikidata API rate limit did not clear")


q = lambda uri: uri.rsplit("/", 1)[1]
_w = json.loads((RAW / "wd_women.json").read_text())
women = {q(r["a"]["value"]) for r in (_w["results"]["bindings"] if isinstance(_w, dict) else _w)}
edges = set()


def step(frontier, up):
    found = set()
    ids = sorted(frontier)
    for i in range(0, len(ids), 150):
        vals = " ".join("wd:" + x for x in ids[i:i + 150])
        if up:   # teachers of ?x
            rows = sparql(f"SELECT ?x ?t WHERE {{ VALUES ?x {{ {vals} }} {{ ?x wdt:P1066 ?t }} UNION {{ ?t wdt:P802 ?x }} }}")
        else:    # pupils of ?t
            rows = sparql(f"SELECT ?x ?t WHERE {{ VALUES ?t {{ {vals} }} {{ ?x wdt:P1066 ?t }} UNION {{ ?t wdt:P802 ?x }} }}")
        for r in rows:
            t, x = q(r["t"]["value"]), q(r["x"]["value"])
            if t.startswith("Q") and x.startswith("Q") and t != x:
                edges.add((t, x))
                found.add(t if up else x)
        time.sleep(3)
    return found


seen_up, frontier = set(women), set(women)
for g in range(UP):
    frontier = step(frontier, True) - seen_up
    seen_up |= frontier
    print(f"up {g + 1}: {len(frontier)} new teachers", file=sys.stderr)
seen_down, frontier = set(women), set(women)
for g in range(DOWN):
    frontier = step(frontier, False) - seen_down
    seen_down |= frontier
    print(f"down {g + 1}: {len(frontier)} new pupils", file=sys.stderr)
    if len(seen_up | seen_down) > MAX_PEOPLE:
        print("stopping: people cap reached", file=sys.stderr); break

people = {}
ids = sorted(seen_up | seen_down)
for i in range(0, len(ids), 50):
    ents = api({"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]), "props": "labels|claims|descriptions",
                "languages": "en|it"})["entities"]
    for k, e in ents.items():
        if "missing" in e:
            continue
        lab = e.get("labels", {}); de = e.get("descriptions", {})
        def yr(p):
            for st in e.get("claims", {}).get(p, []):
                v = st["mainsnak"].get("datavalue", {}).get("value")
                if isinstance(v, dict) and "time" in v:
                    return int(v["time"][:5].replace("+", ""))
        sex = next((st["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for st in e.get("claims", {}).get("P21", [])), None)
        people[k] = {"label": (lab.get("en") or lab.get("it") or {}).get("value", k), "birth": yr("P569"), "death": yr("P570"),
                     "sex": "F" if sex == "Q6581072" else ("M" if sex else None),
                     "desc": (de.get("en") or de.get("it") or {}).get("value", "")}
    time.sleep(1.5)

(RAW / "wd_lineage.json").write_text(json.dumps({"edges": sorted(edges), "people": people}, ensure_ascii=False))
print(f"edges={len(edges)} people={len(people)}")
