"""Lê o TEXTO que as ferramentas da ClaudIA Sat devolvem e tira dele os números
do dossiê, sem interpretar nada.

A IA cola o texto de cada ferramenta num arquivo, como veio. Aqui ele vira
dados por expressão regular e passa por conferências de soma: se um número foi
copiado errado, a conta não fecha e o dossiê avisa em vez de imprimir o erro.

Ferramentas lidas: uso_do_solo, prodes_fazenda, relevo_fazenda, imagem_satelite.
Campo que não for achado vira aviso ("não li ...") e a seção sai sem ele.
"""

import re


def numero(texto):
    """'1.669,5' → 1669.5 · '33' → 33.0 · '1669.5' → 1669.5 · '1.669' → 1669.0"""
    t = str(texto).strip().replace(' ', '').replace(' ', '')
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(\.\d{3})+', t):
        t = t.replace('.', '')
    return float(t)


_NUM = r'\d[\d.]*(?:,\d+)?'


def _area(texto):
    m = re.search(rf'— ({_NUM}) ha', texto[:400])
    return numero(m.group(1)) if m else None


def _classes(trecho):
    """'Pastagem 549,1 ha (33 %) · Cana 3,9 ha (0 %)' → [(nome, ha, pct)]"""
    achados = []
    for parte in trecho.split(' · '):
        m = re.fullmatch(rf'\s*(.+?) ({_NUM}) ha(?: \(({_NUM}) %\))?\.?\s*', parte)
        if m:
            achados.append((m.group(1).strip(), numero(m.group(2)),
                            numero(m.group(3)) if m.group(3) else None))
    return achados


def ler_uso(texto):
    """Texto de uso_do_solo → dados + avisos."""
    d, avisos = {'area_ha': _area(texto)}, []
    m = re.search(r'MapBiomas Coleção (\d+), de (\d{4}) a (\d{4})', texto)
    if m:
        d.update(colecao=int(m.group(1)), ano_inicial=int(m.group(2)), ano_final=int(m.group(3)))
    m = re.search(rf'HOJE \(mapa de (\d{{4}})\): (.*?)\. Vegetação nativa: ({_NUM}) ha \(({_NUM}) %\)', texto)
    if m:
        d['hoje'] = {'ano': int(m.group(1)), 'classes': _classes(m.group(2)),
                     'nativa_ha': numero(m.group(3)), 'nativa_pct': numero(m.group(4))}
    else:
        avisos.append('uso do solo: não li a linha "HOJE (mapa de …)"')
    d['marcos'] = []
    for m in re.finditer(rf'^- (\d{{4}})(?: \((.*?)\))?: vegetação nativa ({_NUM}) ha \(({_NUM}) %\) · (.*)$',
                         texto, re.M):
        d['marcos'].append({'ano': int(m.group(1)), 'rotulo': m.group(2) or '',
                            'nativa_ha': numero(m.group(3)), 'nativa_pct': numero(m.group(4)),
                            'classes': _classes(m.group(5))})
    if not d['marcos']:
        avisos.append('uso do solo: não li as linhas das datas-marco')
    m = re.search(r'SITUAÇÃO HOJE \(.*?\): (.*)$', texto, re.M)
    d['situacao'] = [(n, ha) for n, ha, _ in _classes(m.group(1))] if m else []
    if not d['situacao']:
        avisos.append('uso do solo: não li a linha "SITUAÇÃO HOJE"')
    m = re.search(rf'ABERTO DEPOIS DE 2008: ({_NUM}) ha · depois de 2019: ({_NUM}) ha · '
                  rf'depois de 2020: ({_NUM}) ha', texto)
    if m:
        d['aberto_desde'] = {2008: numero(m.group(1)), 2019: numero(m.group(2)), 2020: numero(m.group(3))}
    else:
        avisos.append('uso do solo: não li a linha "ABERTO DEPOIS DE 2008"')
    m = re.search(r'ANO DA ABERTURA \(.*?\): (.*?)\.?$', texto, re.M)
    d['abertura_por_ano'] = ([(int(a), numero(h)) for a, h in
                              re.findall(rf'(\d{{4}}) ({_NUM}) ha', m.group(1))] if m else [])
    m = re.search(r'Cite a fonte: (.+?)\.\s*$', texto, re.M)
    d['fonte'] = m.group(1).strip() if m else 'MapBiomas'

    # conferências de soma (pegam número copiado errado)
    area = d['area_ha']
    if area and 'hoje' in d:
        soma = sum(ha for _, ha, _ in d['hoje']['classes'])
        if abs(soma - area) > max(1.0, 0.02 * area):
            avisos.append(f'uso do solo: as classes de hoje somam {soma:.1f} ha e a área é '
                          f'{area:.1f} ha — confira o texto colado')
    if area and d['situacao']:
        soma = sum(ha for _, ha in d['situacao'])
        if abs(soma - area) > max(1.0, 0.02 * area):
            avisos.append(f'uso do solo: a situação soma {soma:.1f} ha e a área é {area:.1f} ha — '
                          'confira o texto colado')
    if 'aberto_desde' in d:
        a = d['aberto_desde']
        if not a[2008] + 0.05 >= a[2019] and a[2019] + 0.05 >= a[2020]:
            avisos.append('uso do solo: "aberto depois de" deveria diminuir de 2008 para 2020 — '
                          'confira o texto colado')
        abertos = sum(ha for n, ha in d['situacao'] if n.lower().startswith('aberto'))
        if d['situacao'] and abs(abertos - a[2008]) > 0.35:
            avisos.append(f'uso do solo: as faixas "aberto" somam {abertos:.1f} ha e o total depois '
                          f'de 2008 é {a[2008]:.1f} ha — confira o texto colado')
    return d, avisos


