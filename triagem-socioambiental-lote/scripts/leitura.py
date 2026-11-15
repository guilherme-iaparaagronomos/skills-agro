"""Lê a resposta da ferramenta `dossie_pdf` (ClaudIA Sat) colada num arquivo de
texto e tira dela os fatos de um imóvel, um por coluna.

A resposta é um resumo com uma linha por assunto ("- USO DO SOLO (...)",
"- PRODES E DETER (...)", "- RESTRIÇÕES (...)" e as demais). Assunto que não
veio fica VAZIO na planilha, nunca zero: seção que a ferramenta não conseguiu
gerar não é "nada encontrado".

No alto do arquivo a IA pode pôr duas linhas próprias:
    IMOVEL: <número do CAR, ou o nome da fazenda>
    FICHA: <nome do arquivo PDF salvo>

Teste embutido: python scripts/leitura.py
"""

import re

CAR = re.compile(r'^[A-Z]{2}-\d{7}-[0-9A-F]{32}$')
NUM = r'-?[\d.]+(?:,\d+)?'

COLUNAS = [
    ('imovel', 'Imóvel (CAR ou nome)'), ('ficha', 'Ficha (PDF)'), ('titulo', 'Título do dossiê'), ('municipio', 'Município'),
    ('area_ha', 'Área (ha)'), ('perimetro', 'Origem do perímetro'),
    ('car_situacao', 'CAR: situação do cadastro'), ('car_condicao', 'CAR: condição da análise'),
    ('car_area_declarada_ha', 'CAR: área declarada (ha)'), ('car_consultado_em', 'CAR: consultado em'),
    ('nativa_ha', 'Vegetação nativa (ha)'), ('nativa_pct', 'Vegetação nativa (%)'),
    ('uso_fonte', 'Uso do solo: fonte'), ('uso_ano', 'Uso do solo: ano do mapa'),
    ('aberta_depois_2008_ha', 'Nativa aberta depois de 2008 (ha)'), ('aberta_depois_2019_ha', 'Nativa aberta depois de 2019 (ha)'),
    ('aberta_depois_2020_ha', 'Nativa aberta depois de 2020 (ha)'),
    ('prodes_2020_poligonos', 'PRODES 2020 em diante: polígonos'), ('prodes_2020_ha', 'PRODES 2020 em diante (ha)'),
    ('prodes_2019_poligonos', 'PRODES 2019: polígonos'), ('prodes_2019_ha', 'PRODES 2019 (ha)'),
    ('prodes_2008_2018_poligonos', 'PRODES 2008 a 2018: polígonos'), ('prodes_2008_2018_ha', 'PRODES 2008 a 2018 (ha)'),
    ('deter_alertas', 'DETER: alertas'), ('deter_ha', 'DETER (ha)'),
    ('deter_depois_prodes_alertas', 'DETER depois da última imagem do PRODES: alertas'),
    ('deter_depois_prodes_ha', 'DETER depois da última imagem do PRODES (ha)'),
    ('uc_n', 'Unidades de conservação sobrepostas'), ('uc_ha', 'Sobreposição com UC (ha)'),
    ('ti_n', 'Terras indígenas sobrepostas'), ('ti_ha', 'Sobreposição com TI (ha)'),
    ('embargos_n', 'Termos de embargo que tocam o perímetro'), ('embargos_ha', 'Embargos com contorno (ha)'),
    ('embargos_por_ponto', 'Embargos marcados por ponto'), ('itens_perto', 'Itens perto do perímetro'),
    ('bases_nao_lidas', 'Bases de restrição não lidas'),
    ('declive_medio_pct', 'Declive médio (%)'), ('declive_max_pct', 'Declive máximo (%)'),
    ('argila_pct', 'Argila 0–30 cm (%), estimativa'), ('textura', 'Textura 0–30 cm, estimativa'),
    ('imagem_data', 'Imagem em cor real: data'), ('paginas', 'Páginas do PDF'),
    ('nao_saiu', 'Seções que não saíram'), ('observacoes', 'Observações do documento'),
]
NUMERICAS = {c for c, _ in COLUNAS if c.endswith(('_ha', '_pct', '_n', '_poligonos', '_alertas', '_por_ponto')) or
             c in ('itens_perto', 'bases_nao_lidas', 'paginas', 'uso_ano')}
