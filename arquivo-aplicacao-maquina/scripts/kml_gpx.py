"""KML, KMZ e GPX: leitura e gravação. Os três são sempre em graus (WGS 84).

KML: lê os marcadores (Placemark) de qualquer nível de pasta, com ponto, linha,
polígono (com furos), MultiGeometry e trilha (gx:Track); guarda o nome, a
descrição, os dados estendidos e o caminho das pastas (campo "pasta").
GPX: lê pontos de passagem (wpt), rotas (rte) e trilhas (trk). O GPX não tem
polígono: na gravação o polígono vira uma trilha fechada, e isso é avisado.
A altitude é descartada nos dois.
"""

import io
import re
import zipfile
from xml.sax.saxutils import escape

import geom

try:
    from defusedxml import ElementTree as ET
except ImportError:  # sem a biblioteca, o filtro de DOCTYPE abaixo faz a proteção
    from xml.etree import ElementTree as ET

LIMITE_ZIP = 300 * 1024 * 1024  # tamanho máximo, descompactado, de um arquivo dentro do zip
CAMPOS_DE_NOME = ('name', 'nome', 'talhao', 'talhão', 'nome_talhao', 'nm_talhao', 'gleba', 'fazenda', 'id', 'cod', 'codigo', 'código')


def raiz_xml(dados):
    """Abre um XML recusando declaração de entidade (arquivo malicioso se expande na memória)."""
    if isinstance(dados, bytes):
        cabeca = dados[:4096].decode('utf-8', 'replace')
    else:
        cabeca, dados = dados[:4096], dados.encode('utf-8')
    if re.search(r'<!\s*(DOCTYPE|ENTITY)', cabeca, re.I):
        raise ValueError('o arquivo XML traz declaração DOCTYPE/ENTITY e não foi aberto por segurança')
    try:
        return ET.fromstring(dados)
    except Exception as e:
        raise ValueError(f'o arquivo não é um XML válido ({e})')


def ler_do_zip(dados, extensoes):
    """Lê do zip (em memória, sem extrair para o disco) os arquivos com as extensões pedidas.
    Devolve {nome: bytes}. Nome com '..' ou caminho absoluto é ignorado."""
    try:
        z = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile:
        raise ValueError('o arquivo não é um zip válido')
    achados, total = {}, 0
    for info in z.infolist():
        nome = info.filename.replace('\\', '/')
        if info.is_dir() or nome.startswith('/') or '..' in nome.split('/') or nome.startswith('__MACOSX/'):
            continue
        if nome.rsplit('.', 1)[-1].lower() in extensoes:
            total += info.file_size
            if info.file_size > LIMITE_ZIP or total > 2 * LIMITE_ZIP:
                raise ValueError(f'{nome} tem {info.file_size // 1048576} MB descompactado: o zip é grande demais para abrir aqui')
            achados[nome] = z.read(info)
    return achados


