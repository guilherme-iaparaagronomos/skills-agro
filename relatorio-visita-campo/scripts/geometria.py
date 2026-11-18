"""Geometrias e projeção: GeoJSON/KML/WKT/shapefile/CSV → UTM → grade de 5 m.

Convenções:
- Coordenadas geográficas (lon/lat, WGS84/SIRGAS) são detectadas pela magnitude
  (|lon| ≤ 180 e |lat| ≤ 90); qualquer outra coisa é tratada como UTM em metros
  e exige a zona (do .prj ou informada pelo usuário).
- Projeção alvo: UTM / SIRGAS 2000 (GRS80) — fórmulas de Snyder, erro ≪ 1 m,
  mais que suficiente para pixel de 5 m.
- Furos e multipolígonos são resolvidos por paridade (ponto dentro de um número
  ímpar de anéis = dentro do talhão).
"""

import csv
import json
import math
import re
from pathlib import Path

import numpy as np

try:  # arquivos KML são locais e do próprio usuário, mas defusedxml não custa
    from defusedxml import ElementTree as ET
except ImportError:
    from xml.etree import ElementTree as ET

# ---------------------------------------------------------------- projeção UTM

_A = 6378137.0
_F = 1 / 298.257222101  # GRS80 (SIRGAS 2000)
_E2 = _F * (2 - _F)
_EP2 = _E2 / (1 - _E2)
_K0 = 0.9996


def zona_de(lon, lat):
    return int(math.floor((lon + 180) / 6) + 1), lat < 0


def epsg_utm(zona, sul):
    """EPSG SIRGAS 2000 / UTM (31954+zona no N, 31960+zona no S)."""
    return (31960 if sul else 31954) + zona


def utm_direta(lons, lats, zona, sul):
    """Projeção UTM (Transverse Mercator, série de Snyder), vetorizada."""
    lon = np.radians(np.asarray(lons, dtype=float))
    lat = np.radians(np.asarray(lats, dtype=float))
    lon0 = math.radians(zona * 6 - 183)

    sen, cos = np.sin(lat), np.cos(lat)
    n = _A / np.sqrt(1 - _E2 * sen**2)
    t = np.tan(lat) ** 2
    c = _EP2 * cos**2
    a = (lon - lon0) * cos
    m = _A * (
        (1 - _E2 / 4 - 3 * _E2**2 / 64 - 5 * _E2**3 / 256) * lat
        - (3 * _E2 / 8 + 3 * _E2**2 / 32 + 45 * _E2**3 / 1024) * np.sin(2 * lat)
        + (15 * _E2**2 / 256 + 45 * _E2**3 / 1024) * np.sin(4 * lat)
        - (35 * _E2**3 / 3072) * np.sin(6 * lat)
    )
    x = _K0 * n * (a + (1 - t + c) * a**3 / 6
                   + (5 - 18 * t + t**2 + 72 * c - 58 * _EP2) * a**5 / 120) + 500000
    y = _K0 * (m + n * np.tan(lat) * (a**2 / 2 + (5 - t + 9 * c + 4 * c**2) * a**4 / 24
               + (61 - 58 * t + t**2 + 600 * c - 330 * _EP2) * a**6 / 720))
    if sul:
        y = y + 10000000
    return x, y


def _geografica(xs, ys):
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    return bool(np.all(np.abs(xs) <= 180) and np.all(np.abs(ys) <= 90))


# ---------------------------------------------------------------- leitura

def _sem_ns(tag):
    return tag.rsplit('}', 1)[-1]


def _coords_kml(texto):
    pares = []
    for trecho in texto.replace('\n', ' ').split():
        partes = trecho.split(',')
        if len(partes) >= 2:
            pares.append((float(partes[0]), float(partes[1])))
    return pares


def _aneis_geojson(geom):
    t, cs = geom.get('type'), geom.get('coordinates')
    if t == 'Polygon':
        return [[(p[0], p[1]) for p in anel] for anel in cs]
    if t == 'MultiPolygon':
        return [[(p[0], p[1]) for p in anel] for poli in cs for anel in poli]
    raise ValueError(f'geometria {t} não é polígono')


