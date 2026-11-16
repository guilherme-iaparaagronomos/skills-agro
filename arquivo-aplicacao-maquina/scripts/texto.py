"""GeoJSON, CSV e WKT: leitura e gravação.

GeoJSON: coleção, feição ou geometria solta; GeometryCollection é desmontada.
CSV: pontos por duas colunas de coordenadas (graus decimais, graus-minutos-
segundos ou metros; ponto ou vírgula decimal) ou geometria numa coluna WKT.
WKT: POINT, LINESTRING, POLYGON, as três MULTI e GEOMETRYCOLLECTION, com ou sem
Z/M e com o prefixo SRID= do PostGIS.
"""

import csv
import io
import json
import re
import unicodedata

import geom
import projecao

COLUNAS_X = ('lon', 'long', 'longitude', 'lng', 'x', 'este', 'leste', 'easting', 'e', 'coordx', 'coord_x', 'utm_e', 'utme', 'utm_x', 'utmx', 'xcoord', 'x_coord')
COLUNAS_Y = ('lat', 'latitude', 'y', 'norte', 'northing', 'n', 'coordy', 'coord_y', 'utm_n', 'utmn', 'utm_y', 'utmy', 'ycoord', 'y_coord')
COLUNAS_WKT = ('wkt', 'geom', 'geometry', 'geometria', 'the_geom', 'wkt_geom', 'shape')


def decodificar(dados):
    """Texto de um arquivo: UTF-8 (com ou sem BOM) e, se não for, cp1252."""
    if isinstance(dados, str):
        return dados
    try:
        return dados.decode('utf-8-sig')
    except UnicodeDecodeError:
        return dados.decode('cp1252', 'replace')


# ---------------------------------------------------------------- GeoJSON

def _dois(c, avisos):
    if len(c) > 2 and c[2] not in (0, 0.0, None):
        avisos.add('o arquivo tem altitude: foi descartada')
    return (float(c[0]), float(c[1]))


def geometria_geojson(g, avisos):
    """Geometria do GeoJSON em 2D. Devolve uma LISTA (a GeometryCollection vira várias)."""
    if not g or not g.get('type'):
        return [None]
    t = g['type']
    if t == 'GeometryCollection':
        saida = [x for parte in g.get('geometries', []) for x in geometria_geojson(parte, avisos) if x]
        return saida or [None]
    c = g.get('coordinates')
    if c is None or (isinstance(c, list) and not c):
        return [None]
    if t == 'Point':
        return [{'type': t, 'coordinates': _dois(c, avisos)}]
    if t in ('MultiPoint', 'LineString'):
        return [{'type': t, 'coordinates': [_dois(p, avisos) for p in c]}]
    if t in ('MultiLineString', 'Polygon'):
        return [{'type': t, 'coordinates': [[_dois(p, avisos) for p in s] for s in c]}]
    if t == 'MultiPolygon':
        return [{'type': t, 'coordinates': [[[_dois(p, avisos) for p in s] for s in poli] for poli in c]}]
    raise ValueError(f'tipo de geometria "{t}" não existe no GeoJSON')


def ler_geojson(dados):
    """Devolve {'feicoes', 'campos', 'avisos', 'epsg'} (epsg só quando o arquivo traz o membro "crs")."""
    try:
        gj = json.loads(decodificar(dados))
    except json.JSONDecodeError as e:
        raise ValueError(f'o arquivo não é um JSON válido ({e})')
    if not isinstance(gj, dict):
        raise ValueError('o arquivo JSON não é um GeoJSON')
    avisos, feicoes, campos = set(), [], []
    if gj.get('type') == 'FeatureCollection':
        brutas = gj.get('features') or []
    elif gj.get('type') == 'Feature':
        brutas = [gj]
    elif gj.get('type'):
        brutas = [{'geometry': gj, 'properties': {}}]
    else:
        raise ValueError('o arquivo JSON não é um GeoJSON (falta o "type")')
    for f in brutas:
        props = f.get('properties') or {}
        props = {str(k): (v if isinstance(v, (str, int, float, bool)) or v is None else json.dumps(v, ensure_ascii=False)) for k, v in props.items()}
        gs = geometria_geojson(f.get('geometry'), avisos)
        if len(gs) > 1:
            avisos.add('há GeometryCollection: cada parte virou uma feição, com os mesmos atributos')
        for g in gs:
            feicoes.append({'geometry': g, 'properties': dict(props)})
        for k in props:
            if k not in campos:
                campos.append(k)
    codigo = None
    nome_crs = str(((gj.get('crs') or {}).get('properties') or {}).get('name', ''))
    if nome_crs:
        m = re.search(r'EPSG:+(\d+)$', nome_crs, re.I)
        codigo = int(m.group(1)) if m else (4326 if 'CRS84' in nome_crs.upper() else None)
        if codigo is None:
            avisos.add(f'o arquivo declara o sistema "{nome_crs}", que não foi reconhecido')
    return {'feicoes': feicoes, 'campos': campos, 'avisos': sorted(avisos), 'epsg': codigo}


