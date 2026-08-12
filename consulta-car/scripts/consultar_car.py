#!/usr/bin/env python3
"""Consulta pública do CAR (SICAR) — um número ou planilha inteira.

Fonte: API pública do Consulta Pública do CAR (consulta.car.gov.br) — a
mesma que a página oficial usa ao clicar em "Buscar". GET simples, sem
captcha. CAR inexistente responde corpo VAZIO (tratado como "não
encontrado").

Uso:
  python consultar_car.py PI-2200053-1BAB.C06A.E224.43BC.A804.FFEC.51C2.5EB9
  python consultar_car.py planilha.csv            # preenche e salva -preenchida.csv
  python consultar_car.py planilha.xlsx -o saida.xlsx
  python consultar_car.py planilha.csv --decimal  # lat/long em graus decimais
  python consultar_car.py planilha.csv --sobrescrever  # refaz até células já preenchidas

Somente biblioteca padrão (urllib, csv, zipfile) — roda em qualquer
ambiente Python 3.9+ com acesso à internet. XLSX é lido e escrito sem
openpyxl (leitura de inlineStr/sharedStrings; escrita de um xlsx mínimo
válido).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

API = "https://consulta.car.gov.br/api/totalizer/getDeatilsByIdentifier/{car}"
UA = "Mozilla/5.0 (compatible; consulta-car-skill/1.0; uso educacional)"
PAUSA_S = 0.5  # gentileza com o servidor público entre consultas
TENTATIVAS = 3

# regex do CAR normalizado (sem pontos): UF-cod.IBGE(7)-hash(32 hex,
# 8 grupos de 4 no formato pontuado do site)
RE_CAR = re.compile(r"^[A-Z]{2}-\d{7}-[0-9A-F]{32}$")

MSG_SEM_REDE = (
    "o site do CAR (consulta.car.gov.br) NÃO é acessível a partir deste "
    "ambiente — a sandbox de código do chat bloqueia hosts externos "
    "(403 host_not_allowed). Rode esta skill no CLAUDE CODE ou no COWORK, "
    "que têm internet real; ou peça à IA para consultar a API pela própria "
    "ferramenta de busca/fetch dela."
)


class BloqueioDeRede(RuntimeError):
    """Ambiente sem saída para a internet (sandbox do chat) — não adianta tentar de novo."""


def _eh_bloqueio(erro: Exception) -> bool:
    if isinstance(erro, urllib.error.HTTPError) and erro.code == 403:
        cabecalho = str(getattr(erro, "headers", "") or "")
        return "host_not_allowed" in cabecalho or "host_not_allowed" in str(erro)
    # DNS/egress totalmente bloqueado costuma vir como URLError
    return isinstance(erro, urllib.error.URLError) and not isinstance(erro, urllib.error.HTTPError)


# ---------------------------------------------------------------- consulta
def normalizar_car(texto: str) -> str | None:
    """'pi-2200053-1bab.c06a...' -> 'PI-2200053-1BABC06A...' (ou None)."""
    bruto = re.sub(r"[.\s]", "", str(texto).strip().upper())
    return bruto if RE_CAR.match(bruto) else None


def consultar(car: str) -> dict | None:
    """Consulta um CAR normalizado. None = não encontrado.
    Levanta BloqueioDeRede (ambiente sem internet) ou RuntimeError (5xx/timeout)."""
    url = API.format(car=car)
    ultimo_erro: Exception | None = None
    for tentativa in range(TENTATIVAS):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                corpo = resp.read().decode("utf-8").strip()
            if not corpo:
                return None  # CAR inexistente: a API devolve 200 vazio
            return json.loads(corpo)
        except Exception as e:
            if _eh_bloqueio(e):
                raise BloqueioDeRede(MSG_SEM_REDE) from e  # sem retry: não vai mudar
            ultimo_erro = e  # 5xx/timeout do gov.br: espera e tenta de novo
            time.sleep(1.5 * (tentativa + 1))
    raise RuntimeError(f"falha ao consultar {car}: {ultimo_erro}")


# --------------------------------------------- resolução OFFLINE (sem rede)
# o código IBGE do município está EMBUTIDO no número do CAR: os 7 dígitos
# após a UF. Com a tabela oficial (references/municipios_ibge.tsv), dá para
# preencher município e estado SEM acessar o SICAR — útil quando o ambiente
# bloqueia a internet (ex.: sandbox do chat). Lat/long/área ainda exigem a
# API, mas 2 colunas já saem de graça e o resultado é auditável.
COD_UF = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}
NOME_UF = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia",
    "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}
_TABELA_IBGE: dict[str, tuple[str, str]] | None = None


def _carregar_ibge() -> dict[str, tuple[str, str]]:
    global _TABELA_IBGE
    if _TABELA_IBGE is None:
        _TABELA_IBGE = {}
        arq = Path(__file__).resolve().parent.parent / "references" / "municipios_ibge.tsv"
        if arq.exists():
            for linha in arq.read_text(encoding="utf-8").splitlines():
                partes = linha.split("\t")
                if len(partes) >= 3:
                    _TABELA_IBGE[partes[0]] = (partes[1], partes[2])
    return _TABELA_IBGE


def resolver_offline(car: str) -> dict:
    """Município/estado/UF a partir do código IBGE embutido no número do CAR."""
    cod = car.split("-")[1] if "-" in car else ""
    nome, uf = _carregar_ibge().get(cod, ("", COD_UF.get(cod[:2], "")))
    return {"municipio": nome, "uf": uf, "estado": NOME_UF.get(uf, "")}


def dms_para_decimal(dms: str) -> float | None:
    """8°22'26.947\"S -> -8.374152 (S/W negativos)."""
    m = re.match(r"(\d+)°(\d+)'([\d.]+)\"?([NSEW])", str(dms).strip())
    if not m:
        return None
    graus, minutos, segundos, hemisferio = m.groups()
    valor = int(graus) + int(minutos) / 60 + float(segundos) / 3600
    return round(-valor if hemisferio in "SW" else valor, 6)


