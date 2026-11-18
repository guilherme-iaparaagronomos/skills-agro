"""Áreas (talhões ou zonas) com nome: leitura, projeção e geometria.

Lê polígonos de GeoJSON, KML, shapefile ou WKT guardando o NOME de cada um (o
talhão ou a zona), leva tudo para UTM/SIRGAS 2000 e responde o que o desenho
amostral pergunta: o ponto está dentro? a que distância da borda? qual a área?

Furos e partes múltiplas são resolvidos por paridade, como no resto da casa: um
ponto está dentro se cai num número ímpar de anéis.
"""

import json
import math
import re
import unicodedata
from pathlib import Path

import numpy as np
from matplotlib.path import Path as Caminho

import geometria
from geometria import _A, _E2, _EP2, _K0

CAMPOS_DE_NOME = ('talhao', 'talhão', 'plot_name', 'field_name', 'nome_talhao', 'talhao_nome', 'nm_talhao',
                  'nome', 'name', 'zona', 'zone', 'classe', 'class', 'gleba', 'area', 'área', 'id', 'cod',
                  'codigo', 'código')
# pedaços que indicam "é o nome do talhão" quando o campo tem outro nome (plot_name, NM_TALH…)
PISTAS = ('talh', 'plot', 'field', 'gleba', 'zona', 'zone')


def nome_limpo(texto):
    """'Talhão 01 / A' → 'TALHAO01A': só letras e números, para virar parte do ID da amostra."""
    s = unicodedata.normalize('NFKD', str(texto))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^A-Za-z0-9]+', '', s).upper()


def _nome_de(props, campo, indice):
    if campo:
        for chave, valor in props.items():
            if chave.lower() == campo.lower() and str(valor).strip():
                return str(valor).strip()
    else:
        baixas = {k.lower(): v for k, v in props.items()}
        for chave in CAMPOS_DE_NOME[:7]:
            if str(baixas.get(chave, '')).strip():
                return str(baixas[chave]).strip()
        # campo com cara de nome de talhão (prefere o que tem "nome"/"name" ao que é só código)
        parecidos = sorted((k for k in baixas if any(p in k for p in PISTAS) and str(baixas[k]).strip()),
                           key=lambda k: (not ('nom' in k or 'name' in k or k.startswith('nm')), k))
        if parecidos:
            return str(baixas[parecidos[0]]).strip()
        for chave in CAMPOS_DE_NOME[7:]:
            if str(baixas.get(chave, '')).strip():
                return str(baixas[chave]).strip()
    return f'A{indice:02d}'


def ler_areas(caminho, campo=None):
    """Devolve (areas, crs, zona). areas = [{'nome', 'aneis': [[(x, y), …], …]}],
    um item por feição; crs = 'geo' | 'utm'; zona = (n, sul?) do .prj ou None."""
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    zona, brutas = None, []  # brutas: [(props, aneis)]
    if ext == '.shp':
        from shapefile_min import ler_shp
        tipo, geoms, atributos, zona = ler_shp(str(caminho))
        if tipo != 'poligono':
            raise ValueError('o shapefile precisa ser de polígonos')
        brutas = [(a, [list(anel) for anel in g]) for g, a in zip(geoms, atributos) if g]
    elif ext in ('.geojson', '.json'):
        gj = json.loads(caminho.read_text(encoding='utf-8-sig'))
        feicoes = gj.get('features', [gj] if gj.get('type') != 'FeatureCollection' else [])
        for f in feicoes:
            geom = f.get('geometry', f)
            if geom and geom.get('type') in ('Polygon', 'MultiPolygon'):
                brutas.append((f.get('properties') or {}, geometria._aneis_geojson(geom)))
    elif ext == '.kml':
        raiz = geometria.ET.fromstring(caminho.read_text(encoding='utf-8-sig'))
        for marca in raiz.iter():
            if geometria._sem_ns(marca.tag) != 'Placemark':
                continue
            nome = next((el.text for el in marca if geometria._sem_ns(el.tag) == 'name' and el.text), None)
            aneis = [geometria._coords_kml(sub.text or '') for el in marca.iter()
                     if geometria._sem_ns(el.tag) == 'Polygon'
                     for sub in el.iter() if geometria._sem_ns(sub.tag) == 'coordinates']
            if aneis:
                brutas.append(({'nome': nome} if nome else {}, aneis))
    else:
        aneis, _, _ = geometria.ler_perimetro(caminho)
        brutas = [({}, aneis)]

    areas = []
    for props, aneis in brutas:
        aneis = [[(float(p[0]), float(p[1])) for p in a] for a in aneis if len(a) >= 4]
        if aneis:
            areas.append({'nome': _nome_de(props, campo, len(areas) + 1), 'aneis': aneis})
    if not areas:
        raise ValueError(f'nenhum polígono encontrado em {caminho.name}')
    xs = [p[0] for a in areas for anel in a['aneis'] for p in anel]
    ys = [p[1] for a in areas for anel in a['aneis'] for p in anel]
    return areas, ('geo' if geometria._geografica(xs, ys) else 'utm'), zona