def ler_perimetro(caminho):
    """Lê o perímetro do talhão. Devolve (aneis, crs, zona):
    aneis = [[(x, y), ...], ...] (furos inclusos — paridade resolve),
    crs = 'geo' | 'utm', zona = (n, sul?) ou None."""
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    zona = None

    if ext == '.shp':
        from shapefile_min import ler_shp
        tipo, geoms, _, zona = ler_shp(str(caminho))
        if tipo != 'poligono':
            raise ValueError('o shapefile do perímetro precisa ser de polígonos')
        aneis = [anel for g in geoms if g for anel in g]
    elif ext in ('.geojson', '.json'):
        gj = json.loads(caminho.read_text(encoding='utf-8-sig'))
        feats = gj.get('features', [gj] if gj.get('type') != 'FeatureCollection' else [])
        aneis = []
        for f in feats:
            geom = f.get('geometry', f)
            if geom and geom.get('type') in ('Polygon', 'MultiPolygon'):
                aneis += _aneis_geojson(geom)
    elif ext == '.kml':
        raiz = ET.fromstring(caminho.read_text(encoding='utf-8-sig'))
        aneis = []
        for el in raiz.iter():
            if _sem_ns(el.tag) == 'Polygon':
                for sub in el.iter():
                    if _sem_ns(sub.tag) == 'coordinates':
                        aneis.append(_coords_kml(sub.text or ''))
    else:  # WKT em .wkt/.txt
        texto = caminho.read_text(encoding='utf-8-sig')
        if 'POLYGON' not in texto.upper():
            raise ValueError(f'formato de perímetro não reconhecido: {ext}')
        aneis = []
        for grupo in re.findall(r'\(([^()]+)\)', texto):
            pares = [tuple(map(float, p.split()[:2])) for p in grupo.split(',')]
            aneis.append(pares)

    aneis = [a for a in aneis if len(a) >= 4]
    if not aneis:
        raise ValueError(f'nenhum polígono encontrado em {caminho.name}')
    xs = [p[0] for a in aneis for p in a]
    ys = [p[1] for a in aneis for p in a]
    crs = 'geo' if _geografica(xs, ys) else 'utm'
    return aneis, crs, zona


_NOMES_LON = {'lon', 'long', 'longitude', 'lng', 'x'}
_NOMES_LAT = {'lat', 'latitude', 'y'}


def ler_pontos(caminho):
    """Lê os pontos de amostragem. Devolve (props, coords, crs, zona):
    props = [dict de atributos por ponto], coords = [(x, y)]."""
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    zona = None

    if ext == '.shp':
        from shapefile_min import ler_shp
        tipo, geoms, attrs, zona = ler_shp(str(caminho))
        if tipo != 'ponto':
            raise ValueError('o shapefile de amostras precisa ser de pontos')
        props = [a for g, a in zip(geoms, attrs) if g]
        coords = [g for g in geoms if g]
    elif ext in ('.geojson', '.json'):
        gj = json.loads(caminho.read_text(encoding='utf-8-sig'))
        props, coords = [], []
        for f in gj.get('features', []):
            g = f.get('geometry') or {}
            if g.get('type') == 'Point':
                coords.append(tuple(g['coordinates'][:2]))
                props.append(f.get('properties') or {})
    elif ext == '.kml':
        raiz = ET.fromstring(caminho.read_text(encoding='utf-8-sig'))
        props, coords = [], []
        for el in raiz.iter():
            if _sem_ns(el.tag) != 'Placemark':
                continue
            atual, nome = None, ''
            dados = {}
            for sub in el.iter():
                t = _sem_ns(sub.tag)
                if t == 'name':
                    nome = (sub.text or '').strip()
                elif t == 'Point':
                    atual = sub
                elif t in ('Data', 'SimpleData'):
                    chave = sub.get('name', '')
                    valor = sub.findtext('*') if t == 'Data' else sub.text
                    if chave:
                        dados[chave] = (valor or '').strip()
            if atual is not None:
                for sub in atual.iter():
                    if _sem_ns(sub.tag) == 'coordinates':
                        c = _coords_kml(sub.text or '')
                        if c:
                            coords.append(c[0])
                            props.append({'name': nome, **dados})
    elif ext == '.csv':
        with open(caminho, encoding='utf-8-sig', newline='') as f:
            amostra = f.read(4096)
            f.seek(0)
            delim = ';' if amostra.count(';') > amostra.count(',') else ','
            linhas = list(csv.DictReader(f, delimiter=delim))
        baixas = {k.lower().strip(): k for k in (linhas[0] if linhas else {})}
        col_x = next((baixas[n] for n in _NOMES_LON if n in baixas), None)
        col_y = next((baixas[n] for n in _NOMES_LAT if n in baixas), None)
        if not col_x or not col_y:
            raise ValueError('CSV de pontos precisa de colunas de coordenadas (lon/lat ou x/y)')
        props, coords = [], []
        for ln in linhas:
            try:
                x = float(str(ln[col_x]).replace(',', '.'))
                y = float(str(ln[col_y]).replace(',', '.'))
            except (TypeError, ValueError):
                continue
            coords.append((x, y))
            props.append({k: v for k, v in ln.items() if k not in (col_x, col_y)})
    else:
        raise ValueError(f'formato de pontos não reconhecido: {ext}')

    if len(coords) < 3:
        raise ValueError(f'só {len(coords)} pontos lidos de {caminho.name}')
    xs, ys = zip(*coords)
    crs = 'geo' if _geografica(xs, ys) else 'utm'
    return props, coords, crs, zona


