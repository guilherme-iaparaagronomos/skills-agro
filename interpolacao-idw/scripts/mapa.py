"""Páginas da apostila: o mapa classificado de cada elemento, a capa e o resumo.

Cada página é uma folha A4 deitada com o mapa em classes, a legenda (classe,
faixa, área em ha e % da área), as estatísticas, a escala gráfica, o norte e a
fonte das classes. As mesmas figuras viram o PDF e o PNG do elemento e as
páginas da apostila.
"""

import textwrap

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.path import Path as Caminho  # noqa: E402

from classes import num_br, rotulos_de_faixa  # noqa: E402

A4_DEITADA = (11.69, 8.27)
TINTA = '#1f2933'
CINZA = '#6b7280'
LINHA = '#d1d5db'
RODAPE = 'agrônomo10X · OagronomIA'

_OTIMO_MEIO = ['#d73027', '#fdae61', '#1a9850', '#74add1', '#4575b4']


def cores_das_classes(n, sentido):
    """n cores para as classes: vermelho→verde (alto é bom), invertido (alto é
    ruim), ótimo no meio (pH) ou neutra (textura, classes livres)."""
    if n == 1:
        return ['#a6d96a']
    if sentido == 'otimo_meio' and n == 5:
        return list(_OTIMO_MEIO)
    if sentido == 'neutra':
        mapa = matplotlib.colormaps['YlOrBr']
        return [matplotlib.colors.to_hex(mapa(v)) for v in np.linspace(0.12, 0.88, n)]
    mapa = matplotlib.colormaps['RdYlGn']
    cores = [matplotlib.colors.to_hex(mapa(v)) for v in np.linspace(0.06, 0.94, n)]
    return cores[::-1] if sentido == 'alto_ruim' else cores


def _escala_bonita(largura_m):
    alvo = largura_m / 4
    base = 10 ** int(np.floor(np.log10(alvo)))
    for mult in (5, 2, 1):
        if base * mult <= alvo:
            return base * mult
    return base


def _reduzir(indices, teto=4_000_000):
    """Desenhar 20 milhões de células só engorda o PDF: reduz para o desenho."""
    ny, nx = indices.shape
    passo = int(np.ceil(np.sqrt(ny * nx / teto))) if ny * nx > teto else 1
    return indices[::passo, ::passo]


def _engordar(indices, passos=2):
    """Células vazias coladas numa célula válida recebem a classe dela. Serve só
    ao desenho: cobre a meia célula entre o centro da última célula e o contorno."""
    idx = indices.copy()
    for _ in range(passos):
        vazio = idx < 0
        if not vazio.any():
            break
        novo = idx.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            vizinho = np.full_like(idx, -1)
            origem = idx[max(dy, 0):idx.shape[0] + min(dy, 0), max(dx, 0):idx.shape[1] + min(dx, 0)]
            vizinho[max(-dy, 0):idx.shape[0] + min(-dy, 0),
                    max(-dx, 0):idx.shape[1] + min(-dx, 0)] = origem
            usar = vazio & (novo < 0) & (vizinho >= 0)
            novo[usar] = vizinho[usar]
        idx = novo
    return idx


