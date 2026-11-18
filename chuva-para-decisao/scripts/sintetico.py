"""Dados INVENTADOS para a demonstração e para os testes, no formato de texto que
as ferramentas de clima devolvem. Nenhum número aqui é de lugar de verdade.

As séries têm resposta conhecida: o início e o fim das águas de cada ano são
plantados em uma data, e os testes conferem se as regras devolvem essas datas.

Teste embutido: python scripts/sintetico.py
"""

import calendar
import datetime as dt

import numpy as np

LOCAL = 'Fazenda Exemplo (dados inventados)'
CLIMA = {7: 6, 8: 14, 9: 55, 10: 140, 11: 230, 12: 270, 1: 280, 2: 220, 3: 210, 4: 95, 5: 30, 6: 10}   # mm por mês
TEMP = {7: 21.5, 8: 23.5, 9: 25.5, 10: 26.0, 11: 25.0, 12: 24.5, 1: 24.5, 2: 24.5, 3: 24.5, 4: 24.0, 5: 22.0, 6: 21.0}
INICIOS = [(9, 20), (9, 28), (10, 3), (10, 5), (10, 8), (10, 12), (10, 15), (10, 18), (10, 22), (11, 5)]
FINS = [(3, 28), (4, 2), (4, 6), (4, 9), (4, 12), (4, 15), (4, 19), (4, 23), (4, 27), (5, 4)]
ANOS = list(range(2015, 2025))            # dez janelas de plantio; os fins caem no ano seguinte


def _mm(v):
    return f'{v:,.1f}'.replace(',', '§').replace('.', ',').replace('§', '.')


def texto_mensal(anos=20, primeiro=2005, semente=11):
    """Tabela mensal inventada, de julho de `primeiro` a junho, `anos` anos agrícolas."""
    rng = np.random.default_rng(semente)
    linhas, total, gdd_total = [], 0.0, 0.0
    for a in range(anos):
        for passo in range(12):
            mes = (6 + passo) % 12 + 1
            ano = primeiro + a + (1 if mes < 7 else 0)
            chuva = round(float(CLIMA[mes] * rng.gamma(6.0, 1 / 6.0)), 1)
            if mes == 10 and a % 4 == 1:      # um outubro falho a cada quatro anos
                chuva = round(chuva * 0.35, 1)
            media = TEMP[mes] + float(rng.normal(0, 0.5))
            gdd = round((media - 10.0) * calendar.monthrange(ano, mes)[1], 1)
            total += chuva
            gdd_total += gdd
            desvio = (chuva / CLIMA[mes] - 1) * 100
            linhas.append(f'{ano}-{mes:02d}: {_mm(chuva)} mm (média {_mm(CLIMA[mes])} mm → {desvio:+.0f}%) · temp média '
                          f'{media - 5.5:.1f}–{media + 5.5:.1f}°C · graus-dia {gdd:g}')
    fim = dt.date(primeiro + anos, 6, 30)
    dias = (fim - dt.date(primeiro, 7, 1)).days + 1
    cabeca = [f'Chuva — {LOCAL} (01/07/{primeiro} a 30/06/{primeiro + anos}, {dias} dias):',
              f'RESUMO: total {_mm(total)} mm · média histórica (1991–2020) do mesmo período: '
              f'{_mm(sum(CLIMA.values()) * anos)} mm · confiança alta',
              f'TEMPERATURA: graus-dia {round(gdd_total, 1):g} (base 10°C) · médias das mínimas 18.5°C e das máximas '
              '29.5°C', '']
    return '\n'.join(cabeca + linhas) + '\n'


