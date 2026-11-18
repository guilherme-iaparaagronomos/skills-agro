"""Lê as respostas das ferramentas da ClaudIA Sat e da ClaudIA Clima coladas em
arquivos de texto, do jeito que vieram.

Entende três formatos:

- `curva_com_chuva`: o título com o período, a linha CHUVA, a lista VERANICOS e
  as linhas da curva ("Área: 01/10/2023 0,21 · 16/10/2023 0,27 · ..." ou
  "Talhão Sede: ...");
- `curva_indice`: uma linha por imagem ("2023-10-01: média 0.21 (...)" ou, com
  vários talhões, "  2023-10-01: 0.21" embaixo de "Talhão Sede (12.3 ha, 40 pontos):");
- a linha RESUMO da `clima_historico` do mesmo período, que traz a chuva e a
  média histórica.

Um arquivo pode ter uma safra ou várias: cada título de `curva_com_chuva`
começa uma safra nova.

Teste embutido: python scripts/leitura.py
"""

import re
from datetime import date
from pathlib import Path

TITULO = re.compile(r'([A-Za-z]{3,6}) cruzado com a chuva de (\d{2}/\d{2}/\d{4}) a (\d{2}/\d{2}/\d{4}) \((\d+) dias\)')
PAR_BR = re.compile(r'(\d{2}/\d{2}/\d{4})\s+(-?\d+(?:,\d+)?)')
LINHA_BR = re.compile(r'^\s*(Área|Area|Talhão\s+.+?|Talhao\s+.+?)\s*:\s*(\d{2}/\d{2}/\d{4}\s+-?\d.*)$')
LINHA_ISO = re.compile(r'^\s*(\d{4}-\d{2}-\d{2})\s*:\s*(?:média\s+|media\s+)?(-?\d+(?:[.,]\d+)?)')
BLOCO_TALHAO = re.compile(r'^\s*Talh[ãa]o\s+(.+?)\s*\(\s*[\d.,?]+\s*ha\s*,\s*(\d+)\s*pontos?\s*\)\s*:\s*$')
CURVA_UNICA = re.compile(r'^\s*(Área completa|Talh[ãa]o\s+.+?)\s+—.*Curva de ([A-Za-z]{3,6}) com (\d+) ponto')
CURVAS_MULTI = re.compile(r'^\s*Curvas de ([A-Za-z]{3,6}) por talhão')
CHUVA = re.compile(r'^\s*CHUVA:\s*total\s+([\d.,]+)\s*mm(?:\s*·\s*(\d+)\s*dia\(s\) de chuva)?')
SEM_DADO = re.compile(r'(\d+)\s*dia\(s\) SEM DADO')
VERANICOS = re.compile(r'^\s*VERANICOS\s*\((.+?)\)\s*:\s*(\d+|nenhum)')
VERANICO = re.compile(r'^\s*-\s*de (\d{2}/\d{2}/\d{4}) a (\d{2}/\d{2}/\d{4}) \((\d+) dias, ([\d.,]+) mm no total\)')
RESUMO = re.compile(r'RESUMO:\s*total\s+([\d.,]+)\s*mm(?:\s*·\s*média histórica \(1991[–-]2020\) do mesmo período:\s*([\d.,]+)\s*mm\s*→\s*([+\-−]?\d+)\s*%)?')
PERIODO = re.compile(r'^\s*PER[IÍ]ODO\s*:\s*(\d{2}/\d{2}/\d{4})\s+a\s+(\d{2}/\d{2}/\d{4})', re.IGNORECASE)
BLOCO_DE_FONTES = re.compile(r'^\s*FONTES DOS DADOS\b')          # o bloco com que a ferramenta fecha a resposta
ITEM_DE_FONTE = re.compile(r'^\s*[-•]\s+(.+)$')
FONTE_SOLTA = re.compile(r'^\s*Fontes?:\s*(.+)$', re.IGNORECASE)   # a linha "Fonte: ..." avulsa
ANO_DA_FONTE = re.compile(r'\((\d{4})\)')
INSTRUCAO = re.compile(r'\s+(?:NÃO|NUNCA|SEMPRE)\b')


