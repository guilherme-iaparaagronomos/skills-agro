"""A grade fina sobre o perímetro: cada célula recebe a classe do ponto mais próximo.

É o equivalente, em grade, de desenhar o polígono de influência de cada ponto
(Voronoi) e juntar os de mesma classe. Depois disso, a parte de zona menor que
a área mínima é fundida à vizinha com quem divide a maior divisa.

  pixel_automatico()        tamanho da célula, pelo espaçamento dos pontos e pela área
  montar_grade()            a grade e a máscara do que está dentro do perímetro
  classes_em_grade()        a classe de cada célula (o ponto mais próximo)
  partes()                  os pedaços contíguos de cada classe
  fundir_partes_pequenas()  funde os pedaços abaixo do mínimo

Teste embutido: python scripts/grade.py
"""

import math

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from areas import dentro

TETO_DE_CELULAS = 1_500_000
PIXELS = (0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100)


def pixel_automatico(area_m2, espacamento):
    """Célula de um quarto do espaçamento dos pontos, sem passar de TETO_DE_CELULAS dentro da área."""
    alvo = max(espacamento / 4, math.sqrt(area_m2 / TETO_DE_CELULAS), PIXELS[0])
    return next((p for p in PIXELS if p >= alvo), PIXELS[-1])


def montar_grade(areas, pixel, folga=1):
    """Grade alinhada a múltiplos do pixel. Devolve dict: x0, y0 (canto superior esquerdo), pixel,
    nx, ny, mascara [ny, nx] (o centro da célula cai dentro de alguma área)."""
    xs = [p[0] for a in areas for anel in a['aneis'] for p in anel]
    ys = [p[1] for a in areas for anel in a['aneis'] for p in anel]
    x0 = math.floor(min(xs) / pixel) * pixel - folga * pixel
    y0 = math.ceil(max(ys) / pixel) * pixel + folga * pixel
    nx = int(math.ceil((max(xs) - x0) / pixel)) + folga
    ny = int(math.ceil((y0 - min(ys)) / pixel)) + folga
    cx = x0 + (np.arange(nx) + 0.5) * pixel
    cy = y0 - (np.arange(ny) + 0.5) * pixel
    gx, gy = np.meshgrid(cx, cy)
    centros = np.column_stack([gx.ravel(), gy.ravel()])
    mascara = np.zeros(nx * ny, dtype=bool)
    for a in areas:
        mascara |= dentro(a['aneis'], centros)
    return {'x0': x0, 'y0': y0, 'pixel': pixel, 'nx': nx, 'ny': ny, 'mascara': mascara.reshape(ny, nx)}


def centros_da_grade(g):
    """Coordenadas (x, y) dos centros das células de dentro, na ordem de np.nonzero(mascara)."""
    linhas, colunas = np.nonzero(g['mascara'])
    return np.column_stack([g['x0'] + (colunas + 0.5) * g['pixel'], g['y0'] - (linhas + 0.5) * g['pixel']])


def classes_em_grade(g, xy, rotulos):
    """Cada célula de dentro recebe a classe do ponto mais próximo; fora fica -1."""
    L = np.full((g['ny'], g['nx']), -1, dtype=np.int32)
    _, mais_perto = cKDTree(np.asarray(xy, float)).query(centros_da_grade(g))
    L[g['mascara']] = np.asarray(rotulos)[mais_perto]
    return L


def partes(L):
    """Pedaços contíguos (vizinhança de 4) de cada classe. Devolve (grade de ids começando em 1,
    0 fora; classe de cada id; células de cada id), os dois últimos com o índice 0 sem uso."""
    ids = np.zeros(L.shape, dtype=np.int32)
    classe, proximo = [-1], 1
    for c in np.unique(L[L >= 0]):
        marcado, n = ndimage.label(L == c)
        ids[marcado > 0] = marcado[marcado > 0] + proximo - 1
        classe += [int(c)] * n
        proximo += n
    return ids, np.array(classe), np.bincount(ids.ravel(), minlength=proximo)


