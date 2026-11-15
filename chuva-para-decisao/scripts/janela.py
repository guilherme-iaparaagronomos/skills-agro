"""A janela crítica dia a dia, comparada entre os anos.

Da mesma janela do calendário em N anos saem: a chuva por decêndio (em quantos
anos passou de um corte), os veranicos por uma régua explícita (D ou mais dias
seguidos com menos de L mm cada), a data em que as águas firmaram e a data em
que terminaram, cada uma por uma regra com os números à vista.

As contagens são sempre "em k de N anos". Nada aqui é previsão.

Teste embutido: python scripts/janela.py
"""

import calendar
import datetime as dt

import numpy as np

from leitura import MESES, dm, rotulo

ORDINAL = {1: '1º', 2: '2º', 3: '3º'}


def _dec(dia):
    return 1 if dia <= 10 else 2 if dia <= 20 else 3


def _limites(ano, mes, dec):
    ultimo = calendar.monthrange(ano, mes)[1]
    return {1: (1, 10), 2: (11, 20), 3: (21, ultimo)}[dec]


def decendios(j):
    """Decêndios do calendário que a janela toca, na ordem: chave (mês, decêndio), soma e se está inteiro."""
    saida, ordem = {}, []
    for k, v in enumerate(j['mm']):
        d = j['inicio'] + dt.timedelta(days=k)
        chave = (d.month, _dec(d.day))
        if chave not in saida:
            a, b = _limites(d.year, d.month, chave[1])
            inteiro = dt.date(d.year, d.month, a) >= j['inicio'] and dt.date(d.year, d.month, b) <= j['fim']
            saida[chave] = dict(mes=d.month, dec=chave[1], inteiro=inteiro, valores=[],
                                nome=f'{ORDINAL[chave[1]]} dec. de {MESES[d.month - 1]}')
            ordem.append(chave)
        saida[chave]['valores'].append(v)
    return [saida[c] for c in ordem]


def por_decendio(janelas, cortes, seco_mm):
    """Uma linha por decêndio inteiro da janela: total de cada ano e as contagens."""
    linhas = []
    por_ano = [(rotulo(j), decendios(j)) for j in janelas]
    for k, ref in enumerate(por_ano[-1][1]):
        if not ref['inteiro']:
            linhas.append(dict(nome=ref['nome'], inteiro=False))
            continue
        totais, sem_chuva, sem_dado = [], 0, 0
        for nome_ano, decs in por_ano:
            valores = decs[k]['valores']
            if any(v is None for v in valores):
                sem_dado += 1
                continue
            totais.append((float(sum(valores)), nome_ano))
            sem_chuva += all(v < seco_mm for v in valores)
        if not totais:
            linhas.append(dict(nome=ref['nome'], inteiro=True, n=0, sem_dado=sem_dado))
            continue
        v = [t[0] for t in totais]
        linhas.append(dict(nome=ref['nome'], inteiro=True, n=len(v), sem_dado=sem_dado, mediana=float(np.median(v)),
                           menor=min(totais)[0], ano_menor=min(totais)[1], maior=max(totais)[0],
                           ano_maior=max(totais)[1], sem_chuva=sem_chuva,
                           acima={c: sum(1 for x in v if x >= c) for c in cortes},
                           por_ano={nome: t for t, nome in totais}))
    return linhas


def sequencias_secas(mm, seco_mm):
    """Trechos (primeiro índice, último índice) de dias seguidos com menos de `seco_mm`. Dia sem dado quebra."""
    trechos, ini = [], None
    for k, v in enumerate(list(mm) + [None]):
        seco = v is not None and v < seco_mm
        if seco and ini is None:
            ini = k
        elif not seco and ini is not None:
            trechos.append((ini, k - 1))
            ini = None
    return trechos


def veranicos(janelas, seco_mm, lista_dias):
    """Por ano: a maior sequência seca e quantas passam de cada D. No conjunto: em quantos anos houve."""
    linhas = []
    for j in janelas:
        n = len(j['mm'])
        trechos = sequencias_secas(j['mm'], seco_mm)
        maior = max(trechos, key=lambda t: (t[1] - t[0], -t[0])) if trechos else None
        linha = dict(rotulo=rotulo(j), total=j['total'], dias_chuva=j['dias_chuva'], da_ferramenta=j['veranico'],
                     maior_chuva=j['maior'], confianca=j['confianca'], quantos={}, maior=None)
        if maior:
            linha['maior'] = dict(dias=maior[1] - maior[0] + 1, de=j['inicio'] + dt.timedelta(days=maior[0]),
                                  ate=j['inicio'] + dt.timedelta(days=maior[1]),
                                  borda=maior[0] == 0 or maior[1] == n - 1)
        for d in lista_dias:
            linha['quantos'][d] = sum(1 for a, b in trechos if b - a + 1 >= d)
        linhas.append(linha)
    resumo = []
    for d in lista_dias:
        com = [l['rotulo'] for l in linhas if l['quantos'][d] > 0]
        resumo.append(dict(dias=d, anos=len(com), quais=com, n=len(linhas)))
    return dict(seco_mm=seco_mm, linhas=linhas, resumo=resumo)


