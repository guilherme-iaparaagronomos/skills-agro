"""Modelo linear dos delineamentos: quadro da análise de variância, resíduos,
pressupostos, transformações e regressão polinomial.

Um motor só serve a todos os delineamentos: cada fonte de variação entra no
modelo na ordem do quadro, e a soma de quadrados dela é o quanto a soma de
quadrados do resíduo cai quando ela entra. Em dado balanceado essa conta não
depende da ordem e dá o mesmo que as fórmulas dos livros (o teste embutido
confere as duas).

  dic           um fator, inteiramente casualizado (aceita repetições desiguais)
  dbc           um fator em blocos completos
  fatorial      dois fatores cruzados, em DIC ou em blocos
  subdividida   parcela subdividida em blocos: fator A na parcela, B na subparcela

Teste embutido: python scripts/modelo.py
"""

import math

import numpy as np
from scipy import stats


class ErroDeModelo(Exception):
    """Dado que o modelo não cobre; a mensagem vai para o usuário como está."""


# ------------------------------------------------------------------ motor
def indicadoras(codigos, quantos=None):
    codigos = np.asarray(codigos, int)
    quantos = int(codigos.max()) + 1 if quantos is None else quantos
    m = np.zeros((len(codigos), quantos))
    m[np.arange(len(codigos)), codigos] = 1.0
    return m


def cruzar(a, b):
    """Código da combinação de dois fatores (uma casela para cada par de níveis)."""
    a, b = np.asarray(a, int), np.asarray(b, int)
    return a * (int(b.max()) + 1) + b


def _ajuste(x, y):
    beta, _, posto, _ = np.linalg.lstsq(x, y, rcond=None)
    residuos = y - x @ beta
    return float(residuos @ residuos), int(posto), residuos


def sequencial(y, termos):
    """Soma de quadrados de cada termo, na ordem dada. Devolve (linhas, resíduo, matriz completa)."""
    y = np.asarray(y, float)
    x = np.ones((len(y), 1))
    sq_antes, posto_antes, _ = _ajuste(x, y)
    total = {'gl': len(y) - 1, 'sq': sq_antes}
    linhas = []
    for nome, matriz in termos:
        x = np.hstack([x, matriz])
        sq, posto, _ = _ajuste(x, y)
        linhas.append({'fonte': nome, 'gl': posto - posto_antes, 'sq': max(0.0, sq_antes - sq)})
        sq_antes, posto_antes = sq, posto
    sq, posto, residuos = _ajuste(x, y)
    return linhas, {'gl': len(y) - posto, 'sq': sq, 'residuos': residuos}, total, x


def _alavanca(x):
    u, s, _ = np.linalg.svd(x, full_matrices=False)
    posto = int((s > s.max() * 1e-10).sum())
    return (u[:, :posto] ** 2).sum(axis=1)


def _f(linha, erro):
    """Preenche QM, F e p de uma linha do quadro, contra o erro dado."""
    linha['qm'] = linha['sq'] / linha['gl'] if linha['gl'] > 0 else float('nan')
    if linha['gl'] > 0 and erro['gl'] > 0 and erro['qm'] > 0:
        linha['f'] = linha['qm'] / erro['qm']
        linha['p'] = float(stats.f.sf(linha['f'], linha['gl'], erro['gl']))
    else:
        linha['f'], linha['p'] = float('nan'), float('nan')
    return linha


