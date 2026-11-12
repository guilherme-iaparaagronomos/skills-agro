"""Leitor mínimo de shapefile (pontos e polígonos), sem dependências externas.

Cobre o que a skill precisa: .shp tipos 1/11/21 (Point/Z/M) e 5/15/25
(Polygon/Z/M), .dbf (atributos) e .prj (detecção da zona UTM). Geometria fora
disso (linhas, multipoint): converta para GeoJSON antes.
"""

import re
import struct
from pathlib import Path


def _ler_dbf(caminho):
    """Lê os atributos do .dbf — devolve lista de dicts (uma por feição)."""
    dados = Path(caminho).read_bytes()
    n_reg = struct.unpack('<I', dados[4:8])[0]
    tam_cab, tam_reg = struct.unpack('<HH', dados[8:12])
    campos = []
    pos = 32
    while pos < tam_cab - 1 and dados[pos] != 0x0D:
        nome = dados[pos:pos + 11].split(b'\x00')[0].decode('ascii', 'replace')
        largura = dados[pos + 16]
        campos.append((nome, largura))
        pos += 32
    registros = []
    pos = tam_cab
    for _ in range(n_reg):
        bruto = dados[pos:pos + tam_reg]
        pos += tam_reg
        if not bruto or bruto[0:1] == b'*':  # registro marcado como apagado
            continue
        reg, cursor = {}, 1
        for nome, largura in campos:
            valor = bruto[cursor:cursor + largura]
            cursor += largura
            try:
                texto = valor.decode('utf-8').strip()
            except UnicodeDecodeError:
                texto = valor.decode('cp1252', 'replace').strip()
            reg[nome] = texto
        registros.append(reg)
    return registros


def zona_do_prj(wkt):
    """Extrai (zona, sul?) de um .prj com UTM; None se não der pra afirmar."""
    m = re.search(r'UTM[_ ]?zone[_ ]?(\d+)\s*([NS])?', wkt, re.IGNORECASE)
    if not m:
        return None
    zona = int(m.group(1))
    if m.group(2):
        sul = m.group(2).upper() == 'S'
    else:
        sul = bool(re.search(r'false_northing"?\s*,\s*10000000', wkt, re.IGNORECASE))
    return zona, sul


def ler_shp(caminho):
    """Lê um shapefile de pontos ou polígonos.

    Devolve (tipo, geometrias, atributos, zona):
      tipo 'ponto'    → geometrias = [(x, y), ...]
      tipo 'poligono' → geometrias = [[anel=[(x, y), ...], ...], ...]
      atributos = dicts do .dbf (mesma ordem); zona = (n, sul?) do .prj ou None.
    """
    caminho = Path(caminho)
    dados = caminho.read_bytes()
    tipo_shp = struct.unpack('<i', dados[32:36])[0]
    if tipo_shp in (1, 11, 21):
        tipo = 'ponto'
    elif tipo_shp in (5, 15, 25):
        tipo = 'poligono'
    else:
        raise ValueError(
            f'shapefile tipo {tipo_shp} não suportado — use pontos ou polígonos, '
            'ou converta para GeoJSON'
        )

    geometrias = []
    pos = 100
    while pos + 8 <= len(dados):
        _, tam = struct.unpack('>ii', dados[pos:pos + 8])
        c = dados[pos + 8:pos + 8 + tam * 2]
        pos += 8 + tam * 2
        t = struct.unpack('<i', c[:4])[0]
        if t == 0:  # feição nula
            geometrias.append(None)
        elif tipo == 'ponto':
            geometrias.append(struct.unpack('<dd', c[4:20]))
        else:
            n_partes, n_pontos = struct.unpack('<ii', c[36:44])
            partes = struct.unpack(f'<{n_partes}i', c[44:44 + 4 * n_partes])
            base = 44 + 4 * n_partes
            plano = struct.unpack(f'<{2 * n_pontos}d', c[base:base + 16 * n_pontos])
            xy = list(zip(plano[0::2], plano[1::2]))
            aneis = []
            for i, ini in enumerate(partes):
                fim = partes[i + 1] if i + 1 < n_partes else n_pontos
                aneis.append(xy[ini:fim])
            geometrias.append(aneis)

    dbf = caminho.with_suffix('.dbf')
    atributos = _ler_dbf(dbf) if dbf.exists() else [{} for _ in geometrias]
    prj = caminho.with_suffix('.prj')
    zona = None
    if prj.exists():
        zona = zona_do_prj(prj.read_text(encoding='utf-8', errors='replace'))
    return tipo, geometrias, atributos, zona


if __name__ == '__main__':
    # exemplo embutido: monta um shapefile de 2 pontos em memória e relê
    import io, tempfile, os

    shp = io.BytesIO()
    reg = struct.pack('<i', 1) + struct.pack('<dd', -47.5, -22.5)
    reg2 = struct.pack('<i', 1) + struct.pack('<dd', -47.4, -22.4)
    corpo = (struct.pack('>ii', 1, len(reg) // 2) + reg
             + struct.pack('>ii', 2, len(reg2) // 2) + reg2)
    cab = struct.pack('>i', 9994) + b'\x00' * 20 + struct.pack('>i', (100 + len(corpo)) // 2)
    cab += struct.pack('<ii', 1000, 1)  # versão + tipo ponto
    cab += struct.pack('<8d', -47.5, -22.5, -47.4, -22.4, 0, 0, 0, 0)
    shp.write(cab + corpo)

    with tempfile.TemporaryDirectory() as d:
        arq = os.path.join(d, 'teste.shp')
        with open(arq, 'wb') as f:
            f.write(shp.getvalue())
        tipo, geoms, attrs, zona = ler_shp(arq)
        assert tipo == 'ponto' and len(geoms) == 2 and geoms[0] == (-47.5, -22.5)
        print('ler_shp OK:', tipo, geoms)
    assert zona_do_prj('PROJCS["SIRGAS_2000_UTM_Zone_23S"...') == (23, True)
    assert zona_do_prj('...UTM zone 22, PARAMETER["false_northing",10000000]...') == (22, True)
    print('zona_do_prj OK')