def inicio_das_aguas(j, seco_mm, acum_mm, acum_dias, falso_dias, falso_janela):
    """Primeiro dia de chuva em que a regra do início fecha.

    Regra: o dia tem pelo menos `seco_mm`; do dia em diante, `acum_dias` dias
    somam pelo menos `acum_mm`; e nos `falso_janela` dias seguintes não há
    `falso_dias` dias seguidos com menos de `seco_mm` (falso início).
    """
    mm = j['mm']
    n = len(mm)
    soma = lambda a, b: sum(v for v in mm[a:b] if v is not None)  # noqa: E731
    falsos = 0
    for t in range(n):
        if mm[t] is None or mm[t] < seco_mm or soma(t, t + acum_dias) < acum_mm:
            continue
        ate = min(n - 1, t + falso_janela)
        if any(b - a + 1 >= falso_dias for a, b in sequencias_secas(mm[t + 1:ate + 1], seco_mm)):
            falsos += 1
            continue
        d = j['inicio'] + dt.timedelta(days=t)
        if t + falso_janela > n - 1:
            return dict(situacao='sem conferência', data=d, faltam=t + falso_janela - (n - 1), falsos=falsos)
        return dict(situacao='ok', data=d, faltam=0, falsos=falsos)
    return dict(situacao='não firmou na janela', data=None, faltam=0, falsos=falsos)


def fim_das_aguas(j, seco_mm, fim_dias):
    """Último dia de chuva antes da primeira sequência de `fim_dias` ou mais dias com menos de `seco_mm`."""
    mm = j['mm']
    for a, b in sequencias_secas(mm, seco_mm):
        if b - a + 1 >= fim_dias:
            if a == 0:
                return dict(situacao='já tinham terminado antes da janela', data=None, faltam=0)
            if mm[a - 1] is None:
                return dict(situacao='sem dado no dia anterior ao período seco', data=None, faltam=0)
            return dict(situacao='ok', data=j['inicio'] + dt.timedelta(days=a - 1), faltam=0)
    # sequência seca mais curta que `fim_dias` no fim da janela ainda não é o fim: faltam dias para saber
    return dict(situacao='não terminaram na janela', data=None, faltam=0)


def _posicao(d, j):
    return (d - j['inicio']).days


def datas_por_ano(janelas, funcao):
    """Aplica a regra a cada ano e resume: mais cedo, mais tarde, metade dos anos até, e o acumulado por decêndio."""
    linhas = []
    for j in janelas:
        r = funcao(j)
        r['rotulo'] = rotulo(j)
        r['posicao'] = None if r['data'] is None else _posicao(r['data'], j)
        linhas.append(r)
    ok = sorted((l for l in linhas if l['situacao'] == 'ok'), key=lambda l: l['posicao'])
    resumo = dict(n=len(linhas), determinados=len(ok), cedo=None, tarde=None, metade=None, acumulado=[],
                  outros={})
    for l in linhas:
        if l['situacao'] != 'ok':
            resumo['outros'].setdefault(l['situacao'], []).append(l['rotulo'])
    if ok:
        resumo['cedo'] = dict(data=ok[0]['data'], rotulo=ok[0]['rotulo'])
        resumo['tarde'] = dict(data=ok[-1]['data'], rotulo=ok[-1]['rotulo'])
        # "metade dos anos até": a data em que pelo menos metade de TODOS os anos da contagem já tinha fechado a regra
        precisa = (len(linhas) + 1) // 2
        resumo['metade'] = ok[precisa - 1]['data'] if len(ok) >= precisa else None
        ref = janelas[-1]
        for d in decendios(ref):
            ano_fim = ref['inicio'].year + (1 if d['mes'] < ref['inicio'].month else 0)
            fim_dec = min(dt.date(ano_fim, d['mes'], _limites(ano_fim, d['mes'], d['dec'])[1]), ref['fim'])
            limite = _posicao(fim_dec, ref)
            resumo['acumulado'].append(dict(ate=fim_dec, anos=sum(1 for l in ok if l['posicao'] <= limite)))
    return dict(linhas=linhas, resumo=resumo)