# ------------------------------------------------------------------ quadro
def analisar(y, fatores, bloco=None, subdividida=False, nomes=None, nome_bloco='Blocos'):
    """Quadro da análise de variância do delineamento.

    y: respostas (sem faltantes); fatores: lista com 1 ou 2 vetores de códigos;
    bloco: vetor de códigos ou None. Devolve um dicionário com as linhas do quadro,
    o(s) erro(s), os resíduos e o que os testes de médias precisam.
    """
    y = np.asarray(y, float)
    fatores = [np.asarray(f, int) for f in fatores]
    nomes = list(nomes or ['Tratamentos', 'Fator B'][:len(fatores)])
    n = len(y)
    termos = []
    if bloco is not None:
        bloco = np.asarray(bloco, int)
        termos.append((nome_bloco, indicadoras(bloco)))
    if len(fatores) == 1:
        tipo = 'dbc' if bloco is not None else 'dic'
        termos.append((nomes[0], indicadoras(fatores[0])))
        caselas = fatores[0]
    elif len(fatores) == 2:
        if subdividida:
            if bloco is None:
                raise ErroDeModelo('A parcela subdividida está implementada só em blocos: informe a coluna do bloco.')
            tipo = 'subdividida'
            termos += [(nomes[0], indicadoras(fatores[0])), ('Erro (a)', indicadoras(cruzar(bloco, fatores[0]))),
                       (nomes[1], indicadoras(fatores[1])),
                       (f'{nomes[0]} × {nomes[1]}', indicadoras(cruzar(fatores[0], fatores[1])))]
        else:
            tipo = 'fatorial-dbc' if bloco is not None else 'fatorial-dic'
            termos += [(nomes[0], indicadoras(fatores[0])), (nomes[1], indicadoras(fatores[1])),
                       (f'{nomes[0]} × {nomes[1]}', indicadoras(cruzar(fatores[0], fatores[1])))]
        caselas = cruzar(fatores[0], fatores[1])
    else:
        raise ErroDeModelo('Esta versão cobre um ou dois fatores.')

    linhas, residuo, total, x = sequencial(y, termos)
    if residuo['gl'] < 1:
        raise ErroDeModelo('Não sobram graus de liberdade para o resíduo: sem repetição não há como estimar o erro '
                           'experimental.')
    residuo['qm'] = residuo['sq'] / residuo['gl']
    media = float(y.mean())
    r = {'tipo': tipo, 'n': n, 'media': media, 'nomes': nomes, 'nome_bloco': nome_bloco if bloco is not None else None}
    if tipo == 'subdividida':
        erro_a = next(l for l in linhas if l['fonte'] == 'Erro (a)')
        if erro_a['gl'] < 1:
            raise ErroDeModelo('Sem graus de liberdade no erro (a): a parcela subdividida precisa de pelo menos dois '
                               'blocos e dois níveis do fator da parcela.')
        erro_a['qm'] = erro_a['sq'] / erro_a['gl']
        erro_a['f'] = erro_a['p'] = float('nan')
        for l in linhas:
            if l['fonte'] in (nome_bloco, nomes[0]):
                _f(l, erro_a)
            elif l['fonte'] != 'Erro (a)':
                _f(l, residuo)
        r['erro_a'] = {'gl': erro_a['gl'], 'qm': erro_a['qm']}
        r['cv_a'] = 100 * math.sqrt(erro_a['qm']) / media if media else float('nan')
        nome_residuo = 'Erro (b)'
    else:
        for l in linhas:
            _f(l, residuo)
        nome_residuo = 'Resíduo'
    linhas.append({'fonte': nome_residuo, 'gl': residuo['gl'], 'sq': residuo['sq'], 'qm': residuo['qm'],
                   'f': float('nan'), 'p': float('nan')})
    linhas.append({'fonte': 'Total', 'gl': total['gl'], 'sq': total['sq'], 'qm': float('nan'), 'f': float('nan'),
                   'p': float('nan')})
    alavanca = _alavanca(x)
    padronizados = residuo['residuos'] / np.sqrt(np.maximum(residuo['qm'] * (1 - alavanca), 1e-300))
    padronizados[alavanca > 1 - 1e-9] = 0.0  # observação que o modelo reproduz exata não tem resíduo para padronizar
    r.update({'linhas': linhas, 'residuo': {'gl': residuo['gl'], 'qm': residuo['qm']},
              'cv': 100 * math.sqrt(residuo['qm']) / media if media else float('nan'),
              'residuos': residuo['residuos'], 'ajustados': y - residuo['residuos'], 'padronizados': padronizados,
              'caselas': caselas})
    return r


def linha(quadro, fonte):
    return next(l for l in quadro['linhas'] if l['fonte'] == fonte)


