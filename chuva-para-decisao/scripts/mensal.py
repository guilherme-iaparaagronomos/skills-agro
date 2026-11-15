"""Calendário da chuva a partir da tabela mensal de muitos anos.

Por mês do calendário: mediana, faixa (P20 a P80), menor e maior com o ano e em
quantos anos o mês ficou abaixo de um corte. Por ano agrícola: o total e a
posição de cada ano. Pela regra mensal declarada: o mês em que as águas
firmaram e o mês em que terminaram, ano a ano. E os graus-dia acumulados a
partir de um mês de plantio.

Tudo é descrição do registro. Nada aqui é previsão.

Teste embutido: python scripts/mensal.py
"""

import calendar
import math

import numpy as np

from leitura import MESES

MESES_SEGUIDOS = 2      # a regra mensal das águas olha o mês e o seguinte


def rotulo_ano(ano, inicia):
    return str(ano) if inicia == 1 else f'{ano}/{str(ano + 1)[2:]}'


def faixa(valores):
    """Mediana, P20 e P80 (interpolação linear entre os valores ordenados)."""
    v = np.asarray(valores, float)
    return float(np.median(v)), float(np.percentile(v, 20)), float(np.percentile(v, 80))


def anos_agricolas(meses, inicia=7):
    """Anos agrícolas inteiros (12 meses seguidos a partir do mês `inicia`), com o total."""
    anos = []
    for k, m in enumerate(meses):
        if m['mes'] == inicia and k + 12 <= len(meses):
            doze = meses[k:k + 12]
            chuvas = [x['chuva'] for x in doze]
            anos.append(dict(rotulo=rotulo_ano(m['ano'], inicia), ano=m['ano'], indice=k, meses=doze,
                             total=None if any(c is None for c in chuvas) else float(sum(chuvas))))
    return anos


def calendario(meses, cortes=(), normal=None, inicia=7):
    """Uma linha por mês do calendário, na ordem do ano agrícola."""
    linhas = []
    for passo in range(12):
        mes = (inicia - 1 + passo) % 12 + 1
        pares = [(m['chuva'], m['ano']) for m in meses if m['mes'] == mes and m['chuva'] is not None]
        if not pares:
            continue
        valores = [p[0] for p in pares]
        mediana, p20, p80 = faixa(valores)
        menor, maior = min(pares), max(pares)
        linhas.append(dict(mes=mes, nome=MESES[mes - 1], n=len(pares), mediana=mediana, p20=p20, p80=p80,
                           menor=menor[0], ano_menor=menor[1], maior=maior[0], ano_maior=maior[1],
                           normal=(normal or {}).get(mes),
                           abaixo={c: sum(1 for v in valores if v < c) for c in cortes}))
    return linhas


def totais(anos):
    """Total de cada ano agrícola e a posição (1 = o que mais choveu)."""
    validos = [a for a in anos if a['total'] is not None]
    ordem = sorted(validos, key=lambda a: -a['total'])
    posicao = {a['rotulo']: k + 1 for k, a in enumerate(ordem)}
    linhas = [dict(rotulo=a['rotulo'], total=a['total'], posicao=posicao.get(a['rotulo'])) for a in anos]
    resumo = None
    if validos:
        mediana, p20, p80 = faixa([a['total'] for a in validos])
        resumo = dict(n=len(validos), mediana=mediana, p20=p20, p80=p80, menor=ordem[-1]['total'],
                      ano_menor=ordem[-1]['rotulo'], maior=ordem[0]['total'], ano_maior=ordem[0]['rotulo'])
    return linhas, resumo


