"""Talhão de exemplo com zonas PLANTADAS, para a demonstração e para medir o método.

Não é dado de fazenda: é um talhão inventado, com três zonas de formato
conhecido. Cada camada (argila, produtividade, altitude e um índice de
vegetação) tem uma média por zona e ruído por cima, de modo que ponto a ponto
as zonas se misturam, como no campo. Serve para duas coisas:
  - a demonstração (zonas.py --demo), que roda sem arquivo do usuário;
  - o teste que mede quanto das zonas plantadas o método recupera.

Teste embutido: python scripts/sintetico.py
"""

import csv
import json
import math

import numpy as np

from areas import dentro, utm_inversa

ZONA, SUL = 22, True
ORIGEM = (642300.0, 7541800.0)  # canto do talhão, em UTM 22S (interior de SP)
CONTORNO = [(0, 40), (520, 0), (900, 180), (860, 620), (420, 760), (60, 560)]  # metros, a partir da origem
MEDIAS = {  # média de cada camada em cada zona plantada (0, 1, 2)
    'argila_g_kg': (190.0, 320.0, 450.0),
    'prod_t_ha': (2.9, 3.6, 4.3),
    'altitude_m': (534.0, 526.0, 518.0),
}
RUIDO = {'argila_g_kg': 45.0, 'prod_t_ha': 0.32, 'altitude_m': 2.6}
MEDIAS_INDICE, RUIDO_INDICE = (0.58, 0.68, 0.79), 0.045


def zona_plantada(u, v):
    """A zona verdadeira de cada posição (u, v em metros a partir da origem): 0, 1 ou 2."""
    u, v = np.asarray(u, float), np.asarray(v, float)
    z = np.ones(u.shape, dtype=int)
    z[u < 290 + 70 * np.sin(v / 130.0)] = 0
    z[np.hypot(u - 660, v - 430) < 190] = 2
    return z


def talhao(semente=11, espacamento=20.0):
    """Devolve o dicionário do exemplo: os pontos com as camadas, a zona verdadeira de cada ponto,
    o perímetro e um raster do índice de vegetação (para a demonstração ler também um GeoTIFF)."""
    g = np.random.default_rng(semente)
    us, vs = np.meshgrid(np.arange(10, 900, espacamento), np.arange(10, 760, espacamento))
    u = us.ravel() + g.uniform(-3, 3, us.size)
    v = vs.ravel() + g.uniform(-3, 3, vs.size)
    fica = dentro([CONTORNO], np.column_stack([u, v]))
    u, v = u[fica], v[fica]
    verdade = zona_plantada(u, v)
    colunas = {}
    for nome, medias in MEDIAS.items():
        colunas[nome] = np.array(medias)[verdade] + g.normal(0, RUIDO[nome], len(u))
    x, y = ORIGEM[0] + u, ORIGEM[1] + v
    lon, lat = utm_inversa(x, y, ZONA, SUL)
    # o índice de vegetação vai como raster de 10 m (linha 0 = norte)
    pixel, nx, ny = 10.0, 92, 78
    ru, rv = np.meshgrid((np.arange(nx) + 0.5) * pixel - 10, (ny - np.arange(ny) - 0.5) * pixel - 10)
    indice = np.array(MEDIAS_INDICE)[zona_plantada(ru, rv)] + g.normal(0, RUIDO_INDICE, ru.shape)
    plon, plat = utm_inversa([ORIGEM[0] + p[0] for p in CONTORNO], [ORIGEM[1] + p[1] for p in CONTORNO], ZONA, SUL)
    return {
        'colunas': {'Longitude': np.round(lon, 7), 'Latitude': np.round(lat, 7),
                    'argila_g_kg': np.round(colunas['argila_g_kg'], 1), 'prod_t_ha': np.round(colunas['prod_t_ha'], 3),
                    'altitude_m': np.round(colunas['altitude_m'], 2)},
        'verdade': verdade, 'x': x, 'y': y, 'perimetro': list(zip(plon.tolist(), plat.tolist())),
        'perimetro_utm': [(ORIGEM[0] + p[0], ORIGEM[1] + p[1]) for p in CONTORNO],
        'raster': {'dados': indice, 'x_oeste': ORIGEM[0] - 10, 'y_norte': ORIGEM[1] - 10 + ny * pixel, 'pixel': pixel,
                   'epsg': 31960 + ZONA},
    }


def gravar_csv(caminho, exemplo):
    nomes = list(exemplo['colunas'])
    with open(caminho, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(nomes)
        w.writerows(zip(*(exemplo['colunas'][n].tolist() for n in nomes)))


def gravar_perimetro(caminho, exemplo):
    anel = [list(p) for p in exemplo['perimetro']]
    anel.append(anel[0])
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump({'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'properties': {'talhao': 'Exemplo'},
             'geometry': {'type': 'Polygon', 'coordinates': [anel]}}]}, f)


def gravar_raster(caminho, exemplo):
    from geotiff import escrever_geotiff

    r = exemplo['raster']
    escrever_geotiff(caminho, r['dados'], r['x_oeste'], r['y_norte'], r['pixel'], r['epsg'])


def acerto(previsto, verdade):
    """Fração de pontos na zona certa, depois de casar cada zona prevista com a plantada que mais
    coincide com ela (os números das zonas não precisam ser os mesmos)."""
    previsto, verdade = np.asarray(previsto), np.asarray(verdade)
    certos = 0
    for c in np.unique(previsto):
        da_zona = verdade[previsto == c]
        certos += np.bincount(da_zona).max()
    return certos / len(verdade)


if __name__ == '__main__':
    ex = talhao()
    n = len(ex['verdade'])
    assert 1000 < n < 1500, n
    partes = np.bincount(ex['verdade']) / n
    assert all(0.2 < p < 0.5 for p in partes), partes
    assert abs(ex['colunas']['argila_g_kg'][ex['verdade'] == 2].mean() - 450) < 10
    # ponto a ponto as zonas se misturam: pela argila sozinha, um em cada sete ou oito pontos cai fora
    limites = np.searchsorted([255, 385], ex['colunas']['argila_g_kg'])
    assert 0.80 < acerto(limites, ex['verdade']) < 0.95, acerto(limites, ex['verdade'])
    assert acerto(ex['verdade'], ex['verdade']) == 1.0 and ex['raster']['dados'].shape == (78, 92)
    assert math.isclose(ex['raster']['y_norte'], ORIGEM[1] + 770)
    print('sintetico OK ·', n, 'pontos · zonas plantadas:', [round(float(p), 2) for p in partes])
