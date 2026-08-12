#!/usr/bin/env python3
"""Organiza o zip de FEIÇÕES baixado do Consulta Pública do CAR.

O download (botão "Baixar feições", após o USUÁRIO resolver o reCAPTCHA)
traz um zip com shapefiles por tema do cadastro (perímetro do imóvel,
reserva legal, APP etc.). Este script:

  1. lista os temas presentes no zip;
  2. extrai tudo para uma pasta ao lado do zip;
  3. lê o cabeçalho de cada .shp (sem GDAL) e imprime tipo de geometria,
     nº aproximado de registros e a caixa envolvente (graus, SIRGAS 2000).

Uso:
  python feicoes.py caminho/do/shape-car.zip
  python feicoes.py shape-car.zip -o pasta_destino

Somente biblioteca padrão. O perímetro (tema AREA_IMOVEL) sai pronto para
a skill `krigagem-solo` (entrada de perímetro) e para o QGIS.
"""

from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from pathlib import Path

TIPOS_SHP = {
    0: "nulo", 1: "ponto", 3: "linha", 5: "polígono", 8: "multiponto",
    11: "ponto Z", 13: "linha Z", 15: "polígono Z", 21: "ponto M",
    23: "linha M", 25: "polígono M",
}


def cabecalho_shp(dados: bytes) -> dict | None:
    """Lê o cabeçalho de 100 bytes de um .shp (formato ESRI)."""
    if len(dados) < 100 or struct.unpack(">i", dados[:4])[0] != 9994:
        return None
    tamanho_palavras = struct.unpack(">i", dados[24:28])[0]  # em words de 16 bits
    tipo = struct.unpack("<i", dados[32:36])[0]
    xmin, ymin, xmax, ymax = struct.unpack("<4d", dados[36:68])
    return {
        "tipo": TIPOS_SHP.get(tipo, f"tipo {tipo}"),
        "bytes": tamanho_palavras * 2,
        "bbox": (round(xmin, 6), round(ymin, 6), round(xmax, 6), round(ymax, 6)),
    }


def registros_dbf(dados: bytes) -> int | None:
    """Nº de registros do .dbf (bytes 4-8, little-endian)."""
    return struct.unpack("<I", dados[4:8])[0] if len(dados) >= 8 else None


def main() -> None:
    ap = argparse.ArgumentParser(description="Extrai e resume o zip de feições do CAR")
    ap.add_argument("zip", help="zip baixado do consulta.car.gov.br (Baixar feições)")
    ap.add_argument("-o", "--saida", help="pasta de extração (padrão: nome do zip)")
    args = ap.parse_args()

    caminho = Path(args.zip)
    if not caminho.exists():
        sys.exit(f"arquivo não encontrado: {caminho}")
    try:
        z = zipfile.ZipFile(caminho)
    except zipfile.BadZipFile:
        sys.exit("o arquivo não é um zip válido — o download pode ter falhado no meio")

    destino = Path(args.saida) if args.saida else caminho.with_suffix("")
    destino.mkdir(parents=True, exist_ok=True)
    z.extractall(destino)

    shps = sorted(n for n in z.namelist() if n.lower().endswith(".shp"))
    if not shps:
        print(f"zip extraído em {destino} — nenhum .shp encontrado; conteúdo:")
        for n in z.namelist():
            print(f"  {n}")
        return

    print(f"{caminho.name} → {destino}/")
    for nome in shps:
        cab = cabecalho_shp(z.read(nome))
        base = nome[:-4]
        dbf = next((n for n in z.namelist() if n.lower() == f"{base.lower()}.dbf"), None)
        n_reg = registros_dbf(z.read(dbf)) if dbf else None
        if cab:
            xmin, ymin, xmax, ymax = cab["bbox"]
            print(
                f"  {nome}: {cab['tipo']}"
                + (f" · {n_reg} registro(s)" if n_reg is not None else "")
                + f" · bbox lon [{xmin}, {xmax}] lat [{ymin}, {ymax}]"
            )
        else:
            print(f"  {nome}: cabeçalho inválido")
    area = next((n for n in shps if "AREA_IMOVEL" in n.upper()), None)
    if area:
        print(f"\nperímetro do imóvel: {destino / area}")
        print("  → pronto p/ QGIS e p/ a skill krigagem-solo (entrada de perímetro)")


if __name__ == "__main__":
    main()