def _arred(seq, casas):
    return [[round(p[0], casas), round(p[1], casas)] for p in seq]


def geometria_para_geojson(g, casas):
    """Geometria pronta para o JSON: externo anti-horário e furo horário, como pede a RFC 7946."""
    if g is None:
        return None
    t, c = g['type'], g['coordinates']
    if t == 'Point':
        return {'type': t, 'coordinates': _arred([c], casas)[0]}
    if t in ('MultiPoint', 'LineString'):
        return {'type': t, 'coordinates': _arred(c, casas)}
    if t == 'MultiLineString':
        return {'type': t, 'coordinates': [_arred(s, casas) for s in c]}
    if t == 'Polygon':
        return {'type': t, 'coordinates': [_arred(a, casas) for a in geom.normalizar_poligono(c)]}
    return {'type': t, 'coordinates': [[_arred(a, casas) for a in geom.normalizar_poligono(poli)] for poli in c]}


def gravar_geojson(feicoes, campos, nome, casas=8, epsg=None):
    """Texto do GeoJSON. epsg só é escrito (membro "crs") quando a saída NÃO é em graus."""
    colecao = {'type': 'FeatureCollection', 'name': nome}
    if epsg:
        colecao['crs'] = {'type': 'name', 'properties': {'name': f'urn:ogc:def:crs:EPSG::{epsg}'}}
    colecao['features'] = [{'type': 'Feature', 'properties': {k: f['properties'].get(k) for k in campos},
                            'geometry': geometria_para_geojson(f['geometry'], casas)} for f in feicoes]
    return json.dumps(colecao, ensure_ascii=False, separators=(',', ':')).replace('{"type":"Feature"', '\n{"type":"Feature"') + '\n'


# ---------------------------------------------------------------- WKT

_PEDACO = re.compile(r'\s*([A-Za-z]+|\(|\)|,|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)')


