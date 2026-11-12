"""Desenhos amostrais em coordenadas métricas (UTM) e a rota de coleta.

Três desenhos:
- grade: um ponto por nó de uma grade regular (quadrada ou triangular);
- celula: a área é dividida em células e cada célula vira UMA amostra composta,
  com as subamostras espalhadas dentro dela;
- zona: cada zona (ou talhão) vira uma ou mais amostras compostas, com as
  subamostras espalhadas por toda a zona.

Nada aqui é sorteado: o mesmo perímetro com os mesmos parâmetros dá sempre os
mesmos pontos, para o trabalho poder ser refeito e auditado.
"""

import math

import numpy as np

import areas as modulo_areas

RAIZ3_2 = math.sqrt(3) / 2


def espacamento_de(ha_por_ponto, arranjo='quadrado'):
    """Distância entre pontos (m) que dá a densidade pedida."""
    area = ha_por_ponto * 10000
    return math.sqrt(area / RAIZ3_2) if arranjo == 'triangular' else math.sqrt(area)


def _girar(pontos, angulo, centro):
    if not angulo:
        return pontos
    a = math.radians(angulo)
    giro = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    return (pontos - centro) @ giro.T + centro


def _reticulado(aneis, passo_x, passo_y, angulo=0.0, triangular=False, meio_passo=False):
    """Nós de uma grade que cobre a área. Devolve (pontos [n, 2], linha [n], coluna [n]).
    Com `meio_passo`, os nós ficam deslocados de meio passo: é o que faz as BORDAS das
    células (e não os centros) passarem pelo meio da área."""
    x0, y0, x1, y1 = modulo_areas.caixa(aneis)
    centro = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    raio = math.hypot(x1 - x0, y1 - y0) / 2 + max(passo_x, passo_y)
    nx, ny = int(math.ceil(raio / passo_x)), int(math.ceil(raio / passo_y))
    colunas, linhas = np.meshgrid(np.arange(-nx, nx + 1), np.arange(-ny, ny + 1))
    xs = colunas * passo_x + (np.where(linhas % 2 != 0, passo_x / 2, 0.0) if triangular else 0.0)
    pontos = np.column_stack([xs.ravel(), (linhas * passo_y).ravel()]) + centro
    if meio_passo:
        pontos = pontos + np.array([passo_x / 2, passo_y / 2])
    return _girar(pontos, angulo, centro), linhas.ravel(), colunas.ravel()


def grade(aneis, espacamento, arranjo='quadrado', angulo=0.0, borda=0.0):
    """Pontos de uma grade regular dentro da área, a pelo menos `borda` metros do
    contorno, já na ordem de caminhamento em serpentina."""
    triangular = arranjo == 'triangular'
    pontos, linhas, colunas = _reticulado(
        aneis, espacamento, espacamento * (RAIZ3_2 if triangular else 1.0), angulo, triangular,
        meio_passo=True)  # o ponto fica no CENTRO de cada malha, nunca em cima da divisa
    fica = modulo_areas.dentro(aneis, pontos)
    if borda > 0 and fica.any():
        fica[fica] = modulo_areas.distancia_da_borda(aneis, pontos[fica]) >= borda
    pontos, linhas, colunas = pontos[fica], linhas[fica], colunas[fica]
    ordem = sorted(range(len(pontos)),
                   key=lambda i: (linhas[i], colunas[i] if linhas[i] % 2 == 0 else -colunas[i]))
    return pontos[ordem]


def mais_espalhados(candidatos, quantos):
    """Escolhe `quantos` pontos o mais afastados possível entre si (determinístico:
    começa pelo mais próximo do centro e vai somando o mais distante dos já escolhidos)."""
    candidatos = np.asarray(candidatos, dtype=float)
    if len(candidatos) <= quantos:
        return candidatos
    centro = candidatos.mean(axis=0)
    escolhidos = [int(np.argmin(((candidatos - centro) ** 2).sum(axis=1)))]
    distancia = ((candidatos - candidatos[escolhidos[0]]) ** 2).sum(axis=1)
    while len(escolhidos) < quantos:
        proximo = int(np.argmax(distancia))
        escolhidos.append(proximo)
        distancia = np.minimum(distancia, ((candidatos - candidatos[proximo]) ** 2).sum(axis=1))
    return candidatos[escolhidos]


