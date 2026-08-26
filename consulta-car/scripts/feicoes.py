#!/usr/bin/env python3
"""Organiza o zip de FEIÇÕES baixado do Consulta Pública do CAR.

O download (botão "Baixar feições", após o USUÁRIO resolver o reCAPTCHA)
traz um zip com shapefiles por tema do cadastro (perímetro do imóvel,
reserva legal, APP etc.). Este script:

  1. extrai o zip — INCLUSIVE zips DENTRO do zip (o SICAR costuma entregar
     `Area_do_Imovel.zip` aninhado no pacote externo);
  2. lista os temas encontrados, com tipo de geometria, nº de registros e
     caixa envolvente;
  3. GERA O GEOJSON de cada tema, em SIRGAS 2000 (EPSG:4674) — é o polígono
     REAL, com todos os vértices, não a caixa envolvente.

Uso:
  python feicoes.py caminho/do/shape-car.zip
  python feicoes.py shape-car.zip -o pasta_destino
  python feicoes.py shape-car.zip --somente-perimetro

Somente biblioteca padrão (sem GDAL). O GeoJSON do perímetro serve de
entrada para `converter.py` (→ shapefile empacotado + KML) e para a skill
`krigagem-solo`.

POR QUE ESTE SCRIPT MUDOU (25/08): a versão anterior lia só o índice do zip
RAIZ e, com o pacote aninhado do SICAR, terminava em "nenhum .shp
encontrado" — sem entregar nada. Pior: sem um GeoJSON, quem estivesse com
pressa acabava usando a caixa envolvente (um retângulo de 4 pontos) como se
fosse o perímetro. Retângulo NÃO é perímetro: num imóvel rural ele inclui
terra de vizinhos, e alimentar krigagem ou laudo com isso produz mapa
errado com cara de certo.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zipfile
from pathlib import Path

# Console do Windows abre em cp1252, que não tem "→" nem "·". Sem isto o
# script MORRE com UnicodeEncodeError na primeira linha impressa — foi o que
# acontecia na versão anterior assim que ela encontrava um .shp. Nunca deixar
# a saída de texto derrubar um script que já fez o trabalho.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TIPOS_SHP = {
    0: "nulo", 1: "ponto", 3: "linha", 5: "polígono", 8: "multiponto",
    11: "ponto Z", 13: "linha Z", 15: "polígono Z", 21: "ponto M",
    23: "linha M", 25: "polígono M",
}
TIPOS_POLIGONO = {5, 15, 25}


# --------------------------------------------------------------- extração
def extrair_tudo(caminho: Path, destino: Path, nivel: int = 0) -> None:
    """Extrai o zip e, recursivamente, os zips que vierem dentro dele.

    O SICAR entrega `Area_do_Imovel.zip` dentro do pacote externo. Ler só o
    índice do zip de fora faz o .shp "não existir". O teto de profundidade é
    um freio de mão contra zip malicioso aninhado sem fim (zip bomb).
    """
    if nivel > 3:
        return
    with zipfile.ZipFile(caminho) as z:
        for membro in z.namelist():
            # nunca extrair para fora da pasta destino (zip slip)
            alvo = (destino / membro).resolve()
            if not str(alvo).startswith(str(destino.resolve())):
                print(f"  ignorado (caminho suspeito): {membro}", file=sys.stderr)
                continue
        z.extractall(destino)
    for interno in sorted(destino.rglob("*.zip")):
        sub = interno.with_suffix("")
        sub.mkdir(parents=True, exist_ok=True)
        try:
            extrair_tudo(interno, sub, nivel + 1)
        except zipfile.BadZipFile:
            print(f"  aviso: {interno.name} não é um zip válido", file=sys.stderr)


# ------------------------------------------------------------------- .shp
def cabecalho_shp(dados: bytes) -> dict | None:
    """Cabeçalho de 100 bytes de um .shp (formato ESRI)."""
    if len(dados) < 100 or struct.unpack(">i", dados[:4])[0] != 9994:
        return None
    tipo = struct.unpack("<i", dados[32:36])[0]
    xmin, ymin, xmax, ymax = struct.unpack("<4d", dados[36:68])
    return {
        "tipo_num": tipo,
        "tipo": TIPOS_SHP.get(tipo, f"tipo {tipo}"),
        "bbox": (round(xmin, 6), round(ymin, 6), round(xmax, 6), round(ymax, 6)),
    }


def _area_assinada(anel: list[list[float]]) -> float:
    """Fórmula do cadarço. Positiva = anti-horário."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(anel, anel[1:]):
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _orientado(anel: list[list[float]], exterior: bool) -> list[list[float]]:
    """Normaliza para o RFC 7946: exterior anti-horário, buraco horário."""
    anti_horario = _area_assinada(anel) > 0
    return anel if anti_horario == exterior else anel[::-1]


