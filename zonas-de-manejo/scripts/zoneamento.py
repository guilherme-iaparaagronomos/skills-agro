"""Dos pontos com camadas às zonas: junta o agrupamento, a grade e os polígonos.

  zonear()   a sequência inteira, com os números de cada etapa e os avisos

A ordem é a do método: padronizar as camadas (com peso, se houver) → componentes
principais → K-Means (número de grupos pela silhueta, ou o que o usuário
fixar) → classe pequena absorvida pelas vizinhas → fragmento solto reatribuído →
classe de cada célula da grade pelo ponto mais próximo → parte pequena fundida
à vizinha de maior divisa → polígonos com as divisas suavizadas.

Teste embutido: python scripts/zoneamento.py   (mede o método no talhão sintético)
"""

import math

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

import agrupamento
import grade
import vetor
from areas import dentro

ESPACAMENTOS = (5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 150, 200, 300)
TETO_PARA_AGREGAR = 20000


def espacamento_tipico(xy):
    """Distância mediana de cada ponto ao vizinho mais próximo (m)."""
    if len(xy) < 2:
        return 0.0
    distancia, _ = cKDTree(xy).query(xy, k=2)
    return float(np.median(distancia[:, 1]))


def espacamento_automatico(area_m2, alvo=6000):
    """Espaçamento redondo que dá perto de `alvo` pontos na área."""
    ideal = math.sqrt(area_m2 / alvo)
    return next((e for e in ESPACAMENTOS if e >= ideal), ESPACAMENTOS[-1])


def grade_de_pontos(areas, espacamento):
    """Pontos em grade regular dentro das áreas (para amostrar rasters quando não há pontos)."""
    xs = [p[0] for a in areas for anel in a['aneis'] for p in anel]
    ys = [p[1] for a in areas for anel in a['aneis'] for p in anel]
    gx, gy = np.meshgrid(np.arange(min(xs) + espacamento / 2, max(xs), espacamento),
                         np.arange(min(ys) + espacamento / 2, max(ys), espacamento))
    xy = np.column_stack([gx.ravel(), gy.ravel()])
    fica = np.zeros(len(xy), dtype=bool)
    for a in areas:
        fica |= dentro(a['aneis'], xy)
    return xy[fica]


def agregar(xy, X, celula):
    """Média dos pontos por célula de `celula` metros (para dado denso e ruidoso).
    Devolve (xy médio, X médio, pontos por célula)."""
    chave = np.floor(xy / celula).astype(np.int64)
    _, inverso, vezes = np.unique(chave, axis=0, return_inverse=True, return_counts=True)
    inverso = inverso.ravel()

    def media(M):
        soma = np.zeros((len(vezes), M.shape[1]))
        np.add.at(soma, inverso, M)
        return soma / vezes[:, None]

    return media(xy), media(X), vezes


def _ponto_de_rotulo(mascara, g):
    """Um ponto bem dentro da maior parte da zona (o mais longe da divisa), para escrever o número."""
    marcado, n = ndimage.label(mascara)
    if n == 0:
        return None
    maior = 1 + int(np.argmax(ndimage.sum(mascara, marcado, range(1, n + 1))))
    fundo = ndimage.distance_transform_edt(marcado == maior)
    linha, coluna = np.unravel_index(int(np.argmax(fundo)), fundo.shape)
    return g['x0'] + (coluna + 0.5) * g['pixel'], g['y0'] - (linha + 0.5) * g['pixel']