def _candidatos(aneis, quantos, borda):
    """Malha fina de pontos possíveis dentro da área (uns 12 por ponto pedido)."""
    passo = max(2.0, math.sqrt(modulo_areas.area_ha(aneis) * 10000 / max(quantos * 12, 60)))
    pontos, _, _ = _reticulado(aneis, passo, passo)
    fica = modulo_areas.dentro(aneis, pontos)
    pontos = pontos[fica]
    if borda > 0 and len(pontos):
        longe = modulo_areas.distancia_da_borda(aneis, pontos) >= borda
        if longe.sum() >= quantos:  # área estreita demais para a borda pedida: afrouxa em vez de falhar
            pontos = pontos[longe]
    return pontos


def _dividir(pontos, partes):
    """Separa os pontos em `partes` grupos compactos (k-médias com início espalhado)."""
    if partes <= 1 or len(pontos) <= partes:
        return np.zeros(len(pontos), dtype=int)
    centros = mais_espalhados(pontos, partes).copy()
    rotulo = np.zeros(len(pontos), dtype=int)
    for _ in range(40):
        novo = np.argmin(((pontos[:, None, :] - centros[None, :, :]) ** 2).sum(axis=2), axis=1)
        if (novo == rotulo).all() and _ > 0:
            break
        rotulo = novo
        for k in range(partes):
            if (rotulo == k).any():
                centros[k] = pontos[rotulo == k].mean(axis=0)
    # numera os grupos de oeste para leste, de norte para sul
    ordem = sorted(range(partes), key=lambda k: (-round(centros[k][1], -1), centros[k][0]))
    troca = {antigo: novo for novo, antigo in enumerate(ordem)}
    return np.array([troca[r] for r in rotulo])


def compostas(aneis, n_compostas, subamostras, borda=0.0):
    """Divide a área em `n_compostas` partes e espalha `subamostras` pontos em cada.
    Devolve uma lista de matrizes [subamostras, 2], uma por amostra composta."""
    candidatos = _candidatos(aneis, n_compostas * subamostras, borda)
    if not len(candidatos):
        return []
    rotulo = _dividir(candidatos, n_compostas)
    grupos = []
    for k in range(int(rotulo.max()) + 1):
        do_grupo = candidatos[rotulo == k]
        if len(do_grupo):
            grupos.append(rota(mais_espalhados(do_grupo, subamostras)))
    return grupos


def celulas(aneis, lado, subamostras, angulo=0.0, borda=0.0, fracao_minima=0.25):
    """Células quadradas de `lado` metros. Cada célula com pelo menos `fracao_minima`
    da área dentro do perímetro vira uma amostra composta. Devolve
    [{'quadro': [4 cantos], 'pontos': [subamostras, 2], 'fracao': 0–1}], em serpentina."""
    centros, linhas, colunas = _reticulado(aneis, lado, lado, angulo, meio_passo=True)
    k = 11  # 11 × 11 pontos de teste por célula: sobra candidato mesmo em célula de borda
    passo = np.linspace(-0.5 + 0.5 / k, 0.5 - 0.5 / k, k) * lado
    dx, dy = np.meshgrid(passo, passo)
    molde = _girar(np.column_stack([dx.ravel(), dy.ravel()]), angulo, np.zeros(2))
    cantos = _girar(np.array([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]) * lado, angulo, np.zeros(2))
    achadas = []
    for c, linha, coluna in zip(centros, linhas, colunas):
        testes = c + molde
        fica = modulo_areas.dentro(aneis, testes)
        fracao = float(fica.mean())
        if fracao < fracao_minima:
            continue
        validos = testes[fica]
        if borda > 0:
            longe = modulo_areas.distancia_da_borda(aneis, validos) >= borda
            if longe.sum() >= min(subamostras, 3):
                validos = validos[longe]
        achadas.append({'quadro': (c + cantos).tolist(), 'fracao': round(fracao, 2),
                        'pontos': rota(mais_espalhados(validos, subamostras)),
                        '_ordem': (linha, coluna if linha % 2 == 0 else -coluna)})
    achadas.sort(key=lambda a: a.pop('_ordem'))
    return achadas


def comprimento(pontos):
    pontos = np.asarray(pontos, dtype=float)
    return float(np.sqrt((np.diff(pontos, axis=0) ** 2).sum(axis=1)).sum()) if len(pontos) > 1 else 0.0


