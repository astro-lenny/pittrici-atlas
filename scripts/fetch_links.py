"""Collect external links for every person with a Wikidata id: Wikipedia articles
(it/en/de/fr/es), authority files and art databases (Treccani DBI, ULAN, RKD, GND,
BnF, VIAF, ...), plus the Wikidata descriptions (CC0). Writes data/raw/wd_links.json."""
import json, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
UA = {"User-Agent": "artists-network-research/0.1 (research prototype)"}
WIKIS = ["itwiki", "enwiki", "dewiki", "frwiki", "eswiki"]
# External-id properties worth showing for early modern artists, with a display label.
PROPS = {
    "P1986": "Treccani, Dizionario Biografico", "P3365": "Treccani, Enciclopedia", "P245": "Getty ULAN",
    "P650": "RKD Artists", "P227": "GND", "P7902": "Deutsche Biographie", "P268": "BnF", "P214": "VIAF",
    "P1882": "Web Gallery of Art", "P1367": "Art UK", "P1711": "British Museum", "P3219": "Encyclopædia Universalis",
    "P1417": "Encyclopædia Britannica", "P2268": "Musée d'Orsay", "P4927": "Invaluable", "P8406": "Grove Art Online",
    "P10297": "Google Arts & Culture", "P1795": "Smithsonian American Art Museum", "P4659": "Musée d'Orsay (works)",
    "P6379": "has works in collection", "P2750": "Photographers' Identities", "P10706": "Art Institute of Chicago",
    "P4400": "National Gallery of Art", "P3634": "The Met", "P2041": "National Gallery of Victoria",
    "P1712": "Metacritic", "P7704": "Europeana entity", "P11938": "Prado",
}
PROPS.pop("P1712"); PROPS.pop("P6379")  # not person-level art links


def api(params):
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


def entities(ids, props):
    out = {}
    for i in range(0, len(ids), 50):
        out.update(api({"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]), "props": props,
                        "languages": "en|it|de|fr"})["entities"])
        time.sleep(2)
    return out


details = json.loads((RAW / "wd_details.json").read_text())
qids = sorted({d["qid"] for d in details})
formatters = {}
for pid, e in entities(sorted(PROPS), "claims").items():
    for st in e.get("claims", {}).get("P1630", []):
        v = st["mainsnak"].get("datavalue", {}).get("value")
        if v and pid not in formatters and st.get("rank") != "deprecated":
            formatters[pid] = v

links = {}
for q, e in entities(qids, "sitelinks/urls|claims|descriptions").items():
    if "missing" in e:
        continue
    out = [{"label": "Wikidata", "url": f"https://www.wikidata.org/wiki/{q}", "kind": "data"}]
    for w in WIKIS:
        s = e.get("sitelinks", {}).get(w)
        if s:
            out.append({"label": f"Wikipedia ({w[:2]})", "url": s["url"], "kind": "encyclopedia"})
    for pid, label in PROPS.items():
        for st in e.get("claims", {}).get(pid, [])[:1]:
            v = st["mainsnak"].get("datavalue", {}).get("value")
            if isinstance(v, str) and pid in formatters:
                out.append({"label": label, "url": formatters[pid].replace("$1", urllib.parse.quote(v, safe="/:_-()'")),
                            "kind": "authority" if pid in ("P227", "P268", "P214", "P245") else "art"})
    desc = {lang: d["value"] for lang, d in e.get("descriptions", {}).items()}
    links[q] = {"links": out, "desc": desc}

(RAW / "wd_links.json").write_text(json.dumps(links, ensure_ascii=False, indent=0))
n = sum(len(v["links"]) for v in links.values())
print(f"persons={len(links)} links={n} formatters={len(formatters)}")
