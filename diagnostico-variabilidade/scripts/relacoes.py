"""O que varia junto com a variável a explicar: correlações e a parte de cada
camada no que o conjunto acompanha.

Três números por camada, todos de regressão linear por mínimos quadrados e
todos em fração da variância da variável a explicar (R²):

- sozinha: o R² da camada sem as outras (o quadrado da correlação);
- por cima das outras: quanto o R² do conjunto cai quando só ela sai;
- repartida: a média do que ela acrescenta em todas as ordens de entrada
  possíveis (método de Lindeman, Merenda e Gold; o mesmo que o valor de
  Shapley). As partes repartidas somam o R² do conjunto.

Camadas redundantes (que dizem quase a mesma coisa) aparecem assim: as duas
altas em "sozinha", as duas perto de zero em "por cima das outras", e o que
elas têm em comum dividido entre as duas em "repartida".

Nada disto é causa. É descrição de quem varia junto com quem.

Teste embutido: python scripts/relacoes.py
"""

import math
from itertools import combinations

import numpy as np
from scipy import stats

TETO_DO_REPARTIDA = 12        # com mais camadas que isto, 2^p regressões ficam demais
REDUNDANTE = 0.80
QUASE_IGUAL = 0.95
QUASE_A_RESPOSTA = 0.90


class DadosInvalidos(Exception):
    pass


def correlacoes(matriz):
    """Pearson e Spearman entre as colunas de `matriz` [n, p]."""
    m = np.asarray(matriz, float)
    if m.shape[0] < 3:
        raise DadosInvalidos('menos de 3 células completas')
    if (m.std(axis=0) <= 0).any():
        raise DadosInvalidos('há coluna constante')
    pearson = np.corrcoef(m, rowvar=False)
    postos = np.column_stack([stats.rankdata(m[:, j]) for j in range(m.shape[1])])
    spearman = np.corrcoef(postos, rowvar=False)
    return np.atleast_2d(pearson), np.atleast_2d(spearman)


def _r2(rxx, rxy, colunas):
    """R² da regressão da resposta nas colunas dadas, a partir das correlações."""
    if not colunas:
        return 0.0
    idx = np.asarray(sorted(colunas))
    a, b = rxx[np.ix_(idx, idx)], rxy[idx]
    coef, *_ = np.linalg.lstsq(a, b, rcond=1e-10)
    return float(min(1.0, max(0.0, b @ coef)))


def _padronizar(colunas):
    x = np.asarray(colunas, float)
    return (x - x.mean(axis=0)) / x.std(axis=0)


def blocos_de(numericas, categoricas=None):
    """Monta a matriz de colunas e os blocos. numericas = {nome: vetor}; categoricas = {nome: rótulos inteiros}.
    Uma camada de classes vira um bloco de colunas 0/1 (uma por classe, menos a primeira)."""
    nomes, colunas, blocos = [], [], []
    for nome, v in numericas.items():
        blocos.append([len(colunas)])
        colunas.append(np.asarray(v, float))
        nomes.append(nome)
    for nome, rot in (categoricas or {}).items():
        classes = [c for c in np.unique(rot) if (rot == c).sum() > 0]
        if len(classes) < 2:
            raise DadosInvalidos(f'a camada de classes "{nome}" tem uma classe só nas células completas')
        inicio = len(colunas)
        for c in classes[1:]:
            colunas.append((rot == c).astype(float))
        blocos.append(list(range(inicio, len(colunas))))
        nomes.append(nome)
    return nomes, np.column_stack(colunas), blocos


