"""Lê o TEXTO que as ferramentas da ClaudIA Sat devolvem e tira dele os números
do dossiê, sem interpretar nada.

A IA cola o texto de cada ferramenta num arquivo, como veio. Aqui ele vira
dados por expressão regular e passa por conferências de soma: se um número foi
copiado errado, a conta não fecha e o dossiê avisa em vez de imprimir o erro.

Ferramentas lidas: uso_do_solo, cobertura_do_solo, prodes_fazenda, relevo_fazenda,
imagem_satelite, restricoes_fazenda e solo_textura_carbono.
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


def ler_cobertura(texto):
    """Texto de cobertura_do_solo (retrato recente, classificação de 10 m) → dados + avisos."""
    d, avisos = {'area_ha': _area(texto)}, []
    m = re.search(r'período de (\d{2}/\d{2}/\d{4}) a (\d{2}/\d{2}/\d{4})', texto)
    d['periodo'] = (m.group(1), m.group(2)) if m else None
    m = re.search(r'(\d+) dias? com imagem, a última em (\d{2}/\d{2}/\d{4})', texto)
    d['dias_com_imagem'], d['ultima_imagem'] = (int(m.group(1)), m.group(2)) if m else (None, None)
    d['classes'] = []
    for m in re.finditer(rf'^- (.+?) ({_NUM}) ha \(({_NUM}) %\) — probabilidade média ({_NUM}) %'
                         rf'(?:; 2ª mais provável ali: (.+?) \(({_NUM}) %\))?\.?$', texto, re.M):
        d['classes'].append({'nome': m.group(1).strip(), 'ha': numero(m.group(2)), 'pct': numero(m.group(3)),
                             'probabilidade': numero(m.group(4)), 'segunda': m.group(5),
                             'segunda_pct': numero(m.group(6)) if m.group(6) else None})
    if not d['classes']:
        avisos.append('cobertura do solo: não li as linhas das classes')
    m = re.search(rf'^PROBABILIDADE DA CLASSE ESCOLHIDA, POR FAIXA \(média de ({_NUM}) %\): (.*?)\.?$', texto, re.M)
    d['probabilidade_media'] = numero(m.group(1)) if m else None
    d['faixas'] = [(nome.strip(), numero(ha), numero(pct)) for nome, ha, pct in
                   re.findall(rf'([^·]+?) em ({_NUM}) ha \(({_NUM}) %\)', m.group(2))] if m else []
    m = re.search(r'Cite a fonte como está: (.+?)\.\s*$', texto, re.M)
    d['fonte'] = m.group(1).strip() if m else 'Dynamic World'
    area = d['area_ha']
    if area and d['classes']:
        soma = sum(c['ha'] for c in d['classes'])
        if abs(soma - area) > max(1.0, 0.02 * area):
            avisos.append(f'cobertura do solo: as classes somam {soma:.1f} ha e a área é {area:.1f} ha — '
                          'confira o texto colado')
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


def _trecho(texto, inicio, fins):
    """(cabeçalho casado, pedaço do texto entre ele e o primeiro dos `fins`); (None, None) sem cabeçalho."""
    m = re.search(inicio, texto, re.M)
    if not m:
        return None, None
    resto = texto[m.end():]
    corte = len(resto)
    for fim in fins:
        f = re.search(fim, resto, re.M)
        if f:
            corte = min(corte, f.start())
    return m, resto[:corte]


def _embargo(linha):
    """Uma linha de termo de embargo → dict (sem nome nem documento de pessoa: o texto não traz)."""
    m = re.match(r'^- ([^,]+), termo (.+?)(?:, de (\d{2}/\d{2}/\d{4}))? — (.+)$', linha)
    if not m:
        return None
    tipo, _, onde = m.group(4).partition('; ')
    e = {'orgao': m.group(1).strip(), 'termo': m.group(2).strip(), 'data': m.group(3), 'tipo': tipo.strip(),
         'origem': 'contorno', 'ha_na_area': None, 'pct': None, 'distancia_km': None, 'ha_no_termo': None,
         'local': None}
    c = re.search(rf'contorno com ({_NUM}) ha dentro da área \(({_NUM})%\)', onde)
    k = re.search(rf'a ({_NUM}) km da divisa( \(marcado por ponto\))?', onde)
    if c:
        e['ha_na_area'], e['pct'] = numero(c.group(1)), numero(c.group(2))
    elif 'marcado por PONTO dentro da área' in onde:
        e['origem'] = 'ponto'
    elif k:
        e['distancia_km'] = numero(k.group(1))
        e['origem'] = 'ponto' if k.group(2) else 'contorno'
    t = re.search(rf'área embargada declarada no termo: ({_NUM}) ha', onde)
    e['ha_no_termo'] = numero(t.group(1)) if t else None
    lugar = re.search(r' \(([^()]+)\)$', onde)
    if lugar and not lugar.group(1).startswith(('o órgão', 'marcado por ponto')):
        e['local'] = lugar.group(1)
    return e


def ler_restricoes(texto):
    """Texto de restricoes_fazenda (unidades de conservação, terras indígenas e embargos) → dados + avisos.
    Base que a ferramenta não conseguiu ler fica com lida=False: o dossiê diz "base não lida", nunca "nenhuma"."""
    d, avisos = {'area_ha': _area(texto)}, []

    def grupo():
        return {'lida': False, 'data': None, 'n': 0, 'ha': 0.0, 'pct': 0.0, 'itens': [], 'n_perto': 0, 'perto': []}

    def conferir(nome, g, dentro, teto):
        mais = re.search(r'\(e mais (\d+); o arquivo traz todos\)', dentro)
        listados = len(g['itens']) + (int(mais.group(1)) if mais else 0)
        if g['lida'] and listados < min(g['n'], teto if not mais else g['n']):
            avisos.append(f'restrições: o texto fala em {g["n"]} {nome} e só li {len(g["itens"])} — confira o texto colado')

    # ---- unidades de conservação
    uc = grupo()
    cab, bloco = _trecho(texto, r'^UNIDADES DE CONSERVAÇÃO \(CNUC, MMA(?:, versão de ([^)]+))?\):$', [r'^TERRAS INDÍGENAS \('])
    if cab is None:
        avisos.append('restrições: não li o bloco das unidades de conservação')
    elif 'não pôde ser lida' not in bloco:
        uc['lida'], uc['data'] = True, cab.group(1)
        dentro, _, perto = bloco.partition('PERTO (até 10 km da divisa)')
        m = re.search(rf'^(\d+) unidade\(s\) sobrepõe\(m\) a área: ({_NUM}) ha, ({_NUM})% dela', dentro, re.M)
        if m:
            uc.update(n=int(m.group(1)), ha=numero(m.group(2)), pct=numero(m.group(3)))
        elif 'Nenhuma unidade de conservação sobrepõe a área' not in dentro:
            avisos.append('restrições: não li o total das unidades de conservação')
        for m in re.finditer(rf'^- (.+?) — ([^,;]+), ([^,;]+), esfera ([^,;]+)(?:, criada em (\d{{4}}))?; '
                             rf'plano de manejo: ([^;]+); ({_NUM}) ha na área \(({_NUM})%\)'
                             rf'(?:; a unidade inteira tem ({_NUM}) ha)?$', dentro, re.M):
            uc['itens'].append({'nome': m.group(1).strip(), 'categoria': m.group(2).strip(), 'grupo': m.group(3).strip(),
                                'esfera': m.group(4).strip(), 'criada_em': m.group(5), 'plano_manejo': m.group(6).strip(),
                                'ha': numero(m.group(7)), 'pct': numero(m.group(8)),
                                'ha_total': numero(m.group(9)) if m.group(9) else None})
        m = re.match(r': (\d+) unidade\(s\)\.', perto)
        uc['n_perto'] = int(m.group(1)) if m else 0
        for m in re.finditer(rf'^- (.+) \(([^()]+), ([^(),]+), esfera ([^()]+)\) a ({_NUM}) km$', perto, re.M):
            uc['perto'].append({'nome': m.group(1).strip(), 'categoria': m.group(2).strip(), 'grupo': m.group(3).strip(),
                                'esfera': m.group(4).strip(), 'km': numero(m.group(5))})
        conferir('unidade(s) de conservação', uc, dentro, 12)
    d['uc'] = uc

    # ---- terras indígenas
    ti = grupo()
    cab, bloco = _trecho(texto, r'^TERRAS INDÍGENAS \(FUNAI(?:, base atualizada até ([^)]+))?\):$', [r'^EMBARGOS \('])
    if cab is None:
        avisos.append('restrições: não li o bloco das terras indígenas')
    elif 'não pôde ser lida' not in bloco:
        ti['lida'], ti['data'] = True, cab.group(1)
        dentro, _, perto = bloco.partition('PERTO (até 10 km da divisa)')
        m = re.search(rf'^(\d+) terra\(s\) indígena\(s\) sobrepõe\(m\) a área: ({_NUM}) ha, ({_NUM})% dela', dentro, re.M)
        if m:
            ti.update(n=int(m.group(1)), ha=numero(m.group(2)), pct=numero(m.group(3)))
        elif 'Nenhuma terra indígena sobrepõe a área' not in dentro:
            avisos.append('restrições: não li o total das terras indígenas')
        for m in re.finditer(rf'^- (.+?)(?: — etnia (.+?))?; fase do processo: ([^;(]+?)(?: \(([^)]+)\))?; '
                             rf'({_NUM}) ha na área \(({_NUM})%\)(?:; a terra inteira tem ({_NUM}) ha)?$', dentro, re.M):
            ti['itens'].append({'nome': m.group(1).strip(), 'etnia': m.group(2), 'fase': m.group(3).strip(),
                                'modalidade': m.group(4), 'ha': numero(m.group(5)), 'pct': numero(m.group(6)),
                                'ha_total': numero(m.group(7)) if m.group(7) else None})
        m = re.match(r': (\d+) terra\(s\)\.', perto)
        ti['n_perto'] = int(m.group(1)) if m else 0
        for m in re.finditer(rf'^- (.+) \(fase: ([^()]+)\) a ({_NUM}) km$', perto, re.M):
            ti['perto'].append({'nome': m.group(1).strip(), 'fase': m.group(2).strip(), 'km': numero(m.group(3))})
        conferir('terra(s) indígena(s)', ti, dentro, 12)
    d['ti'] = ti

    # ---- termos de embargo
    em = grupo()
    em.update(n_contorno=0, n_ponto=0, base_que_faltou=None, sem_localizacao=None)
    cab, bloco = _trecho(texto, r'^EMBARGOS \((.+)\):$', [r'^O QUE ESTA LEITURA NÃO COBRE'])
    if cab is None:
        avisos.append('restrições: não li o bloco dos embargos')
    elif 'não puderam ser lidas' not in bloco:
        em['lida'], em['data'] = True, cab.group(1).replace('base atualizada até ', '').replace(', até ', ' ').replace(
            ', ', ' ').replace('; ', ' · ')
        dentro, _, perto = bloco.partition('PERTO (até 1 km da divisa')
        m = re.search(rf'^(\d+) termo\(s\) de embargo toca\(m\) a área: (\d+) com contorno \(({_NUM}) ha dentro da área, '
                      rf'({_NUM})% dela\) e (\d+) marcado\(s\) por ponto\.', dentro, re.M)
        if m:
            em.update(n=int(m.group(1)), n_contorno=int(m.group(2)), ha=numero(m.group(3)), pct=numero(m.group(4)),
                      n_ponto=int(m.group(5)))
            if em['n_contorno'] + em['n_ponto'] != em['n']:
                avisos.append('restrições: os termos com contorno e por ponto não somam o total — confira o texto colado')
        elif 'Nenhum termo de embargo toca a área' not in dentro:
            avisos.append('restrições: não li o total dos termos de embargo')
        em['itens'] = [e for e in (_embargo(linha) for linha in dentro.splitlines() if linha.startswith('- ')) if e]
        m = re.search(r'\): (\d+) termo\(s\)\.', perto)
        em['n_perto'] = int(m.group(1)) if m else 0
        em['perto'] = [e for e in (_embargo(linha) for linha in perto.splitlines() if linha.startswith('- ')) if e]
        m = re.search(r'\(a base de embargos do (IBAMA|ICMBio) não pôde ser lida', bloco)
        em['base_que_faltou'] = m.group(1) if m else None
        m = re.search(rf'SEM localização \(({_NUM}) hoje\)', bloco)
        em['sem_localizacao'] = int(numero(m.group(1))) if m else None
        conferir('termo(s) de embargo', em, dentro, 15)
    d['embargo'] = em

    m = re.search(r'^O QUE ESTA LEITURA NÃO COBRE: (.+?)\.(?: Para supressão.*)?$', texto, re.M)
    d['nao_cobre'] = m.group(1).strip() if m else None
    m = re.search(r'^Cite a fonte como está: (.+?)\. ', texto, re.M) or re.search(r'^Cite a fonte como está: (.+?)\.?$',
                                                                                 texto, re.M)
    d['fonte'] = m.group(1).strip() if m else 'CNUC (MMA), FUNAI, IBAMA e ICMBio'
    return d, avisos


_CAMADA = (rf'argila ({_NUM})%, areia ({_NUM})%, silte ({_NUM})% — textura ([^;]+); carbono orgânico ({_NUM}) g/kg '
           rf'\(cerca de ({_NUM})% de matéria orgânica\)')


def _camada(m, base=0):
    g = m.groups()[base:]
    return {'argila': numero(g[0]), 'areia': numero(g[1]), 'silte': numero(g[2]), 'textura': g[3].strip(),
            'carbono_g_kg': numero(g[4]), 'materia_organica': numero(g[5])}


def ler_solo(texto):
    """Texto de solo_textura_carbono (SoilGrids 2.0, pixel de 250 m; valores MODELADOS) → dados + avisos."""
    d, avisos = {'area_ha': _area(texto)}, []
    m = re.search(r'\((\d+) pixel\(s\) tocam a área\)', texto)
    d['pixels'] = int(m.group(1)) if m else None
    m = re.search(r'^CAMADA DE 0–30 cm \(média pesada pela espessura\): ' + _CAMADA, texto, re.M)
    d['superficie'] = _camada(m) if m else None
    m = re.search(r'^CAMADA DE 30–100 cm: ' + _CAMADA, texto, re.M)
    d['subsolo'] = _camada(m) if m else None
    if not d['superficie']:
        avisos.append('solo: não li a camada de 0–30 cm')
    m = re.search(rf'^ESTOQUE DE CARBONO ORGÂNICO DE 0–30 cm: ({_NUM}) t de carbono por hectare — cerca de ({_NUM}) t de '
                  rf'carbono nos ({_NUM}) ha com dado', texto, re.M)
    d['estoque'] = {'t_ha': numero(m.group(1)), 'total_t': numero(m.group(2)), 'area_com_dado_ha': numero(m.group(3))} if m else None
    d['poucos_pixels'] = 'ÁREA PEQUENA PARA ESTE MAPA' in texto
    m = re.search(rf'^DENTRO DA ÁREA: a argila de 0–30 cm vai de ({_NUM})% a ({_NUM})% \(a maior parte entre ({_NUM})% e '
                  rf'({_NUM})%\) e o estoque de carbono, de ({_NUM}) a ({_NUM}) t/ha', texto, re.M)
    d['variacao'] = {'argila': (numero(m.group(1)), numero(m.group(2))), 'argila_maior_parte': (numero(m.group(3)), numero(m.group(4))),
                     'estoque': (numero(m.group(5)), numero(m.group(6)))} if m else None
    faixa = re.search(r'^FAIXA DE 90% DO PRÓPRIO MODELO, em cada pixel: (.+)$', texto, re.M)
    d['faixa_do_modelo'] = None
    if faixa:
        a = re.search(rf'argila de 0–30 cm entre ({_NUM})% e ({_NUM})%', faixa.group(1))
        e = re.search(rf'estoque entre ({_NUM}) e ({_NUM}) t/ha', faixa.group(1))
        d['faixa_do_modelo'] = {'argila': (numero(a.group(1)), numero(a.group(2))) if a else None,
                                'estoque': (numero(e.group(1)), numero(e.group(2))) if e else None}
    d['camadas'] = [{'camada': m.group(1).strip(), **_camada(m, 1)}
                    for m in re.finditer(r'^- ([^:]+): ' + _CAMADA + r'$', texto, re.M)]
    m = re.search(rf'^O mapa tem dado em ({_NUM})% da área', texto, re.M)
    d['cobertura_pct'] = numero(m.group(1)) if m else None
    m = re.search(r'^Cite a fonte como está: (.+?), licença (.+?)\. ', texto, re.M)
    d['fonte'], d['licenca'] = (m.group(1).strip(), m.group(2).strip()) if m else ('SoilGrids 2.0 (ISRIC — World Soil Information)', 'CC BY 4.0')
    for nome, c in [('0–30 cm', d['superficie']), ('30–100 cm', d['subsolo'])] + [(c['camada'], c) for c in d['camadas']]:
        if c and abs(c['argila'] + c['areia'] + c['silte'] - 100) > 1.5:
            avisos.append(f'solo: argila + areia + silte da camada {nome} não somam 100% — confira o texto colado')
    return d, avisos


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

    COBERTURA = '''Área completa — 1.000 ha. COBERTURA DO SOLO pelo Dynamic World (classificação de 10 m de cada imagem Sentinel-2), período de 13/11/2025 a 12/11/2026 (os últimos 12 meses, o padrão): 88 dias com imagem, a última em 09/11/2026.
CLASSES (a mais provável de cada pixel):
- Árvores 480 ha (48 %) — probabilidade média 68 %; 2ª mais provável ali: Gramíneas (pasto e campo) (5 %)
- Gramíneas (pasto e campo) 290,5 ha (29 %) — probabilidade média 48 %; 2ª mais provável ali: Lavoura (15 %)
- Lavoura 229,5 ha (23 %) — probabilidade média 34 %
PROBABILIDADE MÉDIA DE CADA CLASSE NA ÁREA TODA: Árvores 39 % · Lavoura 14 %.
PROBABILIDADE DA CLASSE ESCOLHIDA, POR FAIXA (média de 55 %): 50 % ou mais em 580 ha (58 %) · 35 a 50 % em 220 ha (22 %) · menos de 35 % em 200 ha (20 %).

LEIA ASSIM: é a leitura de um modelo. Cite a fonte como está: Dynamic World V1 (Google e World Resources Institute), de imagens Sentinel-2.
'''
    cb, av = ler_cobertura(COBERTURA)
    assert av == [], av
    assert cb['periodo'] == ('13/11/2025', '12/11/2026') and cb['dias_com_imagem'] == 88 and cb['ultima_imagem'] == '09/11/2026'
    assert cb['classes'][1] == {'nome': 'Gramíneas (pasto e campo)', 'ha': 290.5, 'pct': 29.0, 'probabilidade': 48.0,
                                'segunda': 'Lavoura', 'segunda_pct': 15.0}
    assert cb['classes'][2]['segunda'] is None and cb['probabilidade_media'] == 55
    assert cb['faixas'] == [('50 % ou mais', 580.0, 58.0), ('35 a 50 %', 220.0, 22.0), ('menos de 35 %', 200.0, 20.0)]
    assert cb['fonte'].startswith('Dynamic World V1')
    _, av = ler_cobertura(COBERTURA.replace('Árvores 480 ha', 'Árvores 840 ha'))
    assert any('somam' in a for a in av), av
    assert conferir_areas({'uso': uso, 'relevo': rv})  # 1.000 ha × 1.669,5 ha: perímetros diferentes
    RESTRICOES = """Área completa — 520 ha. RESTRIÇÕES que a área sobrepõe ou que ficam perto dela, pelas bases públicas: unidades de conservação (CNUC, MMA), terras indígenas (FUNAI) e embargos (IBAMA e ICMBio).
