# Contributing to the Pittrici Atlas

Corrections and additions are very welcome, especially from people who know the sources.

## Report an error or a gap

Open an [issue](https://github.com/astro-lenny/pittrici-atlas/issues/new) and say:

- which artist, place, date or relation is affected,
- what you think is right,
- the source: author, title, year and page, or a link.

A wrong or missing teacher, a stay in another city, a better date: all of these help.

## Add data yourself

The curated data is plain CSV in [`data/`](data/). Most contributions touch one of these:

| To add or fix | Edit |
|---|---|
| a stay (person, place, years) | `data/stays.csv` |
| a teacher, patron, marriage or other relation | `data/relations.csv` |
| a person missing from Wikidata, or a wrong Wikidata date | `data/persons.csv` |
| a city or a site inside a city | `data/places.csv` |
| the source you cite | `data/sources.csv` (add a short id and use it in the other tables) |

Every row needs a source id. Use `confidence` (`high`, `medium`, `low`) and the `note` column to say what is uncertain; the atlas shows this as the green, yellow and red certainty dots.

Then rebuild and check:

```
python3 scripts/build.py
python3 -m http.server 8791 --directory docs
```

The build stops with `DatabaseUnusableError` if a row points to an unknown person, place or source, so mistakes show up before anything is published. Commit the changed CSV files together with the regenerated `docs/index.html` and `data/build/`, and open a pull request.

## Code

The app is a single page, [`app/template.html`](app/template.html) (Leaflet + D3, no build tools); [`scripts/build.py`](scripts/build.py) merges the data and writes `docs/index.html`. Bug fixes and improvements are welcome as pull requests; please describe what you changed and how you checked it.

## Licence

By contributing you agree that code is released under the [MIT licence](LICENSE) and data under [CC BY 4.0](LICENSE-DATA.md).
