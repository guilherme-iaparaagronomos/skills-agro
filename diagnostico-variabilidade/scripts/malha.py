"""A grade comum: uma malha de células quadradas sobre o talhão, e cada camada
levada para ela.

- Raster (GeoTIFF): o valor no centro da célula. Quando o pixel do raster é bem
  menor que a célula, a célula recebe a média de vários pontos dentro dela, para
  não sortear um pixel só.
- Pontos densos (monitor de colheita, condutividade, GPS de máquina): a média
  dos pontos que caem em cada célula. Célula sem ponto fica sem valor: aqui não
  se interpola. Amostra esparsa (laudo de solo) deve vir já interpolada.
- Polígonos com classe (zonas, variedades, talhões): a classe do polígono onde
  cai o centro da célula.

Teste embutido: python scripts/malha.py
"""

import math

import numpy as np
from scipy.spatial import cKDTree

import geotiff
from areas import dentro, utm_inversa

CELULAS = (5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 150, 200)
ALVO_DE_CELULAS = 20000
TETO_DE_CELULAS = 400000


def celula_automatica(area_m2):
    """A menor célula da lista, a partir de 10 m, que deixa o talhão com até ALVO_DE_CELULAS células."""
    alvo = max(10.0, math.sqrt(area_m2 / ALVO_DE_CELULAS))
    return float(next((c for c in CELULAS if c >= alvo), CELULAS[-1]))


def montar(areas, celula):
    """Grade alinhada a múltiplos da célula. Devolve dict: x0, y0 (canto superior esquerdo), celula,
    nx, ny, mascara [ny, nx] (centro da célula dentro do perímetro), x e y dos centros."""
    xs = [p[0] for a in areas for anel in a['aneis'] for p in anel]
    ys = [p[1] for a in areas for anel in a['aneis'] for p in anel]
    x0 = math.floor(min(xs) / celula) * celula
    y0 = math.ceil(max(ys) / celula) * celula
    nx = max(1, int(math.ceil((max(xs) - x0) / celula)))
    ny = max(1, int(math.ceil((y0 - min(ys)) / celula)))
    if nx * ny > 4 * TETO_DE_CELULAS:
        raise ValueError(f'a grade teria {nx} × {ny} células de {celula:g} m: aumente a célula (--celula)')
    cx = x0 + (np.arange(nx) + 0.5) * celula
    cy = y0 - (np.arange(ny) + 0.5) * celula
    gx, gy = np.meshgrid(cx, cy)
    centros = np.column_stack([gx.ravel(), gy.ravel()])
    mascara = np.zeros(nx * ny, dtype=bool)
    for a in areas:
        mascara |= dentro(a['aneis'], centros)
    mascara = mascara.reshape(ny, nx)
    if mascara.sum() > TETO_DE_CELULAS:
        raise ValueError(f'{int(mascara.sum())} células de {celula:g} m dentro do perímetro: aumente a célula (--celula)')
    return {'x0': x0, 'y0': y0, 'celula': float(celula), 'nx': nx, 'ny': ny, 'mascara': mascara, 'x': gx, 'y': gy}


def pixel_em_metros(raster, zona, sul, g):
    """Lado do pixel do raster em metros (para raster em graus, na latitude do talhão)."""
    if raster['crs'] != 'geo':
        return float(raster['dx']), float(raster['dy'])
    _, lat = utm_inversa([g['x0'] + g['nx'] * g['celula'] / 2], [g['y0'] - g['ny'] * g['celula'] / 2], zona, sul)
    return (float(raster['dx']) * 111320.0 * math.cos(math.radians(float(lat[0]))), float(raster['dy']) * 110574.0)