# ------------------------------------------------------------------ médias
def medias_por(y, codigos, quantos=None):
    """(médias, repetições, desvios-padrão) de y por nível de `codigos`."""
    y, codigos = np.asarray(y, float), np.asarray(codigos, int)
    quantos = int(codigos.max()) + 1 if quantos is None else quantos
    n = np.bincount(codigos, minlength=quantos).astype(float)
    soma = np.bincount(codigos, weights=y, minlength=quantos)
    media = soma / np.maximum(n, 1)
    sq = np.bincount(codigos, weights=(y - media[codigos]) ** 2, minlength=quantos)
    dp = np.sqrt(np.where(n > 1, sq / np.maximum(n - 1, 1), np.nan))
    return media, n, dp


def desdobrar(y, de, dentro, erro):
    """Efeito do fator `de` dentro de cada nível de `dentro`: SQ, GL, F e p de cada fatia.

    `erro` é {'gl', 'qm'}: o resíduo que testa as fatias.
    """
    y, de, dentro = np.asarray(y, float), np.asarray(de, int), np.asarray(dentro, int)
    fatias = []
    for nivel in range(int(dentro.max()) + 1):
        quais = dentro == nivel
        media, n, _ = medias_por(y[quais], de[quais], int(de.max()) + 1)
        geral = y[quais].mean()
        sq = float((n * (media - geral) ** 2).sum())
        gl = int((n > 0).sum()) - 1
        fatias.append(_f({'nivel': nivel, 'gl': gl, 'sq': sq, 'medias': media, 'n': n}, erro))
    return fatias


def erro_de_a_dentro_de_b(erro_a, erro_b, niveis_b):
    """Parcela subdividida: variância e graus de liberdade (Satterthwaite) para comparar níveis de A dentro de B."""
    qm = ((niveis_b - 1) * erro_b['qm'] + erro_a['qm']) / niveis_b
    gl = ((niveis_b - 1) * erro_b['qm'] + erro_a['qm']) ** 2 / (
        ((niveis_b - 1) * erro_b['qm']) ** 2 / erro_b['gl'] + erro_a['qm'] ** 2 / erro_a['gl'])
    return {'qm': qm, 'gl': gl}


# ------------------------------------------------------------------ pressupostos
def pressupostos(quadro, limite_discrepante=3.0):
    """Normalidade dos resíduos, homogeneidade de variâncias entre as caselas e resíduos discrepantes."""
    res, caselas = quadro['residuos'], quadro['caselas']
    saida = {'shapiro': None, 'bartlett': None, 'levene': None, 'notas': []}
    if 3 <= len(res) <= 5000 and np.ptp(res) > 0:
        w, p = stats.shapiro(res)
        saida['shapiro'] = {'w': float(w), 'p': float(p)}
    else:
        saida['notas'].append('Shapiro-Wilk não calculado (precisa de 3 a 5.000 resíduos que não sejam todos iguais).')
    grupos = [res[caselas == c] for c in np.unique(caselas)]
    grupos = [g for g in grupos if len(g) >= 2]
    com_variacao = [g for g in grupos if np.ptp(g) > 0]
    if len(grupos) >= 2 and len(com_variacao) == len(grupos):
        est, p = stats.bartlett(*grupos)
        saida['bartlett'] = {'estatistica': float(est), 'p': float(p)}
    else:
        saida['notas'].append('Bartlett não calculado (precisa de pelo menos dois grupos com duas ou mais repetições '
                              'e variação dentro de cada um).')
    if len(grupos) >= 2 and all(len(g) >= 3 for g in grupos):
        est, p = stats.levene(*grupos, center='median')
        saida['levene'] = {'estatistica': float(est), 'p': float(p)}
    else:
        saida['notas'].append('Levene não calculado (precisa de três ou mais repetições por grupo).')
    if quadro['tipo'] != 'dic':
        saida['notas'].append('Em blocos e em fatorial os testes de variância usam os resíduos do modelo agrupados '
                              'por tratamento: o resultado é aproximado.')
    pad = quadro['padronizados']
    saida['discrepantes'] = [{'linha': int(i), 'residuo_padronizado': float(pad[i])}
                             for i in np.nonzero(np.abs(pad) > limite_discrepante)[0]]
    saida['limite_discrepante'] = limite_discrepante
    return saida


