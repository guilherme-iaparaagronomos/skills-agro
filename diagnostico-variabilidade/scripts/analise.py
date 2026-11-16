"""A análise, depois que o usuário escolheu a variável a explicar e as camadas.

Sai daqui, para as células que têm valor em TODAS as camadas escolhidas:

- a correlação de cada par (Pearson e Spearman), com o tamanho efetivo de
  amostra e o intervalo de 95% que respeita a semelhança entre vizinhas;
- a parte de cada camada no que o conjunto acompanha (sozinha, por cima das
  outras, repartida);
- as manchas da variável a explicar e o perfil de cada camada nelas;
- os avisos: camada que é quase a própria resposta, camadas redundantes,
  poucas observações independentes, conjunto que não passa do ruído.

Só descreve. Nada aqui é causa nem recomendação.

Teste embutido: python scripts/analise.py
"""

import numpy as np

import manchas as M
import relacoes as R
from espacial import Defasagens, intervalo_de_r

MINIMO_DE_CELULAS = 50
POUCAS_UNIDADES = 15


class EscolhaInvalida(Exception):
    """A escolha do usuário não dá análise. A mensagem diz o motivo."""


def analisar(estado, alvo, camadas, classes=(), faixas=3, cortes=None, filtro=True, mancha_minima_ha=None):
    numericas_do_estado = estado['camadas']
    camadas, classes = list(dict.fromkeys(camadas)), list(dict.fromkeys(classes))
    if alvo not in numericas_do_estado:
        raise EscolhaInvalida(f'a variável a explicar "{alvo}" não está entre as camadas numéricas: {", ".join(numericas_do_estado)}')
    if alvo in camadas:
        raise EscolhaInvalida(f'"{alvo}" é a variável a explicar: tire-a da lista de camadas')
    faltam = [c for c in camadas if c not in numericas_do_estado] + [c for c in classes if c not in estado['classes']]
    if faltam:
        raise EscolhaInvalida(f'camada que não existe: {", ".join(faltam)}. As lidas: '
                              f'{", ".join(list(numericas_do_estado) + list(estado["classes"]))}')
    if not camadas and not classes:
        raise EscolhaInvalida('é preciso pelo menos uma camada além da variável a explicar: com uma camada só não há o que comparar')

    g = estado['grade']
    y_malha = numericas_do_estado[alvo]['malha']
    valida = g['mascara'] & np.isfinite(y_malha)
    limitante, menor = None, int(valida.sum())
    for nome in camadas:
        antes = valida.sum()
        valida = valida & np.isfinite(numericas_do_estado[nome]['malha'])
        if antes - valida.sum() > 0 and valida.sum() < menor:
            limitante, menor = nome, int(valida.sum())
    for nome in classes:
        valida = valida & (estado['classes'][nome]['rotulos'] >= 0)
    n = int(valida.sum())
    if n < MINIMO_DE_CELULAS:
        raise EscolhaInvalida(f'só {n} células têm valor em todas as camadas escolhidas (mínimo {MINIMO_DE_CELULAS}). Confira a cobertura '
                              'de cada camada no diagnóstico' + (f'; a que mais limita é "{limitante}"' if limitante else ''))
    y = y_malha[valida]
    if y.std() <= 0:
        raise EscolhaInvalida(f'"{alvo}" é constante nas células em comum: não há variabilidade para descrever')
    constantes = [c for c in camadas if numericas_do_estado[c]['malha'][valida].std() <= 0]
    if constantes:
        raise EscolhaInvalida(f'camada constante nas células em comum: {", ".join(constantes)}. Tire-a da lista')

    avisos = []
    nomes = [alvo] + camadas
    colunas = {nome: numericas_do_estado[nome]['malha'][valida] for nome in nomes}
    pearson, spearman = R.correlacoes(np.column_stack([colunas[k] for k in nomes]))

    # dependência espacial: tamanho efetivo e intervalo de cada par
    d = Defasagens(valida, g['celula'])
    somas = {nome: d.somas(numericas_do_estado[nome]['malha']) for nome in nomes}
    p = len(nomes)
    n_ef = np.full((p, p), np.nan)
    baixo, alto = np.full((p, p), np.nan), np.full((p, p), np.nan)
    for i in range(p):
        for j in range(i, p):
            ef, _ = d.tamanho_efetivo(*somas[nomes[i]], *somas[nomes[j]])
            n_ef[i, j] = n_ef[j, i] = ef
            if i != j:
                lo, hi = intervalo_de_r(pearson[i, j], ef)
                baixo[i, j] = baixo[j, i] = lo
                alto[i, j] = alto[j, i] = hi
    alcance = {}
    for nome in nomes:
        s, v = somas[nome]
        alcance[nome] = d.distancia_de_correlacao(d.correlograma(s, v))

    # a parte de cada camada
    categoricas = {nome: estado['classes'][nome]['rotulos'][valida] for nome in classes}
    try:
        nomes_blocos, x, blocos = R.blocos_de({k: colunas[k] for k in camadas}, categoricas)
        imp = R.importancia(y, x, blocos)
    except R.DadosInvalidos as erro:
        raise EscolhaInvalida(str(erro))
    n_colunas = x.shape[1]
    ef_das_camadas = [float(n_ef[0, nomes.index(c)]) for c in camadas]
    ef_do_conjunto = min(ef_das_camadas) if ef_das_camadas else float(n)
    piso = R.piso_de_ruido(n_colunas, ef_do_conjunto)

    linhas = []
    for j, nome in enumerate(nomes_blocos):
        linha = {'nome': nome, 'tipo': 'classes' if nome in classes else 'numerica', 'sozinha': imp['sozinha'][j],
                 'por_cima': imp['por_cima'][j], 'repartida': None if imp['repartida'] is None else imp['repartida'][j],
                 'notas': []}
        if nome in camadas:
            k = nomes.index(nome)
            reta, curva = R.em_curva(y, colunas[nome])
            fora_de_zero = bool(np.isfinite(baixo[0, k]) and not (baixo[0, k] <= 0 <= alto[0, k]))
            linha.update(r=float(pearson[0, k]), spearman=float(spearman[0, k]), n_efetivo=float(n_ef[0, k]),
                         intervalo=(float(baixo[0, k]), float(alto[0, k])), fora_de_zero=fora_de_zero,
                         coeficiente_no_conjunto=imp['coeficiente_no_conjunto'][j], inflacao=imp['inflacao'][j],
                         r2_reta=reta, r2_curva=curva, distancia_de_correlacao_m=alcance[nome][0])
            if abs(linha['r']) >= R.QUASE_A_RESPOSTA:
                linha['notas'].append('quase a própria resposta')
                avisos.append(f'"{nome}" e "{alvo}" andam quase iguais (r = {_br(linha["r"])}). Se for índice de vegetação da MESMA '
                              'safra, ou outra medida da mesma coisa, ela não ajuda a entender a variabilidade: tire-a e rode de novo.')
            if not fora_de_zero:
                linha['notas'].append('não se distingue de zero')
            if linha['n_efetivo'] < POUCAS_UNIDADES:
                linha['notas'].append('poucas observações independentes')
            if curva - reta >= 0.05:
                linha['notas'].append(f'relação em curva (R² da reta {_br(reta)}, da curva {_br(curva)})')
            if abs(linha['spearman'] - linha['r']) >= 0.15:
                linha['notas'].append('Pearson e Spearman diferem: relação que não é reta, ou valores extremos')
            coef = linha['coeficiente_no_conjunto']
            if coef is not None and abs(coef) > 0.05 and abs(linha['r']) > 0.05 and (coef > 0) != (linha['r'] > 0) and len(nomes_blocos) > 1:
                linha['notas'].append('o sinal muda quando as outras camadas entram (efeito de camadas parecidas)')
            if linha['inflacao'] is not None and linha['inflacao'] >= 5:
                linha['notas'].append('muito parecida com o conjunto das outras')
        else:
            rot, nomes_c = estado['classes'][nome]['rotulos'][valida], estado['classes'][nome]['nomes']
            linha['classes'] = [{'classe': c, 'celulas': int((rot == i).sum()), 'area_ha': float((rot == i).sum() * g['celula'] ** 2 / 10000),
                                 'media': float(y[rot == i].mean()) if (rot == i).any() else None,
                                 'desvio': float(y[rot == i].std()) if (rot == i).any() else None} for i, c in enumerate(nomes_c)]
        if len(nomes_blocos) > 1 and linha['por_cima'] > linha['sozinha'] + 0.02:
            linha['notas'].append('aparece mais quando as outras camadas entram: sozinha, as outras escondiam a relação')
        linhas.append(linha)
    ordem = sorted(range(len(linhas)), key=lambda j: -(linhas[j]['repartida'] if linhas[j]['repartida'] is not None else linhas[j]['sozinha']))
    linhas = [linhas[j] for j in ordem]

    redundantes = R.pares_redundantes(pearson[1:, 1:], camadas) if len(camadas) > 1 else []
    for a, b, r in redundantes:
        avisos.append(f'"{a}" e "{b}" dizem quase a mesma coisa (r = {_br(r)}): o que as duas têm em comum fica repartido entre elas, '
                      'e nenhuma acrescenta muito por cima da outra. Isso não diz qual das duas importa.')
    if imp['repartida'] is None:
        avisos.append(f'com mais de {R.TETO_DO_REPARTIDA} camadas a coluna "repartida" não é calculada; ficam "sozinha" e "por cima das outras".')
    if piso is None:
        avisos.append(f'há {n_colunas} coluna(s) de camadas para cerca de {ef_do_conjunto:.0f} observações independentes: o R² do conjunto '
                      'não pode ser separado do acaso. Use menos camadas.')
    elif imp['r2_do_conjunto'] <= piso:
        avisos.append(f'o R² do conjunto ({_br(imp["r2_do_conjunto"])}) não passa do que camadas sem relação nenhuma alcançariam por acaso '
                      f'com cerca de {ef_do_conjunto:.0f} observações independentes ({_br(piso)}).')
    poucas = [l['nome'] for l in linhas if l.get('n_efetivo') is not None and l['n_efetivo'] < POUCAS_UNIDADES]
    if poucas:
        avisos.append(f'camada(s) que variam devagar no talhão, com menos de {POUCAS_UNIDADES} observações independentes na comparação: '
                      f'{", ".join(poucas)}. Duas camadas suaves se acompanham por acaso com frequência; olhe o intervalo, não só o r.')
    fracao = n / estado['celulas']
    if fracao < 0.8:
        avisos.append(f'a análise usa {100 * fracao:.0f}% das células do talhão ({n} de {estado["celulas"]}): fora delas alguma camada '
                      'não tem valor' + (f'; a que mais limita é "{limitante}"' if limitante else '') + '.')
    for nome in nomes:
        info = numericas_do_estado[nome]['info']
        if info.get('mais_grossa_que_a_celula'):
            avisos.append(f'"{nome}" tem pixel de {info["pixel_m"]:.0f} m, maior que a célula de {g["celula"]:g} m: células vizinhas repetem o mesmo valor.')
    avisos += estado['avisos']

    # manchas
    try:
        cortes_usados = sorted(float(c) for c in cortes) if cortes else M.cortes_por_quantil(y, faixas)
    except ValueError as erro:
        raise EscolhaInvalida(str(erro))
    n_faixas = len(cortes_usados) + 1
    if n_faixas not in M.NOMES:
        raise EscolhaInvalida('informe de 1 a 4 cortes (2 a 5 faixas)')
    mapa = M.classificar(y_malha, valida, cortes_usados)
    if len({int(v) for v in np.unique(mapa[valida])}) < n_faixas:
        raise EscolhaInvalida(f'com os cortes {", ".join(_br(c) for c in cortes_usados)} alguma faixa fica vazia: "{alvo}" vai de '
                              f'{_br(float(y.min()))} a {_br(float(y.max()))}')
    if filtro:
        mapa = M.filtro_de_maioria(mapa, n_faixas)
    minima = mancha_minima_ha if mancha_minima_ha is not None else max(0.1, 0.005 * n * g['celula'] ** 2 / 10000)
    perfil = M.perfil(mapa, n_faixas, y_malha, {k: numericas_do_estado[k]['malha'] for k in camadas},
                      {k: (estado['classes'][k]['rotulos'], estado['classes'][k]['nomes']) for k in classes}, g['celula'])
    for linha, parte in zip(perfil['faixas'], M.partes(mapa, n_faixas, g['celula'], minima)):
        linha.update(parte)

    return {
        'alvo': alvo, 'camadas': camadas, 'classes': classes, 'celulas': n, 'celulas_no_perimetro': estado['celulas'],
        'area_analisada_ha': n * g['celula'] ** 2 / 10000, 'celula_m': g['celula'], 'nomes': nomes, 'pearson': pearson,
        'spearman': spearman, 'n_efetivo': n_ef, 'intervalo_baixo': baixo, 'intervalo_alto': alto,
        'alvo_resumo': {'media': float(y.mean()), 'desvio': float(y.std()), 'minimo': float(y.min()), 'maximo': float(y.max()),
                        'cv_pct': float(100 * y.std() / abs(y.mean())) if y.mean() else None,
                        'distancia_de_correlacao_m': alcance[alvo][0]},
        'importancia': linhas, 'r2_do_conjunto': imp['r2_do_conjunto'], 'colunas_do_conjunto': n_colunas,
        'n_efetivo_do_conjunto': ef_do_conjunto, 'piso_de_ruido': piso, 'redundantes': redundantes, 'avisos': avisos,
        'manchas': {'cortes': cortes_usados, 'por_quantil': not cortes, 'filtro': bool(filtro), 'mancha_minima_ha': minima,
                    'mapa': mapa, **perfil},
        'valida': valida,
    }


