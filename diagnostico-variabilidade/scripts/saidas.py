"""Arquivos de saída: tabelas em CSV, o mapa das manchas em GeoTIFF, as figuras
e o relatório em PDF, no formato dos documentos da casa.

Os CSV saem com ponto e vírgula e vírgula decimal (abrem direto na planilha).

Teste embutido: python scripts/saidas.py
"""

import csv
import textwrap

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

import geometria  # noqa: E402
import geotiff  # noqa: E402
import relato as T  # noqa: E402
from areas import utm_inversa  # noqa: E402

# tokens do design system da casa (tema claro de impressão) e paleta de dataviz
C = dict(pagina='#FBFCF9', fg1='#121810', fg2='#3C4636', fg3='#6B7562', line='#D4DBCA', line_forte='#B4BFA8',
         verde='#2E8B1E', faixa='#EEF2E8')
CORES_DAS_FAIXAS = {2: ['#C26A3D', '#2E8B1E'], 3: ['#C26A3D', '#E8D9A8', '#2E8B1E'],
                    4: ['#C26A3D', '#E9C08F', '#B9D99A', '#2E8B1E'], 5: ['#C26A3D', '#E9C08F', '#EFE7C6', '#B9D99A', '#2E8B1E']}
ROTULO_DOC = 'agrônomo10X · Diagnóstico da variabilidade'
MONO = 'DejaVu Sans Mono'
RODAPE = ('Descreve quem varia junto com quem. Variar junto não é causa; o que fazer no manejo é decisão do '
          'responsável técnico.')


def espacado(texto):
    return ' '.join(str(texto).upper())


def _curto(texto, teto):
    texto = str(texto)
    return texto if len(texto) <= teto else texto[:teto - 1].rstrip() + '…'


# ------------------------------------------------------------------ CSV e GeoTIFF
def _n(v, casas=None):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return ''
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return (format(float(v), f'.{casas}f') if casas is not None else format(float(v), '.8g')).replace('.', ',')


