# Architecture

These diagrams follow the [C4 model](https://c4model.com): each level zooms into the one above it.

1. **System context**: who uses the site and which outside systems it depends on.
2. **Containers**: the pieces the project is made of and how data moves between them.
3. **Components**: the scripts inside the data pipeline, and the parts of the web page.
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
        pipeline["<b>Data pipeline</b><br/>[Python scripts]<br/>scripts/00–07"]
        repo["<b>Repository, main branch</b><br/>[Git]<br/>template, scripts, data/*.json, index.html"]
        issues["<b>data-review issues</b><br/>[GitHub Issues]<br/>Updates waiting for a text review"]
        pages["<b>Website</b><br/>[GitHub Pages]<br/>Serves index.html"]
    end

    browser["<b>Web page</b><br/>[HTML, CSS, JavaScript in the reader's browser]<br/>Draws SVG charts from embedded data"]

    sync -- "runs every Monday" --> pipeline
    pipeline -- "1. any dataset changed? 2. download changed datasets" --> portal
    pipeline -- "rebuilt index.html and data, if every quoted number still holds" --> repo
    pipeline -- "review branch + issue, if a quoted number no longer holds" --> issues
    maintainer -- "fixes the text, merges the branch" --> repo
    issues -. "notifies" .-> maintainer
    repo -- "every push to main publishes" --> pages
    pages -- "sends index.html" --> browser
    reader -- "reads, hovers, switches theme" --> browser

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef internal fill:#1168bd,stroke:#0b4884,color:#fff
    classDef external fill:#999,stroke:#6b6b6b,color:#fff
    class reader,maintainer person
    class sync,pipeline,repo,issues,pages,browser internal
    class portal external
```

## 3a. Components: the data pipeline

Each script reads the previous step's output. Files in italics are temporary and not committed.

```mermaid
flowchart TB
    portal["<b>data.gov.ma</b><br/>[External]"]
    list[/"datasets.txt<br/>46 watched datasets"/]
    state[/"data/sources_state.json<br/>last-modified times"/]

    check["<b>00_check_updates</b><br/>anything changed?"]
    dl["<b>01_download</b><br/>fetch watched datasets"]
    raw[("<i>datasets/</i><br/>original xlsx, xls, csv")]
    ex1["<b>02_extract</b><br/>water, jobs, prices, health,<br/>internet, roads, courts, integrity"]
    ex2["<b>02b_extract_more</b><br/>growth, credit, funds, pensions,<br/>startups, parliament (deduplicated)"]
    ex3["<b>02c_extract_services</b><br/>health centres and schools<br/>+ census population"]
    b1["<b>03_build</b><br/>chart series"]
    b2["<b>03b_build_more</b><br/>chart series"]
    pack["<b>04_pack</b><br/>merge + source links"]
    data[/"data/morocco_by_the_numbers.json<br/>(ODbL)"/]
    tpl[/"template.html<br/>text, layout, chart code"/]
    render["<b>05_render</b><br/>insert data into template"]
    page[/"index.html"/]
    cmp["<b>06_compare</b><br/>which figures moved?"]
    claims["<b>07_check_claims</b><br/>29 quoted numbers vs data"]

    list --> check
    state --> check
    portal --> check
    check -- "changed" --> dl
    list --> dl
    portal --> dl
    dl --> raw
    raw --> ex1 --> b1 --> pack
    raw --> ex2 --> b2 --> pack
    raw --> ex3 --> pack
    pack --> data
    data --> render
    tpl --> render
    render --> page
    data --> cmp
    data --> claims

    classDef internal fill:#1168bd,stroke:#0b4884,color:#fff
    classDef store fill:#dbe8f6,stroke:#1168bd,color:#0b2540
    classDef external fill:#999,stroke:#6b6b6b,color:#fff
    class check,dl,ex1,ex2,ex3,b1,b2,pack,render,cmp,claims internal
    class list,state,raw,data,tpl,page store
    class portal external
```

## 3b. Components: the web page

`index.html` is self-contained apart from Google Fonts. Everything below runs in the reader's browser.

```mermaid
flowchart TB
    data[/"DATA<br/>embedded JSON: series + source links"/]
    sections["<b>Sections and text</b><br/>Land and water · Work · Economy · Living · State · About"]
    charts["<b>Chart functions</b><br/>lineChart · columnChart · dotPlot · hbar<br/>draw SVG at the current width"]
    tip["<b>Tooltip</b><br/>exact values on hover or tap"]
    sources["<b>Source links</b><br/>dataset title + publisher under each chart"]
    nav["<b>Section bar</b><br/>highlights the section in view"]
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
    participant S as Pipeline scripts
    participant R as Repository (main)
    participant I as Issues
    participant W as GitHub Pages

    A->>P: last-modified time of the 46 watched datasets
    alt nothing changed, or a review is already open
        A-->>A: stop (a few seconds)
    else a dataset changed
        A->>P: download watched datasets (~790 files)
        A->>S: extract, build, pack, render
        S->>S: every chart present? figures moved? 29 claims hold?
        alt every quoted number still holds
            S->>R: commit index.html + data
            R->>W: publish (about a minute)
        else a quoted number no longer holds
            S->>R: push data-review-YYYYMMDD branch
            S->>I: open "New data needs a text review"
            Note over I,R: Maintainer updates the text,<br/>merges the branch, closes the issue
        end
    end
```
