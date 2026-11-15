"""Ensaios INVENTADOS, com diferenças plantadas, para o exemplo e para os testes.

Nenhum número aqui veio de experimento de verdade. Cada conjunto sai sempre
igual (semente fixa), para os testes embutidos conferirem o resultado.

  dbc                     6 cultivares em 4 blocos (uma é a testemunha)
  dic-desbalanceado       5 tratamentos com 3 a 5 repetições
  fatorial                3 cultivares x 4 doses em 4 blocos, com interação plantada
  fatorial-sem-interacao  o mesmo esquema, com os efeitos só somados
  subdividida             3 preparos de solo (parcela) x 4 cultivares (subparcela), 4 blocos
  doses                   5 doses em 4 blocos, com resposta em parábola

Teste embutido: python scripts/sintetico.py
"""

import numpy as np

import delineamento

CONJUNTOS = ('dbc', 'dic-desbalanceado', 'fatorial', 'fatorial-sem-interacao', 'subdividida', 'doses')
TITULOS = {
    'dbc': 'Ensaio inventado · cultivares em blocos',
    'dic-desbalanceado': 'Ensaio inventado · repetições desiguais',
    'fatorial': 'Ensaio inventado · cultivar × dose',
    'fatorial-sem-interacao': 'Ensaio inventado · cultivar × dose',
    'subdividida': 'Ensaio inventado · preparo × cultivar',
    'doses': 'Ensaio inventado · doses de nitrogênio',
}


def _tabela(colunas):
    nomes = list(colunas)
    t = {'arquivo': 'exemplo-inventado.csv', 'origem': 'exemplo embutido', 'colunas': nomes, 'texto': {}, 'numero': {},
         'linhas': len(colunas[nomes[0]]), 'avisos': []}
    for nome, valores in colunas.items():
        t['texto'][nome] = [format(v, '.10g') if isinstance(v, (int, float, np.integer, np.floating)) else str(v)
                            for v in valores]
        try:
            t['numero'][nome] = np.array([float(v) for v in valores])
        except (TypeError, ValueError):
            t['numero'][nome] = None
    return t


def tabela(qual='dbc'):
    """A tabela do conjunto, no formato do módulo `leitura`, e os papéis das colunas."""
    if qual not in CONJUNTOS:
        raise ValueError(f'Conjunto desconhecido: {qual}. Os que existem: {", ".join(CONJUNTOS)}.')
    rng = np.random.default_rng({'dbc': 101, 'dic-desbalanceado': 202, 'fatorial': 303, 'fatorial-sem-interacao': 408,
                                 'subdividida': 505, 'doses': 606}[qual])
    if qual == 'dbc':
        nomes = ['Testemunha', 'Cv. Aurora', 'Cv. Brisa', 'Cv. Cedro', 'Cv. Duna', 'Cv. Estrela']
        plantado = [3200, 3450, 3900, 3950, 4400, 3500]
        efeito_bloco = [120, 30, -60, -90]
        cultivar, bloco, prod, altura = [], [], [], []
        for b in range(4):
            for k in rng.permutation(6):
                cultivar.append(nomes[k])
                bloco.append(b + 1)
                prod.append(round(float(plantado[k] + efeito_bloco[b] + rng.normal(0, 180)), 0))
                altura.append(round(float(88 + 0.004 * (plantado[k] - 3200) + rng.normal(0, 3.5)), 1))
        t = _tabela({'Parcela': list(range(101, 125)), 'Bloco': bloco, 'Cultivar': cultivar, 'Prod_kg_ha': prod,
                     'Altura_cm': altura})
        return t, {'resposta': 'Prod_kg_ha', 'fatores': ['Cultivar'], 'bloco': 'Bloco', 'unidade': 'kg/ha'}
    if qual == 'dic-desbalanceado':
        trat, y = [], []
        for nome, media, n in (('T1', 42, 5), ('T2', 47, 4), ('T3', 44, 5), ('T4', 55, 3), ('T5', 51, 5)):
            trat += [nome] * n
            y += [round(float(v), 1) for v in rng.normal(media, 3.0, n)]
        return _tabela({'Tratamento': trat, 'Massa_g': y}), {'resposta': 'Massa_g', 'fatores': ['Tratamento'],
                                                             'bloco': None, 'unidade': 'g'}
    if qual in ('fatorial', 'fatorial-sem-interacao'):
        cultivares, doses = ['Cv. Aurora', 'Cv. Brisa', 'Cv. Cedro'], [0, 60, 120, 180]
        base = {'Cv. Aurora': 5200, 'Cv. Brisa': 5600, 'Cv. Cedro': 6100}
        # com interação: a Aurora quase não responde ao nitrogênio, a Cedro responde muito
        ganho = ({'Cv. Aurora': 1.0, 'Cv. Brisa': 6.0, 'Cv. Cedro': 11.0} if qual == 'fatorial'
                 else {'Cv. Aurora': 6.0, 'Cv. Brisa': 6.0, 'Cv. Cedro': 6.0})
        cv, dn, bl, y = [], [], [], []
        for b in range(4):
            for c in cultivares:
                for d in doses:
                    cv.append(c)
                    dn.append(d)
                    bl.append(b + 1)
                    y.append(round(float(base[c] + ganho[c] * d + 90 * (1.5 - b) + rng.normal(0, 260)), 0))
        return _tabela({'Bloco': bl, 'Cultivar': cv, 'Dose_N': dn, 'Prod_kg_ha': y}), {
            'resposta': 'Prod_kg_ha', 'fatores': ['Cultivar', 'Dose_N'], 'bloco': 'Bloco', 'unidade': 'kg/ha'}
    if qual == 'subdividida':
        preparos, cultivares = ['Convencional', 'Mínimo', 'Direto'], ['Cv. Aurora', 'Cv. Brisa', 'Cv. Cedro', 'Cv. Duna']
        ef_p = {'Convencional': 0, 'Mínimo': 250, 'Direto': 520}
        ef_c = {'Cv. Aurora': 0, 'Cv. Brisa': 180, 'Cv. Cedro': 420, 'Cv. Duna': 150}
        pr, cv, bl, y = [], [], [], []
        for b in range(4):
            for p in preparos:
                erro_da_parcela = rng.normal(0, 190)
                for c in cultivares:
                    pr.append(p)
                    cv.append(c)
                    bl.append(b + 1)
                    y.append(round(float(3400 + ef_p[p] + ef_c[c] + 70 * (1.5 - b) + erro_da_parcela
                                         + rng.normal(0, 130)), 0))
        return _tabela({'Bloco': bl, 'Preparo': pr, 'Cultivar': cv, 'Prod_kg_ha': y}), {
            'resposta': 'Prod_kg_ha', 'fatores': ['Preparo', 'Cultivar'], 'bloco': 'Bloco', 'subdividida': True,
            'unidade': 'kg/ha'}
    doses, dn, bl, y = [0, 50, 100, 150, 200], [], [], []
    for b in range(4):
        for d in doses:
            dn.append(d)
            bl.append(b + 1)
            y.append(round(float(6200 + 22 * d - 0.07 * d ** 2 + 110 * (1.5 - b) + rng.normal(0, 240)), 0))
    return _tabela({'Bloco': bl, 'Dose_N': dn, 'Prod_kg_ha': y}), {'resposta': 'Prod_kg_ha', 'fatores': ['Dose_N'],
                                                                   'bloco': 'Bloco', 'unidade': 'kg/ha'}


