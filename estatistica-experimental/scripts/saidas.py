"""Arquivos de saída da análise: tabelas em CSV, o gráfico, a figura dos resíduos
e o relatório em PDF, no formato dos documentos da casa.

Os CSV saem com ponto e vírgula e vírgula decimal (abrem direto na planilha).

Teste embutido: python scripts/saidas.py
"""

import csv
import math
import textwrap

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from scipy import stats  # noqa: E402

from ensaio import num, p_txt, pct  # noqa: E402

# tokens do design system da casa (tema claro de impressão) e paleta de dataviz
T = dict(pagina='#FBFCF9', fg1='#121810', fg2='#3C4636', fg3='#6B7562', line='#D4DBCA', line_forte='#B4BFA8',
         verde='#2E8B1E', faixa='#EEF2E8')
DATAVIZ = ['#2E8B1E', '#C26A3D', '#4FB7C9', '#E8B33B', '#7D5BA6', '#8A7556', '#D1495B', '#3B6FB6']
ROTULO_DOC = 'agrônomo10X · Estatística experimental'
MONO = 'DejaVu Sans Mono'
LINHAS_POR_PAGINA = 22


def espacado(texto):
    return ' '.join(str(texto).upper())


def casas_para(valor):
    """Casas decimais para mostrar um valor dessa grandeza (médias da resposta)."""
    v = abs(float(valor)) if valor and np.isfinite(valor) else 1.0
    return 0 if v >= 1000 else 1 if v >= 100 else 2 if v >= 1 else 3 if v >= 0.1 else 4


def _casas_do_quadro(qm):
    if not qm or not np.isfinite(qm) or qm <= 0:
        return 2
    return int(min(6, max(0, 3 - math.floor(math.log10(qm)))))


def _coef(c):
    if c == 0:
        return '0'
    casas = int(min(8, max(0, 4 - 1 - math.floor(math.log10(abs(c))))))
    return num(abs(c), casas)


def equacao(eq):
    """Texto da equação ajustada: ŷ = a + bx − cx²."""
    c = eq['coeficientes']
    partes = [('−' if c[0] < 0 else '') + _coef(c[0])]
    for k, valor in enumerate(c[1:], 1):
        partes.append(f'{"−" if valor < 0 else "+"} {_coef(valor)}x' + ('' if k == 1 else {2: '²', 3: '³'}[k]))
    return 'ŷ = ' + ' '.join(partes)


# ------------------------------------------------------------------ CSV
def _br(v, casas=None):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return ''
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    texto = format(float(v), f'.{casas}f') if casas is not None else format(float(v), '.10g')
    return texto.replace('.', ',')


def _gravar(caminho, cabecalho, linhas):
    with open(caminho, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(cabecalho)
        w.writerows(linhas)
    return len(linhas)


def gravar_anova(caminho, quadro):
    return _gravar(caminho, ['fonte_de_variacao', 'gl', 'sq', 'qm', 'f', 'p'],
                   [[l['fonte'].strip(), _br(l['gl']), _br(l['sq']), _br(l.get('qm')), _br(l.get('f')), _br(l.get('p'))]
                    for l in quadro])


def gravar_medias(caminho, r):
    linhas = []
    for c in r['comparacoes']:
        contra = {x['tratamento']: x for x in c['teste'].get('contra_testemunha', [])}
        for i, nivel in enumerate(c['niveis']):
            d = contra.get(i)
            linhas.append([c['titulo'], nivel, c['n'][i], _br(c['medias'][i]), _br(c['medias_originais'][i]),
                           _br(c['ep'][i]), '' if c['letras'] is None else c['letras'][i],
                           _br(d['diferenca']) if d else '', _br(d['p']) if d else '',
                           ('sim' if d['difere'] else 'não') if d else ''])
    if r['regressao']:
        g = r['regressao']
        for i, nivel in enumerate(g['niveis']):
            linhas.append([f'Médias de {g["fator"]}', nivel, g['n'][i], _br(g['medias'][i]),
                           _br(g['medias_originais'][i]), '', '', '', '', ''])
    return _gravar(caminho, ['comparacao', 'nivel', 'n', 'media_na_escala_da_analise', 'media_original',
                             'erro_padrao_da_media', 'letras', 'diferenca_da_testemunha', 'p_dunnett',
                             'difere_da_testemunha'], linhas)


def gravar_pares(caminho, r):
    linhas = []
    for c in r['comparacoes']:
        for par in c['teste'].get('pares', []):
            linhas.append([c['titulo'], c['niveis'][par['i']], c['niveis'][par['j']], _br(par['diferenca']),
                           _br(par['p']), 'sim' if par['difere'] else 'não'])
    return _gravar(caminho, ['comparacao', 'nivel_1', 'nivel_2', 'diferenca', 'p', 'difere'], linhas)


# ------------------------------------------------------------------ moldura e tabelas
def _moldura(fig, titulo, subtitulo, kpis, rodape):
    fig.text(0.035, 0.955, espacado(ROTULO_DOC), fontsize=6.4, color=T['verde'], va='center', fontweight='bold')
    titulo = titulo if len(titulo) <= 44 else titulo[:43].rstrip() + '…'
    fig.text(0.035, 0.915, titulo, fontsize=15.5, color=T['fg1'], va='center', fontstyle='italic', fontweight='bold')
    subtitulo = subtitulo if len(subtitulo) <= 76 else subtitulo[:75].rstrip() + '…'
    fig.text(0.035, 0.878, subtitulo, fontsize=9.5, color=T['fg2'], va='center')
    x = 0.965
    for rotulo, valor, unidade in reversed(kpis):
        fig.text(x, 0.955, espacado(rotulo), fontsize=5.8, color=T['fg3'], va='center', ha='right')
        fig.text(x, 0.918, valor, fontsize=14, color=T['fg1'], va='center', ha='right', family=MONO, fontweight='bold')
        fig.text(x, 0.885, unidade, fontsize=7, color=T['fg3'], va='center', ha='right', family=MONO)
        x -= 0.028 + 0.0118 * max(len(valor), 7)
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.86, 0.86], color=T['line'], linewidth=0.8))
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.062, 0.062], color=T['line'], linewidth=0.8))
    fig.text(0.035, 0.044, rodape, fontsize=7, color=T['fg3'], va='center')
    fig.text(0.035, 0.026, 'O teste e a significância foram escolhidos pelo usuário. O relatório descreve o resultado; '
             'a interpretação agronômica é do responsável técnico.', fontsize=6.4, color=T['fg3'], va='center')
    fig.text(0.965, 0.036, 'OagronomIA', fontsize=10.5, color=T['fg1'], va='center', ha='right', fontstyle='italic',
             fontweight='bold')