COMO DIZER À PESSOA: sempre "pelas bases públicas, na data de cada uma".

UNIDADES DE CONSERVAÇÃO (CNUC, MMA, versão de 31/07/2026):
1 unidade(s) sobrepõe(m) a área: 130 ha, 25% dela (o que se sobrepõe entre unidades conta uma vez).
- Área de Proteção Ambiental Exemplo — Área de Proteção Ambiental, uso sustentável, esfera estadual, criada em 1983; plano de manejo: sim; 130 ha na área (25%); a unidade inteira tem 83.310 ha
PERTO (até 10 km da divisa): 2 unidade(s).
- Parque Estadual Exemplo (Parque, proteção integral, esfera estadual) a 2,88 km
- Reserva Exemplo (da Serra) (Reserva Particular do Patrimônio Natural, uso sustentável, esfera federal) a 7,5 km

TERRAS INDÍGENAS (FUNAI, base atualizada até 10/11/2026):
1 terra(s) indígena(s) sobrepõe(m) a área: 4,5 ha, 0,9% dela.
- Terra Exemplo — etnia Exemplo; fase do processo: Regularizada (tradicionalmente ocupada); 4,5 ha na área (0,9%); a terra inteira tem 12.000 ha
PERTO (até 10 km da divisa): 1 terra(s).
- Outra Terra Exemplo (fase: Declarada) a 9,1 km