def _para_desenho(indices, aneis, x_oeste, y_norte, pixel, teto=3_000_000):
    """A grade que vai para a figura. Talhão pequeno: cada célula é subdividida e
    recortada pelo contorno (parando o "serrilhado" de 5 m na borda). Fazenda
    grande: a grade é reduzida, porque desenhar milhões de células só engorda o
    PDF. As áreas e o GeoTIFF usam sempre a grade original."""
    ny, nx = indices.shape
    if ny * nx > teto:
        return _reduzir(indices, teto)
    fator = int(min(6, max(1, np.floor(np.sqrt(teto / (ny * nx))))))
    if fator == 1:
        return indices
    fino = np.repeat(np.repeat(_engordar(indices), fator, axis=0), fator, axis=1)
    passo = pixel / fator
    xc = x_oeste + (np.arange(nx * fator) + 0.5) * passo
    yc = y_norte - (np.arange(ny * fator) + 0.5) * passo
    gx, gy = np.meshgrid(xc, yc)
    centros = np.column_stack([gx.ravel(), gy.ravel()])
    dentro = np.zeros(len(centros), dtype=bool)
    for anel in aneis:  # paridade, como na máscara dos cálculos (furos respeitados)
        axs = [p[0] for p in anel]
        ays = [p[1] for p in anel]
        cand = np.flatnonzero((centros[:, 0] >= min(axs)) & (centros[:, 0] <= max(axs))
                              & (centros[:, 1] >= min(ays)) & (centros[:, 1] <= max(ays)))
        if len(cand):
            dentro[cand] ^= Caminho(anel).contains_points(centros[cand])
    fino[~dentro.reshape(fino.shape)] = -1
    return fino


def _logo(fig, caminho):
    if not caminho:
        return
    try:
        imagem = plt.imread(str(caminho))
    except Exception:  # logo ilegível não derruba a apostila
        return
    ax = fig.add_axes([0.80, 0.895, 0.165, 0.075], anchor='E')
    ax.imshow(imagem)
    ax.axis('off')


def _cabecalho(fig, titulo, subtitulo, logo):
    fig.text(0.035, 0.945, titulo, fontsize=18, fontweight='bold', color=TINTA, va='center')
    if subtitulo:
        fig.text(0.035, 0.905, subtitulo, fontsize=9.5, color=CINZA, va='center')
    _logo(fig, logo)
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.882, 0.882], color=LINHA, linewidth=0.8))


def _rodape(fig, esquerda, data):
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.062, 0.062], color=LINHA, linewidth=0.8))
    for i, linha in enumerate(esquerda[:2]):
        fig.text(0.035, 0.044 - i * 0.02, linha, fontsize=7, color=CINZA, va='center')
    direita = f'{data} · {RODAPE}' if data else RODAPE
    fig.text(0.965, 0.044, direita, fontsize=7, color=CINZA, va='center', ha='right')


