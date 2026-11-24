"""Compare freshly built data with the committed version and write a review summary.
Usage: python 06_compare.py <old.json> <new.json> <summary.md>
Prints changed=true|false (append to $GITHUB_OUTPUT in CI).
"""
import json, sys
old, new = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
lines = []
for k, v in new.items():
    if k in ("src", "updated") or old.get(k) == v:
        continue
    if isinstance(v, list) and v and isinstance(old.get(k), list) and old[k]:
        lines.append(f"- **{k}**: last point {old[k][-1]} → {v[-1]} ({len(v) - len(old[k]):+d} points)")
    else:
        lines.append(f"- **{k}**: changed")
body = ["## New data on data.gov.ma", "",
        "The monthly refresh rebuilt the site from the latest portal files. These series changed:", ""] + (lines or ["- none"]) + [
        "", "### Before merging", "",
        "- Charts update automatically, but the headline numbers in the text do not. Check every finding whose series changed and update its wording in `scripts/template.html`.",
        "- Check for method changes or breaks in the new data.",
        "- Re-run `scripts/05_render.py` after editing the template."]
open(sys.argv[3], "w", encoding="utf-8").write("\n".join(body) + "\n")
print("changed=" + ("true" if lines else "false"))
