"""Papel de cada coluna (resposta, fator, bloco) e a estrutura do ensaio.

O palpite do papel de cada coluna é só palpite: sai do nome e do jeito dos
valores, para o diagnóstico ter por onde começar. Quem confirma é o usuário.
Depois de confirmado, `montar` confere se o arquivo tem mesmo a estrutura do
delineamento e recusa, dizendo por quê, o que esta versão não analisa:
parcela perdida em blocos, fatorial desbalanceado, três fatores ou mais.

Teste embutido: python scripts/delineamento.py
"""

import re
from collections import Counter

import numpy as np

from leitura import chave

PISTAS = {
    'bloco': (r'^bloco', r'^block', r'^blk', r'^bl$'),
    'repeticao': (r'^rep', r'^r$', r'repet'),
    'identificador': (r'^parcela', r'^plot', r'^id', r'^obs', r'^ordem', r'^n$', r'^num', r'^amostra', r'^unidade',
                      r'^codigo', r'^cod$'),
    'fator': (r'^trat', r'cultivar', r'variedade', r'hibrid', r'genotip', r'^dose', r'fator', r'adub', r'manejo',
              r'epoca', r'fonte', r'produto', r'espacament', r'populac', r'densidade', r'fungicida', r'herbicida',
              r'inseticida', r'^cv$', r'material', r'lamina', r'irrig', r'substrato', r'^nivel', r'^trt'),
}
NOMES = {'dic': 'inteiramente casualizado (DIC)', 'dbc': 'em blocos casualizados (DBC)',
         'fatorial-dic': 'fatorial em delineamento inteiramente casualizado',
         'fatorial-dbc': 'fatorial em blocos casualizados', 'subdividida': 'em parcelas subdivididas, em blocos'}


class ErroDeDelineamento(Exception):
    """Estrutura que a skill não analisa; a mensagem vai para o usuário como está."""


def _casa(nome, papel):
    k = chave(nome)
    return any(re.search(p, k) for p in PISTAS[papel])


def descrever_colunas(tabela):
    """Uma linha por coluna: quantos valores, quantos níveis e o palpite do papel."""
    saida = []
    for nome in tabela['colunas']:
        preenchidos = [t for t in tabela['texto'][nome] if t != '']
        contagem = Counter(preenchidos)
        niveis = len(contagem)
        numeros = tabela['numero'][nome]
        repetida = niveis < len(preenchidos)
        equilibrada = repetida and len(set(contagem.values())) == 1
        info = {'coluna': nome, 'preenchidas': len(preenchidos), 'niveis': niveis, 'numerica': numeros is not None,
                'exemplos': list(contagem)[:6]}
        if numeros is None:
            if _casa(nome, 'bloco'):
                papel = 'bloco'
            elif _casa(nome, 'repeticao'):
                papel = 'repeticao'
            elif not repetida:
                papel = 'identificador'
            else:
                papel = 'fator'
        else:
            finitos = numeros[np.isfinite(numeros)]
            inteiros = bool(len(finitos)) and bool(np.all(finitos == np.round(finitos)))
            em_sequencia = inteiros and not repetida and len(finitos) > 2 and bool(
                np.all(np.sort(finitos) == np.arange(finitos.min(), finitos.min() + len(finitos))))
            if repetida and _casa(nome, 'bloco'):
                papel = 'bloco'
            elif repetida and _casa(nome, 'repeticao'):
                papel = 'repeticao'
            elif not repetida and (_casa(nome, 'identificador') or em_sequencia):
                papel = 'identificador'
            elif repetida and (_casa(nome, 'fator') or (equilibrada and niveis <= len(preenchidos) / 2)):
                papel = 'fator'
            else:
                papel = 'resposta'
            info['minimo'], info['maximo'] = (float(finitos.min()), float(finitos.max())) if len(finitos) else (None, None)
        info['palpite'] = papel
        saida.append(info)
    return saida


def sugerir(tabela):
    """Palpite dos papéis: {'respostas', 'fatores', 'bloco', 'repeticao', 'colunas'}."""
    colunas = descrever_colunas(tabela)
    de = lambda papel: [c['coluna'] for c in colunas if c['palpite'] == papel]  # noqa: E731
    return {'respostas': de('resposta'), 'fatores': de('fator'), 'bloco': (de('bloco') or [None])[0],
            'repeticao': (de('repeticao') or [None])[0], 'colunas': colunas}