def campos_de(caminho, exemplos=3):
    """Atributos do arquivo com alguns valores, para o usuário dizer qual é o nome do talhão.
    Devolve [(campo, [valores…])]; vazio para KML e WKT (o KML usa o nome do marcador)."""
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    if ext == '.shp':
        from shapefile_min import ler_shp
        registros = ler_shp(str(caminho))[2]
    elif ext in ('.geojson', '.json'):
        gj = json.loads(caminho.read_text(encoding='utf-8-sig'))
        registros = [f.get('properties') or {} for f in gj.get('features', [])]
    else:
        return []
    campos = {}
    for r in registros:
        for chave, valor in r.items():
            lista = campos.setdefault(chave, [])
            if str(valor).strip() and str(valor) not in lista and len(lista) < exemplos:
                lista.append(str(valor))
    return list(campos.items())


def para_utm(areas, crs, zona=None):
    """Projeta as áreas para UTM. Devolve (areas, zona, sul)."""
    if crs == 'utm':
        if not zona:
            raise ValueError('coordenadas em metros sem .prj: informe a zona UTM (ex.: --zona 22S)')
        return areas, zona[0], zona[1]
    if not zona:
        lons = [p[0] for a in areas for anel in a['aneis'] for p in anel]
        lats = [p[1] for a in areas for anel in a['aneis'] for p in anel]
        zona = geometria.zona_de(sum(lons) / len(lons), sum(lats) / len(lats))
    z, sul = zona
    saida = []
    for a in areas:
        aneis = []
        for anel in a['aneis']:
            xs, ys = geometria.utm_direta([p[0] for p in anel], [p[1] for p in anel], z, sul)
            aneis.append(list(zip(xs.tolist(), ys.tolist())))
        saida.append({**a, 'aneis': aneis})
    return saida, z, sul


def utm_inversa(xs, ys, zona, sul):
    """UTM → longitude e latitude em graus (série de Snyder), vetorizada."""
    x = np.asarray(xs, dtype=float) - 500000
    y = np.asarray(ys, dtype=float) - (10000000 if sul else 0)
    m = y / _K0
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E2**2 / 64 - 5 * _E2**3 / 256))
    e1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
    fi = (mu + (3 * e1 / 2 - 27 * e1**3 / 32) * np.sin(2 * mu)
          + (21 * e1**2 / 16 - 55 * e1**4 / 32) * np.sin(4 * mu)
          + (151 * e1**3 / 96) * np.sin(6 * mu) + (1097 * e1**4 / 512) * np.sin(8 * mu))
    sen, cos, tan = np.sin(fi), np.cos(fi), np.tan(fi)
    c1 = _EP2 * cos**2
    t1 = tan**2
    n1 = _A / np.sqrt(1 - _E2 * sen**2)
    r1 = _A * (1 - _E2) / (1 - _E2 * sen**2) ** 1.5
    d = x / (n1 * _K0)
    lat = fi - (n1 * tan / r1) * (d**2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * _EP2) * d**4 / 24
                                  + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * _EP2 - 3 * c1**2) * d**6 / 720)
    lon = (d - (1 + 2 * t1 + c1) * d**3 / 6
           + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * _EP2 + 24 * t1**2) * d**5 / 120) / cos
    return np.degrees(lon) + (zona * 6 - 183), np.degrees(lat)


def dentro(aneis, pontos):
    """Quais pontos [n, 2] caem dentro da área (paridade entre os anéis)."""
    pontos = np.asarray(pontos, dtype=float).reshape(-1, 2)
    marca = np.zeros(len(pontos), dtype=bool)
    for anel in aneis:
        marca ^= Caminho(np.asarray(anel)).contains_points(pontos)
    return marca


def distancia_da_borda(aneis, pontos):
    """Distância (m) de cada ponto ao segmento de contorno mais próximo."""
    pontos = np.asarray(pontos, dtype=float).reshape(-1, 2)
    menor = np.full(len(pontos), np.inf)
    for anel in aneis:
        a = np.asarray(anel, dtype=float)
        b = np.roll(a, -1, axis=0)
        ab = b - a
        comprimento2 = np.maximum((ab**2).sum(axis=1), 1e-12)
        for ini in range(0, len(pontos), 2000):  # em blocos: n pontos × m segmentos
            p = pontos[ini:ini + 2000, None, :]
            t = np.clip(((p - a) * ab).sum(axis=2) / comprimento2, 0, 1)
            proximo = a + t[:, :, None] * ab
            d = np.sqrt(((p - proximo) ** 2).sum(axis=2)).min(axis=1)
            menor[ini:ini + 2000] = np.minimum(menor[ini:ini + 2000], d)
    return menor