def _gravar(caminho, cabecalho, linhas):
    with open(caminho, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(cabecalho)
        w.writerows(linhas)
    return len(linhas)


def gravar_correlacoes(caminho, r):
    nomes, linhas = r['nomes'], []
    for i in range(len(nomes)):
        for j in range(i + 1, len(nomes)):
            linhas.append([nomes[i], nomes[j], _n(r['pearson'][i, j], 4), _n(r['intervalo_baixo'][i, j], 4),
                           _n(r['intervalo_alto'][i, j], 4), _n(r['spearman'][i, j], 4), _n(r['n_efetivo'][i, j], 1), r['celulas']])
    return _gravar(caminho, ['camada_a', 'camada_b', 'pearson', 'intervalo_95_de', 'intervalo_95_ate', 'spearman',
                             'observacoes_independentes', 'celulas'], linhas)


def gravar_importancia(caminho, r):
    linhas = []
    for l in r['importancia']:
        ic = l.get('intervalo') or (None, None)
        linhas.append([l['nome'], l['tipo'], _n(l.get('r'), 4), _n(ic[0], 4), _n(ic[1], 4), _n(l.get('spearman'), 4),
                       _n(l.get('n_efetivo'), 1), _n(l['sozinha'], 4), _n(l['por_cima'], 4), _n(l['repartida'], 4),
                       _n(l.get('r2_curva'), 4), _n(l.get('inflacao'), 2), '; '.join(l['notas'])])
    linhas.append(['(conjunto)', '', '', '', '', '', _n(r['n_efetivo_do_conjunto'], 1), '', '', _n(r['r2_do_conjunto'], 4), '', '',
                   f'piso de ruído: {_n(r["piso_de_ruido"], 4) or "não calculável"}'])
    return _gravar(caminho, ['camada', 'tipo', 'pearson', 'intervalo_95_de', 'intervalo_95_ate', 'spearman',
                             'observacoes_independentes', 'r2_sozinha', 'r2_por_cima_das_outras', 'r2_repartida',
                             'r2_da_curva_de_2_grau', 'fator_de_inflacao', 'notas'], linhas)


def gravar_manchas(caminho, r):
    m = r['manchas']
    cab = ['faixa', 'area_ha', 'area_pct', 'manchas', 'maior_mancha_ha', f'{r["alvo"]}_media', f'{r["alvo"]}_minimo', f'{r["alvo"]}_maximo']
    for k in r['camadas']:
        cab += [f'{k}_media', f'{k}_desvio']
    for k in r['classes']:
        cab += [f'{k}={c}_pct' for c in m['faixas'][0]['classes'][k]]
    linhas = []
    for f in m['faixas']:
        linha = [f['faixa'], _n(f['area_ha'], 2), _n(f['area_pct'], 1), f['manchas'], _n(f['maior_ha'], 2), _n(f['alvo_media']),
                 _n(f['alvo_minimo']), _n(f['alvo_maximo'])]
        for k in r['camadas']:
            linha += [_n(f['camadas'][k]['media']), _n(f['camadas'][k]['desvio'])]
        for k in r['classes']:
            linha += [_n(v, 1) for v in f['classes'][k].values()]
        linhas.append(linha)
    sep = ['alto − baixo, em desvios da camada', '', '', '', '', '', '', '']
    for k in r['camadas']:
        sep += [_n(m['separacao'][k], 3), '']
    linhas.append(sep)
    return _gravar(caminho, cab, linhas)


def gravar_celulas(caminho, estado, r):
    g, v = estado['grade'], r['valida']
    x, y = g['x'][v], g['y'][v]
    lon, lat = utm_inversa(x, y, estado['zona'], estado['sul'])
    nomes = [r['alvo']] + r['camadas']
    colunas = [estado['camadas'][k]['malha'][v] for k in nomes]
    classes = [np.asarray(estado['classes'][k]['nomes'], dtype=object)[estado['classes'][k]['rotulos'][v]] for k in r['classes']]
    faixa = np.asarray([f['faixa'] for f in r['manchas']['faixas']], dtype=object)[r['manchas']['mapa'][v]]
    linhas = []
    for i in range(len(x)):
        linhas.append([_n(float(x[i]), 1), _n(float(y[i]), 1), _n(float(lon[i]), 7), _n(float(lat[i]), 7)]
                      + [_n(float(c[i])) for c in colunas] + [str(c[i]) for c in classes] + [faixa[i]])
    return _gravar(caminho, ['x_utm', 'y_utm', 'longitude', 'latitude'] + nomes + r['classes'] + ['faixa'], linhas)


def gravar_geotiff_das_manchas(caminho, estado, r):
    """Faixa de cada célula (1 = a mais baixa); -9999 fora. Abre no QGIS."""
    g = estado['grade']
    mapa = np.where(r['manchas']['mapa'] >= 0, r['manchas']['mapa'] + 1, -9999).astype(float)
    geotiff.escrever_geotiff(caminho, mapa, g['x0'], g['y0'], g['celula'], geometria.epsg_utm(estado['zona'], estado['sul']))


# ------------------------------------------------------------------ moldura e tabelas
def _moldura(fig, titulo, subtitulo, kpis, rodape):
    fig.text(0.035, 0.955, espacado(ROTULO_DOC), fontsize=6.4, color=C['verde'], va='center', fontweight='bold')
    fig.text(0.035, 0.915, _curto(titulo, 46), fontsize=15.5, color=C['fg1'], va='center', fontstyle='italic', fontweight='bold')
    fig.text(0.035, 0.878, _curto(subtitulo, 88), fontsize=9.5, color=C['fg2'], va='center')
    x = 0.965
    for rotulo, valor, unidade in reversed(kpis):
        fig.text(x, 0.955, espacado(rotulo), fontsize=5.8, color=C['fg3'], va='center', ha='right')
        fig.text(x, 0.918, valor, fontsize=14, color=C['fg1'], va='center', ha='right', family=MONO, fontweight='bold')
        fig.text(x, 0.885, unidade, fontsize=7, color=C['fg3'], va='center', ha='right', family=MONO)
        x -= 0.03 + 0.0118 * max(len(valor), len(unidade) * 0.55, len(rotulo) * 0.75, 7)
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.86, 0.86], color=C['line'], linewidth=0.8))
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.062, 0.062], color=C['line'], linewidth=0.8))
    fig.text(0.035, 0.044, rodape, fontsize=7, color=C['fg3'], va='center')
    fig.text(0.035, 0.026, RODAPE, fontsize=6.4, color=C['fg3'], va='center')
    fig.text(0.965, 0.036, 'OagronomIA', fontsize=10.5, color=C['fg1'], va='center', ha='right', fontstyle='italic', fontweight='bold')