def achar_coluna(tabela, pedido):
    if pedido in tabela['colunas']:
        return pedido
    iguais = [n for n in tabela['colunas'] if chave(n) == chave(pedido)]
    if len(iguais) == 1:
        return iguais[0]
    raise ErroDeDelineamento(f'A coluna "{pedido}" não existe no arquivo. As colunas são: '
                             f'{", ".join(tabela["colunas"])}.')


def _rotulo(valor):
    return str(int(valor)) if float(valor) == int(valor) else format(valor, '.10g').replace('.', ',')


def _codificar(tabela, nome, linhas):
    """Códigos 0..k-1 dos níveis. Coluna numérica: níveis em ordem crescente; texto: na ordem do arquivo."""
    numeros = tabela['numero'][nome]
    if numeros is not None and np.all(np.isfinite(numeros[linhas])):
        valores = sorted(set(float(v) for v in numeros[linhas]))
        indice = {v: k for k, v in enumerate(valores)}
        return np.array([indice[float(v)] for v in numeros[linhas]]), [_rotulo(v) for v in valores], valores
    textos = [tabela['texto'][nome][i] for i in linhas]
    rotulos = list(dict.fromkeys(textos))
    indice = {t: k for k, t in enumerate(rotulos)}
    return np.array([indice[t] for t in textos]), rotulos, None


def _lista(itens, teto=6):
    itens = list(itens)
    return ', '.join(itens[:teto]) + (f' e mais {len(itens) - teto}' if len(itens) > teto else '')