def pagina_mapa(d):
    """Uma página por elemento. `d` é o bloco montado em interpolar.py:
    indices, x_oeste, y_norte, pixel, aneis_utm, pontos_xy, titulo, subtitulo,
    unidade, nomes, limites, sentido, areas_ha, estat (dict), metodo (linhas),
    fonte, observacao, logo, data."""
    n_classes = len(d['areas_ha'])
    cores = cores_das_classes(n_classes, d['sentido'])
    fig = plt.figure(figsize=A4_DEITADA)
    _cabecalho(fig, d['titulo'], d.get('subtitulo'), d.get('logo'))

    # ------------------------------------------------------------ o mapa
    ax = fig.add_axes([0.035, 0.085, 0.60, 0.78])
    ny, nx = d['indices'].shape
    extensao = [d['x_oeste'], d['x_oeste'] + nx * d['pixel'],
                d['y_norte'] - ny * d['pixel'], d['y_norte']]
    desenho = _para_desenho(d['indices'], d['aneis_utm'], d['x_oeste'], d['y_norte'], d['pixel'])
    ax.imshow(np.ma.masked_less(desenho, 0), extent=extensao, origin='upper',
              cmap=ListedColormap(cores), norm=BoundaryNorm(range(n_classes + 1), n_classes),
              interpolation='nearest')
    for anel in d['aneis_utm']:
        xs = [p[0] for p in anel] + [anel[0][0]]
        ys = [p[1] for p in anel] + [anel[0][1]]
        ax.plot(xs, ys, color='#111827', linewidth=0.9)
    if d.get('pontos_xy'):
        px, py = zip(*d['pontos_xy'])
        ax.scatter(px, py, s=7, c='#111827', linewidths=0.35, edgecolors='white', zorder=5)
    ax.set_aspect('equal')
    ax.set_anchor('NW')  # o mapa encosta no topo, alinhado com a legenda
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_color(LINHA)

    largura = extensao[1] - extensao[0]
    altura = extensao[3] - extensao[2]
    comprimento = _escala_bonita(largura)
    bx, by = extensao[0] + largura * 0.03, extensao[2] + altura * 0.035
    ax.plot([bx, bx + comprimento], [by, by], color='#111827', linewidth=3, solid_capstyle='butt')
    rotulo = f'{num_br(comprimento / 1000)} km' if comprimento >= 1000 else f'{comprimento:g} m'
    ax.annotate(rotulo, (bx + comprimento / 2, by), xytext=(0, 5), textcoords='offset points',
                ha='center', fontsize=8, color='#111827')
    ax.annotate('N', xy=(0.965, 0.955), xycoords='axes fraction', ha='center', fontsize=11,
                fontweight='bold', color='#111827')
    ax.annotate('', xy=(0.965, 0.945), xycoords='axes fraction', xytext=(0.965, 0.885),
                textcoords='axes fraction',
                arrowprops={'arrowstyle': '-|>', 'color': '#111827', 'linewidth': 1.4})

    # ---------------------------------------------------------- a legenda
    painel = fig.add_axes([0.66, 0.085, 0.305, 0.78])
    painel.set_xlim(0, 1)
    painel.set_ylim(0, 1)
    painel.axis('off')
    nomes = d['nomes']
    faixas = rotulos_de_faixa(d['limites']) if d['limites'] is not None else None
    total = sum(d['areas_ha']) or 1.0

    y = 0.985
    painel.text(0, y, 'Classes' + (f' ({d["unidade"]})' if d.get('unidade') else ''),
                fontsize=10.5, fontweight='bold', color=TINTA, va='top')
    y -= 0.05
    col_faixa = 0.47 if nomes else 0.09
    for x, texto, alinh in ((0.09, 'Classe' if nomes else 'Faixa', 'left'),
                            (col_faixa, 'Faixa' if nomes and faixas else '', 'left'),
                            (0.84, 'ha', 'right'), (1.0, '%', 'right')):
        painel.text(x, y, texto, fontsize=8, color=CINZA, va='center', ha=alinh)
    y -= 0.022
    painel.plot([0, 1], [y, y], color=LINHA, linewidth=0.8)
    passo = min(0.058, 0.44 / max(n_classes, 1))
    for i in range(n_classes):
        y -= passo
        painel.add_patch(Rectangle((0, y - 0.016), 0.06, 0.032, facecolor=cores[i],
                                   edgecolor='#374151', linewidth=0.5))
        if nomes:
            painel.text(0.09, y, nomes[i], fontsize=9, color=TINTA, va='center')
            if faixas:
                painel.text(col_faixa, y, faixas[i], fontsize=8.5, color=TINTA, va='center')
        else:
            painel.text(0.09, y, faixas[i], fontsize=9, color=TINTA, va='center')
        painel.text(0.84, y, num_br(d['areas_ha'][i], 1), fontsize=9, color=TINTA,
                    va='center', ha='right')
        painel.text(1.0, y, num_br(100 * d['areas_ha'][i] / total, 1), fontsize=9,
                    color=TINTA, va='center', ha='right')
    y -= passo * 0.62
    painel.plot([0, 1], [y, y], color=LINHA, linewidth=0.8)
    y -= 0.03
    painel.text(0.09, y, 'Área total', fontsize=9, fontweight='bold', color=TINTA, va='center')
    painel.text(0.84, y, num_br(total, 1), fontsize=9, fontweight='bold', color=TINTA,
                va='center', ha='right')
    painel.text(1.0, y, '100,0', fontsize=9, fontweight='bold', color=TINTA, va='center', ha='right')
    if d.get('observacao'):
        linhas = textwrap.wrap(d['observacao'], 58)
        y -= 0.035
        painel.text(0, y, '\n'.join(linhas), fontsize=7.5, color=CINZA, va='top', linespacing=1.4)
        y -= 0.024 * len(linhas)

    # ------------------------------------------------------ estatísticas
    e = d['estat']
    y -= 0.055
    painel.text(0, y, 'Estatísticas', fontsize=10.5, fontweight='bold', color=TINTA, va='top')
    y -= 0.05
    for x, texto in ((0.50, 'Mínimo'), (0.75, 'Média'), (1.0, 'Máximo')):
        painel.text(x, y, texto, fontsize=8, color=CINZA, va='center', ha='right')
    y -= 0.022
    painel.plot([0, 1], [y, y], color=LINHA, linewidth=0.8)
    for rotulo, chave in (('Mapa', 'mapa'), (f'Amostras (n = {e["n"]})', 'amostras')):
        y -= 0.045
        painel.text(0, y, rotulo, fontsize=9, color=TINTA, va='center')
        for x, v in zip((0.50, 0.75, 1.0), e[chave]):
            painel.text(x, y, num_br(v), fontsize=9, color=TINTA, va='center', ha='right')
    y -= 0.06
    for linha in d.get('metodo', []):
        painel.text(0, y, linha, fontsize=7.5, color=CINZA, va='center')
        y -= 0.027

    _rodape(fig, [f'Classes: {d["fonte"]}' if d.get('fonte') else
                  'Classes livres (sem tabela oficial para esta coluna)',
                  d.get('referencia', '')], d.get('data'))
    return fig