def linha_resultado(dados: dict, decimal: bool) -> dict:
    """Mapeia a resposta da API para os campos da planilha."""
    lat, lon = dados.get("latitude", ""), dados.get("longitude", "")
    if decimal:
        lat = dms_para_decimal(lat) if lat else ""
        lon = dms_para_decimal(lon) if lon else ""
    area = dados.get("haRegisteredArea", "")
    modulos = dados.get("fiscalModules", "")
    return {
        "latitude": lat,
        "longitude": lon,
        "area": f"{area:.2f}".replace(".", ",") if isinstance(area, (int, float)) else area,
        "municipio": dados.get("nameCity", ""),
        "estado": dados.get("nameState", ""),
        "uf": dados.get("idState", ""),
        "modulos": f"{modulos:.2f}".replace(".", ",") if isinstance(modulos, (int, float)) else modulos,
        "cadastro": dados.get("createdAt", ""),
    }


# --------------------------------------------------- casamento de colunas
def _chave(texto: str) -> str:
    s = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in s if c.isalnum())


# cabeçalho da planilha -> campo do resultado (casamento por substring)
MAPA_COLUNAS = [
    ("latitude", "latitude"),
    ("longitude", "longitude"),
    ("area", "area"),
    ("municipio", "municipio"),
    ("cidade", "municipio"),
    ("estado", "estado"),
    ("uf", "uf"),
    ("modulo", "modulos"),
    ("cadastro", "cadastro"),
    ("data", "cadastro"),
]
# colunas criadas quando a planilha não tiver nenhuma equivalente
COLUNAS_PADRAO = [
    ("Latitude", "latitude"),
    ("Longitude", "longitude"),
    ("Área do Imóvel (ha)", "area"),
    ("Município", "municipio"),
    ("Estado", "estado"),
    ("Módulos Fiscais", "modulos"),
]


def mapear_colunas(cabecalho: list[str]) -> tuple[int | None, dict[int, str]]:
    """Acha a coluna do CAR e mapeia as demais para os campos do resultado."""
    col_car = None
    destino: dict[int, str] = {}
    usados: set[str] = set()
    for i, nome in enumerate(cabecalho):
        chave = _chave(nome)
        if col_car is None and ("car" in chave or "registro" in chave):
            col_car = i
            continue
        for padrao, campo in MAPA_COLUNAS:
            if padrao in chave and campo not in usados:
                destino[i] = campo
                usados.add(campo)
                break
    return col_car, destino


