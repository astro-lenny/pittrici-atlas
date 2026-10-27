"""Fetch the Wikidata backbone: women artists active in Italy (born 1450-1660),
their relations, the related people, and dated work locations.
Writes raw JSON into data/raw/. Re-run to refresh."""
import json, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
UA = {"User-Agent": "artists-network-research/0.1 (research prototype)",
      "Accept": "application/sparql-results+json"}
EXTRA_TITLES = [  # English Wikipedia titles of people/institutions the curated layer links to
    "Michelangelo", "Titian", "Galileo Galilei", "Anthony van Dyck", "Cassiano dal Pozzo",
    "Michelangelo Buonarroti the Younger", "Agostino Tassi", "Philip II of Spain",
    "Elisabeth of Valois", "Charles I of England", "Giorgio Vasari", "Fra Bartolomeo",
    "Alessandro Allori", "Guido Reni", "Pietro del Po", "Luca Longhi", "Francesco da Volterra",
    "Cosimo II de' Medici, Grand Duke of Tuscany", "Maria Maddalena of Austria", "Christine of France",
    "Ferdinando II de' Medici, Grand Duke of Tuscany", "Pope Clement VIII", "Pope Gregory XIII",
    "Annibale Carracci", "Ludovico Carracci", "Massimo Stanzione", "Giovanni Lanfranco",
    "Bernardino Campi", "Domenico Fetti", "Carlo Dolci", "Pietro Novelli", "Accademia di San Luca",
    "Accademia delle Arti del Disegno", "Gian Lorenzo Bernini", "Giulio Romano", "Orazio Gentileschi",
    "Simon Vouet", "Tintoretto", "Prospero Fontana", "Giovanni Andrea Sirani", "Marcantonio Raimondi",
    "Bernardino Gatti", "Padovanino", "Francesco Barberini (1597–1679)", "Marie de' Medici",
    "Henrietta Maria", "Fernando Afán de Ribera, 3rd Duke of Alcalá",
]


def sparql(q):
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": q})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.load(r)["results"]["bindings"]
        except Exception as e:  # rate limits / timeouts: back off and retry
            print("retry", attempt, e, file=sys.stderr); time.sleep(5 * (attempt + 1))
    raise RuntimeError("Wikidata query failed repeatedly")


def get_api(params):
    url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            print("429, waiting", file=sys.stderr); time.sleep(30 * (attempt + 1))
    raise RuntimeError("Wikidata API rate limit did not clear")


def qid(uri):
    return uri.rsplit("/", 1)[1]


cache = RAW / "wd_women.json"
if cache.exists() and "--refresh" not in sys.argv:  # the women query is heavy; reuse the last result
    women = json.loads(cache.read_text())
    women = women["results"]["bindings"] if isinstance(women, dict) else women
else:
    women = sparql((ROOT / "scripts/q_women.rq").read_text())
wq = sorted({qid(r["a"]["value"]) for r in women})
vals = " ".join("wd:" + x for x in wq)
rel_cache = RAW / "wd_rel.json"
if rel_cache.exists() and "--refresh" not in sys.argv:
    rel = json.loads(rel_cache.read_text())
    rel = rel["results"]["bindings"] if isinstance(rel, dict) else rel
else:
    rel = sparql(f"""SELECT ?a ?p ?o ?oLabel WHERE {{
 VALUES ?a {{ {vals} }}
 VALUES ?p {{ wdt:P1066 wdt:P802 wdt:P22 wdt:P25 wdt:P3373 wdt:P26 wdt:P1038 wdt:P737 wdt:P1327 wdt:P463 }}
 ?a ?p ?o . FILTER(isIRI(?o))
 SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,it". }} }}""")
rel = [r for r in rel if "/entity/Q" in r["o"]["value"]]

extra = {}
res = get_api({"action": "wbgetentities", "sites": "enwiki", "titles": "|".join(EXTRA_TITLES),
               "props": "labels|sitelinks", "languages": "en", "sitefilter": "enwiki"})
for q, e in res["entities"].items():
    if q.startswith("Q"):
        extra[e["sitelinks"]["enwiki"]["title"]] = {"qid": q, "label": e["labels"].get("en", {}).get("value")}
print("unresolved titles:", sorted(set(EXTRA_TITLES) - set(extra)), file=sys.stderr)

people = sorted(set(wq) | {qid(r["o"]["value"]) for r in rel} | {v["qid"] for v in extra.values()})


def entities(ids, props="labels|claims"):
    """wbgetentities (the entity API, not the query service), 50 ids per call."""
    out = {}
    for i in range(0, len(ids), 50):
        out.update(get_api({"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]),
                            "props": props, "languages": "en|it"})["entities"])
        time.sleep(2)
    return out


def label(e):
    lb = e.get("labels", {})
    return (lb.get("en") or lb.get("it") or {}).get("value", e.get("id"))


def vals_of(e, prop):
    res = []
    for st in e.get("claims", {}).get(prop, []):
        dv = st["mainsnak"].get("datavalue")
        if not dv:
            continue
        q = {k: [x.get("datavalue", {}).get("value") for x in v] for k, v in st.get("qualifiers", {}).items()}
        res.append((dv["value"], q))
    return res


def year(t):
    return int(t["time"][:5].replace("+", "")) if t and isinstance(t, dict) and "time" in t else None


ents = entities(people)
place_ids = set()
for e in ents.values():
    for prop in ("P19", "P20", "P937"):
        place_ids |= {v["id"] for v, _ in vals_of(e, prop)}
pents = entities(sorted(place_ids))
coords = {}
for pid, e in pents.items():
    c = vals_of(e, "P625")
    if c:
        coords[pid] = {"label": label(e), "lat": c[0][0]["latitude"], "lon": c[0][0]["longitude"]}

details, locs = [], []
for q, e in ents.items():
    if "missing" in e:
        continue
    first = lambda prop: (vals_of(e, prop) or [(None, {})])[0][0]
    bp, dp = first("P19"), first("P20")
    details.append({
        "qid": q, "label": label(e),
        "sex": (first("P21") or {}).get("id"), "inst": (first("P31") or {}).get("id"),
        "birth": year(first("P569")), "death": year(first("P570")),
        "birth_place": coords.get(bp["id"]) if bp else None,
        "death_place": coords.get(dp["id"]) if dp else None,
        "occupations": [v["id"] for v, _ in vals_of(e, "P106")],
    })
    for v, quals in vals_of(e, "P937"):
        if v["id"] in coords:
            locs.append({"qid": q, "place": v["id"], **coords[v["id"]],
                         "start": year((quals.get("P580") or [None])[0]),
                         "end": year((quals.get("P582") or [None])[0])})

for name, obj in [("wd_women", women), ("wd_rel", rel), ("wd_extra", extra),
                  ("wd_details", details), ("wd_loc", locs)]:
    (RAW / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=0))
print(f"women={len(wq)} relations={len(rel)} people={len(people)} detail_rows={len(details)} locations={len(locs)}")
for n, v in extra.items():
    print(f"  {n:45s} -> {v['qid']:10s} {v['label']}")
