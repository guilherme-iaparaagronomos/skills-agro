#!/usr/bin/env python3
"""Baixa a FEIÇÃO (polígono) de um CAR — SEM captcha, direto do WFS oficial.

O GeoServer público do SICAR (consulta.car.gov.br/geoserver) expõe as
camadas do cadastro por WFS, filtráveis pelo código do imóvel — é uma
requisição pública legítima, não burla nada: o botão "Baixar feições" do
site (com reCAPTCHA) empacota shapefile; aqui pegamos o MESMO dado em
GeoJSON por API. Traz o perímetro do imóvel e, opcionalmente, as camadas
temáticas (reserva legal, APP, vegetação nativa, área consolidada...).

Uso:
  python baixar_feicao.py PI-2200053-1BAB.C06A.E224.43BC.A804.FFEC.51C2.5EB9
  python baixar_feicao.py <CAR> -o fazenda.geojson
  python baixar_feicao.py <CAR> --temas arl_averbada,vegetacao_nativa
  python baixar_feicao.py <CAR> --temas todos      # todas as camadas com dado

Saída: GeoJSON (EPSG:4674 SIRGAS 2000) — abre no QGIS e serve de perímetro
para a skill krigagem-solo. Só biblioteca padrão.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# reaproveita normalização/validação/bloqueio do consultar_car
sys.path.insert(0, str(Path(__file__).resolve().parent))
from consultar_car import BloqueioDeRede, MSG_SEM_REDE, _eh_bloqueio, normalizar_car  # noqa: E402

WFS = "https://consulta.car.gov.br/geoserver/consulta_publica/ows"
UA = "Mozilla/5.0 (compatible; consulta-car-skill/1.0; uso educacional)"

# camada principal (perímetro) + temáticas úteis que filtram por cod_imovel
CAMADA_PERIMETRO = "iru"
TEMAS_COMUNS = [
    "arl_averbada", "arl_aprovada_nao_averbada", "arl_proposta",
    "vegetacao_nativa", "area_consolidada", "area_pousio", "ast",
    "reservatorio_artificial_decorrente_barramento",
]


def wfs_geojson(camada: str, car: str) -> dict:
    """GetFeature de uma camada filtrada pelo cod_imovel, em GeoJSON."""
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": f"consulta_publica:{camada}",
        "outputFormat": "application/json",
        "srsName": "EPSG:4674",
        "cql_filter": f"cod_imovel='{car}'",
    }
    url = f"{WFS}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if _eh_bloqueio(e):
                raise BloqueioDeRede(MSG_SEM_REDE) from e
            if tentativa == 2:
                raise RuntimeError(f"WFS falhou em '{camada}': {e}")
            time.sleep(1.5 * (tentativa + 1))
    return {"features": []}


def contar_vertices(coords) -> int:
    if isinstance(coords, (int, float)):
        return 0
    if coords and isinstance(coords[0], (int, float)):
        return 1
    return sum(contar_vertices(c) for c in coords)


def main() -> None:
    ap = argparse.ArgumentParser(description="Baixa a feição (polígono) de um CAR via WFS")
    ap.add_argument("car", help="número do CAR")
    ap.add_argument("-o", "--saida", help="arquivo .geojson de saída")
    ap.add_argument(
        "--temas",
        help="camadas temáticas além do perímetro: lista separada por vírgula, "
        "ou 'todos' para varrer as comuns (arl, vegetação, área consolidada...)",
    )
    args = ap.parse_args()

    car = normalizar_car(args.car)
    if not car:
        sys.exit(f"CAR inválido: {args.car!r}")

    # perímetro (sempre)
    try:
        perimetro = wfs_geojson(CAMADA_PERIMETRO, car)
    except BloqueioDeRede as e:
        sys.exit(f"{e}\n(o download da feição EXIGE rede — não há como derivar o "
                 f"polígono offline; rode no Claude Code ou no Cowork)")
    feats = perimetro.get("features", [])
    if not feats:
        sys.exit(f"CAR não encontrado no acervo geográfico: {car}")
    for f in feats:
        f.setdefault("properties", {})["camada"] = "perimetro_imovel"
    print(f"perímetro: {contar_vertices(feats[0]['geometry']['coordinates'])} vértices")

    todas = list(feats)

    # temas opcionais
    if args.temas:
        temas = TEMAS_COMUNS if args.temas.strip().lower() == "todos" else [
            t.strip() for t in args.temas.split(",") if t.strip()
        ]
        for tema in temas:
            try:
                r = wfs_geojson(tema, car)
            except RuntimeError as e:
                print(f"  {tema}: {e}", file=sys.stderr)
                continue
            time.sleep(0.4)
            tf = r.get("features", [])
            if tf:
                for f in tf:
                    f.setdefault("properties", {})["camada"] = tema
                todas.extend(tf)
                print(f"  {tema}: {len(tf)} feição(ões)")

    saida = Path(args.saida) if args.saida else Path(f"{car}.geojson")
    colecao = {"type": "FeatureCollection", "crs": {"type": "name",
              "properties": {"name": "urn:ogc:def:crs:EPSG::4674"}}, "features": todas}
    saida.write_text(json.dumps(colecao, ensure_ascii=False), encoding="utf-8")
    print(f"{saida}: {len(todas)} feição(ões) — SIRGAS 2000 (EPSG:4674)")
    print("  → abre no QGIS e serve de perímetro p/ a skill krigagem-solo")


if __name__ == "__main__":
    main()