def _faixa_prodes(trecho):
    if 'nenhum polígono' in trecho:
        return {'n': 0, 'ha': 0.0, 'n_acima': 0, 'ha_acima': 0.0, 'n_abaixo': 0, 'ha_abaixo': 0.0}
    m = re.search(rf'(\d+) polígono\(s\), ({_NUM}) ha na área — ({_NUM}) ha em (\d+) polígono\(s\) '
                  rf'ACIMA .*? e ({_NUM}) ha em (\d+) ABAIXO', trecho)
    if not m:
        return None
    return {'n': int(m.group(1)), 'ha': numero(m.group(2)), 'ha_acima': numero(m.group(3)),
            'n_acima': int(m.group(4)), 'ha_abaixo': numero(m.group(5)), 'n_abaixo': int(m.group(6))}


def ler_prodes(texto):
    """Texto de prodes_fazenda → dados + avisos."""
    d, avisos = {'area_ha': _area(texto)}, []
    m = re.search(r'recortados nela — bioma: (.+?):', texto)
    d['biomas'] = m.group(1).strip() if m else None
    d['faixas'] = {}
    for chave, padrao in (('depois_2019', r'^DEPOIS DE 31/07/2019 \(PRODES 2020 em diante\): (.*)$'),
                          ('ano_2019', r'^PRODES 2019 — À PARTE.*?\): (.*)$'),
                          ('de_2008_a_2018', r'^PRODES de 2008 a 2018: (.*)$')):
        m = re.search(padrao, texto, re.M)
        faixa = _faixa_prodes(m.group(1)) if m else None
        if faixa is None:
            avisos.append(f'PRODES: não li a linha da faixa "{chave}"')
        else:
            d['faixas'][chave] = faixa
    d['poligonos'] = []
    for m in re.finditer(rf'^- PRODES (\d{{4}})(?: \(imagem de ([\d/]+)\))?: ({_NUM}) ha na área '
                         rf'\(polígono de ({_NUM}) ha\) — (ABAIXO|acima) do mínimo de ({_NUM}) ha',
                         texto, re.M):
        d['poligonos'].append({'ano': int(m.group(1)), 'imagem': m.group(2), 'ha_na_area': numero(m.group(3)),
                               'ha_do_poligono': numero(m.group(4)), 'abaixo_do_minimo': m.group(5) == 'ABAIXO',
                               'minimo_ha': numero(m.group(6))})
    m = re.search(r'\(e mais (\d+) polígonos', texto)
    d['poligonos_fora_da_lista'] = int(m.group(1)) if m else 0
    total = sum(f['n'] for f in d['faixas'].values())
    if d['faixas'] and len(d['poligonos']) + d['poligonos_fora_da_lista'] != total:
        avisos.append(f'PRODES: as faixas somam {total} polígono(s) e a lista traz '
                      f'{len(d["poligonos"]) + d["poligonos_fora_da_lista"]} — confira o texto colado')

    d['deter'] = None
    m = re.search(r'ALERTAS DO DETER desde ([\d/]+): nenhum na área', texto)
    if m:
        d['deter'] = {'desde': m.group(1), 'n': 0, 'ha': 0.0, 'n_depois': 0, 'ha_depois': 0.0, 'alertas': []}
    m = re.search(rf'ALERTAS DO DETER \(.*?\) desde ([\d/]+): (\d+) alerta\(s\), ({_NUM}) ha na área; '
                  rf'depois da última imagem do PRODES \(.*?\): (\d+) alerta\(s\), ({_NUM}) ha', texto)
    if m:
        alertas = [{'data': a, 'classe': c.strip(), 'ha': numero(h), 'depois_do_prodes': bool(dep)}
                   for a, c, h, dep in re.findall(
                       rf'^- (\d{{2}}/\d{{2}}/\d{{4}}) · (.+?) · ({_NUM}) ha( · depois da última imagem do PRODES)?$',
                       texto, re.M)]
        d['deter'] = {'desde': m.group(1), 'n': int(m.group(2)), 'ha': numero(m.group(3)),
                      'n_depois': int(m.group(4)), 'ha_depois': numero(m.group(5)), 'alertas': alertas}
    if d['deter'] is None:
        avisos.append('PRODES: não li a linha dos alertas do DETER')
    m = re.search(r'^ATÉ ONDE VAI O DADO: (.*?)\.?$', texto, re.M)
    d['ate_onde'] = m.group(1) if m else None
    d['ano_civil'] = 'o ano do polígono não casa com 31/07' in texto
    m = re.search(r'\(os dados de (\d+) arquivo\(s\) do INPE não estão carregados', texto)
    d['arquivos_faltando'] = int(m.group(1)) if m else 0
    m = re.search(r'Cite a fonte como está: (.+?), licença (.+?)\.\s*$', texto, re.M)
    d['fonte'] = m.group(1).strip() if m else 'PRODES e DETER (INPE)'
    d['licenca'] = m.group(2).strip() if m else None
    return d, avisos