EMBARGOS (IBAMA, base atualizada até 11/11/2026; ICMBio, até 31/10/2026):
2 termo(s) de embargo toca(m) a área: 1 com contorno (12,4 ha dentro da área, 2,4% dela) e 1 marcado(s) por ponto.
- IBAMA, termo 000001-C, de 20/10/2010 — ligado a desmatamento; contorno com 12,4 ha dentro da área (2,4%); área embargada declarada no termo: 5.718,6 ha (Município Exemplo/SP)
- IBAMA, termo 000002-E, de 26/09/2014 — desmatamento; marcado por PONTO dentro da área (o órgão registrou a coordenada, não o contorno); área embargada declarada no termo: 1 ha (Município Exemplo/SP)
PERTO (até 1 km da divisa — a coordenada de um embargo por ponto pode estar deslocada): 1 termo(s).
- ICMBio, termo 000003 — tipo não informado na base; a 0,42 km da divisa (marcado por ponto); unidade: Parque Exemplo (Município Exemplo/SP)
Ficam de fora do cruzamento os embargos que a base do IBAMA traz SEM localização (12.345 hoje): estes só aparecem na consulta pública do órgão.

O QUE ESTA LEITURA NÃO COBRE: territórios quilombolas, assentamentos, florestas públicas, embargos de órgãos estaduais e a zona de amortecimento de cada unidade (definida no plano de manejo dela). Para supressão de vegetação nativa existe o PRODES (prodes_fazenda).
Cite a fonte como está: CNUC (MMA), FUNAI, IBAMA e ICMBio. Leitura informativa das bases públicas, na data de cada uma.
"""
    rs, avisos = ler_restricoes(RESTRICOES)
    assert avisos == [], avisos
    assert rs['area_ha'] == 520 and rs['uc']['lida'] and rs['uc']['data'] == '31/07/2026'
    assert (rs['uc']['n'], rs['uc']['ha'], rs['uc']['pct'], rs['uc']['n_perto']) == (1, 130, 25, 2)
    assert rs['uc']['itens'][0]['ha_total'] == 83310 and rs['uc']['itens'][0]['criada_em'] == '1983'
    assert rs['uc']['itens'][0]['plano_manejo'] == 'sim' and rs['uc']['itens'][0]['esfera'] == 'estadual'
    assert [u['km'] for u in rs['uc']['perto']] == [2.88, 7.5] and rs['uc']['perto'][1]['nome'] == 'Reserva Exemplo (da Serra)'
    assert rs['ti']['n'] == 1 and rs['ti']['itens'][0]['etnia'] == 'Exemplo' and rs['ti']['itens'][0]['fase'] == 'Regularizada'
    assert rs['ti']['itens'][0]['modalidade'] == 'tradicionalmente ocupada' and rs['ti']['perto'][0]['km'] == 9.1
    em = rs['embargo']
    assert (em['n'], em['n_contorno'], em['n_ponto'], em['ha'], em['pct'], em['n_perto']) == (2, 1, 1, 12.4, 2.4, 1)
    assert em['data'] == 'IBAMA 11/11/2026 · ICMBio 31/10/2026' and em['sem_localizacao'] == 12345
    assert em['itens'][0] == {'orgao': 'IBAMA', 'termo': '000001-C', 'data': '20/10/2010', 'tipo': 'ligado a desmatamento',
                              'origem': 'contorno', 'ha_na_area': 12.4, 'pct': 2.4, 'distancia_km': None,
                              'ha_no_termo': 5718.6, 'local': 'Município Exemplo/SP'}
    assert em['itens'][1]['origem'] == 'ponto' and em['itens'][1]['ha_no_termo'] == 1 and em['itens'][1]['local'] == 'Município Exemplo/SP'
    assert em['perto'][0]['distancia_km'] == 0.42 and em['perto'][0]['origem'] == 'ponto' and em['perto'][0]['data'] is None
    assert rs['nao_cobre'].startswith('territórios quilombolas') and rs['fonte'] == 'CNUC (MMA), FUNAI, IBAMA e ICMBio'

    # nada sobreposto, nada perto; e uma base que a ferramenta não conseguiu ler
    VAZIO = """Área completa — 100 ha. RESTRIÇÕES que a área sobrepõe ou que ficam perto dela, pelas bases públicas: …