def montar(tabela, resposta, fatores, bloco=None, subdividida=False):
    """Confere a estrutura e devolve o ensaio pronto para o modelo."""
    resposta = achar_coluna(tabela, resposta)
    fatores = [achar_coluna(tabela, f) for f in fatores]
    bloco = achar_coluna(tabela, bloco) if bloco else None
    if not 1 <= len(fatores) <= 2:
        raise ErroDeDelineamento('Esta versão analisa ensaios com um ou dois fatores. Com três ou mais, a análise '
                                 'precisa de outro programa.')
    papeis = fatores + ([bloco] if bloco else []) + [resposta]
    if len(set(papeis)) != len(papeis):
        raise ErroDeDelineamento('A mesma coluna foi informada em dois papéis (resposta, fator ou bloco).')
    y_tudo = tabela['numero'][resposta]
    if y_tudo is None:
        raise ErroDeDelineamento(f'A coluna "{resposta}" não é numérica: não serve de resposta.')
    sem_nivel = [i + 2 for i in range(tabela['linhas'])
                 if np.isfinite(y_tudo[i]) and any(tabela['texto'][c][i] == '' for c in papeis[:-1])]
    if sem_nivel:
        raise ErroDeDelineamento(f'Há resposta sem o nível do fator ou do bloco na(s) linha(s) {_lista(map(str, sem_nivel))} '
                                 'do arquivo. Preencha ou retire essas linhas.')
    linhas = np.nonzero(np.isfinite(y_tudo))[0]
    perdidas = [int(i) + 2 for i in range(tabela['linhas']) if not np.isfinite(y_tudo[i])
                and all(tabela['texto'][c][i] != '' for c in papeis[:-1])]
    if len(linhas) < 4:
        raise ErroDeDelineamento(f'A coluna "{resposta}" tem só {len(linhas)} valor(es): não há ensaio para analisar.')
    y = y_tudo[linhas]
    ens = {'resposta': resposta, 'y': y, 'linhas': linhas, 'perdidas': perdidas, 'avisos': [], 'fatores': []}
    for nome in fatores:
        cod, rotulos, valores = _codificar(tabela, nome, linhas)
        if len(rotulos) < 2:
            raise ErroDeDelineamento(f'O fator "{nome}" tem um nível só: não há o que comparar.')
        ens['fatores'].append({'nome': nome, 'codigos': cod, 'rotulos': rotulos, 'valores': valores})
    ens['bloco'] = None
    if bloco:
        cod, rotulos, _ = _codificar(tabela, bloco, linhas)
        if len(rotulos) < 2:
            raise ErroDeDelineamento(f'A coluna "{bloco}" tem um bloco só: sem dois blocos ou mais não há delineamento '
                                     'em blocos.')
        ens['bloco'] = {'nome': bloco, 'codigos': cod, 'rotulos': rotulos}
    aviso_perdidas = (f' Há {len(perdidas)} parcela(s) sem valor na resposta (linha(s) {_lista(map(str, perdidas))} do '
                      'arquivo).') if perdidas else ''
    f1 = ens['fatores'][0]
    t = len(f1['rotulos'])

    if len(fatores) == 1 and not bloco:
        n = np.bincount(f1['codigos'], minlength=t)
        if len(y) - t < 1:
            raise ErroDeDelineamento('Cada tratamento aparece uma vez só: sem repetição não há como estimar o erro '
                                     'experimental.')
        ens.update(tipo='dic', balanceado=bool(np.all(n == n[0])), repeticoes=[int(v) for v in n])
        reps = f'{int(n[0])} repetições cada' if ens['balanceado'] else f'de {int(n.min())} a {int(n.max())} repetições'
        ens['descricao'] = (f'Delineamento {NOMES["dic"]}: {t} tratamentos (coluna "{f1["nome"]}"), {reps}; '
                            f'{len(y)} parcelas.')
        if not ens['balanceado']:
            ens['avisos'].append('Repetições desiguais entre os tratamentos: a análise de variância segue valendo; '
                                 'dos testes de médias, ficam Tukey (Tukey-Kramer), t e Dunnett.' + aviso_perdidas)
        if n.min() < 2:
            ens['avisos'].append('Há tratamento com uma repetição só: a variância dele não entra nos testes de '
                                 'homogeneidade.')
        return ens

    def exige_completo(contagem, rotulos_das_dimensoes, o_que):
        if (contagem == 0).any():
            onde = np.argwhere(contagem == 0)[0]
            quem = ', '.join(f'{d["nome"]} = {d["rotulos"][i]}' for d, i in zip(rotulos_das_dimensoes, onde))
            raise ErroDeDelineamento(f'Falta parcela: não há observação para {quem}.{aviso_perdidas} Esta versão não '
                                     f'estima parcela perdida nem analisa {o_que}; a análise precisa de outro programa '
                                     '(modelo com dados desbalanceados).')

    if len(fatores) == 1:
        b = ens['bloco']
        contagem = np.zeros((len(b['rotulos']), t), int)
        np.add.at(contagem, (b['codigos'], f1['codigos']), 1)
        exige_completo(contagem, [b, f1], 'blocos incompletos')
        if (contagem > 1).any():
            onde = np.argwhere(contagem > 1)[0]
            raise ErroDeDelineamento(
                f'Há {int(contagem[tuple(onde)])} observações de {f1["nome"]} = {f1["rotulos"][onde[1]]} no bloco '
                f'{b["rotulos"][onde[0]]}; em blocos casualizados é uma parcela por tratamento em cada bloco. Se são '
                'amostras da mesma parcela, tire a média por parcela antes. Se a coluna não é bloco, rode sem --bloco.')
        ens.update(tipo='dbc', balanceado=True, repeticoes=len(b['rotulos']))
        ens['descricao'] = (f'Delineamento {NOMES["dbc"]}: {t} tratamentos (coluna "{f1["nome"]}") em '
                            f'{len(b["rotulos"])} blocos (coluna "{b["nome"]}"); {len(y)} parcelas, uma de cada '
                            'tratamento em cada bloco.')
        return ens

    f2 = ens['fatores'][1]
    s = len(f2['rotulos'])
    if not bloco:
        if subdividida:
            raise ErroDeDelineamento('A parcela subdividida está implementada só em blocos: informe a coluna do bloco '
                                     'com --bloco.')
        contagem = np.zeros((t, s), int)
        np.add.at(contagem, (f1['codigos'], f2['codigos']), 1)
        exige_completo(contagem, [f1, f2], 'fatorial incompleto')
        if not (contagem == contagem[0, 0]).all():
            raise ErroDeDelineamento('As combinações dos dois fatores não têm o mesmo número de repetições '
                                     f'(de {contagem.min()} a {contagem.max()}).{aviso_perdidas} Esta versão analisa '
                                     'fatorial só com dado balanceado.')
        r = int(contagem[0, 0])
        if r < 2:
            raise ErroDeDelineamento('Cada combinação dos dois fatores aparece uma vez só: não sobra resíduo. Se o '
                                     'ensaio tem blocos, informe a coluna com --bloco.')
        ens.update(tipo='fatorial-dic', balanceado=True, repeticoes=r)
        ens['descricao'] = (f'Esquema {NOMES["fatorial-dic"]}: {t} × {s} ("{f1["nome"]}" com {t} níveis e '
                            f'"{f2["nome"]}" com {s}), {r} repetições por combinação; {len(y)} parcelas.')
        return ens

    b = ens['bloco']
    contagem = np.zeros((len(b['rotulos']), t, s), int)
    np.add.at(contagem, (b['codigos'], f1['codigos'], f2['codigos']), 1)
    exige_completo(contagem, [b, f1, f2], 'fatorial incompleto')
    if (contagem > 1).any():
        raise ErroDeDelineamento('Há mais de uma observação da mesma combinação de fatores no mesmo bloco. Se são '
                                 'amostras da mesma parcela, tire a média por parcela antes. Se a coluna não é bloco, '
                                 'rode sem --bloco.')
    tipo = 'subdividida' if subdividida else 'fatorial-dbc'
    ens.update(tipo=tipo, balanceado=True, repeticoes=len(b['rotulos']))
    if subdividida:
        ens['descricao'] = (f'Delineamento {NOMES["subdividida"]}: "{f1["nome"]}" na parcela ({t} níveis) e '
                            f'"{f2["nome"]}" na subparcela ({s} níveis), em {len(b["rotulos"])} blocos '
                            f'(coluna "{b["nome"]}"); {len(y)} subparcelas.')
    else:
        ens['descricao'] = (f'Esquema {NOMES["fatorial-dbc"]}: {t} × {s} ("{f1["nome"]}" com {t} níveis e '
                            f'"{f2["nome"]}" com {s}) em {len(b["rotulos"])} blocos (coluna "{b["nome"]}"); '
                            f'{len(y)} parcelas.')
    return ens


