"""Dados INVENTADOS para o exemplo (`--demo`) e para os testes: um lugar que não
existe, com verão chuvoso e inverno seco. Nenhum número aqui veio de estação,
de satélite ou de fazenda de verdade.

O sorteio tem semente fixa: o exemplo dá sempre os mesmos números.

Teste embutido: python scripts/sintetico.py
"""

import calendar
import datetime
import random

NOME = 'Fazenda Exemplo (dados inventados)'
LATITUDE = -16.0
# janeiro a dezembro: chuva (mm), média das mínimas e média das máximas (°C)
CHUVA = (265, 215, 220, 105, 35, 10, 6, 15, 55, 140, 225, 270)
TMIN = (20.5, 20.4, 20.2, 19.0, 16.5, 14.8, 14.5, 16.2, 19.0, 20.6, 20.6, 20.6)
TMAX = (29.5, 29.8, 29.8, 29.6, 28.6, 28.0, 28.4, 30.8, 32.6, 32.0, 30.0, 29.4)


def _dia(sorteio, data):
    m = data.month - 1
    dias = calendar.monthrange(data.year, data.month)[1]
    chance = min(0.72, 0.06 + CHUVA[m] / (dias * 11.0))
    chuva = round(sorteio.expovariate(chance * dias / CHUVA[m]), 1) if sorteio.random() < chance else 0.0
    frio = 2.0 if chuva > 15 else 0.0
    tmin = round(TMIN[m] + sorteio.gauss(0, 1.4))
    tmax = max(tmin + 3, round(TMAX[m] + sorteio.gauss(0, 1.8) - frio))
    return chuva, tmin, tmax


def diaria(inicio, fim, semente=2026):
    """Lista de (data, chuva, mínima, máxima), um item por dia. O sorteio começa em 01/01/2014."""
    sorteio, saida = random.Random(semente), []
    data = datetime.date(2014, 1, 1)
    while data <= fim:
        valores = _dia(sorteio, data)
        if data >= inicio:
            saida.append((data,) + valores)
        data += datetime.timedelta(days=1)
    return saida


def mensal(ano_inicial=2015, ano_final=2024, semente=2026):
    """Lista de (ano, mês, chuva, média das mínimas, média das máximas), agregada da série diária."""
    dias = diaria(datetime.date(ano_inicial, 1, 1), datetime.date(ano_final, 12, 31), semente)
    saida = []
    for ano in range(ano_inicial, ano_final + 1):
        for mes in range(1, 13):
            do_mes = [d for d in dias if d[0].year == ano and d[0].month == mes]
            saida.append((ano, mes, round(sum(d[1] for d in do_mes), 1),
                          round(sum(d[2] for d in do_mes) / len(do_mes), 1),
                          round(sum(d[3] for d in do_mes) / len(do_mes), 1)))
    return saida


def _br(v):
    return f'{v:,.1f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def arquivo_mensal(ano_inicial=2015, ano_final=2024):
    """A tabela mensal no formato compacto, com as linhas de controle."""
    linhas = mensal(ano_inicial, ano_final)
    texto = ['# DADOS INVENTADOS: tabela mensal no formato compacto (mês, chuva, média das mínimas, média das máximas)',
             f'local: {LATITUDE}, -50.0', f'periodo: 01/01/{ano_inicial} a 31/12/{ano_final}',
             f'total: {_br(sum(l[2] for l in linhas))}', 'normal: ' + ' '.join(_br(c) for c in CHUVA)]
    texto += [f'{a}-{m:02d} {_br(c)} {tn} {tx}' for a, m, c, tn, tx in linhas]
    return '\n'.join(texto) + '\n'


def arquivo_diario(inicio=datetime.date(2024, 7, 1), fim=datetime.date(2025, 6, 30)):
    """A tabela diária no formato compacto, com as linhas de controle."""
    dias = diaria(inicio, fim)
    texto = ['# DADOS INVENTADOS: tabela diária no formato compacto (data, chuva, mínima, máxima)',
             f'local: {LATITUDE}, -50.0', f'periodo: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}',
             f'total: {_br(sum(d[1] for d in dias))}',
             f'temperatura: {min(d[2] for d in dias)} {max(d[3] for d in dias)}']
    texto += [f'{d:%Y-%m-%d} {_br(c)} {tn} {tx}' for d, c, tn, tx in dias]
    return '\n'.join(texto) + '\n'


def texto_da_ferramenta(inicio=datetime.date(2024, 10, 1), fim=datetime.date(2024, 10, 31)):
    """Os mesmos dias no jeito que a ferramenta de clima escreve, para testar a leitura do texto colado."""
    dias = diaria(inicio, fim)
    texto = [f'Chuva — {LATITUDE}, -50.0 ({inicio:%d/%m/%Y} a {fim:%d/%m/%Y}, {len(dias)} dias):',
             f'RESUMO: total {_br(sum(d[1] for d in dias))} mm · confiança alta',
             f'TEMPERATURA: graus-dia 0 (base 10°C) · mín {min(d[2] for d in dias)}°C e máx {max(d[3] for d in dias)}°C no período',
             '']
    texto += [f'{d:%Y-%m-%d}: chuva {_br(c)} mm · temp {tn}–{tx}°C · umid 60% · vento 8km/h' for d, c, tn, tx in dias]
    return '\n'.join(texto) + '\n'


if __name__ == '__main__':
    m = mensal()
    assert len(m) == 120 and m == mensal() and all(tx > tn for _, _, _, tn, tx in m)
    por_mes = [sum(l[2] for l in m if l[1] == k) / 10 for k in range(1, 13)]
    assert all(abs(a - b) < 0.45 * b + 12 for a, b in zip(por_mes, CHUVA)), por_mes       # perto das normais inventadas
    assert por_mes[0] > 150 > 40 > por_mes[6]
    d = diaria(datetime.date(2024, 7, 1), datetime.date(2025, 6, 30))
    assert len(d) == 365 and d[0][0] == datetime.date(2024, 7, 1) and all(c >= 0 for _, c, _, _ in d)
    assert arquivo_mensal().count('\n') == 125 and arquivo_diario().count('\n') == 370
    assert 'chuva' in texto_da_ferramenta() and texto_da_ferramenta().count('umid') == 31
    print('sintetico OK')