def importancia(y, x, blocos):
    """Para cada bloco: R² sozinho, por cima dos outros e repartido. Devolve dict com o R² do conjunto."""
    y = np.asarray(y, float)
    if y.std() <= 0:
        raise DadosInvalidos('a variável a explicar é constante nas células completas')
    if (np.asarray(x, float).std(axis=0) <= 0).any():
        raise DadosInvalidos('há camada constante nas células completas')
    z = _padronizar(x)
    zy = (y - y.mean()) / y.std()
    n = len(y)
    rxx = (z.T @ z) / n
    rxy = (z.T @ zy) / n
    p = len(blocos)
    todas = [c for b in blocos for c in b]
    total = _r2(rxx, rxy, todas)
    sozinha = [_r2(rxx, rxy, b) for b in blocos]
    por_cima = [max(0.0, total - _r2(rxx, rxy, [c for k, b in enumerate(blocos) if k != j for c in b])) for j in range(p)]
    repartida = None
    if p <= TETO_DO_REPARTIDA:
        r2 = {}
        for mascara in range(1 << p):
            r2[mascara] = _r2(rxx, rxy, [c for k in range(p) if mascara >> k & 1 for c in blocos[k]])
        peso = [math.factorial(s) * math.factorial(p - s - 1) / math.factorial(p) for s in range(p)]
        repartida = [0.0] * p
        for j in range(p):
            for mascara in range(1 << p):
                if mascara >> j & 1:
                    continue
                repartida[j] += peso[bin(mascara).count('1')] * (r2[mascara | 1 << j] - r2[mascara])
    # sinal da relação: o da correlação e o do coeficiente quando as outras entram (só para camada de uma coluna)
    coef, *_ = np.linalg.lstsq(rxx[np.ix_(todas, todas)], rxy[todas], rcond=1e-10)
    por_coluna = dict(zip(todas, coef))
    sinal, sinal_no_conjunto, inflacao = [], [], []
    for j, b in enumerate(blocos):
        if len(b) != 1:
            sinal.append(None)
            sinal_no_conjunto.append(None)
            inflacao.append(None)
            continue
        c = b[0]
        sinal.append(float(rxy[c]))
        sinal_no_conjunto.append(float(por_coluna[c]))
        outras = [k for k in todas if k != c]
        r2_j = _r2(rxx, rxx[:, c], outras) if outras else 0.0
        inflacao.append(float('inf') if r2_j >= 1 - 1e-9 else 1 / (1 - r2_j))
    return {'r2_do_conjunto': total, 'sozinha': sozinha, 'por_cima': por_cima, 'repartida': repartida,
            'correlacao': sinal, 'coeficiente_no_conjunto': sinal_no_conjunto, 'inflacao': inflacao, 'n': n, 'blocos': p}