def duracao(inicios, fins):
    """Dias entre o início (janela de plantio) e o fim (janela seguinte) das águas, quando os dois fecharam."""
    por_ano = {l['rotulo'][:4]: l for l in inicios['linhas'] if l['situacao'] == 'ok'}
    linhas = []
    for f in fins['linhas']:
        if f['situacao'] != 'ok':
            continue
        # o fim pertence às águas que começaram no ano anterior, a não ser que as duas janelas sejam do mesmo ano
        for ano in (f['data'].year - 1, f['data'].year):
            i = por_ano.get(str(ano))
            if i and i['data'] < f['data'] and (f['data'] - i['data']).days <= 330:
                linhas.append(dict(rotulo=f'{i["data"].year}/{str(f["data"].year)[2:]}', inicio=i['data'],
                                   fim=f['data'], dias=(f['data'] - i['data']).days + 1))
                break
    return linhas


# ------------------------------------------------------------------ autoteste
def _janela(ano, mm, ini=(9, 1)):
    inicio = dt.date(ano, *ini)
    return dict(inicio=inicio, fim=inicio + dt.timedelta(days=len(mm) - 1), mm=list(mm), total=float(sum(
        v for v in mm if v is not None)), dias_chuva=None, veranico=None, maior=None, confianca='alta')


