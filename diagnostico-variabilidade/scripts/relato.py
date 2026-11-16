"""O texto do diagnóstico e da análise, em Markdown, pronto para a conversa.

As frases dizem "acompanha" e "varia junto". Nunca "causa", "explica" nem
"é o problema": a análise descreve quem varia junto com quem, e para aí.

Teste embutido: python scripts/relato.py
"""

import numpy as np


def br(v, casas=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return '—'
    texto = f'{v:,.{casas}f}'
    return texto.replace(',', '§').replace('.', ',').replace('§', '.')


def casas_de(valor):
    v = abs(valor) if valor else 1.0
    return 0 if v >= 1000 else 1 if v >= 100 else 2 if v >= 1 else 3


def inteiro(v):
    return f'{int(round(v)):,}'.replace(',', '.')


def sinal(v, casas=2):
    return ('+' if v >= 0 else '−') + br(abs(v), casas)


def metros(v, limitada=False):
    if v is None or not np.isfinite(v):
        return '—'
    return ('mais de ' if limitada else '') + f'{inteiro(v)} m'


def _resolucao(l):
    if l.get('tipo') == 'pontos':
        return f'pontos a cada {br(l["espacamento_m"], 1)} m ({inteiro(l["pontos_dentro"])} no talhão)'
    return f'raster de {br(l["pixel_m"], 1 if l["pixel_m"] < 10 else 0)} m ({l.get("src", "")})'


def texto_do_diagnostico(d, nome=None):
    L = [f'# Diagnóstico das camadas{" — " + nome if nome else ""}', '',
         f'Área de {br(d["area_ha"], 1)} ha (UTM {d["utm"]}). Grade comum: células de {d["celula_m"]:g} m '
         f'({"automática" if d["celula_automatica"] else "informada"}), {inteiro(d["celulas_no_perimetro"])} células dentro do perímetro.',
         '', '## Camadas numéricas', '',
         '| Camada | Origem | Cobertura | Mínimo | Média | Máximo | CV | Distância de correlação | Observações independentes |',
         '|---|---|---|---|---|---|---|---|---|']
    for l in d['camadas']:
        c = casas_de(l['media'])
        L.append(f'| {l["nome"]} | {_resolucao(l)}; {l.get("arquivo", "")} | {br(l["cobertura_pct"], 0)}% | {br(l["minimo"], c)} | '
                 f'{br(l["media"], c)} | {br(l["maximo"], c)} | {br(l["cv_pct"], 1)}% | '
                 f'{metros(l.get("distancia_de_correlacao_m"), l.get("distancia_limitada"))} | '
                 f'{"—" if l.get("unidades_independentes") is None else "cerca de " + inteiro(l["unidades_independentes"])} |')
    notas = [(l['nome'], n) for l in d['camadas'] for n in l['notas']]
    if notas:
        L += ['', 'Notas:'] + [f'- {nome_c}: {n}.' for nome_c, n in notas]
    L += ['', 'Distância de correlação: até onde as células vizinhas se parecem. Observações independentes: quantas '
              'observações soltas o mapa vale, descontada essa semelhança.']
    if d['classes']:
        L += ['', '## Camadas de classes', '', '| Camada | Arquivo | Cobertura | Classes (células) |', '|---|---|---|---|']
        for c in d['classes']:
            L.append(f'| {c["nome"]} | {c["arquivo"]} | {br(c["cobertura_pct"], 0)}% | '
                     + '; '.join(f'{k} ({inteiro(v)})' for k, v in c['celulas_por_classe'].items()) + ' |')
    L += ['', '## O conjunto', '',
          f'- Células com valor em todas as camadas: {inteiro(d["celulas_completas_com_todas"])} de {inteiro(d["celulas_no_perimetro"])} '
          f'({br(100 * d["celulas_completas_com_todas"] / d["celulas_no_perimetro"], 0)}%).']
    if d['pares_parecidos']:
        L.append('- Camadas parecidas entre si (|r| de 0,80 para cima): '
                 + '; '.join(f'{p["a"]} e {p["b"]} (r = {sinal(p["r"])}{", quase iguais" if p["quase_iguais"] else ""})' for p in d['pares_parecidos']) + '.')
    else:
        L.append('- Nenhum par de camadas com |r| de 0,80 para cima.')
    if d['ignoradas']:
        L.append('- Colunas deixadas de fora: ' + '; '.join(d['ignoradas']) + '.')
    for a in d['avisos']:
        L.append(f'- Aviso: {a}.')
    L += ['', '## O que falta decidir', '',
          '1. Qual é a variável a explicar (`--alvo`).',
          '2. Quais camadas entram (`--camadas`, e `--com-classes` para as de classes). Camadas parecidas entre si repartem a importância.',
          '3. Se alguma camada é índice de vegetação da MESMA safra da variável a explicar, ou outra medida da mesma coisa: ela fica de fora.',
          '4. Se a célula e as faixas das manchas ficam como estão (`--celula`, `--faixas` ou `--cortes`).', '',
          'Nada foi calculado além desta descrição. A análise só roda com as escolhas acima.']
    return '\n'.join(L) + '\n'


def frases_de_leitura(r):
    """As frases principais do resultado, na ordem em que vão para a conversa e para o PDF."""
    alvo, f = r['alvo'], []
    piso = r['piso_de_ruido']
    frase = (f'Juntas, as {len(r["importancia"])} camadas acompanham {br(100 * r["r2_do_conjunto"], 0)}% da variação de {alvo} entre as '
             f'células (R² = {br(r["r2_do_conjunto"])}).') if len(r['importancia']) > 1 else \
        f'A camada acompanha {br(100 * r["r2_do_conjunto"], 0)}% da variação de {alvo} entre as células (R² = {br(r["r2_do_conjunto"])}).'
    if piso is None:
        frase += ' Com tão poucas observações independentes para tantas camadas, esse número não se separa do acaso.'
    elif r['r2_do_conjunto'] <= piso:
        frase += f' Isso não passa do que camadas sem relação alcançam por acaso ({br(piso)}).'
    else:
        frase += f' Camadas sem relação nenhuma chegariam por acaso a até {br(piso)}.'
    f.append(frase)
    for l in r['importancia'][:6]:
        parte = l['repartida'] if l['repartida'] is not None else l['sozinha']
        if l['tipo'] == 'classes':
            f.append(f'{l["nome"]} (classes): sozinha acompanha {br(100 * l["sozinha"], 0)}% e acrescenta {br(100 * l["por_cima"], 0)}% '
                     f'por cima das outras; parte repartida de {br(100 * parte, 0)}%.')
            continue
        direcao = 'sobe junto' if l['r'] > 0 else 'desce quando ela sobe'
        if not l['fora_de_zero']:
            direcao = 'não mostra relação que se distinga do acaso'
        f.append(f'{l["nome"]}: {alvo} {direcao} (r = {sinal(l["r"])}; intervalo de 95% de {sinal(l["intervalo"][0])} a '
                 f'{sinal(l["intervalo"][1])}, com cerca de {inteiro(l["n_efetivo"])} observações independentes). '
                 + (f'Sozinha acompanha {br(100 * l["sozinha"], 0)}%; por cima das outras, {br(100 * l["por_cima"], 0)}%; parte repartida de '
                    f'{br(100 * parte, 0)}%.' if len(r['importancia']) > 1 else f'Acompanha {br(100 * l["sozinha"], 0)}% da variação.')
                 + (' ' + '; '.join(n[0].upper() + n[1:] for n in l['notas'] if n != 'não se distingue de zero') + '.'
                    if [n for n in l['notas'] if n != 'não se distingue de zero'] else ''))
    return f


def texto_da_analise(r, nome=None):
    alvo, a = r['alvo'], r['alvo_resumo']
    c = casas_de(a['media'])
    L = [f'# O que acompanha a variabilidade de {alvo}{" — " + nome if nome else ""}', '',
         f'Análise em {inteiro(r["celulas"])} células de {r["celula_m"]:g} m ({br(r["area_analisada_ha"], 1)} ha; '
         f'{br(100 * r["celulas"] / r["celulas_no_perimetro"], 0)}% das células da área), as que têm valor em todas as camadas escolhidas.',
         f'{alvo}: média {br(a["media"], c)}, de {br(a["minimo"], c)} a {br(a["maximo"], c)}, CV de {br(a["cv_pct"], 1)}%; '
         f'células vizinhas se parecem até cerca de {metros(a["distancia_de_correlacao_m"])}.',
         '', '## Leitura', ''] + [f'- {x}' for x in frases_de_leitura(r)]
    L += ['', '## Camada por camada', '',
          '| Camada | r (Pearson) | Intervalo de 95% | Spearman | Observações independentes | Sozinha | Por cima das outras | Repartida | Notas |',
          '|---|---|---|---|---|---|---|---|---|']
    for l in r['importancia']:
        rep = '—' if l['repartida'] is None else br(100 * l['repartida'], 1) + '%'
        if l['tipo'] == 'classes':
            L.append(f'| {l["nome"]} (classes) | — | — | — | — | {br(100 * l["sozinha"], 1)}% | {br(100 * l["por_cima"], 1)}% | {rep} | '
                     f'{"; ".join(l["notas"]) or "—"} |')
        else:
            L.append(f'| {l["nome"]} | {sinal(l["r"])} | {sinal(l["intervalo"][0])} a {sinal(l["intervalo"][1])} | {sinal(l["spearman"])} | '
                     f'cerca de {inteiro(l["n_efetivo"])} | {br(100 * l["sozinha"], 1)}% | {br(100 * l["por_cima"], 1)}% | {rep} | '
                     f'{"; ".join(l["notas"]) or "—"} |')
    L += ['', f'Sozinha, por cima das outras e repartida são frações da variação de {alvo} (R²). As partes repartidas somam o R² do conjunto '
              f'({br(100 * r["r2_do_conjunto"], 1)}%).']
    for l in r['importancia']:
        if l['tipo'] == 'classes':
            L += ['', f'### {alvo} em cada classe de {l["nome"]}', '', '| Classe | Área | Média | Desvio |', '|---|---|---|---|']
            L += [f'| {k["classe"]} | {br(k["area_ha"], 1)} ha | {br(k["media"], c)} | {br(k["desvio"], c)} |' for k in l['classes']]
            L += ['', 'Média crua de cada classe: as outras camadas também mudam de uma classe para outra, e a diferença pode vir delas.']
    m = r['manchas']
    L += ['', '## As manchas', '',
          f'{alvo} repartida em {len(m["faixas"])} faixas ' + ('de mesma área (quantis)' if m['por_quantil'] else 'pelos cortes informados')
          + f': cortes em {", ".join(br(x, c) for x in m["cortes"])}.' + (' Uma passada de filtro de maioria tirou células soltas.' if m['filtro'] else ''),
          '', '| Faixa | Área | ' + alvo + ' | Manchas | ' + ' | '.join(r['camadas']) + ' |',
          '|---|---|---|---|' + '---|' * len(r['camadas'])]
    for f in m['faixas']:
        L.append(f'| {f["faixa"]} | {br(f["area_ha"], 1)} ha ({br(f["area_pct"], 0)}%) | {br(f["alvo_media"], c)} | '
                 f'{f["manchas"]} de {br(m["mancha_minima_ha"], 1)} ha ou mais; a maior com {br(f["maior_ha"], 1)} ha | '
                 + ' | '.join(br(f['camadas'][k]['media'], casas_de(f['camadas'][k]['media'])) for k in r['camadas']) + ' |')
    if r['camadas']:
        L += ['', 'Diferença entre a faixa mais alta e a mais baixa, em desvios de cada camada: '
              + '; '.join(f'{k} {sinal(v, 1)}' for k, v in sorted(m['separacao'].items(), key=lambda t: -abs(t[1] or 0)) if v is not None) + '.']
    for nome_c in r['classes']:
        L += ['', f'Parte de cada faixa em cada classe de {nome_c}: '
              + '; '.join(f'{f["faixa"]}: ' + ', '.join(f'{k} {br(v, 0)}%' for k, v in f['classes'][nome_c].items()) for f in m['faixas']) + '.']
    if r['avisos']:
        L += ['', '## Avisos', ''] + [f'- {x}' for x in r['avisos']]
    L += ['', '## Como ler', '',
          '- Variar junto não é causa. Duas camadas podem se acompanhar porque uma terceira mexe nas duas, ou por acaso.',
          '- As células de um mapa não são observações independentes: vizinhas se parecem. Por isso o intervalo de cada correlação usa o '
          'número de observações independentes, bem menor que o de células. Intervalo que inclui o zero: a relação não se distingue do acaso.',
          '- Mapa interpolado de poucas amostras é suave por construção: acompanha outros mapas suaves com facilidade.',
          '- A conta é de reta. Relação em curva aparece na nota da camada e no perfil das manchas, não no r.',
          '- O que fazer com isto no manejo é decisão do responsável técnico, com o conhecimento da área.']
    return '\n'.join(L) + '\n'


def _autoteste():
    assert br(1234.5, 1) == '1.234,5' and br(None) == '—' and sinal(-0.5) == '−0,50' and sinal(0.25) == '+0,25'
    assert inteiro(5305) == '5.305' and metros(123.4) == '123 m' and metros(900, True) == 'mais de 900 m' and casas_de(380) == 1
    d = {'area_ha': 53.1, 'utm': '22S', 'celula_m': 10.0, 'celula_automatica': True, 'celulas_no_perimetro': 5313,
         'camadas': [{'nome': 'argila', 'tipo': 'raster', 'arquivo': 'a.tif', 'pixel_m': 5.0, 'src': 'UTM 22S', 'cobertura_pct': 100.0,
                      'minimo': 200.0, 'media': 380.0, 'maximo': 560.0, 'cv_pct': 23.0, 'distancia_de_correlacao_m': 95.0,
                      'distancia_limitada': False, 'unidades_independentes': 31.0, 'notas': ['varia devagar no talhão']},
                     {'nome': 'prod', 'tipo': 'pontos', 'arquivo': 'c.csv', 'espacamento_m': 5.1, 'pontos_dentro': 11000,
                      'cobertura_pct': 99.0, 'minimo': 2.0, 'media': 3.7, 'maximo': 5.5, 'cv_pct': 14.0, 'notas': []}],
         'classes': [{'nome': 'variedade', 'arquivo': 'v.geojson', 'cobertura_pct': 100.0, 'celulas_por_classe': {'A': 2600, 'B': 2700}}],
         'celulas_completas_com_todas': 5200, 'pares_parecidos': [{'a': 'argila', 'b': 'outra', 'r': 0.99, 'quase_iguais': True}],
         'ignoradas': ['id (c.csv: parece identificador)'], 'avisos': []}
    t = texto_do_diagnostico(d, 'Talhão 7')
    assert '# Diagnóstico das camadas — Talhão 7' in t and '| argila | raster de 5,0 m (UTM 22S); a.tif | 100% |' in t
    assert 'pontos a cada 5,1 m (11.000 no talhão)' in t and 'cerca de 31' in t and 'quase iguais' in t
    assert '`--alvo`' in t and 'A análise só roda com as escolhas acima.' in t
    # "variável a explicar" é o nome da resposta; o que não pode é dizer que uma camada explica ou causa
    for palavra in ('causa', 'explica ', 'explicam', 'problema', 'recomend'):
        assert palavra not in t.lower(), palavra
    print('relato OK (formatação e texto do diagnóstico; o texto da análise é testado no variabilidade.py)')


if __name__ == '__main__':
    _autoteste()
