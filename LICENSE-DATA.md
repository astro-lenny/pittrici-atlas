# Data licence

## Curated data: CC BY 4.0

The curated tables and the database built from them are licensed under the
[Creative Commons Attribution 4.0 International licence (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
You may share and adapt them for any purpose, provided you give credit.

This covers:

- `data/*.csv` (people, places, stays, relations, sources, states, city and province state histories)
- `data/build/` (the merged database: persons, places, stays, relations, tracks, report, `network.json`)
- `assets/` and the texts in this repository

Please cite as:

> Lennart M. Boehm, *Pittrici Atlas: women artists of early modern Italy, 1480–1720*, 2026.
> https://github.com/astro-lenny/pittrici-atlas

## Third-party data under its own terms

| Files | Source | Licence |
|---|---|---|
| `data/raw/wd_*.json` and the Wikidata part of `data/build/` | [Wikidata](https://www.wikidata.org/) | CC0 1.0 (public domain) |
| `geo/osm_cities.json` (streets, water, parks of the hotspot cities) | © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/); adaptations must stay under ODbL |
| `geo/basemap.json` (coastlines, lakes, rivers) | [Natural Earth](https://www.naturalearthdata.com/) | Public domain |
| Region and province outlines in `geo/basemap.json` and `geo/borders.json` | [openpolis/geojson-italy](https://github.com/openpolis/geojson-italy), from ISTAT boundaries | Terms of that repository and of ISTAT |
| `app/vendor/leaflet.css`, Leaflet and D3 (loaded from cdnjs) | [Leaflet](https://leafletjs.com/), [D3](https://d3js.org/) | BSD-2-Clause, ISC |
| Map tiles loaded live (OpenStreetMap, Esri World Imagery, OpenTopoMap) | their providers | Not part of this repository; the providers' terms apply |

The historical assignments of provinces to states in `geo/borders.json` (which state held which
province when) are curated data under CC BY 4.0; the outline geometry they are drawn with keeps
the terms of its source above.