def ensaio(qual='dbc'):
    """O conjunto já conferido pelo módulo `delineamento`."""
    t, papeis = tabela(qual)
    return delineamento.montar(t, papeis['resposta'], papeis['fatores'], papeis['bloco'],
                               subdividida=papeis.get('subdividida', False))


def como_csv(qual='dbc'):
    """O conjunto em texto, com ponto e vírgula e vírgula decimal, como sai de uma planilha brasileira."""
    t, _ = tabela(qual)
    linhas = [';'.join(t['colunas'])]
    for i in range(t['linhas']):
        linhas.append(';'.join(t['texto'][c][i].replace('.', ',') if t['numero'][c] is not None else t['texto'][c][i]
                               for c in t['colunas']))
    return '\n'.join(linhas) + '\n'


if __name__ == '__main__':
    import modelo

    for qual in CONJUNTOS:
        e = ensaio(qual)
        assert e['descricao'] and len(e['y']) >= 20, qual
        t1, _ = tabela(qual)
        t2, _ = tabela(qual)
        assert t1['texto'] == t2['texto'], 'o conjunto tem de sair sempre igual'
    assert ensaio('dbc')['tipo'] == 'dbc' and ensaio('dic-desbalanceado')['repeticoes'] == [5, 4, 5, 3, 5]
    assert ensaio('subdividida')['tipo'] == 'subdividida' and ensaio('doses')['fatores'][0]['valores'] == [0, 50, 100, 150, 200]
    # o que foi plantado aparece: interação num e não no outro
    for qual, tem in (('fatorial', True), ('fatorial-sem-interacao', False)):
        e = ensaio(qual)
        q = modelo.analisar(e['y'], [f['codigos'] for f in e['fatores']], e['bloco']['codigos'],
                            nomes=[f['nome'] for f in e['fatores']])
        p = modelo.linha(q, 'Cultivar × Dose_N')['p']
        assert (p < 0.01) == tem and (tem or p > 0.10), (qual, p)
    texto = como_csv('dbc')
    assert texto.splitlines()[0] == 'Parcela;Bloco;Cultivar;Prod_kg_ha;Altura_cm' and ',' in texto.splitlines()[1]
    print('sintetico OK')
