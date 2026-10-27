# Pittrici Atlas

**Where women artists of early modern Italy lived and travelled, 1480–1720, and who taught, married, employed and met them.**

<p align="center">
  <a href="https://astro-lenny.github.io/pittrici-atlas/"><img src="assets/launch-button.svg" alt="Launch the atlas" width="320"></a>
</p>

<p align="center"><sub>Runs in the browser, nothing to install · <a href="https://astro-lenny.github.io/pittrici-atlas/">astro-lenny.github.io/pittrici-atlas</a></sub></p>

---

## What it shows

- **A map that moves through time.** Play/pause through 1480–1720 at 1, 3 or 8 years per second, or jump from event to event. Each year shows where every artist was, who was connected to whom (teachers, family, marriages, patrons, academies, encounters) and recent travels.
- **Zoom from Europe into a city.** Zoomed out, each city is one bubble; in Bologna, Florence, Rome, Venice and Naples people move onto the actual buildings: Elisabetta Sirani's workshop, San Petronio, Casa Buonarroti, the Accademia di San Luca, Villa Benedetta and others.
- **One click per artist.** A popup with a summary of everything recorded about her, Wikidata descriptions in Italian, English, German and French, and every link found: Wikipedia (it/en/de/fr/es), Treccani, Grove, Getty ULAN, RKD, GND, BnF, VIAF, museum collections, plus the sources used here.
- **Certainty on every statement.** A green / yellow / red dot next to each date, place and relation; click it to see why. Green: given by a source checked online or by two or more references. Yellow: Wikidata only, a single reference, approximate, or a family tie dated only by the two lifetimes. Red: estimated, or no record for that year. Dots on the map carry a ring in the same colours.
- **Two views: Map and Lineage.** Tabs next to the title switch between space (the map) and time (the lineage). The Lineage view is a zoomable network of every artist, earlier at the top and later at the bottom, with lines from teacher to pupil, in the spirit of [AstroGen](https://astrogen.aas.org/front/index.php). Click a person to trace everyone she learned from and everyone who learned from her; artists with no recorded teacher or pupil stand in their own column. Linkable as `#lineage-elisabetta-sirani`.
- **States and (experimental) borders.** Each city's state is recorded year by year. Optional historical borders change with the year (18 periods), rebuilt from modern provinces; marked as experimental and explained on click.
- **Base maps:** Street (OpenStreetMap), Satellite (Esri), Terrain (OpenTopoMap) and Plain (built in, works offline).

## The data in numbers

| | |
|---|---|
| Women artists (born 1450–1660) | 72, of whom 67 on the map and 19 with a researched multi-city itinerary |
| People in total | 162 on the map, plus 33 more in the lineages |
| Dated stays | 140 curated from the literature, 443 from Wikidata |
| Relations | 192: 64 dated by a cited source, 89 family ties dated by lifetimes, 39 estimated |
| Places | 105, including 28 sites inside the five hotspot cities |
| Sources | 44, in Italian, English, French, German and Spanish |

The build refuses to produce the page if the data is too thin (see `DatabaseUnusableError` in [`scripts/build.py`](scripts/build.py)): fewer than 40 geolocated women, 15 multi-place itineraries, 150 mappable relations or 3 zoomable hotspots, or any dangling reference.

## Repository layout

```
docs/index.html          the app (generated; served by GitHub Pages)
app/template.html        app source: HTML, CSS and JavaScript (Leaflet + D3)
app/vendor/leaflet.css   inlined into the page at build time
data/*.csv               curated tables (edit these)
data/raw/                cached Wikidata extracts
data/build/              merged database: persons, places, stays, relations, yearly tracks, report, network.json
geo/                     derived geometry: basemap, OSM streets of the hotspot cities, border periods
scripts/                 fetch, build and validation scripts
```

### Curated tables

| File | Content |
|---|---|
| `persons.csv` | People added by hand and corrections to Wikidata (matched by `qid`) |
| `places.csv` | Cities and, inside hotspots, individual sites |
| `stays.csv` | Dated stays: person, place, from, to, kind, confidence, sources |
| `relations.csv` | Relations a → b: type, dates, confidence, sources |
| `sources.csv` | Bibliography; `status` says whether it was checked online or is a bibliographic reference |
| `states.csv` | States with colour and rulers |
| `city_states.csv` | State of each city by year interval |
| `province_states.csv`, `province_changes.csv` | State of each modern province over time (basis of the experimental borders) |

## Running and rebuilding

Open the app locally (map tiles need an http address, not `file://`):

```
python3 -m http.server 8791 --directory docs
```

then go to http://localhost:8791.

Rebuild after editing a table:

```
python3 scripts/build.py
```

Full pipeline from scratch (network access needed):

```
python3 scripts/fetch_wikidata.py      # women artists, relations, work places (cached; --refresh to re-query)
python3 scripts/fetch_links.py         # Wikipedia, Treccani, ULAN, RKD, GND, BnF, VIAF ... links
python3 scripts/fetch_lineage.py       # teacher–pupil chains, 4 generations up and 3 down
sh scripts/download_geo.sh             # raw Natural Earth and openpolis geometry (not kept in git)
python3 scripts/make_basemap.py        # -> geo/basemap.json
python3 scripts/fetch_osm.py           # OpenStreetMap streets of the hotspot centres -> geo/osm_cities.json
pip install -r requirements.txt        # shapely, only for the next step
python3 scripts/make_borders.py        # -> geo/borders.json (checks the province histories for consistency)
python3 scripts/build.py               # -> data/build/, docs/index.html
```

Everything except `make_borders.py` uses only the Python standard library.

## Publishing

The atlas is served by GitHub Pages from the `docs/` folder of `main` (**Settings → Pages → Deploy from a branch**).
After `python3 scripts/build.py`, commit `docs/index.html` and push; the live page updates within a minute or two.

## Limitations

- Most curated data rests on one or two references each, cited from the literature but not re-checked page by page; the certainty dots say so wherever it applies.
- About half of the painters have no recorded teacher or pupil yet; many trained in a father's or brother's workshop without dated sources. Malvasia, Baldinucci and the Dizionario Biografico degli Italiani are the obvious next sources.
- The historical borders are approximate by construction: each modern province goes to the state that held most of it, so enclaves and small fiefs (Mirandola, Piombino, Castro, the Stato dei Presidi) disappear, and areas outside today's Italy are not drawn.
- Coordinates of sites are placed by hand to within tens of metres.

## Licence

Code (scripts and app) is under the [MIT licence](LICENSE). The curated data is under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); third-party data keeps its own terms,
notably the OpenStreetMap street data under ODbL. Details and a suggested citation: [LICENSE-DATA.md](LICENSE-DATA.md).

## Sources

- People, relations, work places and external links: [Wikidata](https://www.wikidata.org/) (CC0).
- Curated stays and relations: the references in [`data/sources.csv`](data/sources.csv), among them Vasari, Malvasia, Ridolfi, Garrard, Christiansen & Mann, Murphy, Modesti, Perlingieri and the NMWA catalogue *Italian Women Artists from Renaissance to Baroque*.
- Coastlines, lakes and rivers: [Natural Earth](https://www.naturalearthdata.com/) (public domain).
- Italian regions and provinces: [openpolis/geojson-italy](https://github.com/openpolis/geojson-italy), from ISTAT boundaries; see that repository for terms.
- Street, water and park data of the hotspot cities (`geo/osm_cities.json`): © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, ODbL.
- Map tiles loaded live: OpenStreetMap, Esri World Imagery and OpenTopoMap, under their providers' terms.
- 1494 borders checked against William R. Shepherd, *Historical Atlas* (1923), via the [Perry-Castañeda Library](https://maps.lib.utexas.edu/maps/historical/history_shepherd_1923.html).
- Libraries: [Leaflet](https://leafletjs.com/) 1.9.4 and [D3](https://d3js.org/) 7.8.5, loaded from cdnjs.
