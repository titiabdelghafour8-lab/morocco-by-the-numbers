"""Download portal files into <out>/<organization>/<dataset>/, with resume and long-path handling."""

from __future__ import annotations

import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from mbn.sources import ckan

UA = {"User-Agent": "open-data-downloader/1.0"}


def safe(name: object, maxlen: int = 90) -> str:
    """A file-system-safe name."""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip(" .")
    return (s or "unnamed")[:maxlen]


def filename_for(res: dict[str, Any], used: set[str]) -> str:
    """Pick a unique local file name for a CKAN resource."""
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


def longpath(p: str) -> str:
    r"""On Windows, prefix ``\\?\`` so paths over 260 characters work."""
    return "\\\\?\\" + os.path.abspath(p) if os.name == "nt" and not p.startswith("\\\\?\\") else p


def download(url: str, dest: str) -> tuple[str, int]:
    """Download one file unless it is already there; returns (status, bytes)."""
    dest = longpath(dest)
    url = url.replace("://datagovma.webhi.net/", "://data.gov.ma/")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return "skipped", os.path.getsize(dest)
    url = urllib.parse.quote(url, safe=":/?&=%#+@,;~")
    err: Exception | None = None
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
            time.sleep(2**attempt)
    if os.path.exists(dest + ".part"):
        os.remove(dest + ".part")
    return f"failed: {err}", 0


def download_all(out: str, patterns: list[str] | None = None) -> list[dict[str, Any]]:
    """Download every dataset (or those matching ``patterns``); write _catalog.json and _manifest.csv."""
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    print("Fetching catalog...", flush=True)
    datasets = list(ckan.search(rows=100, fetch=lambda u: ckan.get_json(u, backoff=1, user_agent=UA["User-Agent"])))
    if patterns:
        datasets = [d for d in datasets if ckan.matches(d["name"], patterns)]
    print(f"{len(datasets)} datasets", flush=True)
    with open(os.path.join(out, "_catalog.json"), "w", encoding="utf-8") as f:
        json.dump(datasets, f, ensure_ascii=False, indent=1)

    jobs, rows = [], []
    for ds in datasets:
        org = safe((ds.get("organization") or {}).get("name") or "no-organization")
        ddir = os.path.join(out, org, safe(ds["name"]))
        os.makedirs(ddir, exist_ok=True)
        with open(os.path.join(ddir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(ds, f, ensure_ascii=False, indent=1)
        used = {"metadata.json"}
        for res in ds.get("resources", []):
            if not res.get("url"):
                continue
            fname = filename_for(res, used)
            row: dict[str, Any] = {
                "organization": org,
                "dataset": ds["name"],
                "title": ds.get("title"),
                "groups": "|".join(g["name"] for g in ds.get("groups", [])),
                "resource_id": res["id"],
                "format": res.get("format"),
                "url": res["url"],
                "local_path": os.path.relpath(os.path.join(ddir, fname), out),
            }
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
    if rows:
        with open(os.path.join(out, "_manifest.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    failed = [r for r in rows if r["status"].startswith("failed")]
    total = sum(r["bytes"] for r in rows)
    print(f"Done. {len(rows) - len(failed)} ok, {len(failed)} failed, {total / 1e6:.1f} MB")
    for r in failed:
        print("FAILED", r["local_path"], r["url"], r["status"])
    return rows
