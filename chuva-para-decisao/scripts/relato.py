"""As frases do relato: o que o registro mostra, sempre como contagem de anos.

Recebe o resultado montado pelo chuva.py e devolve blocos de frases prontas,
usadas no resumo em texto e no PDF. Nenhuma frase prevê, qualifica ou recomenda.

Teste embutido: python scripts/relato.py
"""

from leitura import MESES, br, dm, dma

MES_EXTENSO = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro',
               'novembro', 'dezembro']
FONTE = 'Fonte: pluviômetros e satélites da comunidade agrônomo10X (OagronomIA).'
NAO_E_PREVISAO = ('Descrição do que foi registrado, não previsão: não diz quanto vai chover nem que o ano será igual '
                  'a outro. A decisão de plantio e de manejo é do responsável técnico.')


def de_n(k, n):
    return f'{k} de {n} anos'


def lista(itens, teto=12):
    itens = [str(i) for i in itens]
    if not itens:
        return ''
    if len(itens) > teto:
        return ''
    return ' (' + ', '.join(itens) + ')'


def regra_inicio(g):
    dias = 'o próprio dia soma' if g['acum_dias'] == 1 else f'{g["acum_dias"]} dias somam'
    return (f'dia com pelo menos {br(g["seco_mm"], 0)} mm, a partir do qual {dias} pelo menos '
            f'{br(g["acum_mm"], 0)} mm, sem {g["falso_dias"]} dias seguidos abaixo de {br(g["seco_mm"], 0)} mm nos '
            f'{g["falso_janela"]} dias seguintes')


def regra_fim(g):
    return (f'último dia com pelo menos {br(g["seco_mm"], 0)} mm antes da primeira sequência de {g["fim_dias"]} ou '
            f'mais dias seguidos abaixo de {br(g["seco_mm"], 0)} mm')


def aviso_amostra(n):
    return (f'São {n} anos. Evento que acontece uma vez a cada 10 ou 20 anos pode não aparecer numa amostra desse '
            f'tamanho, e "em 0 de {n} anos" não quer dizer que não acontece.')