def _autoteste():
    regra = dict(seco_mm=2.0, acum_mm=20.0, acum_dias=3, falso_dias=10, falso_janela=30)
    n = 91                                   # 01/09 a 30/11

    def chuvoso(de, ate=n):                  # 6 mm dia sim, dia não
        return {k: 6.0 for k in range(de, ate, 2)}

    def serie(marcas):
        mm = [0.0] * n
        for k, v in marcas.items():
            mm[k] = v
        return mm

    # A: seco até 30/09; 25 mm em 01/10 (índice 30) e chuva firme depois → início em 01/10
    a = _janela(2020, serie({30: 25.0, **chuvoso(32)}))
    # B: 22 mm em 12/09 (índice 11) e 15 dias secos (falso início); 10 + 12 mm em 10 e 11/10 → início em 10/10
    b = _janela(2021, serie({11: 22.0, 39: 10.0, 40: 12.0, **chuvoso(42)}))
    # C: só firma em 20/11 (índice 80): faltam 20 dias de janela para conferir o falso início
    c = _janela(2022, serie({80: 25.0, **chuvoso(82)}))
    # D: nunca soma 20 mm em 3 dias
    d = _janela(2023, serie({k: 3.0 for k in range(5, n, 4)}))
    # E: 20 mm exatos em três dias a partir de 05/10 (índice 34), com veranico de 9 dias depois (não chega a 10)
    e = _janela(2024, serie({34: 2.0, 35: 8.0, 36: 10.0, 46: 5.0, **chuvoso(47)}))
    r = [inicio_das_aguas(j, **regra) for j in (a, b, c, d, e)]
    assert r[0]['situacao'] == 'ok' and r[0]['data'] == dt.date(2020, 10, 1) and r[0]['falsos'] == 0
    assert r[1]['situacao'] == 'ok' and r[1]['data'] == dt.date(2021, 10, 10) and r[1]['falsos'] == 1
    assert r[2]['situacao'] == 'sem conferência' and r[2]['data'] == dt.date(2022, 11, 20) and r[2]['faltam'] == 20
    assert r[3]['situacao'] == 'não firmou na janela' and r[3]['data'] is None
    assert r[4]['situacao'] == 'ok' and r[4]['data'] == dt.date(2024, 10, 5)
    # com falso início de 9 dias na regra, o E vira falso início; depois dele nenhum trio de dias soma 20 mm
    r9 = inicio_das_aguas(e, **dict(regra, falso_dias=9))
    assert r9['falsos'] == 1 and r9['data'] is None and r9['situacao'] == 'não firmou na janela'
    # e com 12 mm em 3 dias na regra, os dias 05 e 06/10 são falsos inícios e a regra fecha em 18/10 (6 + 0 + 6)
    r12 = inicio_das_aguas(e, **dict(regra, falso_dias=9, acum_mm=12.0))
    assert r12['falsos'] == 2 and r12['data'] == dt.date(2024, 10, 18), r12
    # dia sem dado não conta como seco nem como chuva
    furo = _janela(2020, serie({30: 25.0, **chuvoso(32)}))
    furo['mm'][30] = None
    assert inicio_das_aguas(furo, **regra)['data'] != dt.date(2020, 10, 1)

    resumo = datas_por_ano([a, b, c, d, e], lambda j: inicio_das_aguas(j, **regra))['resumo']
    assert resumo['n'] == 5 and resumo['determinados'] == 3
    assert resumo['cedo'] == dict(data=dt.date(2020, 10, 1), rotulo='2020')
    assert resumo['tarde'] == dict(data=dt.date(2021, 10, 10), rotulo='2021')
    assert resumo['metade'] == dt.date(2021, 10, 10)          # 3 de 5: a terceira data
    assert resumo['outros'] == {'sem conferência': ['2022'], 'não firmou na janela': ['2023']}
    acumulado = {dm(x['ate']): x['anos'] for x in resumo['acumulado']}
    assert acumulado['30/09'] == 0 and acumulado['10/10'] == 3 and acumulado['30/11'] == 3, acumulado

    # veranicos: um de 12 dias no meio e outro de 7; régua de 2 mm
    v = _janela(2020, serie({k: 6.0 for k in list(range(0, 20)) + list(range(32, 50)) + list(range(57, n))}))
    assert sequencias_secas(v['mm'], 2.0) == [(20, 31), (50, 56)]
    ver = veranicos([v, a], 2.0, [7, 10, 15])
    assert ver['linhas'][0]['maior']['dias'] == 12 and ver['linhas'][0]['maior']['de'] == dt.date(2020, 9, 21)
    assert ver['linhas'][0]['maior']['borda'] is False and ver['linhas'][0]['quantos'] == {7: 2, 10: 1, 15: 0}
    assert ver['linhas'][1]['maior']['dias'] == 30 and ver['linhas'][1]['maior']['borda'] is True
    assert [(x['dias'], x['anos']) for x in ver['resumo']] == [(7, 2), (10, 2), (15, 1)]
    assert sequencias_secas([0, None, 0, 0, 5, 1.9, 2.0], 2.0) == [(0, 0), (2, 3), (5, 5)]

    # decêndios: 2º de outubro (índices 40 a 49) com 30 mm em 3 de 5 anos
    anos = []
    for k in range(5):
        marcas = {45: 30.0 if k in (0, 2, 4) else 5.0, 62: 12.0}
        anos.append(_janela(2016 + k, serie(marcas)))
    dec = por_decendio(anos, [10, 30], 2.0)
    assert [l['nome'] for l in dec][:2] == ['1º dec. de set', '2º dec. de set'] and len(dec) == 9
    out2 = next(l for l in dec if l['nome'] == '2º dec. de out')
    assert out2['n'] == 5 and out2['acima'] == {10: 3, 30: 3} and out2['mediana'] == 30 and out2['sem_chuva'] == 0
    assert out2['menor'] == 5 and out2['ano_menor'] == '2016' or out2['ano_menor'] == '2017'
    assert next(l for l in dec if l['nome'] == '1º dec. de nov')['acima'] == {10: 5, 30: 0}
    assert next(l for l in dec if l['nome'] == '1º dec. de out')['sem_chuva'] == 5
    meia = por_decendio([_janela(2016 + k, serie({})[14:], ini=(9, 15)) for k in range(5)], [10], 2.0)
    assert meia[0]['nome'] == '2º dec. de set' and meia[0]['inteiro'] is False and meia[1]['inteiro'] is True
    com_furo = [dict(x, mm=list(x['mm'])) for x in anos]
    com_furo[1]['mm'][45] = None
    assert next(l for l in por_decendio(com_furo, [10], 2.0) if l['nome'] == '2º dec. de out')['n'] == 4

    # fim das águas: janela de 01/03 a 31/05; chuva até 10/04 (índice 40) e seca depois
    m = 92
    f1 = _janela(2021, [6.0 if k <= 40 and k % 2 == 0 else 0.0 for k in range(m)], ini=(3, 1))
    f2 = _janela(2022, [0.0] * m, ini=(3, 1))
    f3 = _janela(2023, [6.0 if k % 2 == 0 else 0.0 for k in range(m)], ini=(3, 1))
    f4 = _janela(2024, [6.0 if k < m - 8 else 0.0 for k in range(m)], ini=(3, 1))
    fins = [fim_das_aguas(j, 2.0, 15) for j in (f1, f2, f3, f4)]
    assert fins[0]['situacao'] == 'ok' and fins[0]['data'] == dt.date(2021, 4, 10)
    assert fins[1]['situacao'].startswith('já tinham terminado') and fins[2]['situacao'] == 'não terminaram na janela'
    assert fins[3]['situacao'] == 'não terminaram na janela' and fins[3]['data'] is None     # só 8 dias secos no fim

    # duração: início em 01/10/2020 e fim em 10/04/2021 = 192 dias
    ini = datas_por_ano([a, b], lambda j: inicio_das_aguas(j, **regra))
    fim = datas_por_ano([f1, f2], lambda j: fim_das_aguas(j, 2.0, 15))
    dur = duracao(ini, fim)
    assert dur == [dict(rotulo='2020/21', inicio=dt.date(2020, 10, 1), fim=dt.date(2021, 4, 10), dias=192)]
    print('janela.py: autoteste ok')


if __name__ == '__main__':
    _autoteste()
