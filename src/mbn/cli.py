"""Command line: ``mbn check | watchlist | download | build | render | claims | verify | publish``.

Lines of the form ``key=value`` on standard output are meant for ``$GITHUB_OUTPUT``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mbn.config import DATA_DIR, DEFAULT_DATASETS, ROOT, STATE_FILE, WATCH_FILE
from mbn.findings.pages import PAGES, Page, all_watch_patterns
from mbn.publish import claims as claims_mod
from mbn.publish import compare, data_export, site
from mbn.sources import ckan, files
from mbn.sources.store import DatasetStore

WATCH_HEADER = (
    "# data.gov.ma datasets this site uses, as patterns on the CKAN dataset name.\n"
    "# The weekly sync watches these for changes and downloads only these.\n"
    "# Generated from the registry by `mbn watchlist`: do not edit by hand.\n"
)


def _select(names: list[str] | None) -> list[Page]:
    if not names:
        return list(PAGES)
    return [p for p in PAGES if p.name in names]


def cmd_watchlist(args: argparse.Namespace) -> int:
    text = WATCH_HEADER + "\n".join(all_watch_patterns()) + "\n"
    if args.check:
        current = WATCH_FILE.read_text(encoding="utf-8") if WATCH_FILE.exists() else ""
        if current.replace("\r\n", "\n") != text:
            print(f"{WATCH_FILE.relative_to(ROOT)} is out of date: run `mbn watchlist`", file=sys.stderr)
            return 1
        return 0
    data_export.write_text(WATCH_FILE, text)
    print(f"{len(all_watch_patterns())} patterns written to {WATCH_FILE.relative_to(ROOT)}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    old = data_export.read_json(Path(args.state))
    new = ckan.watched_state(all_watch_patterns())
    lines = ckan.diff_states(old, new)
    data_export.write_json(DATA_DIR / "sources_state.new.json", dict(sorted(new.items())))
    data_export.write_text(
        Path("changes.md"), "### Datasets that changed on data.gov.ma\n\n" + ("\n".join(lines) or "- none") + "\n"
    )
    print("changed=" + ("true" if lines else "false"))
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    rows = files.download_all(args.out, None if args.all else all_watch_patterns())
    return 1 if any(r["status"].startswith("failed") for r in rows) else 0


def cmd_build(args: argparse.Namespace) -> int:
    st = DatasetStore(args.datasets)
    for p in _select(args.page):
        data = p.build(st, args.date)
        data_export.write_json(p.data_file, data)
        print(f"{p.name}: {p.data_file.relative_to(ROOT)} written")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    for p in _select(args.page):
        html = p.render(data_export.read_json(p.data_file))
        site.write_page(p.html, html)
        print(f"{p.name}: {p.html} written")
    return 0


def run_claims(pages: list[Page]) -> tuple[list[str], int]:
    lines, failed = [], 0
    for p in pages:
        page_lines, page_failed = claims_mod.check(p.claims(), data_export.read_json(p.data_file))
        lines += [f"## {p.name}", *page_lines, ""]
        failed += page_failed
    return lines, failed


def cmd_claims(args: argparse.Namespace) -> int:
    lines, failed = run_claims(_select(args.page))
    print("\n".join(lines))
    return 1 if failed else 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Compare against the previous data files, check claims, write summary.md and claims.txt."""
    old_dir = Path(args.old)
    changed: dict[str, list[str]] = {}
    for p in PAGES:
        old_file = old_dir / p.data_file.name
        old = data_export.read_json(old_file) if old_file.exists() else {}
        changed[p.name] = compare.changed_series(old, data_export.read_json(p.data_file))
    data_export.write_text(Path(args.summary), compare.summary(changed))
    lines, failed = run_claims(list(PAGES))
    data_export.write_text(Path(args.claims), "\n".join(lines) + "\n")
    print("changed=" + ("true" if any(changed.values()) else "false"))
    print("claims_ok=" + ("false" if failed else "true"))
    return 0


def cmd_charts(args: argparse.Namespace) -> int:
    """Every page has as many chart containers as its template declares."""
    bad = 0
    for p in PAGES:
        tpl = site.read_template(p.html)
        out = (ROOT / p.html).read_text(encoding="utf-8")
        if len(site.chart_ids(tpl)) != len(site.chart_ids(out)):
            print(f"{p.html}: {len(site.chart_ids(out))} charts, template has {len(site.chart_ids(tpl))}")
            bad += 1
    return 1 if bad else 0


def cmd_topics(args: argparse.Namespace) -> int:
    """Fit the parliament topic model offline (needs `uv sync --extra topics`)."""
    from mbn.findings import parliament_model

    cache = Path(args.cache) if args.cache else None
    res = parliament_model.run(DatasetStore(args.datasets), cache=cache)
    print(f"{res['n_topics']} topics over {res['documents']} questions; fingerprint {res['fingerprint']}")
    print("Now read data/parliament/topic_model.json, update data/parliament/topic_labels.json and its fingerprint.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mbn", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("watchlist", help="write data/datasets.txt from the registry")
    s.add_argument("--check", action="store_true", help="fail if the file is out of date")
    s.set_defaults(fn=cmd_watchlist)
    s = sub.add_parser("check", help="ask data.gov.ma whether a watched dataset changed")
    s.add_argument("--state", default=str(STATE_FILE))
    s.set_defaults(fn=cmd_check)
    s = sub.add_parser("download", help="download the watched datasets")
    s.add_argument("out", nargs="?", default=str(DEFAULT_DATASETS))
    s.add_argument("--all", action="store_true", help="download the whole portal")
    s.set_defaults(fn=cmd_download)
    for name, fn, hlp in [
        ("build", cmd_build, "rebuild data files from downloaded datasets"),
        ("render", cmd_render, "render pages from data files"),
        ("claims", cmd_claims, "check the numbers quoted in the text"),
    ]:
        s = sub.add_parser(name, help=hlp)
        if name == "build":
            s.add_argument("datasets", nargs="?", default=str(DEFAULT_DATASETS))
            s.add_argument("--date", help="value for 'updated' (default: $DATA_DATE or today)")
        s.add_argument("--page", action="append", help="only this page (repeatable)")
        s.set_defaults(fn=fn)
    s = sub.add_parser("verify", help="compare with old data files and check claims (for the sync job)")
    s.add_argument("--old", required=True, help="folder holding the previous data files")
    s.add_argument("--summary", default="summary.md")
    s.add_argument("--claims", default="claims.txt")
    s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("topics", help="fit the parliament topic model offline (topics extra)")
    s.add_argument("datasets", nargs="?", default=str(DEFAULT_DATASETS))
    s.add_argument("--cache", help="where to keep the embeddings between runs (not published)")
    s.set_defaults(fn=cmd_topics)
    s = sub.add_parser("charts", help="check every page has all its charts")
    s.set_defaults(fn=cmd_charts)
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    rc: int = args.fn(args)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