def _dentro(ponto: list[float], anel: list[list[float]]) -> bool:
    """Ponto dentro do anel (lançamento de raio)."""
    x, y = ponto
    dentro = False
    for (x1, y1), (x2, y2) in zip(anel, anel[1:]):
        if (y1 > y) != (y2 > y):
            corte = x1 + (y - y1) * (x2 - x1) / ((y2 - y1) or 1e-15)
            if x < corte:
                dentro = not dentro
    return dentro


def ler_poligonos(dados: bytes) -> list[list[list[list[float]]]]:
    """Lê os registros de polígono do .shp e devolve, por registro, a lista
    de anéis já na convenção do GeoJSON.

    QUEM É BURACO SE DECIDE POR CONTENÇÃO, não por orientação. A regra ESRI
    diz que o anel externo é horário e o buraco anti-horário, mas arquivo do
    mundo real desrespeita isso com frequência — inclusive um gerado pelo
    `converter.py` desta mesma skill, que até 25/08 gravava invertido.
    Confiar na orientação faria um buraco virar ilha e a área do imóvel sair
    errada. Contenção é geometria, não convenção: vale sempre.

    A orientação, essa sim, é normalizada NA SAÍDA: o RFC 7946 pede exterior
    anti-horário e buraco horário.
    """
    saida: list[list[list[list[float]]]] = []
    pos, fim = 100, len(dados)
    while pos + 8 <= fim:
        tamanho = struct.unpack(">i", dados[pos + 4:pos + 8])[0] * 2
        conteudo = dados[pos + 8:pos + 8 + tamanho]
        pos += 8 + tamanho
        if len(conteudo) < 44:
            continue
        tipo = struct.unpack("<i", conteudo[:4])[0]
        if tipo not in TIPOS_POLIGONO:
            continue
        n_partes, n_pontos = struct.unpack("<2i", conteudo[36:44])
        ini = 44
        partes = list(struct.unpack(f"<{n_partes}i", conteudo[ini:ini + n_partes * 4]))
        ini += n_partes * 4
        # Nos tipos Z e M os arrays extras vêm DEPOIS dos pontos, então ler
        # os primeiros n_pontos pares serve para os três tipos.
        pares = struct.unpack(f"<{n_pontos * 2}d", conteudo[ini:ini + n_pontos * 16])
        pontos = [[round(pares[i], 8), round(pares[i + 1], 8)] for i in range(0, len(pares), 2)]

        limites = partes + [n_pontos]
        aneis = []
        for i in range(n_partes):
            anel = pontos[limites[i]:limites[i + 1]]
            if len(anel) < 4:
                continue
            if anel[0] != anel[-1]:
                anel = anel + [anel[0]]
            aneis.append(anel)

        poligonos: list[list[list[list[float]]]] = []
        for anel in aneis:
            # buraco = primeiro ponto cai dentro de um exterior já aberto
            alvo = next((p for p in poligonos if _dentro(anel[0], p[0])), None)
            if alvo is None:
                poligonos.append([_orientado(anel, exterior=True)])
            else:
                alvo.append(_orientado(anel, exterior=False))
        saida.extend(poligonos)
    return saida


# ------------------------------------------------------------------- .dbf
def ler_dbf(caminho: Path) -> list[dict]:
    """Atributos do .dbf (stdlib). O SICAR grava em Latin-1; tento UTF-8
    primeiro porque arquivo re-exportado costuma vir assim."""
    dados = caminho.read_bytes()
    if len(dados) < 32:
        return []
    n_reg, inicio_dados, tam_reg = struct.unpack("<I2H", dados[4:12])
    campos, pos = [], 32
    while pos < len(dados) and dados[pos] != 0x0D:
        nome = dados[pos:pos + 11].split(b"\0")[0].decode("latin-1").strip()
        tamanho = dados[pos + 16]
        campos.append((nome, tamanho))
        pos += 32

    def texto(b: bytes) -> str:
        for cod in ("utf-8", "latin-1"):
            try:
                return b.decode(cod).strip()
            except UnicodeDecodeError:
                continue
        return b.decode("latin-1", "replace").strip()

    registros = []
    for i in range(n_reg):
        base = inicio_dados + i * tam_reg
        linha = dados[base:base + tam_reg]
        if not linha or linha[:1] == b"*":  # marcado como apagado
            continue
        reg, desloc = {}, 1
        for nome, tamanho in campos:
            reg[nome] = texto(linha[desloc:desloc + tamanho])
            desloc += tamanho
        registros.append(reg)
    return registros