UNIDADES DE CONSERVAÇÃO (CNUC, MMA, versão de 31/07/2026):
Nenhuma unidade de conservação sobrepõe a área.
Nenhuma unidade a até 10 km da divisa.

TERRAS INDÍGENAS (FUNAI):
A base não pôde ser lida nesta consulta — não dá para dizer nada sobre terras indígenas agora. Diga isso.

EMBARGOS (IBAMA, base atualizada até 11/11/2026):
Nenhum termo de embargo toca a área.
Nenhum termo de embargo a até 1 km da divisa.
(a base de embargos do ICMBio não pôde ser lida nesta consulta: diga que essa parte ficou de fora)

O QUE ESTA LEITURA NÃO COBRE: territórios quilombolas e assentamentos.
Cite a fonte como está: CNUC (MMA), FUNAI, IBAMA e ICMBio. Leitura informativa.
"""
    rs, avisos = ler_restricoes(VAZIO)
    assert avisos == [] and rs['uc']['lida'] and rs['uc']['n'] == 0 and rs['uc']['n_perto'] == 0
    assert rs['ti']['lida'] is False and rs['embargo']['lida'] and rs['embargo']['base_que_faltou'] == 'ICMBio'
    assert rs['embargo']['data'] == 'IBAMA 11/11/2026' and rs['nao_cobre'] == 'territórios quilombolas e assentamentos'
    assert ler_restricoes('texto de outra ferramenta')[1] != []

    SOLO = """Área completa — 520 ha. TEXTURA E CARBONO DO SOLO pelo SoilGrids 2.0 (ISRIC): mapa MUNDIAL feito por modelo, com pixel de 250 m (96 pixel(s) tocam a área).
