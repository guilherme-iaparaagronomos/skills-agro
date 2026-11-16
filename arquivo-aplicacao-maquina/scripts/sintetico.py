"""Talhão INVENTADO para a demonstração e os testes: nada aqui é dado de fazenda.

- `grade()`: um talhão de 600 m por 450 m em células de 30 m, com a dose em
  kg/ha em cinco classes (o desenho de um mapa de aplicação em grade);
- `zonas()`: o mesmo talhão em três zonas, com o campo `zona`, como sai da
  skill zonas-de-manejo;
- `grade_grande()`: milhares de células, para testar arquivo pesado;
- `com_defeitos()`: a grade com os defeitos que a skill tem de pegar.

As coordenadas nascem em metros (UTM 22S) e são levadas a graus.

Teste embutido: python scripts/sintetico.py
"""

import math

import projecao

ZONA, SUL = 22, True
E0, N0 = 512000.0, 7445000.0
CLASSES = [80.0, 120.0, 160.0, 200.0, 240.0]


def _graus(pontos):
    lon, lat = projecao.utm_inversa([E0 + x for x, _ in pontos], [N0 + y for _, y in pontos], ZONA, SUL)
    return list(zip(lon.tolist(), lat.tolist()))


def _retangulo(x0, y0, x1, y1):
    return _graus([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def dose_em(x, y, largura=600.0, altura=450.0):
    """Dose inventada, em kg/ha: uma rampa suave com uma mancha, cortada em cinco classes."""
    v = 0.55 * x / largura + 0.25 * y / altura + 0.25 * math.exp(-(((x - 0.3 * largura) / (0.2 * largura)) ** 2
                                                                  + ((y - 0.6 * altura) / (0.25 * altura)) ** 2))
    return CLASSES[min(len(CLASSES) - 1, int(v * len(CLASSES)))]


def grade(lado=30.0, colunas=20, linhas=15):
    """Feições de polígono em graus, uma por célula, com a dose no campo DOSE (kg/ha)."""
    feicoes = []
    for j in range(linhas):
        for i in range(colunas):
            x0, y0 = i * lado, j * lado
            dose = dose_em(x0 + lado / 2, y0 + lado / 2, colunas * lado, linhas * lado)
            feicoes.append({'geometry': {'type': 'Polygon', 'coordinates': [_retangulo(x0, y0, x0 + lado, y0 + lado)]},
                            'properties': {'ID': j * colunas + i + 1, 'DOSE': dose, 'TALHAO': 'T01'}})
    return feicoes


def grade_grande(colunas=100, linhas=60, lado=10.0):
    return grade(lado, colunas, linhas)


def zonas():
    """Três zonas que cobrem o talhão (faixas), com o campo `zona`, como no zonas.geojson da skill zonas-de-manejo."""
    faixas = [(1, [(0, 0, 200, 450)]), (2, [(200, 0, 400, 450)]), (3, [(400, 0, 600, 300), (400, 300, 600, 450)])]
    feicoes = []
    for zona, retangulos in faixas:
        if len(retangulos) == 1:
            g = {'type': 'Polygon', 'coordinates': [_retangulo(*retangulos[0])]}
        else:
            g = {'type': 'MultiPolygon', 'coordinates': [[_retangulo(*r)] for r in retangulos]}
        feicoes.append({'geometry': g, 'properties': {'zona': zona, 'area_ha': 0.0, 'partes': len(retangulos)}})
    return feicoes


def com_defeitos():
    """A grade com: dose em texto com vírgula, uma dose vazia, uma negativa, um texto que não é número,
    um ponto perdido no meio dos polígonos e um nome de campo com acento."""
    feicoes = []
    for k, f in enumerate(grade()):
        p = dict(f['properties'])
        dose = p.pop('DOSE')
        p['Dose (kg/ha)'] = f'{dose:.1f}'.replace('.', ',')
        feicoes.append({'geometry': f['geometry'], 'properties': p})
    feicoes[5]['properties']['Dose (kg/ha)'] = ''
    feicoes[9]['properties']['Dose (kg/ha)'] = '-40'
    feicoes[14]['properties']['Dose (kg/ha)'] = '120 kg'
    feicoes.append({'geometry': {'type': 'Point', 'coordinates': _graus([(300, 200)])[0]}, 'properties': {'ID': 999, 'Dose (kg/ha)': '100', 'TALHAO': 'T01'}})
    return feicoes


def geojson(feicoes):
    """Texto GeoJSON das feições (em graus)."""
    import json
    return json.dumps({'type': 'FeatureCollection',
                       'features': [{'type': 'Feature', 'properties': f['properties'], 'geometry': f['geometry']} for f in feicoes]},
                      ensure_ascii=False)


if __name__ == '__main__':
    import geom
    g = grade()
    assert len(g) == 300 and {f['properties']['DOSE'] for f in g} <= set(CLASSES) and len({f['properties']['DOSE'] for f in g}) >= 4
    areas, _, _ = geom.medir(g, projecao.geo('SIRGAS 2000'))
    assert abs(sum(areas) - 27.0) < 0.01 and abs(areas[0] - 0.09) < 1e-4, (sum(areas), areas[0])
    z = zonas()
    az, _, _ = geom.medir(z, projecao.geo('SIRGAS 2000'))
    assert [f['properties']['zona'] for f in z] == [1, 2, 3] and abs(sum(az) - 27.0) < 0.01 and z[2]['geometry']['type'] == 'MultiPolygon'
    assert len(grade_grande()) == 6000 and len(com_defeitos()) == 301 and '"FeatureCollection"' in geojson(z)
    print('sintetico OK: grade de 300 células (27 ha), 3 zonas, grade de 6.000 células, grade com defeitos')
