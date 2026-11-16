"""Shapefile: leitura e gravação em Python puro (.shp, .shx, .dbf, .prj e .cpg).

Lê pontos, multipontos, linhas e polígonos (com ou sem Z e M; Z e M são
descartados) e os atributos do .dbf, com a codificação do .cpg ou, sem ele,
UTF-8 e depois cp1252. Grava os mesmos tipos, com .cpg em UTF-8.

Limites do formato que a gravação respeita e avisa:
- nome de campo com até 10 caracteres, sem acento;
- texto com até 254 bytes;
- um tipo de geometria por arquivo.
"""

import datetime
import re
import struct
import unicodedata

import geom

TIPOS = {1: 'Point', 11: 'Point', 21: 'Point', 8: 'MultiPoint', 18: 'MultiPoint', 28: 'MultiPoint',
         3: 'LineString', 13: 'LineString', 23: 'LineString', 5: 'Polygon', 15: 'Polygon', 25: 'Polygon'}
CODECS = {'utf8': 'utf-8', 'utf-8': 'utf-8', '65001': 'utf-8', '1252': 'cp1252', 'cp1252': 'cp1252', 'windows-1252': 'cp1252',
          'ansi 1252': 'cp1252', 'ansi': 'cp1252', 'latin1': 'latin-1', 'iso-8859-1': 'latin-1', 'iso8859-1': 'latin-1', '88591': 'latin-1',
          '850': 'cp850', 'cp850': 'cp850', 'oem 850': 'cp850', '437': 'cp437', 'cp437': 'cp437', 'oem 437': 'cp437'}
LDID = {0x03: 'cp1252', 0x57: 'cp1252', 0x02: 'cp850', 0x01: 'cp437', 0x0D: 'cp850'}


# ---------------------------------------------------------------- leitura

def _texto(bruto, codec):
    if codec:
        return bruto.decode(codec, 'replace')
    try:
        return bruto.decode('utf-8')
    except UnicodeDecodeError:
        return bruto.decode('cp1252', 'replace')


def ler_dbf(dados, cpg=None):
    """Devolve (campos, registros, codec): campos = [(nome, tipo, largura, casas)],
    registros = [dict ou None para registro apagado]."""
    if len(dados) < 32:
        return [], [], None
    n_reg = struct.unpack('<I', dados[4:8])[0]
    tam_cab, tam_reg = struct.unpack('<HH', dados[8:12])
    codec = CODECS.get((cpg or '').strip().lower()) or LDID.get(dados[29])
    campos, pos = [], 32
    while pos + 32 <= tam_cab and dados[pos] != 0x0D:
        nome = _texto(dados[pos:pos + 11].split(b'\x00')[0], codec).strip()
        campos.append((nome, chr(dados[pos + 11]), dados[pos + 16], dados[pos + 17]))
        pos += 32
    registros, pos = [], tam_cab
    for _ in range(n_reg):
        bruto = dados[pos:pos + tam_reg]
        pos += tam_reg
        if len(bruto) < tam_reg:
            break
        if bruto[0:1] == b'*':
            registros.append(None)
            continue
        reg, cursor = {}, 1
        for nome, tipo, largura, casas in campos:
            valor = _texto(bruto[cursor:cursor + largura], codec).strip().strip('\x00')
            cursor += largura
            if tipo in ('N', 'F'):
                if not valor or set(valor) <= {'*'}:
                    reg[nome] = None
                else:
                    try:
                        reg[nome] = int(valor) if casas == 0 and re.fullmatch(r'[-+]?\d+', valor) else float(valor)
                    except ValueError:
                        reg[nome] = valor
            elif tipo == 'D':
                reg[nome] = f'{valor[:4]}-{valor[4:6]}-{valor[6:8]}' if re.fullmatch(r'\d{8}', valor) else (valor or None)
            elif tipo == 'L':
                reg[nome] = True if valor[:1] in 'TtYySs' and valor else (False if valor[:1] in 'FfNn' and valor else None)
            else:
                reg[nome] = valor
        registros.append(reg)
    return campos, registros, codec or 'utf-8, e cp1252 onde não era UTF-8'