def _sem_ns(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _coords(texto, avisos):
    pares = []
    for trecho in re.sub(r'\s*,\s*', ',', (texto or '').strip()).split():
        p = trecho.split(',')
        if len(p) >= 2:
            try:
                pares.append((float(p[0]), float(p[1])))
            except ValueError:
                continue
            if len(p) >= 3 and p[2] not in ('', '0', '0.0'):
                avisos.add('o arquivo tem altitude: foi descartada')
    return pares


# ---------------------------------------------------------------- KML

def _geometrias_kml(el, avisos):
    """Geometrias simples dentro de um elemento (desce nas MultiGeometry)."""
    saida = []
    for filho in el:
        t = _sem_ns(filho.tag)
        if t == 'MultiGeometry':
            saida += _geometrias_kml(filho, avisos)
        elif t == 'Point':
            c = _coords(next((s.text for s in filho.iter() if _sem_ns(s.tag) == 'coordinates'), ''), avisos)
            if c:
                saida.append({'type': 'Point', 'coordinates': c[0]})
        elif t in ('LineString', 'LinearRing'):
            c = _coords(next((s.text for s in filho.iter() if _sem_ns(s.tag) == 'coordinates'), ''), avisos)
            if len(c) >= 2:
                saida.append({'type': 'LineString', 'coordinates': c})
        elif t == 'Polygon':
            externo, furos = None, []
            for b in filho:
                tb = _sem_ns(b.tag)
                if tb in ('outerBoundaryIs', 'innerBoundaryIs'):
                    c = _coords(next((s.text for s in b.iter() if _sem_ns(s.tag) == 'coordinates'), ''), avisos)
                    if len(c) >= 3 and tb == 'innerBoundaryIs':
                        furos.append(c)
                    elif len(c) >= 3 and externo is None:  # um polígono do KML tem um anel externo só
                        externo = c
            if externo:
                saida.append({'type': 'Polygon', 'coordinates': [externo] + furos})
        elif t == 'Track':
            c = []
            for s in filho:
                if _sem_ns(s.tag) == 'coord':
                    p = (s.text or '').split()
                    if len(p) >= 2:
                        c.append((float(p[0]), float(p[1])))
            if len(c) >= 2:
                saida.append({'type': 'LineString', 'coordinates': c})
        elif t == 'MultiTrack':
            saida += _geometrias_kml(filho, avisos)
    return saida


def juntar(geometrias):
    """Várias geometrias simples de um marcador viram uma multi, ou uma lista quando os tipos se misturam."""
    if not geometrias:
        return [None]
    familias = {geom.familia(g) for g in geometrias}
    if len(geometrias) == 1:
        return geometrias
    if len(familias) > 1:
        return geometrias
    fam = familias.pop()
    if fam == 'ponto':
        return [{'type': 'MultiPoint', 'coordinates': [g['coordinates'] for g in geometrias]}]
    if fam == 'linha':
        return [{'type': 'MultiLineString', 'coordinates': [g['coordinates'] for g in geometrias]}]
    return [{'type': 'MultiPolygon', 'coordinates': [g['coordinates'] for g in geometrias]}]


def ler_kml(dados):
    """Devolve {'feicoes', 'campos', 'avisos'} de um KML (bytes ou texto)."""
    raiz = raiz_xml(dados)
    avisos, feicoes, campos = set(), [], []
    tem_pasta = [False]

    def nota(chave):
        if chave not in campos:
            campos.append(chave)

    def anda(el, pasta):
        for filho in el:
            t = _sem_ns(filho.tag)
            if t == 'kml':
                anda(filho, pasta)
            elif t in ('Document', 'Folder'):
                nome = next(((s.text or '').strip() for s in filho if _sem_ns(s.tag) == 'name'), '')
                if t == 'Folder' and nome:
                    tem_pasta[0] = True
                anda(filho, pasta + [nome] if t == 'Folder' and nome else pasta)
            elif t == 'Placemark':
                props = {}
                for s in filho:
                    ts = _sem_ns(s.tag)
                    if ts == 'name':
                        props['name'] = (s.text or '').strip()
                    elif ts == 'description' and ''.join(s.itertext()).strip():
                        props['description'] = ' '.join(''.join(s.itertext()).split())
                    elif ts == 'ExtendedData':
                        for d in s.iter():
                            td = _sem_ns(d.tag)
                            if td == 'Data' and d.get('name'):
                                props[d.get('name')] = next(((v.text or '').strip() for v in d if _sem_ns(v.tag) == 'value'), '')
                            elif td == 'SimpleData' and d.get('name'):
                                props[d.get('name')] = (d.text or '').strip()
                if (filho.get('id') or '').strip() and not any(k.lower() == 'id' for k in props):
                    props['id'] = filho.get('id').strip()  # o identificador do marcador (o QGIS grava o campo "id" assim)
                if pasta:
                    props['pasta'] = '/'.join(pasta)
                gs = juntar(_geometrias_kml(filho, avisos))
                if len(gs) > 1:
                    avisos.add('há marcador com tipos de geometria misturados: cada parte virou uma feição, com os mesmos atributos')
                for g in gs:
                    feicoes.append({'geometry': g, 'properties': dict(props)})
                for k in props:
                    nota(k)
    anda([raiz], [])
    return {'feicoes': feicoes, 'campos': campos, 'avisos': sorted(avisos)}


def ler_kmz(dados):
    kmls = ler_do_zip(dados, {'kml'})
    if not kmls:
        raise ValueError('o KMZ não tem nenhum arquivo .kml dentro')
    # o doc.kml pode só apontar para os outros arquivos do pacote: lê todos, ele primeiro
    camada = {'feicoes': [], 'campos': [], 'avisos': []}
    com_dado = 0
    for nome in sorted(kmls, key=lambda n: (n != 'doc.kml', n)):
        parte = ler_kml(kmls[nome])
        com_dado += 1 if parte['feicoes'] else 0
        camada['feicoes'] += parte['feicoes']
        camada['campos'] += [c for c in parte['campos'] if c not in camada['campos']]
        camada['avisos'] += [a for a in parte['avisos'] if a not in camada['avisos']]
    if com_dado > 1:
        camada['avisos'].append(f'o KMZ tem {com_dado} arquivos .kml com marcadores: foram lidos todos, juntos')
    return camada


def nome_da_feicao(props, campo, indice):
    if campo:
        for k, v in props.items():
            if k.lower() == campo.lower() and str(v).strip():
                return str(v).strip()
    baixas = {k.lower(): v for k, v in props.items()}
    for k in CAMPOS_DE_NOME:
        if baixas.get(k) not in (None, '') and str(baixas[k]).strip():
            return str(baixas[k]).strip()
    for v in props.values():  # sem campo com cara de nome: o primeiro texto curto serve de rótulo
        if isinstance(v, str) and 0 < len(v.strip()) <= 60:
            return v.strip()
    return f'feição {indice}'


def _txt(v):
    return '' if v is None else ('sim' if v is True else 'não' if v is False else str(v))


def _coords_kml(seq, casas):
    return ' '.join(f'{p[0]:.{casas}f},{p[1]:.{casas}f}' for p in seq)


def _geometria_kml(g, casas):
    t, c = g['type'], g['coordinates']
    if t == 'Point':
        return f'<Point><coordinates>{_coords_kml([c], casas)}</coordinates></Point>'
    if t == 'LineString':
        return f'<LineString><tessellate>1</tessellate><coordinates>{_coords_kml(c, casas)}</coordinates></LineString>'
    if t == 'Polygon':
        aneis = [geom.fechar(a) for a in c]
        s = f'<outerBoundaryIs><LinearRing><coordinates>{_coords_kml(aneis[0], casas)}</coordinates></LinearRing></outerBoundaryIs>'
        s += ''.join(f'<innerBoundaryIs><LinearRing><coordinates>{_coords_kml(a, casas)}</coordinates></LinearRing></innerBoundaryIs>' for a in aneis[1:])
        return f'<Polygon><tessellate>1</tessellate>{s}</Polygon>'
    simples = {'MultiPoint': 'Point', 'MultiLineString': 'LineString', 'MultiPolygon': 'Polygon'}[t]
    return '<MultiGeometry>' + ''.join(_geometria_kml({'type': simples, 'coordinates': p}, casas) for p in c) + '</MultiGeometry>'


def gravar_kml(feicoes, campos, titulo, campo_nome=None, casas=8):
    """Texto do KML. Cada feição vira um marcador com o nome e todos os atributos em dados estendidos."""
    marcas = []
    # um campo chamado "id" vai também como identificador do marcador: é de lá que o QGIS lê o campo "id" de um KML
    campo_id = next((k for k in campos if k.lower() == 'id'), None)
    ids = [_txt(f['properties'].get(campo_id)) for f in feicoes if f['geometry']] if campo_id else []
    usar_id = bool(ids) and len(set(ids)) == len(ids) and all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*', v) for v in ids)
    for i, f in enumerate(feicoes, 1):
        if not f['geometry']:
            continue
        props = f['properties']
        marca_id = f' id="{_txt(props.get(campo_id))}"' if usar_id else ''
        dados = ''.join(f'<Data name="{escape(str(k), {chr(34): "&quot;"})}"><value>{escape(_txt(props.get(k)))}</value></Data>'
                        for k in campos if k not in ('name', 'description'))
        desc = f'<description>{escape(_txt(props["description"]))}</description>' if props.get('description') else ''
        marcas.append(f'<Placemark{marca_id}><name>{escape(nome_da_feicao(props, campo_nome, i))}</name>{desc}<styleUrl>#padrao</styleUrl>'
                      f'<ExtendedData>{dados}</ExtendedData>{_geometria_kml(f["geometry"], casas)}</Placemark>')
    estilo = ('<Style id="padrao"><LineStyle><color>ff37c952</color><width>2</width></LineStyle>'
              '<PolyStyle><color>4037c952</color></PolyStyle></Style>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
            f'<name>{escape(titulo)}</name>{estilo}\n' + '\n'.join(marcas) + '\n</Document></kml>\n')


def gravar_kmz(texto_kml):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('doc.kml', texto_kml)
    return buf.getvalue()


# ---------------------------------------------------------------- GPX

def _ponto_gpx(el):
    try:
        return float(el.get('lon')), float(el.get('lat'))
    except (TypeError, ValueError):
        return None


def ler_gpx(dados):
    """Devolve {'feicoes', 'campos', 'avisos'}: wpt = pontos; rte e trk = linhas (campo "tipo")."""
    raiz = raiz_xml(dados)
    avisos, feicoes, campos = set(), [], []

    def props_de(el, extras=()):
        props = {}
        for s in el:
            t = _sem_ns(s.tag)
            if t in ('name', 'desc', 'cmt', 'sym', 'type', 'time') and (s.text or '').strip():
                props[t] = (s.text or '').strip()
            elif t == 'ele' and (s.text or '').strip():
                avisos.add('o arquivo tem altitude: foi descartada')
        props.update(extras)
        for k in props:
            if k not in campos:
                campos.append(k)
        return props

    for el in raiz:
        t = _sem_ns(el.tag)
        if t == 'wpt':
            p = _ponto_gpx(el)
            if p:
                feicoes.append({'geometry': {'type': 'Point', 'coordinates': p}, 'properties': props_de(el)})
        elif t == 'rte':
            pts = [p for p in (_ponto_gpx(s) for s in el if _sem_ns(s.tag) == 'rtept') if p]
            if len(pts) >= 2:
                feicoes.append({'geometry': {'type': 'LineString', 'coordinates': pts}, 'properties': props_de(el, {'tipo': 'rota'})})
        elif t == 'trk':
            segs = []
            for s in el:
                if _sem_ns(s.tag) == 'trkseg':
                    pts = [p for p in (_ponto_gpx(q) for q in s if _sem_ns(q.tag) == 'trkpt') if p]
                    if len(pts) >= 2:
                        segs.append(pts)
            if segs:
                g = {'type': 'LineString', 'coordinates': segs[0]} if len(segs) == 1 else {'type': 'MultiLineString', 'coordinates': segs}
                feicoes.append({'geometry': g, 'properties': props_de(el, {'tipo': 'trilha'})})
    return {'feicoes': feicoes, 'campos': campos, 'avisos': sorted(avisos)}


def gravar_gpx(feicoes, campos, titulo, campo_nome=None, casas=8, rota=False):
    """Texto do GPX 1.1. Pontos viram wpt; linhas viram trilha (ou rota); polígonos, trilha fechada.
    Devolve (texto, avisos)."""
    avisos, partes = set(), {'wpt': [], 'rte': [], 'trk': []}

    def rotulo(props, i):
        nome = nome_da_feicao(props, campo_nome, i)
        resto = '; '.join(f'{k}={_txt(props.get(k))}' for k in campos
                          if props.get(k) not in (None, '') and _txt(props.get(k)) != nome and k not in ('tipo',))
        return f'<name>{escape(nome)}</name>' + (f'<desc>{escape(resto)}</desc>' if resto else '')

    for i, f in enumerate(feicoes, 1):
        g = f['geometry']
        if not g:
            continue
        fam = geom.familia(g)
        if fam == 'ponto':
            for p in ([g['coordinates']] if g['type'] == 'Point' else g['coordinates']):
                partes['wpt'].append(f'<wpt lat="{p[1]:.{casas}f}" lon="{p[0]:.{casas}f}">{rotulo(f["properties"], i)}</wpt>')
            continue
        if fam == 'polígono':
            avisos.add('o GPX não tem polígono: cada anel virou uma trilha fechada (os furos também)')
            seqs = [geom.fechar(a) for poli in geom.poligonos_de(g) for a in poli]
        else:
            seqs = [g['coordinates']] if g['type'] == 'LineString' else list(g['coordinates'])
        if rota and fam == 'linha':
            for s in seqs:
                pts = ''.join(f'<rtept lat="{p[1]:.{casas}f}" lon="{p[0]:.{casas}f}"/>' for p in s)
                partes['rte'].append(f'<rte>{rotulo(f["properties"], i)}{pts}</rte>')
        else:
            segs = ''.join('<trkseg>' + ''.join(f'<trkpt lat="{p[1]:.{casas}f}" lon="{p[0]:.{casas}f}"/>' for p in s) + '</trkseg>' for s in seqs)
            partes['trk'].append(f'<trk>{rotulo(f["properties"], i)}{segs}</trk>')
    texto = ('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="conversor-geo" xmlns="http://www.topografix.com/GPX/1/1">'
             f'<metadata><name>{escape(titulo)}</name></metadata>\n' + '\n'.join(partes['wpt'] + partes['rte'] + partes['trk']) + '\n</gpx>\n')
    return texto, sorted(avisos)


if __name__ == '__main__':
    kml = '''<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2"><Document><name>Fazenda</name>
    <Folder><name>Talhões</name><Folder><name>Sede</name>
      <Placemark><name>T01 &amp; cia</name><description>área de <b>soja</b></description>
        <ExtendedData><Data name="cultura"><value>Soja</value></Data><SchemaData><SimpleData name="area_ha">12.5</SimpleData></SchemaData></ExtendedData>
        <Polygon><outerBoundaryIs><LinearRing><coordinates>-51.20,-23.10,0 -51.19,-23.10,0 -51.19,-23.09,0 -51.20,-23.09,0 -51.20,-23.10,0</coordinates></LinearRing></outerBoundaryIs>
        <innerBoundaryIs><LinearRing><coordinates>-51.197, -23.097, 0 -51.193, -23.097, 0 -51.193, -23.093, 0 -51.197, -23.097, 0</coordinates></LinearRing></innerBoundaryIs></Polygon></Placemark>
    </Folder></Folder>
    <Placemark><name>dois</name><MultiGeometry><Polygon><outerBoundaryIs><LinearRing><coordinates>-51.1,-23.1 -51.09,-23.1 -51.09,-23.09 -51.1,-23.1</coordinates></LinearRing></outerBoundaryIs></Polygon>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>-51.0,-23.1 -50.99,-23.1 -50.99,-23.09 -51.0,-23.1</coordinates></LinearRing></outerBoundaryIs></Polygon></MultiGeometry></Placemark>
    <Placemark><name>misto</name><MultiGeometry><Point><coordinates>-51.15,-23.05,812</coordinates></Point><LineString><coordinates>-51.15,-23.05 -51.14,-23.04</coordinates></LineString></MultiGeometry></Placemark>
    <Placemark><name>trilha</name><gx:Track><gx:coord>-51.3 -23.2 500</gx:coord><gx:coord>-51.31 -23.21 501</gx:coord></gx:Track></Placemark>
    <Placemark><name>vazio</name></Placemark></Document></kml>'''
    c = ler_kml(kml.encode('utf-8'))
    fs = c['feicoes']
    assert len(fs) == 6 and c['campos'] == ['name', 'description', 'cultura', 'area_ha', 'pasta'], (len(fs), c['campos'])
    assert fs[0]['properties'] == {'name': 'T01 & cia', 'description': 'área de soja', 'cultura': 'Soja', 'area_ha': '12.5', 'pasta': 'Talhões/Sede'}
    assert fs[0]['geometry']['type'] == 'Polygon' and len(fs[0]['geometry']['coordinates']) == 2 and len(fs[0]['geometry']['coordinates'][1]) == 4
    assert fs[1]['geometry']['type'] == 'MultiPolygon' and [f['geometry']['type'] for f in fs[2:4]] == ['Point', 'LineString']
    assert fs[4]['geometry']['type'] == 'LineString' and fs[5]['geometry'] is None
    assert any('altitude' in a for a in c['avisos']) and any('misturados' in a for a in c['avisos'])
    texto = gravar_kml(fs, c['campos'], 'Teste <1>', None)
    de_novo = ler_kml(texto)
    assert len(de_novo['feicoes']) == 5 and de_novo['feicoes'][0]['properties']['cultura'] == 'Soja'
    assert de_novo['feicoes'][0]['geometry']['coordinates'][0][0] == (-51.2, -23.1) and de_novo['feicoes'][0]['properties']['name'] == 'T01 & cia'
    assert ler_kmz(gravar_kmz(texto))['feicoes'][1]['geometry']['type'] == 'MultiPolygon'
    com_id = [{'geometry': {'type': 'Point', 'coordinates': (-51.2, -23.1)}, 'properties': {'ID': 'P01', 'n': 1}},
              {'geometry': {'type': 'Point', 'coordinates': (-51.3, -23.2)}, 'properties': {'ID': 'P02', 'n': 2}}]
    t_id = gravar_kml(com_id, ['ID', 'n'], 'ids')
    assert '<Placemark id="P01">' in t_id and ler_kml(t_id)['feicoes'][1]['properties'] == {'name': 'P02', 'ID': 'P02', 'n': '2'}
    com_id[1]['properties']['ID'] = '7'  # não serve de identificador de XML: fica só nos dados
    assert '<Placemark id=' not in gravar_kml(com_id, ['ID', 'n'], 'ids')
    assert ler_kml('<kml><Placemark id="abc"><Point><coordinates>1,2</coordinates></Point></Placemark></kml>')['feicoes'][0]['properties'] == {'id': 'abc'}
    for ruim in (b'<!DOCTYPE x [<!ENTITY a "b">]><kml/>', b'<kml><Document>'):
        try:
            ler_kml(ruim)
            raise AssertionError('devia recusar')
        except ValueError:
            pass
    # zip com caminho malicioso: é ignorado
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('../fora.kml', texto)
        z.writestr('pasta/dentro.kml', texto)
    assert list(ler_do_zip(buf.getvalue(), {'kml'})) == ['pasta/dentro.kml']

    gpx = '''<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
    <wpt lat="-23.10" lon="-51.20"><ele>640</ele><name>P01</name><sym>Flag</sym></wpt>
    <rte><name>rota 1</name><rtept lat="-23.1" lon="-51.2"/><rtept lat="-23.2" lon="-51.3"/></rte>
    <trk><name>volta</name><trkseg><trkpt lat="-23.1" lon="-51.2"/><trkpt lat="-23.11" lon="-51.21"/></trkseg>
      <trkseg><trkpt lat="-23.3" lon="-51.4"/><trkpt lat="-23.31" lon="-51.41"/></trkseg></trk></gpx>'''
    g = ler_gpx(gpx.encode('utf-8'))
    assert [f['geometry']['type'] for f in g['feicoes']] == ['Point', 'LineString', 'MultiLineString']
    assert g['feicoes'][0]['geometry']['coordinates'] == (-51.2, -23.1) and g['feicoes'][0]['properties'] == {'name': 'P01', 'sym': 'Flag'}
    assert g['feicoes'][1]['properties']['tipo'] == 'rota' and g['feicoes'][2]['properties']['tipo'] == 'trilha'
    texto, avisos = gravar_gpx(g['feicoes'] + fs[:1], g['campos'] + ['cultura'], 'teste')
    volta = ler_gpx(texto)
    assert [f['geometry']['type'] for f in volta['feicoes']] == ['Point', 'LineString', 'MultiLineString', 'MultiLineString'] and avisos
    assert volta['feicoes'][3]['geometry']['coordinates'][0][0] == volta['feicoes'][3]['geometry']['coordinates'][0][-1]
    rota, _ = gravar_gpx(g['feicoes'][1:2], [], 'r', rota=True)
    assert ler_gpx(rota)['feicoes'][0]['properties']['tipo'] == 'rota'
    print('kml_gpx OK: pastas, MultiGeometry, furos, dados estendidos, trilha, KMZ, GPX de ida e volta, XML e zip maliciosos recusados')
