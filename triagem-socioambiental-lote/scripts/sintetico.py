"""Quatro respostas inventadas do dossiê, no formato de texto que a ferramenta
devolve, para a demonstração e os testes. Não são imóveis de verdade: os
números de CAR, os nomes e os valores foram criados para o exemplo.

Teste embutido: python scripts/sintetico.py
"""

IMOVEIS = [
    ('GO-5200000-0A1B2C3D4E5F60718293A4B5C6D7E8F9', 'Sítio Exemplo Um'),
    ('GO-5200000-112233445566778899AABBCCDDEEFF00', 'Fazenda Exemplo Dois'),
    ('MT-5100000-ABCDEF0123456789ABCDEF0123456789', 'Fazenda Exemplo Três'),
    ('MT-5100000-00FFEEDDCCBBAA998877665544332211', 'Chácara Exemplo Quatro'),
]
# área, município, nativa ha e %, aberta depois de 2008/2019/2020, PRODES 2020+ (pol, ha), 2019, 2008–18, DETER (alertas, ha, depois, ha),
# UC (n, ha), TI (n, ha), embargos (n, ha, ponto), perto, declive médio e máximo, argila, textura
DADOS = [
    (842.6, 'Cidade Exemplo A/GO', 201.3, 23.9, (41.8, 12.4, 6.1), (3, 6.1), (1, 4.0), (2, 31.7), (2, 1.9, 1, 0.7),
     (0, 0.0), (0, 0.0), (1, 5.2, 0), 2, (6.4, 28.0), 44.1, 'argilosa'),
    (1530.0, 'Cidade Exemplo A/GO', 612.0, 40.0, (0.0, 0.0, 0.0), (0, 0.0), (0, 0.0), (0, 0.0), (0, 0.0, 0, 0.0),
     (1, 88.5), (0, 0.0), (0, 0.0, 0), 1, (3.1, 17.5), 31.0, 'média'),
    (3210.4, 'Cidade Exemplo B/MT', 1444.7, 45.0, (310.2, 0.0, 0.0), None, None, None, None,
     None, None, None, None, (2.2, 9.8), 52.3, 'muito argilosa'),
    (64.9, 'Cidade Exemplo B/MT', 9.7, 14.9, (2.1, 0.0, 0.0), (0, 0.0), (0, 0.0), (1, 2.1), (0, 0.0, 0, 0.0),
     (0, 0.0), (1, 12.3), (0, 0.0, 1), 0, (8.9, 35.2), 18.6, 'arenosa'),
]


def _n(v, casas=1):
    if float(v).is_integer():
        texto = f'{int(v):,}'
    else:
        texto = f'{v:,.{casas}f}'.rstrip('0').rstrip('.')
    return texto.replace(',', '§').replace('.', ',').replace('§', '.')


def respostas():
    """[(nome do arquivo, texto)] — uma resposta por imóvel, com as linhas IMOVEL e FICHA no alto."""
    saida = []
    for k, ((car, nome), d) in enumerate(zip(IMOVEIS, DADOS), 1):
        area, cidade, nat, nat_pct, aberta, p20, p19, p08, deter, uc, ti, emb, perto, declive, argila, textura = d
        linhas = [
            f'IMOVEL: {car}', f'FICHA: dossie-imovel-{k}.pdf',
            f'DOSSIÊ DE USO E OCUPAÇÃO DO SOLO pronto: PDF de 18 páginas — {nome}, {_n(area)} ha, {cidade}. Perímetro: consulta pública do SICAR.',
            'COMO DIZER À PESSOA: o documento é o PDF; aqui vai o resumo dos FATOS que estão nele, cada um com a fonte.', '',
            f'- O QUE O CAR DECLARA (consulta pública do SICAR, em 10/11/2025): situação do cadastro: Ativo; condição da análise: '
            f'Aguardando análise; área declarada: {_n(area * 0.998, 2)} ha; áreas declaradas — Reserva legal {_n(area * 0.2, 2)} ha.',
            f'- USO DO SOLO (mapeamento anual de uso e cobertura, mapa de 2024): vegetação nativa {_n(nat)} ha ({_n(nat_pct)}%); maiores classes — '
            f'Lavoura {_n(area * 0.5)} ha (50%); Pastagem {_n(area * 0.2)} ha (20%). Vegetação nativa aberta — depois de 2008: '
            f'{_n(aberta[0])} ha; depois de 2019: {_n(aberta[1])} ha; depois de 2020: {_n(aberta[2])} ha.',
        ]
        if p20 is not None:
            linhas.append(
                f'- PRODES E DETER (INPE): PRODES 2020 em diante (depois de 31/07/2019): {p20[0]} polígono(s), {_n(p20[1])} ha; '
                f'PRODES 2019: {p19[0]} polígono(s), {_n(p19[1])} ha; PRODES de 2008 a 2018: {p08[0]} polígono(s), {_n(p08[1])} ha; '
                f'DETER desde 01/11/2023: {deter[0]} alerta(s), {_n(deter[1])} ha ({deter[2]} depois da última imagem do PRODES, {_n(deter[3])} ha).')
        linhas.append(f'- RELEVO (terreno de 30 m): altitude de 400 a 520 m; declive médio de {_n(declive[0])}% (máximo {_n(declive[1])}%).')
        linhas.append('- IMAGEM EM COR REAL (Copernicus Sentinel-2 L2A): cena de 08/11/2025, 98,2% do perímetro sem nuvem.')
        if uc is not None:
            linhas.append(
                '- RESTRIÇÕES (bases públicas do CNUC/MMA, da FUNAI, do IBAMA e do ICMBio, na data de cada uma): '
                f'{uc[0]} unidade(s) de conservação sobrepõe(m) o perímetro ({_n(uc[1])} ha); {ti[0]} terra(s) indígena(s) ({_n(ti[1])} ha); '
                f'{emb[0]} termo(s) de embargo tocam o perímetro ({_n(emb[1])} ha com contorno; {emb[2]} marcado(s) por ponto), '
                f'sem nome nem documento de pessoa; {perto} item(ns) perto.')
        linhas.append(
            f'- SOLO (SoilGrids 2.0, ISRIC — ESTIMATIVA de um mapa mundial de 250 m, não medição): argila de 0–30 cm {_n(argila)}%, '
            f'textura {textura}; carbono 15 g/kg; estoque de carbono de 0–30 cm 45 t/ha.')
        if p20 is None:
            linhas.append('NÃO SAIU DESTA VEZ (o PDF marca a seção; as outras não dependem dela): PRODES e DETER — a base não respondeu; '
                          'Restrições — a base não respondeu. Diga isso à pessoa e ofereça gerar de novo depois.')
        linhas += ['', 'O documento reúne fatos de bases públicas e de satélite, cada um com a fonte e a data; não é laudo, parecer nem recomendação.']
        saida.append((f'imovel-{k}.txt', '\n'.join(linhas) + '\n'))
    return saida


def _autoteste():
    r = respostas()
    assert len(r) == 4 and r == respostas()
    assert 'IMOVEL: GO-5200000-0A1B2C3D4E5F60718293A4B5C6D7E8F9' in r[0][1] and '842,6 ha, Cidade Exemplo A/GO' in r[0][1]
    assert '- PRODES E DETER' not in r[2][1] and 'NÃO SAIU DESTA VEZ' in r[2][1] and '3.210,4 ha' in r[2][1]
    print('sintetico.py: autoteste ok (4 imóveis inventados; o 3º com duas seções que não saíram)')


if __name__ == '__main__':
    _autoteste()
