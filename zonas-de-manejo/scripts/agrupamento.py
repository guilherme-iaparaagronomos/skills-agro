"""Do conjunto de pontos com camadas até a classe de cada ponto.

  padronizar()            cada camada em média 0 e desvio 1, com peso opcional
  pca()                   componentes principais até a variância pedida
  kmeans()                K-Means (início k-means++, várias partidas)
  silhueta()              quão separados ficaram os grupos (de -1 a 1)
  escolher_k()            a silhueta de cada número de grupos
  tamanho_minimo()        classe com poucos pontos é absorvida pelas vizinhas
  refinar_fragmentos()    pedaço pequeno e solto de uma classe passa para a vizinha
  reducao_de_variancia()  quanto as zonas explicam de uma camada

Só numpy e scipy. Tudo é reprodutível: a mesma semente dá o mesmo resultado.

Teste embutido: python scripts/agrupamento.py
"""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

PADRAO = {'variancia_pca': 0.90, 'k_min': 2, 'k_max': 8, 'area_minima': 0.10, 'vizinhos': 8,
          'frag_total': 0.03, 'frag_classe': 0.20, 'max_iter': 10, 'semente': 0}


def padronizar(X, pesos=None):
    """(Z, média, desvio): cada coluna com média 0 e desvio 1, multiplicada pelo peso dela."""
    X = np.asarray(X, float)
    media, desvio = X.mean(axis=0), X.std(axis=0)
    desvio = np.where(desvio == 0, 1.0, desvio)
    Z = (X - media) / desvio
    if pesos is not None:
        Z = Z * np.asarray(pesos, float)
    return Z, media, desvio


def pca(Z, variancia=0.90):
    """Componentes principais de Z (já padronizado) até somar `variancia` da variância total.
    Devolve dict: escores [n, m], explicada (todas), componentes (m), cargas [colunas, m]."""
    Z = np.asarray(Z, float)
    centro = Z - Z.mean(axis=0)
    _, s, vt = np.linalg.svd(centro, full_matrices=False)
    explicada = s**2 / max(float((s**2).sum()), 1e-300)
    m = int(np.searchsorted(np.cumsum(explicada), variancia - 1e-12) + 1)
    m = max(1, min(m, len(s)))
    # sinal fixo: a maior carga de cada componente fica positiva (resultado igual entre máquinas)
    for i in range(len(vt)):
        if vt[i, np.argmax(np.abs(vt[i]))] < 0:
            vt[i] = -vt[i]
    return {'escores': centro @ vt[:m].T, 'explicada': explicada.tolist(), 'componentes': m, 'cargas': vt[:m].T}


def _distancias2(X, C):
    return np.maximum((X**2).sum(axis=1)[:, None] - 2 * X @ C.T + (C**2).sum(axis=1)[None, :], 0)


def kmeans(X, k, semente=0, partidas=5, max_iter=300):
    """K-Means com início k-means++ e `partidas` tentativas; fica a de menor inércia.
    Devolve (rótulos, centros, inércia)."""
    X = np.asarray(X, float)
    n = len(X)
    if k < 1 or k > n:
        raise ValueError(f'k = {k} não serve para {n} pontos')
    gerador = np.random.default_rng(semente)
    melhor = None
    for _ in range(partidas):
        centros = [X[gerador.integers(n)]]
        d2 = _distancias2(X, np.array(centros))[:, 0]
        for _ in range(1, k):
            total = d2.sum()
            escolhido = gerador.choice(n, p=d2 / total) if total > 0 else gerador.integers(n)
            centros.append(X[escolhido])
            d2 = np.minimum(d2, _distancias2(X, X[escolhido][None, :])[:, 0])
        C = np.array(centros)
        rotulos = None
        for _ in range(max_iter):
            D = _distancias2(X, C)
            novos = D.argmin(axis=1)
            if rotulos is not None and np.array_equal(novos, rotulos):
                break
            rotulos = novos
            for j in range(k):
                do_grupo = rotulos == j
                if do_grupo.any():
                    C[j] = X[do_grupo].mean(axis=0)
                else:  # grupo vazio: recomeça no ponto mais longe do centro dele
                    C[j] = X[D.min(axis=1).argmax()]
        inercia = float(_distancias2(X, C)[np.arange(n), rotulos].sum())
        if melhor is None or inercia < melhor[2]:
            melhor = (rotulos.copy(), C.copy(), inercia)
    return melhor


