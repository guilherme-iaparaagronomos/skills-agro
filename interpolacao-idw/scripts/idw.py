"""IDW (inverso da distância ponderada) com potência escolhida por validação cruzada.

Cada célula recebe a média dos k pontos mais próximos, com peso 1/d^p. A
potência p não é chute: testam-se várias e vence a de menor RMSE na validação
cruzada leave-one-out (cada amostra é retirada e predita pelas vizinhas). O
mesmo teste mede quanto o IDW ganha de "usar a média do talhão em todo lugar"
— se não ganha, a malha não captou padrão espacial e o mapa precisa dizer isso.

Propriedades que o usuário deve conhecer (references/idw.md):
- interpolador EXATO: no ponto amostrado o mapa devolve o valor da amostra;
- nunca sai do intervalo [mínimo, máximo] das amostras vizinhas;
- potência alta ou malha rala produzem "olhos de boi" em volta dos pontos.
"""

import numpy as np
from scipy.spatial import cKDTree

POTENCIAS = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)


def remover_duplicados(x, y, z, tolerancia=0.01):
    """Pontos na MESMA coordenada (±tolerância em m) viram um só (média de z)."""
    x, y, z = (np.asarray(v, dtype=float) for v in (x, y, z))
    chaves = {}
    for i in range(len(x)):
        k = (round(x[i] / tolerancia), round(y[i] / tolerancia))
        chaves.setdefault(k, []).append(i)
    xs, ys, zs = [], [], []
    for grupo in chaves.values():
        xs.append(x[grupo].mean())
        ys.append(y[grupo].mean())
        zs.append(z[grupo].mean())
    return np.array(xs), np.array(ys), np.array(zs), len(x) - len(xs)


def _media_ponderada(dist, valores, potencia):
    """dist/valores [m, k] → predição [m]. Distância infinita = vizinho ausente
    (peso 0); distância zero = o próprio ponto amostrado (devolve o valor dele)."""
    with np.errstate(divide='ignore'):
        pesos = 1.0 / np.power(dist, potencia)
    exato = dist == 0
    linhas_exatas = exato.any(axis=1)
    if linhas_exatas.any():
        pesos[linhas_exatas] = exato[linhas_exatas].astype(float)
    soma = pesos.sum(axis=1)
    with np.errstate(invalid='ignore', divide='ignore'):
        pred = (pesos * valores).sum(axis=1) / soma
    pred[soma == 0] = np.nan  # nenhum vizinho dentro do raio
    return pred


def _consultar(arvore, xy, k, raio):
    dist, idx = arvore.query(xy, k=k, distance_upper_bound=raio if raio else np.inf)
    if k == 1:
        dist, idx = dist[:, None], idx[:, None]
    ausente = ~np.isfinite(dist)
    return dist, np.where(ausente, 0, idx)


def validacao_loo(x, y, z, potencia, vizinhos=12, raio=None):
    """Leave-one-out: cada amostra predita pelas k vizinhas (sem ela mesma).
    Devolve (rmse, erro_medio, n_preditos)."""
    xy = np.column_stack([x, y])
    n = len(z)
    k = min(vizinhos + 1, n)
    dist, idx = _consultar(cKDTree(xy), xy, k, raio)
    dist = dist.copy()
    dist[idx == np.arange(n)[:, None]] = np.inf  # tira a própria amostra
    pred = _media_ponderada(dist, z[idx], potencia)
    ok = np.isfinite(pred)
    erro = pred[ok] - z[ok]
    if not len(erro):
        return float('nan'), float('nan'), 0
    return float(np.sqrt(np.mean(erro ** 2))), float(np.mean(erro)), int(ok.sum())


def escolher_potencia(x, y, z, vizinhos=12, raio=None, potencias=POTENCIAS):
    """Testa as potências por LOO e compara com o preditor ingênuo (a média das
    outras amostras). Devolve o dicionário que vai para o relatório."""
    n = len(z)
    tabela = {}
    for p in potencias:
        rmse, me, n_ok = validacao_loo(x, y, z, p, vizinhos, raio)
        tabela[f'{p:g}'] = {'rmse_loo': rmse, 'erro_medio': me, 'n': n_ok}
    validas = {p: v for p, v in tabela.items() if np.isfinite(v['rmse_loo'])}
    if not validas:
        raise ValueError('validação cruzada sem predição — raio de busca pequeno demais?')
    vencedora = min(validas, key=lambda p: validas[p]['rmse_loo'])

    media_sem_i = (z.sum() - z) / (n - 1)
    rmse_media = float(np.sqrt(np.mean((media_sem_i - z) ** 2)))
    rmse = validas[vencedora]['rmse_loo']
    ganho = 1 - rmse / rmse_media if rmse_media > 0 else 0.0
    return {
        'potencias': tabela, 'vencedora': float(vencedora),
        'rmse_loo': rmse, 'rmse_da_media': rmse_media,
        'ganho_sobre_a_media': round(ganho, 3),
        # < 5% de ganho: o IDW não prevê melhor que a média do talhão
        'estrutura_fraca': bool(ganho < 0.05),
    }


