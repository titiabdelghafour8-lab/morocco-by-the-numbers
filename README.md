# Morocco by the Numbers

Twenty-one findings about Morocco, drawn from the government's open data portal [data.gov.ma](https://www.data.gov.ma) and checked against the original files.

**Live site:** https://titiabdelghafour8-lab.github.io/morocco-by-the-numbers/

## What's on the site

| Section | Findings |
|---|---|
| Land and water | The Souss river has almost stopped flowing · A drought year can cut the cereal harvest by two-thirds |
| Work | Youth unemployment at 37% · Graduates six times more likely to be unemployed than people with no diploma · Unemployment by region and province |
| Economy | GDP growth · Bank lending at its fastest since 2010 · Food inflation · Investment funds up 77% since 2020 · Startups concentrated in Casablanca and Rabat |
| Living | Health insurance coverage and finances · Public health centres per resident · Pension contributors per pensioner · Pension schemes paying out more than they collect · Internet subscriptions · Road deaths · Vehicles on the road |
| State | Appeal court caseload · Corruption Perceptions Index · Parliamentary questions by policy area |

### Project pages

| Page | Question | Data |
|---|---|---|
| [Water](https://titiabdelghafour8-lab.github.io/morocco-by-the-numbers/water.html) | How dry is the Souss now compared with the last 57 years, and does less rain explain the river's collapse? Drought index (SPI) since 1969, rainfall trend, rain-only model of the river. | Daily rain and river flow, Souss-Massa river basin agency |
| [Prices](https://titiabdelghafour8-lab.github.io/morocco-by-the-numbers/prices.html) | What is getting more expensive, where, and is it speeding up? Headline, food and 3-month annualised inflation, what drove it, the biggest movers, a city × spending-group heatmap, and a 3-month forecast shown only if it beats a naive benchmark. Refreshes monthly through the weekly sync. | HCP monthly consumer price index, 18 cities |
| [Parliament](https://titiabdelghafour8-lab.github.io/morocco-by-the-numbers/parliament.html) | What do MPs ask the government about, and how has that changed? A topic explorer over about 67,000 questions (Arabic topic model, reviewed topic names in Arabic, French and English) and the topics rising and falling. By topic and year only: no names. | House of Representatives written and oral questions |

Every chart links to the dataset it comes from. The About section at the bottom of the site explains sources, licence, personal data and the corrections made during the data audit.

## How it works

```
data.gov.ma  ->  check  ->  download  ->  parse  ->  analyse  ->  publish  ->  verify
 (watched        anything    raw files     one table   chart       data files   quoted numbers
  datasets)      changed?                  per file    series      and pages    vs data
```

The code is a Python package, `mbn`, in layers: `sources` (the portal and local files), `parsers` (one publisher's file into a table), `analyses` (tables into published figures), `findings` (the registry of what the site shows), `publish` (data files, pages, claims check) and a command line, `mbn`. Parsers and analyses do no input or output, so they are quick to test. For diagrams (C4 model: context, containers, components and the weekly sync), see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

The site is static: one HTML file per page, shared `site/assets/site.css` and `site/assets/charts.js`, and charts drawn as plain SVG. There is no framework and no server: GitHub Pages serves the `main` branch and republishes within a minute of every merge.

## Project layout

| Path | What it is |
|---|---|
| `index.html` | The findings page. Generated: edit `site/templates/index.html`, not this file. |
| `site/templates/` | Page text and layout, one template per page. The data goes in at `/*DATA*/`. |
| `site/assets/` | `site.css` (colours, light/dark theme, layout) and `charts.js` (chart library), shared by every page. |
| `src/mbn/sources/` | Portal client (`ckan.py`), downloader (`files.py`), local file store, census population. |
| `src/mbn/parsers/` | One module per publisher's file layout (HCP, river basin agency, parliament, ...). |
| `src/mbn/model/` | Shared vocabulary: claims, source links and pandera data contracts. |
| `src/mbn/analyses/` | Pure functions that turn tables into the published series. |
| `src/mbn/findings/` | `registry.py`: every finding with its datasets, source links and claims; `pages.py`: every page. |
| `src/mbn/publish/` | Data export, page rendering, claims check, comparison and the sync's publish-or-review decision. |
| `src/mbn/cli.py` | The `mbn` command. |
| `data/morocco_by_the_numbers.json` | All processed figures for the findings page, shared under the ODbL. |
| `data/datasets.txt` | The datasets the site uses. Generated from the registry with `mbn watchlist`. |
| `data/sources_state.json` | Last-modified time of each watched dataset, used by the sync. |
| `tests/` | `unit/`, `properties/` (hypothesis), `contracts/` (pandera), `features/` (Gherkin, pytest-bdd), `golden/`, `e2e/` (Playwright). |
| `.github/workflows/ci.yml` | Lint, types and every test layer on each pull request. |
| `.github/workflows/sync.yml` | The weekly automatic data sync. |

## Rebuild it yourself

You need Python 3.12 and [uv](https://docs.astral.sh/uv/). Run everything from the repository root:

```bash
uv sync                          # create .venv with the locked dependencies

uv run mbn download datasets     # the watched datasets, about 790 files, 90 MB
uv run mbn build datasets        # data/*.json
uv run mbn render                # index.html and the other pages
uv run mbn claims                # should end with "44/44 claims hold"
```

`mbn download --all` fetches the whole portal (about 800 MB). The downloader skips files it already has, so re-running it only fetches what changed. To preview the site, run `python -m http.server` and open http://localhost:8000.

## Tests

```bash
uv run pytest --ignore=tests/e2e                 # unit, property, contract, BDD and golden tests
uv run playwright install chromium               # once
uv run pytest tests/e2e                          # every page in a browser, desktop and phone
uv run ruff check src tests && uv run mypy       # lint and types
```

### The parliament topic model (offline)

The topic model needs an Arabic language model (CAMeL-BERT, about 0.44 GB from Hugging Face) and PyTorch, so it runs offline, not in CI or the weekly sync:

```bash
uv sync --extra topics
uv run mbn topics datasets --cache .cache/embeddings.npy   # 20-40 minutes on a laptop CPU
```

It writes `data/parliament/topic_model.json` and `data/parliament/assignments.csv` (question number, kind, date and topic: no names, no text). Topic names live in `data/parliament/topic_labels.json`. If a rerun changes the topics, `mbn build` stops until someone reads the new topics, updates the names and the file's `fingerprint`, and reviews the change in a pull request.

Set `MBN_DATASETS` to the downloaded `datasets` folder to also run the slow golden test that rebuilds the data file from the original spreadsheets and compares it byte for byte. CI runs everything except that test on every pull request, and requires at least 90% coverage of `parsers` and `analyses`.

## Automatic data sync

Every Monday at 06:23 UTC, `.github/workflows/sync.yml` runs `mbn check` to see whether any watched dataset changed on data.gov.ma. If nothing changed, it stops after a few seconds. If something changed, it downloads those datasets, rebuilds every page and runs the claims check:

- **Every quoted number still holds:** the job opens a pull request labelled `data-sync` with the new figures and starts CI on it. Merge it once CI is green; the site updates within a minute. (Set the repository variable `SYNC_AUTO_MERGE` to `true`, and allow auto-merge in the repository settings, to let these pull requests merge themselves when CI passes.)
- **A quoted number no longer holds:** the live site is left as it is. The job pushes a `data-review-YYYYMMDD` branch and opens an issue labelled `data-review` that lists what changed.

While a `data-sync` pull request or a `data-review` issue is open, the weekly sync skips its rebuild so it doesn't open a second one for the same change. To pick up an update before Monday, open the **Actions** tab, choose **Data sync** and click **Run workflow**.

### When a `data-review` issue opens

1. Read the issue: it lists the datasets that changed, the figures that moved and the claims that failed.
2. Check out the review branch named in the issue.
3. Update the affected sentences in `site/templates/`, and the expected values for the same claims in `src/mbn/findings/`.
4. Run `uv run mbn render` and `uv run mbn claims` until every claim holds.
5. Open a pull request from the branch, merge it when CI is green, and close the issue.

## Adding a finding

1. Add a parser for the file layout in `src/mbn/parsers/` (with a test on a trimmed copy of a real file in `tests/fixtures/`), and its series in `src/mbn/analyses/`.
2. Add a `Finding` to `src/mbn/findings/registry.py` with its dataset patterns, source links and a `Claim` for every number quoted in the text.
3. Add a `<section class="ch">` with its text and a chart call in `site/templates/index.html`.
4. Run `uv run mbn watchlist`, `build`, `render` and `claims`, run the tests, then open a pull request.

## Data, licence and personal data

- The source data is published on data.gov.ma under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). The processed figures in `data/morocco_by_the_numbers.json` are shared under the same licence.
- Regional population for per-resident rates comes from HCP's [2024 census legal population](https://www.hcp.ma/Population-legale-du-Royaume-du-Maroc-repartie-par-regions-provinces-et-prefectures-et-communes-selon-les-resultats-du_a3974.html).
- The code and page design are under the MIT licence (see `LICENSE`).
- Some portal datasets name individuals, such as members of parliament and startup founders. This project only publishes counts and totals. No names, contact details or other personal information are kept in `data/` or shown on the site.
- This is an independent project. It is not produced or endorsed by the Moroccan government or any data publisher.

To reuse the figures, credit both the original publisher and data.gov.ma, for example: *"Source: HCP via data.gov.ma (ODbL), processed by Morocco by the Numbers."*

## Known caveats

- HCP changed its employment survey method in 2017, so job comparisons start in 2017 and the charts mark the break.
- Inflation and growth rates are calculated from published indices. Food inflation (February 2023) and GDP (second quarter of 2020) differ between HCP's first announcements and the revised series on the portal; the site gives both.
- The startup database merges four overlapping lists, and parliamentary files overlap. Both are deduplicated.
- Public-service counts are facilities, not beds or staff. They exclude private clinics, and the hospital list has no university hospitals.
- Provincial unemployment rates come from a sample survey and can move a lot from one year to the next.
- Parliamentary questions are grouped into policy areas by keyword, because ministry names changed in 2021.

## Corrections

Found a mistake? [Open an issue](https://github.com/titiabdelghafour8-lab/morocco-by-the-numbers/issues) with the chart, the number and, if you can, the source that disagrees.
