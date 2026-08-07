"""Krigagem ordinária com seleção automática de modelo de semivariograma.

Fluxo: semivariograma experimental → ajuste dos TRÊS modelos (exponencial,
esférico, gaussiano) por mínimos quadrados ponderados (pesos de Cressie,
Np/h²) → validação cruzada leave-one-out com cada modelo → vence o menor
RMSE. A interpolação final usa o vencedor em grade regular (pixel definido
pelo chamador; a skill usa 5 m).
"""

import numpy as np
from scipy.linalg import lu_factor, lu_solve


# ---------------------------------------------------------------- modelos
# Convenção de alcance PRÁTICO (a = distância onde γ ≈ 95% do patamar) nos
# três modelos, para que os alcances sejam comparáveis entre si.

def _exponencial(h, c0, c, a):
    return c0 + c * (1 - np.exp(-3 * h / a))


def _esferico(h, c0, c, a):
    hr = np.minimum(h / a, 1.0)
    return c0 + c * (1.5 * hr - 0.5 * hr**3)


def _gaussiano(h, c0, c, a):
    return c0 + c * (1 - np.exp(-3 * (h / a) ** 2))


MODELOS = {'exponencial': _exponencial, 'esferico': _esferico, 'gaussiano': _gaussiano}


def _gamma(nome, params):
    """γ(h) com γ(0) = 0 (a pepita é descontinuidade, não vale na origem)."""
    c0, c, a = params
    funcao = MODELOS[nome]

    def g(h):
        h = np.asarray(h, dtype=float)
        out = funcao(h, c0, c, a)
        return np.where(h <= 0, 0.0, out)

    return g


# ---------------------------------------------------------------- variograma

def variograma_experimental(x, y, z, n_lags=12, frac_corte=0.5):
    """Semivariograma experimental em classes de distância.

    Devolve (h_medio, gamma, n_pares) por classe (classes vazias caem fora).
    Corte em frac_corte × distância máxima (além disso há poucos pares e o
    variograma vira ruído).
    """
    x, y, z = (np.asarray(v, dtype=float) for v in (x, y, z))
    iu = np.triu_indices(len(x), k=1)
    h = np.hypot(x[iu[0]] - x[iu[1]], y[iu[0]] - y[iu[1]])
    g = 0.5 * (z[iu[0]] - z[iu[1]]) ** 2

    corte = h.max() * frac_corte
    validos = (h > 0) & (h <= corte)
    h, g = h[validos], g[validos]
    bordas = np.linspace(0, corte, n_lags + 1)
    classe = np.clip(np.digitize(h, bordas) - 1, 0, n_lags - 1)

    hm, gm, npares = [], [], []
    for i in range(n_lags):
        sel = classe == i
        if sel.sum() >= 2:
            hm.append(h[sel].mean())
            gm.append(g[sel].mean())
            npares.append(int(sel.sum()))
    return np.array(hm), np.array(gm), np.array(npares)


def ajustar_modelo(nome, hm, gm, npares, corte):
    """Ajusta (c0, c, a) por mínimos quadrados ponderados (Cressie: Np/h²).

    O alcance é varrido numa grade (robusto — sem depender de convergência de
    otimizador); para cada alcance, c0 e c saem de um sistema linear 2×2 com
    restrição de não-negatividade. Devolve (params, sse_ponderado).
    """
    funcao = MODELOS[nome]
    pesos = npares / np.maximum(hm, 1e-9) ** 2
    melhores = (None, np.inf)
    for a in np.geomspace(max(corte / 60, 1e-3), corte * 2, 80):
        s = funcao(hm, 0.0, 1.0, a)  # forma do modelo com c=1, c0=0
        # min Σ w (gm − c0 − c·s)² → normal equations 2×2
        w = pesos
        m11, m12, m22 = w.sum(), (w * s).sum(), (w * s * s).sum()
        b1, b2 = (w * gm).sum(), (w * gm * s).sum()
        det = m11 * m22 - m12 * m12
        if abs(det) < 1e-12:
            continue
        c0 = (b1 * m22 - b2 * m12) / det
        c = (m11 * b2 - m12 * b1) / det
        if c0 < 0:  # pepita não pode ser negativa: reestima só o patamar
            c0 = 0.0
            c = b2 / m22 if m22 > 0 else 0.0
        if c <= 0:  # sem estrutura neste alcance
            c = 1e-12
            c0 = b1 / m11
        sse = float((w * (gm - c0 - c * s) ** 2).sum())
        if sse < melhores[1]:
            melhores = ((float(c0), float(c), float(a)), sse)
    return melhores


