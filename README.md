# Morocco by the Numbers

Eleven findings from Morocco's open data portal, [data.gov.ma](https://www.data.gov.ma): rivers running dry, youth unemployment, food prices, health insurance, internet, road deaths, courts and corruption perception.

**Live site:** https://titiabdelghafour8-lab.github.io/morocco-by-the-numbers/

The site is one static `index.html` with the data embedded. Charts are plain SVG, no framework.

## Data sources

All figures come from data.gov.ma (ODbL licence), downloaded 23 November 2026. Each chart links to its dataset.

| Topic | Publisher |
|---|---|
| River flow, rainfall | Agence du Bassin Hydraulique de Souss-Massa |
| Cereal harvest | Département de l'Agriculture |
| Unemployment, consumer prices | Haut-Commissariat au Plan (HCP) |
| Health insurance coverage | ACAPS |
| Internet and mobile | ANRT |
| Road deaths | NARSA |
| Court caseload | Ministère de la Justice |
| Corruption Perceptions Index | INPPLC |

## Rebuild the numbers

```bash
pip install -r requirements.txt
python scripts/01_download.py datasets        # whole portal, ~800 MB
python scripts/02_extract.py datasets         # parse spreadsheets -> raw.json
python scripts/03_build.py datasets           # derive series -> site_data.json
python scripts/04_pack.py datasets            # compact data + source links -> data.min.json
python scripts/05_render.py                   # write index.html
```

Run the steps from the repository root. The downloader skips files it already has, so re-running it only fetches what changed.
