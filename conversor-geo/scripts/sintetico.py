"""Fazenda INVENTADA para a demonstração e os testes: nada aqui é dado de verdade.

Quatro talhões vizinhos em UTM fuso 22S (com uma divisa em T e um talhão com
furo), oito pontos de amostra, um carreador e uma versão dos talhões com os
defeitos de geometria mais comuns.
"""

import numpy as np

import projecao

ZONA, SUL = 22, True
E0, N0 = 512000.0, 7445000.0


def _desloca(seq):
    return [(E0 + x, N0 + y) for x, y in seq]


def talhoes_utm():
    """Feições de polígono em metros (SIRGAS 2000 / UTM 22S)."""
    dados = [
        ('T01', 'Soja', [[(0, 0), (600, 0), (600, 500), (0, 500), (0, 0)]]),
        ('T02', 'Soja', [[(600, 0), (1100, 0), (1150, 500), (600, 500), (600, 0)]]),
        # a divisa de baixo do T03 passa reta por cima do canto (600, 500) dos dois de baixo: divisa em T
        ('T03', 'Milho', [[(0, 500), (1150, 500), (1100, 950), (0, 900), (0, 500)]]),
        # talhão com um furo (uma represa) no meio
        ('T04', 'Pastagem', [[(1100, 0), (1700, 0), (1700, 800), (1123.5294117647059, 738.2352941176471), (1150, 500), (1100, 0)],
                             [(1350, 300), (1350, 450), (1500, 450), (1500, 300), (1350, 300)]]),
    ]
    feicoes = []
    for nome, cultura, aneis in dados:
        feicoes.append({'geometry': {'type': 'Polygon', 'coordinates': [_desloca(a) for a in aneis]},
                        'properties': {'TALHAO': nome, 'CULTURA': cultura, 'FAZENDA': 'Fazenda Exemplo', 'OBSERVACAO_DE_CAMPO': 'inventado'}})
    return feicoes


def _em_graus(feicoes):
    saida = []
    for f in feicoes:
        g = f['geometry']

        def leva(seq):
            a = np.asarray(seq, dtype=float)
            lon, lat = projecao.utm_inversa(a[:, 0], a[:, 1], ZONA, SUL)
            return list(zip(lon.tolist(), lat.tolist()))
        t, c = g['type'], g['coordinates']
        if t == 'Point':
            novo = leva([c])[0]
        elif t == 'LineString':
            novo = leva(c)
        else:
            novo = [leva(a) for a in c]
        saida.append({'geometry': {'type': t, 'coordinates': novo}, 'properties': dict(f['properties'])})
    return saida


def talhoes():
    """Os mesmos talhões em graus."""
    return _em_graus(talhoes_utm())


def pontos():
    rng = np.random.default_rng(7)
    fs = []
    for i, (x, y) in enumerate([(150, 120), (450, 380), (800, 150), (950, 400), (300, 700), (850, 720), (1250, 150), (1600, 650)], 1):
        fs.append({'geometry': {'type': 'Point', 'coordinates': (E0 + x, N0 + y)},
                   'properties': {'ID': f'P{i:02d}', 'ARGILA': round(float(rng.uniform(25, 60)), 1), 'COLETA': '2026-10-05'}})
    return _em_graus(fs)


def carreador():
    f = {'geometry': {'type': 'LineString', 'coordinates': _desloca([(0, 500), (600, 500), (1150, 500), (1700, 520)])},
         'properties': {'NOME': 'Carreador central', 'TIPO': 'estrada interna'}}
    return _em_graus([f])


def talhoes_com_defeito():
    """Em graus, com: anel aberto e vértice repetido (T01), ida e volta (T02), contorno que se cruza (T03)."""
    fs = talhoes_utm()
    a = fs[0]['geometry']['coordinates'][0]
    fs[0]['geometry']['coordinates'][0] = [a[0], a[1], a[1], a[2], a[3]]  # sem o ponto que fecha, e com um repetido
    b = fs[1]['geometry']['coordinates'][0]
    fs[1]['geometry']['coordinates'][0] = [b[0], b[1], b[2], (b[2][0] + 80, b[2][1] + 60), b[2], b[3], b[4]]
    c = fs[2]['geometry']['coordinates'][0]
    fs[2]['geometry']['coordinates'][0] = [c[0], c[2], c[1], c[3], c[0]]  # dois vértices trocados: vira uma gravata
    return _em_graus(fs[:3])


if __name__ == '__main__':
    import geom
    ts = talhoes_utm()
    areas = [geom.area_m2(f['geometry']) / 10000 for f in ts]
    assert [round(a, 2) for a in areas] == [30.0, 26.25, 47.88, 41.7], areas
    assert len(talhoes()) == 4 and len(pontos()) == 8 and len(carreador()) == 1 and len(talhoes_com_defeito()) == 3
    lon, lat = talhoes()[0]['geometry']['coordinates'][0][0]
    assert -51 < lon < -50.8 and -23.2 < lat < -23.0, (lon, lat)
    print(f'sintetico OK: 4 talhões inventados ({sum(areas):.2f} ha), 8 pontos, 1 linha e 3 talhões com defeito')
