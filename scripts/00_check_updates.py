"""Check data.gov.ma for changes to the datasets this site uses.

Usage: python scripts/00_check_updates.py [scripts/datasets.txt] [data/sources_state.json]
Compares each watched dataset's last-modified time (and any new matching dataset)
with the recorded state. Writes data/sources_state.new.json and changes.md, and
prints changed=true|false for $GITHUB_OUTPUT. Costs a handful of API calls.
"""
import fnmatch, json, sys, time, urllib.request

API = "https://data.gov.ma/data/api/3/action/package_search"
pats_file = sys.argv[1] if len(sys.argv) > 1 else "scripts/datasets.txt"
state_file = sys.argv[2] if len(sys.argv) > 2 else "data/sources_state.json"
pats = [l.strip() for l in open(pats_file, encoding="utf-8") if l.strip() and not l.startswith("#")]
# timestamps come back in two formats (microseconds or milliseconds + Z): compare to the second
norm = lambda s: str(s)[:19]
old = {k: norm(v) for k, v in json.load(open(state_file, encoding="utf-8")).items()}

def get(url):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "open-data-sync/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))

new, start = {}, 0
while True:
    res = get(f"{API}?rows=200&start={start}&fl=name,metadata_modified")["result"]
    for d in res["results"]:
        if any(fnmatch.fnmatch(d["name"], p) for p in pats):
            new[d["name"]] = norm(d["metadata_modified"])
    start += 200
    if start >= res["count"]:
        break

lines = [f"- `{n}`: {'new dataset' if n not in old else 'updated ' + new[n][:10]}" for n in sorted(new) if old.get(n) != new[n]]
lines += [f"- `{n}`: removed from the portal" for n in sorted(set(old) - set(new))]
json.dump(dict(sorted(new.items())), open("data/sources_state.new.json", "w", encoding="utf-8"), indent=1)
open("changes.md", "w", encoding="utf-8").write("### Datasets that changed on data.gov.ma\n\n" + ("\n".join(lines) or "- none") + "\n")
print("changed=" + ("true" if lines else "false"))