def _matriz_aumentada(x, y, g):
    n = len(x)
    a = np.empty((n + 1, n + 1))
    a[:n, :n] = g(np.hypot(x[:, None] - x[None, :], y[:, None] - y[None, :]))
    a[:n, n] = 1.0
    a[n, :n] = 1.0
    a[n, n] = 0.0
    return a


def validacao_loo(x, y, z, nome, params):
    """Leave-one-out EXATO pelo atalho de Dubrule (1983): inverte a matriz
    aumentada UMA vez; o erro de cada ponto sai da diagonal da inversa —
    e_i = −[W·z̃]_i / W_ii, com W = A⁻¹ e z̃ = [z; 0]. O(n³) em vez de O(n⁴)
    do loop ingênuo (447 pontos: décimos de segundo em vez de minutos).
    Devolve (rmse, me)."""
    x, y, z = (np.asarray(v, dtype=float) for v in (x, y, z))
    n = len(x)
    g = _gamma(nome, params)
    try:
        w = np.linalg.inv(_matriz_aumentada(x, y, g))
    except np.linalg.LinAlgError:
        return _validacao_loo_ingenua(x, y, z, nome, params)
    yv = w @ np.append(z, 0.0)
    diag = np.diag(w)[:n]
    erros = -yv[:n] / diag
    erros = erros[np.isfinite(erros)]
    return float(np.sqrt(np.mean(erros**2))), float(np.mean(erros))


def _validacao_loo_ingenua(x, y, z, nome, params):
    """Referência O(n⁴) — usada no teste embutido p/ validar o atalho."""
    x, y, z = (np.asarray(v, dtype=float) for v in (x, y, z))
    n = len(x)
    g = _gamma(nome, params)
    gamma_cheia = g(np.hypot(x[:, None] - x[None, :], y[:, None] - y[None, :]))

    erros = np.empty(n)
    idx = np.arange(n)
    for i in range(n):
        outros = idx[idx != i]
        m = len(outros)
        a = np.empty((m + 1, m + 1))
        a[:m, :m] = gamma_cheia[np.ix_(outros, outros)]
        a[:m, m] = 1.0
        a[m, :m] = 1.0
        a[m, m] = 0.0
        b = np.append(gamma_cheia[outros, i], 1.0)
        try:
            lam = np.linalg.solve(a, b)
        except np.linalg.LinAlgError:
            erros[i] = np.nan
            continue
        erros[i] = float(lam[:m] @ z[outros]) - z[i]
    erros = erros[np.isfinite(erros)]
    return float(np.sqrt(np.mean(erros**2))), float(np.mean(erros))


def escolher_modelo(x, y, z, n_lags=12):
    """Ajusta os três modelos e escolhe o de menor RMSE na validação LOO.

    Devolve dict: variograma experimental, os 3 ajustes com métricas, o nome
    do vencedor e diagnósticos (razão pepita/patamar — classes de Cambardella).
    """
    hm, gm, npares = variograma_experimental(x, y, z, n_lags=n_lags)
    if len(hm) < 4:
        raise ValueError('pontos insuficientes para o semivariograma (aumente a malha)')
    corte = float(hm.max())

    resultado = {'variograma': {'h': hm.tolist(), 'gamma': gm.tolist(),
                                'pares': npares.tolist()},
                 'modelos': {}}
    for nome in MODELOS:
        params, sse = ajustar_modelo(nome, hm, gm, npares, corte)
        rmse, me = validacao_loo(x, y, z, nome, params)
        c0, c, a = params
        resultado['modelos'][nome] = {
            'pepita': c0, 'patamar_parcial': c, 'alcance_m': a,
            'sse_ajuste': sse, 'rmse_loo': rmse, 'erro_medio_loo': me,
        }

    vencedor = min(resultado['modelos'], key=lambda k: resultado['modelos'][k]['rmse_loo'])
    resultado['vencedor'] = vencedor

    c0, c = (resultado['modelos'][vencedor][k] for k in ('pepita', 'patamar_parcial'))
    razao = c0 / (c0 + c) if (c0 + c) > 0 else 1.0
    resultado['razao_pepita'] = round(float(razao), 3)
    resultado['dependencia_espacial'] = (
        'forte' if razao <= 0.25 else 'moderada' if razao <= 0.75 else 'fraca'
    )
    var_z = float(np.var(z))
    resultado['estrutura_fraca'] = bool(c < 0.05 * var_z)  # quase pepita pura
    return resultado