class _Leitor:
    def __init__(self, texto):
        self.t, self.i = texto, 0

    def espia(self):
        m = _PEDACO.match(self.t, self.i)
        return m.group(1) if m else None

    def pega(self, esperado=None):
        m = _PEDACO.match(self.t, self.i)
        if not m:
            raise ValueError(f'WKT inválido perto de "{self.t[self.i:self.i + 30].strip()}"')
        self.i = m.end()
        if esperado and m.group(1) != esperado:
            raise ValueError(f'WKT inválido: esperava "{esperado}" e veio "{m.group(1)}"')
        return m.group(1)

    def fim(self):
        return not self.t[self.i:].strip(' \t\r\n;')

    def ponto(self, avisos):
        nums = []
        while self.espia() not in (',', ')', None):
            nums.append(float(self.pega()))
        if len(nums) < 2:
            raise ValueError('WKT inválido: ponto com menos de duas coordenadas')
        if len(nums) > 2:
            avisos.add('o arquivo tem altitude ou medida (Z/M): foram descartadas')
        return (nums[0], nums[1])

    def lista(self, item, avisos):
        """( item , item , … ) ou EMPTY."""
        if (self.espia() or '').upper() == 'EMPTY':
            self.pega()
            return []
        self.pega('(')
        saida = [item(avisos)]
        while self.espia() == ',':
            self.pega()
            saida.append(item(avisos))
        self.pega(')')
        return saida

    def geometria(self, avisos):
        tipo = self.pega().upper()
        while (self.espia() or '').upper() in ('Z', 'M', 'ZM'):
            self.pega()
        if tipo.endswith(('ZM',)) and tipo not in ('MULTIPOLYGONZM',):
            tipo = tipo[:-2]
        for sufixo in ('ZM', 'Z', 'M'):
            if tipo.endswith(sufixo) and tipo[:-len(sufixo)] in ('POINT', 'LINESTRING', 'POLYGON', 'MULTIPOINT', 'MULTILINESTRING', 'MULTIPOLYGON'):
                tipo = tipo[:-len(sufixo)]
        seq = lambda a: self.lista(self.ponto, a)
        if tipo == 'POINT':
            c = seq(avisos)
            return [{'type': 'Point', 'coordinates': c[0]}] if c else [None]
        if tipo == 'LINESTRING':
            c = seq(avisos)
            return [{'type': 'LineString', 'coordinates': c}] if c else [None]
        if tipo == 'POLYGON':
            c = self.lista(seq, avisos)
            return [{'type': 'Polygon', 'coordinates': c}] if c else [None]
        if tipo == 'MULTIPOINT':  # aceita MULTIPOINT (1 2, 3 4) e MULTIPOINT ((1 2), (3 4))
            def um(a):
                if self.espia() == '(':
                    self.pega()
                    p = self.ponto(a)
                    self.pega(')')
                    return p
                return self.ponto(a)
            c = self.lista(um, avisos)
            return [{'type': 'MultiPoint', 'coordinates': c}] if c else [None]
        if tipo == 'MULTILINESTRING':
            c = self.lista(seq, avisos)
            return [{'type': 'MultiLineString', 'coordinates': c}] if c else [None]
        if tipo == 'MULTIPOLYGON':
            c = self.lista(lambda a: self.lista(seq, a), avisos)
            return [{'type': 'MultiPolygon', 'coordinates': c}] if c else [None]
        if tipo == 'GEOMETRYCOLLECTION':
            partes = self.lista(self.geometria, avisos)
            return [g for parte in partes for g in parte if g] or [None]
        raise ValueError(f'WKT inválido: "{tipo}" não é um tipo de geometria')


def ler_wkt_texto(texto, avisos=None):
    """Todas as geometrias de um texto WKT (uma por linha ou várias em seguida).
    Devolve (geometrias, epsg): epsg vem do prefixo SRID=…; quando existe."""
    avisos = avisos if avisos is not None else set()
    codigo = None
    m = re.match(r'\s*SRID\s*=\s*(\d+)\s*;', texto, re.I)
    if m:
        codigo = int(m.group(1))
    texto = re.sub(r'SRID\s*=\s*\d+\s*;', ' ', texto, flags=re.I)
    leitor, saida = _Leitor(texto), []
    while not leitor.fim():
        saida += leitor.geometria(avisos)
        while leitor.t[leitor.i:leitor.i + 1] in (';', ' ', '\n', '\r', '\t') and leitor.i < len(leitor.t):
            leitor.i += 1
    return saida, codigo


def ler_wkt(dados):
    avisos = set()
    gs, codigo = ler_wkt_texto(decodificar(dados), avisos)
    if not gs:
        raise ValueError('nenhuma geometria WKT encontrada no arquivo')
    return {'feicoes': [{'geometry': g, 'properties': {}} for g in gs], 'campos': [], 'avisos': sorted(avisos), 'epsg': codigo}


def _n(v, casas):
    t = f'{v:.{casas}f}'
    return t.rstrip('0').rstrip('.') if '.' in t else t


