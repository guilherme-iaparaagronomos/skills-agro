#!/usr/bin/env python3
"""Converte o GeoJSON do imóvel (perímetro/feições) para Shapefile e KML.

Python puro (stdlib) — não depende de GDAL/ogr2ogr/fiona. Lê o GeoJSON
gerado por baixar_feicao.py/consultar_car.py (polígonos em SIRGAS 2000,
EPSG:4674) e escreve:

  - Shapefile (.shp + .shx + .dbf + .prj), empacotado num .zip (o formato é
    multiarquivo — o zip entrega tudo junto);
  - KML (um Placemark por feição, com nome vindo do cod_imovel/camada).

Uso:
  python converter.py PI-....geojson                 # gera .zip (shp) e .kml
  python converter.py area.geojson --formatos shp    # só shapefile
  python converter.py area.geojson -o saida          # prefixo dos arquivos
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SHAPE_POLYGON = 5
# WKT de SIRGAS 2000 geográfico (EPSG:4674) para o .prj
PRJ_SIRGAS2000 = (
    'GEOGCS["SIRGAS 2000",DATUM["Sistema_de_Referencia_Geocentrico_para_las_'
    'AmericaS_2000",SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM['
    '"Greenwich",0],UNIT["degree",0.0174532925199433]]'
)


# ------------------------------------------------------------- geometria
def _aneis(geom: dict) -> list[list[list[float]]]:
    """Extrai os anéis (exterior + buracos) de Polygon/MultiPolygon,
    marcando cada um como exterior (True) ou buraco (False)."""
    t = geom.get("type")
    poligonos: list[list[list[list[float]]]] = []
    if t == "Polygon":
        poligonos = [geom["coordinates"]]
    elif t == "MultiPolygon":
        poligonos = geom["coordinates"]
    else:
        return []
    saida = []
    for pol in poligonos:
        for i, anel in enumerate(pol):
            saida.append((anel, i == 0))  # 1º anel = exterior
    return saida


def _area_assinada(anel: list[list[float]]) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(anel, anel[1:]):
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _orientar(anel: list[list[float]], exterior: bool) -> list[list[float]]:
    """ESRI: exterior HORÁRIO (área<0), buraco ANTI-HORÁRIO (área>0).
    (GeoJSON usa a convenção OPOSTA — por isso normalizamos aqui.)"""
    a = _area_assinada(anel)
    horario = a < 0
    if exterior != horario:  # exterior quer horário; buraco quer anti-horário
        return anel
    return list(reversed(anel))


# ------------------------------------------------------------- shapefile
def _registro_shp(geom: dict) -> bytes | None:
    aneis = _aneis(geom)
    if not aneis:
        return None
    partes, pontos = [], []
    for anel, exterior in aneis:
        anel = _orientar([[float(x), float(y)] for x, y in anel], exterior)
        partes.append(len(pontos))
        pontos.extend(anel)
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    corpo = struct.pack("<i", SHAPE_POLYGON)
    corpo += struct.pack("<4d", min(xs), min(ys), max(xs), max(ys))
    corpo += struct.pack("<ii", len(partes), len(pontos))
    corpo += struct.pack(f"<{len(partes)}i", *partes)
    for x, y in pontos:
        corpo += struct.pack("<2d", x, y)
    return corpo


def _cabecalho(tamanho_words: int, bbox: tuple[float, float, float, float]) -> bytes:
    h = struct.pack(">i", 9994) + b"\x00" * 20
    h += struct.pack(">i", tamanho_words)
    h += struct.pack("<ii", 1000, SHAPE_POLYGON)
    h += struct.pack("<4d", *bbox)
    h += struct.pack("<4d", 0, 0, 0, 0)  # Z/M mins e maxs
    return h


def _bbox_geral(feicoes: list[dict]) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for f in feicoes:
        for anel, _ in _aneis(f["geometry"]):
            for x, y in anel:
                xs.append(float(x))
                ys.append(float(y))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)


def _dbf(campos: list[str], registros: list[list[str]]) -> bytes:
    larguras = [
        max(10, min(80, max([len(str(r[i])) for r in registros] + [len(campos[i])])))
        for i in range(len(campos))
    ]
    tam_registro = 1 + sum(larguras)
    tam_cabecalho = 32 + 32 * len(campos) + 1
    out = struct.pack("<B3BIHH", 3, 26, 8, 12, len(registros), tam_cabecalho, tam_registro)
    out += b"\x00" * 20
    for nome, larg in zip(campos, larguras):
        nome_b = nome.encode("ascii", "replace")[:10].ljust(11, b"\x00")
        out += nome_b + b"C" + b"\x00" * 4 + struct.pack("<B", larg) + b"\x00" * 15
    out += b"\x0d"
    for r in registros:
        out += b" "  # flag "não deletado"
        for valor, larg in zip(r, larguras):
            out += str(valor).encode("utf-8", "replace")[:larg].ljust(larg, b" ")
    out += b"\x1a"
    return out


def shapefile_partes(colecao: dict) -> dict[str, bytes]:
    """Os 4 arquivos do shapefile (.shp/.shx/.dbf/.prj) em MEMÓRIA — quem
    chama decide se grava em disco ou empacota num zip (útil p/ montar um
    zip com um shapefile POR CAR)."""
    feicoes = [f for f in colecao.get("features", []) if _aneis(f["geometry"])]
    if not feicoes:
        raise ValueError("nenhuma feição de polígono no GeoJSON")

    # campos do .dbf (subset útil das properties, nomes ≤10 chars)
    mapa = [("cod_imovel", "cod_imovel"), ("camada", "camada"),
            ("municipio", "municipio"), ("uf", "uf")]
    campos = [c for c, _ in mapa]
    registros = [[str(f.get("properties", {}).get(k, "")) for _, k in mapa] for f in feicoes]

    corpos = [_registro_shp(f["geometry"]) for f in feicoes]
    bbox = _bbox_geral(feicoes)

    shp = bytearray(b"\x00" * 100)
    shx = bytearray(b"\x00" * 100)
    offset = 50  # em words de 16 bits (100 bytes de cabeçalho)
    for i, corpo in enumerate(corpos, start=1):
        clen = len(corpo) // 2
        shp += struct.pack(">ii", i, clen) + corpo
        shx += struct.pack(">ii", offset, clen)
        offset += 4 + clen  # 8 bytes de header do registro = 4 words
    shp[:100] = _cabecalho(len(shp) // 2, bbox)
    shx[:100] = _cabecalho((100 + 8 * len(corpos)) // 2, bbox)

    return {
        "shp": bytes(shp),
        "shx": bytes(shx),
        "dbf": _dbf(campos, registros),
        "prj": PRJ_SIRGAS2000.encode("utf-8"),
    }


def geojson_para_shapefile_zip(colecao: dict, base: Path) -> Path:
    """Shapefile de UMA coleção, empacotado num .zip (formato multiarquivo)."""
    partes = shapefile_partes(colecao)
    zip_path = base.with_name(f"{base.stem}-shapefile.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for ext, dados in partes.items():
            z.writestr(f"{base.stem}.{ext}", dados)
    return zip_path


# -------------------------------------------------------------------- KML
def _coords_kml(anel: list[list[float]]) -> str:
    return " ".join(f"{float(x)},{float(y)},0" for x, y in anel)


def kml_str(colecao: dict) -> str:
    """KML da coleção como texto (quem chama grava ou põe num zip)."""
    marcas = []
    for f in colecao.get("features", []):
        aneis = _aneis(f["geometry"])
        if not aneis:
            continue
        props = f.get("properties", {})
        nome = escape(str(props.get("cod_imovel") or props.get("camada") or "feição"))
        # exterior(es) + buracos como innerBoundary do polígono anterior
        poligonos_kml = []
        atual = None
        for anel, exterior in aneis:
            if exterior:
                if atual:
                    poligonos_kml.append(atual)
                atual = [f"<outerBoundaryIs><LinearRing><coordinates>"
                         f"{_coords_kml(anel)}</coordinates></LinearRing></outerBoundaryIs>"]
            elif atual:
                atual.append(f"<innerBoundaryIs><LinearRing><coordinates>"
                             f"{_coords_kml(anel)}</coordinates></LinearRing></innerBoundaryIs>")
        if atual:
            poligonos_kml.append(atual)
        geom = "".join(f"<Polygon>{''.join(p)}</Polygon>" for p in poligonos_kml)
        multi = f"<MultiGeometry>{geom}</MultiGeometry>" if len(poligonos_kml) > 1 else geom
        marcas.append(f"<Placemark><name>{nome}</name>{multi}</Placemark>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        + "".join(marcas)
        + "</Document></kml>"
    )


def geojson_para_kml(colecao: dict, destino: Path) -> Path:
    destino.write_text(kml_str(colecao), encoding="utf-8")
    return destino


# ------------------------------------------------- vários CARs (1 por arquivo)
def zips_por_car(
    colecoes: dict[str, dict],
    base: Path,
    formatos: set[str] | None = None,
) -> list[Path]:
    """Consulta com VÁRIOS CARs (decisão do fundador 2026-08-13): cada
    imóvel vira um ARQUIVO PRÓPRIO — nada de tudo junto numa coleção só —
    e os arquivos vão empacotados num zip por formato:
      <base>-geojson.zip · <base>-shapefile.zip · <base>-kml.zip
    (no zip do shapefile cada CAR leva seu conjunto .shp/.shx/.dbf/.prj).
    """
    formatos = formatos or {"geojson", "shp", "kml"}
    gerados: list[Path] = []
    if "geojson" in formatos:
        destino = base.with_name(f"{base.name}-geojson.zip")
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
            for car, colecao in colecoes.items():
                z.writestr(f"{car}.geojson", json.dumps(colecao, ensure_ascii=False))
        gerados.append(destino)
    if formatos & {"shp", "shapefile"}:
        destino = base.with_name(f"{base.name}-shapefile.zip")
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
            for car, colecao in colecoes.items():
                for ext, dados in shapefile_partes(colecao).items():
                    z.writestr(f"{car}.{ext}", dados)
        gerados.append(destino)
    if "kml" in formatos:
        destino = base.with_name(f"{base.name}-kml.zip")
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
            for car, colecao in colecoes.items():
                z.writestr(f"{car}.kml", kml_str(colecao))
        gerados.append(destino)
    return gerados


# ------------------------------------------------------------------- main
def converter(geojson_path: Path, prefixo: Path | None, formatos: set[str]) -> list[Path]:
    colecao = json.loads(geojson_path.read_text(encoding="utf-8"))
    base = prefixo or geojson_path.with_suffix("")
    gerados = []
    if "shp" in formatos or "shapefile" in formatos:
        gerados.append(geojson_para_shapefile_zip(colecao, base))
    if "kml" in formatos:
        gerados.append(geojson_para_kml(colecao, base.with_suffix(".kml")))
    return gerados


def main() -> None:
    ap = argparse.ArgumentParser(description="Converte GeoJSON do CAR em Shapefile e KML")
    ap.add_argument("geojson", help="arquivo .geojson de entrada")
    ap.add_argument("-o", "--saida", help="prefixo dos arquivos de saída")
    ap.add_argument("--formatos", default="shp,kml",
                    help="formatos separados por vírgula: shp, kml (padrão: ambos)")
    args = ap.parse_args()

    entrada = Path(args.geojson)
    if not entrada.exists():
        sys.exit(f"arquivo não encontrado: {entrada}")
    formatos = {f.strip().lower() for f in args.formatos.split(",") if f.strip()}
    gerados = converter(entrada, Path(args.saida) if args.saida else None, formatos)
    for g in gerados:
        print(f"gerado: {g}")


if __name__ == "__main__":
    main()