def zonear(xy, X, nomes, areas, cfg=None):
    """Roda o método. `xy` [n, 2] em metros, `X` [n, camadas] sem valor faltando, `areas` em metros.
    Devolve dict com as zonas (polígonos, área e médias), a grade, os números de cada etapa e os avisos."""
    c = {**agrupamento.PADRAO, 'k': 'auto', 'pesos': None, 'pixel': None, 'suavizar': None, 'ordenar_por': 0,
         'iteracoes': 2, 'deslocamento': 0.25, **(cfg or {})}
    xy, X = np.asarray(xy, float), np.asarray(X, float)
    n, alertas = len(xy), []
    if n < 30:
        raise ValueError(f'só {n} pontos dentro do perímetro: é pouco para formar zonas')
    Z, _, _ = agrupamento.padronizar(X, c['pesos'])
    comp = agrupamento.pca(Z, c['variancia_pca'])
    escores = comp['escores']

    # ---- número de grupos
    if c['k'] == 'auto':
        tabela = agrupamento.escolher_k(escores, c['k_min'], c['k_max'], c['semente'])
        validas = [t for t in tabela if np.isfinite(t['silhueta'])]
        if not validas:
            raise ValueError('não foi possível formar grupos com estas camadas')
        escolhida = max(validas, key=lambda t: t['silhueta'])
    else:
        rotulos, _, inercia = agrupamento.kmeans(escores, int(c['k']), c['semente'])
        escolhida = {'k': int(c['k']), 'silhueta': agrupamento.silhueta(escores, rotulos, semente=c['semente']),
                     'inercia': inercia, 'rotulos': rotulos}
        tabela = [escolhida]
    rotulos = escolhida['rotulos']

    # ---- refino nos pontos
    min_pontos = max(int(math.ceil(c['area_minima'] * n)), 1)
    antes = len(np.unique(rotulos))
    rotulos = agrupamento.tamanho_minimo(xy, rotulos, min_pontos, c['vizinhos'])
    absorvidas = antes - len(np.unique(rotulos))
    rotulos, fragmentos = agrupamento.refinar_fragmentos(xy, rotulos, c['vizinhos'], c['frag_total'], c['frag_classe'],
                                                         c['max_iter'])

    # ---- grade e fusão das partes pequenas
    espacamento = espacamento_tipico(xy)
    area_m2 = sum(_area(a['aneis']) for a in areas)
    pixel = c['pixel'] or grade.pixel_automatico(area_m2, espacamento)
    g = grade.montar_grade(areas, pixel)
    dentro_da_grade = int(g['mascara'].sum())
    L = grade.classes_em_grade(g, xy, rotulos)
    minimo_de_celulas = max(int(c['area_minima'] * dentro_da_grade), 1)
    L, fusoes = grade.fundir_partes_pequenas(L, minimo_de_celulas)
    _, _, tamanho_das_partes = grade.partes(L)
    isoladas = int((tamanho_das_partes[1:] < minimo_de_celulas).sum())

    # ---- a classe final de cada ponto vem da grade (a mesma dos polígonos)
    coluna = np.clip(((xy[:, 0] - g['x0']) / pixel).astype(int), 0, g['nx'] - 1)
    linha = np.clip(((g['y0'] - xy[:, 1]) / pixel).astype(int), 0, g['ny'] - 1)
    finais = L[linha, coluna]
    finais = np.where(finais >= 0, finais, rotulos)
    presentes = [int(k) for k in np.unique(L[L >= 0])]
    finais = np.where(np.isin(finais, presentes), finais, presentes[0])

    # ---- numera as zonas pela média da camada de ordenação (zona 1 = a menor média)
    ordem_col = int(c['ordenar_por'])
    medias = {k: float(X[finais == k, ordem_col].mean()) if (finais == k).any() else math.inf for k in presentes}
    numero = {k: i + 1 for i, k in enumerate(sorted(presentes, key=lambda k: medias[k]))}
    grade_final = np.full(L.shape, -1, dtype=np.int32)
    for k, novo in numero.items():
        grade_final[L == k] = novo
    zona_do_ponto = np.array([numero[int(k)] for k in finais])

    # ---- polígonos
    suavizar = c['suavizar'] if c['suavizar'] is not None else max(espacamento, pixel)
    poligonos = vetor.vetorizar(grade_final, g, tolerancia=float(suavizar), iteracoes=c['iteracoes'] if suavizar else 0,
                                deslocamento=c['deslocamento'], perimetro=[anel for a in areas for anel in a['aneis']])
    area_da_grade = dentro_da_grade * pixel * pixel / 10000
    area_total = sum(vetor.area_ha(p) for lista in poligonos.values() for p in lista) or area_da_grade
    zonas = []
    for z in sorted(numero.values()):
        do_ponto = zona_do_ponto == z
        celulas = int((grade_final == z).sum())
        desenhada = sum(vetor.area_ha(p) for p in poligonos.get(z, []))
        estat = {nome: {'media': float(X[do_ponto, j].mean()), 'dp': float(X[do_ponto, j].std(ddof=1)) if do_ponto.sum() > 1 else 0.0,
                        'min': float(X[do_ponto, j].min()), 'max': float(X[do_ponto, j].max())}
                 for j, nome in enumerate(nomes)} if do_ponto.any() else {}
        zonas.append({'zona': z, 'ha': desenhada, 'pct': 100 * desenhada / area_total,
                      'ha_na_grade': celulas * pixel * pixel / 10000,
                      'partes': len(poligonos.get(z, [])), 'pontos': int(do_ponto.sum()), 'estat': estat,
                      'poligonos': poligonos.get(z, []), 'rotulo': _ponto_de_rotulo(grade_final == z, g)})
    desenhado = area_total
    area_do_perimetro = sum(_area(a['aneis']) for a in areas) / 10000
    maior_desvio = max((abs(z['ha'] - z['ha_na_grade']) for z in zonas), default=0.0)

    # ---- o que as zonas explicam
    k_final = len(zonas)
    reducao = {nome: agrupamento.reducao_de_variancia(X[:, j], zona_do_ponto) for j, nome in enumerate(nomes)}
    silhueta_final = agrupamento.silhueta(escores, zona_do_ponto, semente=c['semente']) if k_final > 1 else float('nan')
    correlacao = np.corrcoef(X.T) if X.shape[1] > 1 else np.ones((1, 1))
    repetidas = [(nomes[i], nomes[j], float(correlacao[i, j])) for i in range(len(nomes)) for j in range(i + 1, len(nomes))
                 if abs(correlacao[i, j]) > 0.9]

    if k_final < escolhida['k']:
        alertas.append(f'O agrupamento formou {escolhida["k"]} grupos, mas {escolhida["k"] - k_final} ficaram abaixo da '
                       f'área mínima ({agrupamento_pct(c["area_minima"])} da área) e foram absorvidos pelos vizinhos: '
                       f'sobraram {k_final} zona(s).')
    if isoladas:
        alertas.append(f'{isoladas} parte(s) de zona ficaram abaixo da área mínima por serem blocos separados do resto do '
                       f'talhão (sem zona vizinha com quem fundir): foram mantidas como estão.')
    if len(areas) > 1:
        alertas.append(f'O perímetro tem {len(areas)} áreas e as zonas foram feitas para o conjunto: a mesma zona pode '
                       f'aparecer em mais de uma, e a área mínima vale para o total. Para zonas dentro de cada talhão, '
                       f'rode um talhão por vez.')
    if k_final < 2:
        alertas.append('Sobrou uma zona só: com estas camadas e esta área mínima, o talhão não se divide. Diminua a '
                       'área mínima ou reveja as camadas.')
    if np.isfinite(escolhida['silhueta']) and escolhida['silhueta'] < 0.25:
        alertas.append(f'A silhueta do agrupamento é {escolhida["silhueta"]:.2f} (abaixo de 0,25): os grupos encostam uns '
                       f'nos outros. As camadas não formam zonas nítidas; trate o mapa como uma divisão possível, não como '
                       f'limites firmes.')
    for nome, valor in reducao.items():
        if np.isfinite(valor) and valor < 0.10 and k_final > 1:
            alertas.append(f'As zonas quase não separam a camada "{nome}" (explicam {100 * valor:.0f}% da variação '
                           f'dela): ela pesou pouco na divisão.')
    for a, b, r in repetidas:
        alertas.append(f'As camadas "{a}" e "{b}" andam juntas (correlação {r:.2f}): na prática a mesma informação entrou '
                       f'duas vezes e pesa em dobro. Considere tirar uma ou dar peso 0,5 a cada.')
    if area_do_perimetro and abs(desenhado - area_do_perimetro) / area_do_perimetro > 0.01:
        alertas.append(f'As zonas somam {desenhado:.1f} ha e o perímetro tem {area_do_perimetro:.1f} ha: alguma parte do '
                       f'talhão ficou sem zona ou a borda não encaixou. Confira o mapa.')
    if area_total and maior_desvio / area_total > 0.02:
        alertas.append(f'A suavização mudou a área de uma zona em {maior_desvio:.1f} ha em relação à grade: está larga para '
                       f'este talhão. Diminua --suavizar.')
    return {'zonas': zonas, 'grade': g, 'grade_de_zonas': grade_final, 'zona_do_ponto': zona_do_ponto,
            'tabela_k': [{'k': t['k'], 'silhueta': float(t['silhueta']), 'inercia': float(t['inercia'])} for t in tabela],
            'k_escolhido': escolhida['k'], 'k_automatico': c['k'] == 'auto', 'k_final': k_final,
            'silhueta': float(escolhida['silhueta']), 'silhueta_final': float(silhueta_final),
            'pca': {'componentes': comp['componentes'], 'explicada': comp['explicada'], 'cargas': comp['cargas'].tolist()},
            'reducao': reducao, 'correlacao': correlacao.tolist(), 'repetidas': repetidas,
            'etapas': {'pontos': n, 'minimo_de_pontos_por_classe': min_pontos, 'classes_absorvidas': absorvidas,
                       'fragmentos_reatribuidos': fragmentos, 'partes_fundidas': fusoes,
                       'partes_isoladas_abaixo_do_minimo': isoladas},
            'area_ha': area_total, 'area_dos_poligonos_ha': desenhado, 'area_do_perimetro_ha': area_do_perimetro,
            'area_da_grade_ha': area_da_grade, 'pixel': pixel, 'espacamento': espacamento,
            'suavizar': float(suavizar), 'ordenado_por': nomes[ordem_col], 'parametros': {k: c[k] for k in (
                'variancia_pca', 'k', 'k_min', 'k_max', 'area_minima', 'vizinhos', 'frag_total', 'frag_classe', 'max_iter',
                'semente', 'pesos', 'iteracoes', 'deslocamento')},
            'alertas': alertas}


