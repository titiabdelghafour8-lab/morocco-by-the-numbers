"""Inject data.min.json into template.html and write ../index.html."""
import os
here = os.path.dirname(os.path.abspath(__file__))
head = ('<!doctype html>
<html lang="en">
<meta charset="utf-8">
'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
')
page = open(os.path.join(here, "template.html"), encoding="utf-8").read()
data = open("data.min.json", encoding="utf-8").read()
open(os.path.join(here, "..", "index.html"), "w", encoding="utf-8").write(head + page.replace("/*DATA*/", data))
print("index.html written")