def _painel(fig, caixa):
    ax = fig.add_axes(caixa)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    return ax


def _titulo(ax, y, texto):
    ax.text(0, y, espacado(texto), fontsize=7.6, fontweight='bold', color=C['fg1'], va='top')
    return y - 0.06


def _tabela(ax, y, colunas, linhas, passo=0.055, fonte=7.0, destaque=None):
    for titulo, xc, alinh, _ in colunas:
        ax.text(xc, y, espacado(titulo), fontsize=5.0, color=C['fg3'], va='center', ha=alinh)
    y -= 0.03
    ax.plot([0, 1], [y, y], color=C['line'], linewidth=0.8)
    for k, linha in enumerate(linhas):
        if destaque and k in destaque:
            ax.fill_between([0, 1], y - passo, y, color=C['faixa'], linewidth=0)
        for (_, xc, alinh, mono), texto in zip(colunas, linha):
            ax.text(xc, y - passo / 2, texto, fontsize=fonte, color=C['fg1'], va='center', ha=alinh, family=MONO if mono else None)
        y -= passo
        ax.plot([0, 1], [y, y], color=C['line'], linewidth=0.4)
    return y


def _texto(ax, y, linhas, largura, fonte=6.8, cor='fg2', passo=0.036, piso=0.0, marcador='– '):
    for k, linha in enumerate(linhas):
        partes = textwrap.wrap(marcador + linha, largura, subsequent_indent='  ') or ['']
        if y - passo * len(partes) < piso:
            ax.text(0, y, f'… (mais {len(linhas) - k} no relato.md)', fontsize=fonte, color=C['fg3'], va='top')
            return y - passo
        ax.text(0, y, '\n'.join(partes), fontsize=fonte, color=C[cor], va='top', linespacing=1.4)
        y -= passo * len(partes) + 0.016
    return y


def _eixo(ax, titulo=None):
    for lado in ('top', 'right'):
        ax.spines[lado].set_visible(False)
    for lado in ('bottom', 'left'):
        ax.spines[lado].set_color(C['line_forte'])
    ax.tick_params(labelsize=6.6, colors=C['fg3'])
    ax.set_facecolor('#FFFFFF')
    if titulo:
        ax.set_title(espacado(titulo), fontsize=7.0, color=C['fg1'], fontweight='bold', loc='left', pad=7)


# ------------------------------------------------------------------ gráficos
def barras_da_importancia(ax, r):
    linhas = r['importancia'][:12][::-1]
    y = np.arange(len(linhas))
    series = [('sozinha', 'Sozinha', '#B4BFA8'), ('por_cima', 'Por cima das outras', '#C26A3D'), ('repartida', 'Repartida', '#2E8B1E')]
    series = [s for s in series if s[0] != 'repartida' or linhas[0]['repartida'] is not None]
    alt = 0.8 / len(series)
    for k, (chave, rotulo, cor) in enumerate(series):
        ax.barh(y + (k - (len(series) - 1) / 2) * alt, [100 * l[chave] for l in linhas], height=alt * 0.92, color=cor, label=rotulo)
    ax.set_yticks(y)
    ax.set_yticklabels([_curto(l['nome'], 20) for l in linhas])
    ax.set_xlabel(f'% da variação de {_curto(r["alvo"], 24)} (R²)', fontsize=6.6, color=C['fg3'])
    if r['piso_de_ruido'] is not None:
        ax.axvline(100 * r['piso_de_ruido'], color=C['fg3'], linewidth=0.8, linestyle=(0, (3, 3)))
        ax.text(100 * r['piso_de_ruido'], len(linhas) - 0.45, ' piso de ruído do conjunto', fontsize=5.6, color=C['fg3'], va='bottom')
    ax.legend(fontsize=6.0, frameon=False, loc='lower right', labelcolor=C['fg2'])
    _eixo(ax, 'A parte de cada camada')
    ax.grid(axis='x', color=C['line'], linewidth=0.4)
    ax.set_axisbelow(True)