def _resumo_do_bloco(inicio, mm):
    """As três primeiras linhas, como a ferramenta as escreve, a partir dos dias inventados."""
    fim = inicio + dt.timedelta(days=len(mm) - 1)
    maior = max(range(len(mm)), key=lambda k: (mm[k], -k))
    melhor, atual, ini = (0, None, None), 0, None
    for k, v in enumerate(mm):
        if v < 2.0:
            ini = k if atual == 0 else ini
            atual += 1
            if atual > melhor[0]:
                melhor = (atual, ini, k)
        else:
            atual = 0
    br = lambda d: f'{d.day:02d}/{d.month:02d}/{d.year}'  # noqa: E731
    veranico = f'veranico máx {melhor[0]} dia(s)'
    if melhor[0]:
        veranico += f' ({br(inicio + dt.timedelta(days=melhor[1]))} a {br(inicio + dt.timedelta(days=melhor[2]))})'
    return [f'Chuva — {LOCAL} ({br(inicio)} a {br(fim)}, {len(mm)} dias):',
            f'RESUMO: total {_mm(sum(mm))} mm · média histórica (1991–2020) do mesmo período: 380,0 mm · confiança alta',
            f'AGRO: {sum(1 for v in mm if v >= 2.0)} dia(s) de chuva · {veranico} · maior chuva {_mm(mm[maior])} mm em '
            f'{br(inicio + dt.timedelta(days=maior))}']


def _chuva_firme(rng, n):
    """Dias de estação chuvosa: chove em cerca de metade dos dias e nunca fica 6 dias seguidos sem chuva."""
    mm, secos = [], 0
    for _ in range(n):
        if rng.random() < 0.55 or secos >= 5:
            mm.append(round(float(2.5 + rng.gamma(1.6, 6.0)), 1))
            secos = 0
        else:
            mm.append(0.0)
            secos += 1
    return mm


def dias_do_plantio(k, semente=3):
    """Janela de 15/09 a 30/11 do ano k: seca até a véspera do início plantado, chuva firme depois."""
    rng = np.random.default_rng(semente + k)
    inicio = dt.date(ANOS[k], 9, 15)
    n = (dt.date(ANOS[k], 11, 30) - inicio).days + 1
    t = (dt.date(ANOS[k], *INICIOS[k]) - inicio).days
    mm = [round(float(rng.choice([0.0, 0.0, 0.0, 0.3, 0.8])), 1) for _ in range(t)] + [26.0] \
        + _chuva_firme(rng, n - t - 1)
    if k in (0, 2, 4):                       # veranico de 12 dias, bem depois do início
        a = t + 33
        mm[a:a + 12] = [0.0] * 12
        mm[a - 1], mm[a + 12] = max(mm[a - 1], 6.0), max(mm[a + 12], 6.0)
    return inicio, [min(v, 25.9) if i != t else v for i, v in enumerate(mm)]


def dias_do_fim(k, semente=40):
    """Janela de 01/03 a 31/05 do ano seguinte: chuva firme até o fim plantado, seca depois."""
    rng = np.random.default_rng(semente + k)
    ano = ANOS[k] + 1
    inicio = dt.date(ano, 3, 1)
    n = (dt.date(ano, 5, 31) - inicio).days + 1
    t = (dt.date(ano, *FINS[k]) - inicio).days
    mm = _chuva_firme(rng, t) + [9.0] + [0.0] * 15
    cauda = n - len(mm)
    mm += [round(float(rng.choice([0.0, 0.0, 0.0, 0.4, 4.0])), 1) for _ in range(max(cauda, 0))]
    return inicio, mm[:n]


def _texto(blocos, com_dias):
    partes = []
    for inicio, mm in blocos:
        partes += _resumo_do_bloco(inicio, mm)
        if com_dias:        # as linhas de dia, como a ferramenta devolve
            partes += [f'{(inicio + dt.timedelta(days=k)).isoformat()}: chuva {_mm(v)} mm · temp 21–33°C · umid 60% · '
                       'vento 9km/h' for k, v in enumerate(mm)]
        else:               # o jeito resumido: só os mm, na ordem
            partes += ['mm: ' + ' '.join(_mm(v) for v in mm[i:i + 31]) for i in range(0, len(mm), 31)]
        partes.append('')
    return '\n'.join(partes)


def texto_plantio(com_dias=False):
    return _texto([dias_do_plantio(k) for k in range(len(ANOS))], com_dias)


def texto_fim(com_dias=False):
    return _texto([dias_do_fim(k) for k in range(len(ANOS))], com_dias)


CONTEXTO = ('Chuva deste ano, de 01/07/2025 a 14/11/2025 (dado até 14/11/2025), comparada com 27 anos (1998–2024):\n'
            '- Desde 1º de julho choveu 310 mm — mais do que em 6 de cada 10 anos nesta mesma data (um ano típico tem '
            '280 mm até aqui; metade dos anos ficou entre 230 e 330).\n'
            '- De hoje até 31/12, em metade dos anos choveu entre 300 e 420 mm (ano típico: 360). Isso é o normal da '
            'região, não uma previsão.\n\n'
            'COMO RESPONDER: repasse essas frases como estão.')