def unificar_utm(perimetro, pontos, zona_manual=None):
    """Leva perímetro e pontos ao MESMO UTM. Cada item = (dados, crs, zona).
    Devolve (aneis_utm, coords_utm, zona, sul, epsg)."""
    aneis, crs_per, zona_per = perimetro
    coords, crs_pts, zona_pts = pontos

    zona = zona_manual or zona_per or zona_pts
    if zona is None:
        if 'utm' in (crs_per, crs_pts):
            raise ValueError(
                'coordenadas em metros sem .prj — informe a zona UTM (ex.: --zona 22S)'
            )
        # tudo geográfico: zona pelo centroide do perímetro
        lons = [p[0] for a in aneis for p in a]
        lats = [p[1] for a in aneis for p in a]
        zona = zona_de(sum(lons) / len(lons), sum(lats) / len(lats))
    z, sul = zona

    def leva(pares, crs):
        if crs == 'utm':
            return [(float(x), float(y)) for x, y in pares]
        xs, ys = utm_direta([p[0] for p in pares], [p[1] for p in pares], z, sul)
        return list(zip(xs.tolist(), ys.tolist()))

    aneis_utm = [leva(a, crs_per) for a in aneis]
    coords_utm = leva(coords, crs_pts)
    return aneis_utm, coords_utm, z, sul, epsg_utm(z, sul)


# ---------------------------------------------------------------- grade

def grade_e_mascara(aneis_utm, pixel=5.0, folga=1):
    """Grade regular cobrindo o perímetro. Devolve (x_oeste, y_norte, nx, ny,
    mascara[ny, nx], xc, yc) — linha 0 = norte; centros de célula em xc/yc."""
    from matplotlib.path import Path as CaminhoMpl

    xs = [p[0] for a in aneis_utm for p in a]
    ys = [p[1] for a in aneis_utm for p in a]
    x_oeste = math.floor(min(xs) / pixel) * pixel - folga * pixel
    y_norte = math.ceil(max(ys) / pixel) * pixel + folga * pixel
    nx = int(math.ceil((max(xs) - x_oeste) / pixel)) + folga
    ny = int(math.ceil((y_norte - min(ys)) / pixel)) + folga

    xc = x_oeste + (np.arange(nx) + 0.5) * pixel
    yc = y_norte - (np.arange(ny) + 0.5) * pixel
    gx, gy = np.meshgrid(xc, yc)
    centros = np.column_stack([gx.ravel(), gy.ravel()])

    # paridade por anel, testando só as células dentro do bbox do anel —
    # em fazendas com dezenas de talhões isso corta o custo em ordens de grandeza
    dentro = np.zeros(len(centros), dtype=bool)
    for anel in aneis_utm:
        axs = [p[0] for p in anel]
        ays = [p[1] for p in anel]
        cand = ((centros[:, 0] >= min(axs)) & (centros[:, 0] <= max(axs))
                & (centros[:, 1] >= min(ays)) & (centros[:, 1] <= max(ays)))
        idx = np.flatnonzero(cand)
        if len(idx):
            dentro[idx] ^= CaminhoMpl(anel).contains_points(centros[idx])
    return x_oeste, y_norte, nx, ny, dentro.reshape(ny, nx), xc, yc


if __name__ == '__main__':
    # exemplo embutido: projeção conhecida + grade com furo
    # região de Campinas-SP, zona 23S (2° a oeste do meridiano central −45°)
    x, y = utm_direta([-47.0], [-22.9], 23, True)
    assert abs(x[0] - 294857) < 100 and abs(y[0] - 7466157) < 100, (x, y)
    # cheque físico: 0,01° de longitude nessa latitude ≈ 1.025 m (com k0)
    x2, _ = utm_direta([-46.99], [-22.9], 23, True)
    passo = x2[0] - x[0]
    assert 1015 < passo < 1035, passo
    print(f'utm_direta OK: E={x[0]:.0f} N={y[0]:.0f} | 0,01°lon = {passo:.1f} m '
          f'(EPSG {epsg_utm(23, True)})')

    quadrado = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
    furo = [(40, 40), (60, 40), (60, 60), (40, 60), (40, 40)]
    x0, y0, nx, ny, m, xc, yc = grade_e_mascara([quadrado, furo], pixel=5)
    assert m.shape == (ny, nx)
    area = m.sum() * 25
    assert 9000 < area < 10100, area  # 100×100 menos furo 20×20 ≈ 9600 m²
    print(f'grade OK: {nx}×{ny} células, área mascarada {area:.0f} m² (~9600)')
