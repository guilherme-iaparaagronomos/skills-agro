"""Da grade de classes aos polígonos das zonas, com divisas COMPARTILHADAS.

A divisa entre duas zonas é traçada uma vez só, como um arco entre dois nós
(pontos onde três ou mais zonas se encontram), simplificada e suavizada uma vez,
e usada pelas duas zonas. Assim a suavização não abre fresta nem cria
sobreposição entre vizinhas.

  vetorizar()   grade de classes → {classe: [polígono, …]}, cada polígono com
                o anel externo e os furos, em coordenadas da grade (metros)
  area_ha()     área de um polígono

Teste embutido: python scripts/vetor.py
"""

import math

import numpy as np
from matplotlib.path import Path as Caminho


def _arestas(L):
    """Arestas de divisa, orientadas com a classe à ESQUERDA (anel externo anti-horário no mapa).
    Devolve (classe, outra classe, nó inicial, nó final, grau de cada nó, largura da malha de nós)."""
    ny, nx = L.shape
    P = np.pad(L, 1, constant_values=-1)
    W = nx + 1
    cima, baixo = P[:-1, 1:-1], P[1:, 1:-1]
    ih, jh = np.nonzero(cima != baixo)
    esq, dire = P[1:-1, :-1], P[1:-1, 1:]
    iv, jv = np.nonzero(esq != dire)
    oeste, leste = ih * W + jh, ih * W + jh + 1
    norte, sul = iv * W + jv, (iv + 1) * W + jv
    classe = np.concatenate([baixo[ih, jh], cima[ih, jh], dire[iv, jv], esq[iv, jv]])
    outra = np.concatenate([cima[ih, jh], baixo[ih, jh], esq[iv, jv], dire[iv, jv]])
    inicio = np.concatenate([leste, oeste, norte, sul])
    fim = np.concatenate([oeste, leste, sul, norte])
    grau = np.bincount(np.concatenate([oeste, leste, norte, sul]), minlength=(ny + 1) * W)
    return classe, outra, inicio, fim, grau, W


def _aneis(inicio, fim, W):
    """Encadeia as arestas de UMA classe em anéis fechados. Onde a classe ocupa duas células em
    diagonal, o anel vira à esquerda: as duas células ficam em polígonos separados."""
    m = len(inicio)
    saidas = {}
    for e in range(m):
        saidas.setdefault(int(inicio[e]), []).append(e)
    esquerda = {1: -W, -W: -1, -1: W, W: 1}
    usado = np.zeros(m, dtype=bool)
    aneis = []
    for e0 in range(m):
        if usado[e0]:
            continue
        anel, e = [], e0
        while not usado[e]:
            usado[e] = True
            anel.append(e)
            opcoes = saidas[int(fim[e])]
            if len(opcoes) == 1:
                e = opcoes[0]
                continue
            direcao = int(fim[e] - inicio[e])
            for quero in (esquerda[direcao], direcao, -esquerda[direcao]):
                achada = [x for x in opcoes if int(fim[x] - inicio[x]) == quero]
                if achada:
                    e = achada[0]
                    break
        aneis.append(anel)
    return aneis


def _dividir(anel, inicio):
    """Um anel que passa duas vezes pelo mesmo nó (um "8") vira dois anéis que só se tocam ali."""
    visto = {}
    for k, e in enumerate(anel):
        no = int(inicio[e])
        if no in visto:
            a = visto[no]
            return _dividir(anel[a:k], inicio) + _dividir(anel[:a] + anel[k:], inicio)
        visto[no] = k
    return [anel]