def em_curva(y, x):
    """R² da reta e da curva de segundo grau de y em x. Serve para avisar relação que não é reta."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    xs = (x - x.mean()) / x.std()
    sq = float(((y - y.mean()) ** 2).sum())
    saida = []
    for grau in (1, 2):
        a = np.column_stack([xs ** k for k in range(grau + 1)])
        coef, *_ = np.linalg.lstsq(a, y, rcond=None)
        saida.append(float(1 - ((y - a @ coef) ** 2).sum() / sq))
    return saida[0], saida[1]


def piso_de_ruido(n_colunas, n_efetivo, nivel=0.95):
    """R² que um conjunto de `n_colunas` SEM relação nenhuma alcança em 95% das vezes, com `n_efetivo`
    observações independentes. None quando há colunas demais para as observações."""
    if not np.isfinite(n_efetivo) or n_efetivo - n_colunas - 1 <= 0:
        return None
    return float(stats.beta.ppf(nivel, n_colunas / 2, (n_efetivo - n_colunas - 1) / 2))


def pares_redundantes(pearson, nomes, corte=REDUNDANTE):
    """[(nome_a, nome_b, r)] dos pares de camadas com |r| a partir do corte, do maior para o menor."""
    pares = [(nomes[i], nomes[j], float(pearson[i, j])) for i, j in combinations(range(len(nomes)), 2)
             if abs(pearson[i, j]) >= corte]
    return sorted(pares, key=lambda t: -abs(t[2]))


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    g = np.random.default_rng(3)
    n = 4000
    a, b, c = g.standard_normal(n), g.standard_normal(n), g.standard_normal(n)
    copia = a + 0.15 * g.standard_normal(n)
    y = 1.0 * a + 0.6 * b + 0.8 * g.standard_normal(n)

    pearson, spearman = correlacoes(np.column_stack([y, a, b, c, copia]))
    assert abs(pearson[0, 1] - np.corrcoef(y, a)[0, 1]) < 1e-12 and pearson.shape == (5, 5)
    assert abs(spearman[0, 1] - stats.spearmanr(y, a)[0]) < 1e-12

    nomes, x, blocos = blocos_de({'a': a, 'b': b, 'c': c, 'copia': copia})
    r = importancia(y, x, blocos)
    # R² do conjunto contra mínimos quadrados direto nos dados
    A = np.column_stack([np.ones(n), x])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    direto = 1 - ((y - A @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    assert abs(r['r2_do_conjunto'] - direto) < 1e-9, (r['r2_do_conjunto'], direto)
    # sozinha = quadrado da correlação; as partes repartidas somam o R² do conjunto
    assert abs(r['sozinha'][0] - np.corrcoef(y, a)[0, 1] ** 2) < 1e-9
    assert abs(sum(r['repartida']) - r['r2_do_conjunto']) < 1e-9
    # redundância: a e a cópia altas sozinhas, quase nada por cima uma da outra, e repartem o que têm em comum
    ia, ib, ic, ik = (nomes.index(k) for k in ('a', 'b', 'c', 'copia'))
    assert r['sozinha'][ia] > 0.45 and r['sozinha'][ik] > 0.45
    assert r['por_cima'][ia] < 0.03 and r['por_cima'][ik] < 0.01
    assert abs(r['repartida'][ia] - r['repartida'][ik]) < 0.06 and r['repartida'][ia] > 0.2
    assert r['sozinha'][ic] < 0.01 and r['repartida'][ic] < 0.01
    assert r['inflacao'][ia] > 10 and r['inflacao'][ib] < 1.1
    assert pares_redundantes(np.corrcoef(x, rowvar=False), nomes)[0][:2] == ('a', 'copia')

    # bloco de classes: R² sozinho igual à fração da variância entre as classes (eta²)
    classes = g.integers(0, 3, n)
    yc = np.array([0.0, 1.0, 3.0])[classes] + g.standard_normal(n)
    nomes2, x2, blocos2 = blocos_de({'c': c}, {'zona': classes})
    r2 = importancia(yc, x2, blocos2)
    medias = np.array([yc[classes == k].mean() for k in range(3)])
    eta2 = sum((classes == k).sum() * (medias[k] - yc.mean()) ** 2 for k in range(3)) / ((yc - yc.mean()) ** 2).sum()
    assert abs(r2['sozinha'][nomes2.index('zona')] - eta2) < 1e-9
    assert r2['correlacao'][nomes2.index('zona')] is None and len(blocos2[1]) == 2

    # relação em curva: a reta não vê, a curva vê
    u = g.uniform(-2, 2, n)
    reta, curva = em_curva(1 - u ** 2 + 0.3 * g.standard_normal(n), u)
    assert reta < 0.02 and curva > 0.9, (reta, curva)

    # piso de ruído: confere com simulação de colunas sem relação
    acima = 0
    for _ in range(400):
        yy, xx = g.standard_normal(30), g.standard_normal((30, 3))
        A = np.column_stack([np.ones(30), xx])
        coef, *_ = np.linalg.lstsq(A, yy, rcond=None)
        acima += (1 - ((yy - A @ coef) ** 2).sum() / ((yy - yy.mean()) ** 2).sum()) > piso_de_ruido(3, 30)
    assert 0.02 < acima / 400 < 0.09, acima / 400
    assert piso_de_ruido(5, 6) is None

    for ruim in (lambda: importancia(np.ones(50), x[:50], blocos), lambda: correlacoes(np.column_stack([np.ones(9), a[:9]]))):
        try:
            ruim()
        except DadosInvalidos:
            pass
        else:
            raise AssertionError('devia recusar coluna constante')
    print(f'relacoes OK (R² do conjunto {r["r2_do_conjunto"]:.3f}; repartida: a {r["repartida"][ia]:.3f}, cópia '
          f'{r["repartida"][ik]:.3f}, b {r["repartida"][ib]:.3f}, c {r["repartida"][ic]:.3f})')


if __name__ == '__main__':
    _autoteste()