def _br(v, casas=2):
    return format(v, f'.{casas}f').replace('.', ',')


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    import tempfile

    import camadas as C
    import sintetico
    with tempfile.TemporaryDirectory() as pasta:
        e = sintetico.gravar(pasta)
        p = e['pasta']
        estado = C.carregar(str(p / 'talhao.geojson'),
                            rasters=[f'argila={p / "argila_g_kg.tif"}', f'argila_outra={p / "argila_outra_g_kg.tif"}',
                                     f'altitude={p / "altitude_m.tif"}', f'ph={p / "ph.tif"}',
                                     f'ndvi_mesma_safra={p / "ndvi_mesma_safra.tif"}'],
                            pontos=[str(p / 'colheita_limpa.csv')], classes=[f'variedade={p / "variedades.geojson"}:variedade'])
    r = analisar(estado, 'prod_t_ha', ['argila', 'argila_outra', 'altitude', 'ph'], ['variedade'])
    por = {l['nome']: l for l in r['importancia']}
    # o plantado aparece: argila sobe, altitude desce, pH não se distingue de zero
    assert por['argila']['r'] > 0.5 and por['argila']['fora_de_zero'], por['argila']
    assert por['altitude']['r'] < -0.25 and por['altitude']['fora_de_zero'], por['altitude']
    assert not por['ph']['fora_de_zero'] and por['ph']['repartida'] < 0.02, por['ph']
    # a cópia: alta sozinha, quase nada por cima, reparte com a argila, e o aviso sai
    assert por['argila_outra']['sozinha'] > 0.4 and por['argila_outra']['por_cima'] < 0.02 and por['argila']['por_cima'] < 0.05
    assert abs(por['argila']['repartida'] - por['argila_outra']['repartida']) < 0.08
    assert r['redundantes'][0][:2] == ('argila', 'argila_outra') and any('quase a mesma coisa' in a for a in r['avisos'])
    # as partes repartidas somam o R² do conjunto, que passa do piso de ruído
    assert abs(sum(l['repartida'] for l in r['importancia']) - r['r2_do_conjunto']) < 1e-9
    assert 0.6 < r['r2_do_conjunto'] < 0.9 and r['piso_de_ruido'] is not None and r['r2_do_conjunto'] > r['piso_de_ruido']
    # tamanho efetivo muito menor que o número de células
    assert por['argila']['n_efetivo'] < r['celulas'] / 20 and por['argila']['intervalo'][0] < por['argila']['r'] < por['argila']['intervalo'][1]
    # variedade: o efeito plantado (+0,25 na B) fica escondido na média crua, porque a metade leste também tem mais
    # altitude; ele aparece quando as outras camadas entram, e a nota diz isso
    v = {c['classe']: c for c in por['variedade']['classes']}
    assert por['variedade']['tipo'] == 'classes' and abs(v['B']['media'] - v['A']['media']) < 0.2
    assert por['variedade']['por_cima'] > por['variedade']['sozinha'] + 0.02
    assert any('aparece mais' in nota for nota in por['variedade']['notas']), por['variedade']['notas']
    # manchas: três faixas de área parecida; a argila sobe do baixo para o alto
    f = r['manchas']['faixas']
    assert len(f) == 3 and all(25 < x['area_pct'] < 42 for x in f), [x['area_pct'] for x in f]
    assert f[0]['camadas']['argila']['media'] < f[2]['camadas']['argila']['media'] and r['manchas']['separacao']['argila'] > 1
    assert r['manchas']['separacao']['altitude'] < -0.4 and abs(r['manchas']['separacao']['ph']) < 0.5
    assert abs(sum(f[0]['classes']['variedade'].values()) - 100) < 1e-9
    # índice da mesma safra: aviso de que é quase a própria resposta
    r2 = analisar(estado, 'prod_t_ha', ['argila', 'altitude', 'ndvi_mesma_safra'])
    assert any('quase iguais' in a and 'ndvi_mesma_safra' in a for a in r2['avisos']), r2['avisos']
    # cortes informados e recusas
    r3 = analisar(estado, 'prod_t_ha', ['argila'], cortes=[3.2, 4.0], filtro=False)
    assert r3['manchas']['cortes'] == [3.2, 4.0] and not r3['manchas']['por_quantil']
    recusas = [
        (dict(alvo='prod', camadas=['argila']), 'não está entre as camadas'),
        (dict(alvo='prod_t_ha', camadas=['prod_t_ha', 'argila']), 'tire-a da lista'),
        (dict(alvo='prod_t_ha', camadas=['calcio']), 'camada que não existe'),
        (dict(alvo='prod_t_ha', camadas=[]), 'uma camada só'),
        (dict(alvo='prod_t_ha', camadas=['argila'], cortes=[99.0]), 'alguma faixa fica vazia'),
        (dict(alvo='prod_t_ha', camadas=['argila'], cortes=[1, 2, 3, 4, 5]), 'de 1 a 4 cortes'),
    ]
    for argumentos, trecho in recusas:
        try:
            analisar(estado, **argumentos)
        except EscolhaInvalida as erro:
            assert trecho in str(erro), (trecho, str(erro))
        else:
            raise AssertionError(f'devia recusar: {trecho}')
    # poucas células em comum e variável constante
    oco = {**estado, 'camadas': {**estado['camadas']}}
    buraco = np.full_like(estado['camadas']['ph']['malha'], np.nan)
    buraco[10:14, 30:38] = 5.0 + np.arange(32).reshape(4, 8) / 100
    oco['camadas']['furada'] = {'malha': buraco, 'info': {'tipo': 'raster'}, 'resumo': {}}
    plano = np.where(estado['grade']['mascara'], 7.0, np.nan)
    oco['camadas']['plana'] = {'malha': plano, 'info': {'tipo': 'raster'}, 'resumo': {}}
    for argumentos, trecho in [(dict(alvo='prod_t_ha', camadas=['furada']), 'células têm valor em todas'),
                               (dict(alvo='plana', camadas=['argila']), 'é constante'),
                               (dict(alvo='prod_t_ha', camadas=['plana']), 'camada constante')]:
        try:
            analisar(oco, **argumentos)
        except EscolhaInvalida as erro:
            assert trecho in str(erro), (trecho, str(erro))
        else:
            raise AssertionError(f'devia recusar: {trecho}')
    print(f'analise OK (R² do conjunto {r["r2_do_conjunto"]:.2f}; argila r = {por["argila"]["r"]:+.2f} com cerca de '
          f'{por["argila"]["n_efetivo"]:.0f} observações independentes em {r["celulas"]} células; {len(recusas) + 3} recusas)')


if __name__ == '__main__':
    _autoteste()
