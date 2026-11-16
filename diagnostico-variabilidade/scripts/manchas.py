"""As manchas: o talhão repartido em faixas da variável a explicar (baixo, médio
e alto, por padrão) e o que cada camada marca em cada faixa.

- As faixas saem de cortes: por padrão, quantis que dão áreas iguais; ou os
  valores que o usuário informar.
- Uma passada de filtro de maioria (3 × 3) tira células soltas, para a mancha
  ficar legível no mapa. Dá para desligar.
- O perfil é a média e o desvio de cada camada dentro de cada faixa, e a
  "separação": a diferença entre a faixa mais alta e a mais baixa, em desvios
  da camada. É descrição do que há em cada mancha, não a causa dela.

Teste embutido: python scripts/manchas.py
"""

import numpy as np
from scipy import ndimage

NOMES = {2: ['baixo', 'alto'], 3: ['baixo', 'médio', 'alto'], 4: ['muito baixo', 'baixo', 'alto', 'muito alto'],
         5: ['muito baixo', 'baixo', 'médio', 'alto', 'muito alto']}


def cortes_por_quantil(valores, n_faixas):
    """Cortes que deixam as faixas com o mesmo número de células."""
    if n_faixas not in NOMES:
        raise ValueError('o número de faixas vai de 2 a 5')
    v = np.asarray(valores, float)
    cortes = [float(np.quantile(v, k / n_faixas)) for k in range(1, n_faixas)]
    if len(set(cortes)) != len(cortes):
        raise ValueError('a variável tem valores repetidos demais para esse número de faixas: use menos faixas ou informe os cortes')
    return cortes


def classificar(alvo, valida, cortes):
    """Faixa de cada célula válida (0 = a mais baixa); -1 fora."""
    faixas = np.full(alvo.shape, -1, dtype=np.int32)
    faixas[valida] = np.searchsorted(np.asarray(cortes, float), alvo[valida], side='right')
    return faixas


def filtro_de_maioria(faixas, n_faixas):
    """Uma passada 3 × 3: a célula fica com a faixa mais comum entre ela e as vizinhas (empate: fica como está)."""
    valida = faixas >= 0
    contagem = np.stack([ndimage.uniform_filter((faixas == k).astype(float), size=3, mode='constant') for k in range(n_faixas)])
    melhor = contagem.argmax(axis=0)
    propria = np.take_along_axis(contagem, np.clip(faixas, 0, n_faixas - 1)[None], axis=0)[0]
    troca = valida & (contagem.max(axis=0) > propria + 1e-9)
    saida = faixas.copy()
    saida[troca] = melhor[troca]
    return saida


def partes(faixas, n_faixas, celula, area_minima_ha):
    """Para cada faixa: quantas manchas (pedaços contíguos) têm a área mínima e o tamanho da maior, em ha."""
    ha = celula * celula / 10000.0
    saida = []
    for k in range(n_faixas):
        rot, n = ndimage.label(faixas == k, structure=np.ones((3, 3)))
        tamanhos = np.bincount(rot.ravel())[1:] * ha if n else np.array([])
        saida.append({'manchas': int((tamanhos >= area_minima_ha).sum()), 'pedacos': int(n),
                      'maior_ha': float(tamanhos.max()) if n else 0.0})
    return saida


