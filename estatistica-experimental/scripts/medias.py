"""Testes de comparação de médias e as letras da tabela.

Todos os testes partem dos mesmos quatro números da análise de variância: as
médias, o número de repetições de cada uma, o quadrado médio do resíduo e os
graus de liberdade do resíduo. Quem escolhe o teste e a significância é o
usuário; aqui não há padrão.

  tukey        diferença honestamente significativa (Tukey-Kramer com n desigual)
  t            teste t par a par (LSD), sem ajuste para o número de comparações
  snk          Student-Newman-Keuls, por amplitudes (só com repetições iguais)
  duncan       amplitudes múltiplas de Duncan (só com repetições iguais)
  scott-knott  agrupamento sem sobreposição (só com repetições iguais)
  dunnett      cada tratamento contra a testemunha, bilateral

Teste embutido: python scripts/medias.py
"""

import math
from functools import lru_cache

import numpy as np
from scipy import stats

TESTES = {
    'tukey': 'Tukey',
    't': 't (LSD)',
    'snk': 'SNK (Student-Newman-Keuls)',
    'duncan': 'Duncan',
    'scott-knott': 'Scott-Knott',
    'dunnett': 'Dunnett',
}
SO_BALANCEADO = ('snk', 'duncan', 'scott-knott')
LETRAS = 'abcdefghijklmnopqrstuvwxyz'


class ErroDeTeste(Exception):
    """Pedido que o teste não cobre; a mensagem vai para o usuário como está."""


def _amplitude():
    if not hasattr(stats, 'studentized_range'):
        raise ErroDeTeste('Este teste usa a distribuição da amplitude estudentizada, que existe no scipy a partir da '
                          'versão 1.7. Atualize o scipy ou escolha t, scott-knott ou dunnett.')
    return stats.studentized_range


@lru_cache(maxsize=1024)
def _quantil_amplitude(prob, k, gl):
    """Quantil da amplitude estudentizada; guardado porque o cálculo é lento e se repete nos desdobramentos."""
    return float(_amplitude().ppf(prob, k, gl))


def _iguais(n):
    n = np.asarray(n, float)
    return bool(np.all(n == n[0]))


def _prob(p):
    return float(min(1.0, max(0.0, p)))