def pagina_capa(c):
    """Capa da apostila. c: titulo, fazenda, cliente, responsavel, linhas
    (lista de pares rótulo/valor), logo, data."""
    fig = plt.figure(figsize=A4_DEITADA)
    _logo(fig, c.get('logo'))
    fig.add_artist(Rectangle((0.035, 0.52), 0.012, 0.22, transform=fig.transFigure,
                             facecolor='#1a9850', edgecolor='none'))
    fig.text(0.065, 0.69, c['titulo'], fontsize=30, fontweight='bold', color=TINTA, va='center')
    fig.text(0.065, 0.61, c.get('fazenda') or '', fontsize=18, color=TINTA, va='center')
    fig.text(0.065, 0.555, c.get('cliente') or '', fontsize=12, color=CINZA, va='center')
    y = 0.42
    for rotulo, valor in c.get('linhas', []):
        fig.text(0.065, y, rotulo, fontsize=10, color=CINZA, va='center')
        fig.text(0.26, y, str(valor), fontsize=10, color=TINTA, va='center')
        y -= 0.036
    fig.text(0.065, 0.13,
             'Mapas gerados por interpolação a partir das amostras do laudo. São apoio técnico: a\n'
             'interpretação e a recomendação cabem ao engenheiro agrônomo responsável.',
             fontsize=8.5, color=CINZA, va='center', linespacing=1.5)
    _rodape(fig, [c.get('responsavel') or ''], c.get('data'))
    return fig


def paginas_resumo(linhas, logo=None, data=None, por_pagina=22):
    """Tabela-resumo (uma linha por elemento). Devolve uma figura por página.
    linhas: dicts com elemento, unidade, n, min, media, max, predominante, pagina."""
    colunas = (('Elemento', 0.035, 'left'), ('Unidade', 0.30, 'left'), ('n', 0.435, 'right'),
               ('Mínimo', 0.525, 'right'), ('Média', 0.615, 'right'), ('Máximo', 0.705, 'right'),
               ('Classe predominante (% da área)', 0.735, 'left'), ('Pág.', 0.965, 'right'))
    figuras = []
    for ini in range(0, len(linhas), por_pagina):
        fig = plt.figure(figsize=A4_DEITADA)
        _cabecalho(fig, 'Resumo dos mapas', 'Valores do mapa interpolado, dentro do perímetro', logo)
        y = 0.84
        for titulo, x, alinh in colunas:
            fig.text(x, y, titulo, fontsize=8.5, color=CINZA, va='center', ha=alinh)
        fig.add_artist(plt.Line2D([0.035, 0.965], [y - 0.02, y - 0.02], color=LINHA, linewidth=0.8))
        for ln in linhas[ini:ini + por_pagina]:
            y -= 0.034
            celulas = (ln['elemento'], ln.get('unidade') or '—', str(ln['n']), num_br(ln['min']),
                       num_br(ln['media']), num_br(ln['max']), ln['predominante'], str(ln['pagina']))
            for (_, x, alinh), texto in zip(colunas, celulas):
                fig.text(x, y, texto, fontsize=9.5, color=TINTA, va='center', ha=alinh)
        _rodape(fig, [''], data)
        figuras.append(fig)
    return figuras