def area_ha(aneis):
    """Área em hectares; anel dentro de outro conta como furo (ou ilha dentro do furo)."""
    total = 0.0
    for i, anel in enumerate(aneis):
        a = np.asarray(anel, dtype=float)
        x, y = a[:, 0], a[:, 1]
        area = abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2
        nivel = sum(1 for j, outro in enumerate(aneis)
                    if j != i and Caminho(np.asarray(outro)).contains_point(anel[0]))
        total += area if nivel % 2 == 0 else -area
    return total / 10000


def caixa(aneis):
    xs = [p[0] for anel in aneis for p in anel]
    ys = [p[1] for anel in aneis for p in anel]
    return min(xs), min(ys), max(xs), max(ys)


if __name__ == '__main__':
    import os
    import tempfile

    # ida e volta da projeção: erro abaixo de 1 cm
    lons, lats = np.array([-47.05, -49.62, -55.3]), np.array([-22.85, -22.68, -12.1])
    for lon, lat in zip(lons, lats):
        z, sul = geometria.zona_de(lon, lat)
        x, y = geometria.utm_direta([lon], [lat], z, sul)
        lon2, lat2 = utm_inversa(x, y, z, sul)
        assert abs(lon2[0] - lon) < 1e-7 and abs(lat2[0] - lat) < 1e-7, (lon, lat, lon2, lat2)

    quadrado = [(0, 0), (1000, 0), (1000, 1000), (0, 1000), (0, 0)]
    furo = [(400, 400), (600, 400), (600, 600), (400, 600), (400, 400)]
    assert abs(area_ha([quadrado]) - 100) < 1e-6 and abs(area_ha([quadrado, furo]) - 96) < 1e-6
    assert dentro([quadrado, furo], [(100, 100), (500, 500), (2000, 0)]).tolist() == [True, False, False]
    d = distancia_da_borda([quadrado, furo], [(100, 500), (500, 380), (990, 990)])
    assert np.allclose(d, [100, 20, 10]), d
    assert nome_limpo('Talhão 01 / A') == 'TALHAO01A'

    with tempfile.TemporaryDirectory() as pasta:
        arq = os.path.join(pasta, 't.geojson')
        anel = [[-47.05, -22.85], [-47.04, -22.85], [-47.04, -22.84], [-47.05, -22.84], [-47.05, -22.85]]
        open(arq, 'w', encoding='utf-8').write(json.dumps({'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'properties': {'TALHAO': 'T01'}, 'geometry': {'type': 'Polygon', 'coordinates': [anel]}},
            {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'Polygon', 'coordinates': [anel]}}]}))
        areas, crs, zona = ler_areas(arq)
        assert [a['nome'] for a in areas] == ['T01', 'A02'] and crs == 'geo'
        assert campos_de(arq) == [('TALHAO', ['T01'])]
        # nome do talhão em campo de outro nome: vale o que tem "name", não o código nem o da fazenda
        assert _nome_de({'plot_id': '101', 'plot_name': 'GLEBA 01', 'farm_name': 'Fazenda Exemplo'}, None, 1) == 'GLEBA 01'
        assert _nome_de({'farm_name': 'Fazenda Exemplo', 'area_ha': '20'}, None, 3) == 'A03'
        assert _nome_de({'NM_TALH': 'Sede 2', 'nome': 'outra coisa'}, None, 1) == 'Sede 2'
        assert _nome_de({'cultura': 'Soja', 'apelido': 'Baixada'}, 'apelido', 1) == 'Baixada'
        proj, z, sul = para_utm(areas, crs, zona)
        assert (z, sul) == (23, True) and 110 < area_ha(proj[0]['aneis']) < 116
        kml = os.path.join(pasta, 't.kml')
        open(kml, 'w', encoding='utf-8').write(
            '<kml><Document><Placemark><name>Zona Alta</name><Polygon><outerBoundaryIs><LinearRing><coordinates>'
            '-47.05,-22.85,0 -47.04,-22.85,0 -47.04,-22.84,0 -47.05,-22.84,0 -47.05,-22.85,0'
            '</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>')
        assert ler_areas(kml)[0][0]['nome'] == 'Zona Alta'
    print('areas OK: leitura com nome, projeção de ida e volta, dentro, borda e área com furo')