COMO DIZER À PESSOA: é ESTIMATIVA de um modelo mundial, NÃO medição.

CAMADA DE 0–30 cm (média pesada pela espessura): argila 35,5%, areia 46,9%, silte 17,6% — textura argilosa; carbono orgânico 16,4 g/kg (cerca de 2,8% de matéria orgânica).
CAMADA DE 30–100 cm: argila 43,9%, areia 40,1%, silte 16%, — textura argilosa; carbono orgânico 7,3 g/kg (cerca de 1,3% de matéria orgânica).
ESTOQUE DE CARBONO ORGÂNICO DE 0–30 cm: 36,3 t de carbono por hectare — cerca de 18.876 t de carbono nos 520 ha com dado.
DENTRO DA ÁREA: a argila de 0–30 cm vai de 33,2% a 41,5% (a maior parte entre 34% e 39,8%) e o estoque de carbono, de 31 a 46 t/ha.
FAIXA DE 90% DO PRÓPRIO MODELO, em cada pixel: argila de 0–30 cm entre 4,6% e 75%; estoque entre 10,4 e 86,6 t/ha. A faixa é larga: é o tamanho da incerteza do mapa.

POR CAMADA:
- 0–5 cm: argila 33,2%, areia 47,3%, silte 19,5% — textura média; carbono orgânico 23,4 g/kg (cerca de 4% de matéria orgânica)
- 5–15 cm: argila 34,8%, areia 47%, silte 18,2% — textura média; carbono orgânico 17,9 g/kg (cerca de 3,1% de matéria orgânica)
- 15–30 cm: argila 37%, areia 46,6%, silte 16,4% — textura argilosa; carbono orgânico 12,9 g/kg (cerca de 2,2% de matéria orgânica)

