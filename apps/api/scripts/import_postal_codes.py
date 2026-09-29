#!/usr/bin/env python
"""Genera las filas de la Comunidad de Madrid de `data/postal_codes_es.csv` desde GeoNames.

La cobertura de la Etapa 1 es solo la Comunidad de Madrid, asi que cualquier CP 28xxx
real tiene que estar en el catalogo: si falta, el cliente recibe "codigo postal no
reconocido" aunque viva en la zona. La semilla original solo traia 20.

Fuente: https://download.geonames.org/export/zip/ES.zip (CC BY 4.0, (c) GeoNames).
El fichero trae varias filas por CP (una por lugar) y algunos CP 28xxx incluyen
pedanias de Guadalajara o Toledo. Reglas, en este orden:

1. Solo filas cuya comunidad autonoma es Madrid y cuyas coordenadas caen dentro de la
   Comunidad (hay centroides de urbanizaciones claramente desplazados).
2. El municipio sale de la columna de municipio ("Cardoso de la Sierra, El" pasa a
   "El Cardoso de la Sierra"); si falta, del nombre del lugar.
3. Las coordenadas son las del lugar que se llama como el municipio; si no hay, las de
   la fila con mayor precision.

Las filas de fuera de Madrid del CSV (capitales de provincia, para la base de los
profesionales) se conservan tal cual.

Uso:
    uv run python -m scripts.import_postal_codes ruta/a/ES.txt
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "postal_codes_es.csv"
HEADER = """\
# Catalogo de codigos postales. Columnas: code,city,province,latitude,longitude.
# Comunidad de Madrid (28xxx): completa, generada con scripts/import_postal_codes.py
# a partir de GeoNames (https://www.geonames.org, CC BY 4.0). Resto de Espana: capitales
# de provincia y algunos distritos, con el centroide aproximado de cada zona.
"""
FIELDS = ["code", "city", "province", "latitude", "longitude"]

# Caja que envuelve la Comunidad de Madrid, con algo de margen.
LAT_RANGE = (39.85, 41.20)
LON_RANGE = (-4.60, -3.00)


@dataclass(frozen=True, slots=True)
class Place:
    code: str
    place: str
    municipality: str
    latitude: float
    longitude: float
    accuracy: int


def _fold(text: str) -> str:
    """Compara nombres sin acentos ni mayusculas ("Alcala De Henares" == "Alcala de Henares")."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def _municipality_name(raw: str) -> str:
    """GeoNames pospone el articulo: "Cardoso de la Sierra, El" -> "El Cardoso de la Sierra"."""
    if ", " in raw:
        name, article = raw.rsplit(", ", 1)
        if article in {"El", "La", "Los", "Las"}:
            return f"{article} {name}"
    return raw


def _inside_madrid(place: Place) -> bool:
    return (
        LAT_RANGE[0] <= place.latitude <= LAT_RANGE[1]
        and LON_RANGE[0] <= place.longitude <= LON_RANGE[1]
    )


def read_geonames(path: Path) -> dict[str, list[Place]]:
    by_code: dict[str, list[Place]] = {}
    with path.open(encoding="utf-8") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            code, admin1 = row[1], row[3]
            if not code.startswith("28") or admin1 != "Madrid":
                continue
            place = Place(
                code=code,
                place=row[2],
                municipality=_municipality_name(row[7]),
                latitude=float(row[9]),
                longitude=float(row[10]),
                accuracy=int(row[11] or 0),
            )
            if _inside_madrid(place):
                by_code.setdefault(code, []).append(place)
    return by_code


def pick(places: list[Place]) -> dict[str, str]:
    municipality = next((p.municipality for p in places if p.municipality), places[0].place)
    same_name = [p for p in places if _fold(p.place) == _fold(municipality)]
    # max() se queda con la primera en caso de empate: el orden del fichero decide.
    best = same_name[0] if same_name else max(places, key=lambda p: p.accuracy)
    return {
        "code": best.code,
        "city": municipality,
        "province": "Madrid",
        "latitude": f"{best.latitude:.4f}",
        "longitude": f"{best.longitude:.4f}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("geonames", type=Path, help="ES.txt descomprimido de GeoNames")
    args = parser.parse_args()

    madrid = [pick(places) for _, places in sorted(read_geonames(args.geonames).items())]
    if not madrid:
        print("No se encontro ningun CP de Madrid: revisa el fichero de entrada", file=sys.stderr)
        return 1

    with CSV_PATH.open(encoding="utf-8") as handle:
        rows = csv.DictReader(line for line in handle if not line.startswith("#"))
        others = [row for row in rows if not row["code"].startswith("28")]

    merged = sorted(others + madrid, key=lambda row: row["code"])
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        handle.write(HEADER)
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row[key] for key in FIELDS} for row in merged)

    print(f"{len(madrid)} codigos postales de Madrid, {len(merged)} en total -> {CSV_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