# ------------------------------------------------------------------ saída
def escrever_geojson(shp: Path, destino: Path) -> tuple[Path, int, int] | None:
    """Gera o GeoJSON de um .shp. Devolve (arquivo, nº feições, nº vértices)."""
    dados = shp.read_bytes()
    cab = cabecalho_shp(dados)
    if not cab or cab["tipo_num"] not in TIPOS_POLIGONO:
        return None
    poligonos = ler_poligonos(dados)
    if not poligonos:
        return None

    dbf = shp.with_suffix(".dbf")
    atributos = ler_dbf(dbf) if dbf.exists() else []
    camada = shp.stem

    feicoes, vertices = [], 0
    for i, aneis in enumerate(poligonos):
        props = dict(atributos[i]) if i < len(atributos) else {}
        # nomes que o converter.py usa para nomear Placemark e colunas
        props.setdefault("camada", camada)
        if "cod_imovel" not in props:
            for chave in ("COD_IMOVEL", "cod_imove", "COD_IMOVE"):
                if chave in props:
                    props["cod_imovel"] = props[chave]
                    break
        vertices += sum(len(a) for a in aneis)
        feicoes.append({"type": "Feature", "geometry":
                        {"type": "Polygon", "coordinates": aneis}, "properties": props})

    fc = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4674"}},
        "features": feicoes,
    }
    arquivo = destino / f"{camada}.geojson"
    arquivo.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    return arquivo, len(feicoes), vertices


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Extrai o zip de feições do CAR e gera o GeoJSON do perímetro real"
    )
    ap.add_argument("zip", help="zip baixado do consulta.car.gov.br (Baixar feições)")
    ap.add_argument("-o", "--saida", help="pasta de extração (padrão: nome do zip)")
    ap.add_argument("--somente-perimetro", action="store_true",
                    help="gera GeoJSON só do tema AREA_IMOVEL")
    args = ap.parse_args()

    caminho = Path(args.zip)
    if not caminho.exists():
        sys.exit(f"arquivo não encontrado: {caminho}")

    destino = Path(args.saida) if args.saida else caminho.with_suffix("")
    destino.mkdir(parents=True, exist_ok=True)
    try:
        extrair_tudo(caminho, destino)
    except zipfile.BadZipFile:
        sys.exit("o arquivo não é um zip válido — o download pode ter falhado no meio")

    # varre a PASTA, não o índice do zip: assim pega .shp em qualquer nível
    shps = sorted(destino.rglob("*.shp"))
    if not shps:
        print(f"zip extraído em {destino} — nenhum .shp encontrado. Conteúdo:")
        for item in sorted(destino.rglob("*")):
            if item.is_file():
                print(f"  {item.relative_to(destino)}")
        sys.exit(
            "\nSe o pacote veio do 'Baixar feições' do SICAR, ele deveria conter shapefiles.\n"
            "Confirme se o download terminou e reenvie o arquivo."
        )

    print(f"{caminho.name} → {destino}/")
    perimetro_shp = None
    for shp in shps:
        cab = cabecalho_shp(shp.read_bytes())
        dbf = shp.with_suffix(".dbf")
        n_reg = len(ler_dbf(dbf)) if dbf.exists() else None
        rel = shp.relative_to(destino)
        if cab:
            xmin, ymin, xmax, ymax = cab["bbox"]
            print(f"  {rel}: {cab['tipo']}"
                  + (f" · {n_reg} registro(s)" if n_reg is not None else "")
                  + f" · bbox lon [{xmin}, {xmax}] lat [{ymin}, {ymax}]")
        else:
            print(f"  {rel}: cabeçalho inválido")
        if "AREA_IMOVEL" in shp.stem.upper() or "AREA_DO_IMOVEL" in shp.stem.upper():
            perimetro_shp = shp

    alvos = [perimetro_shp] if (args.somente_perimetro and perimetro_shp) else shps
    print("\nGeoJSON gerado (polígono real, SIRGAS 2000):")
    gerados = 0
    for shp in alvos:
        if shp is None:
            continue
        r = escrever_geojson(shp, destino)
        if not r:
            continue
        arquivo, n_feic, n_vert = r
        marca = "  ← PERÍMETRO DO IMÓVEL" if shp is perimetro_shp else ""
        print(f"  {arquivo.relative_to(destino)}: {n_feic} feição(ões) · {n_vert} vértices{marca}")
        gerados += 1

    if gerados == 0:
        print("  (nenhum tema poligonal — nada a converter)")
        return

    if perimetro_shp:
        geo = destino / f"{perimetro_shp.stem}.geojson"
        print(f"\nperímetro: {geo}")
        print(f"  shapefile + KML:  python converter.py \"{geo}\"")
        print("  krigagem-solo:    use este GeoJSON como --perimetro")


if __name__ == "__main__":
    main()
