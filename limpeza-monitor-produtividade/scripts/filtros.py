"""Filtros de dado denso (monitor de colheita e sensores embarcados).

Funções puras sobre vetores do numpy, na ORDEM DO ARQUIVO (a ordem em que a
máquina gravou). Nada aqui lê arquivo nem decide parâmetro sozinho: quem chama
passa o número, e cada filtro devolve a máscara do que ele tiraria.

  passadas()             divide os pontos em passadas (tiros da máquina)
  rampa()                como o valor entra e sai de cada passada, em média
  sugerir_pontas()       quantos pontos cortar no começo e no fim, pela rampa
  limites_globais()      limites estatísticos do talhão inteiro
  filtro_local()         cada ponto contra a mediana dos vizinhos
  raio_automatico()      raio que pega perto de 12 vizinhos

Teste embutido: python scripts/filtros.py
"""

import math
import warnings

import numpy as np
from scipy.spatial import cKDTree

DP_ROBUSTO = 1.4826  # MAD × 1,4826 = desvio-padrão, numa distribuição normal
PADRAO_K = {'mad': 3.0, 'dp': 3.0, 'iqr': 1.5, 'pct': 50.0}


# ------------------------------------------------------------------ passadas
def passadas(x, y, t=None, coluna=None, pausa=None, salto=None, curva=60.0, janela=3):
    """Número da passada de cada ponto. Uma passada nova começa quando:
      - a coluna de passada do arquivo muda (se houver);
      - o relógio para por mais de `pausa` segundos ou anda para trás;
      - a máquina salta mais de `salto` metros entre dois pontos seguidos;
      - o rumo vira mais de `curva` graus (manobra de cabeceira gravada).
    Sem `pausa` e `salto`, eles saem do próprio arquivo (4 × o intervalo e o
    passo típicos, com piso de 5 s e de 20 m). Devolve (ids, informações)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    info = {'passo_m': None, 'intervalo_s': None, 'pausa_s': None, 'salto_m': None}
    if n == 0:
        return np.zeros(0, dtype=int), info
    corte = np.zeros(n, dtype=bool)
    passo = np.hypot(np.diff(x), np.diff(y))
    anda = passo[np.isfinite(passo) & (passo > 0)]
    tipico = float(np.median(anda)) if len(anda) else 0.0
    if salto is None:
        salto = max(4 * tipico, 20.0)
    corte[1:] |= ~np.isfinite(passo) | (passo > salto)
    info.update(passo_m=tipico, salto_m=float(salto))
    if coluna is not None:
        coluna = np.asarray(coluna)
        corte[1:] |= coluna[1:] != coluna[:-1]
    if t is not None:
        dt = np.diff(np.asarray(t, float))
        corre = dt[np.isfinite(dt) & (dt > 0)]
        intervalo = float(np.median(corre)) if len(corre) else 1.0
        if pausa is None:
            pausa = max(4 * intervalo, 5.0)
        corte[1:] |= ~np.isfinite(dt) | (dt > pausa) | (dt < 0)
        info.update(intervalo_s=intervalo, pausa_s=float(pausa))
    w = janela
    if curva and n > 2 * w + 1:
        # rumo de chegada (i-w → i) contra rumo de saída (i → i+w), só onde não há corte dentro da janela
        ax_, ay_ = x[w:-w] - x[:-2 * w], y[w:-w] - y[:-2 * w]
        bx_, by_ = x[2 * w:] - x[w:-w], y[2 * w:] - y[w:-w]
        la, lb = np.hypot(ax_, ay_), np.hypot(bx_, by_)
        cosseno = (ax_ * bx_ + ay_ * by_) / np.maximum(la * lb, 1e-9)
        andou = max(1.0, 1.5 * tipico)
        acumulado = np.cumsum(corte)
        livre = acumulado[2 * w:] == acumulado[:-2 * w]
        vira = livre & (cosseno < math.cos(math.radians(curva))) & (la > andou) & (lb > andou)
        corte[w:-w] |= vira
    ids = np.cumsum(corte)
    info['passadas'] = int(ids[-1]) + 1
    return ids, info


def posicao_na_passada(ids):
    """(quantos pontos desde o começo da passada, quantos até o fim), por ponto."""
    ids = np.asarray(ids)
    n = len(ids)
    if n == 0:
        return np.zeros(0, int), np.zeros(0, int)
    i = np.arange(n)
    comeca = np.r_[True, ids[1:] != ids[:-1]]
    termina = np.r_[ids[1:] != ids[:-1], True]
    primeiro = np.maximum.accumulate(np.where(comeca, i, 0))
    ultimo = np.minimum.accumulate(np.where(termina, i, n - 1)[::-1])[::-1]
    return i - primeiro, ultimo - i


def tamanho_da_passada(ids):
    do_inicio, do_fim = posicao_na_passada(ids)
    return do_inicio + do_fim + 1


def rampa(valor, ids, n=15):
    """Como o valor entra e sai das passadas: mediana, entre as passadas longas, de
    valor ÷ referência, nas n primeiras e nas n últimas posições. A referência de cada ponta é
    a mediana dos n pontos logo depois dela (o trecho vizinho, já em regime), e não a passada
    inteira: assim uma mancha no meio do talhão não entorta a medida.
    Devolve (entrada[n], saida[n], passadas usadas); saida[0] é o último ponto."""
    valor = np.asarray(valor, float)
    limites = np.flatnonzero(np.r_[True, ids[1:] != ids[:-1], True])
    entradas, saidas = [], []
    for a, b in zip(limites[:-1], limites[1:]):
        if b - a < 4 * n:
            continue
        trecho = valor[a:b]
        ref_ini, ref_fim = np.nanmedian(trecho[n:2 * n]), np.nanmedian(trecho[-2 * n:-n])
        if not (np.isfinite(ref_ini) and np.isfinite(ref_fim)) or ref_ini <= 0 or ref_fim <= 0:
            continue
        entradas.append(trecho[:n] / ref_ini)
        saidas.append(trecho[::-1][:n] / ref_fim)
    if len(entradas) < 5:
        return None, None, len(entradas)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        return np.nanmedian(entradas, axis=0), np.nanmedian(saidas, axis=0), len(entradas)


def sugerir_pontas(curva, alvo=0.9):
    """Quantos pontos cortar numa ponta: até o valor se firmar em pelo menos `alvo` do miolo
    (dois pontos seguidos). None se a curva não existe ou nunca chega lá."""
    if curva is None:
        return None
    for k in range(len(curva) - 1):
        if curva[k] >= alvo and curva[k + 1] >= alvo:
            return k
    return None


# ------------------------------------------------------------------ filtros simples
def duplicados(x, y, casas=2):
    """Pontos que repetem a posição de um ponto anterior (mesma coordenada até o centímetro)."""
    chave = np.round(np.column_stack([x, y]), casas)
    _, primeiro = np.unique(chave, axis=0, return_index=True)
    repetido = np.ones(len(chave), dtype=bool)
    repetido[primeiro] = False
    return repetido


def fora_da_faixa(v, minimo=None, maximo=None, minimo_incluso=True):
    v = np.asarray(v, float)
    fora = ~np.isfinite(v)
    if minimo is not None:
        fora |= (v < minimo) if minimo_incluso else (v <= minimo)
    if maximo is not None:
        fora |= v > maximo
    return fora


def variacao_brusca(velocidade, ids, limite):
    """Velocidade que muda mais que `limite` (fração) de um ponto para o seguinte, na mesma passada."""
    v = np.asarray(velocidade, float)
    brusca = np.zeros(len(v), dtype=bool)
    with np.errstate(divide='ignore', invalid='ignore'):
        mudou = np.abs(v[1:] - v[:-1]) / np.abs(v[:-1])
    brusca[1:] = (ids[1:] == ids[:-1]) & np.isfinite(mudou) & (mudou > limite)
    return brusca


def largura_cheia(largura):
    """A largura de trabalho mais comum do arquivo (a plataforma inteira)."""
    v = np.asarray(largura, float)
    v = np.round(v[np.isfinite(v) & (v > 0)], 2)
    if not len(v):
        return None
    valores, vezes = np.unique(v, return_counts=True)
    return float(valores[np.argmax(vezes)])


# ------------------------------------------------------------------ estatísticos
def limites_globais(v, metodo='mad', k=None):
    """Limites do talhão inteiro. mad: mediana ± k desvios robustos; dp: média ± k desvios;
    iqr: quartis ± k × distância interquartil; pct: mediana ± k %."""
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if k is None:
        k = PADRAO_K[metodo]
    mediana = float(np.median(v))
    if metodo == 'mad':
        d = DP_ROBUSTO * float(np.median(np.abs(v - mediana)))
        return mediana - k * d, mediana + k * d
    if metodo == 'dp':
        m, d = float(v.mean()), float(v.std(ddof=1))
        return m - k * d, m + k * d
    if metodo == 'iqr':
        q1, q3 = np.percentile(v, [25, 75])
        return float(q1 - k * (q3 - q1)), float(q3 + k * (q3 - q1))
    if metodo == 'pct':
        folga = abs(mediana) * k / 100
        return mediana - folga, mediana + folga
    raise ValueError(f'método global desconhecido: {metodo}')


def raio_automatico(xy, vizinhos=12, amostra=20000):
    """Raio (m) que alcança perto de `vizinhos` pontos: mediana da distância ao 12º vizinho,
    arredondada para cima em número redondo."""
    xy = np.asarray(xy, float)
    if len(xy) <= vizinhos:
        return None
    arvore = cKDTree(xy)
    passo = max(1, len(xy) // amostra)
    d, _ = arvore.query(xy[::passo], k=vizinhos + 1)
    r = 1.1 * float(np.median(d[:, -1]))  # folga: o ponto de borda tem vizinho de um lado só
    base = 10 ** math.floor(math.log10(r))
    return next(base * m for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10) if base * m >= r)


def filtro_local(xy, v, raio, limite, metodo='pct', min_viz=4, k_max=40, bloco=40000, piso=None):
    """Cada ponto contra a mediana dos vizinhos dentro do raio.
      pct: sai o ponto que difere mais que `limite` % da mediana local;
      mad: sai o ponto a mais de `limite` desvios robustos locais da mediana local.
    Ponto com menos de `min_viz` vizinhos não é julgado. Devolve (remover, sem_vizinhos, mediana_local)."""
    xy, v = np.asarray(xy, float), np.asarray(v, float)
    n = len(v)
    remover = np.zeros(n, dtype=bool)
    sozinho = np.ones(n, dtype=bool)
    mediana = np.full(n, np.nan)
    if n < 2:
        return remover, sozinho, mediana
    if piso is None:  # desvio local mínimo no método mad: 10% do desvio robusto do conjunto
        piso = 0.1 * DP_ROBUSTO * float(np.median(np.abs(v - np.median(v)))) or 1e-9
    arvore = cKDTree(xy)
    v_ext = np.r_[v, np.nan]  # o índice n (vizinho que não existe) vira nan
    k = min(k_max + 1, n)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        for ini in range(0, n, bloco):
            fim = min(ini + bloco, n)
            _, j = arvore.query(xy[ini:fim], k=k, distance_upper_bound=raio)
            viz = v_ext[j[:, 1:]]  # a coluna 0 é o próprio ponto
            quantos = np.isfinite(viz).sum(axis=1)
            med = np.nanmedian(viz, axis=1)
            if metodo == 'pct':
                folga = np.abs(med) * limite / 100
            elif metodo == 'mad':
                desvio = DP_ROBUSTO * np.nanmedian(np.abs(viz - med[:, None]), axis=1)
                folga = limite * np.maximum(desvio, piso)
            else:
                raise ValueError(f'método local desconhecido: {metodo}')
            julga = quantos >= min_viz
            remover[ini:fim] = julga & (np.abs(v[ini:fim] - med) > folga)
            sozinho[ini:fim] = ~julga
            mediana[ini:fim] = med
    return remover, sozinho, mediana


if __name__ == '__main__':
    # duas passadas de ida e volta, 1 ponto por segundo, com uma pausa entre elas
    xs = np.r_[np.arange(0, 60, 2.0), np.arange(58, -2, -2.0)]
    ys = np.r_[np.zeros(30), np.full(30, 9.0)]
    ts = np.r_[np.arange(30), np.arange(30) + 60.0]
    ids, info = passadas(xs, ys, ts)
    assert info['passadas'] == 2 and ids[29] == 0 and ids[30] == 1, info
    assert abs(info['passo_m'] - 2) < 1e-9 and info['intervalo_s'] == 1.0
    # sem relógio, o salto de 9 m não corta (menor que 20 m), mas a virada de 180° corta
    ids2, info2 = passadas(xs, ys)
    assert info2['passadas'] >= 2 and ids2[0] != ids2[-1], info2
    ini, fim = posicao_na_passada(ids)
    assert ini[:3].tolist() == [0, 1, 2] and fim[27:30].tolist() == [2, 1, 0] and ini[30] == 0
    assert tamanho_da_passada(ids)[0] == 30

    # rampa: 40 passadas de 60 pontos, o valor sobe nos 4 primeiros pontos
    gerador = np.random.default_rng(1)
    idsr = np.repeat(np.arange(40), 60)
    val = 4 + 0.05 * gerador.standard_normal(40 * 60)
    for kk, fator in enumerate((0.2, 0.45, 0.7, 0.85)):
        val[kk::60] *= fator
    entrada, saida, usadas = rampa(val, idsr)
    assert usadas == 40 and sugerir_pontas(entrada) == 4 and sugerir_pontas(saida) == 0, (entrada[:6], saida[:3])
    assert sugerir_pontas(None) is None

    assert duplicados([0, 1, 0, 2], [0, 1, 0, 2]).tolist() == [False, False, True, False]
    assert fora_da_faixa([0, 1, np.nan, 9], 0, 5, minimo_incluso=False).tolist() == [True, False, True, True]
    assert variacao_brusca([5, 5, 8, 8], np.zeros(4, int), 0.3).tolist() == [False, False, True, False]
    assert largura_cheia([9.1, 9.1, 9.1, 4.5, 0]) == 9.1

    base = np.r_[gerador.normal(4, 0.3, 2000), 12.0, 0.2]
    for metodo in ('mad', 'dp', 'iqr'):
        lo, hi = limites_globais(base, metodo)
        assert lo < 3.3 and 4.7 < hi < 12 and lo > 0.2, (metodo, lo, hi)
    assert limites_globais([10, 10, 10, 10], 'pct', 50) == (5.0, 15.0)

    # local: grade de 30 × 30 com um ponto 60% acima dos vizinhos
    gx, gy = np.meshgrid(np.arange(30) * 5.0, np.arange(30) * 5.0)
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    campo = 4 + 0.002 * pts[:, 0] + 0.02 * gerador.standard_normal(len(pts))
    campo[455] *= 1.6
    r = raio_automatico(pts)
    assert 8 <= r <= 15, r
    for metodo, limite in (('pct', 30), ('mad', 6)):
        tira, sozinho, _ = filtro_local(pts, campo, r, limite, metodo)
        assert tira.sum() == 1 and tira[455] and not sozinho.any(), (metodo, tira.sum())
    tira, sozinho, _ = filtro_local(pts[:3] * 100, campo[:3], 10, 30)
    assert not tira.any() and sozinho.all()
    print('filtros OK')
