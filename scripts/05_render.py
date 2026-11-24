"""Inject data.min.json into template.html and write ../index.html.

Run from the folder that holds data.min.json (the repository root if you followed the README).
"""
import os

here = os.path.dirname(os.path.abspath(__file__))
head = (
    '<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
    '<meta name="description" content="Eleven findings from Morocco\'s open data portal: '
    'water, jobs, prices, health, internet, roads, courts and integrity.">\n'
)
page = open(os.path.join(here, "template.html"), encoding="utf-8").read()
data = open("data.min.json", encoding="utf-8").read()
open(os.path.join(here, "..", "index.html"), "w", encoding="utf-8").write(head + page.replace("/*DATA*/", data))
print("index.html written")