def mapa_de_calor(ax, r):
    nomes = r['nomes']
    p = len(nomes)
    m = np.where(np.tri(p, k=-1, dtype=bool), r['pearson'], np.where(np.tri(p, k=-1, dtype=bool).T, r['spearman'], np.nan))
    ax.imshow(m, cmap='BrBG', vmin=-1, vmax=1)
    for i in range(p):
        for j in range(p):
            if i != j:
                ax.text(j, i, T.br(m[i, j]), ha='center', va='center', fontsize=max(4.2, 7.4 - 0.3 * p),
                        color='#FFFFFF' if abs(m[i, j]) > 0.6 else C['fg1'], family=MONO)
    ax.set_xticks(range(p))
    ax.set_yticks(range(p))
    ax.set_xticklabels([_curto(n, 12) for n in nomes], rotation=40, ha='right')
    ax.set_yticklabels([_curto(n, 16) for n in nomes])
    _eixo(ax, 'Correlações: Pearson abaixo, Spearman acima')
    for lado in ('bottom', 'left'):
        ax.spines[lado].set_visible(False)
    ax.tick_params(length=0)


def _extensao(g):
    return [g['x0'], g['x0'] + g['nx'] * g['celula'], g['y0'] - g['ny'] * g['celula'], g['y0']]


def _contorno(ax, estado):
    for a in estado['areas']:
        for anel in a['aneis']:
            xs, ys = zip(*anel)
            ax.plot(xs, ys, color=C['fg1'], linewidth=0.6)
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_visible(False)


def mapa_da_camada(ax, estado, nome, valida, cmap='viridis'):
    malha = np.where(valida, estado['camadas'][nome]['malha'], np.nan)
    faixa = np.nanpercentile(malha, [2, 98])
    im = ax.imshow(malha, extent=_extensao(estado['grade']), cmap=cmap, vmin=faixa[0], vmax=faixa[1], interpolation='nearest')
    _contorno(ax, estado)
    ax.set_title(_curto(nome, 26), fontsize=6.8, color=C['fg1'], loc='left', pad=3)
    barra = ax.figure.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    barra.ax.tick_params(labelsize=5.2, colors=C['fg3'], length=2)
    barra.outline.set_visible(False)


def mapa_das_manchas(ax, estado, r):
    m = r['manchas']
    n = len(m['faixas'])
    mapa = np.where(m['mapa'] >= 0, m['mapa'].astype(float), np.nan)
    ax.imshow(mapa, extent=_extensao(estado['grade']), cmap=ListedColormap(CORES_DAS_FAIXAS[n]), vmin=-0.5, vmax=n - 0.5,
              interpolation='nearest')
    _contorno(ax, estado)
    marcas = [plt.Rectangle((0, 0), 1, 1, color=CORES_DAS_FAIXAS[n][k]) for k in range(n)]
    ax.legend(marcas, [f'{f["faixa"]} ({T.br(f["area_pct"], 0)}%)' for f in m['faixas']], fontsize=6.2, frameon=False,
              loc='upper center', bbox_to_anchor=(0.5, -0.01), ncol=n, labelcolor=C['fg2'], handlelength=1.2)