TRANSFORMACOES = {
    'log': 'log(x)',
    'log1': 'log(x + 1)',
    'raiz': 'raiz(x)',
    'raiz05': 'raiz(x + 0,5)',
    'arcsen': 'arcsen(raiz(x/100))',
}


def transformar(y, qual):
    """Devolve (y transformado, descrição). Recusa a transformação que o dado não aceita."""
    y = np.asarray(y, float)
    if qual in (None, '', 'nenhuma'):
        return y, 'sem transformação'
    if qual == 'log':
        if (y <= 0).any():
            raise ErroDeModelo('log(x) não aceita zero nem valor negativo; veja log1, que usa log(x + 1).')
        return np.log(y), TRANSFORMACOES[qual]
    if qual == 'log1':
        if (y < 0).any():
            raise ErroDeModelo('log(x + 1) não aceita valor negativo.')
        return np.log1p(y), TRANSFORMACOES[qual]
    if qual in ('raiz', 'raiz05'):
        if (y < 0).any():
            raise ErroDeModelo('A raiz quadrada não aceita valor negativo.')
        return np.sqrt(y + (0.5 if qual == 'raiz05' else 0.0)), TRANSFORMACOES[qual]
    if qual == 'arcsen':
        if (y < 0).any() or (y > 100).any():
            raise ErroDeModelo('arcsen(raiz(x/100)) é para porcentagem, de 0 a 100 (ou proporção, de 0 a 1).')
        if y.max() <= 1:
            return np.arcsin(np.sqrt(y)), 'arcsen(raiz(x)), com x em proporção de 0 a 1'
        return np.arcsin(np.sqrt(y / 100.0)), TRANSFORMACOES[qual]
    raise ErroDeModelo(f'Transformação desconhecida: {qual}. As que existem: {", ".join(TRANSFORMACOES)}.')


def painel_de_transformacoes(y, **modelo):
    """Para a escala original e cada transformação que o dado aceita: CV e os p dos pressupostos. Só mostra."""
    painel = []
    for qual in ['nenhuma'] + list(TRANSFORMACOES):
        try:
            yt, descricao = transformar(y, qual)
            quadro = analisar(yt, **modelo)
        except ErroDeModelo as e:
            painel.append({'transformacao': qual, 'descricao': TRANSFORMACOES.get(qual, 'sem transformação'),
                           'recusada': str(e)})
            continue
        p = pressupostos(quadro)
        painel.append({'transformacao': qual, 'descricao': descricao, 'cv': quadro['cv'],
                       'shapiro_p': p['shapiro'] and p['shapiro']['p'],
                       'bartlett_p': p['bartlett'] and p['bartlett']['p'],
                       'levene_p': p['levene'] and p['levene']['p'], 'discrepantes': len(p['discrepantes'])})
    return painel


# ------------------------------------------------------------------ regressão
NOMES_DE_GRAU = {1: 'linear', 2: 'quadrática', 3: 'cúbica'}


