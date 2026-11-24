"""Morocco by the Numbers: turn data.gov.ma open data into checked findings and pages.

Layers (each depends only on the ones above it in this list):

- ``model``: shared vocabulary (sources, schemas)
- ``sources``: network and local file access (the only I/O besides ``publish``)
- ``parsers``: pure functions, one publisher's file -> tidy table
- ``analyses``: pure functions, tables -> published figures
- ``findings``: the registry of what the site shows
- ``publish``: data export, page rendering, claims check
- ``cli``: the command line that ties them together
"""

__version__ = "1.0.0"