ESCOLHAS = dict(inicia=7, cortes_mes=[50.0, 100.0], firme_mm=100.0, gdd_de=10, gdd_ate=2, gdd_alvo=1400.0,
                seco_mm=2.0, veranico_dias=[7, 10, 15], cortes_decendio=[20.0, 40.0],
                regra_inicio=dict(acum_mm=20.0, acum_dias=3, falso_dias=10, falso_janela=30), fim_dias=15)


def resultado_demo():
    """O resultado completo da demonstração, com as escolhas de ESCOLHAS (que na vida real são do usuário)."""
    import chuva
    e = ESCOLHAS
    r = dict(local=LOCAL)
    r['mensal'] = chuva.montar_mensal(texto_mensal(), e['inicia'], e['cortes_mes'], e['firme_mm'], e['gdd_de'],
                                      e['gdd_ate'], e['gdd_alvo'])
    r['janela'] = chuva.montar_janela(texto_plantio(), e['seco_mm'], e['veranico_dias'], e['cortes_decendio'],
                                      e['regra_inicio'])
    r['fim'] = chuva.montar_fim(texto_fim(), e['seco_mm'], e['fim_dias'])
    r['duracao'] = chuva.duracao_das_aguas(r)
    r['contexto'] = chuva.ler_contexto(CONTEXTO)
    r['fontes'] = [('demonstração', ['Chuva e graus-dia: exemplo inventado, sem dado de verdade.'])]
    return r


# ------------------------------------------------------------------ autoteste
def _autoteste():
    import janela
    import leitura
    import mensal

    m = leitura.ler_mensal(texto_mensal())
    meses, notas = leitura.conferir_mensal(m)
    assert len(meses) == 240 and sum('fecha' in n for n in notas) == 2 and m['local'] == LOCAL
    assert len(mensal.anos_agricolas(meses)) == 20 and m['normal'][1] == 280.0

    for com_dias in (False, True):
        js, _ = leitura.conferir_conjunto(leitura.ler_janelas(texto_plantio(com_dias)))
        assert len(js) == 10 and all(len(j['mm']) == 77 for j in js)
        achados = [janela.inicio_das_aguas(j, 2.0, 20.0, 3, 10, 30) for j in js]
        # os nove primeiros fecham na data plantada; o de 05/11 cai a menos de 30 dias do fim da janela
        for k in range(9):
            assert achados[k]['situacao'] == 'ok' and achados[k]['data'] == dt.date(ANOS[k], *INICIOS[k]), (k, achados[k])
        assert achados[9]['situacao'] == 'sem conferência' and achados[9]['data'] == dt.date(2024, 11, 5)
        assert achados[9]['faltam'] == 5
        ver = janela.veranicos(js, 2.0, [12])
        # veranico de 12 dias plantado em 3 anos; nos outros, a seca do começo da janela pode passar disso
        for k in (0, 2, 4):
            assert ver['linhas'][k]['quantos'][12] >= 1
        assert ver['linhas'][0]['maior']['dias'] == 12 and ver['linhas'][0]['maior']['borda'] is False

        fs, _ = leitura.conferir_conjunto(leitura.ler_janelas(texto_fim(com_dias)))
        fins = [janela.fim_das_aguas(j, 2.0, 15) for j in fs]
        for k in range(10):
            assert fins[k]['situacao'] == 'ok' and fins[k]['data'] == dt.date(ANOS[k] + 1, *FINS[k]), (k, fins[k])

    r = resultado_demo()
    assert r['janela']['n'] == 10 and r['fim']['datas']['resumo']['determinados'] == 10
    assert len(r['duracao']) == 9 and r['duracao'][0]['dias'] == (dt.date(2016, 3, 28) - dt.date(2015, 9, 20)).days + 1
    assert r['contexto'][0].startswith('Chuva deste ano') and len(r['contexto']) == 3
    print('sintetico.py: autoteste ok')


if __name__ == '__main__':
    _autoteste()