def _simplificar(p, tolerancia):
    """Douglas-Peucker numa linha aberta [n, 2]; as pontas ficam."""
    n = len(p)
    if n < 3 or tolerancia <= 0:
        return p
    fica = np.zeros(n, dtype=bool)
    fica[0] = fica[-1] = True
    pilha = [(0, n - 1)]
    while pilha:
        a, b = pilha.pop()
        if b <= a + 1:
            continue
        trecho = p[a + 1:b]
        base = p[b] - p[a]
        comprimento = math.hypot(base[0], base[1])
        if comprimento == 0:
            distancia = np.hypot(trecho[:, 0] - p[a, 0], trecho[:, 1] - p[a, 1])
        else:
            distancia = np.abs(base[0] * (trecho[:, 1] - p[a, 1]) - base[1] * (trecho[:, 0] - p[a, 0])) / comprimento
        k = int(np.argmax(distancia))
        if distancia[k] > tolerancia:
            fica[a + 1 + k] = True
            pilha += [(a, a + 1 + k), (a + 1 + k, b)]
    return p[fica]


def _chaikin(p, iteracoes, deslocamento, fechado):
    """Corte de cantos de Chaikin. Na linha aberta as pontas ficam onde estão."""
    for _ in range(iteracoes):
        if len(p) < 3:
            break
        a, b = (p, np.roll(p, -1, axis=0)) if fechado else (p[:-1], p[1:])
        q = (1 - deslocamento) * a + deslocamento * b
        r = deslocamento * a + (1 - deslocamento) * b
        meio = np.empty((2 * len(q), 2))
        meio[0::2], meio[1::2] = q, r
        p = meio if fechado else np.vstack([p[:1], meio, p[-1:]])
    return p


def _suavizar(p, fechado, tolerancia, iteracoes, deslocamento):
    if not fechado:
        return _chaikin(_simplificar(p, tolerancia), iteracoes, deslocamento, False)
    if len(p) < 4:
        return p
    longe = int(np.argmax(np.hypot(p[:, 0] - p[0, 0], p[:, 1] - p[0, 1])))
    ida = _simplificar(p[:longe + 1], tolerancia)
    volta = _simplificar(np.vstack([p[longe:], p[:1]]), tolerancia)
    anel = np.vstack([ida[:-1], volta[:-1]])
    if len(anel) < 3:  # o anel é menor que a tolerância: fica como a grade o desenhou
        return p
    return _chaikin(anel, iteracoes, deslocamento, True)


def _area_com_sinal(p):
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def area_ha(poligono):
    """Área do polígono {'externo', 'furos'} em hectares."""
    return (abs(_area_com_sinal(poligono['externo'])) - sum(abs(_area_com_sinal(f)) for f in poligono['furos'])) / 10000


def _encaixar(pontos, perimetro, alcance):
    """O ponto mais próximo de cada ponto sobre o perímetro. Devolve (pontos encaixados, índice do
    segmento, vale?), com `vale` falso onde o perímetro fica a mais de `alcance`."""
    inicio, fim = [], []
    for anel in perimetro:
        a = np.asarray(anel, float)
        if len(a) > 1 and np.allclose(a[0], a[-1]):
            a = a[:-1]
        inicio.append(a)
        fim.append(np.roll(a, -1, axis=0))
    A, B = np.vstack(inicio), np.vstack(fim)
    AB = B - A
    comprimento2 = np.maximum((AB**2).sum(axis=1), 1e-12)
    encaixados = np.empty_like(pontos)
    segmento = np.zeros(len(pontos), dtype=int)
    distancia = np.zeros(len(pontos))
    for k in range(0, len(pontos), 2000):  # em blocos: n pontos × m segmentos
        P = pontos[k:k + 2000, None, :]
        t = np.clip(((P - A) * AB).sum(axis=2) / comprimento2, 0, 1)
        Q = A + t[:, :, None] * AB
        d = np.hypot(P[:, :, 0] - Q[:, :, 0], P[:, :, 1] - Q[:, :, 1])
        melhor = d.argmin(axis=1)
        linhas = np.arange(len(melhor))
        encaixados[k:k + 2000], segmento[k:k + 2000], distancia[k:k + 2000] = Q[linhas, melhor], melhor, d[linhas, melhor]
    # de qual anel é cada segmento, e onde o anel começa na lista corrida
    tamanhos = [len(a) for a in inicio]
    comeco = np.cumsum([0] + tamanhos[:-1])
    anel_do_segmento = np.repeat(np.arange(len(tamanhos)), tamanhos)
    return encaixados, segmento, distancia <= alcance, A, anel_do_segmento, comeco, np.array(tamanhos)