def _divisas(ids):
    """{(a, b): quantos lados de célula a parte a divide com a parte b}, nos dois sentidos."""
    pares = []
    for a, b in ((ids[:, :-1], ids[:, 1:]), (ids[:-1, :], ids[1:, :])):
        diferente = (a != b) & (a > 0) & (b > 0)
        pares.append(np.column_stack([a[diferente], b[diferente]]))
    pares = np.vstack(pares)
    if not len(pares):
        return {}
    pares = np.vstack([pares, pares[:, ::-1]])
    unicos, vezes = np.unique(pares, axis=0, return_counts=True)
    return {(int(a), int(b)): int(n) for (a, b), n in zip(unicos, vezes)}


def fundir_partes_pequenas(L, min_celulas, max_passadas=60):
    """Parte de zona com menos de `min_celulas` células é fundida à parte vizinha com quem divide a
    maior divisa (e fica com a classe dela). Da menor para a maior, até não sobrar parte pequena
    com vizinha. Parte pequena ISOLADA (um bloco separado do resto, sem vizinha) fica como está:
    não há com quem fundir. Devolve (grade, quantas fusões)."""
    L = L.copy()
    fusoes = 0
    for _ in range(max_passadas):
        ids, classe, tamanho = partes(L)
        n = len(classe) - 1
        pequenas = [i for i in np.argsort(tamanho[1:], kind='stable') + 1 if tamanho[i] < min_celulas]
        if not pequenas or n <= 1:
            break
        divisas = _divisas(ids)
        vizinhas = {}
        for (a, b), comprimento in divisas.items():
            vizinhas.setdefault(a, []).append((comprimento, b))
        mexidas, mudou = set(), False
        for i in pequenas:
            if i in mexidas:
                continue
            candidatas = [(c, b) for c, b in vizinhas.get(i, []) if b not in mexidas]
            if not candidatas:
                continue
            alvo = max(candidatas)[1]
            L[ids == i] = classe[alvo]
            mexidas.update((i, alvo))  # a que recebeu cresceu: só volta a ser olhada na próxima passada
            fusoes += 1
            mudou = True
        if not mudou:
            break
    return L, fusoes


if __name__ == '__main__':
    assert pixel_automatico(100 * 10000, 20) == 5 and pixel_automatico(5000 * 10000, 20) == 10
    assert pixel_automatico(10 * 10000, 3) == 1
    quadrado = [{'nome': 'T1', 'aneis': [[(1000, 2000), (1400, 2000), (1400, 2300), (1000, 2300)]]}]
    g = montar_grade(quadrado, 10)
    assert g['mascara'].sum() == 40 * 30 and (g['nx'], g['ny']) == (42, 32), (g['mascara'].sum(), g['nx'], g['ny'])
    assert g['x0'] == 990 and g['y0'] == 2310
    c = centros_da_grade(g)
    assert c[0].tolist() == [1005.0, 2295.0] and len(c) == 1200

    # dois pontos: metade esquerda de uma classe, metade direita de outra
    L = classes_em_grade(g, [(1100, 2150), (1300, 2150)], [0, 1])
    assert (L == 0).sum() == 600 and (L == 1).sum() == 600 and (L == -1).sum() == 42 * 32 - 1200
    ids, classe, tamanho = partes(L)
    assert classe.tolist() == [-1, 0, 1] and tamanho[1:].tolist() == [600, 600]
    assert _divisas(ids) == {(1, 2): 30, (2, 1): 30}

    # ilha de 12 células da classe 1 dentro da 0, e uma tira da classe 2 encostada na 1
    M = L.copy()
    M[10:13, 5:9] = 1
    M[1:4, 35:41] = 2
    ids, classe, tamanho = partes(M)
    assert sorted(tamanho[1:].tolist()) == [12, 18, 582, 588]
    F, fusoes = fundir_partes_pequenas(M, min_celulas=50)
    assert fusoes == 2 and (F[10:13, 5:9] == 0).all() and (F[1:4, 35:41] == 1).all()
    assert np.array_equal(F, L)
    # nada pequeno: nada muda
    assert fundir_partes_pequenas(L, 50)[1] == 0
    # uma classe só: não tem para onde fundir
    U = np.where(L >= 0, 0, -1)
    assert fundir_partes_pequenas(U, 5000)[1] == 0
    # bloco pequeno e separado do resto (sem vizinha) fica com a classe que tem
    B = np.full((10, 30), -1, dtype=np.int32)
    B[:, :20] = 0
    B[2:5, 25:28] = 1
    FB, fusoes = fundir_partes_pequenas(B, 50)
    assert fusoes == 0 and (FB[2:5, 25:28] == 1).all()
    print('grade OK')
