# Morocco by the Numbers

Seventeen findings from Morocco's open data portal, [data.gov.ma](https://www.data.gov.ma), grouped into land and water, work, the economy, daily life and the state.

**Live site:** https://titiabdelghafour8-lab.github.io/morocco-by-the-numbers/

The site is one static `index.html` with the data embedded. Charts are plain SVG, no framework.

## Data and licence

- All figures come from data.gov.ma, downloaded 23 November 2026. Each chart links to its source dataset.
- The source data is published under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). The processed figures in `data/morocco_by_the_numbers.json` are shared under the same licence. Credit data.gov.ma and the original publisher when you reuse them.
- The code and page design are under the MIT licence (see `LICENSE`).
- This is an independent project, not produced or endorsed by the Moroccan government or any data publisher.

## Personal data

Some portal datasets name individuals (members of parliament, startup founders). This project only publishes counts and totals. No names, contact details or other personal information are kept in `data/` or shown on the site.

## Rebuild the numbers

```bash
pip install -r requirements.txt
python scripts/01_download.py datasets        # whole portal, ~800 MB
python scripts/02_extract.py datasets         # water, jobs, prices, health, internet, roads, courts, integrity -> raw.json
python scripts/02b_extract_more.py datasets   # growth, credit, funds, pensions, startups, parliament -> raw2.json
python scripts/03_build.py datasets           # -> site_data.json
python scripts/03b_build_more.py              # -> site_data2.json
python scripts/04_pack.py datasets            # -> data.min.json and data/morocco_by_the_numbers.json
python scripts/05_render.py                   # -> index.html
```

Run the steps from the repository root. The downloader skips files it already has.

## Known caveats

- HCP changed its employment survey method in 2017; the job charts mark the break.
- Inflation and growth rates are calculated from published indices and may differ by a few tenths from official announcements.
- Parliamentary questions are grouped into policy areas by keyword because ministry names changed in 2021.

Found a mistake? Open an issue.