def dispersao(ax, r, estado, nome):
    v = r['valida']
    x, y = estado['camadas'][nome]['malha'][v], estado['camadas'][r['alvo']]['malha'][v]
    ax.hexbin(x, y, gridsize=28, cmap='Greens', mincnt=1, linewidths=0)
    coef = np.polyfit(x, y, 1)
    xs = np.array([np.percentile(x, 1), np.percentile(x, 99)])
    ax.plot(xs, np.polyval(coef, xs), color=C['fg1'], linewidth=0.9)
    linha = next(l for l in r['importancia'] if l['nome'] == nome)
    _eixo(ax, f'{_curto(nome, 20)} · r = {T.sinal(linha["r"])}')
    ax.set_ylabel(_curto(r['alvo'], 22), fontsize=6.2, color=C['fg3'])


def figuras(pasta, estado, r):
    """Grava as figuras soltas em PNG. Devolve os nomes."""
    nomes = []
    fig, ax = plt.subplots(figsize=(7.2, 0.9 + 0.42 * max(3, min(12, len(r['importancia'])))), facecolor=C['pagina'])
    barras_da_importancia(ax, r)
    fig.tight_layout()
    fig.savefig(pasta / 'importancia.png', dpi=160, facecolor=C['pagina'])
    plt.close(fig)
    nomes.append('importancia.png')
    lado = 3.4 + 0.42 * len(r['nomes'])
    fig, ax = plt.subplots(figsize=(lado, lado * 0.92), facecolor=C['pagina'])
    mapa_de_calor(ax, r)
    fig.tight_layout()
    fig.savefig(pasta / 'correlacoes.png', dpi=160, facecolor=C['pagina'])
    plt.close(fig)
    nomes.append('correlacoes.png')
    fig, ax = plt.subplots(figsize=(6.4, 5.6), facecolor=C['pagina'])
    mapa_das_manchas(ax, estado, r)
    ax.set_title(f'Faixas de {_curto(r["alvo"], 30)}', fontsize=8.5, color=C['fg1'], loc='left', fontweight='bold')
    fig.tight_layout()
    fig.savefig(pasta / 'manchas.png', dpi=160, facecolor=C['pagina'])
    plt.close(fig)
    nomes.append('manchas.png')
    return nomes