def _geometria(c, avisos):
    t = struct.unpack('<i', c[:4])[0]
    if t == 0:
        return None
    if t not in TIPOS:
        raise ValueError(f'tipo de geometria {t} do shapefile não é lido (MultiPatch e afins): exporte como polígono no QGIS')
    if t in (11, 21, 13, 15, 18, 23, 25, 28):
        avisos.add('o arquivo tem altitude ou medida (Z/M): foram descartadas')
    base = TIPOS[t]
    if base == 'Point':
        x, y = struct.unpack('<dd', c[4:20])
        if x < -1e38 or y < -1e38:  # "sem dado" do formato
            return None
        return {'type': 'Point', 'coordinates': (x, y)}
    if base == 'MultiPoint':
        n = struct.unpack('<i', c[36:40])[0]
        plano = struct.unpack(f'<{2 * n}d', c[40:40 + 16 * n])
        pts = list(zip(plano[0::2], plano[1::2]))
        if not pts:
            return None
        return {'type': 'Point', 'coordinates': pts[0]} if n == 1 else {'type': 'MultiPoint', 'coordinates': pts}
    n_partes, n_pontos = struct.unpack('<ii', c[36:44])
    inicio = struct.unpack(f'<{n_partes}i', c[44:44 + 4 * n_partes])
    b = 44 + 4 * n_partes
    plano = struct.unpack(f'<{2 * n_pontos}d', c[b:b + 16 * n_pontos])
    xy = list(zip(plano[0::2], plano[1::2]))
    pedacos = [xy[ini:(inicio[i + 1] if i + 1 < n_partes else n_pontos)] for i, ini in enumerate(inicio)]
    if base == 'LineString':
        pedacos = [p for p in pedacos if len(p) >= 1]
        if not pedacos:
            return None
        return {'type': 'LineString', 'coordinates': pedacos[0]} if len(pedacos) == 1 else {'type': 'MultiLineString', 'coordinates': pedacos}
    # os papéis (externo ou furo) saem do aninhamento, não do sentido em que o arquivo gravou
    return geom.de_poligonos(geom.organizar_aneis([p for p in pedacos if len(p) >= 3]))


def ler(arquivos):
    """arquivos = {'shp': bytes, 'dbf': bytes?, 'prj': bytes?, 'cpg': bytes?}.
    Devolve {'feicoes', 'campos', 'prj', 'avisos'}."""
    dados = arquivos['shp']
    if len(dados) < 100 or struct.unpack('>i', dados[:4])[0] != 9994:
        raise ValueError('o arquivo .shp não é um shapefile válido')
    avisos = set()
    geometrias, pos = [], 100
    while pos + 8 <= len(dados):
        _, tam = struct.unpack('>ii', dados[pos:pos + 8])
        c = dados[pos + 8:pos + 8 + tam * 2]
        pos += 8 + tam * 2
        if len(c) < 4:
            break
        geometrias.append(_geometria(c, avisos))
    campos, registros, codec = [], [], None
    if arquivos.get('dbf'):
        cpg = arquivos['cpg'].decode('ascii', 'replace') if arquivos.get('cpg') else None
        campos, registros, codec = ler_dbf(arquivos['dbf'], cpg)
        if len(registros) != len(geometrias):
            avisos.add(f'o .dbf tem {len(registros)} registros e o .shp tem {len(geometrias)} geometrias: os atributos podem estar desalinhados')
    else:
        avisos.add('sem o .dbf: as feições vieram sem atributos')
    feicoes = []
    for i, g in enumerate(geometrias):
        reg = registros[i] if i < len(registros) else {}
        if reg is None:  # registro marcado como apagado no .dbf
            continue
        feicoes.append({'geometry': g, 'properties': dict(reg)})
    prj = arquivos['prj'].decode('utf-8', 'replace') if arquivos.get('prj') else None
    return {'feicoes': feicoes, 'campos': [c[0] for c in campos], 'prj': prj, 'avisos': sorted(avisos), 'codificacao': codec}


# ---------------------------------------------------------------- gravação

