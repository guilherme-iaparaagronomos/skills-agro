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


# ---------------------------------------------------------------- consulta
def normalizar_car(texto: str) -> str | None:
    """'pi-2200053-1bab.c06a...' -> 'PI-2200053-1BABC06A...' (ou None)."""
    bruto = re.sub(r"[.\s]", "", str(texto).strip().upper())
    return bruto if RE_CAR.match(bruto) else None


def consultar(car: str) -> dict | None:
    """Consulta um CAR normalizado. None = não encontrado; levanta em erro de rede."""
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
        except Exception as e:  # rede/5xx: espera e tenta de novo
            ultimo_erro = e
            time.sleep(1.5 * (tentativa + 1))
    raise RuntimeError(f"falha ao consultar {car}: {ultimo_erro}")


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
def preencher_planilha(caminho: Path, saida: Path | None, decimal: bool, sobrescrever: bool) -> None:
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
        dados = consultar(car)
        time.sleep(PAUSA_S)
        if dados is None:
            nao_encontrados += 1
            print(f"  linha {numero_linha}: CAR não encontrado no SICAR: {car}", file=sys.stderr)
            continue
        resultado = linha_resultado(dados, decimal)
        for i in alvo:
            linha[i] = str(resultado.get(destino[i], ""))
        preenchidos += 1

    if saida is None:
        saida = caminho.with_name(f"{caminho.stem}-preenchida{caminho.suffix}")
    if saida.suffix.lower() == ".xlsx":
        escrever_xlsx(saida, linhas)
    else:
        escrever_csv(saida, linhas)
    print(
        f"{saida.name}: {total} CAR(s) — {preenchidos} preenchido(s), "
        f"{pulados} já completo(s), {nao_encontrados} não encontrado(s), {invalidos} inválido(s)"
    )


# -------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="Consulta pública do CAR (SICAR)")
    ap.add_argument("entrada", help="número do CAR OU caminho de planilha .csv/.xlsx")
    ap.add_argument("-o", "--saida", help="arquivo de saída (planilha)")
    ap.add_argument("--decimal", action="store_true", help="lat/long em graus decimais")
    ap.add_argument("--sobrescrever", action="store_true", help="reconsulta até células já preenchidas")
    args = ap.parse_args()

    caminho = Path(args.entrada)
    if caminho.suffix.lower() in (".csv", ".xlsx") and caminho.exists():
        preencher_planilha(caminho, Path(args.saida) if args.saida else None, args.decimal, args.sobrescrever)
        return

    car = normalizar_car(args.entrada)
    if not car:
        sys.exit(f"CAR inválido: {args.entrada!r} (esperado UF-1234567-32 caracteres hex)")
    dados = consultar(car)
    if dados is None:
        sys.exit(f"CAR não encontrado no SICAR: {car}")
    r = linha_resultado(dados, args.decimal)
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
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
