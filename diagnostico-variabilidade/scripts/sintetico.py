"""Talhão inventado, com relações plantadas, para a demonstração e os testes.
Não é dado de fazenda nenhuma.

O que foi plantado:

- a produtividade sobe com a argila e desce com a altitude, e tem ruído próprio
  que se parece entre células vizinhas (como num mapa de verdade);
- o pH não tem relação nenhuma com a produtividade;
- "argila_outra" é quase uma cópia da argila (outra amostragem do mesmo solo);
- "ndvi_mesma_safra" é o índice de vegetação da mesma safra: quase a própria
  produtividade;
- a variedade B (metade leste) produz 0,25 t/ha a mais.

As camadas saem em formatos diferentes de propósito: a produtividade em pontos
(como o monitor de colheita), a argila num raster de 5 m, o pH num de 20 m, as
outras em 10 m, a variedade em polígonos.

Teste embutido: python scripts/sintetico.py
"""

import csv
import json
import math

import numpy as np
from scipy import ndimage

from areas import dentro, utm_inversa
from espacial import campo_suave
from geotiff import escrever_geotiff

ZONA, SUL, EPSG = 22, True, 31982
ORIGEM = (642300.0, 7541800.0)                 # canto do retângulo do talhão, em UTM 22S
CONTORNO = [(0, 40), (520, 0), (900, 180), (860, 620), (420, 760), (60, 560)]   # metros a partir da origem
PASSO = 10.0
NX, NY = 92, 78                                # malha de 10 m que cobre o contorno com folga (começa em −10 m)
PLANTADO = {'argila': 0.45, 'altitude': -0.30, 'variedade_b': 0.25, 'ruido_vizinho': 0.30, 'ruido_solto': 0.12}


def _z(c):
    return (c - c.mean()) / c.std()


def verdade(semente=5):
    """As malhas de 10 m (linha 0 = norte) de todas as camadas, antes de virar arquivo."""
    g = np.random.default_rng(semente)
    forma = (NY, NX)
    u = (np.arange(NX) + 0.5) * PASSO - 10
    v = (NY - np.arange(NY) - 0.5) * PASSO - 10
    uu, vv = np.meshgrid(u, v)
    argila = 380 + 90 * campo_suave(forma, 14, g)
    altitude = 548 + 0.012 * uu - 0.006 * vv + 5.0 * campo_suave(forma, 20, g)
    ph = 5.6 + 0.35 * campo_suave(forma, 10, g)
    argila_outra = 12 + 0.96 * argila + 9 * campo_suave(forma, 2, g)
    leste = (uu >= 450).astype(float)
    prod = (3.6 + PLANTADO['argila'] * _z(argila) + PLANTADO['altitude'] * _z(altitude) + PLANTADO['variedade_b'] * leste
            + PLANTADO['ruido_vizinho'] * campo_suave(forma, 4, g) + PLANTADO['ruido_solto'] * g.standard_normal(forma))
    ndvi = 0.62 + 0.085 * _z(prod) + 0.028 * g.standard_normal(forma)
    return {'u': uu, 'v': vv, 'argila': argila, 'altitude': altitude, 'ph': ph, 'argila_outra': argila_outra, 'prod': prod,
            'ndvi_mesma_safra': np.clip(ndvi, 0.05, 0.95), 'leste': leste, 'gerador': g}


def _no_ponto(malha, u, v):
    """Valor da malha de 10 m no ponto (u, v) em metros locais, por interpolação bilinear."""
    coluna = (np.asarray(u, float) + 10) / PASSO - 0.5
    linha = NY - (np.asarray(v, float) + 10) / PASSO - 0.5
    return ndimage.map_coordinates(malha, [linha, coluna], order=1, mode='nearest')


def _raster(caminho, malha, pixel):
    """Grava a camada num GeoTIFF com outro tamanho de pixel (reamostrando a malha de 10 m)."""
    nx, ny = int(NX * PASSO / pixel), int(NY * PASSO / pixel)
    u = (np.arange(nx) + 0.5) * pixel - 10
    v = (ny - np.arange(ny) - 0.5) * pixel - 10
    uu, vv = np.meshgrid(u, v)
    escrever_geotiff(caminho, _no_ponto(malha, uu, vv), ORIGEM[0] - 10, ORIGEM[1] - 10 + ny * pixel, pixel, EPSG)


