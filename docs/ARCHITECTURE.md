# Architecture

These diagrams follow the [C4 model](https://c4model.com): each level zooms into the one above it.

1. **System context**: who uses the site and which outside systems it depends on.
2. **Containers**: the pieces the project is made of and how data moves between them.
3. **Components**: the layers of the `mbn` package, and the parts of the web pages.
4. **Weekly sync**: what happens, step by step, when the scheduled job runs.

Key: blue boxes are part of this project; grey boxes are outside it.

## 1. System context

```mermaid
flowchart TB
    reader["<b>Reader</b><br/>[Person]<br/>Anyone reading the findings"]
    maintainer["<b>Maintainer</b><br/>[Person]<br/>Reviews data updates and edits the text"]
    system["<b>Morocco by the Numbers</b><br/>[Software system]<br/>Turns open government data into checked findings and charts"]
    portal["<b>data.gov.ma</b><br/>[External system]<br/>Morocco's open-data portal (CKAN): files and an API"]
    publishers["<b>Data publishers</b><br/>[External]<br/>HCP, Bank Al-Maghrib, ministries, agencies"]
    hcp["<b>HCP website</b><br/>[External system]<br/>2024 census population by region"]
    github["<b>GitHub</b><br/>[External platform]<br/>Code hosting, Actions, Pages, Issues"]

    publishers -- "publish datasets" --> portal
    reader -- "reads the site in a browser" --> system
    maintainer -- "reviews data-review issues, edits text" --> system
    system -- "checks for changes, downloads files (HTTPS, weekly)" --> portal
    system -. "population figures copied once into the code" .-> hcp
    system -- "runs on, is served by" --> github

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef internal fill:#1168bd,stroke:#0b4884,color:#fff
    classDef external fill:#999,stroke:#6b6b6b,color:#fff
    class reader,maintainer person
    class system internal
    class portal,publishers,hcp,github external
```

## 2. Containers

```mermaid
flowchart TB
    reader["<b>Reader</b><br/>[Person]"]
    maintainer["<b>Maintainer</b><br/>[Person]"]
    portal["<b>data.gov.ma</b><br/>[External system]<br/>CKAN API + files"]

    subgraph gh["GitHub"]
        direction TB
        sync["<b>Data sync job</b><br/>[GitHub Actions, weekly]<br/>.github/workflows/sync.yml"]
        ci["<b>CI</b><br/>[GitHub Actions, every pull request]<br/>.github/workflows/ci.yml"]
        pipeline["<b>mbn package and CLI</b><br/>[Python 3.12]<br/>src/mbn"]
        prs["<b>Pull requests</b><br/>data-sync and feature branches"]
        repo["<b>Repository, main branch</b><br/>[Git]<br/>templates, assets, data/*.json, pages"]
        issues["<b>data-review issues</b><br/>[GitHub Issues]<br/>Updates waiting for a text review"]
        pages["<b>Website</b><br/>[GitHub Pages]<br/>Serves the HTML pages and data files"]
    end

    browser["<b>Web pages</b><br/>[HTML, CSS, JavaScript in the reader's browser]<br/>Draw SVG charts with the shared charts.js"]

    sync -- "runs every Monday" --> pipeline
    pipeline -- "1. any dataset changed? 2. download changed datasets" --> portal
    pipeline -- "rebuilt pages and data, if every quoted number still holds" --> prs
    pipeline -- "review branch + issue, if a quoted number no longer holds" --> issues
    prs -- "checked by" --> ci
    maintainer -- "merges green pull requests" --> repo
    prs --> repo
    issues -. "notifies" .-> maintainer
    repo -- "every merge to main publishes" --> pages
    pages -- "sends pages, assets and data files" --> browser
    reader -- "reads, hovers, switches theme" --> browser

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef internal fill:#1168bd,stroke:#0b4884,color:#fff
    classDef external fill:#999,stroke:#6b6b6b,color:#fff
    class reader,maintainer person
    class sync,ci,pipeline,prs,repo,issues,pages,browser internal
    class portal external
```

## 3a. Components: the mbn package

Each layer depends only on the layers above it in this list. Parsers and analyses are pure functions (no network, no disk writes), so they are fast to test; all input and output lives in `sources` and `publish`.

```mermaid
flowchart TB
    portal["<b>data.gov.ma</b><br/>[External]"]
    cli["<b>cli.py</b><br/>mbn check · watchlist · download · build<br/>render · claims · verify · charts"]

    subgraph sources["sources (I/O)"]
        ckan["<b>ckan.py</b><br/>search, retries, change detection"]
        files["<b>files.py</b><br/>download with resume, long paths"]
        store["<b>store.py</b><br/>find files and dataset metadata"]
        pop["<b>population.py</b><br/>HCP 2024 census (versioned constant)"]
    end
    subgraph parsers["parsers (pure)"]
        prs["hcp · abh · parliament · facilities · others<br/>file -> table"]
    end
    subgraph model["model"]
        schemas["<b>schemas.py</b><br/>pandera contracts"]
        claimm["<b>claims.py</b><br/>Claim(text, value, expected, tolerance)"]
    end
    subgraph analyses["analyses (pure)"]
        an["<b>findings.py</b> and one module per project page<br/>tables -> chart series"]
    end
    subgraph findings["findings"]
        reg["<b>registry.py</b><br/>21 findings: datasets, sources, claims"]
        pagesm["<b>pages.py</b><br/>every page: data file, builder, renderer, claims"]
        build["<b>build.py</b> and one builder per page<br/>store -> parsers -> analyses"]
    end
    subgraph publish["publish (I/O)"]
        export["<b>data_export.py</b><br/>ODbL JSON and CSV"]
        site["<b>site.py</b><br/>templates -> pages, page nav"]
        claims["<b>claims.py, compare.py, review.py</b><br/>claims report, changed series,<br/>publish-or-review decision"]
    end

    cli --> pagesm
    cli --> ckan
    cli --> files
    ckan --> portal
    files --> portal
    pagesm --> build
    pagesm --> reg
    build --> store
    build --> prs
    build --> an
    build --> pop
    prs --> schemas
    reg --> claimm
    cli --> export
    cli --> site
    cli --> claims

    classDef internal fill:#1168bd,stroke:#0b4884,color:#fff
    classDef external fill:#999,stroke:#6b6b6b,color:#fff
    class cli,ckan,files,store,pop,prs,schemas,claimm,an,reg,pagesm,build,export,site,claims internal
    class portal external
```

Design rules:

- **Adding a finding means adding one entry to the registry** (and a parser or analysis if the file is new). A new page is one entry in `pages.py`. The watch list (`data/datasets.txt`), the claims check, the page checks and the browser tests all read these lists; CI fails if the watch list is out of date.
- **Schemas at the boundaries.** pandera checks parser outputs (question files, daily series, price indices): types, ranges, no duplicates.
- **Nothing changes a published number silently.** The golden tests rebuild the data file and the page and compare them with snapshots taken before the refactor, and CI fails if a committed page is stale.

## 3b. Components: the web pages

Each page is a static HTML file at the site root. Pages share `site/assets/site.css` (tokens, light/dark theme) and `site/assets/charts.js` (chart library and helpers). The findings page embeds its data; other pages load theirs from `data/` with `fetch()`.

```mermaid
flowchart TB
    data[/"Data<br/>embedded JSON or data/*.json: series + source links"/]
    sections["<b>Sections and text</b><br/>one template per page in site/templates"]
    charts["<b>charts.js</b><br/>lineChart · columnChart · dotPlot · hbar<br/>draw SVG at the current width"]
    tip["<b>Tooltip</b><br/>exact values on hover or tap"]
    sources["<b>Source links</b><br/>dataset title + publisher under each chart"]
    nav["<b>Page nav and section bar</b><br/>links between pages; highlights the section in view"]
    theme["<b>Theme switch</b><br/>light or dark, remembered in the browser"]

    data --> charts
    data --> sources
    charts --> tip
    theme -- "redraw in new colours" --> charts
    nav --> sections
    sections --> charts

    classDef internal fill:#1168bd,stroke:#0b4884,color:#fff
    classDef store fill:#dbe8f6,stroke:#1168bd,color:#0b2540
    class sections,charts,tip,sources,nav,theme internal
    class data store
```

## 4. Weekly sync, step by step

```mermaid
sequenceDiagram
    autonumber
    participant A as GitHub Actions<br/>(Mondays 06:23 UTC)
    participant P as data.gov.ma
    participant M as mbn CLI
    participant B as Pull request
    participant C as CI
    participant I as Issues

    A->>M: mbn check
    M->>P: last-modified time of the watched datasets
    alt nothing changed, or a sync PR or review issue is already open
        A-->>A: stop (a few seconds)
    else a dataset changed
        M->>P: mbn download (watched datasets only)
        A->>M: mbn build, render, charts
        A->>M: mbn verify: figures moved? every claim holds?
        alt every quoted number still holds
            A->>B: open "Sync data from data.gov.ma" (label data-sync)
            A->>C: start CI on the branch
            C-->>B: lint, types, tests, browser checks
            Note over B,C: Maintainer merges when green;<br/>GitHub Pages publishes within a minute
        else a quoted number no longer holds
            A->>B: push data-review-YYYYMMDD branch
            A->>I: open "New data needs a text review"
            Note over I,B: Maintainer updates the text,<br/>opens a pull request, closes the issue
        end
    end
```