# de que linha da resposta vem cada coluna: sem a linha, a coluna fica vazia
DA_SECAO = {
    'car': ['car_situacao', 'car_condicao', 'car_area_declarada_ha', 'car_consultado_em'],
    'uso': ['nativa_ha', 'nativa_pct', 'uso_fonte', 'uso_ano', 'aberta_depois_2008_ha', 'aberta_depois_2019_ha', 'aberta_depois_2020_ha'],
    'prodes': ['prodes_2020_poligonos', 'prodes_2020_ha', 'prodes_2019_poligonos', 'prodes_2019_ha', 'prodes_2008_2018_poligonos',
               'prodes_2008_2018_ha', 'deter_alertas', 'deter_ha', 'deter_depois_prodes_alertas', 'deter_depois_prodes_ha'],
    'restricoes': ['uc_n', 'uc_ha', 'ti_n', 'ti_ha', 'embargos_n', 'embargos_ha', 'embargos_por_ponto', 'itens_perto', 'bases_nao_lidas'],
    'relevo': ['declive_medio_pct', 'declive_max_pct'], 'solo': ['argila_pct', 'textura'], 'imagem': ['imagem_data'],
}


class LeituraInvalida(Exception):
    """O texto não é a resposta do dossiê, ou falta o que identifica o imóvel."""


def num(texto):
    """'1.669,5' -> 1669.5"""
    return float(texto.replace('.', '').replace(',', '.'))


def _n(padrao, linha, grupos=1):
    m = re.search(padrao, linha)
    if not m:
        return (None,) * grupos if grupos > 1 else None
    valores = tuple(num(g) for g in m.groups())
    return valores if grupos > 1 else valores[0]