def silhueta(X, rotulos, amostra=4000, semente=0):
    """Silhueta média (de -1 a 1; perto de 0 = grupos encostados). Em conjunto grande, numa amostra."""
    X, rotulos = np.asarray(X, float), np.asarray(rotulos)
    classes = np.unique(rotulos)
    if len(classes) < 2:
        return float('nan')
    if len(X) > amostra:
        escolha = np.random.default_rng(semente).choice(len(X), amostra, replace=False)
        X, rotulos = X[escolha], rotulos[escolha]
        classes = np.unique(rotulos)
        if len(classes) < 2:
            return float('nan')
    D = np.sqrt(_distancias2(X, X))
    n = len(X)
    medias = np.zeros((n, len(classes)))
    tamanhos = np.zeros(len(classes))
    for j, c in enumerate(classes):
        da_classe = rotulos == c
        tamanhos[j] = da_classe.sum()
        medias[:, j] = D[:, da_classe].sum(axis=1)
    posicao = np.searchsorted(classes, rotulos)
    propria = tamanhos[posicao]
    a = medias[np.arange(n), posicao] / np.maximum(propria - 1, 1)
    outras = medias / tamanhos[None, :]
    outras[np.arange(n), posicao] = np.inf
    b = outras.min(axis=1)
    s = np.where(propria > 1, (b - a) / np.maximum(np.maximum(a, b), 1e-300), 0.0)
    return float(s.mean())


def escolher_k(X, k_min=2, k_max=8, semente=0):
    """Roda o K-Means de k_min a k_max. Devolve [{k, silhueta, inercia, rotulos}]."""
    tabela = []
    for k in range(k_min, min(k_max, len(X) - 1) + 1):
        rotulos, _, inercia = kmeans(X, k, semente)
        tabela.append({'k': k, 'silhueta': silhueta(X, rotulos, semente=semente), 'inercia': inercia,
                       'rotulos': rotulos})
    return tabela


def _vizinhos(xy, quantos):
    """Índices dos `quantos` pontos mais próximos de cada ponto (o próprio ponto vem na lista)."""
    quantos = min(quantos, len(xy))
    _, indices = cKDTree(xy).query(xy, k=quantos)
    return indices.reshape(len(xy), -1)


def _destino(rotulos, indices, pontos, classe):
    """A classe mais comum entre os vizinhos dos `pontos`, fora a própria; a maior classe se não houver."""
    ao_redor = rotulos[indices[pontos]].ravel()
    ao_redor = ao_redor[ao_redor != classe]
    if ao_redor.size:
        valores, vezes = np.unique(ao_redor, return_counts=True)
        return valores[np.argmax(vezes)]
    valores, vezes = np.unique(rotulos[rotulos != classe], return_counts=True)
    return valores[np.argmax(vezes)] if len(valores) else classe


def tamanho_minimo(xy, rotulos, min_pontos, vizinhos=8):
    """Classe com menos de `min_pontos` pontos é absorvida pela classe mais comum ao redor dela."""
    rotulos = np.array(rotulos).copy()
    indices = _vizinhos(np.asarray(xy, float), vizinhos)
    for _ in range(100):
        classes, vezes = np.unique(rotulos, return_counts=True)
        pequenas = [c for c, n in zip(classes, vezes) if n < min_pontos]
        if not pequenas or len(classes) <= 1:
            break
        for c in pequenas:
            pontos = np.flatnonzero(rotulos == c)
            if len(pontos) and len(np.unique(rotulos)) > 1:
                rotulos[pontos] = _destino(rotulos, indices, pontos, c)
    return rotulos


def refinar_fragmentos(xy, rotulos, vizinhos=8, frag_total=0.03, frag_classe=0.20, max_iter=10):
    """Um fragmento é um pedaço de uma classe sem ligação (por vizinhança) com o resto dela. O
    fragmento com menos de `frag_total` de todos os pontos E menos de `frag_classe` dos pontos da
    classe passa para a classe mais comum ao redor. Devolve (rótulos, fragmentos reatribuídos)."""
    xy = np.asarray(xy, float)
    rotulos = np.array(rotulos).copy()
    n = len(rotulos)
    indices = _vizinhos(xy, vizinhos)
    de = np.repeat(np.arange(n), indices.shape[1])
    para = indices.ravel()
    trocados = 0
    for _ in range(max_iter):
        liga = (de != para) & (rotulos[de] == rotulos[para])
        grafo = coo_matrix((np.ones(int(liga.sum()), dtype=np.int8), (de[liga], para[liga])), shape=(n, n))
        _, componente = connected_components(grafo, directed=False)
        tamanho_do_componente = np.bincount(componente)
        classes, vezes = np.unique(rotulos, return_counts=True)
        tamanho_da_classe = dict(zip(classes.tolist(), vezes.tolist()))
        # um componente tem uma classe só; basta olhar um ponto de cada
        _, primeiro = np.unique(componente, return_index=True)
        fragmentos = [(componente[i], rotulos[i]) for i in primeiro
                      if tamanho_do_componente[componente[i]] / n < frag_total
                      and tamanho_do_componente[componente[i]] / tamanho_da_classe[int(rotulos[i])] < frag_classe]
        if not fragmentos:
            break
        mudou = False
        for comp, classe in fragmentos:
            pontos = np.flatnonzero(componente == comp)
            destino = _destino(rotulos, indices, pontos, classe)
            if destino != classe:
                rotulos[pontos] = destino
                mudou = True
                trocados += 1
        if not mudou:
            break
    return rotulos, trocados