# ---------------------------------------------------------------- interpolação

def krigar(x, y, z, nome, params, xc, yc, mascara, bloco=20000, progresso=None):
    """Krigagem ordinária nos centros de célula onde mascara=True.

    O sistema (n+1)×(n+1) é fatorado UMA vez (LU) e resolvido em blocos de
    células. `progresso` (callable, recebe fração 0–1) dá sinal de vida em
    malhas grandes. Devolve (malha_predita, malha_variancia) com NaN fora
    da máscara.
    """
    x, y, z = (np.asarray(v, dtype=float) for v in (x, y, z))
    n = len(x)
    g = _gamma(nome, params)
    fator = lu_factor(_matriz_aumentada(x, y, g))

    ny, nx = mascara.shape
    gx, gy = np.meshgrid(np.asarray(xc, float), np.asarray(yc, float))
    alvos = np.flatnonzero(mascara.ravel())
    ax, ay = gx.ravel()[alvos], gy.ravel()[alvos]

    pred = np.full(ny * nx, np.nan)
    varkrig = np.full(ny * nx, np.nan)
    for ini in range(0, len(alvos), bloco):
        fim = min(ini + bloco, len(alvos))
        d = np.hypot(x[:, None] - ax[None, ini:fim], y[:, None] - ay[None, ini:fim])
        b = np.vstack([g(d), np.ones((1, fim - ini))])
        lam = lu_solve(fator, b)
        pred[alvos[ini:fim]] = lam[:n].T @ z
        varkrig[alvos[ini:fim]] = np.einsum('ij,ij->j', lam[:n], b[:n]) + lam[n]
        if progresso:
            progresso(fim / len(alvos))
    return pred.reshape(ny, nx), varkrig.reshape(ny, nx)


def krigar_local(x, y, z, nome, params, xc, yc, mascara, lado_tile=64,
                 max_pontos=96, buffer_m=None, progresso=None):
    """Krigagem ordinária com VIZINHANÇA MÓVEL por ladrilho — p/ malhas grandes.

    A grade é varrida em ladrilhos de lado_tile×lado_tile células; cada
    ladrilho usa só os pontos num raio de buffer_m do seu bbox (no máximo
    max_pontos, os mais próximos do centro). Com buffer na casa do alcance do
    variograma, os pesos dos pontos excluídos seriam desprezíveis — o
    resultado é praticamente o da krigagem global, com custo ~n_local²/n².
    Devolve (malha_predita, malha_variancia) como krigar().
    """
    import math

    x, y, z = (np.asarray(v, dtype=float) for v in (x, y, z))
    n = len(x)
    g = _gamma(nome, params)
    xc = np.asarray(xc, float)
    yc = np.asarray(yc, float)
    ny, nx = mascara.shape

    if buffer_m is None:
        # espaçamento médio da malha (raiz da área por ponto) e alcance mandam
        area = max((x.max() - x.min()) * (y.max() - y.min()), 1.0)
        espacamento = math.sqrt(area / n)
        buffer_m = max(0.75 * params[2], 3 * espacamento)

    pred = np.full(ny * nx, np.nan)
    varkrig = np.full(ny * nx, np.nan)
    indice = np.arange(ny * nx).reshape(ny, nx)
    total = int(mascara.sum())
    feitos = 0

    for i0 in range(0, ny, lado_tile):
        for j0 in range(0, nx, lado_tile):
            sub = mascara[i0:i0 + lado_tile, j0:j0 + lado_tile]
            m_alvos = int(sub.sum())
            if not m_alvos:
                continue
            xs = xc[j0:j0 + lado_tile]
            ys = yc[i0:i0 + lado_tile]
            cx, cy = xs.mean(), ys.mean()

            sel = ((x >= xs.min() - buffer_m) & (x <= xs.max() + buffer_m)
                   & (y >= ys.min() - buffer_m) & (y <= ys.max() + buffer_m))
            pts = np.flatnonzero(sel)
            if len(pts) < 8:  # ladrilho isolado: usa os mais próximos do centro
                pts = np.argsort(np.hypot(x - cx, y - cy))[:min(max(16, 8), n)]
            elif len(pts) > max_pontos:
                ordem = np.argsort(np.hypot(x[pts] - cx, y[pts] - cy))
                pts = pts[ordem[:max_pontos]]

            xl, yl, zl = x[pts], y[pts], z[pts]
            nl = len(pts)
            fator = lu_factor(_matriz_aumentada(xl, yl, g))

            gx, gy = np.meshgrid(xs, ys)
            dentro = sub.ravel()
            ax, ay = gx.ravel()[dentro], gy.ravel()[dentro]
            d = np.hypot(xl[:, None] - ax[None, :], yl[:, None] - ay[None, :])
            b = np.vstack([g(d), np.ones((1, m_alvos))])
            lam = lu_solve(fator, b)

            destino = indice[i0:i0 + lado_tile, j0:j0 + lado_tile].ravel()[dentro]
            pred[destino] = lam[:nl].T @ zl
            varkrig[destino] = np.einsum('ij,ij->j', lam[:nl], b[:nl]) + lam[nl]
            feitos += m_alvos
            if progresso:
                progresso(feitos / total)

    return pred.reshape(ny, nx), varkrig.reshape(ny, nx)


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


