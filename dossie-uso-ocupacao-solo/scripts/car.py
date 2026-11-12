#!/usr/bin/env python3
"""Consulta pública do CAR para o dossiê: perímetro, situação do cadastro e o
que o imóvel DECLARA (reserva legal, vegetação nativa, área consolidada, APP).

Usa os mesmos serviços públicos da skill `consulta-car` (sem captcha): a API
de detalhes do imóvel e o WFS do SICAR, filtrado pelo código do imóvel.

Uso:
  python car.py SP-3550506-C85A6F90FDE14A5F9991B75F065E3F88 --saida ./dossie
  python car.py <CAR> --saida ./dossie --sem-app     # pula as ~25 camadas de APP

Grava em --saida:
  car.json            atributos do cadastro + área declarada por tema
  perimetro.geojson   o polígono do imóvel (SIRGAS 2000, EPSG:4674)
  car-temas.geojson   os polígonos declarados, um tema por feição

Tudo aqui é DECLARAÇÃO do proprietário no SICAR, no estado em que está na data
da consulta. Só biblioteca padrão.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://consulta.car.gov.br/api/totalizer/getDeatilsByIdentifier/{car}"  # "Deatils": grafia do serviço
WFS = "https://consulta.car.gov.br/geoserver/consulta_publica/ows"
UA = "Mozilla/5.0 (compatible; dossie-uso-solo-skill/1.0; uso educacional)"
PAUSA_S = 0.4  # gentileza com o servidor público entre consultas
RE_CAR = re.compile(r"^[A-Z]{2}-\d{7}-[0-9A-F]{32}$")

MSG_SEM_REDE = (
    "o site do CAR (consulta.car.gov.br) NÃO é acessível a partir deste ambiente — a sandbox de "
    "código do chat bloqueia hosts externos. Peça ao usuário o arquivo do perímetro (KML, GeoJSON "
    "ou shapefile) ou rode esta etapa onde há internet (Claude Code, Cowork). O dossiê sai sem o "
    "bloco do CAR."
)

STATUS = {"AT": "Ativo", "PE": "Pendente", "SU": "Suspenso", "CA": "Cancelado"}

# (camada no WFS, rótulo no dossiê, grupo)
TEMAS = [
    ("arl_averbada", "Reserva legal averbada", "reserva_legal"),
    ("arl_aprovada_nao_averbada", "Reserva legal aprovada e não averbada", "reserva_legal"),
    ("arl_proposta", "Reserva legal proposta", "reserva_legal"),
    ("vegetacao_nativa", "Remanescente de vegetação nativa", "vegetacao_nativa"),
    ("area_consolidada", "Área consolidada", "area_consolidada"),
    ("area_pousio", "Área de pousio", "outros"),
    ("area_servidao_administrativa_total", "Servidão administrativa", "outros"),
    ("area_uso_restrito_declividade_25_a_45", "Uso restrito: declividade de 25° a 45°", "uso_restrito"),
    ("area_uso_restrito_pantaneira", "Uso restrito: área pantaneira", "uso_restrito"),
]
APPS = [
    ("app_rio_ate_10", "APP de curso d'água de até 10 m"),
    ("app_rio_10_a_50", "APP de curso d'água de 10 a 50 m"),
    ("app_rio_50_a_200", "APP de curso d'água de 50 a 200 m"),
    ("app_rio_200_a_600", "APP de curso d'água de 200 a 600 m"),
    ("app_rio_acima_600", "APP de curso d'água acima de 600 m"),
    ("app_nascente_olho_dagua", "APP de nascente ou olho d'água"),
    ("app_lago_natural", "APP de lago ou lagoa natural"),
    ("app_reservatorio_artificial_decorrente_barramento", "APP de reservatório artificial"),
    ("app_vereda", "APP de vereda"),
    ("app_banhado", "APP de banhado"),
    ("app_area_topo_morro", "APP de topo de morro"),
    ("app_area_declividade_maior_45", "APP de declividade acima de 45°"),
    ("app_borda_chapada", "APP de borda de chapada"),
    ("app_area_altitude_superior_1800", "APP de altitude acima de 1.800 m"),
    ("app_restinga", "APP de restinga"),
    ("app_manguezal", "APP de manguezal"),
]


class BloqueioDeRede(RuntimeError):
    """Ambiente sem saída para a internet — não adianta tentar de novo."""


def normalizar_car(texto: str) -> str | None:
    """'sp-3550506-c85a.6f90…' → 'SP-3550506-C85A6F90…' (ou None se não for um CAR)."""
    bruto = re.sub(r"[.\s]", "", str(texto).strip().upper())
    return bruto if RE_CAR.match(bruto) else None


def _eh_bloqueio(erro: Exception) -> bool:
    if isinstance(erro, urllib.error.HTTPError):
        if erro.code != 403:
            return False
        return "host_not_allowed" in (str(getattr(erro, "headers", "") or "") + str(erro))
    return isinstance(erro, urllib.error.URLError)


def _pedir(url: str, espera: int = 45) -> str:
    ultimo: Exception | None = None
    for tentativa in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=espera) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:  # noqa: BLE001 - a causa vai na mensagem
            if _eh_bloqueio(e):
                raise BloqueioDeRede(MSG_SEM_REDE) from e
            ultimo = e
            time.sleep(1.5 * (tentativa + 1))
    raise RuntimeError(f"o serviço do CAR não respondeu: {ultimo}")


def _exigir_car(car: str) -> None:
    """O CAR entra na URL e no filtro do WFS: só passa o que tem o formato do cadastro."""
    if not isinstance(car, str) or not RE_CAR.match(car):
        raise ValueError("CAR fora do formato UF-1234567-32 caracteres hexadecimais")


def detalhes(car: str) -> dict | None:
    """Atributos do imóvel. None = CAR não encontrado (o serviço devolve corpo vazio)."""
    _exigir_car(car)
    corpo = _pedir(API.format(car=car), 30).strip()
    return json.loads(corpo) if corpo else None


def camada(car: str, nome: str) -> list[dict]:
    """Feições de uma camada do WFS filtradas pelo código do imóvel."""
    _exigir_car(car)
    if not re.fullmatch(r"[a-z0-9_]+", nome):
        raise ValueError(f"camada inválida: {nome!r}")
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeName": f"consulta_publica:{nome}", "outputFormat": "application/json",
        "srsName": "EPSG:4674", "cql_filter": f"cod_imovel='{car}'",
    }
    return json.loads(_pedir(f"{WFS}?{urllib.parse.urlencode(params)}")).get("features", [])


def _aneis(geometria: dict) -> list[list]:
    if not geometria:
        return []
    if geometria["type"] == "Polygon":
        return [geometria["coordinates"]]
    if geometria["type"] == "MultiPolygon":
        return list(geometria["coordinates"])
    return []


def area_ha(geometria: dict) -> float:
    """Área do polígono em hectares, na esfera (erro de até ~0,5% frente ao elipsoide).
    Serve de conferência e de reserva; o número do dossiê é o que o SICAR informa."""
    raio = 6371008.8
    total = 0.0
    for poligono in _aneis(geometria):
        for n, anel in enumerate(poligono):
            soma = 0.0
            for (lon1, lat1, *_), (lon2, lat2, *_) in zip(anel, anel[1:]):
                soma += math.radians(lon2 - lon1) * (2 + math.sin(math.radians(lat1))
                                                     + math.sin(math.radians(lat2)))
            parte = abs(soma) * raio * raio / 2
            total += parte if n == 0 else -parte  # anéis internos são furos
    return total / 10000


def _numero(valor) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _area_das_feicoes(feicoes: list[dict]) -> tuple[float, str]:
    """Soma a área das feições. Usa o campo do SICAR; sem ele, a área do polígono."""
    informadas = [_numero(f.get("properties", {}).get("nu_area_imovel")) for f in feicoes]
    if feicoes and all(v is not None for v in informadas):
        return round(sum(informadas), 4), "informada pelo SICAR"
    return round(sum(area_ha(f.get("geometry")) for f in feicoes), 4), "calculada do polígono"


def consultar(car: str, com_app: bool = True, avisar=print) -> dict:
    """Monta o bloco do CAR do dossiê. Levanta BloqueioDeRede, LookupError (CAR não
    encontrado) ou RuntimeError (serviço fora do ar)."""
    perimetro = camada(car, "iru")
    if not perimetro:
        raise LookupError(f"{car}: não encontrado no acervo geográfico do SICAR")
    time.sleep(PAUSA_S)
    det = detalhes(car) or {}
    p = perimetro[0].get("properties", {})
    codigo = str(p.get("status_imovel") or "").upper()

    temas, feicoes_tema = [], []
    lista = TEMAS + ([(c, r, "app") for c, r in APPS] if com_app else [])
    for nome, rotulo, grupo in lista:
        time.sleep(PAUSA_S)
        try:
            feicoes = camada(car, nome)
        except BloqueioDeRede:
            raise
        except RuntimeError as e:
            avisar(f"  {nome}: sem resposta ({e})")
            temas.append({"camada": nome, "rotulo": rotulo, "grupo": grupo, "erro": "sem resposta do serviço"})
            continue
        if not feicoes:
            continue
        area, origem = _area_das_feicoes(feicoes)
        temas.append({"camada": nome, "rotulo": rotulo, "grupo": grupo, "feicoes": len(feicoes),
                      "area_ha": area, "area_origem": origem})
        for f in feicoes:
            f.setdefault("properties", {})["camada"] = nome
            feicoes_tema.append(f)
        avisar(f"  {rotulo}: {len(feicoes)} feição(ões), {area:.2f} ha")

    datas = sorted({str(f["properties"].get("dt_atualizacao") or "")[:10] for f in feicoes_tema} - {""})
    retificacoes = [_numero(f["properties"].get("nu_retificacao")) for f in feicoes_tema]
    retificacoes = [int(v) for v in retificacoes if v is not None]
    return {
        "car": car,
        "consultado_em": datetime.date.today().isoformat(),
        "municipio": det.get("nameCity") or p.get("municipio"),
        "uf": det.get("idState") or p.get("uf"),
        "estado": det.get("nameState"),
        "area_declarada_ha": _numero(det.get("haRegisteredArea")),
        "area_do_poligono_ha": round(area_ha(perimetro[0].get("geometry")), 2),
        "modulos_fiscais": _numero(det.get("fiscalModules")),
        "data_cadastro": det.get("createdAt"),
        "ultima_retificacao": det.get("lastRectification"),
        "numero_retificacao": max(retificacoes) if retificacoes else None,
        "temas_atualizados_em": datas[-1] if datas else None,
        "latitude": det.get("latitude"),
        "longitude": det.get("longitude"),
        "tipo_imovel": p.get("tipo_imovel"),
        "status": {"codigo": codigo, "texto": STATUS.get(codigo)},
        "situacao_analise": p.get("situacao_analise"),
        "sobreposicoes": {
            "Terra indígena": _numero(p.get("sobreposicao_area_indigena")),
            "Unidade de conservação": _numero(p.get("sobreposicao_unidade_conservacao")),
            "Território quilombola": _numero(p.get("sobreposicao_quilombo")),
            "Área embargada": _numero(p.get("sobreposicao_area_embargada")),
            "Terras da União": _numero(p.get("sobreposicao_terras_da_uniao")),
        },
        "temas": temas,
        "app_consultada": com_app,
        "_perimetro": perimetro,
        "_feicoes_tema": feicoes_tema,
    }


def _colecao(feicoes: list[dict]) -> dict:
    return {"type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4674"}},
            "features": feicoes}


def gravar(dados: dict, pasta: Path) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    perimetro, feicoes = dados.pop("_perimetro"), dados.pop("_feicoes_tema")
    for f in perimetro:
        f.setdefault("properties", {})["camada"] = "perimetro_imovel"
    arquivos = [pasta / "car.json", pasta / "perimetro.geojson", pasta / "car-temas.geojson"]
    arquivos[0].write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    arquivos[1].write_text(json.dumps(_colecao(perimetro), ensure_ascii=False), encoding="utf-8")
    arquivos[2].write_text(json.dumps(_colecao(feicoes), ensure_ascii=False), encoding="utf-8")
    return arquivos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Perímetro e declarações do CAR para o dossiê")
    ap.add_argument("car", nargs="?", help="número do CAR, com ou sem pontos")
    ap.add_argument("--saida", default="./dossie", help="pasta de saída")
    ap.add_argument("--sem-app", action="store_true", help="não consulta as camadas de APP")
    ap.add_argument("--teste", action="store_true", help="roda os testes embutidos (sem rede)")
    args = ap.parse_args(argv)
    if args.teste or not args.car:
        return _teste()
    car = normalizar_car(args.car)
    if not car:
        sys.exit("CAR inválido: o formato é UF-1234567-32 caracteres (0–9, A–F), com ou sem pontos")
    try:
        dados = consultar(car, com_app=not args.sem_app)
    except BloqueioDeRede as e:
        sys.exit(str(e))
    except (LookupError, RuntimeError) as e:
        sys.exit(str(e))
    for arq in gravar(dados, Path(args.saida)):
        print(arq)
    area = dados["area_declarada_ha"]
    print(f"{dados['municipio']}/{dados['uf']} · {area if area is not None else '?'} ha declarados · "
          f"{len([t for t in dados['temas'] if 'area_ha' in t])} tema(s) com área")
    return 0


def _teste() -> int:
    assert normalizar_car("sp-3550506-c85a.6f90.fde1.4a5f.9991.b75f.065e.3f88") == \
        "SP-3550506-C85A6F90FDE14A5F9991B75F065E3F88"
    assert normalizar_car("SP-355050-C85A") is None
    # quadrado de 0,01° no equador ≈ 1,112 km de lado ≈ 123,6 ha; furo de 1/4 tira 25%
    fora = [[0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01], [0, 0]]
    furo = [[0, 0], [0.005, 0], [0.005, 0.005], [0, 0.005], [0, 0]]
    cheio = area_ha({"type": "Polygon", "coordinates": [fora]})
    assert 123.0 < cheio < 124.2, cheio
    assert abs(area_ha({"type": "Polygon", "coordinates": [fora, furo]}) - cheio * 0.75) < 0.01
    assert abs(area_ha({"type": "MultiPolygon", "coordinates": [[fora], [fora]]}) - 2 * cheio) < 1e-6
    feicoes = [{"properties": {"nu_area_imovel": "1.5"}, "geometry": None},
               {"properties": {"nu_area_imovel": 2}, "geometry": None}]
    assert _area_das_feicoes(feicoes) == (3.5, "informada pelo SICAR")
    sem_campo = [{"properties": {}, "geometry": {"type": "Polygon", "coordinates": [fora]}}]
    area, origem = _area_das_feicoes(sem_campo)
    assert origem == "calculada do polígono" and abs(area - cheio) < 0.01
    assert _eh_bloqueio(urllib.error.URLError("sem rota"))
    for ruim in ("SP-3550506-X' OR '1'='1", "", None):
        try:
            camada(ruim, "iru")
            raise AssertionError("CAR malformado passou")
        except ValueError:
            pass
    try:
        camada("SP-3550506-C85A6F90FDE14A5F9991B75F065E3F88", "iru&x=1")
        raise AssertionError("camada malformada passou")
    except ValueError:
        pass
    print("car OK: normalização, área na esfera (com furo) e soma das áreas declaradas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