class LeituraInvalida(Exception):
    """O texto não tem o que a análise precisa. A mensagem diz o que falta."""


def data_br(texto):
    d, m, a = texto.split('/')
    return date(int(a), int(m), int(d))


def data_iso(texto):
    a, m, d = texto.split('-')
    return date(int(a), int(m), int(d))


def num_br(texto):
    """'1.234,5' -> 1234.5 ; '0,62' -> 0.62"""
    return float(texto.replace('.', '').replace(',', '.'))


def num_solto(texto):
    """Número de uma linha em formato de dado: '0.62' ou '0,62'."""
    return float(texto.replace(',', '.'))


def _nome(rotulo):
    rotulo = rotulo.strip()
    if rotulo.lower().startswith(('área', 'area')):
        return 'Área'
    return re.sub(r'^Talh[ãa]o\s+', '', rotulo).strip()


def _nova(origem):
    return {'origem': origem, 'indice': None, 'inicio': None, 'fim': None, 'dias': None, 'periodo_informado': False,
            'chuva': None, 'veranicos': None, 'normal': None, 'curvas': {}, 'pontos_declarados': {}, 'avisos': [],
            'fontes': []}


def _guardar_fonte(lista, texto):
    texto = ' '.join(texto.split())
    if texto and texto not in lista:
        lista.append(texto)


def juntar_fontes(listas):
    """Junta as linhas de fonte de várias respostas, sem repetir e na ordem em que aparecem. Linhas que só mudam no
    ano entre parênteses (o ano dos dados do satélite) viram uma só, com os anos em ordem."""
    anos, ordem = {}, []
    for linha in (l for lista in listas for l in lista):
        achados = ANO_DA_FONTE.findall(linha)
        chave = ANO_DA_FONTE.sub('(@)', linha) if len(achados) == 1 else linha
        if chave not in anos:
            anos[chave] = set()
            ordem.append(chave)
        if len(achados) == 1:
            anos[chave].add(achados[0])
    return [c.replace('(@)', '(' + ', '.join(sorted(anos[c])) + ')') if anos[c] else c for c in ordem]


def fontes_de(safras):
    """As fontes dos dados como as ferramentas escreveram no fim de cada resposta colada. A linha da temperatura
    fica de fora: o histórico só usa o índice, a chuva e a média histórica."""
    return [f for f in juntar_fontes(s.get('fontes', []) for s in safras) if not f.lower().startswith('temperatura')]