if __name__ == '__main__':
    # exemplo embutido: página sintética 80×100 células de 5 m, 5 classes
    import os
    import tempfile

    ny, nx = 80, 100
    yy, xx = np.mgrid[0:ny, 0:nx]
    valores = 60 + 45 * np.sin(xx / 20) + 25 * np.cos(yy / 13)
    indices = np.digitize(valores, [15, 40, 70, 120], right=True).astype(np.int16)
    indices[:10, :15] = -1
    areas = [float((indices == i).sum() * 25 / 10000) for i in range(5)]
    assert cores_das_classes(5, 'alto_bom')[::-1] == cores_das_classes(5, 'alto_ruim')
    # desenho: célula vazia vizinha de válida é coberta, e o recorte segue o contorno
    quina = np.array([[-1, -1, -1], [-1, 2, -1], [-1, -1, -1]], dtype=np.int16)
    assert (_engordar(quina, 1) == 2).all()
    fino = _para_desenho(quina, [[(5, -10), (10, -10), (10, -5), (5, -5)]], 0, 0, 5.0)
    assert fino.shape == (18, 18) and (fino >= 0).sum() == 36 and fino.max() == 2
    assert _para_desenho(np.zeros((2000, 2000), dtype=np.int16), [], 0, 0, 5.0).shape == (1000, 1000)
    assert len(set(cores_das_classes(3, 'neutra'))) == 3
    bloco = {
        'indices': indices, 'x_oeste': 0, 'y_norte': 0, 'pixel': 5.0,
        'aneis_utm': [[(0, -400), (500, -400), (500, 0), (0, 0)]],
        'pontos_xy': [(50 + i * 45, -50 - (i % 5) * 70) for i in range(10)],
        'titulo': 'K — teste sintético', 'subtitulo': 'Fazenda Exemplo · 0–20 cm',
        'unidade': 'mg/dm3', 'nomes': ['Muito baixo', 'Baixo', 'Médio', 'Bom', 'Muito bom'],
        'limites': [15, 40, 70, 120], 'sentido': 'alto_bom', 'areas_ha': areas,
        'estat': {'n': 10, 'mapa': (3.2, 61.4, 129.9), 'amostras': (2.0, 60.1, 131.0)},
        'metodo': ['IDW · potência 2 · 12 vizinhos · pixel 5 m', 'RMSE da validação cruzada: 9,8'],
        'fonte': '5ª Aproximação (CFSEMG, 1999), Quadro 5.3', 'data': '12/11/2026',
    }
    with tempfile.TemporaryDirectory() as pasta:
        png = os.path.join(pasta, 'k.png')
        fig = pagina_mapa(bloco)
        fig.savefig(png, dpi=110)
        plt.close(fig)
        assert os.path.getsize(png) > 30000
        capa = pagina_capa({'titulo': 'Mapas de fertilidade do solo', 'fazenda': 'Fazenda Exemplo',
                            'linhas': [('Área', '19,6 ha'), ('Amostras', '10')]})
        resumo = paginas_resumo([{'elemento': f'E{i}', 'unidade': 'mg/dm3', 'n': 10, 'min': 1.0,
                                  'media': 2.0, 'max': 3.0, 'predominante': 'Médio (41,0%)',
                                  'pagina': i + 3} for i in range(30)])
        assert len(resumo) == 2
        for f in [capa, *resumo]:
            plt.close(f)
        print('mapa OK:', os.path.getsize(png), 'bytes; capa e resumo em 2 páginas')