def _mensal(m):
    f = []
    a, b = m['meses'][0], m['meses'][-1]
    inicia = MESES[m['inicia'] - 1]
    f.append(f'Tabela mensal de {MESES[a["mes"] - 1]}/{a["ano"]} a {MESES[b["mes"] - 1]}/{b["ano"]}: '
             f'{len(m["meses"])} meses e {len(m["anos"])} anos agrícolas inteiros (o ano agrícola começa em {inicia}).')
    cal = m['calendario']
    alto, baixo = max(cal, key=lambda l: l['mediana']), min(cal, key=lambda l: l['mediana'])
    f.append(f'Mês de maior mediana: {MES_EXTENSO[alto["mes"] - 1]}, com {br(alto["mediana"])} mm (em 6 de cada 10 '
             f'anos ficou entre {br(alto["p20"])} e {br(alto["p80"])} mm). De menor mediana: '
             f'{MES_EXTENSO[baixo["mes"] - 1]}, com {br(baixo["mediana"])} mm.')
    for corte in m['cortes']:
        com = [l for l in cal if l['abaixo'][corte] > 0 and l['mediana'] >= corte]
        if com:
            f.append(f'Meses de mediana igual ou acima de {br(corte, 0)} mm que ficaram abaixo de {br(corte, 0)} mm em '
                     'algum ano: ' + '; '.join(f'{MES_EXTENSO[l["mes"] - 1]}, em {de_n(l["abaixo"][corte], l["n"])}'
                                              for l in com) + '.')
    t = m['totais'][1]
    if t:
        f.append(f'Total por ano agrícola em {t["n"]} anos: mediana de {br(t["mediana"], 0)} mm; o menor foi '
                 f'{t["ano_menor"]} ({br(t["menor"], 0)} mm) e o maior, {t["ano_maior"]} ({br(t["maior"], 0)} mm).')
    g = m['aguas']
    if g:
        corte = br(g['firme_mm'], 0)
        if g['regra_nao_separa']:
            f.append(f'Regra mensal das águas com {corte} mm: em {de_n(g["ja_no_primeiro"], g["n"])} o primeiro mês do '
                     'ano agrícola já passava do corte. Por esta regra o local não tem estação seca marcada no mês '
                     'em que o ano agrícola começa: o bloco de início e fim das águas não se aplica assim. Mude o '
                     'mês de início do ano agrícola ou o corte.')
        else:
            if g['inicio_por_mes']:
                f.append(f'Pela regra mensal (primeiro mês com pelo menos {corte} mm, seguido de outro também com pelo '
                         f'menos {corte} mm), as águas firmaram em '
                         + '; em '.join(f'{MES_EXTENSO[x["mes"] - 1]} em {de_n(x["anos"], g["n"])}'
                                        for x in g['inicio_por_mes']) + '.')
            if g['n_inicio'] < g['n']:
                f.append(f'Em {de_n(g["n"] - g["n_inicio"], g["n"])} a regra não fechou (sem dois meses seguidos com '
                         f'{corte} mm, ou mês sem dado).')
            if g['fim_por_mes']:
                f.append(f'Terminaram (último mês com pelo menos {corte} mm antes de dois meses seguidos abaixo disso) '
                         'em ' + '; em '.join(f'{MES_EXTENSO[x["mes"] - 1]} em {de_n(x["anos"], g["n_fim"])}'
                                              for x in g['fim_por_mes']) + '.')
        f.append('A regra mensal só diz o mês. Para a data, use a janela dia a dia.')
    d = m['gdd']
    if d:
        base = '' if m['base_gdd'] is None else f' (base {br(m["base_gdd"], 0)} °C)'
        s = d['soma']
        f.append(f'Graus-dia{base} somados de {MES_EXTENSO[d["de_mes"] - 1]} a {MES_EXTENSO[d["ate_mes"] - 1]}, em '
                 f'{s["n"]} anos: mediana de {br(s["mediana"], 0)}; menor {br(s["menor"], 0)} ({s["ano_menor"]}) e '
                 f'maior {br(s["maior"], 0)} ({s["ano_maior"]}).')
        if d['alvo'] and d['dias']:
            x = d['dias']
            f.append(f'Contando do dia 1º de {MES_EXTENSO[d["de_mes"] - 1]}, os {br(d["alvo"], 0)} graus-dia foram '
                     f'alcançados em {x["menor"]} a {x["maior"]} dias (mediana de {br(x["mediana"], 0)}), em '
                     f'{x["n"]} anos. A conta reparte os graus-dia de cada mês por igual entre os dias.'
                     + (f' Em {d["sem_alvo"]} ano(s) o alvo não foi alcançado em 12 meses.' if d['sem_alvo'] else ''))
        elif d['alvo']:
            f.append(f'O alvo de {br(d["alvo"], 0)} graus-dia não foi alcançado em 12 meses em nenhum ano.')
    return f


def acumulado(itens, n, verbo):
    """'até dd/mm, em k de N anos', sem repetir os zeros do começo nem o teto do fim."""
    partes, teto = [], max(x['anos'] for x in itens)
    for k, x in enumerate(itens):
        if x['anos'] == 0 and k + 1 < len(itens) and itens[k + 1]['anos'] == 0:
            continue
        partes.append(f'até {dm(x["ate"])}, em {de_n(x["anos"], n)}')
        if x['anos'] == teto:
            break
    return f'{verbo}: ' + '; '.join(partes) + '.'