def _anel_geo(pontos):
    lon, lat = utm_inversa([ORIGEM[0] + p[0] for p in pontos], [ORIGEM[1] + p[1] for p in pontos], ZONA, SUL)
    anel = [[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]
    return anel + [anel[0]]


def gravar(pasta, semente=5):
    """Grava os arquivos do exemplo na pasta. Devolve dict com os caminhos e os argumentos da linha de comando."""
    from pathlib import Path

    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    t = verdade(semente)
    g = t['gerador']
    _raster(pasta / 'argila_g_kg.tif', t['argila'], 5.0)
    _raster(pasta / 'argila_outra_g_kg.tif', t['argila_outra'], 10.0)
    _raster(pasta / 'altitude_m.tif', t['altitude'], 10.0)
    _raster(pasta / 'ph.tif', t['ph'], 20.0)
    _raster(pasta / 'ndvi_mesma_safra.tif', t['ndvi_mesma_safra'], 10.0)
    # a produtividade em pontos: passadas a cada 8 m, um ponto a cada 5 m, com o GPS tremendo um pouco
    us, vs = np.meshgrid(np.arange(4, 900, 8.0), np.arange(2, 760, 5.0))
    u = us.ravel() + g.uniform(-0.8, 0.8, us.size)
    v = vs.ravel() + g.uniform(-0.8, 0.8, vs.size)
    fica = dentro([CONTORNO], np.column_stack([u, v]))
    u, v = u[fica], v[fica]
    prod = _no_ponto(t['prod'], u, v) + 0.10 * g.standard_normal(len(u))
    lon, lat = utm_inversa(ORIGEM[0] + u, ORIGEM[1] + v, ZONA, SUL)
    with open(pasta / 'colheita_limpa.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Longitude', 'Latitude', 'prod_t_ha', 'id'])
        for k in range(len(u)):
            w.writerow([f'{lon[k]:.7f}'.replace('.', ','), f'{lat[k]:.7f}'.replace('.', ','),
                        f'{prod[k]:.3f}'.replace('.', ','), k + 1])
    (pasta / 'talhao.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'talhao': 'Exemplo'}, 'geometry': {'type': 'Polygon', 'coordinates': [_anel_geo(CONTORNO)]}}]}),
        encoding='utf-8')
    oeste = [(-20, -20), (450, -20), (450, 780), (-20, 780)]
    leste = [(450, -20), (920, -20), (920, 780), (450, 780)]
    (pasta / 'variedades.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'variedade': nome}, 'geometry': {'type': 'Polygon', 'coordinates': [_anel_geo(anel)]}}
        for nome, anel in (('A', oeste), ('B', leste))]}), encoding='utf-8')
    argumentos = ['--perimetro', str(pasta / 'talhao.geojson'), '--pontos', str(pasta / 'colheita_limpa.csv'),
                  '--raster', f'argila={pasta / "argila_g_kg.tif"}', '--raster', f'argila_outra={pasta / "argila_outra_g_kg.tif"}',
                  '--raster', f'altitude={pasta / "altitude_m.tif"}', '--raster', f'ph={pasta / "ph.tif"}',
                  '--raster', f'ndvi_mesma_safra={pasta / "ndvi_mesma_safra.tif"}',
                  '--classes', f'variedade={pasta / "variedades.geojson"}:variedade']
    return {'pasta': pasta, 'argumentos': argumentos, 'pontos': int(len(u)), 'verdade': t}


def _autoteste():
    import tempfile

    from geotiff import ler_geotiff

    a, b = verdade(), verdade()
    assert all(np.array_equal(a[k], b[k]) for k in ('argila', 'prod', 'ph')), 'o exemplo tem de sair sempre igual'
    m = dentro([CONTORNO], np.column_stack([a['u'].ravel(), a['v'].ravel()])).reshape(NY, NX)
    r = lambda x, y: float(np.corrcoef(a[x][m], a[y][m])[0, 1])
    assert r('prod', 'argila') > 0.4 and r('prod', 'altitude') < -0.2, (r('prod', 'argila'), r('prod', 'altitude'))
    assert abs(r('prod', 'ph')) < 0.25 and r('argila', 'argila_outra') > 0.97 and r('prod', 'ndvi_mesma_safra') > 0.9
    with tempfile.TemporaryDirectory() as pasta:
        e = gravar(pasta)
        fino = ler_geotiff(str(e['pasta'] / 'argila_g_kg.tif'))
        assert (fino['dx'], fino['largura'], fino['altura'], fino['epsg']) == (5.0, 184, 156, EPSG)
        assert ler_geotiff(str(e['pasta'] / 'ph.tif'))['dx'] == 20.0
        assert e['pontos'] > 9000 and (e['pasta'] / 'variedades.geojson').stat().st_size > 300
        linha = (e['pasta'] / 'colheita_limpa.csv').read_text(encoding='utf-8').splitlines()[1]
        assert linha.count(';') == 3 and ',' in linha
    assert math.isclose(sum(abs(v) for v in PLANTADO.values()), 1.42)
    print(f'sintetico OK ({int(m.sum())} células no talhão; r plantado: argila {r("prod", "argila"):+.2f}, altitude '
          f'{r("prod", "altitude"):+.2f}, pH {r("prod", "ph"):+.2f})')


if __name__ == '__main__':
    _autoteste()