def _nome_de_campo(nome, usados):
    s = unicodedata.normalize('NFKD', str(nome))
    s = re.sub(r'[^A-Za-z0-9_]', '_', ''.join(c for c in s if not unicodedata.combining(c))) or 'campo'
    if s[0].isdigit():
        s = '_' + s
    base, k = s[:10], 1
    while base.lower() in usados:
        sufixo = f'_{k}'
        base, k = s[:10 - len(sufixo)] + sufixo, k + 1
    usados.add(base.lower())
    return base


_NUMERO = re.compile(r'-?(0|[1-9]\d*)(\.\d+)?')


def _eh_numero(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return v == v and abs(v) != float('inf')
    # texto que é número de verdade; "007" e "1,5" continuam texto (zero à esquerda é código)
    return isinstance(v, str) and len(v) <= 18 and bool(_NUMERO.fullmatch(v.strip()))


def _coluna(valores):
    """Decide o tipo da coluna do .dbf. Devolve (tipo, largura, casas, textos)."""
    presentes = [v for v in valores if v is not None and v != '']
    if presentes and all(isinstance(v, bool) for v in presentes):
        return 'L', 1, 0, ['T' if v is True else 'F' if v is False else '?' for v in valores]
    if presentes and all(_eh_numero(v) for v in presentes):
        casas = 0
        for v in presentes:
            t = repr(float(v)) if isinstance(v, float) else str(v).strip()
            if 'e' in t.lower():
                casas = max(casas, 10)
            elif '.' in t and not t.endswith('.0'):
                casas = max(casas, len(t.split('.')[1]))
        casas = min(casas, 12)
        textos = ['' if v is None or v == '' else (f'{float(v):.{casas}f}' if casas else str(int(float(v)))) for v in valores]
        largura = max(len(t) for t in textos)
        if largura <= 19:
            return 'N', max(largura, 1), casas, textos
    textos = ['' if v is None else ('true' if v is True else 'false' if v is False else str(v)) for v in valores]
    return 'C', 0, 0, textos


def gravar_dbf(campos, feicoes):
    """Devolve (bytes, avisos). Nomes cortados e textos truncados viram aviso."""
    avisos, usados, colunas = [], set(), []
    for campo in campos:
        nome = _nome_de_campo(campo, usados)
        if nome != campo:
            avisos.append(f'campo "{campo}" virou "{nome}" (o shapefile aceita 10 caracteres, sem acento)')
        tipo, largura, casas, textos = _coluna([f['properties'].get(campo) for f in feicoes])
        if tipo == 'C':
            brutos = [t.encode('utf-8') for t in textos]
            cortados = sum(1 for b in brutos if len(b) > 254)
            if cortados:
                avisos.append(f'campo "{campo}": {cortados} valor(es) cortado(s) em 254 bytes (limite do shapefile)')
            brutos = [b[:254].decode('utf-8', 'ignore').encode('utf-8') for b in brutos]
            largura = max([len(b) for b in brutos] + [1])
            celulas = [b.ljust(largura, b' ') for b in brutos]
        else:
            celulas = [t.rjust(largura).encode('ascii') for t in textos]
        colunas.append((nome, tipo, largura, casas, celulas))
    if not colunas:  # o formato exige ao menos um campo
        colunas.append(('ID', 'N', 6, 0, [str(i + 1).rjust(6).encode('ascii') for i in range(len(feicoes))]))
    hoje = datetime.date.today()
    tam_reg = 1 + sum(c[2] for c in colunas)
    saida = bytearray(struct.pack('<B3BIHH20x', 3, hoje.year - 1900, hoje.month, hoje.day, len(feicoes), 32 + 32 * len(colunas) + 1, tam_reg))
    for nome, tipo, largura, casas, _ in colunas:
        saida += struct.pack('<11sc4xBB14x', nome.encode('ascii'), tipo.encode('ascii'), largura, casas)
    saida += b'\x0d'
    for i in range(len(feicoes)):
        saida += b' ' + b''.join(c[4][i] for c in colunas)
    saida += b'\x1a'
    return bytes(saida), avisos


def _registro(g, tipo_shp):
    if g is None:
        return struct.pack('<i', 0)
    if tipo_shp == 1:
        return struct.pack('<i2d', 1, *g['coordinates'][:2])
    if tipo_shp == 8:
        pts = [g['coordinates']] if g['type'] == 'Point' else list(g['coordinates'])
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return struct.pack('<i4di', 8, min(xs), min(ys), max(xs), max(ys), len(pts)) + b''.join(struct.pack('<2d', p[0], p[1]) for p in pts)
    if tipo_shp == 3:
        pedacos = [g['coordinates']] if g['type'] == 'LineString' else list(g['coordinates'])
    else:  # no shapefile o anel externo anda no sentido horário e o furo no anti-horário
        pedacos = [geom.orientar(geom.fechar(anel), k != 0) for poli in geom.poligonos_de(g) for k, anel in enumerate(poli)]
    pts = [p for ped in pedacos for p in ped]
    inicio, total = [], 0
    for ped in pedacos:
        inicio.append(total)
        total += len(ped)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (struct.pack('<i4d2i', tipo_shp, min(xs), min(ys), max(xs), max(ys), len(pedacos), len(pts))
            + struct.pack(f'<{len(inicio)}i', *inicio) + b''.join(struct.pack('<2d', p[0], p[1]) for p in pts))


def gravar(feicoes, campos, prj_texto):
    """Um shapefile de UM tipo de geometria. Devolve ({'shp', 'shx', 'dbf', 'prj', 'cpg'}, avisos)."""
    familias = {geom.familia(f['geometry']) for f in feicoes if f['geometry']}
    if len(familias) > 1:
        raise ValueError('o shapefile leva um tipo de geometria por arquivo: separe pontos, linhas e polígonos')
    fam = familias.pop() if familias else 'ponto'
    if fam == 'ponto':
        tipo_shp = 8 if any(f['geometry'] and f['geometry']['type'] == 'MultiPoint' for f in feicoes) else 1
    else:
        tipo_shp = 3 if fam == 'linha' else 5
    shp, shx = bytearray(100), bytearray(100)
    xs, ys = [], []
    for i, f in enumerate(feicoes, 1):
        corpo = _registro(f['geometry'], tipo_shp)
        shx += struct.pack('>2i', len(shp) // 2, len(corpo) // 2)
        shp += struct.pack('>2i', i, len(corpo) // 2) + corpo
        if f['geometry']:
            for seq in geom.partes(f['geometry']):
                xs += [p[0] for p in seq]
                ys += [p[1] for p in seq]
    cx = (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 0.0, 0.0)

    def cabecalho(tamanho):
        return struct.pack('>7i', 9994, 0, 0, 0, 0, 0, tamanho // 2) + struct.pack('<2i8d', 1000, tipo_shp, *cx, 0, 0, 0, 0)
    shp[:100], shx[:100] = cabecalho(len(shp)), cabecalho(len(shx))
    dbf, avisos = gravar_dbf(campos, feicoes)
    return {'shp': bytes(shp), 'shx': bytes(shx), 'dbf': dbf, 'prj': prj_texto.encode('ascii'), 'cpg': b'UTF-8'}, avisos


if __name__ == '__main__':
    quad = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0), (0.0, 0.0)]
    furo = [(40.0, 40.0), (40.0, 60.0), (60.0, 60.0), (60.0, 40.0), (40.0, 40.0)]
    longo = 'x' * 300
    fs = [{'geometry': {'type': 'Polygon', 'coordinates': [quad, furo]},
           'properties': {'Talhão': 'Baixada São João', 'produtividade_media': 61.25, 'produtividade_max': 70, 'codigo': '007', 'obs': longo, 'ativo': True}},
          {'geometry': {'type': 'MultiPolygon', 'coordinates': [[quad], [[(200.0, 0.0), (300.0, 0.0), (300.0, 50.0), (200.0, 0.0)]]]},
           'properties': {'Talhão': 'T02', 'produtividade_media': None, 'produtividade_max': 55, 'codigo': '012', 'obs': '', 'ativo': False}},
          {'geometry': None, 'properties': {'Talhão': 'sem geometria', 'produtividade_media': 1.5, 'produtividade_max': 1, 'codigo': '1', 'obs': 'a', 'ativo': None}}]
    campos = ['Talhão', 'produtividade_media', 'produtividade_max', 'codigo', 'obs', 'ativo']
    arqs, avisos = gravar(fs, campos, 'PRJ')
    assert any('"produtividade_max" virou "produtiv_1"' in a for a in avisos) and any('254 bytes' in a for a in avisos), avisos
    lido = ler(arqs)
    assert lido['campos'] == ['Talhao', 'produtivid', 'produtiv_1', 'codigo', 'obs', 'ativo'], lido['campos']
    p0, p1, p2 = [f['properties'] for f in lido['feicoes']]
    assert p0['Talhao'] == 'Baixada São João' and p0['produtivid'] == 61.25 and p0['produtiv_1'] == 70 and p0['codigo'] == '007'
    assert p1['produtivid'] is None and p0['ativo'] is True and p1['ativo'] is False and len(p0['obs']) == 254
    g0, g1, g2 = [f['geometry'] for f in lido['feicoes']]
    assert g0['type'] == 'Polygon' and len(g0['coordinates']) == 2 and abs(geom.area_m2(g0) - 9600) < 1e-9
    assert g1['type'] == 'MultiPolygon' and abs(geom.area_m2(g1) - 12500) < 1e-9 and g2 is None
    assert struct.unpack('<i', arqs['shp'][32:36])[0] == 5 and struct.unpack('>i', arqs['shp'][24:28])[0] * 2 == len(arqs['shp'])
    # o anel externo vai no sentido horário (regra do formato)
    reg = arqs['shp'][108:]
    n_partes, n_pontos = struct.unpack('<ii', reg[36:44])
    b = 44 + 4 * n_partes
    primeiros = struct.unpack('<10d', reg[b:b + 80])
    assert geom.area_assinada(list(zip(primeiros[0::2], primeiros[1::2]))) < 0
    # pontos, multipontos e linhas
    pts = [{'geometry': {'type': 'Point', 'coordinates': (1.5, 2.5)}, 'properties': {'n': 1}},
           {'geometry': {'type': 'MultiPoint', 'coordinates': [(1.0, 2.0), (3.0, 4.0)]}, 'properties': {'n': 2}}]
    lp = ler(gravar(pts, ['n'], 'PRJ')[0])
    assert lp['feicoes'][0]['geometry'] == {'type': 'Point', 'coordinates': (1.5, 2.5)} and lp['feicoes'][1]['geometry']['type'] == 'MultiPoint'
    lns = [{'geometry': {'type': 'LineString', 'coordinates': [(0.0, 0.0), (3.0, 4.0)]}, 'properties': {}},
           {'geometry': {'type': 'MultiLineString', 'coordinates': [[(0.0, 0.0), (1.0, 1.0)], [(5.0, 5.0), (6.0, 6.0), (7.0, 8.0)]]}, 'properties': {}}]
    ll = ler(gravar(lns, [], 'PRJ')[0])
    assert ll['feicoes'][0]['geometry']['coordinates'] == [(0.0, 0.0), (3.0, 4.0)] and len(ll['feicoes'][1]['geometry']['coordinates']) == 2
    assert ll['campos'] == ['ID'] and ll['feicoes'][1]['properties']['ID'] == 2
    try:
        gravar(fs[:1] + pts[:1], [], 'PRJ')
        raise AssertionError('devia recusar tipos misturados')
    except ValueError:
        pass
    # .dbf em cp1252 sem .cpg: os acentos são lidos
    velho, _ = gravar_dbf(['nome'], [{'properties': {'nome': 'Sao Joao'}}])
    velho = velho.replace(b'Sao Joao', 'São João'.encode('cp1252'))
    assert ler_dbf(velho)[1][0]['nome'] == 'São João'
    print('shapefile OK: polígono com furo, multipartes, pontos, linhas, campos cortados e avisados, tipos do .dbf, cp1252')
