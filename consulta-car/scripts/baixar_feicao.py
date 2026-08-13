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


def baixar_varios(
    cars: list[str], temas: str | None, formatos: set[str], prefixo: str | None
) -> None:
    """Vários CARs: cada imóvel vira um ARQUIVO PRÓPRIO, empacotado em zips
    por formato (regra do fundador 2026-08-13 — nunca tudo junto)."""
    lista_temas = (
        TEMAS_COMUNS
        if (temas or "").strip().lower() == "todos"
        else [t.strip() for t in (temas or "").split(",") if t.strip()]
    )
    por_car: dict[str, dict] = {}
    for entrada in cars:
        car = normalizar_car(entrada)
        if not car:
            print(f"  {entrada}: CAR inválido", file=sys.stderr)
            continue
        try:
            fc = wfs_geojson(CAMADA_PERIMETRO, car)
        except BloqueioDeRede as e:
            sys.exit(str(e))
        except RuntimeError as e:
            print(f"  {car}: {e}", file=sys.stderr)
            continue
        feats = fc.get("features", [])
        if not feats:
            print(f"  {car}: não encontrado no acervo geográfico", file=sys.stderr)
            continue
        for f in feats:
            f.setdefault("properties", {})["camada"] = "perimetro_imovel"
        time.sleep(0.4)
        for tema in lista_temas:
            try:
                r = wfs_geojson(tema, car)
            except RuntimeError:
                continue
            time.sleep(0.4)
            for f in r.get("features", []):
                f.setdefault("properties", {})["camada"] = tema
                feats.append(f)
        por_car[car] = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4674"}},
            "features": feats,
        }
        print(f"  {car}: {len(feats)} feição(ões)")

    if not por_car:
        sys.exit("nenhum CAR encontrado")
    from converter import zips_por_car

    base = Path(prefixo) if prefixo else Path("cars-perimetros")
    gerados = zips_por_car(por_car, base, formatos)
    print(f"{len(por_car)} imóvel(is) — 1 arquivo por CAR dentro de cada zip:")
    for g in gerados:
        print(f"  {g}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Baixa a feição (polígono) de um ou vários CARs via WFS")
    ap.add_argument("car", nargs="+", help="um ou VÁRIOS números de CAR")
    ap.add_argument("-o", "--saida", help="arquivo .geojson de saída")
    ap.add_argument(
        "--temas",
        help="camadas temáticas além do perímetro: lista separada por vírgula, "
        "ou 'todos' para varrer as comuns (arl, vegetação, área consolidada...)",
    )
    ap.add_argument(
        "--formatos", default="geojson,shp,kml",
        help="formatos de saída: geojson, shp, kml (padrão: os três)",
    )
    args = ap.parse_args()

    formatos_pedidos = {f.strip().lower() for f in args.formatos.split(",") if f.strip()}

    # VÁRIOS CARs (2026-08-13): um arquivo POR CAR, em zips por formato
    if len(args.car) > 1:
        baixar_varios(args.car, args.temas, formatos_pedidos, args.saida)
        return

    car = normalizar_car(args.car[0])
    if not car:
        sys.exit(f"CAR inválido: {args.car[0]!r}")

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
    formatos = formatos_pedidos

    gerados = []
    if "geojson" in formatos:
        saida.write_text(json.dumps(colecao, ensure_ascii=False), encoding="utf-8")
        gerados.append(saida)
    if formatos & {"shp", "shapefile", "kml"}:
        from converter import converter as _converter  # mesmo diretório

        # escreve um geojson temporário se o usuário não pediu geojson
        tmp = saida if "geojson" in formatos else saida.with_suffix(".tmp.geojson")
        if "geojson" not in formatos:
            tmp.write_text(json.dumps(colecao, ensure_ascii=False), encoding="utf-8")
        gerados += _converter(tmp, saida.with_suffix(""), formatos)
        if "geojson" not in formatos:
            tmp.unlink(missing_ok=True)

    print(f"{len(todas)} feição(ões) — SIRGAS 2000 (EPSG:4674):")
    for g in gerados:
        print(f"  {g}")
    print("  → abre no QGIS/Earth e serve de perímetro p/ a skill krigagem-solo")


if __name__ == "__main__":
    main()