def de_raster(g, raster, zona, sul):
    """Leva o raster para a grade. Devolve (malha [ny, nx] com nan fora, info)."""
    px, py = pixel_em_metros(raster, zona, sul, g)
    pixel = math.sqrt(px * py)
    k = int(min(6, max(1, round(g['celula'] / pixel))))
    m = g['mascara']
    x, y = g['x'][m], g['y'][m]
    if k == 1:
        valores = geotiff.amostrar(raster, x, y, zona, sul)
    else:
        passos = ((np.arange(k) + 0.5) / k - 0.5) * g['celula']
        soma, conta = np.zeros(len(x)), np.zeros(len(x))
        for dy in passos:
            for dx in passos:
                v = geotiff.amostrar(raster, x + dx, y + dy, zona, sul)
                bom = np.isfinite(v)
                soma[bom] += v[bom]
                conta[bom] += 1
        valores = np.where(conta >= max(1, (k * k) // 2), soma / np.maximum(conta, 1), np.nan)
    malha = np.full(m.shape, np.nan)
    malha[m] = valores
    info = {'tipo': 'raster', 'pixel_m': pixel, 'src': 'graus' if raster['crs'] == 'geo' else f'UTM {raster["zona"]}{"S" if raster["sul"] else "N"}',
            'largura': raster['largura'], 'altura': raster['altura'], 'pontos_por_celula': k * k,
            'mais_grossa_que_a_celula': pixel > 1.5 * g['celula']}
    return malha, info


def _indice_da_celula(g, x, y):
    col = np.floor((np.asarray(x, float) - g['x0']) / g['celula']).astype(int)
    lin = np.floor((g['y0'] - np.asarray(y, float)) / g['celula']).astype(int)
    ok = (col >= 0) & (col < g['nx']) & (lin >= 0) & (lin < g['ny'])
    ok[ok] &= g['mascara'][lin[ok], col[ok]]
    return lin, col, ok


def espacamento_tipico(x, y, teto=4000):
    """Mediana da distância de cada ponto ao vizinho mais próximo (numa amostra de até `teto` pontos)."""
    xy = np.column_stack([x, y])
    xy = xy[np.isfinite(xy).all(axis=1)]
    if len(xy) < 3:
        return float('nan')
    if len(xy) > teto:
        xy_ref = xy[:: max(1, len(xy) // teto)]
    else:
        xy_ref = xy
    d, _ = cKDTree(xy).query(xy_ref, k=2)
    return float(np.median(d[:, 1]))


def de_pontos(g, x, y, valores):
    """Média dos pontos em cada célula. Devolve (malha, info). Célula sem ponto fica nan."""
    v = np.asarray(valores, float)
    lin, col, ok = _indice_da_celula(g, x, y)
    ok &= np.isfinite(v)
    plano = lin[ok] * g['nx'] + col[ok]
    soma = np.bincount(plano, weights=v[ok], minlength=g['nx'] * g['ny'])
    conta = np.bincount(plano, minlength=g['nx'] * g['ny'])
    malha = np.where(conta > 0, soma / np.maximum(conta, 1), np.nan).reshape(g['ny'], g['nx'])
    malha[~g['mascara']] = np.nan
    com = conta.reshape(g['ny'], g['nx'])[g['mascara']]
    info = {'tipo': 'pontos', 'pontos_dentro': int(ok.sum()), 'espacamento_m': espacamento_tipico(np.asarray(x)[ok], np.asarray(y)[ok]),
            'pontos_por_celula': float(np.median(com[com > 0])) if (com > 0).any() else 0.0}
    return malha, info


def de_classes(g, areas_com_classe):
    """Classe do polígono onde cai o centro da célula. Devolve (rótulos int [ny, nx], -1 = nenhuma; nomes)."""
    nomes = []
    rotulos = np.full(g['nx'] * g['ny'], -1, dtype=np.int32)
    centros = np.column_stack([g['x'].ravel(), g['y'].ravel()])
    for a in areas_com_classe:
        nome = str(a['nome'])
        if nome not in nomes:
            nomes.append(nome)
        rotulos[dentro(a['aneis'], centros) & (rotulos < 0)] = nomes.index(nome)
    rotulos = rotulos.reshape(g['ny'], g['nx'])
    rotulos[~g['mascara']] = -1
    return rotulos, nomes


def descrever(g, malha):
    """Cobertura e resumo de uma camada numérica dentro do perímetro."""
    dentro_ = malha[g['mascara']]
    bons = dentro_[np.isfinite(dentro_)]
    n = int(g['mascara'].sum())
    if len(bons) == 0:
        return {'celulas': 0, 'cobertura_pct': 0.0, 'minimo': None, 'media': None, 'maximo': None, 'desvio': None,
                'cv_pct': None, 'distintos': 0}
    media, desvio = float(bons.mean()), float(bons.std())
    return {'celulas': int(len(bons)), 'cobertura_pct': 100.0 * len(bons) / n, 'minimo': float(bons.min()), 'media': media,
            'maximo': float(bons.max()), 'desvio': desvio, 'cv_pct': (100.0 * desvio / abs(media)) if media else None,
            'distintos': int(len(np.unique(np.round(bons, 9))))}


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    quadrado = [{'nome': 'T', 'aneis': [[(500000, 7500000), (500400, 7500000), (500400, 7500300), (500000, 7500300), (500000, 7500000)]]}]
    assert celula_automatica(120000) == 10.0 and celula_automatica(9_000_000) == 25.0
    g = montar(quadrado, 10.0)
    assert (g['nx'], g['ny'], int(g['mascara'].sum())) == (40, 30, 1200), (g['nx'], g['ny'], int(g['mascara'].sum()))
    assert g['x'][0, 0] == 500005 and g['y'][0, 0] == 7500295

    # raster de 10 m com um plano conhecido (valor = leste − 500000): centro da célula devolve o plano
    xx = (np.arange(60) + 0.5) * 10 + 499900
    plano = np.tile(xx - 500000, (50, 1))
    raster = {'dados': plano, 'x0': 499900.0, 'y0': 7500400.0, 'dx': 10.0, 'dy': 10.0, 'crs': 'utm', 'zona': 22, 'sul': True,
              'epsg': 31982, 'largura': 60, 'altura': 50, 'bandas': 1}
    m, info = de_raster(g, raster, 22, True)
    assert np.allclose(m[g['mascara']], (g['x'] - 500000)[g['mascara']]) and info['pontos_por_celula'] == 1
    # raster de 2 m do mesmo plano: média de 25 pontos por célula, mesmo resultado
    xx2 = (np.arange(300) + 0.5) * 2 + 499900
    fino = dict(raster, dados=np.tile(xx2 - 500000, (250, 1)), dx=2.0, dy=2.0, largura=300, altura=250)
    m2, info2 = de_raster(g, fino, 22, True)
    assert np.allclose(m2[g['mascara']], m[g['mascara']]) and info2['pontos_por_celula'] == 25
    # raster que cobre só a metade oeste: a outra metade fica sem valor
    meio = dict(raster, dados=plano[:, :30], largura=30)
    m3, _ = de_raster(g, meio, 22, True)
    d3 = descrever(g, m3)
    assert 45 < d3['cobertura_pct'] < 55, d3
    # raster de 40 m: mais grosso que a célula
    grosso = dict(raster, dados=np.ones((13, 15)), dx=40.0, dy=40.0, largura=15, altura=13)
    assert de_raster(g, grosso, 22, True)[1]['mais_grossa_que_a_celula']

    # pontos: três numa célula (média), um fora do perímetro, um sem valor
    x = np.array([500012.0, 500015.0, 500018.0, 500205.0, 499000.0, 500305.0])
    y = np.array([7500012.0, 7500015.0, 7500018.0, 7500105.0, 7500105.0, 7500105.0])
    v = np.array([1.0, 2.0, 6.0, 10.0, 99.0, np.nan])
    mp, ip = de_pontos(g, x, y, v)
    assert ip['pontos_dentro'] == 4 and int(np.isfinite(mp).sum()) == 2
    lin, col = 30 - 2, 1
    assert mp[lin, col] == 3.0 and mp[30 - 11, 20] == 10.0, (mp[lin, col], mp[30 - 11, 20])
    assert abs(espacamento_tipico(x[:3], y[:3]) - math.hypot(3, 3)) < 1e-9

    # classes: duas metades
    metades = [{'nome': 'A', 'aneis': [[(500000, 7500000), (500200, 7500000), (500200, 7500300), (500000, 7500300), (500000, 7500000)]]},
               {'nome': 'B', 'aneis': [[(500200, 7500000), (500400, 7500000), (500400, 7500300), (500200, 7500300), (500200, 7500000)]]}]
    rot, nomes = de_classes(g, metades)
    assert nomes == ['A', 'B'] and int((rot == 0).sum()) == 600 and int((rot == 1).sum()) == 600
    d = descrever(g, m)
    assert d['cobertura_pct'] == 100.0 and d['minimo'] == 5.0 and d['maximo'] == 395.0 and d['distintos'] == 40
    try:
        montar(quadrado, 0.1)
    except ValueError as erro:
        assert 'aumente a célula' in str(erro)
    else:
        raise AssertionError('devia recusar a grade enorme')
    print('malha OK (raster no centro, raster fino por média, cobertura parcial, pontos por célula, classes)')


if __name__ == '__main__':
    _autoteste()