if __name__ == '__main__':
    def tabela(colunas):
        nomes = list(colunas)
        linhas = len(colunas[nomes[0]])
        t = {'arquivo': 't.csv', 'origem': '', 'colunas': nomes, 'texto': {}, 'numero': {}, 'linhas': linhas, 'avisos': []}
        for nome, valores in colunas.items():
            t['texto'][nome] = ['' if v is None else str(v) for v in valores]
            try:
                t['numero'][nome] = np.array([np.nan if v is None else float(v) for v in valores])
            except ValueError:
                t['numero'][nome] = None
        return t

    rng = np.random.default_rng(3)
    trat = [x for x in ('Testemunha', 'A', 'B', 'C', 'D') for _ in range(4)]
    bloco = [1, 2, 3, 4] * 5
    y = list(np.round(rng.normal(50, 5, 20), 1))
    t = tabela({'Parcela': list(range(101, 121)), 'Tratamento': trat, 'Bloco': bloco, 'Prod': y,
                'Altura_cm': list(np.round(rng.normal(90, 4, 20)))})
    s = sugerir(t)
    assert s['fatores'] == ['Tratamento'] and s['bloco'] == 'Bloco' and s['respostas'] == ['Prod', 'Altura_cm'], s
    assert [c['palpite'] for c in s['colunas']][0] == 'identificador'
    e = montar(t, 'prod', ['tratamento'], 'bloco')
    assert e['tipo'] == 'dbc' and e['fatores'][0]['rotulos'][0] == 'Testemunha' and e['repeticoes'] == 4
    assert 'blocos casualizados' in e['descricao'] and '5 tratamentos' in e['descricao']
    e = montar(t, 'Prod', ['Tratamento'])
    assert e['tipo'] == 'dic' and e['balanceado'] and e['repeticoes'] == [4] * 5

    # coluna "Rep": palpite de repetição, não de bloco; dose numérica vira fator com níveis em ordem
    doses = [x for x in (100, 0, 50, 150) for _ in range(5)]
    t2 = tabela({'Dose': doses, 'Rep': [1, 2, 3, 4, 5] * 4, 'MS': list(np.round(rng.normal(10, 1, 20), 2))})
    s = sugerir(t2)
    assert s['fatores'] == ['Dose'] and s['repeticao'] == 'Rep' and s['bloco'] is None and s['respostas'] == ['MS']
    e = montar(t2, 'MS', ['Dose'])
    assert e['fatores'][0]['rotulos'] == ['0', '50', '100', '150'] and e['fatores'][0]['valores'] == [0, 50, 100, 150]
    assert e['fatores'][0]['codigos'][0] == 2

    # parcela perdida: DIC segue (desbalanceado), DBC recusa
    y2 = list(y)
    y2[7] = None
    t3 = tabela({'Tratamento': trat, 'Bloco': bloco, 'Prod': y2})
    e = montar(t3, 'Prod', ['Tratamento'])
    assert e['tipo'] == 'dic' and not e['balanceado'] and e['perdidas'] == [9] and len(e['y']) == 19 and e['avisos']
    try:
        montar(t3, 'Prod', ['Tratamento'], 'Bloco')
        raise AssertionError('DBC com parcela perdida devia ser recusado')
    except ErroDeDelineamento as erro:
        assert 'Falta parcela' in str(erro) and 'Tratamento = A' in str(erro) and 'linha(s) 9' in str(erro)

    # fatorial: com e sem bloco, subdividida, e as recusas
    fa = [a for a in ('Cv1', 'Cv2', 'Cv3') for _ in range(8)]
    fb = [d for _ in range(3) for d in (0, 0, 0, 0, 60, 60, 60, 60)]
    rep = [1, 2, 3, 4] * 6
    t4 = tabela({'Cultivar': fa, 'Dose': fb, 'Bloco': rep, 'Y': list(np.round(rng.normal(30, 3, 24), 1))})
    e = montar(t4, 'Y', ['Cultivar', 'Dose'])
    assert e['tipo'] == 'fatorial-dic' and e['repeticoes'] == 4 and '3 × 2' in e['descricao']
    assert montar(t4, 'Y', ['Cultivar', 'Dose'], 'Bloco')['tipo'] == 'fatorial-dbc'
    e = montar(t4, 'Y', ['Cultivar', 'Dose'], 'Bloco', subdividida=True)
    assert e['tipo'] == 'subdividida' and 'na parcela' in e['descricao']
    casos = [
        (lambda: montar(t4, 'Y', ['Cultivar', 'Dose'], subdividida=True), 'só em blocos'),
        (lambda: montar(t4, 'Y', ['Cultivar', 'Dose', 'Bloco']), 'um ou dois fatores'),
        (lambda: montar(t4, 'Y', ['Cultivar'], 'Bloco'), 'observações de Cultivar'),
        (lambda: montar(t4, 'Peso', ['Cultivar']), 'não existe'),
        (lambda: montar(t4, 'Cultivar', ['Dose']), 'não é numérica'),
        (lambda: montar(t4, 'Y', ['Cultivar', 'Cultivar']), 'dois papéis'),
        (lambda: montar(tabela({'T': ['a', 'b', 'c', 'd'], 'Y': [1, 2, 3, 4]}), 'Y', ['T']), 'sem repetição'),
        (lambda: montar(tabela({'A': ['x', 'x', 'y', 'y'], 'B': ['p', 'q', 'p', 'q'], 'Y': [1, 2, 3, 4]}), 'Y', ['A', 'B']),
         'uma vez só'),
        (lambda: montar(tabela({'A': ['x'] * 5 + ['y'] * 4, 'B': ['p', 'p', 'q', 'q', 'q', 'p', 'p', 'q', 'q'],
                                'Y': list(range(9))}), 'Y', ['A', 'B']), 'mesmo número de repetições'),
        (lambda: montar(tabela({'T': ['a', 'a', '', 'b', 'b'], 'Y': [1, 2, 3, 4, 5]}), 'Y', ['T']), 'sem o nível'),
        (lambda: montar(tabela({'T': ['a'] * 6, 'Y': [1, 2, 3, 4, 5, 6]}), 'Y', ['T']), 'um nível só'),
    ]
    for chamada, parte in casos:
        try:
            chamada()
            raise AssertionError(parte)
        except ErroDeDelineamento as erro:
            assert parte in str(erro), (parte, str(erro))
    print('delineamento OK')