def reducao_de_variancia(valores, rotulos):
    """1 − (variância dentro das zonas ÷ variância total), de 0 a 1: quanto da variação da camada
    as zonas explicam. 0 = as zonas não separam nada; 1 = cada zona é uniforme."""
    v, rotulos = np.asarray(valores, float), np.asarray(rotulos)
    bons = np.isfinite(v)
    v, rotulos = v[bons], rotulos[bons]
    total = float(((v - v.mean()) ** 2).sum()) if len(v) else 0.0
    if total <= 0:
        return float('nan')
    dentro = sum(float(((v[rotulos == c] - v[rotulos == c].mean()) ** 2).sum()) for c in np.unique(rotulos))
    return 1 - dentro / total


if __name__ == '__main__':
    g = np.random.default_rng(4)
    # três grupos bem separados em 4 camadas (duas delas quase iguais) e uma de ruído
    centros = np.array([[0, 0, 0], [5, 5, 1], [10, 0, 5]], float)
    verdade = np.repeat([0, 1, 2], 300)
    base = centros[verdade] + g.normal(0, 0.6, (900, 3))
    X = np.column_stack([base[:, 0], base[:, 0] * 2 + g.normal(0, 0.1, 900), base[:, 1], base[:, 2], g.normal(0, 1, 900)])
    Z, media, desvio = padronizar(X)
    assert np.allclose(Z.mean(axis=0), 0) and np.allclose(Z.std(axis=0), 1)
    assert np.allclose(padronizar(X, [1, 1, 2, 1, 1])[0][:, 2], Z[:, 2] * 2)
    p = pca(Z, 0.90)
    assert 2 <= p['componentes'] <= 4 and abs(sum(p['explicada']) - 1) < 1e-9 and p['escores'].shape == (900, p['componentes'])
    assert pca(Z, 0.999)['componentes'] >= p['componentes']
    rot, C, inercia = kmeans(p['escores'], 3)
    acerto = max(np.mean(np.array(perm)[rot] == verdade) for perm in
                 ([0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]))
    assert acerto > 0.97, acerto
    assert np.array_equal(kmeans(p['escores'], 3)[0], rot), 'a mesma semente tem de dar o mesmo resultado'
    tabela = escolher_k(p['escores'], 2, 6)
    assert max(tabela, key=lambda t: t['silhueta'])['k'] == 3, [(t['k'], round(t['silhueta'], 3)) for t in tabela]
    assert 0.4 < silhueta(p['escores'], rot) <= 1 and np.isnan(silhueta(p['escores'], np.zeros(900, int)))
    assert reducao_de_variancia(X[:, 0], rot) > 0.9 and reducao_de_variancia(X[:, 4], rot) < 0.05

    # no espaço: grade de 30 × 30 com duas metades, uma ilha de 6 pontos e uma classe de 9 pontos
    gx, gy = np.meshgrid(np.arange(30.0), np.arange(30.0))
    xy = np.column_stack([gx.ravel(), gy.ravel()])
    classes = (xy[:, 0] >= 15).astype(int)
    ilha = (xy[:, 0] >= 4) & (xy[:, 0] <= 6) & (xy[:, 1] >= 10) & (xy[:, 1] <= 11)
    classes[ilha] = 1
    canto = (xy[:, 0] >= 27) & (xy[:, 1] >= 27)
    classes[canto] = 2
    limpo = tamanho_minimo(xy, classes, min_pontos=90)
    assert set(np.unique(limpo)) == {0, 1} and (limpo[canto] == 1).all()
    refinado, trocados = refinar_fragmentos(xy, limpo)
    assert trocados == 1 and (refinado[ilha] == 0).all() and (refinado == (xy[:, 0] >= 15)).all()
    # fragmento grande (mais de 3% do total) fica
    bloco = (xy[:, 0] <= 6) & (xy[:, 1] <= 6)
    com_bloco = (xy[:, 0] >= 15).astype(int)
    com_bloco[bloco] = 1
    assert (refinar_fragmentos(xy, com_bloco)[0][bloco] == 1).all()
    print('agrupamento OK')