def _janela(j, para_pdf=False):
    f = []
    n = j['n']
    f.append(f'Janela de {j["inicio_dm"]} a {j["fim_dm"]} em {n} anos ({j["anos"][0]} a {j["anos"][-1]}'
             + (', com anos fora da contagem' if j['salteados'] else '') + ').')
    seco = br(j['seco_mm'], 0)
    if para_pdf:
        f.append('A chuva de cada decêndio, entre os anos, está na tabela da página "A janela crítica".')
    for l in ([] if para_pdf else j['decendios']):
        if not l['inteiro']:
            f.append(f'{l["nome"]}: a janela pega só uma parte do decêndio; fica fora da contagem.')
            continue
        if not l.get('n'):
            f.append(f'{l["nome"]}: sem dado em todos os anos.')
            continue
        partes = [f'pelo menos {br(c, 0)} mm em {de_n(k, l["n"])}' for c, k in l['acima'].items()]
        f.append(f'{l["nome"]}: choveu ' + '; '.join(partes) + f'. Mediana de {br(l["mediana"])} mm; menor '
                 f'{br(l["menor"])} mm ({l["ano_menor"]}) e maior {br(l["maior"])} mm ({l["ano_maior"]}). '
                 f'Sem nenhum dia de {seco} mm ou mais: {de_n(l["sem_chuva"], l["n"])}.'
                 + (f' {l["sem_dado"]} ano(s) com dia sem dado ficaram fora.' if l['sem_dado'] else ''))
    v = j['veranicos']
    for x in v['resumo']:
        f.append(f'Veranico de {x["dias"]} dias ou mais (dias seguidos com menos de {seco} mm cada) dentro da janela: '
                 f'{de_n(x["anos"], x["n"])}{lista(x["quais"])}.')
    com = [l for l in v['linhas'] if l['maior']]
    if com:
        m = max(com, key=lambda l: l['maior']['dias'])
        f.append(f'A sequência seca mais longa: {m["maior"]["dias"]} dias, de {dm(m["maior"]["de"])} a '
                 f'{dma(m["maior"]["ate"])}'
                 + ('; encosta na borda da janela, então pode ter sido maior.' if m['maior']['borda'] else '.'))
    difere = [l['rotulo'] for l in v['linhas'] if l['maior'] and l['da_ferramenta']
              and l['da_ferramenta']['dias'] != l['maior']['dias']]
    if difere:
        f.append(f'Em {", ".join(difere)} o veranico máximo da ferramenta difere do contado aqui: a ferramenta usa a '
                 'régua dela para o dia sem chuva (1 ou 2 mm, conforme a fonte do dia). A tabela mostra os dois.')
    i = j['inicio']
    if i:
        s = i['resumo']
        f.append(f'Início das águas pela regra informada ({regra_inicio(i["regra"])}): determinado em '
                 f'{de_n(s["determinados"], s["n"])}.')
        if s['cedo']:
            na_borda = [l['rotulo'] for l in i['linhas'] if l['situacao'] == 'ok' and l['posicao'] == 0]
            f.append(f'Mais cedo: {dm(s["cedo"]["data"])}{" ou antes" if s["cedo"]["rotulo"] in na_borda else ""} '
                     f'({s["cedo"]["rotulo"]}); mais tarde: {dm(s["tarde"]["data"])} ({s["tarde"]["rotulo"]}).'
                     + (f' Em metade dos anos a regra já tinha fechado até {dm(s["metade"])}.' if s['metade'] else ''))
            if na_borda:
                f.append(f'Em {", ".join(na_borda)} a regra fechou já no primeiro dia da janela: as águas podem ter '
                         'firmado antes.')
            f.append(acumulado(s['acumulado'], s['n'], 'A regra já tinha fechado'))
        for situacao, quais in s['outros'].items():
            if situacao == 'sem conferência':
                f.append(f'Em {", ".join(quais)} a regra fechou perto do fim da janela e faltaram dias para conferir o '
                         'falso início: a data fica fora da contagem.')
            else:
                f.append(f'Em {", ".join(quais)}: {situacao}.')
        falsos = [f'{l["rotulo"]} ({l["falsos"]})' for l in i['linhas'] if l['falsos']]
        if falsos:
            f.append('Falso início (dia em que a chuva fechava a regra e veio a sequência seca em seguida), com o '
                     'número de dias assim: ' + ', '.join(falsos) + '.')
    f.append(aviso_amostra(n))
    return f


def _fim(x, duracao):
    s = x['datas']['resumo']
    f = [f'Janela de {x["inicio_dm"]} a {x["fim_dm"]} em {s["n"]} anos ({x["anos"][0]} a {x["anos"][-1]}).',
         f'Fim das águas pela regra informada ({regra_fim(x["regra"])}): determinado em '
         f'{de_n(s["determinados"], s["n"])}.']
    if s['cedo']:
        f.append(f'Mais cedo: {dm(s["cedo"]["data"])} ({s["cedo"]["rotulo"]}); mais tarde: {dm(s["tarde"]["data"])} '
                 f'({s["tarde"]["rotulo"]}).'
                 + (f' Em metade dos anos já tinham terminado até {dm(s["metade"])}.' if s['metade'] else ''))
        f.append(acumulado(s['acumulado'], s['n'], 'Já tinham terminado'))
    for situacao, quais in s['outros'].items():
        f.append(f'Em {", ".join(quais)}: {situacao}.')
    if duracao:
        dias = sorted(d['dias'] for d in duracao)
        f.append(f'Do início ao fim das águas, nos {len(duracao)} anos em que as duas datas fecharam: de {dias[0]} a '
                 f'{dias[-1]} dias' + lista(f'{d["rotulo"]}: {d["dias"]}' for d in duracao) + '.')
    f.append(aviso_amostra(s['n']))
    return f


