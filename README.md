# Morocco by the Numbers

Eighteen findings about Morocco, drawn from the government's open data portal [data.gov.ma](https://www.data.gov.ma) and checked against the original files.

**Live site:** https://titiabdelghafour8-lab.github.io/morocco-by-the-numbers/

## What's on the site

| Section | Findings |
|---|---|
| Land and water | The Souss river has almost stopped flowing · A drought year can cut the cereal harvest by two-thirds |
| Work | Youth unemployment at 37% · Graduates six times more likely to be unemployed than people with no diploma · Unemployment by region and province |
| Economy | GDP growth · Bank lending at its fastest since 2010 · Food inflation · Investment funds up 77% since 2020 · Startups concentrated in Casablanca and Rabat |
| Living | Health insurance coverage · Public health centres per resident · Pension contributors per pensioner · Internet subscriptions · Road deaths |
| State | Appeal court caseload · Corruption Perceptions Index · Parliamentary questions by policy area |

Every chart links to the dataset it comes from. The About section at the bottom of the site explains sources, licence, personal data and the corrections made during the data audit.

## How it works

```
data.gov.ma  ->  download  ->  extract  ->  build  ->  pack  ->  render  ->  check
 (46 datasets)    raw files     clean       chart      one data    index.html  quoted numbers
                                tables      series     file                    vs data
```

The site is a single static `index.html` with the data embedded and charts drawn as plain SVG. There is no framework and no server: GitHub Pages serves the file from the `main` branch and republishes it within a minute of every push.

## Project layout

| Path | What it is |
|---|---|
| `index.html` | The published site. Generated: edit `scripts/template.html`, not this file. |
| `scripts/template.html` | Page text, layout and chart code. The data goes in at `/*DATA*/`. |
| `scripts/datasets.txt` | The data.gov.ma datasets the site uses (patterns on dataset names). |
| `scripts/00_check_updates.py` | Asks the portal whether any watched dataset changed. |
| `scripts/01_download.py` | Downloads datasets into `datasets/` (not committed). |
| `scripts/02_extract.py`, `02b_…`, `02c_…` | Read the original spreadsheets into intermediate tables. |
| `scripts/03_build.py`, `03b_…` | Turn those tables into chart series. |
| `scripts/04_pack.py` | Combines everything, with source links, into `data/morocco_by_the_numbers.json`. |
| `scripts/05_render.py` | Writes `index.html` from the template and the data. |
| `scripts/06_compare.py` | Lists which figures changed between two data files (used by the sync). |
| `scripts/07_check_claims.py` | Checks that every number quoted in the text still matches the data. |
| `data/morocco_by_the_numbers.json` | All processed figures, shared under the ODbL. |
| `data/sources_state.json` | Last-modified time of each watched dataset, used by the sync. |
| `.github/workflows/sync.yml` | The weekly automatic data sync. |

## Rebuild it yourself

You need Python 3.12 or later. Run everything from the repository root:

```bash
pip install -r requirements.txt

python scripts/01_download.py datasets scripts/datasets.txt   # about 790 files, 90 MB
python scripts/02_extract.py datasets
python scripts/02b_extract_more.py datasets
python scripts/02c_extract_services.py datasets
python scripts/03_build.py datasets
python scripts/03b_build_more.py
python scripts/04_pack.py datasets
python scripts/05_render.py
python scripts/07_check_claims.py          # should end with "29/29 claims hold"
```

Leave out `scripts/datasets.txt` to download the whole portal (about 800 MB). The downloader skips files it already has, so re-running it only fetches what changed. Intermediate files (`raw*.json`, `site_data*.json`, `data.min.json`) are temporary and ignored by git.

To preview the site, run `python -m http.server` and open http://localhost:8000.

## Automatic data sync

Every Monday at 06:23 UTC, `.github/workflows/sync.yml` checks whether any watched dataset changed on data.gov.ma. If nothing changed, it stops after a few seconds. If something changed, it downloads those datasets, rebuilds every figure and runs the claims check:

- **Every quoted number still holds:** the new figures are published to the live site automatically.
- **A quoted number no longer holds:** the live site is left as it is. The job pushes a `data-review-YYYYMMDD` branch and opens an issue labelled `data-review` that lists what changed.

To pick up an update before Monday, open the **Actions** tab, choose **Data sync** and click **Run workflow**.

### When a `data-review` issue opens

1. Read the issue: it lists the datasets that changed, the figures that moved and the claims that failed.
2. Check out the review branch named in the issue.
3. Update the affected sentences in `scripts/template.html`, and the expected values for the same claims in `scripts/07_check_claims.py`.
4. Run `python scripts/05_render.py` and `python scripts/07_check_claims.py` until every claim holds.
5. Merge the branch into `main` and close the issue. The site updates within a minute, and the sync resumes the following Monday.

While a `data-review` issue is open, the weekly sync skips its rebuild so it doesn't open a second issue for the same change.

## Adding a finding

1. Add the dataset name to `scripts/datasets.txt`.
2. Read it in one of the extract scripts and add its series in `scripts/04_pack.py`, with a `src` entry for the source link.
3. Add a `<section class="ch">` with its text and a chart call in `scripts/template.html`.
4. Add a claim for every number quoted in the new text to `scripts/07_check_claims.py`.
5. Rebuild, check, preview, then push.

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
