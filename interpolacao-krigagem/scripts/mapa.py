"""PNG do mapa interpolado com legenda em régua (colorbar), escala e norte."""

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _escala_bonita(largura_m):
    """Comprimento 'redondo' pra barra de escala (~1/4 da largura do mapa)."""
    alvo = largura_m / 4
    base = 10 ** int(np.floor(np.log10(alvo)))
    for mult in (5, 2, 1):
        if base * mult <= alvo:
            return base * mult
    return base


def desenhar_mapa(caminho_png, malha, x_oeste, y_norte, pixel, aneis_utm,
                  pontos_xy, titulo, subtitulo, unidade, cmap='RdYlGn'):
    """Desenha o mapa: raster mascarado + perímetro + pontos + régua de valores.

    A legenda é uma colorbar horizontal ("régua") com a unidade do elemento.
    Use cmap='RdYlGn_r' para variáveis em que ALTO é ruim (Al³⁺, m%).
    """
    ny, nx = malha.shape
    extensao = [x_oeste, x_oeste + nx * pixel, y_norte - ny * pixel, y_norte]
    dados = np.ma.masked_invalid(malha)

    fig, ax = plt.subplots(figsize=(9, 7.5), dpi=150)
    im = ax.imshow(dados, extent=extensao, origin='upper', cmap=cmap,
                   interpolation='nearest')

    for anel in aneis_utm:
        xs = [p[0] for p in anel] + [anel[0][0]]
        ys = [p[1] for p in anel] + [anel[0][1]]
        ax.plot(xs, ys, color='#222222', linewidth=1.2)
    if pontos_xy is not None and len(pontos_xy):
        px, py = zip(*pontos_xy)
        ax.scatter(px, py, s=12, c='#111111', marker='o',
                   linewidths=0.5, edgecolors='white', zorder=5,
                   label=f'amostras (n={len(pontos_xy)})')
        ax.legend(loc='upper left', fontsize=8, frameon=True, framealpha=0.85)

    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_color('#bbbbbb')

    # barra de escala (canto inferior esquerdo)
    largura = extensao[1] - extensao[0]
    comprimento = _escala_bonita(largura)
    bx = extensao[0] + largura * 0.04
    by = extensao[2] + (extensao[3] - extensao[2]) * 0.045
    ax.plot([bx, bx + comprimento], [by, by], color='#111111', linewidth=3,
            solid_capstyle='butt')
    rotulo = f'{comprimento / 1000:g} km' if comprimento >= 1000 else f'{comprimento:g} m'
    ax.annotate(rotulo, ((bx + bx + comprimento) / 2, by), xytext=(0, 5),
                textcoords='offset points', ha='center', fontsize=8)

    # norte (canto superior direito)
    ax.annotate('N', xy=(0.97, 0.955), xycoords='axes fraction', ha='center',
                fontsize=11, fontweight='bold')
    ax.annotate('', xy=(0.97, 0.945), xycoords='axes fraction',
                xytext=(0.97, 0.885), textcoords='axes fraction',
                arrowprops={'arrowstyle': '-|>', 'color': '#111111', 'linewidth': 1.4})

    ax.set_title(titulo, fontsize=13, fontweight='bold', loc='left', pad=22)
    if subtitulo:
        ax.text(0, 1.012, subtitulo, transform=ax.transAxes, fontsize=8.5,
                color='#555555')

    # a régua de valores
    barra = fig.colorbar(im, ax=ax, orientation='horizontal', fraction=0.05,
                         pad=0.04, aspect=45)
    barra.set_label(unidade, fontsize=9)
    barra.ax.tick_params(labelsize=8)
    barra.outline.set_edgecolor('#999999')

    fig.text(0.99, 0.005, 'agrônomo10X · OagronomIA', ha='right', fontsize=7,
             color='#999999')
    fig.savefig(caminho_png, bbox_inches='tight', facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    # exemplo embutido: mapa sintético 80×100 células de 5 m
    import os
    import tempfile

    ny, nx = 80, 100
    yy, xx = np.mgrid[0:ny, 0:nx]
    malha = 8 + 3 * np.sin(xx / 14) + 2 * np.cos(yy / 10)
    malha[:10, :15] = np.nan  # canto fora do talhão
    anel = [(0, -400), (500, -400), (500, 0), (0, 0)]
    pontos = [(50 + i * 45, -50 - (i % 5) * 70) for i in range(10)]
    with tempfile.TemporaryDirectory() as d:
        arq = os.path.join(d, 'mapa.png')
        desenhar_mapa(arq, malha, x_oeste=0, y_norte=0, pixel=5.0,
                      aneis_utm=[anel], pontos_xy=pontos,
                      titulo='P — teste sintético',
                      subtitulo='krigagem ordinária · pixel 5 m · modelo exponencial',
                      unidade='P (mg/dm³)')
        assert os.path.getsize(arq) > 20000
        print('mapa OK:', arq, os.path.getsize(arq), 'bytes')