def blocos(r, para_pdf=False):
    """[(título do bloco, [frases])] na ordem do relato. No PDF, o que já está em tabela não se repete em frase."""
    saida = []
    if r.get('mensal'):
        saida.append(('Calendário da chuva (tabela mensal)', _mensal(r['mensal'])))
    if r.get('contexto'):
        saida.append(('O ano em curso (frases da ferramenta, como vieram)', list(r['contexto'])))
    if r.get('janela'):
        saida.append(('A janela, dia a dia', _janela(r['janela'], para_pdf)))
    if r.get('fim'):
        saida.append(('O fim das águas', _fim(r['fim'], r.get('duracao'))))
    avisos = []
    if r.get('mensal') and (r.get('janela') or r.get('fim')):
        avisos.append('A tabela mensal (período longo) e a janela dia a dia (período curto) saem de réguas diferentes '
                      'da ferramenta: os milímetros de uma não fecham com os da outra. Compare ano com ano dentro de '
                      'cada bloco, não um bloco com o outro.')
    for parte in ('mensal', 'janela', 'fim'):
        if r.get(parte):
            avisos += r[parte]['notas']
    avisos += [NAO_E_PREVISAO, FONTE]
    saida.append(('Avisos', avisos))
    return saida


def em_texto(r):
    """O relato inteiro em Markdown simples."""
    linhas = [f'# Chuva para decisão — {r.get("local") or "local informado pelo usuário"}', '']
    for titulo, frases in blocos(r):
        linhas += [f'## {titulo}', ''] + [f'- {x}' for x in frases] + ['']
    return '\n'.join(linhas)


