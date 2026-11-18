"""Respostas inventadas, no mesmo formato de texto que a ferramenta devolve, para
a demonstração e para os testes. Não são dados de fazenda nenhuma.

Quatro safras emendadas (1º de julho a 30 de junho) e três áreas de forma conhecida:

- Sede: um ciclo por safra;
- Baixada: dois ciclos por safra (safra e segunda safra);
- Pasto: oscila pouco, sem ciclo pela amplitude padrão.

Teste embutido: python scripts/sintetico.py
"""

import math
import random
from datetime import date, timedelta

PISO = 0.18
# (dia do início, dia do pico, dia do fim, topo) a contar de 1º de julho; um deslocamento por safra
FORMAS = {
    'Sede': [(105, 195, 275, 0.86)],
    'Baixada': [(95, 155, 210, 0.84), (222, 268, 330, 0.70)],
}
DESLOCAMENTO = {2021: 0, 2022: 12, 2023: -6, 2024: 5}       # dias: a safra adianta ou atrasa
CHUVA = {2021: (1452.3, 1398.0, 4, 92), 2022: (1049.6, 1401.0, -25, 71), 2023: (1381.9, 1399.0, -1, 88), 2024: (1524.4, 1402.0, 9, 97)}
VERANICOS = {
    2021: [((2021, 7, 3), (2021, 9, 21), 81, 6.4), ((2022, 1, 14), (2022, 1, 22), 9, 1.1)],
    2022: [((2022, 7, 1), (2022, 10, 2), 94, 3.0), ((2022, 12, 20), (2023, 1, 9), 21, 4.8), ((2023, 2, 11), (2023, 2, 19), 9, 0.0)],
    2023: [((2023, 7, 6), (2023, 9, 14), 71, 8.2)],
    2024: [((2024, 7, 2), (2024, 9, 25), 86, 2.5), ((2025, 3, 3), (2025, 3, 10), 8, 0.6)],
}


def _valor(nome, ano, dia):
    """Valor sem ruído da área no dia `dia` (a contar de 1º de julho de `ano`)."""
    if nome == 'Pasto':
        return 0.46 + 0.07 * math.sin(2 * math.pi * (dia - 150) / 365)
    v = PISO
    for d0, dp, d1, topo in FORMAS[nome]:
        d0, dp, d1 = (x + DESLOCAMENTO[ano] for x in (d0, dp, d1))
        if d0 <= dia <= dp:
            v = max(v, PISO + (topo - PISO) * (dia - d0) / (dp - d0))
        elif dp < dia <= d1:
            v = max(v, PISO + (topo - PISO) * (d1 - dia) / (d1 - dp))
    return v


def gabarito(fracao=0.30):
    """Para cada área com ciclo: a lista (início, pico, fim) que a detecção deve achar."""
    saida = {}
    for nome, formas in FORMAS.items():
        saida[nome] = []
        for ano in sorted(DESLOCAMENTO):
            base = date(ano, 7, 1)
            for d0, dp, d1, _ in formas:
                d0, dp, d1 = (x + DESLOCAMENTO[ano] for x in (d0, dp, d1))
                saida[nome].append((base + timedelta(days=round(d0 + fracao * (dp - d0))), base + timedelta(days=dp),
                                    base + timedelta(days=round(d1 - fracao * (d1 - dp)))))
    return saida


def _br(v, casas):
    texto = f'{v:,.{casas}f}'
    return texto.replace(',', '§').replace('.', ',').replace('§', '.')


def respostas():
    """Uma resposta de `curva_com_chuva` por safra, com a linha RESUMO da `clima_historico` embaixo."""
    sorteio = random.Random(20261115)
    textos = []
    for ano in sorted(DESLOCAMENTO):
        base, fim = date(ano, 7, 1), date(ano + 1, 6, 30)
        dias = (fim - base).days + 1
        datas = []
        for dia in range(2, dias, 5):
            d = base + timedelta(days=dia)
            nuvem = 0.45 if d.month in (11, 12, 1, 2) else 0.10
            if sorteio.random() > nuvem:
                datas.append((dia, d))
        total, normal, dif, n_chuva = CHUVA[ano]
        linhas = [f'3 talhões — 86,4 ha. NDVI cruzado com a chuva de {base:%d/%m/%Y} a {fim:%d/%m/%Y} ({dias} dias):',
                  f'CHUVA: total {_br(total, 1)} mm · {n_chuva} dia(s) de chuva · maior chuva 61,8 mm em 12/01/{ano + 1} · confiança alta',
                  f'VERANICOS (7 ou mais dias seguidos com menos de 2 mm por dia): {len(VERANICOS[ano])}']
        for de, ate, n, chuva in VERANICOS[ano]:
            linhas.append(f'- de {date(*de):%d/%m/%Y} a {date(*ate):%d/%m/%Y} ({n} dias, {_br(chuva, 1)} mm no total): '
                          'sem imagem antes no período; nenhuma imagem limpa durante; sem imagem depois no período')
        linhas += ['', 'CURVA DE NDVI (média por cena):']
        for nome in ('Sede', 'Baixada', 'Pasto'):
            pares = []
            for dia, d in datas:
                v = _valor(nome, ano, dia) + sorteio.uniform(-0.012, 0.012)
                pares.append(f'{d:%d/%m/%Y} {_br(min(0.95, max(0.05, v)), 2)}')
            linhas.append(f'Talhão {nome}: ' + ' · '.join(pares))
        linhas += ['', f'RESUMO: total {_br(total, 1)} mm · média histórica (1991–2020) do mesmo período: {_br(normal, 1)} mm → '
                       f'{dif:+d}% · confiança alta']
        # as respostas de verdade fecham com este bloco; aqui as fontes dizem que o dado é inventado
        linhas += ['', 'FONTES DOS DADOS (cite no fim da resposta a fonte de cada dado que você usar, como está):',
                   f'- Índice: exemplo inventado, sem dado de satélite de verdade ({ano + 1}).',
                   '- Chuva: exemplo inventado, sem dado de chuva de verdade.']
        textos.append('\n'.join(linhas) + '\n')
    return textos


FONTES_ESPERADAS = ['Índice: exemplo inventado, sem dado de satélite de verdade (2022, 2023, 2024, 2025).',
                    'Chuva: exemplo inventado, sem dado de chuva de verdade.']


def gravar(pasta):
    """Grava uma resposta por arquivo na pasta. Devolve os caminhos."""
    from pathlib import Path
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for ano, texto in zip(sorted(DESLOCAMENTO), respostas()):
        arq = pasta / f'safra-{ano}-{str(ano + 1)[2:]}.txt'
        arq.write_text(texto, encoding='utf-8')
        caminhos.append(arq)
    return caminhos


def _autoteste():
    a, b = respostas(), respostas()
    assert a == b and len(a) == 4, 'as respostas inventadas têm de ser sempre as mesmas'
    assert a[0].startswith('3 talhões — 86,4 ha. NDVI cruzado com a chuva de 01/07/2021 a 30/06/2022 (365 dias):')
    assert 'total 1.452,3 mm' in a[0] and '→ -25%' in a[1] and 'Talhão Baixada: ' in a[2]
    g = gabarito()
    assert len(g['Sede']) == 4 and len(g['Baixada']) == 8
    assert g['Sede'][0] == (date(2021, 7, 1) + timedelta(days=132), date(2021, 7, 1) + timedelta(days=195),
                            date(2021, 7, 1) + timedelta(days=251)), g['Sede'][0]
    print('sintetico.py: autoteste ok (4 safras inventadas, 3 áreas)')


if __name__ == '__main__':
    _autoteste()