def agrupamento_pct(fracao):
    return f'{100 * fracao:g}%'


def _area(aneis):
    """Área (m²) de uma área com anéis por paridade: o maior anel menos os que estão dentro dele."""
    areas = sorted((abs(vetor._area_com_sinal(np.asarray(a, float))) for a in aneis), reverse=True)
    return areas[0] - sum(areas[1:]) if areas else 0.0


if __name__ == '__main__':
    import sintetico

    ex = sintetico.talhao()
    nomes = ['argila_g_kg', 'prod_t_ha', 'altitude_m']
    X = np.column_stack([ex['colunas'][n] for n in nomes])
    xy = np.column_stack([ex['x'], ex['y']])
    area = [{'nome': 'Exemplo', 'aneis': [ex['perimetro_utm']]}]
    assert 14 < espacamento_tipico(xy) < 22 and espacamento_automatico(52 * 10000) == 10
    assert abs(_area(area[0]['aneis']) / 10000 - 52.4) < 1.0, _area(area[0]['aneis']) / 10000

    r = zonear(xy, X, nomes, area)
    certo = sintetico.acerto(r['zona_do_ponto'], ex['verdade'])
    print(f'k escolhido {r["k_escolhido"]} · zonas {r["k_final"]} · silhueta {r["silhueta"]:.2f} · acerto nas zonas '
          f'plantadas {100 * certo:.1f}% · etapas {r["etapas"]}')
    print('  silhueta por k:', [(t['k'], round(t['silhueta'], 3)) for t in r['tabela_k']])
    print('  zonas:', [(z['zona'], round(z['ha'], 1), z['partes'], round(z['estat']['argila_g_kg']['media'])) for z in r['zonas']])
    print('  redução de variância:', {k: round(v, 2) for k, v in r['reducao'].items()}, '· avisos:', len(r['alertas']))
    assert r['k_escolhido'] == 3 and r['k_final'] == 3, (r['k_escolhido'], r['k_final'])
    assert certo > 0.93, certo
    assert [z['zona'] for z in r['zonas']] == [1, 2, 3]
    medias = [z['estat']['argila_g_kg']['media'] for z in r['zonas']]
    assert medias == sorted(medias) and abs(medias[0] - 190) < 25 and abs(medias[2] - 450) < 25, medias
    assert abs(sum(z['ha'] for z in r['zonas']) - r['area_ha']) < 1e-6
    # as zonas cobrem o perímetro verdadeiro, sem sobra e sem falta
    assert abs(r['area_ha'] - r['area_do_perimetro_ha']) < 0.002 * r['area_do_perimetro_ha'], (r['area_ha'], r['area_do_perimetro_ha'])
    assert all(abs(z['ha'] - z['ha_na_grade']) < 0.02 * r['area_ha'] for z in r['zonas'])
    assert all(v > 0.5 for v in r['reducao'].values()) and all(z['rotulo'] for z in r['zonas'])
    assert not r['alertas'], r['alertas']

    # com k fixo em 6 e área mínima de 10%, grupos pequenos são absorvidos e o aviso aparece
    r6 = zonear(xy, X, nomes, area, {'k': 6})
    assert r6['k_escolhido'] == 6 and r6['k_final'] <= 6 and all(z['pct'] >= 9.5 for z in r6['zonas'])
    assert all(vetor.area_ha(p) >= 0.09 * r6['area_ha'] for z in r6['zonas'] for p in z['poligonos'])
    # uma camada de puro ruído é denunciada; duas camadas iguais também
    ruido = np.random.default_rng(1).normal(0, 1, len(xy))
    rr = zonear(xy, np.column_stack([X, ruido, X[:, 0] * 2 + 1]), nomes + ['ruido', 'argila_de_novo'], area, {'k': 3})
    assert any('"ruido"' in a for a in rr['alertas']) and any('andam juntas' in a for a in rr['alertas']), rr['alertas']
    # grade de pontos e agregação
    pts = grade_de_pontos(area, 50)
    assert 180 < len(pts) < 240 and dentro(area[0]['aneis'], pts).all()
    xm, Xm, vezes = agregar(xy, X, 60)
    assert len(xm) < len(xy) / 5 and vezes.sum() == len(xy) and abs(Xm[:, 0].mean() - X[:, 0].mean()) < 15
    print('zoneamento OK')
