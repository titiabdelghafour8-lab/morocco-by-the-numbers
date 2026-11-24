"""Regional population from HCP's 2024 census (copied once; not on data.gov.ma).

Source: HCP, Population légale du Royaume du Maroc, RGPH 2024 (https://www.hcp.ma/file/242342/).
"""

from __future__ import annotations

SOURCE_URL = (
    "https://www.hcp.ma/Population-legale-du-Royaume-du-Maroc-repartie-par-regions-provinces-et-prefectures"
    "-et-communes-selon-les-resultats-du_a3974.html"
)
VERSION = "RGPH 2024, legal population"

POP_2024: dict[str, int] = {
    "Tanger-Tétouan-Al Hoceïma": 4030222,
    "Oriental": 2294665,
    "Fès-Meknès": 4467911,
    "Rabat-Salé-Kénitra": 5132639,
    "Béni Mellal-Khénifra": 2525801,
    "Casablanca-Settat": 7688967,
    "Marrakech-Safi": 4892393,
    "Drâa-Tafilalet": 1655623,
    "Souss-Massa": 3020431,
    "Guelmim-Oued Noun": 448685,
    "Laâyoune-Sakia El Hamra": 451028,
    "Dakhla-Oued Ed-Dahab": 219965,
}
NATIONAL_2024 = 36828330
assert sum(POP_2024.values()) == NATIONAL_2024