# ------------------------------------------------------------------ PDF
def relatorio(caminho_pdf, estado, r, nome=None, caminho_png=None):
    alvo = r['alvo']
    titulo = nome or f'Variabilidade de {alvo}'
    subtitulo = f'O que acompanha {alvo} · {T.inteiro(r["celulas"])} células de {r["celula_m"]:g} m · {T.br(r["area_analisada_ha"], 1)} ha'
    kpis = [('Camadas', str(len(r['importancia'])), 'analisadas'), ('Células', T.inteiro(r['celulas']), f'de {r["celula_m"]:g} m'),
            ('Conjunto', T.br(100 * r['r2_do_conjunto'], 0) + '%', 'da variação (R²)')]
    numericas = [l for l in r['importancia'] if l['tipo'] == 'numerica']
    total = 5 + (1 if numericas else 0)
    pagina = 0

    def nova():
        nonlocal pagina
        pagina += 1
        fig = plt.figure(figsize=(11.69, 8.27), facecolor=C['pagina'])
        _moldura(fig, titulo, subtitulo, kpis, f'Diagnóstico da variabilidade · página {pagina} de {total}')
        return fig

    with PdfPages(caminho_pdf) as pdf:
        # 1. camada por camada
        fig = nova()
        ax = _painel(fig, [0.035, 0.42, 0.56, 0.42])
        y = _titulo(ax, 1.0, f'Camada por camada (em % da variação de {_curto(alvo, 30)})')
        colunas = [('Camada', 0.0, 'left', False), ('r', 0.31, 'right', True), ('Intervalo de 95%', 0.56, 'right', True),
                   ('Obs. ind.', 0.68, 'right', True), ('Sozinha', 0.79, 'right', True), ('Por cima', 0.895, 'right', True),
                   ('Repartida', 1.0, 'right', True)]
        linhas, destaque = [], set()
        for k, l in enumerate(r['importancia'][:12]):
            rep = '—' if l['repartida'] is None else T.br(100 * l['repartida'], 1)
            if l['tipo'] == 'classes':
                linhas.append([_curto(l['nome'], 24) + ' (classes)', '—', '—', '—', T.br(100 * l['sozinha'], 1), T.br(100 * l['por_cima'], 1), rep])
            else:
                linhas.append([_curto(l['nome'], 30), T.sinal(l['r']), f'{T.sinal(l["intervalo"][0])} a {T.sinal(l["intervalo"][1])}',
                               T.inteiro(l['n_efetivo']), T.br(100 * l['sozinha'], 1), T.br(100 * l['por_cima'], 1), rep])
                if not l['fora_de_zero']:
                    destaque.add(k)
        y = _tabela(ax, y, colunas, linhas, passo=min(0.07, 0.78 / max(1, len(linhas))), destaque=destaque)
        notas = ['Faixa cinza: o intervalo inclui o zero (não se distingue do acaso).'] if destaque else []
        notas.append('Obs. ind.: observações independentes na comparação com a variável a explicar.')
        if len(r['importancia']) > 12:
            notas.append(f'Mais {len(r["importancia"]) - 12} camada(s) no importancia.csv.')
        _texto(ax, y - 0.03, notas, 112, fonte=6.2, cor='fg3', passo=0.04, marcador='')
        barras_da_importancia(fig.add_axes([0.68, 0.48, 0.285, 0.33]), r)
        ax = _painel(fig, [0.035, 0.085, 0.93, 0.30])
        y = _titulo(ax, 1.0, 'Leitura')
        _texto(ax, y, T.frases_de_leitura(r), 190, fonte=6.9, passo=0.085, piso=0.0)
        pdf.savefig(fig, facecolor=C['pagina'])
        if caminho_png:
            fig.savefig(caminho_png, dpi=140, facecolor=C['pagina'])
        plt.close(fig)

        # 2. correlações e avisos
        fig = nova()
        mapa_de_calor(fig.add_axes([0.075, 0.17, 0.40, 0.60]), r)
        ax = _painel(fig, [0.56, 0.085, 0.405, 0.755])
        y = _titulo(ax, 1.0, 'Avisos')
        y = _texto(ax, y, r['avisos'] or ['Nenhum aviso além dos de leitura.'], 82, fonte=6.7, cor='fg1', passo=0.031, piso=0.42)
        y = _titulo(ax, y - 0.02, 'Como ler')
        _texto(ax, y, ['Variar junto não é causa: uma terceira coisa pode mexer nas duas, ou pode ser acaso.',
                       'Células vizinhas de um mapa se parecem. O intervalo de cada correlação usa o número de observações '
                       'independentes, bem menor que o de células.',
                       'Mapa interpolado de poucas amostras é suave e acompanha outros mapas suaves com facilidade.',
                       'A conta é de reta: relação em curva aparece na nota da camada e no perfil das manchas.'],
               82, fonte=6.6, passo=0.031)
        pdf.savefig(fig, facecolor=C['pagina'])
        plt.close(fig)

        # 3. mapas
        fig = nova()
        mostrar = [alvo] + [l['nome'] for l in numericas][:7]
        colunas_m = 4 if len(mostrar) > 3 else len(mostrar)
        linhas_m = int(np.ceil(len(mostrar) / colunas_m))
        larg, alt = 0.93 / colunas_m, 0.74 / linhas_m
        for k, nome_c in enumerate(mostrar):
            ax = fig.add_axes([0.035 + (k % colunas_m) * larg + 0.008, 0.10 + (linhas_m - 1 - k // colunas_m) * alt + 0.02,
                               larg - 0.03, alt - 0.06])
            mapa_da_camada(ax, estado, nome_c, r['valida'], cmap='YlGn' if k == 0 else 'viridis')
        pdf.savefig(fig, facecolor=C['pagina'])
        plt.close(fig)

        # 4. manchas
        fig = nova()
        m = r['manchas']
        ax = fig.add_axes([0.035, 0.16, 0.36, 0.63])
        mapa_das_manchas(ax, estado, r)
        ax.set_title(espacado(f'Faixas de {_curto(alvo, 26)}'), fontsize=7.2, color=C['fg1'], fontweight='bold', loc='left', pad=7)
        ax = _painel(fig, [0.44, 0.085, 0.525, 0.755])
        y = _titulo(ax, 1.0, 'O que há em cada faixa (média)')
        mostradas = [l['nome'] for l in numericas][:6]
        x0, passo_x = 0.33, (1 - 0.33) / max(1, len(mostradas))
        colunas = [('Faixa', 0.0, 'left', False), ('Área', 0.19, 'right', True), (_curto(alvo, 12), 0.31, 'right', True)] + \
                  [(_curto(k, 11), x0 + (i + 1) * passo_x, 'right', True) for i, k in enumerate(mostradas)]
        c_alvo = T.casas_de(r['alvo_resumo']['media'])
        linhas = [[f['faixa'], f'{T.br(f["area_ha"], 1)} ha', T.br(f['alvo_media'], c_alvo)]
                  + [T.br(f['camadas'][k]['media'], T.casas_de(f['camadas'][k]['media'])) for k in mostradas] for f in m['faixas']]
        linhas.append(['alto − baixo', '', 'em desvios'] + [T.sinal(m['separacao'][k], 1) if m['separacao'][k] is not None else '—' for k in mostradas])
        y = _tabela(ax, y, colunas, linhas, passo=0.05, fonte=6.6, destaque={len(linhas) - 1})
        notas = [f'Cortes de {alvo}: {", ".join(T.br(x, c_alvo) for x in m["cortes"])} '
                 + ('(faixas de mesma área)' if m['por_quantil'] else '(informados)') + ('; filtro de maioria ligado.' if m['filtro'] else '.'),
                 'Manchas com ' + T.br(m['mancha_minima_ha'], 1) + ' ha ou mais: '
                 + '; '.join(f'{f["faixa"]} {f["manchas"]} (a maior com {T.br(f["maior_ha"], 1)} ha)' for f in m['faixas']) + '.',
                 '"Alto − baixo": diferença entre a faixa mais alta e a mais baixa, em desvios da camada. Descreve o que há em cada '
                 'mancha, não a razão dela.']
        for l in r['importancia']:
            if l['tipo'] == 'classes':
                notas.append(f'{alvo} em cada classe de {l["nome"]} (média crua): '
                             + '; '.join(f'{k["classe"]} {T.br(k["media"], c_alvo)} ({T.br(k["area_ha"], 1)} ha)' for k in l['classes']) + '.')
        if len(numericas) > 6:
            notas.append(f'A tabela mostra 6 camadas; as outras {len(numericas) - 6} estão no manchas.csv.')
        _texto(ax, y - 0.035, notas, 104, fonte=6.4, cor='fg2', passo=0.03)
        pdf.savefig(fig, facecolor=C['pagina'])
        plt.close(fig)

        # 5. dispersão
        if numericas:
            fig = nova()
            mostrar = [l['nome'] for l in numericas][:6]
            for k, nome_c in enumerate(mostrar):
                ax = fig.add_axes([0.07 + (k % 3) * 0.31, 0.50 - (k // 3) * 0.39, 0.25, 0.27])
                dispersao(ax, r, estado, nome_c)
            pdf.savefig(fig, facecolor=C['pagina'])
            plt.close(fig)

        # 6. método
        fig = nova()
        ax = _painel(fig, [0.035, 0.085, 0.93, 0.755])
        y = _titulo(ax, 1.0, 'Como a conta foi feita')
        y = _texto(ax, y, [
            f'Grade comum de {r["celula_m"]:g} m sobre o perímetro. Raster: valor no centro da célula (média de vários pontos quando o pixel é '
            'menor que a célula). Pontos: média dos que caem na célula. Só entram as células com valor em todas as camadas escolhidas.',
            'Correlação de Pearson e de Spearman entre a variável a explicar e cada camada, e entre as camadas.',
            'Observações independentes: correção de Clifford, Richardson e Hémon (1989) para duas variáveis com dependência espacial, a '
            'partir do correlograma de cada uma na grade. O intervalo de 95% é o de Fisher com esse número no lugar do número de células.',
            'Sozinha: R² da regressão linear só com a camada. Por cima das outras: quanto o R² do conjunto cai sem ela. Repartida: média do que '
            'ela acrescenta em todas as ordens de entrada (Lindeman, Merenda e Gold; valor de Shapley), que soma o R² do conjunto.',
            'Piso de ruído: o R² que o mesmo número de camadas sem relação nenhuma alcança em 95% das vezes, com as observações independentes '
            'da comparação mais suave.',
            'Manchas: faixas da variável a explicar por quantis (áreas iguais) ou pelos cortes informados; perfil = média de cada camada em '
            'cada faixa.'], 205, fonte=7.0, passo=0.036)
        y = _titulo(ax, y - 0.03, 'O que esta análise não diz')
        _texto(ax, y, [
            'Não diz a causa da variabilidade nem o que corrigir. Camadas que se acompanham podem depender de uma terceira, que não foi enviada.',
            'Não vale fora do talhão e da safra analisados.',
            'Camadas parecidas entre si repartem a importância: isso não diz qual delas pesa de verdade.',
            'Relação em curva (um ótimo no meio) e efeito que depende de outra camada não aparecem numa conta de reta.',
            'Índice de vegetação da mesma safra da variável a explicar é quase a própria resposta e deve ficar de fora.',
            'A decisão de manejo é do responsável técnico, com o conhecimento da área.'], 205, fonte=7.0, passo=0.036)
        pdf.savefig(fig, facecolor=C['pagina'])
        plt.close(fig)
    return pagina


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    import tempfile
    from pathlib import Path

    import analise as A
    import camadas as K
    import sintetico
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        e = sintetico.gravar(pasta / 'dados')
        p = e['pasta']
        estado = K.carregar(str(p / 'talhao.geojson'),
                            rasters=[f'argila={p / "argila_g_kg.tif"}', f'argila_outra={p / "argila_outra_g_kg.tif"}',
                                     f'altitude={p / "altitude_m.tif"}', f'ph={p / "ph.tif"}'],
                            pontos=[str(p / 'colheita_limpa.csv')], classes=[f'variedade={p / "variedades.geojson"}:variedade'])
        r = A.analisar(estado, 'prod_t_ha', ['argila', 'argila_outra', 'altitude', 'ph'], ['variedade'])
        assert gravar_correlacoes(pasta / 'correlacoes.csv', r) == 10
        assert gravar_importancia(pasta / 'importancia.csv', r) == 6
        assert gravar_manchas(pasta / 'manchas.csv', r) == 4
        assert gravar_celulas(pasta / 'celulas.csv', estado, r) == r['celulas']
        gravar_geotiff_das_manchas(pasta / 'manchas.tif', estado, r)
        lido = geotiff.ler_geotiff(str(pasta / 'manchas.tif'))
        assert lido['dx'] == 10.0 and set(np.unique(lido['dados'][np.isfinite(lido['dados'])])) == {1.0, 2.0, 3.0}
        assert figuras(pasta, estado, r) == ['importancia.png', 'correlacoes.png', 'manchas.png']
        assert relatorio(pasta / 'relatorio.pdf', estado, r, 'Talhão de exemplo', pasta / 'relatorio.png') == 6
        cab = (pasta / 'celulas.csv').read_text(encoding='utf-8-sig').splitlines()
        assert cab[0] == 'x_utm;y_utm;longitude;latitude;prod_t_ha;argila;argila_outra;altitude;ph;variedade;faixa'
        assert cab[1].split(';')[-1] in ('baixo', 'médio', 'alto') and cab[1].split(';')[-2] in ('A', 'B')
        for arq in ('relatorio.pdf', 'relatorio.png', 'manchas.png', 'importancia.csv'):
            assert (pasta / arq).stat().st_size > 800, arq
    print('saidas OK (4 CSV, GeoTIFF das manchas, 3 figuras e PDF de 6 páginas)')


if __name__ == '__main__':
    _autoteste()