# ------------------------------------------------------------------ letras
def letras(diferente, medias):
    """Letras a partir da matriz 'diferente' (k x k, simétrica). A letra 'a' fica com a maior média.

    Algoritmo de inserir e absorver: começa com um grupo de todos; cada par diferente
    parte os grupos que têm os dois; grupo contido em outro some.
    """
    k = len(medias)
    ordem = sorted(range(k), key=lambda i: (-medias[i], i))
    posicao = {t: p for p, t in enumerate(ordem)}
    grupos = [frozenset(range(k))]
    for a in range(k):
        for b in range(a + 1, k):
            i, j = ordem[a], ordem[b]
            if not diferente[i][j]:
                continue
            novos = []
            for g in grupos:
                if i in g and j in g:
                    novos.extend((g - {i}, g - {j}))
                else:
                    novos.append(g)
            unicos = list(dict.fromkeys(g for g in novos if g))
            grupos = [g for g in unicos if not any(g < outro for outro in unicos)]
    grupos.sort(key=lambda g: sorted(posicao[t] for t in g))
    saida = [''] * k
    for n, g in enumerate(grupos):
        marca = LETRAS[n] if n < len(LETRAS) else LETRAS[n // len(LETRAS) - 1] + LETRAS[n % len(LETRAS)]
        for t in g:
            saida[t] += marca
    return saida


# ------------------------------------------------------------------ par a par
def tukey(medias, n, qm, gl, alfa):
    dist = _amplitude()
    k = len(medias)
    p = np.ones((k, k))
    for i in range(k):
        for j in range(i + 1, k):
            ep = math.sqrt(qm / 2.0 * (1.0 / n[i] + 1.0 / n[j]))
            p[i, j] = p[j, i] = _prob(dist.sf(abs(medias[i] - medias[j]) / ep, k, gl))
    dms = _quantil_amplitude(1 - alfa, k, gl) * math.sqrt(qm / n[0]) if _iguais(n) else None
    return p, dms


def teste_t(medias, n, qm, gl, alfa):
    k = len(medias)
    p = np.ones((k, k))
    for i in range(k):
        for j in range(i + 1, k):
            ep = math.sqrt(qm * (1.0 / n[i] + 1.0 / n[j]))
            p[i, j] = p[j, i] = _prob(2 * stats.t.sf(abs(medias[i] - medias[j]) / ep, gl))
    dms = float(stats.t.ppf(1 - alfa / 2, gl) * math.sqrt(2 * qm / n[0])) if _iguais(n) else None
    return p, dms


# ------------------------------------------------------------------ amplitudes
def amplitudes(medias, n, qm, gl, alfa, qual):
    """SNK ou Duncan. Devolve (matriz 'diferente', {p: amplitude crítica}).

    Duas médias só são declaradas diferentes se nenhuma faixa que contém as duas
    (na ordem das médias) deixou de ser significativa: é a regra de proteção dos
    testes de amplitude.
    """
    _amplitude()
    k = len(medias)
    ordem = sorted(range(k), key=lambda i: (-medias[i], i))
    m = [medias[i] for i in ordem]
    ep = math.sqrt(qm / n[0])
    critico = {}
    for p in range(2, k + 1):
        nivel = alfa if qual == 'snk' else 1 - (1 - alfa) ** (p - 1)
        critico[p] = _quantil_amplitude(1 - nivel, p, gl) * ep
    folga = 1e-12 * max(1.0, abs(m[0]), abs(m[-1]))
    homogenea = [[(m[a] - m[b]) <= critico[b - a + 1] + folga if b > a else True for b in range(k)] for a in range(k)]
    diferente = np.zeros((k, k), dtype=bool)
    for a in range(k):
        for b in range(a + 1, k):
            protegida = any(homogenea[c][d] for c in range(a + 1) for d in range(b, k))
            diferente[ordem[a], ordem[b]] = diferente[ordem[b], ordem[a]] = not protegida
    return diferente, critico


# ------------------------------------------------------------------ Scott-Knott
def scott_knott(medias, r, qm, gl, alfa):
    """Agrupa as médias (Scott e Knott, 1974). Devolve (grupo de cada média, divisões testadas).

    Em cada passo, parte as médias ordenadas no ponto que dá a maior soma de
    quadrados entre os dois grupos (B0) e testa
        lambda = pi / (2 (pi - 2)) * B0 / sigma0²,
    com sigma0² = [soma (média - média geral)² + gl * QMRes / r] / (k + gl),
    contra o qui-quadrado com k / (pi - 2) graus de liberdade.
    """
    k = len(medias)
    ordem = sorted(range(k), key=lambda i: (-medias[i], i))
    m = np.array([medias[i] for i in ordem], float)
    divisoes = []

    def dividir(ini, fim):
        tam = fim - ini
        if tam < 2:
            return [(ini, fim)]
        parte = m[ini:fim]
        total = parte.sum()
        acum = np.cumsum(parte)[:-1]
        cortes = np.arange(1, tam)
        b0 = acum ** 2 / cortes + (total - acum) ** 2 / (tam - cortes) - total ** 2 / tam
        s = int(np.argmax(b0)) + 1
        sigma2 = (((parte - parte.mean()) ** 2).sum() + gl * qm / r) / (tam + gl)
        lam = math.pi / (2 * (math.pi - 2)) * float(b0[s - 1]) / sigma2
        p = _prob(stats.chi2.sf(lam, tam / (math.pi - 2)))
        divisoes.append({'medias': [ordem[i] for i in range(ini, fim)], 'corte_depois_de': ordem[ini + s - 1],
                         'lambda': lam, 'p': p, 'dividiu': bool(p < alfa)})
        if p < alfa:
            return dividir(ini, ini + s) + dividir(ini + s, fim)
        return [(ini, fim)]

    grupo = [0] * k
    for g, (ini, fim) in enumerate(dividir(0, k)):
        for pos in range(ini, fim):
            grupo[ordem[pos]] = g
    return grupo, divisoes


# ------------------------------------------------------------------ Dunnett
def _nos(quantos, a, b):
    x, w = np.polynomial.legendre.leggauss(quantos)
    return 0.5 * (b - a) * x + 0.5 * (b + a), 0.5 * (b - a) * w


_HERMITE = np.polynomial.hermite.hermgauss(80)


def _dunnett_dentro(c, b, gl):
    """P(|T_i| <= c para todo i), T com correlação b_i * b_j (Dunnett bilateral).

    Integra em z0 (a média padronizada da testemunha, Gauss-Hermite) e em s (o
    desvio estimado sobre o verdadeiro, Gauss-Legendre na densidade de raiz(qui²/gl)).
    """
    b = np.asarray(b, float)
    a = np.sqrt(1 - b ** 2)
    z = math.sqrt(2.0) * _HERMITE[0]
    wz = _HERMITE[1] / math.sqrt(math.pi)
    s_lo = math.sqrt(stats.chi2.ppf(1e-13, gl) / gl)
    s_hi = math.sqrt(stats.chi2.ppf(1 - 1e-13, gl) / gl)
    s, ws = _nos(160, s_lo, s_hi)
    dens = 2 * gl * s * stats.chi2.pdf(gl * s ** 2, gl)
    cs = c * s[:, None, None]                                  # (S, 1, 1)
    zz = z[None, :, None]                                      # (1, Z, 1)
    alto = (cs + b[None, None, :] * zz) / a[None, None, :]
    baixo = (-cs + b[None, None, :] * zz) / a[None, None, :]
    dentro = np.prod(stats.norm.cdf(alto) - stats.norm.cdf(baixo), axis=2)   # (S, Z)
    return float(np.sum(ws * dens * (dentro @ wz)))


def dunnett(medias, n, qm, gl, alfa, controle):
    """Cada tratamento contra a testemunha (bilateral). Devolve lista de comparações e o valor crítico."""
    outros = [i for i in range(len(medias)) if i != controle]
    if not outros:
        raise ErroDeTeste('O teste de Dunnett precisa de pelo menos um tratamento além da testemunha.')
    b = [math.sqrt(n[i] / (n[i] + n[controle])) for i in outros]
    from scipy.optimize import brentq
    lo = float(stats.t.ppf(1 - alfa / 2, gl))
    hi = float(stats.t.ppf(1 - alfa / (2 * len(outros)), gl)) + 1e-9
    critico = lo if len(outros) == 1 else float(brentq(lambda c: _dunnett_dentro(c, b, gl) - (1 - alfa), lo, hi,
                                                         xtol=1e-7))
    saida = []
    for i in outros:
        ep = math.sqrt(qm * (1.0 / n[i] + 1.0 / n[controle]))
        dif = medias[i] - medias[controle]
        p = _prob(1 - _dunnett_dentro(abs(dif) / ep, b, gl)) if len(outros) > 1 else _prob(
            2 * stats.t.sf(abs(dif) / ep, gl))
        saida.append({'tratamento': i, 'diferenca': float(dif), 'dms': float(critico * ep), 'p': p,
                      'difere': bool(p < alfa)})
    return saida, critico


# ------------------------------------------------------------------ porta única
def comparar(medias, n, qm, gl, teste, alfa, controle=None):
    """Roda o teste pedido. Devolve um dicionário com 'letras' (ou None no Dunnett) e os detalhes."""
    medias = [float(v) for v in medias]
    n = [float(v) for v in n]
    k = len(medias)
    if teste not in TESTES:
        raise ErroDeTeste(f'Teste desconhecido: {teste}. Os que existem: {", ".join(TESTES)}.')
    if k < 2:
        raise ErroDeTeste('São necessárias pelo menos duas médias para comparar.')
    if gl < 1 or not qm >= 0:
        raise ErroDeTeste('Sem graus de liberdade no resíduo não há como comparar médias.')
    if teste in SO_BALANCEADO and not _iguais(n):
        raise ErroDeTeste(f'O teste {TESTES[teste]} está implementado só para o mesmo número de repetições em todos os '
                          'tratamentos. Com repetições desiguais, use tukey (Tukey-Kramer), t ou dunnett.')
    r = {'teste': teste, 'nome_do_teste': TESTES[teste], 'alfa': alfa, 'letras': None, 'dms': None, 'pares': [],
         'notas': []}
    if teste in ('tukey', 't'):
        p, dms = (tukey if teste == 'tukey' else teste_t)(medias, n, qm, gl, alfa)
        r['letras'] = letras(p < alfa, medias)
        r['dms'] = dms
        r['pares'] = [{'i': i, 'j': j, 'diferenca': medias[i] - medias[j], 'p': float(p[i, j]),
                       'difere': bool(p[i, j] < alfa)} for i in range(k) for j in range(i + 1, k)]
        if dms is None:
            r['notas'].append('Repetições desiguais: cada par tem a sua diferença mínima; a tabela de pares traz o '
                              'valor de p de cada comparação.')
        if teste == 't':
            r['notas'].append('O teste t par a par não ajusta a significância para o número de comparações: com '
                              'muitos tratamentos, a chance de apontar diferença que não existe cresce.')
    elif teste in ('snk', 'duncan'):
        diferente, critico = amplitudes(medias, n, qm, gl, alfa, teste)
        r['letras'] = letras(diferente, medias)
        r['amplitudes_criticas'] = critico
        r['pares'] = [{'i': i, 'j': j, 'diferenca': medias[i] - medias[j], 'p': None,
                       'difere': bool(diferente[i, j])} for i in range(k) for j in range(i + 1, k)]
        if teste == 'duncan':
            r['notas'].append('No teste de Duncan a significância vale para cada amplitude; o erro do conjunto de '
                              'comparações é maior que o nível escolhido.')
    elif teste == 'scott-knott':
        grupo, divisoes = scott_knott(medias, n[0], qm, gl, alfa)
        r['letras'] = [LETRAS[g] if g < len(LETRAS) else f'g{g + 1}' for g in grupo]
        r['grupos'] = grupo
        r['divisoes'] = divisoes
    else:
        if controle is None:
            raise ErroDeTeste('O teste de Dunnett compara cada tratamento com a testemunha: informe qual é, com '
                              '--testemunha "<nível>".')
        comparacoes, critico = dunnett(medias, n, qm, gl, alfa, controle)
        r['contra_testemunha'] = comparacoes
        r['critico'] = critico
        r['controle'] = controle
    return r


if __name__ == '__main__':
    rng = np.random.default_rng(7)

    # letras: três casos conhecidos
    assert letras(np.zeros((3, 3), bool), [3, 2, 1]) == ['a', 'a', 'a']
    d = np.zeros((3, 3), bool)
    d[0, 2] = d[2, 0] = True
    assert letras(d, [3, 2, 1]) == ['a', 'ab', 'b']
    d = ~np.eye(3, dtype=bool)
    assert letras(d, [1, 3, 2]) == ['c', 'a', 'b']

    grupos = [rng.normal(mu, 2.0, 5) for mu in (20, 21, 24, 27, 23)]
    medias = [g.mean() for g in grupos]
    n = [len(g) for g in grupos]
    gl = sum(n) - len(n)
    qm = sum(((g - g.mean()) ** 2).sum() for g in grupos) / gl

    # Tukey contra o scipy (um fator, variância conjunta)
    p, dms = tukey(medias, n, qm, gl, 0.05)
    if hasattr(stats, 'tukey_hsd'):
        ref = stats.tukey_hsd(*grupos).pvalue
        assert np.max(np.abs(p - ref)[~np.eye(5, dtype=bool)]) < 1e-6, np.max(np.abs(p - ref))
    # t (LSD) com dois grupos = teste t de variância conjunta
    a, b = grupos[0], grupos[3]
    qm2 = (((a - a.mean()) ** 2).sum() + ((b - b.mean()) ** 2).sum()) / 8
    p2, dms2 = teste_t([a.mean(), b.mean()], [5, 5], qm2, 8, 0.05)
    assert abs(p2[0, 1] - stats.ttest_ind(a, b).pvalue) < 1e-12
    # SNK: a faixa de 2 médias é o t; a faixa de todas é o Tukey. Duncan: a faixa de 2 é o t.
    _, c_snk = amplitudes(medias, n, qm, gl, 0.05, 'snk')
    _, c_dun = amplitudes(medias, n, qm, gl, 0.05, 'duncan')
    _, dms_t = teste_t(medias, n, qm, gl, 0.05)
    assert abs(c_snk[2] - dms_t) < 1e-6 and abs(c_snk[5] - dms) < 1e-9 and abs(c_dun[2] - dms_t) < 1e-6
    assert all(c_dun[q] <= c_snk[q] + 1e-9 for q in c_snk) and all(c_snk[q] < c_snk[q + 1] for q in range(2, 5))
    # proteção: média do meio não vira diferente só porque a faixa menor passaria
    dif, _ = amplitudes([10.0, 9.0, 8.0, 1.0], [4] * 4, 4.0, 12, 0.05, 'snk')
    assert not dif[0, 2] and dif[0, 3] and dif[2, 3]

    # Dunnett: com um tratamento só é o teste t; com vários, confere com o scipy quando existe
    comp, crit = dunnett([a.mean(), b.mean()], [5, 5], qm2, 8, 0.05, 0)
    assert abs(comp[0]['p'] - stats.ttest_ind(a, b).pvalue) < 1e-12 and abs(crit - stats.t.ppf(0.975, 8)) < 1e-12
    comp, crit = dunnett(medias, n, qm, gl, 0.05, 0)
    assert abs(_dunnett_dentro(crit, [math.sqrt(0.5)] * 4, gl) - 0.95) < 1e-6
    if hasattr(stats, 'dunnett'):
        ref = stats.dunnett(*grupos[1:], control=grupos[0]).pvalue
        assert max(abs(c['p'] - q) for c, q in zip(comp, ref)) < 3e-3, [(c['p'], q) for c, q in zip(comp, ref)]
    # com correlação zero entre comparações (b = 0) o resultado é o produto das margens da t... só no limite gl grande
    assert abs(_dunnett_dentro(1.959964, [0.0, 0.0], 100000) - 0.95 ** 2) < 1e-4

    # Scott-Knott: médias iguais não dividem; grupos afastados dividem; não muda com deslocamento e escala
    g, div = scott_knott([10.0, 10.1, 9.9, 10.05], 4, 1.0, 12, 0.05)
    assert g == [0, 0, 0, 0] and len(div) == 1 and not div[0]['dividiu']
    m = [30.0, 29.5, 20.0, 19.0, 10.0]
    g, div = scott_knott(m, 4, 1.0, 15, 0.05)
    assert g == [0, 0, 1, 1, 2], g
    g2, _ = scott_knott([100 + 3 * v for v in m], 4, 9.0, 15, 0.05)
    assert g2 == g
    # B0 pela definição: soma de quadrados entre os dois grupos de médias
    ms = np.array(sorted(m, reverse=True))
    b0 = 2 * (ms[:2].mean() - ms.mean()) ** 2 + 3 * (ms[2:].mean() - ms.mean()) ** 2
    sigma2 = (((ms - ms.mean()) ** 2).sum() + 15 * 1.0 / 4) / (5 + 15)
    assert abs(div[0]['lambda'] - math.pi / (2 * (math.pi - 2)) * b0 / sigma2) < 1e-9

    # porta única e recusas
    r = comparar(medias, n, qm, gl, 'tukey', 0.05)
    assert len(r['letras']) == 5 and r['dms'] is not None and len(r['pares']) == 10
    assert comparar(medias, n, qm, gl, 'scott-knott', 0.05)['letras'][int(np.argmax(medias))] == 'a'
    assert comparar(medias, n, qm, gl, 'dunnett', 0.05, controle=0)['letras'] is None
    for pedido, kw in (('snk', {}), ('duncan', {}), ('scott-knott', {})):
        try:
            comparar(medias, [5, 5, 4, 5, 5], qm, gl, pedido, 0.05, **kw)
            raise AssertionError('devia recusar repetições desiguais')
        except ErroDeTeste:
            pass
    try:
        comparar(medias, n, qm, gl, 'dunnett', 0.05)
        raise AssertionError('devia pedir a testemunha')
    except ErroDeTeste:
        pass
    assert comparar(medias, [5, 5, 4, 5, 5], qm, gl, 'tukey', 0.05)['dms'] is None
    print('medias OK')