def regressao(y, doses, fator, bloco=None, grau_maximo=3, nome_bloco='Blocos', nome_fator='Tratamentos'):
    """Desdobra os graus de liberdade de um fator quantitativo em regressão polinomial.

    y: respostas; doses: o valor numérico do nível em cada observação; fator: o
    código do nível. Devolve o quadro (blocos, tratamentos, cada grau, desvios e
    resíduo) e, para cada grau, a equação ajustada às médias e o R².
    """
    y, doses, fator = np.asarray(y, float), np.asarray(doses, float), np.asarray(fator, int)
    niveis = int(fator.max()) + 1
    if niveis < 3:
        raise ErroDeModelo('A regressão precisa de pelo menos três níveis do fator quantitativo.')
    grau_maximo = int(min(grau_maximo, 3, niveis - 1))
    base = analisar(y, [fator], bloco, nomes=[nome_fator], nome_bloco=nome_bloco)
    residuo = base['residuo']
    z = (doses - doses.mean()) / (doses.std() or 1.0)
    termos = [] if bloco is None else [(nome_bloco, indicadoras(np.asarray(bloco, int)))]
    termos += [(f'Regressão {NOMES_DE_GRAU[g]}', (z ** g)[:, None]) for g in range(1, grau_maximo + 1)]
    termos.append(('Desvios da regressão', indicadoras(fator)))
    linhas, _, total, _ = sequencial(y, termos)
    tratamentos = dict(linha(base, nome_fator))
    quadro = []
    for l in linhas:
        if l['fonte'] == nome_bloco:
            quadro.append(_f(l, residuo))
            quadro.append(tratamentos)
        elif l['fonte'] == 'Desvios da regressão' and l['gl'] < 1:
            continue
        else:
            l['fonte'] = '  ' + l['fonte']
            quadro.append(_f(l, residuo))
    if bloco is None:
        quadro.insert(0, tratamentos)
    quadro.append({'fonte': 'Resíduo', 'gl': residuo['gl'], 'sq': residuo['gl'] * residuo['qm'], 'qm': residuo['qm'],
                   'f': float('nan'), 'p': float('nan')})
    quadro.append({'fonte': 'Total', 'gl': total['gl'], 'sq': total['sq'], 'qm': float('nan'), 'f': float('nan'),
                   'p': float('nan')})
    media, n, _ = medias_por(y, fator, niveis)
    x = np.array([doses[fator == k][0] for k in range(niveis)])
    equacoes = []
    acumulada = 0.0
    for g in range(1, grau_maximo + 1):
        acumulada += next(l['sq'] for l in quadro if l['fonte'].strip() == f'Regressão {NOMES_DE_GRAU[g]}')
        coef = np.polyfit(x, media, g, w=np.sqrt(n))[::-1]      # do termo constante para o de maior grau
        eq = {'grau': g, 'nome': NOMES_DE_GRAU[g], 'coeficientes': [float(c) for c in coef],
              'r2': acumulada / tratamentos['sq'] if tratamentos['sq'] > 0 else float('nan')}
        if g == 2 and coef[2] != 0:
            vertice = -coef[1] / (2 * coef[2])
            if x.min() <= vertice <= x.max():
                eq['vertice'] = {'x': float(vertice), 'y': float(np.polyval(coef[::-1], vertice)),
                                 'tipo': 'máximo' if coef[2] < 0 else 'mínimo'}
        equacoes.append(eq)
    base.update({'linhas': quadro, 'equacoes': equacoes, 'doses': x, 'medias_por_dose': media, 'n_por_dose': n,
                 'grau_maximo': grau_maximo})
    return base