def wkt_de(g, casas=8):
    if g is None:
        return 'GEOMETRYCOLLECTION EMPTY'
    seq = lambda s: '(' + ', '.join(f'{_n(p[0], casas)} {_n(p[1], casas)}' for p in s) + ')'
    poli = lambda aneis: '(' + ', '.join(seq(a) for a in geom.normalizar_poligono(aneis)) + ')'
    t, c = g['type'], g['coordinates']
    if t == 'Point':
        return 'POINT ' + seq([c])
    if t == 'MultiPoint':
        return 'MULTIPOINT (' + ', '.join(seq([p]) for p in c) + ')'
    if t == 'LineString':
        return 'LINESTRING ' + seq(c)
    if t == 'MultiLineString':
        return 'MULTILINESTRING (' + ', '.join(seq(s) for s in c) + ')'
    if t == 'Polygon':
        return 'POLYGON ' + poli(c)
    return 'MULTIPOLYGON (' + ', '.join(poli(p) for p in c) + ')'


def gravar_wkt(feicoes, casas=8, unico=False):
    """Uma geometria por linha; com unico=True, os polígonos de todas as feições num MULTIPOLYGON só."""
    if unico:
        polis = [p for f in feicoes if f['geometry'] for p in geom.poligonos_de(f['geometry'])]
        if not polis:
            raise ValueError('a saída em WKT único junta polígonos, e o arquivo não tem nenhum')
        return wkt_de(geom.de_poligonos(polis), casas) + '\n'
    return '\n'.join(wkt_de(f['geometry'], casas) for f in feicoes if f['geometry']) + '\n'


# ---------------------------------------------------------------- CSV

def _chave(nome):
    s = unicodedata.normalize('NFKD', str(nome or ''))
    return re.sub(r'[\s\-]+', '_', ''.join(c for c in s if not unicodedata.combining(c)).strip().lower())


_GMS = re.compile(r'^\s*([NSEWOLnsewol])?\s*([-+]?\d+(?:[.,]\d+)?)\s*[°ºd:\s]\s*(\d+(?:[.,]\d+)?)?\s*[\'′m:\s]?\s*(\d+(?:[.,]\d+)?)?\s*(?:"|″|\'\'|s)?\s*([NSEWOLnsewol])?\s*$')


def numero(texto):
    """'-23,5', '1.234,56', '512300.25', '23°30\\'15.5"S', 'S 23 30 15' -> float; None se não for número."""
    s = str(texto or '').strip()
    if not s:
        return None
    if re.fullmatch(r'[-+]?\d+', s):
        return float(s)
    if re.fullmatch(r'[-+]?\d*[.,]\d+(?:[eE][-+]?\d+)?', s) or re.fullmatch(r'[-+]?\d+[.,]', s):
        return float(s.replace(',', '.'))
    if re.fullmatch(r'[-+]?\d{1,3}(\.\d{3})+,\d+', s):  # 1.234.567,89
        return float(s.replace('.', '').replace(',', '.'))
    if re.fullmatch(r'[-+]?\d{1,3}(,\d{3})+\.\d+', s):  # 1,234,567.89
        return float(s.replace(',', ''))
    if re.fullmatch(r'[-+]?\d+(?:\.\d+)?[eE][-+]?\d+', s):
        return float(s)
    m = _GMS.match(s)
    if m and (m.group(3) or m.group(1) or m.group(5)):
        letra = (m.group(1) or m.group(5) or '').upper()
        g = float(m.group(2).replace(',', '.'))
        valor = abs(g) + float((m.group(3) or '0').replace(',', '.')) / 60 + float((m.group(4) or '0').replace(',', '.')) / 3600
        return -valor if (g < 0 or m.group(2).startswith('-') or letra in ('S', 'W', 'O')) else valor
    return None


def _delimitador(cabecalho):
    fora = re.sub(r'"[^"]*"', '', cabecalho)
    return max((';', '\t', '|', ','), key=lambda d: fora.count(d)) if any(d in fora for d in ';\t|,') else ','