# ------------------------------------------------------------ CSV / XLSX
def ler_csv(caminho: Path) -> list[list[str]]:
    # sniff de separador: planilha BR costuma vir com ';'
    texto = caminho.read_text(encoding="utf-8-sig")
    sep = ";" if texto.splitlines()[0].count(";") >= texto.splitlines()[0].count(",") else ","
    return [list(l) for l in csv.reader(texto.splitlines(), delimiter=sep)]


def escrever_csv(caminho: Path, linhas: list[list[str]]) -> None:
    with caminho.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f, delimiter=";").writerows(linhas)


_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _ref_para_indice(ref: str) -> int:
    col = 0
    for ch in ref:
        if ch.isalpha():
            col = col * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return col - 1


def ler_xlsx(caminho: Path) -> list[list[str]]:
    """Lê a primeira aba (inlineStr + sharedStrings + números). Sem openpyxl."""
    z = zipfile.ZipFile(caminho)
    shared: list[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        raiz = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in raiz.iter(f"{_NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
    folha = next(n for n in z.namelist() if re.match(r"xl/worksheets/sheet1\.xml$", n))
    raiz = ET.fromstring(z.read(folha))
    linhas: list[list[str]] = []
    for row in raiz.iter(f"{_NS}row"):
        celulas: list[str] = []
        for c in row.iter(f"{_NS}c"):
            idx = _ref_para_indice(c.get("r", ""))
            while len(celulas) < idx:
                celulas.append("")
            tipo = c.get("t")
            if tipo == "inlineStr":
                valor = "".join(t.text or "" for t in c.iter(f"{_NS}t"))
            else:
                v = c.find(f"{_NS}v")
                valor = v.text if v is not None and v.text else ""
                if tipo == "s" and valor != "":
                    valor = shared[int(valor)]
            celulas.append(valor)
        linhas.append(celulas)
    largura = max((len(l) for l in linhas), default=0)
    return [l + [""] * (largura - len(l)) for l in linhas]


def _col_letra(i: int) -> str:
    letra = ""
    i += 1
    while i:
        i, resto = divmod(i - 1, 26)
        letra = chr(65 + resto) + letra
    return letra


def escrever_xlsx(caminho: Path, linhas: list[list[str]]) -> None:
    """Escreve um xlsx mínimo válido (inlineStr, sem estilos) só com stdlib."""
    corpo = []
    for r, linha in enumerate(linhas, start=1):
        celulas = "".join(
            f'<c r="{_col_letra(i)}{r}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'
            for i, v in enumerate(linha)
        )
        corpo.append(f'<row r="{r}">{celulas}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(corpo)}</sheetData></worksheet>"
    )
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="CAR" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet)


# ---------------------------------------------------------------- planilha
def preencher_planilha(
    caminho: Path, saida: Path | None, decimal: bool, sobrescrever: bool, feicoes: bool = True
) -> None:
    ehxlsx = caminho.suffix.lower() == ".xlsx"
    linhas = ler_xlsx(caminho) if ehxlsx else ler_csv(caminho)
    if not linhas:
        sys.exit("planilha vazia")

    cabecalho = [str(c) for c in linhas[0]]
    col_car, destino = mapear_colunas(cabecalho)
    if col_car is None:
        sys.exit(
            "não achei a coluna do CAR — o cabeçalho precisa conter 'CAR' "
            f"(colunas vistas: {', '.join(cabecalho) or '(nenhuma)'})"
        )

    # cria colunas que faltam (ex.: planilha só com a coluna CAR)
    campos_presentes = set(destino.values())
    for titulo, campo in COLUNAS_PADRAO:
        if campo not in campos_presentes:
            cabecalho.append(titulo)
            destino[len(cabecalho) - 1] = campo
            for l in linhas[1:]:
                l.append("")
    linhas[0] = cabecalho

    total = preenchidos = pulados = nao_encontrados = invalidos = 0
    parciais = 0  # preenchidos só com o que dá offline (rede bloqueada)
    sem_rede = False  # uma vez bloqueado, não insiste no resto da planilha
    campos_offline = {"municipio", "uf", "estado"}
    perimetros: list[dict] = []  # feições de todos os CARs (saída combinada)
    baixar_perimetro = None
    if feicoes:
        try:
            from baixar_feicao import wfs_geojson as baixar_perimetro  # noqa: F401
        except Exception:
            baixar_perimetro = None
    for numero_linha, linha in enumerate(linhas[1:], start=2):
        while len(linha) < len(cabecalho):
            linha.append("")
        texto_car = linha[col_car]
        if not str(texto_car).strip():
            continue
        total += 1
        car = normalizar_car(texto_car)
        if not car:
            invalidos += 1
            print(f"  linha {numero_linha}: CAR inválido: {texto_car!r}", file=sys.stderr)
            continue
        vazias = [i for i in destino if not str(linha[i]).strip()]
        alvo = list(destino) if sobrescrever else vazias
        if not alvo:
            pulados += 1  # já estava completa
            continue

        # preenche município/estado/UF do próprio número (offline, sempre)
        offline = resolver_offline(car)
        for i in alvo:
            if destino[i] in campos_offline and offline.get(destino[i]):
                linha[i] = offline[destino[i]]

        # o resto (lat/long/área/módulos) exige a API
        falta_api = [i for i in alvo if destino[i] not in campos_offline]
        if sem_rede:
            parciais += 1
            continue
        if not falta_api:
            preenchidos += 1
            continue
        try:
            dados = consultar(car)
        except BloqueioDeRede:
            sem_rede = True
            parciais += 1
            continue
        time.sleep(PAUSA_S)
        if dados is None:
            nao_encontrados += 1
            print(f"  linha {numero_linha}: CAR não encontrado no SICAR: {car}", file=sys.stderr)
            continue
        resultado = linha_resultado(dados, decimal)
        for i in alvo:
            linha[i] = str(resultado.get(destino[i], ""))
        preenchidos += 1

        # perímetro do imóvel (WFS) — acumula p/ a saída combinada
        if baixar_perimetro is not None:
            try:
                fc = baixar_perimetro("iru", car)
                for f in fc.get("features", []):
                    props = f.setdefault("properties", {})
                    props["camada"] = "perimetro_imovel"
                    props.setdefault("cod_imovel", car)
                    perimetros.append(f)
                time.sleep(PAUSA_S)
            except BloqueioDeRede:
                sem_rede = True
            except Exception as e:
                print(f"  linha {numero_linha}: perímetro não baixado: {e}", file=sys.stderr)

    if saida is None:
        saida = caminho.with_name(f"{caminho.stem}-preenchida{caminho.suffix}")
    if saida.suffix.lower() == ".xlsx":
        escrever_xlsx(saida, linhas)
    else:
        escrever_csv(saida, linhas)
    resumo = (
        f"{saida.name}: {total} CAR(s) — {preenchidos} completo(s), "
        f"{pulados} já preenchido(s), {nao_encontrados} não encontrado(s), {invalidos} inválido(s)"
    )
    if parciais:
        resumo += f", {parciais} PARCIAL(is) (só município/estado)"
    print(resumo)

    # perímetros de TODOS os CARs num só arquivo por formato (GeoJSON +
    # Shapefile + KML) ao lado da planilha — pronto p/ abrir no QGIS de uma vez
    if perimetros:
        colecao = {"type": "FeatureCollection",
                   "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4674"}},
                   "features": perimetros}
        base = saida.with_name(f"{saida.stem}-perimetros")
        gj = base.with_suffix(".geojson")
        gj.write_text(json.dumps(colecao, ensure_ascii=False), encoding="utf-8")
        gerados = [gj]
        try:
            from converter import converter as _converter
            gerados += _converter(gj, base, {"shp", "kml"})
        except Exception as e:
            print(f"(conversão shp/kml falhou: {e})", file=sys.stderr)
        print(f"perímetros ({len(perimetros)} imóvel(is)) — SIRGAS 2000:")
        for g in gerados:
            print(f"  {g}")
    if sem_rede:
        print(f"\nAVISO: {MSG_SEM_REDE}\nMunicípio e estado foram preenchidos "
              f"offline pelo código IBGE do número; lat/long e área ficaram em "
              f"branco — rode no Claude Code/Cowork para completar.", file=sys.stderr)