if __name__ == '__main__':
    rng = np.random.default_rng(11)

    # ---- DIC desbalanceado: o F do scipy e a fórmula do livro
    grupos = [rng.normal(mu, 3.0, k) for mu, k in ((50, 5), (54, 4), (47, 5), (58, 6))]
    y = np.concatenate(grupos)
    trat = np.concatenate([[i] * len(g) for i, g in enumerate(grupos)])
    q = analisar(y, [trat])
    ref = stats.f_oneway(*grupos)
    lt = linha(q, 'Tratamentos')
    assert q['tipo'] == 'dic' and abs(lt['f'] - ref.statistic) < 1e-9 and abs(lt['p'] - ref.pvalue) < 1e-12
    sq_livro = sum(len(g) * (g.mean() - y.mean()) ** 2 for g in grupos)
    assert abs(lt['sq'] - sq_livro) < 1e-8 and lt['gl'] == 3 and q['residuo']['gl'] == 16
    assert abs(sum(l['sq'] for l in q['linhas'][:-1]) - q['linhas'][-1]['sq']) < 1e-8
    assert abs(q['cv'] - 100 * math.sqrt(q['residuo']['qm']) / y.mean()) < 1e-12

    # ---- DBC: fórmulas do livro
    t, b = 5, 4
    trat = np.repeat(np.arange(t), b)
    bloco = np.tile(np.arange(b), t)
    y = 40 + 2.0 * trat + 1.5 * bloco + rng.normal(0, 1.2, t * b)
    q = analisar(y, [trat], bloco)
    c = y.sum() ** 2 / (t * b)
    sq_t = sum(y[trat == i].sum() ** 2 for i in range(t)) / b - c
    sq_b = sum(y[bloco == j].sum() ** 2 for j in range(b)) / t - c
    sq_tot = (y ** 2).sum() - c
    assert q['tipo'] == 'dbc' and abs(linha(q, 'Tratamentos')['sq'] - sq_t) < 1e-8
    assert abs(linha(q, 'Blocos')['sq'] - sq_b) < 1e-8 and abs(linha(q, 'Resíduo')['sq'] - (sq_tot - sq_t - sq_b)) < 1e-8
    assert linha(q, 'Resíduo')['gl'] == (t - 1) * (b - 1) and abs(q['residuos'].sum()) < 1e-9
    # resíduo padronizado: alavanca de um DBC é (t + b - 1) / (t b)
    h = (t + b - 1) / (t * b)
    assert np.allclose(q['padronizados'], q['residuos'] / math.sqrt(q['residuo']['qm'] * (1 - h)))

    # ---- fatorial em DIC e em DBC: SQ das caselas = A + B + AxB; o desdobramento fecha com A + AxB
    a_n, b_n, r = 3, 4, 4
    fa = np.repeat(np.arange(a_n), b_n * r)
    fb = np.tile(np.repeat(np.arange(b_n), r), a_n)
    rep = np.tile(np.arange(r), a_n * b_n)
    y = 10 + 2 * fa + 1.0 * fb + 1.5 * (fa == 2) * (fb == 3) + rng.normal(0, 1, a_n * b_n * r)
    q = analisar(y, [fa, fb], nomes=['Cultivar', 'Dose'])
    c = y.sum() ** 2 / len(y)
    sq_a = sum(y[fa == i].sum() ** 2 for i in range(a_n)) / (b_n * r) - c
    sq_b = sum(y[fb == j].sum() ** 2 for j in range(b_n)) / (a_n * r) - c
    sq_cel = sum(y[(fa == i) & (fb == j)].sum() ** 2 for i in range(a_n) for j in range(b_n)) / r - c
    assert q['tipo'] == 'fatorial-dic' and abs(linha(q, 'Cultivar')['sq'] - sq_a) < 1e-8
    assert abs(linha(q, 'Dose')['sq'] - sq_b) < 1e-8
    assert abs(linha(q, 'Cultivar × Dose')['sq'] - (sq_cel - sq_a - sq_b)) < 1e-8
    assert linha(q, 'Cultivar × Dose')['gl'] == 6 and linha(q, 'Resíduo')['gl'] == a_n * b_n * (r - 1)
    fatias = desdobrar(y, fa, fb, q['residuo'])
    assert abs(sum(f['sq'] for f in fatias) - (sq_a + sq_cel - sq_a - sq_b)) < 1e-8 and all(f['gl'] == 2 for f in fatias)
    qb = analisar(y, [fa, fb], rep, nomes=['Cultivar', 'Dose'])
    assert qb['tipo'] == 'fatorial-dbc' and linha(qb, 'Resíduo')['gl'] == (a_n * b_n - 1) * (r - 1)
    assert abs(linha(qb, 'Cultivar')['sq'] - sq_a) < 1e-8

    # ---- parcela subdividida: erro (a) = blocos x A; A e blocos são testados contra ele
    qs = analisar(y, [fa, fb], rep, subdividida=True, nomes=['Cultivar', 'Dose'])
    sq_bl = sum(y[rep == k].sum() ** 2 for k in range(r)) / (a_n * b_n) - c
    sq_parc = sum(y[(fa == i) & (rep == k)].sum() ** 2 for i in range(a_n) for k in range(r)) / b_n - c
    ea = linha(qs, 'Erro (a)')
    assert abs(ea['sq'] - (sq_parc - sq_bl - sq_a)) < 1e-8 and ea['gl'] == (a_n - 1) * (r - 1)
    assert abs(linha(qs, 'Cultivar')['f'] - (sq_a / (a_n - 1)) / ea['qm']) < 1e-9
    assert linha(qs, 'Erro (b)')['gl'] == a_n * (b_n - 1) * (r - 1)
    assert abs(linha(qs, 'Dose')['f'] - linha(qs, 'Dose')['qm'] / qs['residuo']['qm']) < 1e-12
    e = erro_de_a_dentro_de_b(qs['erro_a'], qs['residuo'], b_n)
    assert min(qs['erro_a']['gl'], qs['residuo']['gl']) <= e['gl'] <= qs['erro_a']['gl'] + qs['residuo']['gl']
    try:
        analisar(y, [fa, fb], subdividida=True)
        raise AssertionError('subdividida sem bloco devia ser recusada')
    except ErroDeModelo:
        pass

    # ---- sem repetição: recusa
    try:
        analisar(np.arange(6.0), [np.arange(6)])
        raise AssertionError('devia recusar')
    except ErroDeModelo:
        pass

    # ---- pressupostos e transformações
    p = pressupostos(q)
    assert p['shapiro'] and p['bartlett'] and p['levene'] and 0 <= p['shapiro']['p'] <= 1
    y_ruim = y.copy()
    y_ruim[0] += 25
    assert pressupostos(analisar(y_ruim, [fa, fb]))['discrepantes'][0]['linha'] == 0
    yt, desc = transformar(np.array([0.0, 25.0, 100.0]), 'arcsen')
    assert abs(yt[1] - math.asin(0.5)) < 1e-12 and '100' in desc
    assert 'proporção' in transformar(np.array([0.0, 0.25, 1.0]), 'arcsen')[1]
    for ruim, qual in (([-1.0, 2.0], 'raiz'), ([0.0, 2.0], 'log'), ([10.0, 120.0], 'arcsen')):
        try:
            transformar(np.array(ruim), qual)
            raise AssertionError(qual)
        except ErroDeModelo:
            pass
    painel = painel_de_transformacoes(np.exp(y / 3), fatores=[fa, fb])   # passa de 100: o arcsen recusa
    assert [x['transformacao'] for x in painel] == ['nenhuma', 'log', 'log1', 'raiz', 'raiz05', 'arcsen']
    assert 'recusada' in painel[-1] and painel[1]['cv'] > 0

    # ---- regressão: os graus somam os tratamentos; a equação reproduz uma parábola sem erro
    doses = np.repeat([0.0, 50.0, 100.0, 150.0, 200.0], 4)
    fator = np.repeat(np.arange(5), 4)
    blo = np.tile(np.arange(4), 5)
    yq = 2000 + 12 * doses - 0.04 * doses ** 2 + 30 * blo + rng.normal(0, 60, 20)
    rg = regressao(yq, doses, fator, blo)
    nomes = [l['fonte'].strip() for l in rg['linhas']]
    assert nomes == ['Blocos', 'Tratamentos', 'Regressão linear', 'Regressão quadrática', 'Regressão cúbica',
                     'Desvios da regressão', 'Resíduo', 'Total'], nomes
    partes = sum(l['sq'] for l in rg['linhas'][2:6])
    assert abs(partes - rg['linhas'][1]['sq']) < 1e-6 and sum(l['gl'] for l in rg['linhas'][2:6]) == 4
    exata = regressao(2000 + 12 * doses - 0.04 * doses ** 2 + rng.normal(0, 1e-9, 20), doses, fator)
    c0, c1, c2 = exata['equacoes'][1]['coeficientes']
    assert abs(c0 - 2000) < 1e-4 and abs(c1 - 12) < 1e-6 and abs(c2 + 0.04) < 1e-8
    assert abs(exata['equacoes'][1]['r2'] - 1) < 1e-9 and abs(exata['equacoes'][1]['vertice']['x'] - 150) < 1e-4
    assert exata['equacoes'][1]['vertice']['tipo'] == 'máximo' and [l['fonte'] for l in exata['linhas']][0] == 'Tratamentos'
    assert regressao(yq[:12], doses[:12], fator[:12])['grau_maximo'] == 2
    print('modelo OK')