def colunas_do_csv(dados):
    """Cabeçalho, linhas e as colunas candidatas: (campos, linhas, col_x, col_y, col_wkt, delimitador).
    Candidata ambígua ou ausente volta None: quem chama pergunta ao usuário."""
    texto = decodificar(dados)
    primeira = next((l for l in texto.splitlines() if l.strip()), '')
    delim = _delimitador(primeira)
    leitor = csv.reader(io.StringIO(texto, newline=''), delimiter=delim)
    tabela = [l for l in leitor if any(c.strip() for c in l)]
    if not tabela:
        raise ValueError('o CSV está vazio')
    campos = [c.strip() or f'coluna{i + 1}' for i, c in enumerate(tabela[0])]
    linhas = [dict(zip(campos, l + [''] * (len(campos) - len(l)))) for l in tabela[1:]]
    chaves = {c: _chave(c) for c in campos}

    def unica(nomes):
        achadas = [c for c in campos if chaves[c] in nomes]
        return achadas[0] if len(achadas) == 1 else None
    return campos, linhas, unica(COLUNAS_X), unica(COLUNAS_Y), unica(COLUNAS_WKT), delim


def ler_csv(dados, col_x=None, col_y=None, col_wkt=None):
    """Pontos por duas colunas, ou geometria numa coluna WKT. Devolve {'feicoes', 'campos', 'avisos', 'epsg'}.
    Levanta projecao.SrcAmbiguo quando não dá para saber quais são as colunas."""
    campos, linhas, x_auto, y_auto, wkt_auto, delim = colunas_do_csv(dados)

    def acha(pedida):
        if pedida is None:
            return None
        for c in campos:
            if c == pedida or _chave(c) == _chave(pedida):
                return c
        raise ValueError(f'o CSV não tem a coluna "{pedida}". Colunas: {", ".join(campos)}')
    col_x, col_y, col_wkt = acha(col_x), acha(col_y), acha(col_wkt)
    if not (col_x and col_y) and not col_wkt:
        if x_auto and y_auto:
            col_x, col_y = x_auto, y_auto
        elif wkt_auto:
            col_wkt = wkt_auto
        else:
            exemplo = '; '.join(f'{c} (ex.: {next((l[c] for l in linhas if l[c].strip()), "")})' for c in campos[:12])
            raise projecao.SrcAmbiguo('não deu para saber quais colunas do CSV têm as coordenadas. Colunas: ' + exemplo
                                      + '. Pergunte ao usuário e repita com --x <coluna> --y <coluna> (ou --wkt <coluna>)')
    avisos, feicoes, ruins, codigo = set(), [], [], None
    if col_wkt:
        resto = [c for c in campos if c != col_wkt]
        for i, l in enumerate(linhas, 2):
            try:
                gs, cod = ler_wkt_texto(l[col_wkt], avisos)
                codigo = codigo or cod
            except ValueError:
                gs = []
            if not gs:
                ruins.append(i)
                continue
            for g in gs:
                feicoes.append({'geometry': g, 'properties': {c: l[c] for c in resto}})
    else:
        resto = [c for c in campos if c not in (col_x, col_y)]
        for i, l in enumerate(linhas, 2):
            x, y = numero(l[col_x]), numero(l[col_y])
            if x is None or y is None:
                ruins.append(i)
                continue
            feicoes.append({'geometry': {'type': 'Point', 'coordinates': (x, y)}, 'properties': {c: l[c] for c in resto}})
        avisos.add(f'coordenadas lidas das colunas "{col_x}" (x ou longitude) e "{col_y}" (y ou latitude)')
    if ruins:
        avisos.add(f'{len(ruins)} linha(s) sem coordenada legível ficaram de fora (linhas {", ".join(map(str, ruins[:8]))}{"…" if len(ruins) > 8 else ""})')
    return {'feicoes': feicoes, 'campos': resto, 'avisos': sorted(avisos), 'epsg': codigo}


