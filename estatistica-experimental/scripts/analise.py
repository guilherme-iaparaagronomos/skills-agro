"""Estatística experimental: análise de variância e comparação de médias de ensaios agronômicos.

Duas etapas, sempre nesta ordem:

  1. DIAGNÓSTICO (não compara médias): as colunas, o delineamento encontrado, o
     quadro da análise de variância, os pressupostos e o que cada transformação faria.
       python scripts/analise.py --dados ensaio.csv --diagnostico

  2. ANÁLISE, depois de o usuário confirmar o delineamento e ESCOLHER o teste e a
     significância (a skill não escolhe):
       python scripts/analise.py --dados ensaio.csv --resposta Prod --fatores Cultivar \\
           --bloco Bloco --teste tukey --alfa 5 --nome "Ensaio de cultivares 25/26"

  Exemplo pronto, com dados inventados:  python scripts/analise.py --demo

Entrada: CSV, TSV ou TXT (uma linha por parcela, cabeçalho na primeira linha) ou XLSX.
Delineamentos: DIC, DBC, fatorial duplo (em DIC ou em blocos), parcela subdividida em
blocos; regressão polinomial para um fator quantitativo.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

import delineamento
import ensaio
import leitura
import medias as mod_medias
import modelo
import saidas
import sintetico
from ensaio import num, p_igual, p_txt, pct

ERROS = (leitura.ErroDeLeitura, delineamento.ErroDeDelineamento, ensaio.ErroDeAnalise, modelo.ErroDeModelo,
         mod_medias.ErroDeTeste)


def argumentos(lista=None):
    p = argparse.ArgumentParser(description='Análise de variância e comparação de médias de ensaios agronômicos.')
    p.add_argument('--dados', help='tabela do ensaio: CSV, TSV, TXT ou XLSX, uma linha por parcela')
    p.add_argument('--planilha', help='nome da planilha, quando o XLSX tem mais de uma')
    p.add_argument('--diagnostico', action='store_true', help='descreve o ensaio e os pressupostos; não compara médias')
    p.add_argument('--demo', nargs='?', const='dbc', choices=sintetico.CONJUNTOS, help='roda um exemplo inventado')
    p.add_argument('--resposta', help='coluna da variável resposta')
    p.add_argument('--fatores', help='coluna do fator, ou duas separadas por vírgula (fatorial)')
    p.add_argument('--bloco', help='coluna do bloco (sem ela, o delineamento é inteiramente casualizado)')
    p.add_argument('--subdividida', action='store_true',
                   help='parcela subdividida: o primeiro fator está na parcela e o segundo na subparcela')
    p.add_argument('--teste', help='teste de médias, ESCOLHIDO PELO USUÁRIO: ' + ', '.join(mod_medias.TESTES))
    p.add_argument('--alfa', help='significância, ESCOLHIDA PELO USUÁRIO: 5 (ou 0,05), 1 (ou 0,01)…')
    p.add_argument('--testemunha', help='nível que é a testemunha, para o teste de Dunnett')
    p.add_argument('--transformacao', help='transformação da resposta, se o usuário pedir: '
                   + ', '.join(modelo.TRANSFORMACOES) + ' (padrão: nenhuma)')
    p.add_argument('--desdobrar', default='auto', choices=('auto', 'sim', 'nao'),
                   help='fatorial: comparar um fator dentro do outro (auto = só se a interação for significativa)')
    p.add_argument('--regressao', action='store_true', help='fator quantitativo: regressão polinomial em vez de teste de médias')
    p.add_argument('--grau', type=int, help='grau da regressão, ESCOLHIDO PELO USUÁRIO (1 a 3)')
    p.add_argument('--nome', default='', help='título do relatório (ensaio, cultura, safra)')
    p.add_argument('--unidade', default='', help='unidade da resposta, só para os textos (kg/ha, cm, %%…)')
    p.add_argument('--casas', type=int, help='casas decimais das médias (padrão: pela grandeza do dado)')
    p.add_argument('--saida', default='saida-estatistica')
    return p.parse_args(lista)


def _colunas(texto):
    return [c.strip() for c in str(texto).split(',') if c.strip()] if texto else []


def _tabela_txt(cabecalho, linhas, recuo='  '):
    larguras = [max(len(str(c)), *(len(str(l[k])) for l in linhas)) if linhas else len(str(c))
                for k, c in enumerate(cabecalho)]
    def monta(l):
        return recuo + '  '.join(str(c).ljust(w) if k == 0 else str(c).rjust(w) for k, (c, w) in enumerate(zip(l, larguras)))
    return '\n'.join([monta(cabecalho), recuo + '  '.join('-' * w for w in larguras)] + [monta(l) for l in linhas])


def _imprimir_quadro(quadro, casas):
    print(_tabela_txt(['Fonte de variação', 'GL', 'SQ', 'QM', 'F', 'p'],
                      [[l['fonte'], int(l['gl']), num(l['sq'], casas), '' if l['fonte'] == 'Total' else num(l.get('qm'), casas),
                        num(l.get('f'), 2).replace('—', ''), p_txt(l.get('p')).replace('—', '')] for l in quadro]))


def _imprimir_pressupostos(pr):
    for nome, chave_e, rotulo in (('shapiro', 'w', 'Shapiro-Wilk (normalidade dos resíduos)'),
                                  ('bartlett', 'estatistica', 'Bartlett (variâncias homogêneas)'),
                                  ('levene', 'estatistica', 'Levene (variâncias homogêneas)')):
        t = pr[nome]
        if t:
            marca = '  <- abaixo de 0,05' if t['p'] < 0.05 else ''
            print(f'  - {rotulo}: estatística {num(t[chave_e], 4)}, {p_igual(t["p"])}{marca}')
        else:
            print(f'  - {rotulo}: não calculado')
    print(f'  - Resíduos padronizados além de ±{num(pr["limite_discrepante"], 0)}: {len(pr["discrepantes"])}')
    for nota in pr['notas']:
        print(f'    ({nota})')


def _caselas(ens):
    f = ens['fatores']
    return f[0]['rotulos'] if len(f) == 1 else [f'{a} · {b}' for a in f[0]['rotulos'] for b in f[1]['rotulos']]


def _montar(tabela, a, resposta, fatores, bloco):
    return delineamento.montar(tabela, resposta, fatores, bloco, subdividida=a.subdividida)


# ------------------------------------------------------------------ diagnóstico
def rodar_diagnostico(a, tabela, pasta):
    sug = delineamento.sugerir(tabela)
    print(f'DIAGNÓSTICO — {tabela["arquivo"]} ({tabela["origem"]}) · {tabela["linhas"]} linhas · nenhuma média foi comparada')
    for aviso in tabela['avisos']:
        print(f'AVISO DE LEITURA: {aviso}')
    print('Colunas do arquivo e o palpite do papel de cada uma (CONFIRME COM O USUÁRIO):')
    print(_tabela_txt(['Coluna', 'Tipo', 'Níveis', 'Palpite', 'Exemplos'],
                      [[c['coluna'], 'número' if c['numerica'] else 'texto', c['niveis'], c['palpite'],
                        ', '.join(c['exemplos'][:4])] for c in sug['colunas']]))
    fatores = _colunas(a.fatores) or sug['fatores']
    respostas = [a.resposta] if a.resposta else sug['respostas']
    bloco = a.bloco or sug['bloco']
    if not respostas or not fatores or len(fatores) > 2:
        print('\nNão deu para montar o ensaio só pelo palpite:')
        if not respostas:
            print('  - não achei coluna com cara de resposta (número medido em cada parcela);')
        if not fatores:
            print('  - não achei coluna com cara de fator (tratamento, cultivar, dose);')
        if len(fatores) > 2:
            print(f'  - há {len(fatores)} colunas com cara de fator ({", ".join(fatores)}); esta versão analisa um ou dois;')
        print('Pergunte ao usuário qual é a resposta, qual é o fator (ou os dois) e se há bloco, e rode de novo com '
              '--resposta, --fatores e --bloco.')
        return 2
    resposta = respostas[0]
    if len(respostas) > 1:
        print(f'\nHá {len(respostas)} colunas com cara de resposta: {", ".join(respostas)}. O diagnóstico abaixo é de '
              f'"{resposta}"; para outra, rode de novo com --resposta. Cada resposta é uma análise.')
    leituras = []
    if sug['repeticao'] and not a.bloco and not sug['bloco']:
        print(f'\nATENÇÃO: há a coluna "{sug["repeticao"]}". O arquivo não diz se ela é BLOCO (o ensaio foi em blocos '
              'casualizados) ou só o NÚMERO DA REPETIÇÃO (inteiramente casualizado). PERGUNTE AO USUÁRIO.')
        for rotulo, b in (('sem bloco', None), (f'com "{sug["repeticao"]}" como bloco', sug['repeticao'])):
            try:
                leituras.append((rotulo, b, _montar(tabela, a, resposta, fatores, b)))
            except ERROS as e:
                print(f'  Leitura {rotulo}: não fecha — {e}')
        for k, (rotulo, b, e) in enumerate(leituras, 1):
            print(f'  Leitura {k} ({rotulo}): {e["descricao"]}')
        if not leituras:
            return 2
        if len(leituras) > 1:
            print('  O diagnóstico abaixo é da leitura 1. Para a leitura 2, rode de novo com '
                  f'--bloco "{sug["repeticao"]}".')
        bloco, ens = leituras[0][1], leituras[0][2]
    else:
        ens = _montar(tabela, a, resposta, fatores, bloco)
    d = ensaio.diagnosticar(ens, a.transformacao)
    casas = a.casas if a.casas is not None else saidas.casas_para(d['media'])
    casas_q = saidas._casas_do_quadro(modelo.linha(d['_quadro'], d['quadro'][-2]['fonte'])['qm'])
    print(f'\nDELINEAMENTO ENCONTRADO: {d["descricao"]}')
    if len(fatores) == 2 and bloco and not a.subdividida:
        print('  (Se o ensaio foi em PARCELAS SUBDIVIDIDAS — um fator na parcela, o outro na subparcela —, o arquivo '
              'não mostra: pergunte ao usuário e rode com --subdividida, com o fator da parcela primeiro em --fatores.)')
    for aviso in d['avisos']:
        print(f'AVISO: {aviso}')
    if d['perdidas']:
        print(f'Parcelas sem valor na resposta (linhas do arquivo): {", ".join(map(str, d["perdidas"][:12]))}')
    print(f'\nResposta: {resposta} · escala: {d["transformacao"]["descricao"]} · média geral {num(d["media"], casas)} · '
          + (f'CV(a) {num(d["cv_a"], 2)}% e CV(b) {num(d["cv"], 2)}%' if d['cv_a'] else f'CV {num(d["cv"], 2)}%'))
    print('Estatística descritiva por tratamento (escala original):')
    print(_tabela_txt(['Tratamento', 'n', 'Média', 'Desvio', 'Mínimo', 'Máximo', 'CV %'],
                      [[l['nivel'], l['n'], num(l['media'], casas), num(l['dp'], casas), num(l['minimo'], casas),
                        num(l['maximo'], casas), num(l['cv'], 1)] for l in d['descritiva']]))
    print('\nQuadro da análise de variância (o valor de p de cada fonte; a significância quem escolhe é o usuário):')
    _imprimir_quadro(d['quadro'], casas_q)
    print('\nPressupostos, sobre os resíduos do modelo (a marca usa 0,05 como referência usual):')
    _imprimir_pressupostos(d['pressupostos'])
    print('\nO que cada transformação faria (só mostra; NÃO foi aplicada — transformar é decisão do usuário):')
    linhas = []
    for t in d['painel']:
        if 'recusada' in t:
            linhas.append([t['transformacao'], t['descricao'], 'não se aplica', '', '', '', ''])
        else:
            linhas.append([t['transformacao'], t['descricao'], num(t['cv'], 2), p_txt(t['shapiro_p']),
                           p_txt(t['bartlett_p']), p_txt(t['levene_p']), t['discrepantes']])
    print(_tabela_txt(['--transformacao', 'Conta', 'CV %', 'p Shapiro', 'p Bartlett', 'p Levene', 'Discrepantes'], linhas))
    print('  (O CV de escalas diferentes não se compara: serve para ver a escala, não para escolher a transformação.)')
    if d['regressao']:
        print(f'\nO fator "{fatores[0]}" tem níveis numéricos. Se forem doses ou outro fator quantitativo (e não '
              'códigos de tratamento), a REGRESSÃO é possível (--regressao --grau N). Os graus, testados contra o resíduo:')
        print(_tabela_txt(['Componente', 'GL', 'F', 'p'],
                          [[l['fonte'].strip(), int(l['gl']), num(l['f'], 2), p_txt(l['p'])] for l in d['regressao']['quadro']
                           if l['fonte'].strip().startswith(('Regressão', 'Desvios'))]))
        for eq in d['regressao']['equacoes']:
            print(f'  grau {eq["grau"]} ({eq["nome"]}): {saidas.equacao(eq)} · R² = {num(eq["r2"], 4)}')
        print('  O grau quem escolhe é o usuário.')
    print('\nTESTES DE MÉDIAS QUE ESTE ENSAIO ACEITA: ' + ', '.join(f'{k} ({v})' for k, v in d['testes_possiveis'].items()))
    print('\nO QUE PERGUNTAR AO USUÁRIO ANTES DE ANALISAR:')
    print('  1. O delineamento e os papéis das colunas estão certos?')
    print('  2. Qual TESTE de médias' + (' (ou regressão, e de que grau)' if d['regressao'] else '') + '?')
    print('  3. Qual SIGNIFICÂNCIA (5%, 1%…)?')
    print('  4. A resposta fica na escala original ou ele quer alguma transformação?')
    comando = f'python scripts/analise.py --dados "{a.dados or "<arquivo>"}" --resposta "{resposta}" --fatores "{",".join(fatores)}"'
    comando += (f' --bloco "{bloco}"' if bloco else '') + (' --subdividida' if a.subdividida else '')
    print(f'Depois: {comando} --teste <teste> --alfa <significância>')
    saidas.figura_dos_residuos(pasta / 'residuos.png', d['_quadro'], _caselas(ens), f'Resíduos do modelo · {resposta}')
    (pasta / 'diagnostico.json').write_text(json.dumps(ensaio.limpar(
        {'arquivo': tabela['arquivo'], 'papeis': {'resposta': resposta, 'fatores': fatores, 'bloco': bloco,
                                                  'subdividida': a.subdividida}, 'colunas': sug['colunas'],
         'diagnostico': d}), ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\nArquivos em {pasta}: diagnostico.json, residuos.png')
    return 0


# ------------------------------------------------------------------ análise
def _imprimir_comparacao(c, r, casas):
    transformado = r['transformacao']['aplicada']
    casas_t = 4 if transformado else casas
    print(f'\n{c["titulo"]}' + (f' — F da fatia: {num(c["f"]["f"], 2)}, {p_igual(c["f"]["p"])}' if c.get('f') else ''))
    ordem = saidas._ordem(c)
    if c['letras'] is None:
        contra = {d['tratamento']: d for d in c['teste']['contra_testemunha']}
        linhas = []
        for i in ordem:
            d = contra.get(i)
            linhas.append([c['niveis'][i], c['n'][i], num(c['medias'][i], casas_t),
                           num(d['diferenca'], casas_t) if d else 'testemunha', p_txt(d['p']) if d else '',
                           ('difere' if d['difere'] else 'não difere') if d else ''])
        print(_tabela_txt([c['fator'], 'n', 'Média', 'Dif. da testemunha', 'p', ''], linhas))
    else:
        cab = [c['fator'], 'n', 'Média'] + (['Média original'] if transformado else []) + ['Letras']
        print(_tabela_txt(cab, [[c['niveis'][i], c['n'][i], num(c['medias'][i], casas_t)]
                                + ([num(c['medias_originais'][i], casas)] if transformado else []) + [c['letras'][i]]
                                for i in ordem]))
    for nota in saidas._nota_do_teste(c, r, casas):
        print(f'  {nota}')


def rodar_analise(a, tabela, pasta, aviso_do_exemplo=None):
    fatores = _colunas(a.fatores)
    faltam = [nome for nome, valor in (('--resposta', a.resposta), ('--fatores', fatores)) if not valor]
    if faltam:
        raise ensaio.ErroDeAnalise(f'Falta {" e ".join(faltam)}. Rode antes o --diagnostico, confirme com o usuário o '
                                   'delineamento e informe as colunas.')
    alfa = ensaio.ler_alfa(a.alfa)
    transformacao = None if (a.transformacao or 'nenhuma').lower() == 'nenhuma' else a.transformacao.lower()
    teste = a.teste.lower().replace('_', '-').replace('scottknott', 'scott-knott').replace('lsd', 't') if a.teste else None
    ens = _montar(tabela, a, a.resposta, fatores, a.bloco)
    r = ensaio.rodar(ens, teste, alfa, transformacao, a.testemunha, a.regressao, a.grau, a.desdobrar)
    casas = a.casas if a.casas is not None else saidas.casas_para(r['media_original'])
    casas_q = saidas._casas_do_quadro(r['residuo']['qm'])
    pc = pct(alfa)
    print(f'ANÁLISE — {tabela["arquivo"]} · {r["descricao"]}')
    if aviso_do_exemplo:
        print(aviso_do_exemplo)
    escolha = f'regressão de grau {a.grau}' if a.regressao else f'teste {r["nome_do_teste"]}'
    print(f'Escolhas do usuário: {escolha} · significância de {pc}% · escala: {r["transformacao"]["descricao"]}')
    for aviso in tabela['avisos']:
        print(f'AVISO DE LEITURA: {aviso}')
    print('\nQuadro da análise de variância:')
    _imprimir_quadro(r['quadro'], casas_q)
    print(f'Média geral: {num(r["media"], 4 if r["transformacao"]["aplicada"] else casas)} · '
          + (f'CV(a) {num(r["cv_a"], 2)}% · CV(b) {num(r["cv"], 2)}%' if r['cv_a'] else f'CV {num(r["cv"], 2)}%'))
    for frase in r['frases']:
        print(f'  {frase}')
    print('\nPressupostos, sobre os resíduos:')
    _imprimir_pressupostos(r['pressupostos'])
    if r['regressao']:
        g = r['regressao']
        print(f'\nRegressão em {g["fator"]} — equações ajustadas às médias (a escolhida: grau {g["grau"]}):')
        for eq in g['equacoes']:
            marca = '  <- escolhida' if eq['grau'] == g['grau'] else ''
            print(f'  grau {eq["grau"]} ({eq["nome"]}): {saidas.equacao(eq)} · R² = {num(eq["r2"], 4)}{marca}')
        eq = g['equacoes'][g['grau'] - 1]
        if 'vertice' in eq:
            v = eq['vertice']
            print(f'  A parábola tem ponto de {v["tipo"]} em x = {num(v["x"], saidas.casas_para(v["x"]))} '
                  f'(ŷ = {num(v["y"], casas)}), dentro do intervalo testado. É propriedade da curva, não recomendação.')
        print(_tabela_txt([g['fator'], 'n', 'Média observada'],
                          [[nivel, n, num(m, casas)] for nivel, n, m in zip(g['niveis'], g['n'], g['medias'])]))
    if r['tabela_dupla']:
        td = r['tabela_dupla']
        casas_t = 4 if r['transformacao']['aplicada'] else casas
        print(f'\nMédias de {td["linhas"]} (linhas) × {td["colunas"]} (colunas):')
        print(_tabela_txt([td['linhas']] + [str(n) for n in td['niveis_colunas']],
                          [[nivel] + [f'{num(td["medias"][i][j], casas_t)} {td["minusculas"][i][j]}{td["maiusculas"][i][j]}'
                                      for j in range(len(td['niveis_colunas']))]
                           for i, nivel in enumerate(td['niveis_linhas'])]))
        print('  ' + saidas._frase_das_letras(r, dupla=True))
        print('\nTeste F de cada fatia do desdobramento:')
        print(_tabela_txt(['Fonte de variação', 'GL', 'SQ', 'QM', 'F', 'p'],
                          [[c['titulo'], int(c['f']['gl']), num(c['f']['sq'], casas_q), num(c['f']['qm'], casas_q),
                            num(c['f']['f'], 2), p_txt(c['f']['p'])] for c in r['comparacoes']]))
        for nota in dict.fromkeys(n for c in r['comparacoes'] for n in saidas._nota_do_teste(c, r, casas)[:1] + c['teste']['notas']):
            print(f'  {nota}')
    else:
        for c in r['comparacoes']:
            _imprimir_comparacao(c, r, casas)
        if r['comparacoes']:
            print('\n  ' + saidas._frase_das_letras(r))
    print('\nAVISOS (repasse todos ao usuário, com estas palavras):' if r['avisos'] else '\nSem avisos nesta análise.')
    for aviso in r['avisos']:
        print(f'  - {aviso}')

    meta = {'titulo': a.nome or Path(tabela['arquivo']).stem, 'arquivo': tabela['arquivo'], 'unidade': a.unidade,
            'data': datetime.date.today().strftime('%d/%m/%Y'), 'casas': a.casas, 'niveis_das_caselas': _caselas(ens)}
    saidas.gravar_anova(pasta / 'anova.csv', r['quadro'])
    saidas.gravar_medias(pasta / 'medias.csv', r)
    arquivos = ['anova.csv', 'medias.csv']
    if any(c['teste'].get('pares') for c in r['comparacoes']):
        saidas.gravar_pares(pasta / 'pares.csv', r)
        arquivos.append('pares.csv')
    saidas.figura_do_grafico(pasta / 'grafico.png', r, saidas._rotulo_y(r, meta))
    saidas.figura_dos_residuos(pasta / 'residuos.png', r['_quadro'], meta['niveis_das_caselas'],
                               f'Resíduos do modelo · {r["resposta"]}')
    saidas.relatorio(pasta / 'relatorio.pdf', pasta / 'relatorio.png', r, meta)
    (pasta / 'analise.json').write_text(json.dumps(ensaio.limpar(
        {'arquivo': tabela['arquivo'], 'titulo': meta['titulo'], 'unidade': a.unidade, 'data': meta['data'],
         'analise': r}), ensure_ascii=False, indent=1), encoding='utf-8')
    arquivos += ['grafico.png', 'residuos.png', 'relatorio.pdf', 'relatorio.png', 'analise.json']
    print(f'\nArquivos em {pasta}: ' + ', '.join(arquivos))
    return 0


def rodar_demo(a, pasta):
    qual = a.demo
    _, papeis = sintetico.tabela(qual)
    caminho = pasta / f'exemplo-inventado-{qual}.csv'
    caminho.write_text(sintetico.como_csv(qual), encoding='utf-8')
    tabela = leitura.ler_tabela(caminho)
    print('EXEMPLO COM DADOS INVENTADOS — nenhum número aqui veio de experimento de verdade.\n')
    a.dados = str(caminho)
    a.resposta, a.fatores, a.bloco = papeis['resposta'], ','.join(papeis['fatores']), papeis['bloco']
    a.subdividida = papeis.get('subdividida', False)
    a.unidade = a.unidade or papeis['unidade']
    a.nome = a.nome or sintetico.TITULOS[qual]
    rodar_diagnostico(a, tabela, pasta)
    print('\n' + '=' * 78 + '\n')
    if qual == 'doses':
        a.regressao, a.grau = True, a.grau or 2
        fixado = 'a regressão de grau 2'
    else:
        a.teste = a.teste or 'tukey'
        fixado = f'o teste {mod_medias.TESTES.get(a.teste, a.teste)}'
    a.alfa = a.alfa or '5'
    aviso = (f'NO EXEMPLO, {fixado} e a significância de {pct(ensaio.ler_alfa(a.alfa))}% foram fixados só para mostrar '
             'as saídas. Em uso real, quem escolhe é o usuário.')
    return rodar_analise(a, tabela, pasta, aviso)


def main(lista=None):
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, 'reconfigure'):
            fluxo.reconfigure(encoding='utf-8')
    a = argumentos(lista)
    pasta = Path(a.saida)
    try:
        if a.demo:
            pasta.mkdir(parents=True, exist_ok=True)
            return rodar_demo(a, pasta)
        if not a.dados:
            print('Informe a tabela do ensaio com --dados (ou rode o exemplo com --demo).')
            return 2
        tabela = leitura.ler_tabela(a.dados, a.planilha)
        pasta.mkdir(parents=True, exist_ok=True)
        if a.diagnostico:
            return rodar_diagnostico(a, tabela, pasta)
        return rodar_analise(a, tabela, pasta)
    except ERROS as e:
        print(f'NÃO RODOU: {e}')
        return 2


if __name__ == '__main__':
    sys.exit(main())