def rota(pontos, inicio=None):
    """Ordena os pontos num caminho curto: vizinho mais próximo e depois 2-opt.
    Começa pelo ponto mais a oeste (ou pelo mais próximo de `inicio`)."""
    pontos = np.asarray(pontos, dtype=float)
    n = len(pontos)
    if n < 3:
        return pontos
    atual = (int(np.argmin(((pontos - np.asarray(inicio)) ** 2).sum(axis=1))) if inicio is not None
             else int(np.lexsort((pontos[:, 1], pontos[:, 0]))[0]))
    livre = np.ones(n, dtype=bool)
    ordem = [atual]
    livre[atual] = False
    while livre.any():
        d = ((pontos - pontos[atual]) ** 2).sum(axis=1)
        d[~livre] = np.inf
        atual = int(np.argmin(d))
        ordem.append(atual)
        livre[atual] = False
    caminho = pontos[ordem]
    if n <= 400:  # 2-opt: desfaz os cruzamentos
        melhorou, voltas = True, 0
        while melhorou and voltas < 20:
            melhorou, voltas = False, voltas + 1
            for i in range(1, n - 2):
                a, b = caminho[i - 1], caminho[i]
                for j in range(i + 1, n - 1):
                    c, d2 = caminho[j], caminho[j + 1]
                    antes = math.dist(a, b) + math.dist(c, d2)
                    depois = math.dist(a, c) + math.dist(b, d2)
                    if depois + 1e-9 < antes:
                        caminho[i:j + 1] = caminho[i:j + 1][::-1].copy()
                        b = caminho[i]
                        melhorou = True
    return caminho


if __name__ == '__main__':
    quadrado = [[(0, 0), (1000, 0), (1000, 1000), (0, 1000), (0, 0)]]  # 100 ha

    # densidade → espaçamento: 1 ponto por ha = 100 m na grade quadrada
    assert abs(espacamento_de(1) - 100) < 1e-9 and abs(espacamento_de(4) - 200) < 1e-9
    assert abs(espacamento_de(1, 'triangular') - 107.457) < 0.01

    g = grade(quadrado, 100)
    assert len(g) == 100, len(g)  # 100 ha a 1 ponto por ha
    assert modulo_areas.distancia_da_borda(quadrado, g).min() >= 49.9  # no centro da malha
    assert modulo_areas.dentro(quadrado, g).all()
    # serpentina: pontos seguidos ficam a um passo de distância (sem "voltar a linha vazio")
    passos = np.sqrt((np.diff(g, axis=0) ** 2).sum(axis=1))
    assert passos.max() < 150, passos.max()
    assert (g == grade(quadrado, 100)).all()  # determinístico
    com_borda = grade(quadrado, 100, borda=60)
    assert len(com_borda) < len(g) and modulo_areas.distancia_da_borda(quadrado, com_borda).min() >= 60
    tri = grade(quadrado, espacamento_de(1, 'triangular'), arranjo='triangular')
    assert 85 <= len(tri) <= 115, len(tri)
    girada = grade(quadrado, 100, angulo=30)
    assert modulo_areas.dentro(quadrado, girada).all() and 85 <= len(girada) <= 115

    esp = mais_espalhados(g, 5)
    dmin = min(math.dist(a, b) for i, a in enumerate(esp) for b in esp[i + 1:])
    assert len(esp) == 5 and dmin > 300, dmin

    zonas = compostas(quadrado, 2, 15, borda=20)
    assert len(zonas) == 2 and all(len(z) == 15 for z in zonas)
    assert all(modulo_areas.dentro(quadrado, z).all() for z in zonas)
    assert all(modulo_areas.distancia_da_borda(quadrado, z).min() >= 20 for z in zonas)
    # as duas compostas ocupam metades diferentes da área
    assert math.dist(zonas[0].mean(axis=0), zonas[1].mean(axis=0)) > 300

    cs = celulas(quadrado, 250, 8)
    assert len(cs) == 16 and all(len(c['pontos']) == 8 for c in cs), len(cs)
    triangulo = [[(0, 0), (1000, 0), (0, 1000), (0, 0)]]
    assert 8 <= len(celulas(triangulo, 250, 8)) <= 12

    # a rota não é pior que a ordem original embaralhada e visita todos os pontos
    rng = np.random.default_rng(1)
    soltos = rng.uniform(0, 1000, size=(40, 2))
    r = rota(soltos)
    assert len(r) == 40 and comprimento(r) < 0.6 * comprimento(soltos)
    assert {tuple(p) for p in r.round(6).tolist()} == {tuple(p) for p in soltos.round(6).tolist()}
    print(f'desenho OK: grade {len(g)} pts, triangular {len(tri)}, 2 compostas de 15, '
          f'{len(cs)} células, rota {comprimento(r) / 1000:.1f} km')