def ler_relevo(texto):
    """Texto de relevo_fazenda → dados + avisos."""
    d, avisos = {'area_ha': _area(texto)}, []
    m = re.search(rf'ALTITUDE: de ({_NUM}) a ({_NUM}) m \(média ({_NUM}) m; desnível ({_NUM}) m\)', texto)
    if m:
        d['altitude'] = dict(zip(('min', 'max', 'media', 'desnivel'), map(numero, m.groups())))
    else:
        avisos.append('relevo: não li a linha "ALTITUDE"')
    m = re.search(rf'DECLIVE: médio ({_NUM}) % · (\d+) % da área abaixo de ({_NUM}) % · máximo ({_NUM}) %', texto)
    if m:
        d['declive'] = {'medio': numero(m.group(1)), 'percentil': int(m.group(2)),
                        'abaixo_de': numero(m.group(3)), 'maximo': numero(m.group(4))}
    else:
        avisos.append('relevo: não li a linha "DECLIVE"')
    m = re.search(r'^CLASSES DE RELEVO \(Embrapa\): (.*)$', texto, re.M)
    d['classes'] = [(n.strip(), f, numero(p), numero(h)) for n, f, p, h in
                    re.findall(rf'([^·(]+?) \(([^)]*%)\) ({_NUM}) % = ({_NUM}) ha', m.group(1))] if m else []
    if not d['classes']:
        avisos.append('relevo: não li as classes de relevo')
    elif abs(sum(p for _, _, p, _ in d['classes']) - 100) > 1.5:
        avisos.append('relevo: as classes não somam 100% — confira o texto colado')
    m = re.search(r'^MECANIZAÇÃO \(.*?\): (.*)$', texto, re.M)
    d['mecanizacao'] = [(n.strip(), f, numero(p)) for n, f, p in
                        re.findall(rf'([^·(]+?) \(([^)]*%)\) ({_NUM}) %', m.group(1))] if m else []
    m = re.search(r'^ENCOSTA ACIMA DE 45° \(.*?\): (.*?)\.?$', texto, re.M)
    d['encosta_45'] = m.group(1).strip() if m else None
    m = re.search(r'Cite a fonte como está: (.+?)\.\s*$', texto, re.M)
    d['fonte'] = m.group(1).strip() if m else 'modelo digital de terreno de 30 m'
    return d, avisos