# ------------------------------------------------------------------ autoteste
def _autoteste():
    import datetime as dt

    assert de_n(3, 10) == '3 de 10 anos' and lista(['2020', '2021']) == ' (2020, 2021)' and lista(range(20)) == ''
    regra = dict(seco_mm=2.0, acum_mm=20.0, acum_dias=3, falso_dias=10, falso_janela=30)
    assert '3 dias somam pelo menos 20 mm' in regra_inicio(regra) and '10 dias seguidos' in regra_inicio(regra)
    assert 'o próprio dia soma' in regra_inicio(dict(regra, acum_dias=1))
    d0 = dt.date(2025, 9, 20)
    passos = [dict(ate=d0 + dt.timedelta(days=10 * k), anos=a) for k, a in enumerate([0, 0, 3, 6, 10, 10, 10])]
    assert acumulado(passos, 10, 'Fechou') == ('Fechou: até 30/09, em 0 de 10 anos; até 10/10, em 3 de 10 anos; até '
                                               '20/10, em 6 de 10 anos; até 30/10, em 10 de 10 anos.')
    cal = [dict(mes=m, nome=MESES[m - 1], n=10, mediana=10.0 * m, p20=8.0 * m, p80=12.0 * m, menor=1.0, ano_menor=2001,
                maior=300.0, ano_maior=2005, normal=None, abaixo={100: 2 if m == 11 else 0}) for m in range(1, 13)]
    mensal = dict(meses=[dict(ano=2000, mes=7)] + [dict(ano=2010, mes=6)], anos=list(range(10)), inicia=7,
                  calendario=cal, cortes=[100], base_gdd=10.0, notas=['Soma dos meses fecha.'],
                  totais=([], dict(n=10, mediana=1500.0, menor=1100.0, ano_menor='2002/03', maior=1900.0,
                                   ano_maior='2008/09')),
                  aguas=dict(firme_mm=100.0, regra_nao_separa=False, n=10, n_inicio=9, n_fim=9, ja_no_primeiro=0,
                             inicio_por_mes=[dict(mes=10, nome='out', anos=6), dict(mes=11, nome='nov', anos=3)],
                             fim_por_mes=[dict(mes=4, nome='abr', anos=9)]),
                  gdd=dict(de_mes=10, ate_mes=2, alvo=1400, sem_alvo=0,
                           soma=dict(n=10, mediana=2000.0, menor=1900.0, ano_menor='2001/02', maior=2100.0,
                                     ano_maior='2005/06'),
                           dias=dict(n=10, mediana=96.0, menor=92, ano_menor='x', maior=101, ano_maior='y')))
    d = dt.date
    janela = dict(n=10, anos=[str(a) for a in range(2016, 2026)], inicio_dm='15/09', fim_dm='30/11', salteados=False,
                  seco_mm=2.0, notas=[],
                  decendios=[dict(nome='2º dec. de set', inteiro=False),
                             dict(nome='1º dec. de out', inteiro=True, n=10, sem_dado=0, mediana=32.9, menor=0.0,
                                  ano_menor='2017', maior=90.0, ano_maior='2021', sem_chuva=1, acima={20: 8, 40: 5})],
                  veranicos=dict(resumo=[dict(dias=10, anos=7, quais=['2016', '2017'], n=10)],
                                 linhas=[dict(rotulo='2024', maior=dict(dias=23, de=d(2024, 9, 15), ate=d(2024, 10, 7),
                                                                        borda=True),
                                              da_ferramenta=dict(dias=22))]),
                  inicio=dict(regra=regra,
                              linhas=[dict(rotulo='2018', situacao='ok', posicao=0, falsos=0),
                                      dict(rotulo='2017', situacao='ok', posicao=43, falsos=3)],
                              resumo=dict(n=10, determinados=9, cedo=dict(data=d(2018, 9, 15), rotulo='2018'),
                                          tarde=dict(data=d(2017, 10, 28), rotulo='2017'), metade=d(2016, 10, 3),
                                          acumulado=[dict(ate=d(2025, 10, 10), anos=6)],
                                          outros={'sem conferência': ['2022']})))
    fim = dict(inicio_dm='01/03', fim_dm='31/05', anos=['2017', '2025'], regra=dict(seco_mm=2.0, fim_dias=15),
               notas=[], datas=dict(resumo=dict(n=9, determinados=8, cedo=dict(data=d(2020, 4, 2), rotulo='2020'),
                                                tarde=dict(data=d(2023, 5, 9), rotulo='2023'), metade=d(2021, 4, 20),
                                                acumulado=[dict(ate=d(2025, 4, 30), anos=6)],
                                                outros={'não terminaram na janela': ['2019']})))
    r = dict(local='Ponto de teste', mensal=mensal, janela=janela, fim=fim, contexto=['Frase da ferramenta.'],
             duracao=[dict(rotulo='2020/21', dias=192)])
    texto = em_texto(r)
    for pedaco in ('# Chuva para decisão — Ponto de teste', 'novembro, em 2 de 10 anos', 'outubro em 6 de 10 anos',
                   'abril em 9 de 9 anos', 'mediana de 1.500 mm', '92 a 101 dias', 'pelo menos 20 mm em 8 de 10 anos',
                   '7 de 10 anos (2016, 2017)', '15/09 ou antes (2018)', 'até 10/10, em 6 de 10 anos',
                   'Em 2022 a regra fechou perto do fim', '2017 (3)', 'Frase da ferramenta.', 'de 192 a 192 dias',
                   'réguas diferentes', 'não previsão', 'Fonte: pluviômetros e satélites', 'Em 2024 o veranico máximo',
                   'Em 2019: não terminaram na janela', '"em 0 de 10 anos" não quer dizer'):
        assert pedaco in texto, pedaco
    assert texto.lower().count('vai chover') == 1          # só na frase que diz que o relato NÃO prevê
    for proibida in ('recomend', 'ideal', 'melhor', 'pior', 'deve chover', 'risco baixo', 'risco alto', 'deve plantar'):
        assert proibida not in texto.lower(), proibida
    mensal['aguas'] = dict(mensal['aguas'], regra_nao_separa=True, ja_no_primeiro=8)
    assert 'não tem estação seca marcada' in em_texto(dict(mensal=mensal))
    print('relato.py: autoteste ok')


if __name__ == '__main__':
    _autoteste()