# -------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="Consulta pública do CAR (SICAR)")
    ap.add_argument("entrada", help="número do CAR OU caminho de planilha .csv/.xlsx")
    ap.add_argument("-o", "--saida", help="arquivo de saída (planilha)")
    ap.add_argument("--decimal", action="store_true", help="lat/long em graus decimais")
    ap.add_argument("--sobrescrever", action="store_true", help="reconsulta até células já preenchidas")
    ap.add_argument("--sem-feicao", action="store_true",
                    help="NÃO baixar o perímetro (por padrão, 1 CAR já vem com o GeoJSON)")
    args = ap.parse_args()

    caminho = Path(args.entrada)
    if caminho.suffix.lower() in (".csv", ".xlsx") and caminho.exists():
        preencher_planilha(
            caminho, Path(args.saida) if args.saida else None,
            args.decimal, args.sobrescrever, feicoes=not args.sem_feicao,
        )
        return

    car = normalizar_car(args.entrada)
    if not car:
        sys.exit(f"CAR inválido: {args.entrada!r} (esperado UF-1234567-32 caracteres hex)")
    try:
        dados = consultar(car)
    except BloqueioDeRede:
        # sem internet: entrega o que dá do próprio número e explica
        off = resolver_offline(car)
        print(json.dumps({
            "car": car,
            "municipio": off["municipio"],
            "estado": off["estado"],
            "uf": off["uf"],
            "latitude": None,
            "longitude": None,
            "area_ha": None,
            "modulos_fiscais": None,
            "_parcial": True,
            "_aviso": MSG_SEM_REDE,
        }, ensure_ascii=False, indent=2))
        sys.exit(3)
    if dados is None:
        sys.exit(f"CAR não encontrado no SICAR: {car}")
    r = linha_resultado(dados, args.decimal)

    # PADRÃO (2026-08-12): consultar 1 CAR já traz o PERÍMETRO junto, nos 3
    # formatos (GeoJSON + Shapefile + KML) — o usuário não pede o shape num
    # 2º passo. Arquivos ao lado; --sem-feicao desliga.
    feicoes_geradas: list[str] = []
    if not args.sem_feicao:
        try:
            from baixar_feicao import wfs_geojson  # mesmo diretório
            from converter import converter as _converter

            perimetro = wfs_geojson("iru", car)
            feats = perimetro.get("features", [])
            if feats:
                for f in feats:
                    f.setdefault("properties", {})["camada"] = "perimetro_imovel"
                gj = Path(f"{car}.geojson")
                gj.write_text(
                    json.dumps(
                        {"type": "FeatureCollection",
                         "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4674"}},
                         "features": feats},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                feicoes_geradas.append(str(gj))
                feicoes_geradas += [str(p) for p in _converter(gj, gj.with_suffix(""), {"shp", "kml"})]
        except Exception as e:  # feição é um bônus: falha aqui não derruba a consulta
            print(f"(perímetro não baixado: {e})", file=sys.stderr)

    print(json.dumps({
        "car": dados.get("codeProperty", car),
        "municipio": r["municipio"],
        "estado": r["estado"],
        "uf": r["uf"],
        "latitude": r["latitude"],
        "longitude": r["longitude"],
        "area_ha": r["area"],
        "modulos_fiscais": r["modulos"],
        "data_cadastro": r["cadastro"],
        "bounding_box": dados.get("bounderBox", ""),
        "feicoes": feicoes_geradas,  # perímetro em GeoJSON + Shapefile(.zip) + KML
    }, ensure_ascii=False, indent=2))
    if feicoes_geradas:
        print("\nperímetro salvo (SIRGAS 2000, pronto p/ QGIS/Earth):", file=sys.stderr)
        for p in feicoes_geradas:
            print(f"  {p}", file=sys.stderr)


if __name__ == "__main__":
    main()