def ler_imagem(texto):
    """Texto de imagem_satelite → data da cena e % sem nuvem."""
    m = re.search(r'Cena (\S+) de (\d{4}-\d{2}-\d{2}), com ([\d.,]+)% da área livre de nuvem '
                  r'\(fonte: (.+?)\)', texto)
    if not m:
        return None, ['imagem: não li a linha "Cena … de AAAA-MM-DD"']
    ano, mes, dia = m.group(2).split('-')
    return {'satelite': m.group(1), 'data': f'{dia}/{mes}/{ano}', 'livre_pct': numero(m.group(3)),
            'fonte': m.group(4)}, []


def conferir_areas(blocos):
    """As ferramentas leram o MESMO perímetro? Diferença acima de 1% vira aviso."""
    areas = {nome: b['area_ha'] for nome, b in blocos.items() if b and b.get('area_ha')}
    if len(areas) < 2:
        return []
    menor, maior = min(areas.values()), max(areas.values())
    if maior - menor > 0.01 * maior + 0.1:
        lista = ', '.join(f'{n} {a:.1f} ha' for n, a in areas.items())
        return [f'as ferramentas informam áreas diferentes ({lista}): os textos são do mesmo perímetro?']
    return []


if __name__ == '__main__':
    assert numero('1.669,5') == 1669.5 and numero('33') == 33.0
    assert numero('1669.5') == 1669.5 and numero('1.669') == 1669.0 and numero('0,3') == 0.3

    USO = '''Área completa — 1.000 ha. USO DO SOLO pelos mapas ANUAIS de 30 m do MapBiomas Coleção 11, de 1985 a 2025:
COMO DIZER À PESSOA: sempre "pelo mapeamento do MapBiomas".
HOJE (mapa de 2025): Formação Florestal 400 ha (40 %) · Pastagem 350,5 ha (35 %) · Soja 249,5 ha (25 %). Vegetação nativa: 400 ha (40 %).

DATAS-MARCO (cada mapa é do ANO inteiro, não do dia do marco):
- 1985 (primeiro mapa): vegetação nativa 600 ha (60 %) · Formação Florestal 600 ha (60 %) · Pastagem 400 ha (40 %)
- 2008 (Código Florestal, marco de 22/07/2008): vegetação nativa 430 ha (43 %) · Pastagem 570 ha (57 %) · Formação Florestal 430 ha (43 %)

SITUAÇÃO HOJE (cada pixel numa faixa só; "aberto" = era vegetação nativa): Vegetação nativa 400 ha · Uso que já existia em 2008 570 ha · Aberto de 2009 a 2019 18 ha · Aberto em 2020 2 ha · Aberto depois de 2020 10 ha
ABERTO DEPOIS DE 2008: 30 ha · depois de 2019: 12 ha · depois de 2020: 10 ha.
ANO DA ABERTURA (área hoje em uso que era nativa no ano anterior): 1986 14,3 ha · 2015 18 ha · 2020 2 ha · 2023 10 ha.

LEIA ASSIM: é a leitura do mapeamento anual. Cite a fonte: MapBiomas Coleção 11.

Arquivos:
- uso_solo_situacao.png (126 KB): https://exemplo/arquivo.png
'''
    uso, av = ler_uso(USO)
    assert av == [], av
    assert uso['area_ha'] == 1000 and uso['colecao'] == 11 and uso['ano_final'] == 2025
    assert uso['hoje']['classes'][1] == ('Pastagem', 350.5, 35.0) and uso['hoje']['nativa_ha'] == 400
    assert [m['ano'] for m in uso['marcos']] == [1985, 2008]
    assert uso['marcos'][1]['rotulo'].startswith('Código Florestal') and uso['marcos'][1]['nativa_pct'] == 43
    assert uso['situacao'][2] == ('Aberto de 2009 a 2019', 18.0)
    assert uso['aberto_desde'] == {2008: 30.0, 2019: 12.0, 2020: 10.0}
    assert uso['abertura_por_ano'][0] == (1986, 14.3) and uso['abertura_por_ano'][-1] == (2023, 10.0)
    assert uso['fonte'] == 'MapBiomas Coleção 11'
    # número copiado errado: a soma denuncia
    _, av = ler_uso(USO.replace('Pastagem 350,5 ha (35 %)', 'Pastagem 530,5 ha (35 %)'))
    assert any('somam' in a for a in av), av
    _, av = ler_uso(USO.replace('ABERTO DEPOIS DE 2008: 30 ha', 'ABERTO DEPOIS DE 2008: 3 ha'))
    assert any('faixas "aberto"' in a for a in av), av

    PRODES = '''Área completa — 1.000 ha. PRODES (supressão de vegetação nativa mapeada pelo INPE, por ano, de 2008 em diante) e alertas do DETER que tocam a área, recortados nela — bioma: Cerrado:
COMO DIZER À PESSOA: sempre "pelos dados públicos do INPE (PRODES/DETER)".
DEPOIS DE 31/07/2019 (PRODES 2020 em diante): 2 polígono(s), 13,6 ha na área — 12 ha em 1 polígono(s) ACIMA do mínimo da nota do MMA e 1,6 ha em 1 ABAIXO dele.
PRODES 2019 — À PARTE, zona cinzenta (as imagens de 2019 são de antes e de depois de 31/07/2019): nenhum polígono.
PRODES de 2008 a 2018: 1 polígono(s), 40 ha na área — 40 ha em 1 polígono(s) ACIMA do mínimo da nota do MMA e 0 ha em 0 ABAIXO dele.

MÍNIMO DA NOTA DO MMA (base do crédito rural): mais de 5 ha no Cerrado.
POLÍGONOS (mais recentes primeiro):
- PRODES 2023 (imagem de 14/08/2023): 12 ha na área (polígono de 31,5 ha) — acima do mínimo de 5 ha
- PRODES 2021: 1,6 ha na área (polígono de 1,6 ha) — ABAIXO do mínimo de 5 ha
- PRODES 2012 (imagem de 02/09/2012): 40 ha na área (polígono de 220 ha) — acima do mínimo de 5 ha

ALERTAS DO DETER (avisos rápidos, NÃO consolidados) desde 01/11/2024: 2 alerta(s), 7,5 ha na área; depois da última imagem do PRODES (o que o PRODES ainda não cobre): 1 alerta(s), 3 ha. Os anteriores a ela podem já estar no PRODES.
- 12/09/2026 · Desmatamento com solo exposto · 3 ha · depois da última imagem do PRODES
- 03/02/2025 · Degradação · 4,5 ha

ATÉ ONDE VAI O DADO: Cerrado: PRODES até 2026 (última imagem em 28/08/2026).

É LEITURA dos dados públicos do INPE, não laudo nem a análise do banco. Cite a fonte como está: PRODES e DETER (INPE, Programa BiomasBR — TerraBrasilis), licença CC BY-SA 4.0.
'''
    pr, av = ler_prodes(PRODES)
    assert av == [], av
    assert pr['biomas'] == 'Cerrado' and pr['faixas']['depois_2019'] == {
        'n': 2, 'ha': 13.6, 'ha_acima': 12.0, 'n_acima': 1, 'ha_abaixo': 1.6, 'n_abaixo': 1}
    assert pr['faixas']['ano_2019']['n'] == 0 and pr['faixas']['de_2008_a_2018']['ha'] == 40
    assert len(pr['poligonos']) == 3 and pr['poligonos'][1]['abaixo_do_minimo'] and pr['poligonos'][1]['imagem'] is None
    assert pr['poligonos'][0] == {'ano': 2023, 'imagem': '14/08/2023', 'ha_na_area': 12.0,
                                  'ha_do_poligono': 31.5, 'abaixo_do_minimo': False, 'minimo_ha': 5.0}
    assert pr['deter']['n'] == 2 and pr['deter']['ha_depois'] == 3 and len(pr['deter']['alertas']) == 2
    assert pr['deter']['alertas'][0]['depois_do_prodes'] and not pr['deter']['alertas'][1]['depois_do_prodes']
    assert pr['licenca'] == 'CC BY-SA 4.0' and pr['ate_onde'].startswith('Cerrado: PRODES até 2026')
    vazio, av = ler_prodes('''Área completa — 1.669,5 ha. PRODES e alertas do DETER que tocam a área, recortados nela:
DEPOIS DE 31/07/2019 (PRODES 2020 em diante): nenhum polígono.
PRODES 2019 — À PARTE, zona cinzenta (as imagens de 2019 são de antes e de depois de 31/07/2019): nenhum polígono.
PRODES de 2008 a 2018: nenhum polígono.

ALERTAS DO DETER desde 01/11/2024: nenhum na área (o DETER cobre Amazônia, Cerrado e Pantanal).
''')
    assert av == [] and vazio['deter']['n'] == 0 and not vazio['poligonos'] and vazio['area_ha'] == 1669.5

    RELEVO = '''Área completa — 1.669,5 ha. RELEVO pelo terreno de 30 m (o chão, sem a vegetação):
ALTITUDE: de 450 a 563 m (média 509 m; desnível 113 m).
DECLIVE: médio 7,1 % · 90 % da área abaixo de 12,6 % · máximo 31,4 %.
CLASSES DE RELEVO (Embrapa): Plano (0–3%) 15,4 % = 256,5 ha · Suave ondulado (3–8%) 51,2 % = 854,7 ha · Ondulado (8–20%) 32,1 % = 535,2 ha · Forte ondulado (20–45%) 1,4 % = 23,2 ha
MECANIZAÇÃO (faixas USUAIS de referência técnica, não regra): sem restrição (até 12%) 88,3 % · com restrição (12–20%) 10,3 % · difícil (acima de 20%) 1,4 %
ENCOSTA ACIMA DE 45° (APP de encosta pelo Código Florestal): nenhuma na leitura do terreno de 30 m.

LEIA ASSIM: é um modelo de terreno de 30 m. Cite a fonte como está: ANADEM v1 (UFRGS/ANA), derivado do Copernicus DEM GLO-30.
'''
    rv, av = ler_relevo(RELEVO)
    assert av == [], av
    assert rv['altitude'] == {'min': 450, 'max': 563, 'media': 509, 'desnivel': 113}
    assert rv['declive'] == {'medio': 7.1, 'percentil': 90, 'abaixo_de': 12.6, 'maximo': 31.4}
    assert rv['classes'][1] == ('Suave ondulado', '3–8%', 51.2, 854.7) and len(rv['classes']) == 4
    assert rv['mecanizacao'][0] == ('sem restrição', 'até 12%', 88.3)
    assert rv['encosta_45'].startswith('nenhuma') and rv['fonte'].startswith('ANADEM v1')

    img, av = ler_imagem('Área completa — 1669.5 ha. Cena Sentinel-2 de 2026-10-27, com 99.7% da área '
                         'livre de nuvem (fonte: Copernicus Sentinel-2 L2A, 10 m).')
    assert av == [] and img == {'satelite': 'Sentinel-2', 'data': '27/10/2026', 'livre_pct': 99.7,
                                'fonte': 'Copernicus Sentinel-2 L2A, 10 m'}
    assert conferir_areas({'uso': uso, 'prodes': pr}) == []
    assert conferir_areas({'uso': uso, 'relevo': rv})  # 1.000 ha × 1.669,5 ha: perímetros diferentes
    print('leitura OK: uso do solo, PRODES/DETER, relevo, imagem e as conferências de soma')