def ler_texto(texto, origem='texto'):
    """Devolve a lista de safras encontradas no texto (uma por título de curva_com_chuva; sem título, uma só)."""
    safras, atual, talhao_iso, em_fontes = [], None, None, False
    for bruta in texto.replace('\r\n', '\n').split('\n'):
        linha = bruta.rstrip()
        m = TITULO.search(linha)
        if m:
            atual = _nova(origem)
            safras.append(atual)
            atual.update(indice=m.group(1).upper(), inicio=data_br(m.group(2)), fim=data_br(m.group(3)),
                         dias=int(m.group(4)), periodo_informado=True)
            talhao_iso, em_fontes = None, False
            continue
        if atual is None:
            if not linha.strip():
                continue
            atual = _nova(origem)
            safras.append(atual)
        # as fontes de cada dado, como a ferramenta escreveu no fim da resposta: guardadas inteiras
        if BLOCO_DE_FONTES.match(linha):
            em_fontes = True
            continue
        if em_fontes:
            m = ITEM_DE_FONTE.match(linha)
            if m:
                _guardar_fonte(atual['fontes'], m.group(1))
                continue
            em_fontes = False
        m = FONTE_SOLTA.match(linha)
        if m:       # depois da fonte, o que vem em maiúsculas ("NÃO nomeie...") é instrução para a IA, não fonte
            _guardar_fonte(atual['fontes'], INSTRUCAO.split(m.group(1))[0])
            continue
        m = PERIODO.match(linha)
        if m:
            if atual['curvas']:      # uma linha PERÍODO depois de uma curva começa outra safra
                atual = _nova(origem)
                safras.append(atual)
                talhao_iso = None
            atual.update(inicio=data_br(m.group(1)), fim=data_br(m.group(2)), periodo_informado=True)
            continue
        m = CHUVA.match(linha)
        if m:
            sem = SEM_DADO.search(linha)
            atual['chuva'] = {'total_mm': num_br(m.group(1)), 'dias_chuva': int(m.group(2)) if m.group(2) else None,
                              'sem_dado': int(sem.group(1)) if sem else 0}
            continue
        m = VERANICOS.match(linha)
        if m:
            atual['veranicos'] = {'regua': m.group(1), 'n': 0 if m.group(2) == 'nenhum' else int(m.group(2)), 'lista': []}
            continue
        m = VERANICO.match(linha)
        if m and atual['veranicos'] is not None:
            atual['veranicos']['lista'].append({'de': data_br(m.group(1)), 'ate': data_br(m.group(2)),
                                                'dias': int(m.group(3)), 'mm': num_br(m.group(4))})
            continue
        m = RESUMO.search(linha)
        if m:
            atual['normal'] = {'total_mm': num_br(m.group(1)),
                               'normal_mm': num_br(m.group(2)) if m.group(2) else None,
                               'dif_pct': int(m.group(3).replace('−', '-')) if m.group(3) else None}
            continue
        m = LINHA_BR.match(linha)
        if m:
            pares = [(data_br(d), num_br(v)) for d, v in PAR_BR.findall(m.group(2))]
            if pares:
                atual['curvas'].setdefault(_nome(m.group(1)), []).extend(pares)
            continue
        m = CURVAS_MULTI.match(linha)
        if m:
            atual['indice'] = atual['indice'] or m.group(1).upper()
            continue
        m = CURVA_UNICA.match(linha)
        if m:
            talhao_iso = _nome(m.group(1)) if not m.group(1).startswith('Área') else 'Área'
            atual['indice'] = atual['indice'] or m.group(2).upper()
            atual['pontos_declarados'][talhao_iso] = int(m.group(3))
            continue
        m = BLOCO_TALHAO.match(linha)
        if m:
            talhao_iso = m.group(1).strip()
            atual['pontos_declarados'][talhao_iso] = int(m.group(2))
            continue
        m = LINHA_ISO.match(linha)
        if m:
            atual['curvas'].setdefault(talhao_iso or 'Área', []).append((data_iso(m.group(1)), num_solto(m.group(2))))
            continue
    safras = [s for s in safras if s['curvas'] or s['chuva'] or s['normal']]
    for s in safras:
        _fechar(s)
    return safras


def _fechar(s):
    if not s['curvas']:
        raise LeituraInvalida(f'{s["origem"]}: não achei nenhuma linha de curva (data e valor). Cole a resposta da '
                              'ferramenta como veio, com as linhas "Área: ..." ou "Talhão ...: ...".')
    for nome, pontos in s['curvas'].items():
        pontos.sort()
        for d, v in pontos:
            if not -1.0 <= v <= 1.0:
                raise LeituraInvalida(f'{s["origem"]}: valor {v} em {d:%d/%m/%Y} ({nome}) fora da faixa de um índice '
                                      '(−1 a 1). Confira a cópia da linha.')
        declarado = s['pontos_declarados'].get(nome)
        if declarado is not None and declarado != len(pontos):
            raise LeituraInvalida(f'{s["origem"]}: a ferramenta informou {declarado} pontos para {nome} e o arquivo tem '
                                  f'{len(pontos)}. Falta ou sobra linha na cópia.')
    datas = [d for pontos in s['curvas'].values() for d, _ in pontos]
    if s['inicio'] is None:
        s['inicio'], s['fim'] = min(datas), max(datas)
        s['avisos'].append('o período da consulta não está no arquivo: usei a primeira e a última imagem como limites')
    fora = [d for d in datas if d < s['inicio'] or d > s['fim']]
    if fora:
        raise LeituraInvalida(f'{s["origem"]}: há imagem de {min(fora):%d/%m/%Y} fora do período '
                              f'{s["inicio"]:%d/%m/%Y} a {s["fim"]:%d/%m/%Y}. Duas safras foram coladas juntas sem o título?')
    s['dias'] = (s['fim'] - s['inicio']).days + 1
    s['indice'] = s['indice'] or 'NDVI'
    s['rotulo'] = rotulo_da_safra(s['inicio'], s['fim'])