def vetorizar(L, g, tolerancia=0.0, iteracoes=2, deslocamento=0.25, tolerancia_borda=None, perimetro=None):
    """Polígonos de cada classe da grade L (−1 = fora). `tolerancia` (m) simplifica as divisas
    internas antes da suavização de Chaikin. Com `perimetro` (lista de anéis, em metros), a borda
    de fora das zonas é ENCAIXADA no perímetro verdadeiro do talhão, com os cantos dele; sem ele,
    a borda é a da grade, simplificada com `tolerancia_borda` (padrão: 0,75 célula).
    Devolve {classe: [{'externo': [n, 2], 'furos': [[m, 2], …]}, …]}."""
    pixel = g['pixel']
    if tolerancia_borda is None:
        tolerancia_borda = 0.75 * pixel if tolerancia > 0 else 0.0
    classe, outra, inicio, fim, grau, W = _arestas(L)
    juncao = grau >= 3

    def da_grade(nos):
        nos = np.asarray(nos)
        return np.column_stack([g['x0'] + (nos % W) * pixel, g['y0'] - (nos // W) * pixel]).astype(float)

    encaixe = {}
    if perimetro:
        de_fora = (outra < 0) & (classe >= 0)
        nos_da_borda = np.unique(np.concatenate([inicio[de_fora], fim[de_fora]]))
        if len(nos_da_borda):
            Q, segmento, vale, vertices, anel_do_segmento, comeco, tamanhos = _encaixar(da_grade(nos_da_borda), perimetro,
                                                                                        1.5 * pixel)
            encaixe = {int(no): (Q[i], int(segmento[i])) for i, no in enumerate(nos_da_borda) if vale[i]}

    def coordenadas(nos):
        pontos = da_grade(nos)
        for i, no in enumerate(nos):
            if no in encaixe:
                pontos[i] = encaixe[no][0]
        return pontos

    def pela_borda(nos, fechado):
        """O arco de borda sobre o perímetro verdadeiro, com os vértices dele entre um nó e o seguinte."""
        sequencia = list(nos) + ([nos[0]] if fechado else [])
        pontos = [encaixe[sequencia[0]][0]]
        for a, b in zip(sequencia[:-1], sequencia[1:]):
            sa, sb = encaixe[a][1], encaixe[b][1]
            if sa != sb and anel_do_segmento[sa] == anel_do_segmento[sb]:
                anel = anel_do_segmento[sa]
                base, m = comeco[anel], tamanhos[anel]
                ia, ib = sa - base, sb - base
                frente, tras = (ib - ia) % m, (ia - ib) % m
                if min(frente, tras) <= 6:
                    passos = range(1, frente + 1) if frente <= tras else range(0, -tras, -1)
                    pontos += [vertices[base + (ia + p) % m] for p in passos]
            pontos.append(encaixe[b][0])
        pontos = np.array(pontos[:-1] if fechado else pontos)
        # tira os pontos repetidos e os que estão em linha reta entre os vizinhos
        distintos = np.r_[True, np.hypot(*(pontos[1:] - pontos[:-1]).T) > 1e-9]
        pontos = pontos[distintos]
        if fechado:
            return pontos if len(pontos) < 4 else _suavizar(pontos, True, 0.02 * pixel, 0, deslocamento)
        return _simplificar(pontos, 0.02 * pixel)

    pronto = {}

    def arco(nos, fechado, de_borda):
        """Geometria suavizada de um arco, a mesma para as duas classes que o dividem."""
        if fechado:
            k = nos.index(min(nos))
            giro = nos[k:] + nos[:k]
            contrario = [giro[0]] + giro[:0:-1]
            invertido = contrario[1] < giro[1]
            chave = (tuple(contrario if invertido else giro), True)
        else:
            invertido = tuple(nos[::-1]) < tuple(nos)
            chave = (tuple(nos[::-1] if invertido else nos), False)
        if chave not in pronto:
            if de_borda and encaixe and all(no in encaixe for no in chave[0]):
                pronto[chave] = pela_borda(list(chave[0]), fechado)
            else:
                pronto[chave] = _suavizar(coordenadas(chave[0]), fechado, tolerancia_borda if de_borda else tolerancia,
                                          0 if de_borda else iteracoes, deslocamento)
        return pronto[chave][::-1] if invertido else pronto[chave]

    zonas = {}
    for c in np.unique(classe[classe >= 0]):
        da_classe = np.flatnonzero(classe == c)
        ini_c, fim_c, outra_c = inicio[da_classe], fim[da_classe], outra[da_classe]
        externos, furos = [], []
        for anel in (parte for inteiro in _aneis(ini_c, fim_c, W) for parte in _dividir(inteiro, ini_c)):
            nos = [int(ini_c[e]) for e in anel]
            cortes = [k for k, no in enumerate(nos) if juncao[no]]
            if not cortes:
                pontos = arco(nos, True, bool(outra_c[anel[0]] < 0))
            else:
                pedacos = []
                for a, b in zip(cortes, cortes[1:] + [cortes[0] + len(nos)]):
                    trecho = [nos[k % len(nos)] for k in range(a, b + 1)]
                    pedacos.append(arco(trecho, False, bool(outra_c[anel[a % len(nos)]] < 0))[:-1])
                pontos = np.vstack(pedacos)
            if len(pontos) < 3:
                continue
            area = _area_com_sinal(pontos)
            if area > 0:
                externos.append({'externo': pontos, 'furos': [], '_area': area})
            elif area < 0:
                furos.append(pontos)
        for furo in furos:
            tamanho = abs(_area_com_sinal(furo))
            donos = [p for p in externos if p['_area'] > tamanho
                     and Caminho(p['externo']).contains_points(furo).mean() > 0.5]
            if donos:
                min(donos, key=lambda p: p['_area'])['furos'].append(furo)
        zonas[int(c)] = [{'externo': p['externo'], 'furos': p['furos']} for p in externos]
    return zonas


if __name__ == '__main__':
    g = {'x0': 0.0, 'y0': 300.0, 'pixel': 10.0, 'nx': 40, 'ny': 30}
    L = np.zeros((30, 40), dtype=np.int32)
    L[:, 20:] = 1

    def total(zonas, c):
        return sum(area_ha(p) for p in zonas[c])

    # duas metades, sem suavizar: a área é exata
    z = vetorizar(L, g, iteracoes=0)
    assert len(z[0]) == 1 and len(z[1]) == 1 and abs(total(z, 0) - 6) < 1e-9 and abs(total(z, 1) - 6) < 1e-9
    assert not z[0][0]['furos'] and _area_com_sinal(z[0][0]['externo']) > 0

    # ilha da classe 1 dentro da 0 (furo), e uma terceira classe num canto
    M = L.copy()
    M[10:16, 5:11] = 1
    M[0:8, 30:40] = 2
    z = vetorizar(M, g, iteracoes=0)
    assert len(z[0]) == 1 and len(z[0][0]['furos']) == 1 and len(z[1]) == 2 and len(z[2]) == 1
    assert abs(total(z, 0) - (6 - 0.36)) < 1e-9 and abs(total(z, 1) - (6 + 0.36 - 0.8)) < 1e-9 and abs(total(z, 2) - 0.8) < 1e-9
    # o furo da zona 0 e o contorno da ilha da zona 1 são o MESMO anel
    ilha = min(z[1], key=area_ha)
    assert {tuple(p) for p in np.round(z[0][0]['furos'][0], 6)} == {tuple(p) for p in np.round(ilha['externo'], 6)}

    # suavizado: as zonas continuam cobrindo a área toda (divisa compartilhada, sem fresta nem sobra)
    s = vetorizar(M, g, tolerancia=8.0)
    soma = sum(total(s, c) for c in s)
    assert abs(soma - 12) < 0.02, soma
    assert len(s[0][0]['furos']) == 1 and abs(total(s, 2) - 0.8) < 0.08
    ilha_s = min(s[1], key=area_ha)
    assert {tuple(p) for p in np.round(s[0][0]['furos'][0], 6)} == {tuple(p) for p in np.round(ilha_s['externo'], 6)}
    assert len(ilha_s['externo']) > 8  # cantos arredondados

    # duas células da mesma classe encostadas só pela quina ficam em polígonos separados
    X = np.zeros((6, 6), dtype=np.int32)
    X[2, 2] = X[3, 3] = 1
    gx = {'x0': 0.0, 'y0': 60.0, 'pixel': 10.0, 'nx': 6, 'ny': 6}
    zx = vetorizar(X, gx, iteracoes=0)
    assert len(zx[1]) == 2 and abs(total(zx, 1) - 0.02) < 1e-9 and abs(total(zx, 0) - 0.34) < 1e-9
    assert len(zx[0]) == 1 and len(zx[0][0]['furos']) == 2

    # parte fora da grade (−1): o contorno acompanha a máscara
    F = np.full((10, 10), -1, dtype=np.int32)
    F[2:8, 2:8] = 0
    F[4:8, 5:8] = 1
    gf = {'x0': 0.0, 'y0': 100.0, 'pixel': 10.0, 'nx': 10, 'ny': 10}
    zf = vetorizar(F, gf, tolerancia=6.0)
    assert abs(sum(total(zf, c) for c in zf) - 0.36) < 0.004
    assert _simplificar(np.array([[0, 0], [1, 0.1], [2, 0], [3, 0.0]]), 0.5).tolist() == [[0, 0], [3, 0]]

    # com o perímetro verdadeiro (um losango), a borda das zonas cai em cima dele, com os cantos
    from areas import dentro
    losango = [(200.0, 20.0), (380.0, 150.0), (200.0, 280.0), (20.0, 150.0)]
    gl = {'x0': 0.0, 'y0': 300.0, 'pixel': 5.0, 'nx': 80, 'ny': 60}
    cx, cy = np.meshgrid((np.arange(80) + 0.5) * 5, 300 - (np.arange(60) + 0.5) * 5)
    mascara = dentro([losango], np.column_stack([cx.ravel(), cy.ravel()])).reshape(60, 80)
    D = np.where(mascara, (cx > 200).astype(np.int32), -1)
    area_certa = 0.5 * 360 * 260 / 10000
    solto = vetorizar(D, gl, tolerancia=5.0)
    preso = vetorizar(D, gl, tolerancia=5.0, perimetro=[losango])
    soma_solto = sum(area_ha(p) for c in solto for p in solto[c])
    soma_preso = sum(area_ha(p) for c in preso for p in preso[c])
    assert abs(soma_preso - area_certa) < 1e-6 * area_certa + 1e-9, (soma_preso, area_certa)
    assert abs(soma_solto - area_certa) > 1e-4  # sem o perímetro, a borda é a da grade
    assert len(preso[0]) == 1 and len(preso[1]) == 1 and len(preso[0][0]['externo']) <= 8, len(preso[0][0]['externo'])
    cantos = {tuple(np.round(p, 6)) for c in preso for p in preso[c][0]['externo']}
    assert {(20.0, 150.0), (380.0, 150.0)} <= cantos and abs(area_ha(preso[0][0]) - area_certa / 2) < 0.01
    print('vetor OK')