def interpolar_grade(x, y, z, potencia, xc, yc, mascara, vizinhos=12, raio=None,
                     bloco=250000, progresso=None):
    """IDW nas células da máscara. Devolve a malha [ny, nx] (NaN fora)."""
    ny, nx = mascara.shape
    gx, gy = np.meshgrid(xc, yc)
    alvo = np.flatnonzero(mascara.ravel())
    centros = np.column_stack([gx.ravel()[alvo], gy.ravel()[alvo]])
    arvore = cKDTree(np.column_stack([x, y]))
    k = min(vizinhos, len(z))
    pred = np.full(ny * nx, np.nan)
    for ini in range(0, len(alvo), bloco):
        fim = min(ini + bloco, len(alvo))
        dist, idx = _consultar(arvore, centros[ini:fim], k, raio)
        pred[alvo[ini:fim]] = _media_ponderada(dist, z[idx], potencia)
        if progresso:
            progresso(fim / len(alvo))
    return pred.reshape(ny, nx)


if __name__ == '__main__':
    # exemplo embutido: campo sintético suave, 80 amostras
    rng = np.random.default_rng(42)
    n = 80
    x = rng.uniform(0, 600, n)
    y = rng.uniform(0, 500, n)
    z = 20 + 0.03 * x - 0.02 * y + 4 * np.sin(x / 90) + rng.normal(0, 0.4, n)

    escolha = escolher_potencia(x, y, z)
    assert escolha['rmse_loo'] < escolha['rmse_da_media'], escolha
    assert not escolha['estrutura_fraca']
    print(f"potência vencedora {escolha['vencedora']:g} · RMSE LOO {escolha['rmse_loo']:.3f} "
          f"× média {escolha['rmse_da_media']:.3f} · ganho {escolha['ganho_sobre_a_media']:.0%}")

    xc = np.arange(2.5, 600, 5.0)
    yc = np.arange(497.5, 0, -5.0)
    mascara = np.ones((len(yc), len(xc)), dtype=bool)
    mascara[:10, :10] = False
    malha = interpolar_grade(x, y, z, escolha['vencedora'], xc, yc, mascara)
    assert np.isnan(malha[0, 0]) and np.isfinite(malha[50, 50])
    # nunca sai do intervalo das amostras
    assert np.nanmin(malha) >= z.min() - 1e-9 and np.nanmax(malha) <= z.max() + 1e-9

    # interpolador exato: célula centrada numa amostra devolve o valor dela
    x2 = np.append(x, 302.5)
    y2 = np.append(y, 247.5)
    z2 = np.append(z, 99.0)
    malha2 = interpolar_grade(x2, y2, z2, 2.0, xc, yc, mascara)
    i, j = int(np.argmin(np.abs(yc - 247.5))), int(np.argmin(np.abs(xc - 302.5)))
    assert abs(malha2[i, j] - 99.0) < 1e-9, malha2[i, j]

    # ruído puro: o IDW não ganha da média e o diagnóstico acusa
    ruido = rng.normal(10, 1, n)
    fraca = escolher_potencia(x, y, ruido)
    assert fraca['estrutura_fraca'], fraca

    # raio pequeno demais deixa célula sem vizinho (NaN), sem quebrar
    curta = interpolar_grade(x, y, z, 2.0, xc, yc, mascara, raio=3.0)
    assert np.isnan(curta).sum() > np.isnan(malha).sum()
    _, _, zd, ndup = remover_duplicados([0, 0, 5], [0, 0, 5], [1, 3, 7])
    assert ndup == 1 and sorted(zd.tolist()) == [2.0, 7.0]
    print('idw OK: exato nas amostras, limitado ao intervalo, diagnóstico de estrutura fraca')