def rotulo_da_safra(inicio, fim):
    """'2023/24' quando a janela vira o ano; '2023' quando cabe em um ano só."""
    return f'{inicio.year}/{str(fim.year)[2:]}' if fim.year != inicio.year else str(inicio.year)


def ler_pasta(caminho):
    """Lê todos os .txt e .md de uma pasta (ou um arquivo só). Devolve as safras em ordem de data."""
    raiz = Path(caminho)
    if not raiz.exists():
        raise LeituraInvalida(f'não achei {caminho}')
    arquivos = [raiz] if raiz.is_file() else sorted(p for p in raiz.iterdir() if p.suffix.lower() in ('.txt', '.md'))
    if not arquivos:
        raise LeituraInvalida(f'{caminho}: nenhum arquivo .txt ou .md na pasta')
    safras = []
    for arq in arquivos:
        achadas = ler_texto(arq.read_text(encoding='utf-8-sig'), arq.name)
        if not achadas:
            raise LeituraInvalida(f'{arq.name}: não achei curva nenhuma. Cole a resposta da ferramenta como veio.')
        safras.extend(achadas)
    return conferir_conjunto(safras)


def conferir_conjunto(safras):
    safras = sorted(safras, key=lambda s: (s['inicio'], s['fim']))
    indices = sorted({s['indice'] for s in safras})
    if len(indices) > 1:
        raise LeituraInvalida(f'as safras estão em índices diferentes ({", ".join(indices)}). Use o mesmo índice em todas.')
    for a, b in zip(safras, safras[1:]):
        if a['inicio'] == b['inicio'] and a['fim'] == b['fim']:
            raise LeituraInvalida(f'{a["origem"]} e {b["origem"]} trazem o mesmo período '
                                  f'({a["inicio"]:%d/%m/%Y} a {a["fim"]:%d/%m/%Y}). Tire a cópia repetida.')
        if b['inicio'] <= a['fim']:
            a['avisos'].append(f'a janela se sobrepõe à da safra seguinte ({b["rotulo"]})')
    rotulos = {}
    for s in safras:
        rotulos.setdefault(s['rotulo'], []).append(s)
    for rotulo, grupo in rotulos.items():
        if len(grupo) > 1:
            for s in grupo:
                s['rotulo'] = f'{s["inicio"]:%m/%Y}–{s["fim"]:%m/%Y}'
    return safras