def ler_dossie(texto, origem='texto'):
    """Devolve o dicionário de um imóvel (as chaves de COLUNAS, mais 'secoes' e 'avisos')."""
    f = {c: None for c, _ in COLUNAS}
    f['secoes'], f['avisos'] = set(), []
    linhas = [l.strip() for l in texto.replace('\r\n', '\n').split('\n')]
    achou = False
    for linha in linhas:
        m = re.match(r'^IM[OÓ]VEL\s*:\s*(.+)$', linha, flags=re.I)
        if m:
            f['imovel'] = m.group(1).strip()
            continue
        m = re.match(r'^FICHA\s*:\s*(.+)$', linha, flags=re.I)
        if m:
            f['ficha'] = m.group(1).strip()
            continue
        m = re.match(r'^DOSSIÊ DE USO E OCUPAÇÃO DO SOLO pronto: PDF de (\d+) páginas? — (.+)\. Perímetro: (.+?)\.?$', linha)
        if m:
            achou = True
            f['paginas'], f['perimetro'] = int(m.group(1)), m.group(3).strip()
            corpo = m.group(2)
            ma = re.search(rf'^(.*?), ({NUM}) ha(?:, (.+))?$', corpo)
            if ma:
                f['titulo'], f['area_ha'], f['municipio'] = ma.group(1).strip(), num(ma.group(2)), (ma.group(3) or '').strip() or None
            else:
                f['titulo'] = corpo.strip()
            continue
        if linha.startswith('- O QUE O CAR DECLARA'):
            f['secoes'].add('car')
            m = re.search(r'em (\d{2}/\d{2}/\d{4})\)', linha)
            f['car_consultado_em'] = m.group(1) if m else None
            m = re.search(r'situação do cadastro: ([^;.]+)', linha)
            f['car_situacao'] = m.group(1).strip() if m else None
            m = re.search(r'condição da análise: ([^;]+?)(?:;|\.$)', linha)
            f['car_condicao'] = m.group(1).strip() if m else None
            f['car_area_declarada_ha'] = _n(rf'área declarada: ({NUM}) ha', linha)
        elif linha.startswith('- USO DO SOLO'):
            f['secoes'].add('uso')
            m = re.match(r'^- USO DO SOLO \((.+?), mapa de (\d{4})\)', linha)
            if m:
                f['uso_fonte'], f['uso_ano'] = m.group(1), int(m.group(2))
            f['nativa_ha'], f['nativa_pct'] = _n(rf'vegetação nativa ({NUM}) ha \(({NUM})%\)', linha, 2)
            for ano in (2008, 2019, 2020):
                f[f'aberta_depois_{ano}_ha'] = _n(rf'depois de {ano}: ({NUM}) ha', linha)
        elif linha.startswith('- PRODES E DETER'):
            f['secoes'].add('prodes')
            f['prodes_2020_poligonos'], f['prodes_2020_ha'] = _n(rf'PRODES 2020 em diante[^:]*: ({NUM}) polígono\(s\), ({NUM}) ha', linha, 2)
            f['prodes_2019_poligonos'], f['prodes_2019_ha'] = _n(rf'PRODES 2019: ({NUM}) polígono\(s\), ({NUM}) ha', linha, 2)
            f['prodes_2008_2018_poligonos'], f['prodes_2008_2018_ha'] = _n(rf'PRODES de 2008 a 2018: ({NUM}) polígono\(s\), ({NUM}) ha', linha, 2)
            f['deter_alertas'], f['deter_ha'] = _n(rf'DETER[^:]*: ({NUM}) alerta\(s\), ({NUM}) ha', linha, 2)
            f['deter_depois_prodes_alertas'], f['deter_depois_prodes_ha'] = _n(
                rf'\(({NUM}) depois da última imagem do PRODES, ({NUM}) ha\)', linha, 2)
        elif linha.startswith('- RESTRIÇÕES'):
            f['secoes'].add('restricoes')
            f['uc_n'], f['uc_ha'] = _n(rf'({NUM}) unidade\(s\) de conservação sobrepõe\(m\) o perímetro \(({NUM}) ha\)', linha, 2)
            f['ti_n'], f['ti_ha'] = _n(rf'({NUM}) terra\(s\) indígena\(s\) \(({NUM}) ha\)', linha, 2)
            f['embargos_n'], f['embargos_ha'], f['embargos_por_ponto'] = _n(
                rf'({NUM}) termo\(s\) de embargo tocam o perímetro \(({NUM}) ha com contorno; ({NUM}) marcado\(s\) por ponto\)', linha, 3)
            f['itens_perto'] = _n(rf'({NUM}) item\(ns\) perto', linha)
            nao_lidas = _n(rf'Base\(s\) não lida\(s\) nesta emissão: ({NUM})', linha)
            f['bases_nao_lidas'] = 0.0 if nao_lidas is None else nao_lidas
        elif linha.startswith('- RELEVO'):
            f['secoes'].add('relevo')
            f['declive_medio_pct'], f['declive_max_pct'] = _n(rf'declive médio de ({NUM})% \(máximo ({NUM})%\)', linha, 2)
        elif linha.startswith('- SOLO'):
            f['secoes'].add('solo')
            f['argila_pct'] = _n(rf'argila de 0–30 cm ({NUM})%', linha)
            m = re.search(r'textura ([^;]+);', linha)
            f['textura'] = m.group(1).strip() if m else None
        elif linha.startswith('- IMAGEM EM COR REAL'):
            f['secoes'].add('imagem')
            m = re.search(r'cena de (\d{2}/\d{2}/\d{4})', linha)
            f['imagem_data'] = m.group(1) if m else None
        elif linha.startswith('NÃO SAIU DESTA VEZ'):
            m = re.match(r'^NÃO SAIU DESTA VEZ[^:]*: (.+?)(?:\. Diga isso.*)?$', linha)
            f['nao_saiu'] = m.group(1).strip() if m else linha
        elif linha.startswith(('OBSERVAÇÃO QUE ESTÁ NO DOCUMENTO:', 'NÃO INCLUÍDO NESTA EMISSÃO:')):
            f['observacoes'] = ((f['observacoes'] + ' ') if f['observacoes'] else '') + linha
    if not achou:
        raise LeituraInvalida(f'{origem}: não achei a primeira linha da resposta do dossiê ("DOSSIÊ DE USO E OCUPAÇÃO DO SOLO '
                              'pronto: ..."). Cole a resposta da ferramenta como veio.')
    f['imovel'] = f['imovel'] or f['titulo']
    if not f['imovel']:
        raise LeituraInvalida(f'{origem}: falta a linha "IMOVEL: <CAR ou nome>" no alto do arquivo.')
    for secao, colunas in DA_SECAO.items():
        if secao in f['secoes']:
            for c in colunas:
                if f[c] is None and c in NUMERICAS and not c.startswith('aberta_depois'):
                    f['avisos'].append(f'a linha veio, mas não li "{dict(COLUNAS)[c]}"; confira a cópia')
    if f['area_ha'] is None:
        f['avisos'].append('não li a área do imóvel na primeira linha')
    return f