def perfil(faixas, n_faixas, alvo, numericas, categoricas, celula):
    """O que há em cada faixa. numericas = {nome: malha}; categoricas = {nome: (rótulos, nomes das classes)}."""
    ha = celula * celula / 10000.0
    valida = faixas >= 0
    total = int(valida.sum())
    linhas = []
    for k in range(n_faixas):
        m = faixas == k
        n = int(m.sum())
        linha = {'faixa': NOMES[n_faixas][k], 'celulas': n, 'area_ha': n * ha, 'area_pct': 100.0 * n / total if total else 0.0,
                 'alvo_media': float(alvo[m].mean()) if n else None, 'alvo_minimo': float(alvo[m].min()) if n else None,
                 'alvo_maximo': float(alvo[m].max()) if n else None, 'camadas': {}, 'classes': {}}
        for nome, malha in numericas.items():
            linha['camadas'][nome] = {'media': float(malha[m].mean()) if n else None, 'desvio': float(malha[m].std()) if n else None}
        for nome, (rot, nomes) in categoricas.items():
            linha['classes'][nome] = {c: (100.0 * float((rot[m] == i).sum()) / n if n else 0.0) for i, c in enumerate(nomes)}
        linhas.append(linha)
    separacao = {}
    baixo, alto = faixas == 0, faixas == n_faixas - 1
    for nome, malha in numericas.items():
        desvio = float(malha[valida].std())
        separacao[nome] = None if desvio <= 0 or not baixo.any() or not alto.any() else \
            float((malha[alto].mean() - malha[baixo].mean()) / desvio)
    return {'faixas': linhas, 'separacao': separacao}


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    ny, nx = 30, 40
    yy, xx = np.mgrid[0:ny, 0:nx]
    valida = np.ones((ny, nx), dtype=bool)
    valida[:, :2] = False
    alvo = xx.astype(float)                                   # cresce para o leste
    cortes = cortes_por_quantil(alvo[valida], 3)
    faixas = classificar(alvo, valida, cortes)
    contagem = [int((faixas == k).sum()) for k in range(3)]
    assert sum(contagem) == int(valida.sum()) and max(contagem) - min(contagem) <= ny, contagem
    assert (faixas[:, :2] == -1).all() and faixas[0, 2] == 0 and faixas[0, -1] == 2

    # célula solta some no filtro de maioria; borda entre faixas fica
    sujo = faixas.copy()
    sujo[10, 5] = 2
    limpo = filtro_de_maioria(sujo, 3)
    assert limpo[10, 5] == 0 and (limpo[:, :2] == -1).all()
    assert (filtro_de_maioria(faixas, 3) == faixas).all()

    p = partes(sujo, 3, 10.0, 0.5)
    assert p[2]['pedacos'] == 2 and p[2]['manchas'] == 1 and p[0]['manchas'] == 1
    assert abs(p[0]['maior_ha'] - (contagem[0] - 1) * 0.01) < 1e-9

    acompanha = 2.0 * xx + 5                                   # sobe junto com o alvo
    contra = -1.0 * xx                                        # desce
    alheia = (yy % 2).astype(float)                           # não tem a ver
    rot = (xx >= 21).astype(np.int32)
    r = perfil(faixas, 3, alvo, {'acompanha': acompanha, 'contra': contra, 'alheia': alheia}, {'lado': (rot, ['oeste', 'leste'])}, 10.0)
    f = r['faixas']
    assert [x['faixa'] for x in f] == ['baixo', 'médio', 'alto'] and abs(sum(x['area_pct'] for x in f) - 100) < 1e-9
    assert f[0]['camadas']['acompanha']['media'] < f[1]['camadas']['acompanha']['media'] < f[2]['camadas']['acompanha']['media']
    assert r['separacao']['acompanha'] > 2 and r['separacao']['contra'] < -2 and abs(r['separacao']['alheia']) < 0.05
    assert f[0]['classes']['lado']['oeste'] == 100.0 and f[2]['classes']['lado']['leste'] == 100.0
    assert abs(f[0]['area_ha'] - contagem[0] * 0.01) < 1e-9

    assert classificar(alvo, valida, [10.0, 30.0])[0, 10] == 1          # cortes informados: o valor do corte vai para cima
    for ruim in (lambda: cortes_por_quantil(alvo[valida], 7), lambda: cortes_por_quantil(np.r_[np.zeros(90), np.ones(10)], 3)):
        try:
            ruim()
        except ValueError:
            pass
        else:
            raise AssertionError('devia recusar')
    print('manchas OK (faixas por quantil, filtro de maioria, pedaços contíguos, perfil e separação)')


if __name__ == '__main__':
    _autoteste()