def talhoes_de(safras):
    """Os nomes de talhão na ordem em que aparecem."""
    nomes = []
    for s in safras:
        for nome in s['curvas']:
            if nome not in nomes:
                nomes.append(nome)
    return nomes


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    r1 = (
        'Área completa — 123,4 ha. NDVI cruzado com a chuva de 01/10/2023 a 31/03/2024 (183 dias):\n'
        'CHUVA: total 1.234,5 mm · 87 dia(s) de chuva · maior chuva 65,2 mm em 12/01/2024 · confiança alta · 2 dia(s) SEM DADO (quebram o veranico)\n'
        'VERANICOS (7 ou mais dias seguidos com menos de 2 mm por dia): 2\n'
        '- de 01/10/2023 a 12/10/2023 (12 dias, 3,2 mm no total): sem imagem antes no período; nenhuma imagem limpa durante; primeira imagem DEPOIS em 14/10/2023 — NDVI 0,21\n'
        '- de 02/02/2024 a 09/02/2024 (8 dias, 0,0 mm no total): última imagem ANTES em 01/02/2024 — NDVI 0,71\n'
        '\n'
        'CURVA DE NDVI (média por cena):\n'
        'Área: 14/10/2023 0,21 · 24/10/2023 0,27 · 13/12/2023 0,67 · 01/02/2024 0,71 · 12/03/2024 0,40\n'
        '\n'
        'RESUMO: total 1.230,0 mm · média histórica (1991–2020) do mesmo período: 1.400,0 mm → -12% · confiança alta\n'
    )
    s = ler_texto(r1, 'r1')
    assert len(s) == 1, s
    s = s[0]
    assert (s['indice'], s['inicio'], s['fim'], s['dias']) == ('NDVI', date(2023, 10, 1), date(2024, 3, 31), 183)
    assert s['chuva'] == {'total_mm': 1234.5, 'dias_chuva': 87, 'sem_dado': 2}, s['chuva']
    assert s['veranicos']['n'] == 2 and s['veranicos']['lista'][0]['dias'] == 12 and s['veranicos']['lista'][1]['mm'] == 0.0
    assert s['curvas']['Área'][0] == (date(2023, 10, 14), 0.21) and len(s['curvas']['Área']) == 5
    assert s['normal'] == {'total_mm': 1230.0, 'normal_mm': 1400.0, 'dif_pct': -12}, s['normal']
    assert s['rotulo'] == '2023/24' and s['fontes'] == []

    # o bloco de fontes com que a ferramenta fecha a resposta: lido inteiro, sem confundir com a lista de veranicos
    bloco = ('\nCOMO RESPONDER: descreva o que os dados mostram.\n\n'
             'FONTES DOS DADOS (cite no fim da resposta a fonte de cada dado que você usar, como está):\n'
             '- Índice: satélite de exemplo. Dados do satélite de exemplo ({ano}) — texto da licença.\n'
             '- Chuva: instituto de exemplo A e produto de exemplo B (universidade de exemplo).\n')
    sf = ler_texto(r1 + bloco.format(ano=2024) + '\nFonte: Média histórica: produto de exemplo B. NÃO nomeie nada.\n', 'rf')[0]
    assert sf['fontes'] == ['Índice: satélite de exemplo. Dados do satélite de exemplo (2024) — texto da licença.',
                            'Chuva: instituto de exemplo A e produto de exemplo B (universidade de exemplo).',
                            'Média histórica: produto de exemplo B.'], sf['fontes']
    assert sf['veranicos']['n'] == 2 and len(sf['veranicos']['lista']) == 2 and len(sf['curvas']['Área']) == 5
    outra = ler_texto(r1.replace('2023', '2021').replace('2024', '2022') + bloco.format(ano=2022), 'rg')[0]
    juntas = fontes_de([outra, sf])
    assert juntas == ['Índice: satélite de exemplo. Dados do satélite de exemplo (2022, 2024) — texto da licença.',
                      'Chuva: instituto de exemplo A e produto de exemplo B (universidade de exemplo).',
                      'Média histórica: produto de exemplo B.'], juntas
    assert fontes_de([s]) == [] and fontes_de([dict(fontes=['Chuva: A.', 'Temperatura: modelo de exemplo.'])]) == ['Chuva: A.']

    # vários talhões e duas safras no mesmo arquivo
    r2 = (
        '3 talhões — 80 ha. NDVI cruzado com a chuva de 01/07/2022 a 30/06/2023 (365 dias):\n'
        'CHUVA: total 900,0 mm · 60 dia(s) de chuva\n'
        'VERANICOS (7 ou mais dias seguidos com menos de 2 mm por dia): nenhum no período.\n'
        'CURVA DE NDVI (média por cena):\n'
        'Talhão Sede: 01/07/2022 0,30 · 01/01/2023 0,80\n'
        'Talhão Pivô 1: 01/07/2022 0,35 · 01/01/2023 0,75\n'
        '\n'
        '3 talhões — 80 ha. NDVI cruzado com a chuva de 01/07/2023 a 30/06/2024 (366 dias):\n'
        'CURVA DE NDVI (média por cena):\n'
        'Talhão Sede: 01/07/2023 0,31 · 01/01/2024 0,81\n'
    )
    s2 = ler_texto(r2, 'r2')
    assert [x['rotulo'] for x in s2] == ['2022/23', '2023/24']
    assert list(s2[0]['curvas']) == ['Sede', 'Pivô 1'] and s2[0]['veranicos']['n'] == 0
    assert talhoes_de(s2) == ['Sede', 'Pivô 1']

    # curva_indice: um talhão e vários talhões
    r3 = ('Talhão Sede — 12.3 ha. Curva de NDVI com 3 ponto(s) (Copernicus Sentinel-2 L2A — estatísticas da OagronomIA):\n'
          '2023-10-01: média 0.21 (mín 0.1 / máx 0.4; p10 0.15 / p90 0.3; 98% válida)\n'
          '2023-11-01: média 0.45 (mín 0.1 / máx 0.4; p10 0.15 / p90 0.3; 98% válida)\n'
          '2023-12-01: média 0.8 (mín 0.1 / máx 0.4; p10 0.15 / p90 0.3; 98% válida)\n')
    s3 = ler_texto(r3, 'r3')[0]
    assert s3['curvas']['Sede'] == [(date(2023, 10, 1), 0.21), (date(2023, 11, 1), 0.45), (date(2023, 12, 1), 0.8)]
    assert not s3['periodo_informado'] and s3['avisos']
    r4 = ('Curvas de NDRE por talhão — 2 talhão(ões), média por cena (Copernicus Sentinel-2 L2A — processado pela OagronomIA):\n\n'
          'Talhão A (10 ha, 2 pontos):\n  2023-10-01: 0.21\n  2023-11-01: 0.4\n\n'
          'Talhão B (5 ha, 2 pontos):\n  2023-10-01: 0.3\n  2023-11-01: 0.5\n')
    s4 = ler_texto(r4, 'r4')[0]
    assert s4['indice'] == 'NDRE' and s4['curvas']['B'][1] == (date(2023, 11, 1), 0.5)

    # recusas
    for ruim, trecho in [
        ('NDVI cruzado com a chuva de 01/10/2023 a 31/03/2024 (183 dias):\nCHUVA: total 10,0 mm\n', 'nenhuma linha de curva'),
        ('Área: 14/10/2023 2,10 · 24/10/2023 0,27\n', 'fora da faixa'),
        ('Talhão A (10 ha, 3 pontos):\n  2023-10-01: 0.21\n  2023-11-01: 0.4\n', 'informou 3 pontos'),
        ('NDVI cruzado com a chuva de 01/10/2023 a 31/03/2024 (183 dias):\nÁrea: 14/10/2022 0,21 · 24/10/2023 0,27\n', 'fora do período'),
    ]:
        try:
            ler_texto(ruim, 'ruim')
        except LeituraInvalida as e:
            assert trecho in str(e), (trecho, str(e))
        else:
            raise AssertionError(f'devia recusar: {trecho}')
    try:
        conferir_conjunto(ler_texto(r1, 'a') + ler_texto(r1, 'b'))
    except LeituraInvalida as e:
        assert 'mesmo período' in str(e)
    else:
        raise AssertionError('devia recusar a safra repetida')
    try:
        conferir_conjunto(ler_texto(r1, 'a') + ler_texto(r4, 'b'))
    except LeituraInvalida as e:
        assert 'índices diferentes' in str(e)
    else:
        raise AssertionError('devia recusar índices misturados')
    print('leitura.py: autoteste ok (4 formatos lidos, bloco de fontes, 6 recusas)')


if __name__ == '__main__':
    _autoteste()