def aguas(meses, firme_mm, inicia=7):
    """Regra mensal das águas, ano a ano.

    Firmaram: o primeiro mês do ano agrícola com pelo menos `firme_mm`, seguido
    de outro mês também com pelo menos `firme_mm`. Terminaram: o último mês com
    pelo menos `firme_mm` antes de dois meses seguidos abaixo disso.
    """
    chuva = [m['chuva'] for m in meses]
    linhas = []
    for k, m in enumerate(meses):
        if m['mes'] != inicia or k + 12 > len(meses):
            continue
        ini = fim = None
        situacao = 'não firmou no ano agrícola'
        for i in range(k, k + 12):
            par = chuva[i:i + MESES_SEGUIDOS]
            if len(par) < MESES_SEGUIDOS or any(c is None for c in par):
                situacao = 'sem dado para aplicar a regra'
                break
            if all(c >= firme_mm for c in par):
                ini = i
                situacao = 'ok'
                break
        if ini is not None:
            situacao_fim = 'a tabela acaba antes do fim das águas'
            for e in range(ini + 1, min(len(chuva) - 1, ini + 18)):
                par = chuva[e:e + MESES_SEGUIDOS]
                if any(c is None for c in par):
                    situacao_fim = 'sem dado para aplicar a regra'
                    break
                if all(c < firme_mm for c in par):
                    fim = e - 1
                    situacao_fim = 'ok'
                    break
        else:
            situacao_fim = '—'
        linhas.append(dict(rotulo=rotulo_ano(m['ano'], inicia), situacao=situacao, situacao_fim=situacao_fim,
                           inicio=None if ini is None else (meses[ini]['ano'], meses[ini]['mes']),
                           fim=None if fim is None else (meses[fim]['ano'], meses[fim]['mes']),
                           passo=None if ini is None else ini - k,
                           meses_de_aguas=None if ini is None or fim is None else fim - ini + 1))
    com_inicio = [l for l in linhas if l['inicio']]
    com_fim = [l for l in linhas if l['fim']]

    def contagem(itens, campo):
        cont = {}
        for l in itens:
            cont[l[campo][1]] = cont.get(l[campo][1], 0) + 1
        return [dict(mes=mes, nome=MESES[mes - 1], anos=cont[mes])
                for mes in sorted(cont, key=lambda x: (x - inicia) % 12)]

    ja_no_primeiro = sum(1 for l in com_inicio if l['passo'] == 0)
    return dict(firme_mm=firme_mm, linhas=linhas, n=len(linhas), n_inicio=len(com_inicio), n_fim=len(com_fim),
                inicio_por_mes=contagem(com_inicio, 'inicio'), fim_por_mes=contagem(com_fim, 'fim'),
                regra_nao_separa=bool(linhas) and ja_no_primeiro * 2 > len(linhas),
                ja_no_primeiro=ja_no_primeiro)


def graus_dia(meses, de_mes, ate_mes, alvo=None):
    """Graus-dia somados do mês `de_mes` ao mês `ate_mes`, ano a ano, e os dias até um alvo.

    Os dias até o alvo contam do dia 1º do mês de plantio; dentro de cada mês os
    graus-dia são repartidos por igual entre os dias (a tabela é mensal).
    """
    n_meses = (ate_mes - de_mes) % 12 + 1
    linhas = []
    for k, m in enumerate(meses):
        if m['mes'] != de_mes:
            continue
        trecho = meses[k:k + n_meses]
        if len(trecho) < n_meses or any(x['gdd'] is None for x in trecho):
            continue
        linha = dict(rotulo=str(m['ano']) if trecho[-1]['ano'] == m['ano'] else f'{m["ano"]}/{str(m["ano"] + 1)[2:]}',
                     soma=float(sum(x['gdd'] for x in trecho)), dias=None)
        if alvo:
            acumulado, dias = 0.0, 0
            for x in meses[k:k + 12]:
                if x['gdd'] is None:
                    break
                no_mes = calendar.monthrange(x['ano'], x['mes'])[1]
                if acumulado + x['gdd'] >= alvo and x['gdd'] > 0:
                    # a folga evita que 10,000000000002 dias vire 11 por ruído de ponto flutuante
                    linha['dias'] = dias + max(1, int(math.ceil((alvo - acumulado) / (x['gdd'] / no_mes) - 1e-9)))
                    break
                acumulado += x['gdd']
                dias += no_mes
        linhas.append(linha)
    if not linhas:
        return None

    def extremos(campo):
        v = [(l[campo], l['rotulo']) for l in linhas if l[campo] is not None]
        if not v:
            return None
        return dict(n=len(v), mediana=float(np.median([x[0] for x in v])), menor=min(v)[0], ano_menor=min(v)[1],
                    maior=max(v)[0], ano_maior=max(v)[1])

    return dict(de_mes=de_mes, ate_mes=ate_mes, alvo=alvo, linhas=linhas, soma=extremos('soma'),
                dias=extremos('dias') if alvo else None,
                sem_alvo=sum(1 for l in linhas if l['dias'] is None) if alvo else 0)


def mes_mais_seco(linhas_calendario):
    return min(linhas_calendario, key=lambda l: l['mediana'])


# ------------------------------------------------------------------ autoteste
def _serie(anos, por_mes, gdd=400.0, primeiro=2000, inicia=7):
    """Série inventada: `por_mes(ano_agricola, mes)` devolve a chuva."""
    meses = []
    for a in range(anos):
        for passo in range(12):
            mes = (inicia - 1 + passo) % 12 + 1
            ano = primeiro + a + (1 if mes < inicia else 0)
            meses.append(dict(ano=ano, mes=mes, chuva=por_mes(a, mes), gdd=gdd))
    return meses