if __name__ == '__main__':
    # exemplo embutido: campo sintético suave + validação de que a krigagem
    # honra os dados (interpolador exato) e que o LOO produz RMSE < desvio-padrão
    rng = np.random.default_rng(42)
    n = 60
    x = rng.uniform(0, 500, n)
    y = rng.uniform(0, 400, n)
    z = 10 + 4 * np.sin(x / 120) + 3 * np.cos(y / 90) + rng.normal(0, 0.4, n)

    # o atalho de Dubrule tem que bater com o loop ingênuo (mesma matemática)
    hm, gm, npares = variograma_experimental(x, y, z)
    pr, _ = ajustar_modelo('esferico', hm, gm, npares, float(hm.max()))
    rapido = validacao_loo(x, y, z, 'esferico', pr)
    ingenuo = _validacao_loo_ingenua(x, y, z, 'esferico', pr)
    assert abs(rapido[0] - ingenuo[0]) < 1e-8 and abs(rapido[1] - ingenuo[1]) < 1e-8, \
        (rapido, ingenuo)
    print(f'LOO rápido ≡ ingênuo OK (rmse {rapido[0]:.6f})')

    resultado = escolher_modelo(x, y, z)
    print('vencedor:', resultado['vencedor'],
          '| dependência espacial:', resultado['dependencia_espacial'])
    for nome, m in resultado['modelos'].items():
        print(f"  {nome:12s} rmse_loo={m['rmse_loo']:.3f} alcance={m['alcance_m']:.0f} m "
              f"pepita={m['pepita']:.3f}")
    assert resultado['modelos'][resultado['vencedor']]['rmse_loo'] < np.std(z), \
        'LOO deveria bater a média'

    params = tuple(resultado['modelos'][resultado['vencedor']][k]
                   for k in ('pepita', 'patamar_parcial', 'alcance_m'))
    xc = np.arange(0, 500, 5.0) + 2.5
    yc = (np.arange(0, 400, 5.0) + 2.5)[::-1]
    mascara = np.ones((len(yc), len(xc)), dtype=bool)
    malha, variancia = krigar(x, y, z, resultado['vencedor'], params, xc, yc, mascara)
    assert np.isfinite(malha).all() and float(np.nanmean(variancia)) > 0
    # interpolador honra os dados: célula que contém um ponto fica perto do valor
    i = int(np.argmin(np.hypot(x - 250, y - 200)))
    lin = int((yc[0] - y[i]) // 5)
    col = int((x[i] - 0) // 5)
    print(f'no ponto mais central: z={z[i]:.2f} malha={malha[lin, col]:.2f}')
    assert abs(malha[lin, col] - z[i]) < 1.0

    # vizinhança móvel ≈ global (max_pontos apertado de propósito p/ exercitar
    # a seleção; a diferença tem que ser marginal perto do desvio dos dados)
    local, _ = krigar_local(x, y, z, resultado['vencedor'], params, xc, yc,
                            mascara, lado_tile=24, max_pontos=24)
    dif = float(np.sqrt(np.nanmean((local - malha) ** 2)))
    assert dif < 0.05 * np.std(z), dif
    print(f'krigagem OK — malha {malha.shape} | local≈global (dif RMS {dif:.4f})')
