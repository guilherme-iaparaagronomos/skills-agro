"""A sequência da análise de um ensaio: diagnóstico e, depois, a análise com o
teste e a significância que o usuário escolheu.

  diagnosticar(ens)  descreve o ensaio, o quadro da análise de variância, os
                     pressupostos, o painel de transformações e, se o fator é
                     quantitativo, os graus da regressão. Não compara médias.
  rodar(ens, ...)    a análise completa. Sem teste e sem significância não roda.

Nada aqui escolhe pelo usuário: teste, significância, transformação e grau da
regressão vêm de fora. O que o texto diz é o resultado no nível escolhido.

Teste embutido: python scripts/ensaio.py
"""

import numpy as np

import medias as mod_medias
import modelo
from leitura import chave


class ErroDeAnalise(Exception):
    """Pedido incompleto ou que a skill não cobre; a mensagem vai para o usuário como está."""


def num(v, casas=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return '—'
    texto = f'{float(v):,.{casas}f}'
    return texto.replace(',', '§').replace('.', ',').replace('§', '.')


def p_txt(p):
    if p is None or not np.isfinite(p):
        return '—'
    return '<0,0001' if p < 0.0001 else f'{p:.4f}'.replace('.', ',')


def p_igual(p):
    """'p = 0,0312' ou 'p < 0,0001', para as frases."""
    texto = p_txt(p)
    return f'p {texto[0]} {texto[1:]}' if texto.startswith('<') else f'p = {texto}'


def pct(alfa):
    return format(100 * alfa, '.4g').replace('.', ',')


def ler_alfa(texto):
    """'5', '5%', '0,05' ou '0.05' viram 0.05. Recusa o que não for uma significância usual."""
    if texto is None:
        return None
    bruto = str(texto).strip().replace('%', '').replace(',', '.')
    try:
        valor = float(bruto)
    except ValueError:
        raise ErroDeAnalise(f'Significância não entendida: "{texto}". Use, por exemplo, 5 (para 5%) ou 0,05.')
    if valor >= 1:
        valor /= 100.0
    if not 0.0001 <= valor <= 0.25:
        raise ErroDeAnalise(f'Significância fora do usual: "{texto}". Informe entre 0,01% e 25% (o comum é 5% ou 1%).')
    return valor


def _modelo(ens):
    return dict(fatores=[f['codigos'] for f in ens['fatores']], bloco=ens['bloco'] and ens['bloco']['codigos'],
                subdividida=ens['tipo'] == 'subdividida', nomes=[f['nome'] for f in ens['fatores']])


def quantitativo(ens):
    """O fator único tem níveis numéricos (três ou mais)? Então a regressão é possível."""
    f = ens['fatores'][0]
    return ens['tipo'] in ('dic', 'dbc') and f['valores'] is not None and len(f['valores']) >= 3


def _descritiva(ens, y):
    linhas = []
    f1 = ens['fatores'][0]
    if len(ens['fatores']) == 1:
        caselas, rotulos = f1['codigos'], f1['rotulos']
    else:
        f2 = ens['fatores'][1]
        caselas = modelo.cruzar(f1['codigos'], f2['codigos'])
        rotulos = [f'{a} · {b}' for a in f1['rotulos'] for b in f2['rotulos']]
    for c, rotulo in enumerate(rotulos):
        v = y[caselas == c]
        if not len(v):
            continue
        dp = float(v.std(ddof=1)) if len(v) > 1 else float('nan')
        linhas.append({'nivel': rotulo, 'n': int(len(v)), 'media': float(v.mean()), 'dp': dp, 'minimo': float(v.min()),
                       'maximo': float(v.max()), 'cv': 100 * dp / v.mean() if v.mean() else float('nan')})
    return linhas


def _doses(ens):
    f = ens['fatores'][0]
    return np.array(f['valores'])[f['codigos']]


def diagnosticar(ens, transformacao=None):
    y, descricao_t = modelo.transformar(ens['y'], transformacao)
    quadro = modelo.analisar(y, **_modelo(ens))
    d = {'tipo': ens['tipo'], 'descricao': ens['descricao'], 'resposta': ens['resposta'],
         'transformacao': {'chave': transformacao or 'nenhuma', 'descricao': descricao_t},
         'n': int(len(y)), 'media': quadro['media'], 'cv': quadro['cv'], 'cv_a': quadro.get('cv_a'),
         'quadro': quadro['linhas'], 'pressupostos': modelo.pressupostos(quadro),
         'descritiva': _descritiva(ens, ens['y']),
         'painel': modelo.painel_de_transformacoes(ens['y'], **_modelo(ens)),
         'avisos': list(ens['avisos']), 'perdidas': ens['perdidas'], 'quantitativo': quantitativo(ens),
         'regressao': None, '_quadro': quadro}
    if d['quantitativo']:
        f = ens['fatores'][0]
        rg = modelo.regressao(y, _doses(ens), f['codigos'], ens['bloco'] and ens['bloco']['codigos'],
                              nome_fator=f['nome'])
        d['regressao'] = {'quadro': rg['linhas'], 'equacoes': rg['equacoes'], 'grau_maximo': rg['grau_maximo']}
    testes = dict(mod_medias.TESTES)
    if not ens['balanceado']:
        for t in mod_medias.SO_BALANCEADO:
            testes.pop(t)
    if len(ens['fatores']) > 1:
        testes.pop('dunnett')
    d['testes_possiveis'] = testes
    return d


def _nivel(rotulos, pedido, o_que):
    if pedido in rotulos:
        return rotulos.index(pedido)
    iguais = [i for i, r in enumerate(rotulos) if chave(r) == chave(pedido)]
    if len(iguais) == 1:
        return iguais[0]
    raise ErroDeAnalise(f'{o_que} "{pedido}" não é um nível do fator. Os níveis são: {", ".join(rotulos)}.')


def _comparacao(titulo, fator, rotulos, y, y_original, codigos, erro, nome_do_erro, teste, alfa, controle=None,
                dentro=None, f=None):
    media, n, _ = modelo.medias_por(y, codigos, len(rotulos))
    original, _, dp = modelo.medias_por(y_original, codigos, len(rotulos))
    try:
        t = mod_medias.comparar(media, n, erro['qm'], erro['gl'], teste, alfa, controle)
    except mod_medias.ErroDeTeste as e:
        raise ErroDeAnalise(str(e))
    return {'titulo': titulo, 'fator': fator, 'dentro': dentro, 'niveis': list(rotulos),
            'medias': [float(v) for v in media], 'medias_originais': [float(v) for v in original],
            'dp': [float(v) for v in dp], 'n': [int(v) for v in n], 'letras': t['letras'], 'teste': t,
            'erro': {'qm': float(erro['qm']), 'gl': float(erro['gl']), 'nome': nome_do_erro},
            'ep': [float(np.sqrt(erro['qm'] / v)) for v in n], 'f': f}


def rodar(ens, teste=None, alfa=None, transformacao=None, testemunha=None, regressao=False, grau=None,
          desdobrar='auto'):
    """A análise completa. Devolve um dicionário com o quadro, os pressupostos, as comparações e os avisos."""
    if alfa is None:
        raise ErroDeAnalise('Falta a significância. A skill não escolhe: pergunte ao usuário e informe com --alfa '
                            '(por exemplo, --alfa 5 para 5%).')
    if regressao:
        if not quantitativo(ens):
            raise ErroDeAnalise('A regressão vale para ensaio de um fator com três ou mais níveis numéricos (doses, '
                                'épocas, densidades). Neste ensaio, use um teste de médias.')
    elif teste is None:
        raise ErroDeAnalise('Falta o teste de comparação de médias. A skill não escolhe: pergunte ao usuário e informe '
                            f'com --teste. Os que existem: {", ".join(mod_medias.TESTES)}.')
    elif teste not in mod_medias.TESTES:
        raise ErroDeAnalise(f'Teste desconhecido: "{teste}". Os que existem: {", ".join(mod_medias.TESTES)}.')
    try:
        y, descricao_t = modelo.transformar(ens['y'], transformacao)
        quadro = modelo.analisar(y, **_modelo(ens))
    except modelo.ErroDeModelo as e:
        raise ErroDeAnalise(str(e))
    if not quadro['residuo']['qm'] > 1e-12 * max(1.0, quadro['media'] ** 2):
        raise ErroDeAnalise('O resíduo deu zero: as repetições de cada tratamento têm todas o mesmo valor. Sem variação '
                            'entre repetições não há o que testar; confira a planilha.')
    transformado = transformacao not in (None, '', 'nenhuma')
    fatores = ens['fatores']
    r = {'tipo': ens['tipo'], 'descricao': ens['descricao'], 'resposta': ens['resposta'], 'alfa': alfa,
         'transformacao': {'chave': transformacao or 'nenhuma', 'descricao': descricao_t, 'aplicada': transformado},
         'n': int(len(y)), 'media': quadro['media'], 'media_original': float(np.mean(ens['y'])),
         'cv': quadro['cv'], 'cv_a': quadro.get('cv_a'),
         'quadro': quadro['linhas'], 'residuo': quadro['residuo'], 'erro_a': quadro.get('erro_a'),
         'pressupostos': modelo.pressupostos(quadro), 'comparacoes': [], 'tabela_dupla': None, 'regressao': None,
         'avisos': list(ens['avisos']), 'frases': [], 'perdidas': ens['perdidas'], 'teste': None,
         'nome_do_teste': None, 'fatores': [{'nome': f['nome'], 'niveis': f['rotulos']} for f in fatores],
         '_quadro': quadro}
    a = pct(alfa)

    def frase_f(fonte):
        l = modelo.linha(quadro, fonte)
        sig = l['p'] < alfa
        r['frases'].append(f'Teste F para {fonte}: F = {num(l["f"], 2)}, {p_igual(l["p"])} — '
                           f'{"significativo" if sig else "não significativo"} a {a}%.')
        return sig

    for nome, chave_p, rotulo in (('shapiro', 'Shapiro-Wilk (normalidade dos resíduos)', None),
                                  ('bartlett', 'Bartlett (variâncias homogêneas)', None),
                                  ('levene', 'Levene (variâncias homogêneas)', None)):
        t = r['pressupostos'][nome]
        if t and t['p'] < 0.05:
            r['avisos'].append(f'Pressuposto, na escala desta análise ({descricao_t}): {chave_p} deu '
                               f'{p_igual(t["p"])}, abaixo de 0,05. O diagnóstico mostra o que cada transformação '
                               'faria; a decisão de transformar é do usuário.')
    if r['pressupostos']['discrepantes']:
        quais = ', '.join(str(int(ens['linhas'][d['linha']]) + 2) for d in r['pressupostos']['discrepantes'][:8])
        r['avisos'].append(f'Resíduo padronizado acima de {num(r["pressupostos"]["limite_discrepante"], 0)} em módulo '
                           f'na(s) linha(s) {quais} do arquivo: confira se o valor foi digitado certo. Nada foi retirado.')
    if transformado:
        r['avisos'].append(f'A análise foi feita na escala transformada ({descricao_t}). As letras valem para essa '
                           'escala; a tabela traz também a média na escala original.')

    f1 = fatores[0]
    # ---------------------------------------------------------------- um fator
    if len(fatores) == 1:
        significativo = frase_f(f1['nome'])
        if regressao:
            rg = modelo.regressao(y, _doses(ens), f1['codigos'], ens['bloco'] and ens['bloco']['codigos'],
                                  nome_fator=f1['nome'])
            if grau is None:
                raise ErroDeAnalise('Falta o grau da regressão. A skill não escolhe: mostre ao usuário a tabela dos '
                                    f'graus do diagnóstico e informe com --grau (de 1 a {rg["grau_maximo"]}).')
            if not 1 <= grau <= rg['grau_maximo']:
                raise ErroDeAnalise(f'Grau {grau} não dá: com {len(f1["rotulos"])} níveis, vai de 1 a {rg["grau_maximo"]}.')
            original, _, _ = modelo.medias_por(ens['y'], f1['codigos'], len(f1['rotulos']))
            r['regressao'] = {'quadro': rg['linhas'], 'equacoes': rg['equacoes'], 'grau': grau,
                              'doses': [float(v) for v in rg['doses']],
                              'medias': [float(v) for v in rg['medias_por_dose']],
                              'medias_originais': [float(v) for v in original],
                              'n': [int(v) for v in rg['n_por_dose']], 'fator': f1['nome'], 'niveis': f1['rotulos']}
            r['quadro'] = rg['linhas']
            for l in rg['linhas']:
                if l['fonte'].strip().startswith(('Regressão', 'Desvios')):
                    sig = l['p'] < alfa
                    r['frases'].append(f'{l["fonte"].strip()}: F = {num(l["f"], 2)}, {p_igual(l["p"])} — '
                                       f'{"significativo" if sig else "não significativo"} a {a}%.')
            escolhida = rg['equacoes'][grau - 1]
            desvios = next((l for l in rg['linhas'] if l['fonte'].strip() == 'Desvios da regressão'), None)
            if desvios and grau == rg['grau_maximo'] and desvios['p'] < alfa:
                r['avisos'].append(f'Os desvios da regressão foram significativos a {a}%: o polinômio de grau '
                                   f'{rg["grau_maximo"]} não descreve tudo o que as médias fazem.')
            componente = next(l for l in rg['linhas'] if l['fonte'].strip() == f'Regressão {escolhida["nome"]}')
            if componente['p'] >= alfa:
                r['avisos'].append(f'O componente de grau {grau} ({escolhida["nome"]}) não foi significativo a {a}% '
                                   f'({p_igual(componente["p"])}); a equação desse grau foi ajustada porque foi o pedido.')
            return r
        controle = None
        if teste == 'dunnett':
            if testemunha is None:
                raise ErroDeAnalise('O teste de Dunnett compara cada tratamento com a testemunha: informe qual é com '
                                    f'--testemunha. Os níveis são: {", ".join(f1["rotulos"])}.')
            controle = _nivel(f1['rotulos'], testemunha, 'A testemunha')
        r['teste'], r['nome_do_teste'] = teste, mod_medias.TESTES[teste]
        r['comparacoes'].append(_comparacao(f'Médias de {f1["nome"]}', f1['nome'], f1['rotulos'], y, ens['y'],
                                            f1['codigos'], quadro['residuo'], 'Resíduo', teste, alfa, controle))
        if not significativo:
            r['avisos'].append(f'O teste F para {f1["nome"]} não foi significativo a {a}%. O teste de médias foi '
                               'rodado porque foi o pedido; t, SNK e Duncan costumam ser usados só depois de um F '
                               'significativo.')
        if f1['valores'] is not None and len(f1['valores']) >= 3:
            r['avisos'].append(f'Os níveis de {f1["nome"]} são numéricos. Se forem doses ou outro fator quantitativo, '
                               'a regressão (--regressao) descreve a resposta ao longo deles; o teste de médias foi '
                               'rodado porque foi o pedido.')
        return r

    # ---------------------------------------------------------------- dois fatores
    if regressao:
        raise ErroDeAnalise('A regressão está implementada para ensaio de um fator. Em fatorial, esta versão compara '
                            'médias.')
    if teste == 'dunnett':
        raise ErroDeAnalise('O teste de Dunnett está implementado para ensaio de um fator (cada tratamento contra a '
                            'testemunha). Em fatorial e em parcela subdividida, escolha outro teste.')
    r['teste'], r['nome_do_teste'] = teste, mod_medias.TESTES[teste]
    f2 = fatores[1]
    for f in fatores:
        if f['valores'] is not None and len(f['valores']) >= 3:
            r['avisos'].append(f'Os níveis de {f["nome"]} são numéricos. Esta versão não faz regressão dentro de '
                               'fatorial: esses níveis foram comparados pelo teste de médias pedido, como níveis separados.')
    interacao = f'{f1["nome"]} × {f2["nome"]}'
    sub = ens['tipo'] == 'subdividida'
    sig_a, sig_b, sig_ab = frase_f(f1['nome']), frase_f(f2['nome']), frase_f(interacao)
    if desdobrar not in ('auto', 'sim', 'nao'):
        raise ErroDeAnalise('--desdobrar aceita auto, sim ou nao.')
    faz = sig_ab if desdobrar == 'auto' else desdobrar == 'sim'
    r['desdobrou'] = bool(faz)
    erro_a = quadro['erro_a'] if sub else quadro['residuo']
    erro_b = quadro['residuo']
    blocos = ens['repeticoes']
    if not faz:
        r['frases'].append(f'A interação {interacao} {"" if sig_ab else "não "}foi significativa a {a}%'
                           + ('; as médias foram comparadas por fator, como pedido.' if sig_ab else
                              ': as médias são comparadas por fator, na média do outro.'))
        if sig_ab:
            r['avisos'].append(f'A interação foi significativa a {a}% e o desdobramento foi desligado a pedido: a '
                               'média de um fator esconde o que muda de um nível para outro do outro fator.')
        r['comparacoes'].append(_comparacao(f'Médias de {f1["nome"]}', f1['nome'], f1['rotulos'], y, ens['y'],
                                            f1['codigos'], erro_a, 'Erro (a)' if sub else 'Resíduo', teste, alfa))
        r['comparacoes'].append(_comparacao(f'Médias de {f2["nome"]}', f2['nome'], f2['rotulos'], y, ens['y'],
                                            f2['codigos'], erro_b, 'Erro (b)' if sub else 'Resíduo', teste, alfa))
        for sig, f in ((sig_a, f1), (sig_b, f2)):
            if not sig:
                r['avisos'].append(f'O teste F para {f["nome"]} não foi significativo a {a}%; as letras desse fator '
                                   'são do teste pedido.')
        return r

    r['frases'].append(f'A interação {interacao} {"foi significativa" if sig_ab else "não foi significativa"} a {a}%'
                       + (': ' if sig_ab else ', e o desdobramento foi pedido: ')
                       + 'as médias de cada fator foram comparadas dentro de cada nível do outro.')
    # A dentro de cada B (letras minúsculas na coluna) e B dentro de cada A (maiúsculas na linha)
    if sub:
        erro_a_em_b = modelo.erro_de_a_dentro_de_b(quadro['erro_a'], quadro['residuo'], len(f2['rotulos']))
        nome_a_em_b = 'combinado de (a) e (b), GL de Satterthwaite'
    else:
        erro_a_em_b, nome_a_em_b = quadro['residuo'], 'Resíduo'
    fatias_a = modelo.desdobrar(y, f1['codigos'], f2['codigos'], erro_a_em_b)
    fatias_b = modelo.desdobrar(y, f2['codigos'], f1['codigos'], erro_b)
    minusculas, maiusculas = {}, {}
    for j, fatia in enumerate(fatias_a):
        quais = f2['codigos'] == j
        c = _comparacao(f'{f1["nome"]} dentro de {f2["nome"]} = {f2["rotulos"][j]}', f1['nome'], f1['rotulos'],
                        y[quais], ens['y'][quais], f1['codigos'][quais], erro_a_em_b, nome_a_em_b, teste, alfa,
                        dentro={'fator': f2['nome'], 'nivel': f2['rotulos'][j]},
                        f={k: float(fatia[k]) for k in ('gl', 'sq', 'qm', 'f', 'p')})
        r['comparacoes'].append(c)
        for i, letra in enumerate(c['letras']):
            minusculas[(i, j)] = letra
    for i, fatia in enumerate(fatias_b):
        quais = f1['codigos'] == i
        c = _comparacao(f'{f2["nome"]} dentro de {f1["nome"]} = {f1["rotulos"][i]}', f2['nome'], f2['rotulos'],
                        y[quais], ens['y'][quais], f2['codigos'][quais], erro_b, 'Erro (b)' if sub else 'Resíduo',
                        teste, alfa, dentro={'fator': f1['nome'], 'nivel': f1['rotulos'][i]},
                        f={k: float(fatia[k]) for k in ('gl', 'sq', 'qm', 'f', 'p')})
        r['comparacoes'].append(c)
        for j, letra in enumerate(c['letras']):
            maiusculas[(i, j)] = letra.upper()
    caselas = modelo.cruzar(f1['codigos'], f2['codigos'])
    media, _, _ = modelo.medias_por(y, caselas, len(f1['rotulos']) * len(f2['rotulos']))
    original, _, _ = modelo.medias_por(ens['y'], caselas, len(f1['rotulos']) * len(f2['rotulos']))
    forma = (len(f1['rotulos']), len(f2['rotulos']))
    r['tabela_dupla'] = {'linhas': f1['nome'], 'colunas': f2['nome'], 'niveis_linhas': f1['rotulos'],
                         'niveis_colunas': f2['rotulos'], 'medias': media.reshape(forma).tolist(),
                         'medias_originais': original.reshape(forma).tolist(),
                         'minusculas': [[minusculas[(i, j)] for j in range(forma[1])] for i in range(forma[0])],
                         'maiusculas': [[maiusculas[(i, j)] for j in range(forma[1])] for i in range(forma[0])],
                         'repeticoes': blocos}
    return r


def limpar(obj):
    """Tira o que não vai para o JSON (vetores internos) e converte os tipos do numpy."""
    if isinstance(obj, dict):
        return {k: limpar(v) for k, v in obj.items() if not str(k).startswith('_') and k not in ('residuos', 'caselas')}
    if isinstance(obj, (list, tuple)):
        return [limpar(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return limpar(obj.tolist())
    if isinstance(obj, (np.floating, float)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


if __name__ == '__main__':
    import json

    import sintetico

    assert num(1234.567, 1) == '1.234,6' and num(None) == '—' and num(float('nan')) == '—' and num(-0.5, 2) == '-0,50'
    assert p_igual(0.00001) == 'p < 0,0001' and p_igual(0.0312) == 'p = 0,0312'
    assert p_txt(0.00001) == '<0,0001' and p_txt(0.0312) == '0,0312' and pct(0.05) == '5' and pct(0.001) == '0,1'
    assert ler_alfa('5') == 0.05 and ler_alfa('5%') == 0.05 and ler_alfa('0,01') == 0.01 and ler_alfa('1') == 0.01
    for ruim in ('abc', '60', '0'):
        try:
            ler_alfa(ruim)
            raise AssertionError(ruim)
        except ErroDeAnalise:
            pass

    # ---- DBC: diagnóstico e análise; sem teste e sem significância, recusa
    ens = sintetico.ensaio('dbc')
    d = diagnosticar(ens)
    assert d['tipo'] == 'dbc' and len(d['descritiva']) == 6 and len(d['painel']) == 6 and d['regressao'] is None
    assert set(d['testes_possiveis']) == set(mod_medias.TESTES)
    for kw, parte in (({}, 'significância'), ({'alfa': 0.05}, 'teste de comparação'),
                      ({'alfa': 0.05, 'teste': 'bonferroni'}, 'desconhecido'),
                      ({'alfa': 0.05, 'teste': 'dunnett'}, '--testemunha'),
                      ({'alfa': 0.05, 'teste': 'dunnett', 'testemunha': 'Zeta'}, 'não é um nível'),
                      ({'alfa': 0.05, 'regressao': True}, 'níveis numéricos')):
        try:
            rodar(ens, **kw)
            raise AssertionError(parte)
        except ErroDeAnalise as e:
            assert parte in str(e), (parte, str(e))
    r = rodar(ens, 'tukey', 0.05)
    c = r['comparacoes'][0]
    assert len(c['letras']) == 6 and c['letras'][int(np.argmax(c['medias']))].startswith('a') and c['teste']['dms'] > 0
    assert r['frases'][0].startswith('Teste F para Cultivar') and 'significativo a 5%' in r['frases'][0]
    # o plantado no exemplo: a cultivar de maior média difere da de menor em qualquer teste
    alto, baixo = int(np.argmax(c['medias'])), int(np.argmin(c['medias']))
    for teste in ('tukey', 't', 'snk', 'duncan', 'scott-knott'):
        l = rodar(ens, teste, 0.05)['comparacoes'][0]['letras']
        assert not set(l[alto]) & set(l[baixo]), (teste, l)
    dn = rodar(ens, 'dunnett', 0.05, testemunha=ens['fatores'][0]['rotulos'][0])
    assert dn['comparacoes'][0]['letras'] is None and len(dn['comparacoes'][0]['teste']['contra_testemunha']) == 5
    rt = rodar(ens, 'tukey', 0.05, transformacao='log')
    assert rt['transformacao']['aplicada'] and abs(rt['comparacoes'][0]['medias_originais'][0] - c['medias'][0]) < 1e-9
    assert rt['comparacoes'][0]['medias'][0] < 10 and any('escala transformada' in x for x in rt['avisos'])
    json.dumps(limpar(r)), json.dumps(limpar(d))

    # ---- resíduo zero (todas as repetições iguais): recusa em vez de dividir por zero
    constante = sintetico.ensaio('dic-desbalanceado')
    constante['y'] = 10.0 + 2.0 * constante['fatores'][0]['codigos']
    try:
        rodar(constante, 'tukey', 0.05)
        raise AssertionError('resíduo zero devia ser recusado')
    except ErroDeAnalise as e:
        assert 'resíduo deu zero' in str(e)

    # ---- DIC desbalanceado: Scott-Knott recusado, Tukey-Kramer roda
    ens = sintetico.ensaio('dic-desbalanceado')
    assert 'scott-knott' not in diagnosticar(ens)['testes_possiveis']
    try:
        rodar(ens, 'scott-knott', 0.05)
        raise AssertionError('devia recusar')
    except ErroDeAnalise as e:
        assert 'repetições' in str(e)
    assert rodar(ens, 'tukey', 0.05)['comparacoes'][0]['teste']['dms'] is None

    # ---- fatorial com interação plantada: desdobra; sem interação: por fator
    ens = sintetico.ensaio('fatorial')
    r = rodar(ens, 'tukey', 0.05)
    assert r['desdobrou'] and r['tabela_dupla'] and len(r['comparacoes']) == 3 + 4
    td = r['tabela_dupla']
    assert len(td['medias']) == 3 and len(td['medias'][0]) == 4 and td['maiusculas'][0][0].isupper()
    assert all(x['f']['gl'] == 2 for x in r['comparacoes'][:4]) and all(x['f']['gl'] == 3 for x in r['comparacoes'][4:])
    r2 = rodar(ens, 'tukey', 0.05, desdobrar='nao')
    assert not r2['desdobrou'] and len(r2['comparacoes']) == 2 and r2['comparacoes'][0]['n'] == [16, 16, 16]
    assert any('desligado a pedido' in x for x in r2['avisos'])
    try:
        rodar(ens, 'dunnett', 0.05, testemunha='x')
        raise AssertionError('Dunnett em fatorial devia ser recusado')
    except ErroDeAnalise:
        pass
    ens = sintetico.ensaio('fatorial-sem-interacao')
    r = rodar(ens, 'scott-knott', 0.05)
    assert not r['desdobrou'] and [c['fator'] for c in r['comparacoes']] == ['Cultivar', 'Dose_N']

    # ---- parcela subdividida: A contra o erro (a); A dentro de B com GL de Satterthwaite
    ens = sintetico.ensaio('subdividida')
    r = rodar(ens, 'tukey', 0.05, desdobrar='nao')
    assert r['comparacoes'][0]['erro']['nome'] == 'Erro (a)' and r['comparacoes'][1]['erro']['nome'] == 'Erro (b)'
    assert r['cv_a'] and abs(r['comparacoes'][0]['erro']['qm'] - r['erro_a']['qm']) < 1e-12
    r = rodar(ens, 'tukey', 0.05, desdobrar='sim')
    assert 'Satterthwaite' in r['comparacoes'][0]['erro']['nome'] and r['comparacoes'][-1]['erro']['nome'] == 'Erro (b)'
    gl = r['comparacoes'][0]['erro']['gl']
    assert gl != int(gl) or gl > 0

    # ---- regressão: pede o grau; com o grau, devolve a equação
    ens = sintetico.ensaio('doses')
    d = diagnosticar(ens)
    assert d['quantitativo'] and d['regressao']['grau_maximo'] == 3
    try:
        rodar(ens, alfa=0.05, regressao=True)
        raise AssertionError('devia pedir o grau')
    except ErroDeAnalise as e:
        assert '--grau' in str(e)
    r = rodar(ens, alfa=0.05, regressao=True, grau=2)
    eq = r['regressao']['equacoes'][1]
    assert r['regressao']['grau'] == 2 and eq['coeficientes'][2] < 0 and 0.8 < eq['r2'] <= 1 and 'vertice' in eq
    assert any(f.startswith('Regressão quadrática') for f in r['frases'])
    assert any('numéricos' in x for x in rodar(ens, 'tukey', 0.05)['avisos'])
    print('ensaio OK')