def car_valido(texto):
    return bool(CAR.match(texto.strip().upper()))


# ------------------------------------------------------------------ teste embutido
EXEMPLO = (
    'IMOVEL: SP-3500000-0123456789ABCDEF0123456789ABCDEF\n'
    'FICHA: dossie-sitio-exemplo.pdf\n'
    'DOSSIÊ DE USO E OCUPAÇÃO DO SOLO pronto: PDF de 18 páginas — Sítio Exemplo, 1.234,5 ha, Cidade Exemplo/SP. Perímetro: consulta pública do SICAR.\n'
    'COMO DIZER À PESSOA: o documento é o PDF; aqui vai o resumo dos FATOS que estão nele.\n'
    '\n'
    '- O QUE O CAR DECLARA (consulta pública do SICAR, em 15/11/2026): situação do cadastro: Ativo; condição da análise: Aguardando análise; área declarada: 1.230,12 ha; áreas declaradas — Reserva legal 250,3 ha; APP 40,11 ha.\n'
    '- USO DO SOLO (MapBiomas, mapa de 2024): vegetação nativa 310,4 ha (25,1%); maiores classes — Soja 600 ha (48,6%); Pastagem 300 ha (24,3%). Vegetação nativa aberta — depois de 2008: 12,5 ha; depois de 2019: 3,2 ha; depois de 2020: 0 ha.\n'
    '- COBERTURA RECENTE (Dynamic World, de 01/08/2026 a 31/10/2026, 14 dias com imagem): Lavoura 700 ha (56,7%).\n'
    '- PRODES E DETER (INPE): PRODES 2020 em diante (depois de 31/07/2019): 2 polígono(s), 3,1 ha; PRODES 2019: 0 polígono(s), 0 ha; PRODES de 2008 a 2018: 1 polígono(s), 9,4 ha; DETER desde 01/01/2024: 1 alerta(s), 0,8 ha (1 depois da última imagem do PRODES, 0,8 ha).\n'
    '- DECLARADO NO CAR AO LADO DO OBSERVADO (só a subtração, sem interpretação): Vegetação nativa — declarado 300,5 ha, observado 310,4 ha, diferença 9,9 ha.\n'
    '- RELEVO (terreno de 30 m): altitude de 480 a 560 m; declive médio de 4,2% (máximo 31%).\n'
    '- IMAGEM EM COR REAL (Copernicus Sentinel-2 L2A): cena de 12/11/2026, 99,7% do perímetro sem nuvem.\n'
    '- RESTRIÇÕES (bases públicas do CNUC/MMA, da FUNAI, do IBAMA e do ICMBio, na data de cada uma): 1 unidade(s) de conservação sobrepõe(m) o perímetro (22,5 ha); 0 terra(s) indígena(s) (0 ha); 2 termo(s) de embargo tocam o perímetro (5,5 ha com contorno; 1 marcado(s) por ponto), sem nome nem documento de pessoa; 3 item(ns) perto.\n'
    '- SOLO (SoilGrids 2.0, ISRIC — ESTIMATIVA de um mapa mundial de 250 m, não medição): argila de 0–30 cm 38,5%, textura argilosa; carbono 14,2 g/kg; estoque de carbono de 0–30 cm 48,1 t/ha.\n'
    '\n'
    'O documento reúne fatos de bases públicas e de satélite, cada um com a fonte e a data; não é laudo, parecer nem recomendação.\n'
)