def gravar_csv(feicoes, campos, em_graus, casas=8, brasileiro=False):
    """Pontos saem com duas colunas de coordenadas; o resto, com a geometria em WKT.
    brasileiro=True usa ponto e vírgula e vírgula decimal (abre direto no Excel em português)."""
    so_pontos = all(f['geometry'] is None or f['geometry']['type'] == 'Point' for f in feicoes)
    nx, ny = ('longitude', 'latitude') if em_graus else ('x', 'y')
    usados = {c.lower() for c in campos}
    nx, ny = (nx if nx not in usados else nx + '_geo'), (ny if ny not in usados else ny + '_geo')

    def celula(v):
        if v is None:
            return ''
        if isinstance(v, bool):
            return 'true' if v else 'false'
        if isinstance(v, float):
            t = repr(v)
            return t.replace('.', ',') if brasileiro else t
        return str(v)
    buf = io.StringIO(newline='')
    escritor = csv.writer(buf, delimiter=';' if brasileiro else ',', lineterminator='\n')
    escritor.writerow(([nx, ny] if so_pontos else ['wkt']) + list(campos))
    for f in feicoes:
        g = f['geometry']
        if g is None:
            continue
        if so_pontos:
            xy = [_n(g['coordinates'][0], casas), _n(g['coordinates'][1], casas)]
            geo_cols = [v.replace('.', ',') for v in xy] if brasileiro else xy
        else:
            geo_cols = [wkt_de(g, casas)]
        escritor.writerow(geo_cols + [celula(f['properties'].get(c)) for c in campos])
    return buf.getvalue()