A matéria orgânica é o carbono × 1,724 (conversão convencional). A textura segue o grupamento da Embrapa: arenosa, média, argilosa, muito argilosa ou siltosa.
Cite a fonte como está: SoilGrids 2.0 (ISRIC — World Soil Information), licença CC BY 4.0. Mapa mundial de 250 m.
""".replace('silte 16%, — textura', 'silte 16% — textura')
    so, avisos = ler_solo(SOLO)
    assert avisos == [], avisos
    assert so['area_ha'] == 520 and so['pixels'] == 96 and not so['poucos_pixels']
    assert so['superficie'] == {'argila': 35.5, 'areia': 46.9, 'silte': 17.6, 'textura': 'argilosa', 'carbono_g_kg': 16.4,
                                'materia_organica': 2.8}
    assert so['subsolo']['argila'] == 43.9 and so['estoque'] == {'t_ha': 36.3, 'total_t': 18876, 'area_com_dado_ha': 520}
    assert so['variacao'] == {'argila': (33.2, 41.5), 'argila_maior_parte': (34, 39.8), 'estoque': (31, 46)}
    assert so['faixa_do_modelo'] == {'argila': (4.6, 75), 'estoque': (10.4, 86.6)}
    assert [c['camada'] for c in so['camadas']] == ['0–5 cm', '5–15 cm', '15–30 cm'] and so['camadas'][0]['textura'] == 'média'
    assert so['fonte'] == 'SoilGrids 2.0 (ISRIC — World Soil Information)' and so['licenca'] == 'CC BY 4.0'
    torto = SOLO.replace('argila 35,5%, areia 46,9%', 'argila 55,5%, areia 46,9%')
    assert any('não somam 100%' in a for a in ler_solo(torto)[1])
    assert ler_solo('texto de outra ferramenta')[1] != []

    print('leitura OK: uso do solo, cobertura recente, PRODES/DETER, relevo, imagem e as conferências de soma')