def _autoteste():
    f = ler_dossie(EXEMPLO, 'exemplo')
    assert f['imovel'].startswith('SP-3500000') and f['ficha'] == 'dossie-sitio-exemplo.pdf'
    assert (f['titulo'], f['area_ha'], f['municipio'], f['paginas']) == ('Sítio Exemplo', 1234.5, 'Cidade Exemplo/SP', 18)
    assert f['perimetro'] == 'consulta pública do SICAR'
    assert (f['car_situacao'], f['car_condicao'], f['car_area_declarada_ha'], f['car_consultado_em']) == \
        ('Ativo', 'Aguardando análise', 1230.12, '15/11/2026'), (f['car_situacao'], f['car_condicao'])
    assert (f['nativa_ha'], f['nativa_pct'], f['uso_fonte'], f['uso_ano']) == (310.4, 25.1, 'MapBiomas', 2024)
    assert (f['aberta_depois_2008_ha'], f['aberta_depois_2019_ha'], f['aberta_depois_2020_ha']) == (12.5, 3.2, 0.0)
    assert (f['prodes_2020_poligonos'], f['prodes_2020_ha'], f['prodes_2019_ha'], f['prodes_2008_2018_ha']) == (2.0, 3.1, 0.0, 9.4)
    assert (f['deter_alertas'], f['deter_ha'], f['deter_depois_prodes_alertas'], f['deter_depois_prodes_ha']) == (1.0, 0.8, 1.0, 0.8)
    assert (f['uc_n'], f['uc_ha'], f['ti_n'], f['ti_ha']) == (1.0, 22.5, 0.0, 0.0)
    assert (f['embargos_n'], f['embargos_ha'], f['embargos_por_ponto'], f['itens_perto'], f['bases_nao_lidas']) == (2.0, 5.5, 1.0, 3.0, 0.0)
    assert (f['declive_medio_pct'], f['declive_max_pct'], f['argila_pct'], f['textura']) == (4.2, 31.0, 38.5, 'argilosa')
    assert f['imagem_data'] == '12/11/2026' and not f['avisos'], f['avisos']

    # seção que não saiu fica vazia (nunca zero) e o motivo vai para a coluna própria
    sem = '\n'.join(l for l in EXEMPLO.split('\n') if not l.startswith(('- PRODES', '- RESTRIÇÕES', '- O QUE O CAR', 'IMOVEL', 'FICHA'))) + \
        'NÃO SAIU DESTA VEZ (o PDF marca a seção; as outras não dependem dela): PRODES e DETER — serviço fora do ar; Restrições — base não lida. Diga isso à pessoa e ofereça gerar de novo depois.\n'
    g = ler_dossie(sem, 'sem')
    assert g['prodes_2020_ha'] is None and g['uc_n'] is None and g['embargos_n'] is None and g['car_situacao'] is None
    assert 'PRODES e DETER — serviço fora do ar' in g['nao_saiu'] and g['imovel'] == 'Sítio Exemplo'
    # base de restrição não lida vira número na coluna própria
    h = ler_dossie(EXEMPLO.replace('3 item(ns) perto.', '3 item(ns) perto. Base(s) não lida(s) nesta emissão: 2 — o documento não informa nada sobre ela(s).'), 'h')
    assert h['bases_nao_lidas'] == 2.0
    try:
        ler_dossie('um texto qualquer', 'ruim')
    except LeituraInvalida as e:
        assert 'primeira linha' in str(e)
    else:
        raise AssertionError('devia recusar')
    assert car_valido('sp-3500000-0123456789abcdef0123456789abcdef') and not car_valido('SP-35000-XYZ')
    print(f'leitura.py: autoteste ok ({len(COLUNAS)} colunas; seção ausente fica vazia)')


if __name__ == '__main__':
    _autoteste()