if __name__ == '__main__':
    gj = {'type': 'FeatureCollection', 'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:EPSG::31982'}}, 'features': [
        {'type': 'Feature', 'properties': {'TALHAO': 'T01', 'ha': 12.5, 'obs': None, 'lista': [1, 2]},
         'geometry': {'type': 'Polygon', 'coordinates': [[[0, 0, 5], [0, 100, 5], [100, 100, 5], [100, 0, 5], [0, 0, 5]]]}},
        {'type': 'Feature', 'properties': None, 'geometry': {'type': 'GeometryCollection', 'geometries': [
            {'type': 'Point', 'coordinates': [1, 2]}, {'type': 'LineString', 'coordinates': [[0, 0], [1, 1]]}]}},
        {'type': 'Feature', 'properties': {'TALHAO': 'vazio'}, 'geometry': None}]}
    c = ler_geojson(json.dumps(gj).encode('utf-8'))
    assert len(c['feicoes']) == 4 and c['epsg'] == 31982 and c['campos'] == ['TALHAO', 'ha', 'obs', 'lista']
    assert c['feicoes'][0]['properties']['lista'] == '[1, 2]' and len(c['avisos']) == 2
    texto = gravar_geojson(c['feicoes'], c['campos'], 'teste', 3, 31982)
    volta = json.loads(texto)
    anel = volta['features'][0]['geometry']['coordinates'][0]
    assert geom.area_assinada(anel) > 0 and volta['features'][0]['properties'] == {'TALHAO': 'T01', 'ha': 12.5, 'obs': None, 'lista': '[1, 2]'}
    assert volta['features'][3]['geometry'] is None and 'EPSG::31982' in volta['crs']['properties']['name']
    assert ler_geojson(b'{"type":"Point","coordinates":[-51.2,-23.1]}')['feicoes'][0]['geometry']['coordinates'] == (-51.2, -23.1)

    for w, tipo in (('POINT (30 10)', 'Point'), ('point z (30 10 5)', 'Point'), ('LINESTRING(30 10,10 30, 40 40)', 'LineString'),
                    ('POLYGON ((35 10, 45 45, 15 40, 10 20, 35 10), (20 30, 35 35, 30 20, 20 30))', 'Polygon'),
                    ('MULTIPOINT ((10 40), (40 30))', 'MultiPoint'), ('MULTIPOINT (10 40, 40 30)', 'MultiPoint'),
                    ('MULTILINESTRING ((10 10, 20 20), (40 40, 30 30, 40 20))', 'MultiLineString'),
                    ('SRID=4674;MULTIPOLYGON (((30 20, 45 40, 10 40, 30 20)), ((15 5, 40 10, 10 20, 5 10, 15 5)))', 'MultiPolygon'),
                    ('MULTIPOLYGON Z (((30 20 1, 45 40 1, 10 40 1, 30 20 1)))', 'MultiPolygon'), ('POLYGONZ ((0 0 1, 1 0 1, 1 1 1, 0 0 1))', 'Polygon')):
        gs, cod = ler_wkt_texto(w)
        assert len(gs) == 1 and gs[0]['type'] == tipo, (w, gs)
        de_novo, _ = ler_wkt_texto(wkt_de(gs[0]))
        assert de_novo[0]['type'] == tipo and geom.n_vertices(de_novo[0]) == geom.n_vertices(gs[0])
    assert ler_wkt_texto('SRID=31982;POINT(1 2)')[1] == 31982
    varias, _ = ler_wkt_texto('POINT (1 2)\nGEOMETRYCOLLECTION (POINT (3 4), LINESTRING (0 0, 1 1));\nPOLYGON EMPTY\nPOINT(5 6)')
    assert [g['type'] if g else None for g in varias] == ['Point', 'Point', 'LineString', None, 'Point']
    assert wkt_de({'type': 'Point', 'coordinates': (-51.2, -23.123456789012)}) == 'POINT (-51.2 -23.12345679)'
    for ruim in ('POLYGON ((0 0, 1 1', 'CIRCULO (0 0)', 'POINT (1)'):
        try:
            ler_wkt_texto(ruim)
            raise AssertionError(ruim)
        except ValueError:
            pass
    unico = gravar_wkt(c['feicoes'][:1] * 2, 3, unico=True)
    assert unico.startswith('MULTIPOLYGON (((') and ler_wkt_texto(unico)[0][0]['type'] == 'MultiPolygon'

    for t, v in (('-23,5', -23.5), ('1.234,56', 1234.56), ('512300.25', 512300.25), ('23°30\'15.5"S', -23.504305555555554), ('S 23 30 15', -23.504166666666666),
                 ('51° 12\' W', -51.2), ('-51:12:36', -51.21), ('7.456.000,5', 7456000.5), ('abc', None), ('', None), ('12', 12.0), ('1e3', 1000.0)):
        r = numero(t)
        assert (r is None and v is None) or (r is not None and abs(r - v) < 1e-9), (t, r, v)
    br = 'Ponto;Latitude;Longitude;Argila (%)\nP01;-23,10;-51,20;45,5\nP02;-23,11;-51,21;38\nP03;;;\nP04;x;y;1\n'.encode('cp1252')
    c = ler_csv(br)
    assert len(c['feicoes']) == 2 and c['feicoes'][0]['geometry']['coordinates'] == (-51.2, -23.1) and c['campos'] == ['Ponto', 'Argila (%)']
    assert c['feicoes'][0]['properties'] == {'Ponto': 'P01', 'Argila (%)': '45,5'} and any('2 linha(s)' in a and 'linhas 4, 5' in a for a in c['avisos'])
    try:
        ler_csv(b'id,a,b\n1,-51.2,-23.1\n')
        raise AssertionError('devia perguntar as colunas')
    except projecao.SrcAmbiguo as e:
        assert '--x' in str(e)
    assert ler_csv(b'id,a,b\n1,-51.2,-23.1\n', 'a', 'b')['feicoes'][0]['geometry']['coordinates'] == (-51.2, -23.1)
    w = ler_csv('nome,WKT\nT01,"POLYGON ((0 0, 10 0, 10 10, 0 0))"\nT02,"SRID=31982;POINT (1 2)"\n'.encode('utf-8'))
    assert [f['geometry']['type'] for f in w['feicoes']] == ['Polygon', 'Point'] and w['feicoes'][0]['properties'] == {'nome': 'T01'}
    saida = gravar_csv(c['feicoes'], c['campos'], True, 6, brasileiro=True)
    assert saida.splitlines()[0] == 'longitude;latitude;Ponto;Argila (%)' and saida.splitlines()[1] == '-51,2;-23,1;P01;45,5'
    volta = ler_csv(saida.encode('utf-8'))
    assert volta['feicoes'][1]['geometry']['coordinates'] == (-51.21, -23.11)
    misto = gravar_csv(w['feicoes'], w['campos'], False, 3)
    assert misto.splitlines()[0] == 'wkt,nome' and ler_csv(misto.encode('utf-8'))['feicoes'][0]['geometry']['type'] == 'Polygon'
    print('texto OK: GeoJSON (crs, coleção de geometrias, sentido dos anéis), WKT (10 formas, erros), CSV (vírgula decimal, graus-minutos-segundos, coluna WKT)')
