"""Download every dataset from data.gov.ma (CKAN) into <out>/<organization>/<dataset>/.

Usage: python -I download_datagovma.py <out_dir>
Re-running is safe: files already downloaded (non-empty) are skipped.
"""
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "https://data.gov.ma/data/api/3/action"
UA = {"User-Agent": "open-data-downloader/1.0"}
OUT = os.path.abspath(sys.argv[1])


def get_json(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def safe(name, maxlen=90):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip(" .")
    return (name or "unnamed")[:maxlen]


def fetch_catalog():
    datasets, start = [], 0
    while True:
        res = get_json(f"{API}/package_search?rows=100&start={start}")["result"]
        datasets += res["results"]
        start += 100
        if start >= res["count"]:
            return datasets


def filename_for(res, used):
    path = urllib.parse.urlparse(res.get("url") or "").path
    base = urllib.parse.unquote(os.path.basename(path)) or safe(res.get("name") or res["id"])
    stem, ext = os.path.splitext(safe(base, 120))
    if not ext and res.get("format"):
        ext = "." + res["format"].lower()
    name, i = stem + ext, 2
    while name.lower() in used:
        name, i = f"{stem}_{i}{ext}", i + 1
    used.add(name.lower())
    return name


def longpath(p):
    return "\\\\?\\" + os.path.abspath(p) if os.name == "nt" and not p.startswith("\\\\?\\") else p


def download(url, dest):
    dest = longpath(dest)
    url = url.replace("://datagovma.webhi.net/", "://data.gov.ma/")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return "skipped", os.path.getsize(dest)
    url = urllib.parse.quote(url, safe=":/?&=%#+@,;~")
    for attempt in range(4):
        try:
            tmp = dest + ".part"
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 16):
                    f.write(chunk)
            os.replace(tmp, dest)
            return "ok", os.path.getsize(dest)
        except Exception as e:
            err = e
            time.sleep(2 ** attempt)
    if os.path.exists(dest + ".part"):
        os.remove(dest + ".part")
    return f"failed: {err}", 0


def main():
    os.makedirs(OUT, exist_ok=True)
    print("Fetching catalog...", flush=True)
    datasets = fetch_catalog()
    print(f"{len(datasets)} datasets", flush=True)
    with open(os.path.join(OUT, "_catalog.json"), "w", encoding="utf-8") as f:
        json.dump(datasets, f, ensure_ascii=False, indent=1)

    jobs, rows = [], []
    for ds in datasets:
        org = safe((ds.get("organization") or {}).get("name") or "no-organization")
        ddir = os.path.join(OUT, org, safe(ds["name"]))
        os.makedirs(ddir, exist_ok=True)
        with open(os.path.join(ddir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(ds, f, ensure_ascii=False, indent=1)
        used = {"metadata.json"}
        for res in ds.get("resources", []):
            if not res.get("url"):
                continue
            fname = filename_for(res, used)
            row = {"organization": org, "dataset": ds["name"], "title": ds.get("title"),
                   "groups": "|".join(g["name"] for g in ds.get("groups", [])),
                   "resource_id": res["id"], "format": res.get("format"),
                   "url": res["url"], "local_path": os.path.relpath(os.path.join(ddir, fname), OUT)}
            rows.append(row)
            jobs.append((row, os.path.join(ddir, fname)))

    print(f"{len(jobs)} files to download", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(download, row["url"], dest): row for row, dest in jobs}
        for fut in as_completed(futs):
            row = futs[fut]
            row["status"], row["bytes"] = fut.result()
            done += 1
            if done % 50 == 0 or done == len(jobs):
                print(f"{done}/{len(jobs)}", flush=True)

    rows.sort(key=lambda r: r["local_path"])
    with open(os.path.join(OUT, "_manifest.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    failed = [r for r in rows if r["status"].startswith("failed")]
    total = sum(r["bytes"] for r in rows)
    print(f"Done. {len(rows) - len(failed)} ok, {len(failed)} failed, {total / 1e6:.1f} MB")
    for r in failed:
        print("FAILED", r["local_path"], r["url"], r["status"])


if __name__ == "__main__":
    main()