def _autoteste():
    # clima de duas estações: seco de maio a setembro, águas de outubro a abril; em 3 de 10 anos outubro falha
    def chuva(a, mes):
        if mes in (5, 6, 7, 8, 9):
            return 10.0
        if mes == 10:
            return 40.0 if a in (2, 5, 7) else 150.0
        return 200.0 + a          # cresce com o ano: o último é o que mais chove
    serie = _serie(10, chuva)
    anos = anos_agricolas(serie)
    assert len(anos) == 10 and anos[0]['rotulo'] == '2000/01' and anos[-1]['rotulo'] == '2009/10'
    assert anos[0]['total'] == 5 * 10 + 150 + 6 * 200 and anos[2]['total'] == 50 + 40 + 6 * 202
    cal = calendario(serie, cortes=(50, 100), normal={10: 148.2})
    assert [l['nome'] for l in cal][:4] == ['jul', 'ago', 'set', 'out'] and len(cal) == 12
    out = next(l for l in cal if l['mes'] == 10)
    assert out['n'] == 10 and out['mediana'] == 150 and out['abaixo'] == {50: 3, 100: 3} and out['normal'] == 148.2
    assert out['menor'] == 40 and out['ano_menor'] == 2002 and out['maior'] == 150
    jan = next(l for l in cal if l['mes'] == 1)
    assert jan['menor'] == 200 and jan['ano_menor'] == 2001 and jan['maior'] == 209 and jan['ano_maior'] == 2010
    assert abs(jan['p20'] - 201.8) < 1e-9 and abs(jan['p80'] - 207.2) < 1e-9 and jan['mediana'] == 204.5
    assert mes_mais_seco(cal)['mediana'] == 10
    linhas, resumo = totais(anos)
    assert linhas[-1]['posicao'] == 1 and resumo['ano_maior'] == '2009/10' and resumo['n'] == 10
    assert sorted(l['posicao'] for l in linhas) == list(range(1, 11))

    ag = aguas(serie, 100.0)
    # outubro firma em 7 anos; nos 3 em que falhou, novembro
    assert ag['inicio_por_mes'] == [dict(mes=10, nome='out', anos=7), dict(mes=11, nome='nov', anos=3)]
    assert ag['linhas'][2]['inicio'] == (2002, 11) and ag['linhas'][0]['inicio'] == (2000, 10)
    # terminam em abril (maio e junho abaixo); no último ano a tabela acaba antes de dar para dizer
    assert ag['fim_por_mes'] == [dict(mes=4, nome='abr', anos=10)] and ag['n_fim'] == 10
    assert ag['linhas'][0]['meses_de_aguas'] == 7 and ag['linhas'][2]['meses_de_aguas'] == 6
    assert not ag['regra_nao_separa']
    curta = aguas(serie[:-2], 100.0)        # sem maio e junho do último ano não há como fechar o fim
    assert curta['linhas'][-1]['fim'] is None or len(curta['linhas']) == 9
    sempre = aguas(_serie(6, lambda a, mes: 130.0), 100.0)
    assert sempre['regra_nao_separa'] and sempre['ja_no_primeiro'] == 6 and sempre['n_fim'] == 0
    nunca = aguas(_serie(6, lambda a, mes: 30.0), 100.0)
    assert nunca['n_inicio'] == 0 and nunca['linhas'][0]['situacao'].startswith('não firmou')
    furo = _serie(6, chuva)
    furo[15]['chuva'] = None                # outubro do 2º ano sem dado
    assert aguas(furo, 100.0)['linhas'][1]['situacao'].startswith('sem dado')
    assert anos_agricolas(furo)[1]['total'] is None and totais(anos_agricolas(furo))[1]['n'] == 5

    # graus-dia: 400 por mês; de outubro a fevereiro são 5 meses = 2000; alvo de 1400 = 3 meses e meio
    g = graus_dia(serie, 10, 2, alvo=1400)
    assert g['soma']['mediana'] == 2000 and g['soma']['n'] == 10 and g['linhas'][0]['rotulo'] == '2000/01'
    # out (31) + nov (30) + dez (31) = 92 dias e 1200 graus-dia; faltam 200 a 400/31 por dia = 15,5 → 16 dias
    assert g['linhas'][0]['dias'] == 92 + 16 and g['dias']['menor'] == 108 and g['sem_alvo'] == 0
    assert graus_dia(serie, 10, 2, alvo=999999)['sem_alvo'] == 10
    # alvo que fecha exatamente no fim de um dia: 1200 em 92 dias; e 10 dias de dezembro a mais dão 1200 + 10 * 400/31
    assert graus_dia(serie, 10, 2, alvo=1200)['linhas'][0]['dias'] == 92
    assert graus_dia(_serie(3, chuva, gdd=310.0), 12, 1, alvo=100.0)['linhas'][0]['dias'] == 10
    assert graus_dia([dict(m, gdd=None) for m in serie], 10, 2) is None
    assert graus_dia(serie, 1, 3)['linhas'][0]['rotulo'] == '2001' and graus_dia(serie, 1, 3)['soma']['mediana'] == 1200
    print('mensal.py: autoteste ok')


if __name__ == '__main__':
    _autoteste()