def _pagina(titulo, subtitulo, kpis, rodape):
    fig = plt.figure(figsize=(11.69, 8.27), facecolor=T['pagina'])
    _moldura(fig, titulo, subtitulo, kpis, rodape)
    return fig


def _painel(fig, caixa):
    ax = fig.add_axes(caixa)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    return ax


def _titulo(ax, y, texto):
    ax.text(0, y, espacado(texto), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
    return y - 0.05


def _tabela(ax, y, colunas, linhas, passo=0.036, fonte=7.4, destaque=None):
    """Desenha uma tabela no painel. colunas = [(título, x, 'left'|'right', mono?)]. Devolve o y do fim."""
    for titulo, xc, alinh, _ in colunas:
        ax.text(xc, y, espacado(titulo), fontsize=5.4, color=T['fg3'], va='center', ha=alinh)
    y -= 0.02
    ax.plot([0, 1], [y, y], color=T['line'], linewidth=0.8)
    for k, linha in enumerate(linhas):
        topo = y - passo / 2
        if destaque is not None and k in destaque:
            ax.fill_between([0, 1], y - passo, y, color=T['faixa'], linewidth=0)
        for (_, xc, alinh, mono), texto in zip(colunas, linha):
            ax.text(xc, topo, texto, fontsize=fonte, color=T['fg1'], va='center', ha=alinh,
                    family=MONO if mono else None)
        y -= passo
        ax.plot([0, 1], [y, y], color=T['line'], linewidth=0.4)
    return y


def _texto(ax, y, linhas, largura, fonte=6.9, cor='fg2', passo=0.026, piso=0.0):
    """Parágrafos quebrados na largura. Para antes do piso e diz que há mais. Devolve o y do fim."""
    for k, linha in enumerate(linhas):
        partes = textwrap.wrap(linha, largura) or ['']
        if y - passo * len(partes) < piso:
            ax.text(0, y, f'… (mais {len(linhas) - k} no analise.json)', fontsize=fonte, color=T['fg3'], va='top')
            return y - passo
        ax.text(0, y, '\n'.join(partes), fontsize=fonte, color=T[cor], va='top', linespacing=1.4)
        y -= passo * len(partes) + 0.012
    return y


def _curto(texto, teto):
    texto = str(texto)
    return texto if len(texto) <= teto else texto[:teto - 1].rstrip() + '…'


def _eixo(ax, titulo=None):
    for lado in ('top', 'right'):
        ax.spines[lado].set_visible(False)
    for lado in ('bottom', 'left'):
        ax.spines[lado].set_color(T['line_forte'])
    ax.tick_params(labelsize=7, colors=T['fg3'])
    ax.set_facecolor('#FFFFFF')
    if titulo:
        largura = ax.get_position().width * ax.figure.get_figwidth()      # em polegadas
        ax.set_title(espacado(_curto(titulo, max(8, int(largura * 8.0)))), fontsize=7.4, color=T['fg1'],
                     fontweight='bold', loc='left', pad=8)


# ------------------------------------------------------------------ gráficos
def _ordem(c):
    if c['letras'] is None:   # Dunnett: a testemunha primeiro
        t = c['teste']['controle']
        return [t] + [i for i in range(len(c['niveis'])) if i != t]
    return sorted(range(len(c['niveis'])), key=lambda i: (-c['medias'][i], i))


def barras(ax, c, rotulo_y, original=False):
    """Barras das médias (maior primeiro), com o erro-padrão e as letras em cima."""
    ordem = _ordem(c)
    valores = [c['medias_originais' if original else 'medias'][i] for i in ordem]
    erros = None if original else [c['ep'][i] for i in ordem]
    x = np.arange(len(ordem))
    cores = [T['verde']] * len(ordem)
    marcas = None
    if c['letras'] is None:
        contra = {d['tratamento']: d for d in c['teste']['contra_testemunha']}
        cores = [T['line_forte']] + [T['verde'] if contra[i]['difere'] else '#A9C9A2' for i in ordem[1:]]
        marcas = ['testemunha'] + ['*' if contra[i]['difere'] else 'ns' for i in ordem[1:]]
    else:
        marcas = [c['letras'][i] for i in ordem]
    ax.bar(x, valores, color=cores, width=0.68, yerr=erros, error_kw=dict(ecolor=T['fg2'], elinewidth=0.9, capsize=2.5),
           zorder=2)
    topo = max(v + (e or 0) for v, e in zip(valores, erros or [0] * len(valores)))
    base = min(0.0, min(valores))
    folga = 0.03 * (topo - base or 1)
    muitas = len(ordem) > 12
    maior_marca = max(len(m) for m in marcas)
    for xi, v, e, m in zip(x, valores, erros or [0] * len(valores), marcas):
        ax.text(xi, v + (e or 0) + folga, m, ha='center', va='bottom', fontsize=6 if muitas else 8,
                rotation=90 if muitas else 0, color=T['fg1'], fontweight='bold')
    ax.set_ylim(base, topo + (6 + (0.5 * maior_marca if muitas else 0)) * folga)
    ax.set_xticks(x)
    longos = max(len(c['niveis'][i]) for i in ordem) > 9 or len(ordem) > 8
    ax.set_xticklabels([_curto(c['niveis'][i], 16) for i in ordem], rotation=90 if muitas else 35 if longos else 0,
                       ha='center' if muitas or not longos else 'right', fontsize=5.5 if muitas else 7)
    ax.set_ylabel(rotulo_y, fontsize=7.5, color=T['fg2'])
    ax.grid(axis='y', color=T['line'], linewidth=0.5, zorder=0)
    _eixo(ax, c['titulo'])


def interacao(ax, td, rotulo_y, original=False):
    """Uma linha por nível do fator das linhas, ao longo dos níveis do fator das colunas."""
    x = np.arange(len(td['niveis_colunas']))
    for i, nivel in enumerate(td['niveis_linhas']):
        ax.plot(x, td['medias_originais' if original else 'medias'][i], marker='o', markersize=4, linewidth=1.4,
                color=DATAVIZ[i % len(DATAVIZ)], label=str(nivel))
    ax.set_xticks(x)
    ax.set_xticklabels(td['niveis_colunas'])
    ax.set_xlabel(td['colunas'], fontsize=7.5, color=T['fg2'])
    ax.set_ylabel(rotulo_y, fontsize=7.5, color=T['fg2'])
    ax.grid(axis='y', color=T['line'], linewidth=0.5)
    ax.legend(title=td['linhas'], frameon=False, fontsize=7, title_fontsize=7)
    _eixo(ax, f'{td["linhas"]} × {td["colunas"]}')


def curva(ax, g, rotulo_y):
    """Médias por dose e a curva do grau escolhido."""
    eq = g['equacoes'][g['grau'] - 1]
    x = np.array(g['doses'])
    xs = np.linspace(x.min(), x.max(), 200)
    ax.plot(xs, np.polyval(eq['coeficientes'][::-1], xs), color=T['verde'], linewidth=1.6, zorder=2)
    ax.scatter(x, g['medias'], color=T['fg1'], s=22, zorder=3)
    if 'vertice' in eq and g['grau'] == 2:
        ax.axvline(eq['vertice']['x'], color=T['line_forte'], linewidth=0.8, linestyle='--', zorder=1)
    ax.set_xlabel(g['fator'], fontsize=7.5, color=T['fg2'])
    ax.set_ylabel(rotulo_y, fontsize=7.5, color=T['fg2'])
    ax.grid(color=T['line'], linewidth=0.5)
    ax.text(0.02, 0.97, f'{equacao(eq)}\nR² = {num(eq["r2"], 4)}', transform=ax.transAxes, fontsize=8, va='top',
            color=T['fg1'], family=MONO, bbox=dict(facecolor='#FFFFFF', edgecolor=T['line'], boxstyle='round,pad=0.4'))
    _eixo(ax, f'Regressão {eq["nome"]}')


def residuos(fig, caixas, quadro, niveis):
    """Três quadros: quantis normais, resíduo × valor ajustado e resíduo por tratamento."""
    pad = np.asarray(quadro['padronizados'], float)
    ax = fig.add_axes(caixas[0])
    teoricos = stats.norm.ppf((np.arange(1, len(pad) + 1) - 0.375) / (len(pad) + 0.25))
    ax.scatter(teoricos, np.sort(pad), s=12, color=T['verde'], zorder=3)
    lim = max(3.2, float(np.abs(pad).max()) + 0.3)
    ax.plot([-lim, lim], [-lim, lim], color=T['line_forte'], linewidth=0.9, zorder=1)
    ax.set_xlabel('quantil da normal', fontsize=7.5, color=T['fg2'])
    ax.set_ylabel('resíduo padronizado', fontsize=7.5, color=T['fg2'])
    _eixo(ax, 'Normalidade dos resíduos')
    ax = fig.add_axes(caixas[1])
    ax.scatter(quadro['ajustados'], pad, s=12, color=T['verde'], zorder=3)
    for h, estilo in ((0, '-'), (3, '--'), (-3, '--')):
        ax.axhline(h, color=T['line_forte'], linewidth=0.8, linestyle=estilo, zorder=1)
    ax.set_xlabel('valor ajustado pelo modelo', fontsize=7.5, color=T['fg2'])
    _eixo(ax, 'Resíduo × valor ajustado')
    ax = fig.add_axes(caixas[2])
    caselas = np.asarray(quadro['caselas'])
    codigos = {c: k for k, c in enumerate(np.unique(caselas))}
    posicao = np.array([codigos[c] for c in caselas])
    ax.scatter(posicao, pad, s=12, color=T['verde'], zorder=3)
    for h, estilo in ((0, '-'), (3, '--'), (-3, '--')):
        ax.axhline(h, color=T['line_forte'], linewidth=0.8, linestyle=estilo, zorder=1)
    ax.set_xticks(range(len(codigos)))
    longos = len(niveis) > 6 or max(len(str(n)) for n in niveis) > 8
    muitos = len(niveis) > 12
    ax.set_xticklabels([_curto(n, 14) for n in niveis][:len(codigos)], rotation=90 if muitos else 40 if longos else 0,
                       ha='center' if muitos or not longos else 'right',
                       fontsize=6.5 if not muitos else 5 if len(niveis) <= 36 else 3.5)
    _eixo(ax, 'Resíduo por tratamento')


def figura_dos_residuos(caminho, quadro, niveis, titulo):
    fig = plt.figure(figsize=(11.69, 4.4), facecolor=T['pagina'])
    fig.text(0.035, 0.94, espacado(titulo), fontsize=7.2, color=T['verde'], fontweight='bold', va='center')
    base, altura = (0.36, 0.46) if len(niveis) > 12 else (0.2, 0.6)
    residuos(fig, [[0.06, base, 0.26, altura], [0.39, base, 0.26, altura], [0.72, base, 0.255, altura]], quadro, niveis)
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


def figura_do_grafico(caminho, r, rotulo_y):
    """O gráfico principal sozinho: barras com letras, linhas da interação ou a curva da regressão."""
    if r['regressao']:
        fig, ax = plt.subplots(figsize=(7.6, 4.8), facecolor=T['pagina'])
        curva(ax, r['regressao'], rotulo_y)
    elif r['tabela_dupla']:
        fig, ax = plt.subplots(figsize=(7.6, 4.8), facecolor=T['pagina'])
        interacao(ax, r['tabela_dupla'], rotulo_y, original=r['transformacao']['aplicada'])
    else:
        n = len(r['comparacoes'])
        fig, eixos = plt.subplots(1, n, figsize=(7.6 if n == 1 else 11.5, 4.8), facecolor=T['pagina'], squeeze=False)
        for ax, c in zip(eixos[0], r['comparacoes']):
            barras(ax, c, rotulo_y, original=r['transformacao']['aplicada'])
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------ relatório
def _linhas_do_quadro(quadro, casas):
    saida = []
    for l in quadro:
        saida.append([l['fonte'], str(int(l['gl'])), num(l['sq'], casas),
                      num(l.get('qm'), casas) if l['fonte'] != 'Total' else '', num(l.get('f'), 2).replace('—', ''),
                      p_txt(l.get('p')).replace('—', '')])
    return saida


def _rotulo_y(r, meta):
    """Rótulo do eixo das médias. Barras e linhas mostram a escala original; a curva da regressão, a da análise."""
    unidade = f' ({meta["unidade"]})' if meta.get('unidade') else ''
    if r['transformacao']['aplicada'] and r['regressao']:
        return f'{r["resposta"]} · {r["transformacao"]["descricao"]}'
    return f'{r["resposta"]}{unidade}'


def _frase_das_letras(r, dupla=False):
    a = pct(r['alfa'])
    if r['teste'] == 'dunnett':
        return (f'* difere da testemunha pelo teste de Dunnett (bilateral) a {a}% de probabilidade; '
                'ns: não difere.')
    if r['teste'] == 'scott-knott':
        base = f'pertencem ao mesmo grupo pelo teste de Scott-Knott a {a}% de probabilidade'
    else:
        base = f'não diferem entre si pelo teste {"" if r["teste"] == "t" else "de "}{r["nome_do_teste"]} a {a}% de probabilidade'
    if dupla:
        return f'Médias seguidas da mesma letra minúscula na coluna e maiúscula na linha {base}.'
    return f'Médias seguidas da mesma letra {base}.'


def _tabela_de_medias(ax, y, c, r, casas, inicio=0, fim=None):
    ordem = _ordem(c)[inicio:fim]
    transformado = r['transformacao']['aplicada']
    dunnett = c['letras'] is None
    fator = _curto(c['fator'], 14)
    colunas = [(fator, 0.0, 'left', False), ('n', 0.47 if not transformado else 0.40, 'right', True)]
    if transformado:
        colunas += [('transf.', 0.62, 'right', True), ('original', 0.82, 'right', True)]
    else:
        colunas += [('média', 0.70, 'right', True)]
    if dunnett:
        colunas = [(fator, 0.0, 'left', False), ('n', 0.33, 'right', True), ('média', 0.50, 'right', True),
                   ('diferença', 0.70, 'right', True), ('p', 0.88, 'right', True), ('', 1.0, 'right', False)]
        contra = {d['tratamento']: d for d in c['teste']['contra_testemunha']}
    else:
        colunas += [('grupo' if r['teste'] == 'scott-knott' else 'letras', 1.0, 'right', False)]
    casas_t = casas if not transformado else 4
    linhas = []
    for i in ordem:
        nome = c['niveis'][i] if len(c['niveis'][i]) <= 30 else c['niveis'][i][:29] + '…'
        linha = [nome, str(c['n'][i])]
        if dunnett:
            d = contra.get(i)
            linha += [num(c['medias'][i], casas_t), num(d['diferenca'], casas_t) if d else 'testemunha',
                      p_txt(d['p']) if d else '', ('*' if d['difere'] else 'ns') if d else '']
        else:
            linha += [num(c['medias'][i], casas_t)] + ([num(c['medias_originais'][i], casas)] if transformado else [])
            linha += [c['letras'][i]]
        linhas.append(linha)
    passo = 0.036 if len(linhas) <= 14 else 0.03
    return _tabela(ax, y, colunas, linhas, passo=passo)


def _nota_do_teste(c, r, casas):
    t = c['teste']
    partes = [f'Erro usado: {c["erro"]["nome"]} (QM = {num(c["erro"]["qm"], _casas_do_quadro(c["erro"]["qm"]))}, '
              f'GL = {num(c["erro"]["gl"], 0 if float(c["erro"]["gl"]).is_integer() else 1)}).']
    if t.get('dms') is not None:
        partes.append(f'Diferença mínima significativa: {num(t["dms"], casas if not r["transformacao"]["aplicada"] else 4)}.')
    if t.get('critico') is not None:
        partes.append(f'Valor crítico de Dunnett: {num(t["critico"], 3)}.')
    if t.get('amplitudes_criticas'):
        amp = t['amplitudes_criticas']
        partes.append('Amplitudes críticas: ' + '; '.join(
            f'{p} médias = {num(v, casas if not r["transformacao"]["aplicada"] else 4)}' for p, v in list(amp.items())[:6])
            + ('…' if len(amp) > 6 else '') + '.')
    return partes + t.get('notas', [])


def relatorio(caminho_pdf, caminho_png, r, meta):
    """Relatório em A4 deitado: análise de variância e pressupostos; médias; desdobramento; resíduos."""
    quadro = r['quadro']
    transformado = r['transformacao']['aplicada']
    casas = meta.get('casas') if meta.get('casas') is not None else casas_para(r['media_original'])
    casas_q = _casas_do_quadro(r['residuo']['qm'])
    a = pct(r['alfa'])
    fonte_principal = (f'{r["fatores"][0]["nome"]} × {r["fatores"][1]["nome"]}' if len(r['fatores']) == 2
                       else r['fatores'][0]['nome'])
    p_principal = next(l['p'] for l in quadro if l['fonte'].strip() == fonte_principal)
    kpis = [('Parcelas', str(r['n']), 'analisadas'),
            ('Média geral', num(r['media'], casas if not r['transformacao']['aplicada'] else 4),
             (meta.get('unidade') or 'resposta') if not r['transformacao']['aplicada'] else 'transformada'),
            ('CV', num(r['cv'], 2) if not r.get('cv_a') else f'{num(r["cv_a"], 1)} · {num(r["cv"], 1)}',
             '%' if not r.get('cv_a') else '% (a) · (b)'),
            ('p do F', p_txt(p_principal), 'interação' if len(r['fatores']) == 2 else fonte_principal[:14])]
    rodape = f'comunidade agrônomo10X · gerado em {meta["data"]} · arquivo {meta["arquivo"]}'
    titulo = meta['titulo']
    o_que = (f'regressão de grau {r["regressao"]["grau"]}' if r['regressao'] else f'teste {r["nome_do_teste"]}')
    subtitulo = f'{r["resposta"]} · {o_que} a {a}%'
    rotulo_y = _rotulo_y(r, meta)

    with PdfPages(caminho_pdf) as pdf:
        # ---- página 1: análise de variância e pressupostos
        fig = _pagina(titulo, subtitulo, kpis, rodape)
        esq = _painel(fig, [0.035, 0.085, 0.555, 0.755])
        y = _titulo(esq, 0.985, 'Quadro da análise de variância')
        colunas = [('Fonte de variação', 0.0, 'left', False), ('GL', 0.40, 'right', True), ('SQ', 0.58, 'right', True),
                   ('QM', 0.75, 'right', True), ('F', 0.87, 'right', True), ('p', 1.0, 'right', True)]
        passo = 0.04 if len(quadro) <= 9 else 0.034
        y = _tabela(esq, y, colunas, _linhas_do_quadro(quadro, casas_q), passo=passo)
        y -= 0.04
        y = _titulo(esq, y, f'Teste F a {a}%')
        y = _texto(esq, y, r['frases'], 104, fonte=7.2, piso=0.16)
        y -= 0.015
        y = _titulo(esq, y, 'O ensaio')
        transformacao = r['transformacao']['descricao']
        _texto(esq, y, [r['descricao'], f'Resposta: {r["resposta"]} · escala: {transformacao}.'], 104, fonte=7.2)
        dir_ = _painel(fig, [0.635, 0.085, 0.33, 0.755])
        y = _titulo(dir_, 0.985, 'Pressupostos (sobre os resíduos)')
        pr = r['pressupostos']
        linhas = []
        for nome, chave_e, rotulo in (('shapiro', 'w', 'Shapiro-Wilk (normalidade)'),
                                      ('bartlett', 'estatistica', 'Bartlett (variâncias)'),
                                      ('levene', 'estatistica', 'Levene (variâncias)')):
            t = pr[nome]
            linhas.append([rotulo, num(t[chave_e], 3) if t else 'não calculado', p_txt(t['p']) if t else ''])
        linhas.append([f'Resíduos além de ±{num(pr["limite_discrepante"], 0)}', str(len(pr['discrepantes'])), ''])
        y = _tabela(dir_, y, [('Teste', 0.0, 'left', False), ('Estatística', 0.78, 'right', True),
                              ('p', 1.0, 'right', True)], linhas)
        y -= 0.03
        y = _texto(dir_, y, pr['notas'], 62, fonte=6.5, cor='fg3', piso=0.35)
        y -= 0.02
        y = _titulo(dir_, y, 'Avisos')
        _texto(dir_, y, r['avisos'] or ['Nenhum aviso nesta análise.'], 60, piso=0.02)
        pdf.savefig(fig)
        fig.savefig(caminho_png, dpi=140)
        plt.close(fig)

        # ---- página 2 em diante: médias
        if r['regressao']:
            g = r['regressao']
            fig = _pagina(titulo, f'{r["resposta"]} · regressão polinomial em {g["fator"]}', kpis, rodape)
            esq = _painel(fig, [0.035, 0.085, 0.42, 0.755])
            y = _titulo(esq, 0.985, 'Equações ajustadas às médias')
            linhas = [[f'{eq["grau"]} · {eq["nome"]}', equacao(eq), num(eq['r2'], 4)] for eq in g['equacoes']]
            y = _tabela(esq, y, [('Grau', 0.0, 'left', False), ('Equação', 0.2, 'left', True), ('R²', 1.0, 'right', True)],
                        linhas, fonte=6.8, destaque={g['grau'] - 1})
            y -= 0.02
            eq = g['equacoes'][g['grau'] - 1]
            notas = [f'O grau {g["grau"]} foi o escolhido pelo usuário; as outras equações estão aqui para comparação.',
                     'R² é a parte da variação entre as médias dos tratamentos que a equação descreve.']
            if 'vertice' in eq:
                v = eq['vertice']
                notas.append(f'A parábola ajustada tem o ponto de {v["tipo"]} em x = {num(v["x"], casas_para(v["x"]))} '
                             f'(ŷ = {num(v["y"], casas)}), dentro do intervalo testado. É uma propriedade da curva, não '
                             'uma recomendação de dose.')
            y = _texto(esq, y, notas, 78, fonte=6.8, cor='fg3')
            y -= 0.03
            y = _titulo(esq, y, f'Médias por nível de {g["fator"]}')
            _tabela(esq, y, [(g['fator'], 0.0, 'left', False), ('n', 0.4, 'right', True), ('média', 0.7, 'right', True),
                             ('estimada', 1.0, 'right', True)],
                    [[nivel, str(n), num(m, casas if not r['transformacao']['aplicada'] else 4),
                      num(float(np.polyval(eq['coeficientes'][::-1], x)), casas if not r['transformacao']['aplicada'] else 4)]
                     for nivel, n, m, x in zip(g['niveis'], g['n'], g['medias'], g['doses'])][:12], passo=0.034)
            curva(fig.add_axes([0.53, 0.16, 0.43, 0.62]), g, rotulo_y)
            pdf.savefig(fig)
            plt.close(fig)
        elif r['tabela_dupla']:
            td = r['tabela_dupla']
            fig = _pagina(titulo, f'{r["resposta"]} · desdobramento da interação · {r["nome_do_teste"]} a {a}%', kpis,
                          rodape)
            esq = _painel(fig, [0.035, 0.085, 0.50, 0.755])
            y = _titulo(esq, 0.985, f'Médias de {td["linhas"]} (linhas) × {td["colunas"]} (colunas)')
            nc = len(td['niveis_colunas'])
            largura = 0.74 / nc
            colunas = [(_curto(td['linhas'], 14), 0.0, 'left', False)] + [
                (_curto(n, max(4, int(largura / 0.0165))), 0.26 + largura * (j + 1), 'right', True)
                for j, n in enumerate(td['niveis_colunas'])]
            casas_t = casas if not r['transformacao']['aplicada'] else 4
            linhas = [[str(nivel)[:22]] + [f'{num(td["medias"][i][j], casas_t)} {td["minusculas"][i][j]}{td["maiusculas"][i][j]}'
                                           for j in range(nc)] for i, nivel in enumerate(td['niveis_linhas'])]
            fonte = 7.4 if nc <= 4 else 6.4 if nc <= 6 else 5.4
            y = _tabela(esq, y, colunas, linhas, passo=0.04 if len(linhas) <= 12 else 0.03, fonte=fonte)
            y -= 0.03
            notas = [_frase_das_letras(r, dupla=True)]
            notas += _nota_do_teste(r['comparacoes'][0], r, casas)[:1] if r['tipo'] == 'subdividida' else []
            if r['transformacao']['aplicada']:
                notas.append(f'Médias na escala transformada ({r["transformacao"]["descricao"]}).')
            _texto(esq, y, notas, 96, fonte=6.8, cor='fg3')
            interacao(fig.add_axes([0.60, 0.16, 0.36, 0.62]), td, rotulo_y, original=transformado)
            if transformado:
                fig.text(0.60, 0.10, 'Linhas: médias na escala original. As letras vêm da escala transformada.',
                         fontsize=6.6, color=T['fg3'])
            pdf.savefig(fig)
            plt.close(fig)
            # desdobramento: o F de cada fatia
            fatias = [[c['titulo'][:58], str(int(c['f']['gl'])), num(c['f']['sq'], casas_q), num(c['f']['qm'], casas_q),
                       num(c['f']['f'], 2), p_txt(c['f']['p'])] for c in r['comparacoes']]
            for ini in range(0, len(fatias), LINHAS_POR_PAGINA):
                fig = _pagina(titulo, f'{r["resposta"]} · desdobramento: o teste F de cada fatia', kpis, rodape)
                ax = _painel(fig, [0.035, 0.085, 0.93, 0.755])
                y = _titulo(ax, 0.985, 'Efeito de um fator dentro de cada nível do outro')
                y = _tabela(ax, y, [('Fonte de variação', 0.0, 'left', False), ('GL', 0.52, 'right', True),
                                    ('SQ', 0.66, 'right', True), ('QM', 0.80, 'right', True), ('F', 0.90, 'right', True),
                                    ('p', 1.0, 'right', True)], fatias[ini:ini + LINHAS_POR_PAGINA], passo=0.03)
                erros = list(dict.fromkeys(f'{c["fator"]} dentro de {c["dentro"]["fator"]}: {c["erro"]["nome"]} '
                                           f'(QM = {num(c["erro"]["qm"], casas_q)}, GL = '
                                           f'{num(c["erro"]["gl"], 0 if float(c["erro"]["gl"]).is_integer() else 1)})'
                                           for c in r['comparacoes']))
                _texto(ax, y - 0.03, ['Erro usado em cada desdobramento: ' + '; '.join(erros) + '.'], 170, fonte=6.8,
                       cor='fg3')
                pdf.savefig(fig)
                plt.close(fig)
        else:
            for c in r['comparacoes']:
                total = len(c['niveis'])
                for ini in range(0, total, LINHAS_POR_PAGINA):
                    fig = _pagina(titulo, f'{r["resposta"]} · {c["titulo"]} · {r["nome_do_teste"]} a {a}%', kpis, rodape)
                    esq = _painel(fig, [0.035, 0.085, 0.40, 0.755])
                    parte = '' if total <= LINHAS_POR_PAGINA else f' ({ini + 1} a {min(total, ini + LINHAS_POR_PAGINA)} de {total})'
                    y = _titulo(esq, 0.985, c['titulo'] + parte)
                    y = _tabela_de_medias(esq, y, c, r, casas, ini, ini + LINHAS_POR_PAGINA)
                    if ini + LINHAS_POR_PAGINA >= total:
                        _texto(esq, y - 0.03, [_frase_das_letras(r)] + _nota_do_teste(c, r, casas), 76, fonte=6.8,
                               cor='fg3', piso=0.0)
                    if ini == 0:
                        caixa = [0.52, 0.29, 0.44, 0.49] if total > 12 else [0.52, 0.20, 0.44, 0.58]
                        barras(fig.add_axes(caixa), c, rotulo_y, original=transformado)
                        fig.text(0.52, 0.10, 'Barras: média na escala original. As letras vêm da escala transformada.'
                                 if transformado else
                                 'Barras: média; hastes: erro-padrão da média, pelo quadrado médio do erro.',
                                 fontsize=6.6, color=T['fg3'])
                    pdf.savefig(fig)
                    plt.close(fig)

        # ---- última página: resíduos
        fig = _pagina(titulo, f'{r["resposta"]} · resíduos do modelo', kpis, rodape)
        base, altura = (0.29, 0.47) if len(meta['niveis_das_caselas']) > 12 else (0.2, 0.56)
        residuos(fig, [[0.06, base, 0.26, altura], [0.39, base, 0.26, altura], [0.72, base, 0.245, altura]],
                 r['_quadro'], meta['niveis_das_caselas'])
        fig.text(0.06, 0.10, 'Resíduo padronizado: o resíduo dividido pelo seu desvio-padrão. As linhas tracejadas marcam ±3. '
                 'Pontos fora da reta, no primeiro quadro, indicam afastamento da distribuição normal.', fontsize=6.8,
                 color=T['fg3'])
        pdf.savefig(fig)
        plt.close(fig)


if __name__ == '__main__':
    import os
    import tempfile

    import ensaio
    import sintetico

    assert equacao({'coeficientes': [6200.0, 22.0, -0.07]}) == 'ŷ = 6.200 + 22,00x − 0,07000x²'
    assert casas_para(3500) == 0 and casas_para(45.2) == 2 and casas_para(0.05) == 4 and _casas_do_quadro(32000) == 0
    assert _br(0.5) == '0,5' and _br(None) == '' and _br(float('nan')) == '' and _br(3) == '3'

    def caselas(ens):
        f = ens['fatores']
        return f[0]['rotulos'] if len(f) == 1 else [f'{a_} · {b_}' for a_ in f[0]['rotulos'] for b_ in f[1]['rotulos']]

    with tempfile.TemporaryDirectory() as pasta:
        p = os.path.join
        casos = [('dbc', dict(teste='tukey', alfa=0.05)), ('dbc', dict(teste='dunnett', alfa=0.05, testemunha='Testemunha')),
                 ('dbc', dict(teste='scott-knott', alfa=0.05, transformacao='log')),
                 ('fatorial', dict(teste='tukey', alfa=0.05)), ('fatorial-sem-interacao', dict(teste='snk', alfa=0.01)),
                 ('subdividida', dict(teste='tukey', alfa=0.05, desdobrar='sim')),
                 ('doses', dict(alfa=0.05, regressao=True, grau=2)), ('dic-desbalanceado', dict(teste='t', alfa=0.05))]
        for k, (qual, kw) in enumerate(casos):
            ens = sintetico.ensaio(qual)
            r = ensaio.rodar(ens, **kw)
            meta = {'titulo': sintetico.TITULOS[qual], 'arquivo': 'exemplo-inventado.csv', 'data': '14/11/2026',
                    'unidade': 'kg/ha', 'casas': None, 'niveis_das_caselas': caselas(ens)}
            relatorio(p(pasta, f'r{k}.pdf'), p(pasta, f'r{k}.png'), r, meta)
            figura_do_grafico(p(pasta, f'g{k}.png'), r, 'kg/ha')
            figura_dos_residuos(p(pasta, f'd{k}.png'), r['_quadro'], caselas(ens), 'Resíduos')
            assert os.path.getsize(p(pasta, f'r{k}.pdf')) > 20000 and os.path.getsize(p(pasta, f'g{k}.png')) > 8000, qual
            assert gravar_anova(p(pasta, 'anova.csv'), r['quadro']) == len(r['quadro'])
            n = gravar_medias(p(pasta, 'medias.csv'), r)
            assert n == (sum(len(c['niveis']) for c in r['comparacoes']) or len(r['regressao']['niveis']))
            gravar_pares(p(pasta, 'pares.csv'), r)
        texto = open(p(pasta, 'anova.csv'), encoding='utf-8-sig').read().splitlines()
        assert texto[0] == 'fonte_de_variacao;gl;sq;qm;f;p' and texto[-1].startswith('Total;') and ',' in texto[1]
    print('saidas OK')
