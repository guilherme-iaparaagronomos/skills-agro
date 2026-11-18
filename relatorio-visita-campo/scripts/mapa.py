"""Prepara o mapa da localização da visita: o quadro, a imagem de satélite em
cor natural (e o NDVI, se houver), o contorno do perímetro e a posição das
paradas.

A imagem de satélite é o GeoTIFF que a ferramenta `imagem_satelite` da ClaudIA
Sat devolve. Sem ela, o mapa sai só com o contorno e as paradas; sem contorno
e sem parada, não há mapa.

Teste embutido: python scripts/mapa.py
"""

import math

import numpy as np
from PIL import Image

import geometria as G

CORES_NDVI = ['#a50026', '#f98e52', '#feffbe', '#84ca66', '#006837']
GAMA = 0.8
REFLECTANCIA_MAXIMA = 20000
LADO_DA_IMAGEM = 1000
BARRAS = [20, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 50000]


class MapaInvalido(Exception):
    """A imagem ou o perímetro não puderam ser usados. A mensagem diz por quê."""


def _zona(lon):
    return int((lon + 180.0) // 6) + 1


def cor_natural(bandas):
    """(altura, largura, 3) em refletância → imagem do Pillow. O mesmo esticamento nas três cores (2 a 98% de todos os
    pixels válidos) e gama 0,8; fora da área fica branco."""
    d = np.asarray(bandas, dtype=float).copy()
    fundo = ~np.isfinite(d).all(axis=2)
    d[fundo] = 0
    d[d > REFLECTANCIA_MAXIMA] = 0
    fundo |= d.sum(axis=2) == 0
    saida = np.full(d.shape, 255, dtype=np.uint8)
    validos = d[~fundo]
    if validos.size:
        lo, hi = np.percentile(validos, [2, 98])
        if hi > lo:
            esticado = np.clip((d - lo) / (hi - lo), 0, 1) ** GAMA
            saida[~fundo] = (esticado[~fundo] * 255).astype(np.uint8)
    return Image.fromarray(saida), fundo


def faixas_do_ndvi(dados):
    """Imagem do NDVI em 5 faixas de mesma área (quintis) e os limites de cada faixa."""
    d = np.asarray(dados, dtype=float)
    valido = np.isfinite(d) & (d >= -1.0) & (d <= 1.0)
    if not valido.any():
        raise MapaInvalido('a imagem de NDVI não tem nenhum pixel com valor')
    cortes = np.percentile(d[valido], [0, 20, 40, 60, 80, 100])
    saida = np.full(d.shape + (3,), 255, dtype=np.uint8)
    classe = np.clip(np.searchsorted(cortes[1:-1], d, side='right'), 0, 4)
    for k, cor in enumerate(CORES_NDVI):
        saida[valido & (classe == k)] = [int(cor[i:i + 2], 16) for i in (1, 3, 5)]
    limites = [(float(cortes[k]), float(cortes[k + 1])) for k in range(5)]
    return Image.fromarray(saida), limites


def _ampliar(im):
    fator = max(1, LADO_DA_IMAGEM // max(im.size))
    return im.resize((im.size[0] * fator, im.size[1] * fator), Image.NEAREST) if fator > 1 else im


def _ler_raster(caminho, bandas):
    import geotiff
    try:
        lidas = [geotiff.ler_geotiff(str(caminho), b) for b in bandas]
    except ValueError as e:
        raise MapaInvalido(f'{caminho.name}: {e}')
    r = lidas[0]
    if r['crs'] != 'utm':
        raise MapaInvalido(f'{caminho.name}: a imagem não está em UTM. Use o arquivo que a ferramenta de satélite devolveu')
    return r, np.dstack([x['dados'] for x in lidas])


def _barra(largura_m):
    alvo = largura_m * 0.28
    return max((b for b in BARRAS if b <= alvo), default=BARRAS[0])


def preparar(v):
    """Devolve o mapa pronto para desenhar, ou None quando a visita não tem localização nenhuma.

    {'quadro': (oeste, sul, leste, norte) em metros, 'proporcao': largura/altura, 'cor': imagem ou None,
     'ndvi': imagem ou None, 'limites_ndvi': [...], 'aneis': [[(u, v)]], 'paradas': [(n, u, v)],
     'fora': [(n, distância em metros)], 'barra_m': comprimento da barra de escala}
    u e v vão de 0 a 1 dentro do quadro (u para leste, v para norte)."""
    sat, paradas = v.get('satelite'), v.get('paradas') or []
    aneis_geo = []
    if v.get('perimetro'):
        try:
            aneis, crs, zona_p = G.ler_perimetro(str(v['perimetro']))
        except Exception as e:
            raise MapaInvalido(f'perímetro {v["perimetro"].name}: {e}')
        if crs != 'geo':
            raise MapaInvalido(f'perímetro {v["perimetro"].name}: as coordenadas estão em metros. Envie em graus (GeoJSON ou KML)')
        aneis_geo = aneis
    if not sat and not paradas and not aneis_geo:
        return None

    cor = ndvi = limites = None
    if sat:
        base = sat['rgb'] or sat['ndvi']
        r, _ = _ler_raster(base, [1])
        zona, sul = r['zona'], r['sul']
        quadro = (r['x0'], r['y0'] - r['altura'] * r['dy'], r['x0'] + r['largura'] * r['dx'], r['y0'])
        if sat['rgb']:
            rr, pilha = _ler_raster(sat['rgb'], [1, 2, 3] if r['bandas'] >= 3 else [1, 1, 1])
            cor = _ampliar(cor_natural(pilha)[0])
        if sat['ndvi']:
            rn, banda = _ler_raster(sat['ndvi'], [1])
            if (rn['x0'], rn['y0'], rn['largura'], rn['altura']) != (r['x0'], r['y0'], r['largura'], r['altura']):
                raise MapaInvalido('a imagem de NDVI e a de cor natural não cobrem o mesmo quadro: peça as duas na mesma chamada')
            imagem, limites = faixas_do_ndvi(banda[:, :, 0])
            ndvi = _ampliar(imagem)
    else:
        lons = [p[0] for a in aneis_geo for p in a] + [p['lon'] for p in paradas]
        lats = [p[1] for a in aneis_geo for p in a] + [p['lat'] for p in paradas]
        zona, sul = _zona(sum(lons) / len(lons)), (sum(lats) / len(lats)) < 0
        xs, ys = G.utm_direta(np.array(lons), np.array(lats), zona, sul)
        oeste, leste, baixo, cima = float(xs.min()), float(xs.max()), float(ys.min()), float(ys.max())
        folga = max(0.12 * max(leste - oeste, cima - baixo), 150.0)
        quadro = [oeste - folga, baixo - folga, leste + folga, cima + folga]
        largura, altura = quadro[2] - quadro[0], quadro[3] - quadro[1]
        if largura / altura > 2.0:                      # o cartão do mapa não fica nem fita nem torre
            falta = largura / 2.0 - altura
            quadro[1] -= falta / 2
            quadro[3] += falta / 2
        elif largura / altura < 0.8:
            falta = altura * 0.8 - largura
            quadro[0] -= falta / 2
            quadro[2] += falta / 2
        quadro = tuple(quadro)

    oeste, baixo, leste, cima = quadro
    largura, altura = leste - oeste, cima - baixo

    def uv(lon, lat):
        x, y = G.utm_direta(np.array([lon]), np.array([lat]), zona, sul)
        return (float(x[0]) - oeste) / largura, (float(y[0]) - baixo) / altura

    aneis = [[uv(lon, lat) for lon, lat in anel] for anel in aneis_geo]
    dentro, fora = [], []
    for p in paradas:
        u, w = uv(p['lon'], p['lat'])
        if -0.02 <= u <= 1.02 and -0.02 <= w <= 1.02:
            dentro.append((p['n'], min(1.0, max(0.0, u)), min(1.0, max(0.0, w))))
        else:
            dx = max(0.0, -u, u - 1.0) * largura
            dy = max(0.0, -w, w - 1.0) * altura
            fora.append((p['n'], math.hypot(dx, dy)))
    return {'quadro': quadro, 'proporcao': largura / altura, 'cor': cor, 'ndvi': ndvi, 'limites_ndvi': limites, 'aneis': aneis,
            'paradas': dentro, 'fora': fora, 'barra_m': _barra(largura), 'largura_m': largura}


def distancia_txt(metros):
    if metros < 1000:
        return f'{int(round(metros / 10.0) * 10)} m'
    return f'{metros / 1000.0:.1f} km'.replace('.', ',')


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    import tempfile
    from pathlib import Path

    import sintetico
    import visita as V
    with tempfile.TemporaryDirectory() as pasta:
        v = V.carregar(sintetico.gravar(pasta))
        m = preparar(v)
        assert m['cor'] is not None and m['ndvi'] is not None and len(m['limites_ndvi']) == 5
        assert m['quadro'] == (sintetico.X0, sintetico.Y0 - 1300.0, sintetico.X0 + 1800.0, sintetico.Y0)
        assert abs(m['proporcao'] - 1800.0 / 1300.0) < 1e-9 and m['barra_m'] == 500
        assert max(m['cor'].size) >= 900 and m['cor'].size == m['ndvi'].size
        assert len(m['aneis']) == 2 and all(0 <= u <= 1 and 0 <= w <= 1 for a in m['aneis'] for u, w in a)
        assert [n for n, _, _ in m['paradas']] == [1, 2, 3] and not m['fora'], (m['paradas'], m['fora'])
        assert m['limites_ndvi'][0][0] < m['limites_ndvi'][4][1]
        branco = np.asarray(m['cor'])[0, 0]
        assert tuple(branco) == (255, 255, 255), 'fora da área a imagem fica branca'

        # sem satélite: o quadro sai do perímetro e das paradas
        sem = dict(v, satelite=None)
        m2 = preparar(sem)
        assert m2['cor'] is None and len(m2['paradas']) == 3 and 0.8 <= m2['proporcao'] <= 2.0
        # só paradas, uma delas longe: fica fora só quando há imagem
        so = dict(v, perimetro=None, paradas=v['paradas'] + [{'n': 9, 'lat': -22.60, 'lon': -50.99, 'hora': None, 'nome': None, 'origem': 'x'}])
        m3 = preparar(so)
        assert [n for n, _ in m3['fora']] == [9] and m3['fora'][0][1] > 9000 and distancia_txt(m3['fora'][0][1]).endswith('km')
        assert preparar(dict(v, satelite=None, perimetro=None, paradas=[])) is None
        # imagem que não é GeoTIFF e perímetro em metros: recusa com motivo
        ruim = Path(pasta) / 'ruim.tif'
        ruim.write_bytes(b'nao e tiff')
        for troca, trecho in ((dict(v, satelite=dict(v['satelite'], rgb=ruim, ndvi=None)), 'ruim.tif'),):
            try:
                preparar(troca)
            except MapaInvalido as e:
                assert trecho in str(e)
            else:
                raise AssertionError('devia recusar')
    im, fundo = cor_natural(np.dstack([np.full((4, 4), 500.0), np.full((4, 4), 800.0), np.full((4, 4), 300.0)]))
    assert im.size == (4, 4) and not fundo.any()
    assert distancia_txt(840) == '840 m' and distancia_txt(2400) == '2,4 km'
    print('mapa.py: autoteste ok (imagem em cor natural e NDVI, perímetro e paradas no quadro, sem satélite, parada fora)')


if __name__ == '__main__':
    _autoteste()
