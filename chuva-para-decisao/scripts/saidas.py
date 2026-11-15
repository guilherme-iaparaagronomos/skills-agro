"""Arquivos de saída: tabelas em CSV, as figuras, o relato em texto e o relatório
em PDF, no formato dos documentos da casa.

Os CSV saem com ponto e vírgula e vírgula decimal (abrem direto na planilha).

Teste embutido: python scripts/saidas.py
"""

import csv
import datetime as dt
import json
import os
import textwrap

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

import relato  # noqa: E402
from leitura import MESES, br, dm, dma  # noqa: E402

# tokens do design system da casa (tema claro de impressão) e paleta de dataviz
T = dict(pagina='#FBFCF9', fg1='#121810', fg2='#3C4636', fg3='#6B7562', line='#D4DBCA', line_forte='#B4BFA8',
         verde='#2E8B1E', faixa='#EEF2E8')
DATAVIZ = ['#2E8B1E', '#C26A3D', '#4FB7C9', '#E8B33B', '#7D5BA6', '#8A7556']
CHUVA = ['#D9DDD3', '#F4EBD3', '#BFE3B4', '#6DBB5C', '#1F6B14']      # sem dado, seco, e três faixas de chuva
ROTULO_DOC = 'agrônomo10X · Chuva para decisão'
MONO = 'DejaVu Sans Mono'
RODAPE = ('Descrição do registro de chuva, não previsão. A decisão de plantio e de manejo é do responsável técnico. '
          'Fonte: pluviômetros e satélites da comunidade agrônomo10X (OagronomIA).')


def espacado(texto):
    return ' '.join(str(texto).upper())


# ------------------------------------------------------------------ CSV e JSON
def _n(v, casas=1):
    if v is None:
        return ''
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return format(float(v), f'.{casas}f').replace('.', ',')


def _gravar(caminho, cabecalho, linhas):
    with open(caminho, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(cabecalho)
        w.writerows(linhas)
    return len(linhas)


def _am(par):
    return '' if par is None else f'{par[0]}-{par[1]:02d}'


def gravar_mensal(pasta, m):
    cortes = m['cortes']
    _gravar(os.path.join(pasta, 'calendario_mensal.csv'),
            ['mes', 'anos', 'mediana_mm', 'p20_mm', 'p80_mm', 'menor_mm', 'ano_do_menor', 'maior_mm', 'ano_do_maior',
             'media_1991_2020_da_ferramenta_mm'] + [f'anos_abaixo_de_{_n(c, 0)}_mm' for c in cortes],
            [[l['nome'], l['n'], _n(l['mediana']), _n(l['p20']), _n(l['p80']), _n(l['menor']), l['ano_menor'],
              _n(l['maior']), l['ano_maior'], _n(l['normal'])] + [l['abaixo'][c] for c in cortes]
             for l in m['calendario']])
    aguas = {l['rotulo']: l for l in (m['aguas']['linhas'] if m['aguas'] else [])}
    gdd = {l['rotulo'][:4]: l for l in (m['gdd']['linhas'] if m['gdd'] else [])}
    linhas = []
    for t in m['totais'][0]:
        a, g = aguas.get(t['rotulo']), gdd.get(t['rotulo'][:4])
        linhas.append([t['rotulo'], _n(t['total']), _n(t['posicao']), _am(a['inicio']) if a else '',
                       _am(a['fim']) if a else '', _n(a['meses_de_aguas']) if a else '',
                       _n(g['soma']) if g else '', _n(g['dias']) if g else ''])
    _gravar(os.path.join(pasta, 'anos_agricolas.csv'),
            ['ano_agricola', 'total_mm', 'posicao_1_e_o_mais_chuvoso', 'aguas_firmaram_em', 'aguas_terminaram_em',
             'meses_de_aguas', 'graus_dia_no_periodo_pedido', 'dias_ate_o_alvo_de_graus_dia'], linhas)


def gravar_janela(pasta, j):
    cortes, anos = j['cortes'], j['anos']
    _gravar(os.path.join(pasta, 'janela_decendios.csv'),
            ['decendio', 'anos', 'mediana_mm', 'menor_mm', 'ano_do_menor', 'maior_mm', 'ano_do_maior']
            + [f'anos_com_pelo_menos_{_n(c, 0)}_mm' for c in cortes] + ['anos_sem_dia_de_chuva']
            + [f'total_{a}' for a in anos],
            [[l['nome'], l['n'], _n(l['mediana']), _n(l['menor']), l['ano_menor'], _n(l['maior']), l['ano_maior']]
             + [l['acima'][c] for c in cortes] + [l['sem_chuva']] + [_n(l['por_ano'].get(a)) for a in anos]
             for l in j['decendios'] if l['inteiro'] and l.get('n')])
    dias = [x['dias'] for x in j['veranicos']['resumo']]
    inicio = {l['rotulo']: l for l in (j['inicio']['linhas'] if j['inicio'] else [])}
    linhas = []
    for l in j['veranicos']['linhas']:
        f, m, i = l['da_ferramenta'] or {}, l['maior'] or {}, inicio.get(l['rotulo'], {})
        linhas.append([l['rotulo'], _n(l['total']), _n(l['dias_chuva']), l['confianca'], _n(f.get('dias')),
                       dma(f.get('de')) if f.get('de') else '', dma(f.get('ate')) if f.get('ate') else '',
                       _n(m.get('dias')), dma(m['de']) if m else '', dma(m['ate']) if m else '',
                       ('sim' if m['borda'] else 'não') if m else '']
                      + [l['quantos'][d] for d in dias]
                      + [i.get('situacao', ''), dma(i['data']) if i.get('data') else '', _n(i.get('falsos'))])
    _gravar(os.path.join(pasta, 'janela_por_ano.csv'),
            ['ano', 'total_mm_da_ferramenta', 'dias_de_chuva_da_ferramenta', 'confianca_da_ferramenta',
             'veranico_max_da_ferramenta_dias', 'veranico_da_ferramenta_de', 'veranico_da_ferramenta_ate',
             'maior_sequencia_seca_dias', 'sequencia_seca_de', 'sequencia_seca_ate', 'encosta_na_borda_da_janela']
            + [f'sequencias_de_{d}_dias_ou_mais' for d in dias]
            + ['inicio_das_aguas_situacao', 'inicio_das_aguas_data', 'dias_de_falso_inicio'], linhas)


def gravar_fim(pasta, x, duracao):
    dur = {d['rotulo'][-2:]: d for d in (duracao or [])}
    _gravar(os.path.join(pasta, 'fim_das_aguas_por_ano.csv'),
            ['ano', 'situacao', 'fim_das_aguas', 'dias_do_inicio_ao_fim'],
            [[l['rotulo'], l['situacao'], dma(l['data']) if l['data'] else '',
              _n(dur[l['rotulo'][-2:]]['dias']) if l['data'] and l['rotulo'][-2:] in dur else '']
             for l in x['datas']['linhas']])


def _simples(o):
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    return str(o)


def gravar_json(caminho, r):
    def limpo(o):
        if isinstance(o, dict):
            return {str(k): limpo(v) for k, v in o.items() if not str(k).startswith('_') and k not in ('janelas', 'meses')}
        if isinstance(o, (list, tuple)):
            return [limpo(v) for v in o]
        return o
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(limpo(r), f, ensure_ascii=False, indent=1, default=_simples)


# ------------------------------------------------------------------ moldura e tabelas
def _moldura(fig, titulo, subtitulo, kpis):
    fig.text(0.035, 0.955, espacado(ROTULO_DOC), fontsize=6.4, color=T['verde'], va='center', fontweight='bold')
    titulo = titulo if len(titulo) <= 44 else titulo[:43].rstrip() + '…'
    fig.text(0.035, 0.915, titulo, fontsize=15.5, color=T['fg1'], va='center', fontstyle='italic', fontweight='bold')
    subtitulo = subtitulo if len(subtitulo) <= 84 else subtitulo[:83].rstrip() + '…'
    fig.text(0.035, 0.878, subtitulo, fontsize=9.5, color=T['fg2'], va='center')
    x = 0.965
    for rotulo, valor, unidade in reversed(kpis):
        fig.text(x, 0.955, espacado(rotulo), fontsize=5.8, color=T['fg3'], va='center', ha='right')
        fig.text(x, 0.918, valor, fontsize=14, color=T['fg1'], va='center', ha='right', family=MONO, fontweight='bold')
        fig.text(x, 0.885, unidade, fontsize=7, color=T['fg3'], va='center', ha='right', family=MONO)
        x -= 0.03 + 0.0118 * max(len(valor), len(rotulo) * 0.62, 7)
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.86, 0.86], color=T['line'], linewidth=0.8))
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.062, 0.062], color=T['line'], linewidth=0.8))
    for k, parte in enumerate(textwrap.wrap(RODAPE, 150)[:2]):
        fig.text(0.035, 0.044 - 0.018 * k, parte, fontsize=6.6, color=T['fg3'], va='center')
    fig.text(0.965, 0.036, 'OagronomIA', fontsize=10.5, color=T['fg1'], va='center', ha='right', fontstyle='italic',
             fontweight='bold')


def _pagina(titulo, subtitulo, kpis=()):
    fig = plt.figure(figsize=(11.69, 8.27), facecolor=T['pagina'])
    _moldura(fig, titulo, subtitulo, kpis)
    return fig


def _painel(fig, caixa):
    ax = fig.add_axes(caixa)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    return ax


def _titulo(ax, y, texto):
    k = 0.755 / ax.get_position().height        # os recuos valem para o painel de página inteira
    ax.text(0, y, espacado(texto), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
    ax.plot([0, 0.06], [y - 0.034 * k, y - 0.034 * k], color=T['verde'], linewidth=1.6)
    return y - 0.065 * k


def _tabela(ax, y, colunas, linhas, passo=0.036, fonte=7.2, destaque=()):
    """colunas = [(título, x, 'left'|'right', mono?)]. Devolve o y do fim."""
    for titulo, xc, alinh, _ in colunas:
        ax.text(xc, y, espacado(titulo), fontsize=5.2, color=T['fg3'], va='center', ha=alinh)
    y -= 0.022
    ax.plot([0, 1], [y, y], color=T['line'], linewidth=0.8)
    for k, linha in enumerate(linhas):
        if k in destaque:
            ax.fill_between([0, 1], y - passo, y, color=T['faixa'], linewidth=0)
        for (_, xc, alinh, mono), texto in zip(colunas, linha):
            ax.text(xc, y - passo / 2, texto, fontsize=fonte, color=T['fg1'], va='center', ha=alinh,
                    family=MONO if mono else None)
        y -= passo
        ax.plot([0, 1], [y, y], color=T['line'], linewidth=0.4)
    return y


def _texto(ax, y, frases, largura, fonte=7.0, passo=0.03, piso=0.0, marcador='– '):
    """Frases quebradas na largura. Devolve (y do fim, quantas couberam)."""
    for k, frase in enumerate(frases):
        partes = textwrap.wrap(marcador + frase, largura, subsequent_indent='  ') or ['']
        if y - passo * len(partes) < piso:
            return y, k
        ax.text(0, y, '\n'.join(partes), fontsize=fonte, color=T['fg2'], va='top', linespacing=1.42)
        y -= passo * len(partes) + passo * 0.35
    return y, len(frases)


def _eixo(ax, titulo=None):
    for lado in ('top', 'right'):
        ax.spines[lado].set_visible(False)
    for lado in ('bottom', 'left'):
        ax.spines[lado].set_color(T['line_forte'])
    ax.tick_params(labelsize=7, colors=T['fg3'])
    ax.set_facecolor('#FFFFFF')
    if titulo:
        ax.set_title(espacado(titulo), fontsize=7.4, color=T['fg1'], fontweight='bold', loc='left', pad=8)


# ------------------------------------------------------------------ gráficos
def grafico_calendario(ax, cal):
    x = np.arange(len(cal))
    med = np.array([l['mediana'] for l in cal])
    baixo = med - np.array([l['p20'] for l in cal])
    cima = np.array([l['p80'] for l in cal]) - med
    ax.bar(x, med, color=T['verde'], width=0.66, zorder=2)
    ax.errorbar(x, med, yerr=[baixo, cima], fmt='none', ecolor=T['fg1'], elinewidth=1.0, capsize=3, zorder=3)
    normais = [(k, l['normal']) for k, l in enumerate(cal) if l['normal'] is not None]
    if normais:
        ax.scatter([n[0] for n in normais], [n[1] for n in normais], marker='D', s=16, color=DATAVIZ[1], zorder=4)
    ax.set_xticks(x)
    ax.set_xticklabels([l['nome'] for l in cal])
    ax.set_ylabel('mm no mês', fontsize=7.5, color=T['fg2'])
    ax.set_ylim(0, None)
    ax.grid(axis='y', color=T['line'], linewidth=0.5, zorder=0)
    _eixo(ax, 'Chuva por mês do calendário')
    legenda = 'barra: mediana · traço: P20 a P80' + (' · losango: média 1991–2020 da ferramenta' if normais else '')
    ax.text(0.0, -0.13, legenda, transform=ax.transAxes, fontsize=6.4, color=T['fg3'], va='top')


def grafico_totais(ax, linhas, resumo):
    validos = [l for l in linhas if l['total'] is not None]
    x = np.arange(len(validos))
    ax.bar(x, [l['total'] for l in validos], color=T['verde'], width=0.7, zorder=2)
    if resumo:
        ax.axhline(resumo['mediana'], color=T['fg1'], linewidth=0.9, linestyle='--', zorder=3)
        ax.text(-0.5, resumo['mediana'], f'mediana {br(resumo["mediana"], 0)} ', fontsize=6.4, color=T['fg1'],
                va='bottom', ha='left', bbox=dict(facecolor='#FFFFFF', edgecolor='none', alpha=0.85, pad=1.2))
    ax.set_xticks(x)
    ax.set_xticklabels([l['rotulo'] for l in validos], rotation=90, fontsize=5.6 if len(validos) > 18 else 6.6)
    ax.set_ylabel('mm no ano agrícola', fontsize=7.5, color=T['fg2'])
    ax.grid(axis='y', color=T['line'], linewidth=0.5, zorder=0)
    _eixo(ax, 'Total por ano agrícola')


def grafico_decendios(ax, linhas, cortes, n):
    inteiros = [l for l in linhas if l['inteiro'] and l.get('n')]
    x = np.arange(len(inteiros))
    largura = 0.8 / max(len(cortes), 1)
    for k, c in enumerate(cortes):
        ax.bar(x - 0.4 + largura * (k + 0.5), [l['acima'][c] for l in inteiros], width=largura * 0.92,
               color=DATAVIZ[k % len(DATAVIZ)], label=f'pelo menos {br(c, 0)} mm', zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels([l['nome'].replace(' dec. de ', '\n') for l in inteiros], fontsize=6.6)
    ax.set_ylim(0, n + 0.6)
    ax.set_yticks(range(0, n + 1, 1 if n <= 12 else 2 if n <= 24 else 5))
    ax.set_ylabel(f'anos (de {n})', fontsize=7.5, color=T['fg2'])
    ax.grid(axis='y', color=T['line'], linewidth=0.5, zorder=0)
    ax.legend(frameon=False, fontsize=6.6, loc='upper left', ncol=len(cortes), bbox_to_anchor=(0, -0.2))
    _eixo(ax, 'Em quantos anos choveu o corte, por decêndio')


def grafico_dias(ax, janelas, rotulos, seco_mm, inicio=None, fim=None):
    """Uma linha por ano (o mais recente em cima), um quadrinho por dia, com a data da regra marcada."""
    n_dias = max(len(j['mm']) for j in janelas)
    matriz = np.full((len(janelas), n_dias), -1.0)
    for k, j in enumerate(reversed(janelas)):
        for d, v in enumerate(j['mm']):
            matriz[k, d] = -1.0 if v is None else v
    alto = max(25.0, seco_mm + 20)
    medio = max(10.0, seco_mm + 5)
    norma = BoundaryNorm([-2, -0.5, seco_mm, medio, alto, 1e9], 5)
    ax.imshow(matriz, aspect='auto', cmap=ListedColormap(CHUVA), norm=norma, interpolation='nearest')
    ax.set_yticks(range(len(janelas)))
    ax.set_yticklabels(list(reversed(rotulos)), fontsize=6.2, family=MONO)
    ref = janelas[-1]
    marcas = [(d, ref['inicio'] + dt.timedelta(days=d)) for d in range(n_dias)]
    marcas = [(d, x) for d, x in marcas if x.day in (1, 11, 21)]
    ax.set_xticks([d for d, _ in marcas])
    ax.set_xticklabels([dm(x) for _, x in marcas], fontsize=6.2)
    for conjunto, marca in ((inicio, 'v'), (fim, '^')):
        for l in (conjunto or []):
            if l['situacao'] == 'ok' and l['rotulo'] in rotulos:
                linha = len(janelas) - 1 - rotulos.index(l['rotulo'])
                ax.plot(l['posicao'], linha, marker=marca, markersize=5.5, color=DATAVIZ[1], markeredgecolor='#FFFFFF',
                        markeredgewidth=0.6, zorder=5)
    ax.set_xticks(np.arange(-0.5, n_dias, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(janelas), 1), minor=True)
    ax.grid(which='minor', color='#FFFFFF', linewidth=0.5)
    ax.tick_params(which='both', length=0, colors=T['fg3'])
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.set_title(espacado('A janela, dia a dia'), fontsize=7.4, color=T['fg1'], fontweight='bold', loc='left', pad=8)
    legenda = [('sem dado', CHUVA[0]), (f'menos de {br(seco_mm, 0)} mm', CHUVA[1]),
               (f'{br(seco_mm, 0)} a {br(medio, 0)} mm', CHUVA[2]), (f'{br(medio, 0)} a {br(alto, 0)} mm', CHUVA[3]),
               (f'{br(alto, 0)} mm ou mais', CHUVA[4])]
    x = 0.0
    for texto, cor in legenda[0 if (matriz < -0.5).any() else 1:]:
        ax.add_patch(plt.Rectangle((x, -0.2), 0.014, 0.09, transform=ax.transAxes, color=cor, clip_on=False,
                                   ec=T['line_forte'], lw=0.4))
        ax.text(x + 0.019, -0.155, texto, transform=ax.transAxes, fontsize=6.3, color=T['fg3'], va='center')
        x += 0.03 + 0.0066 * len(texto)
    if inicio or fim:
        ax.plot([x + 0.006], [-0.155], marker='v' if inicio else '^', markersize=5.5, color=DATAVIZ[1],
                transform=ax.transAxes, clip_on=False)
        ax.text(x + 0.018, -0.155, 'dia em que a regra fechou', transform=ax.transAxes, fontsize=6.3, color=T['fg3'],
                va='center')


def figura(caminho, desenho, tamanho=(8.2, 4.6), margens=(0.1, 0.2, 0.86, 0.66)):
    fig = plt.figure(figsize=tamanho, facecolor=T['pagina'])
    desenho(fig.add_axes(margens))
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


# ------------------------------------------------------------------ páginas do PDF
def _pagina_mensal(pdf, r, sub):
    m = r['mensal']
    t = m['totais'][1]
    kpis = [('Anos agrícolas', str(len(m['anos'])), 'inteiros')]
    if t:
        kpis.append(('Mediana do ano', br(t['mediana'], 0), 'mm'))
    fig = _pagina('Calendário da chuva', sub, kpis)
    grafico_calendario(fig.add_axes([0.07, 0.2, 0.42, 0.56]), m['calendario'])
    ax = _painel(fig, [0.545, 0.085, 0.42, 0.755])
    y = _titulo(ax, 0.985, 'Por mês, na ordem do ano agrícola')
    cortes = m['cortes'][:2]
    colunas = [('mês', 0.0, 'left', False), ('mediana', 0.2, 'right', True), ('P20 a P80', 0.43, 'right', True),
               ('menor (ano)', 0.65, 'right', True), ('maior (ano)', 0.87 if not cortes else 0.84, 'right', True)]
    for k, c in enumerate(cortes):
        colunas.append((f'< {br(c, 0)}', 1.0 - 0.085 * (len(cortes) - 1 - k), 'right', True))
    linhas = []
    for l in m['calendario']:
        linha = [l['nome'], br(l['mediana']), f'{br(l["p20"], 0)} a {br(l["p80"], 0)}',
                 f'{br(l["menor"], 0)} ({l["ano_menor"]})', f'{br(l["maior"], 0)} ({l["ano_maior"]})']
        linhas.append(linha + [f'{l["abaixo"][c]}/{l["n"]}' for c in cortes])
    y = _tabela(ax, y, colunas, linhas, passo=0.047, fonte=6.9)
    notas = ['Valores em mm. P20 a P80: a faixa onde ficaram cerca de 6 de cada 10 anos.']
    if cortes:
        notas.append('Colunas "<": em quantos anos o mês ficou abaixo do corte (anos abaixo / anos com dado).')
    notas.append('Nos meses secos, valores pequenos e repetidos de um ano para outro são o piso do dado mensal: não '
                 'leia diferença entre eles.')
    _texto(ax, y - 0.03, notas, 92, fonte=6.4, passo=0.027, marcador='')
    pdf.savefig(fig)
    plt.close(fig)


def _pagina_anos(pdf, r, sub):
    m = r['mensal']
    linhas_t, resumo = m['totais']
    g = m['aguas']
    kpis = []
    if resumo:
        kpis = [('Menor ano', br(resumo['menor'], 0), resumo['ano_menor']),
                ('Maior ano', br(resumo['maior'], 0), resumo['ano_maior'])]
    fig = _pagina('Ano a ano', sub, kpis)
    grafico_totais(fig.add_axes([0.07, 0.53, 0.42, 0.25]), linhas_t, resumo)
    ax = _painel(fig, [0.045, 0.085, 0.455, 0.33])
    frases = [f for f in relato.blocos(dict(mensal=m))[0][1]
              if f.startswith(('Pela regra mensal', 'Regra mensal', 'Em ', 'Terminaram', 'Graus-dia', 'Contando', 'O alvo'))]
    if frases:
        y = _titulo(ax, 0.98, 'As águas pela regra mensal e os graus-dia')
        _texto(ax, y, frases, 100, fonte=6.5, passo=0.062, piso=0.0)
    ax = _painel(fig, [0.545, 0.085, 0.42, 0.755])
    y = _titulo(ax, 0.985, 'Total e as águas (regra mensal), por ano' if g and not g['regra_nao_separa']
                else 'Total e posição, por ano')
    aguas = {l['rotulo']: l for l in (g['linhas'] if g and not g['regra_nao_separa'] else [])}
    colunas = [('ano', 0.0, 'left', True), ('total mm', 0.3, 'right', True), ('posição', 0.43, 'right', True)]
    if aguas:
        colunas += [('firmaram', 0.63, 'right', True), ('terminaram', 0.85, 'right', True), ('meses', 1.0, 'right', True)]
    mostra = linhas_t[-30:]
    linhas = []
    for t in mostra:
        linha = [t['rotulo'], br(t['total'], 0), '—' if t['posicao'] is None else f'{t["posicao"]}º']
        a = aguas.get(t['rotulo'])
        if aguas:
            linha += ['—' if not a or not a['inicio'] else f'{MESES[a["inicio"][1] - 1]}/{a["inicio"][0]}',
                      '—' if not a or not a['fim'] else f'{MESES[a["fim"][1] - 1]}/{a["fim"][0]}',
                      '—' if not a or a['meses_de_aguas'] is None else str(a['meses_de_aguas'])]
        linhas.append(linha)
    passo = min(0.047, 0.86 / max(len(linhas), 1))
    y = _tabela(ax, y, colunas, linhas, passo=passo, fonte=6.9 if passo > 0.035 else 6.0)
    if len(linhas_t) > len(mostra):
        ax.text(0, y - 0.02, f'Os {len(mostra)} anos mais recentes; todos estão em anos_agricolas.csv.', fontsize=6.2,
                color=T['fg3'], va='top')
    pdf.savefig(fig)
    plt.close(fig)


def _pagina_janela(pdf, r, sub):
    j = r['janela']
    fig = _pagina('A janela crítica', f'{sub} · {j["inicio_dm"]} a {j["fim_dm"]}',
                  [('Anos', str(j['n']), f'{j["anos"][0]}–{j["anos"][-1]}'),
                   ('Dia seco', f'< {br(j["seco_mm"], 0)}', 'mm')])
    grafico_decendios(fig.add_axes([0.07, 0.52, 0.4, 0.27]), j['decendios'], j['cortes'], j['n'])
    ax = _painel(fig, [0.525, 0.4, 0.44, 0.44])
    y = _titulo(ax, 0.975, 'Chuva por decêndio (mm), entre os anos')
    cortes = j['cortes'][:3]
    colunas = [('decêndio', 0.0, 'left', False), ('mediana', 0.33, 'right', True), ('menor (ano)', 0.53, 'right', True),
               ('maior (ano)', 0.73, 'right', True)]
    for k, c in enumerate(cortes):
        colunas.append((f'≥ {br(c, 0)}', 0.82 + 0.09 * k if len(cortes) == 3 else 0.86 + 0.14 * k
                        if len(cortes) == 2 else 0.9, 'right', True))
    linhas = [[l['nome'], br(l['mediana']), f'{br(l["menor"], 0)} ({l["ano_menor"]})',
               f'{br(l["maior"], 0)} ({l["ano_maior"]})'] + [f'{l["acima"][c]}/{l["n"]}' for c in cortes]
              for l in j['decendios'] if l['inteiro'] and l.get('n')]
    _tabela(ax, y, colunas, linhas, passo=min(0.085, 0.8 / max(len(linhas), 1)), fonte=6.9)
    altura = min(0.26, 0.05 + 0.021 * j['n'])
    grafico_dias(fig.add_axes([0.07, 0.135 + (0.26 - altura), 0.895, altura]), j['janelas'], j['anos'], j['seco_mm'],
                 inicio=j['inicio']['linhas'] if j['inicio'] else None)
    pdf.savefig(fig)
    plt.close(fig)


def _pagina_por_ano(pdf, r, sub):
    j, x = r.get('janela'), r.get('fim')
    fig = _pagina('Ano a ano na janela', sub, [])
    if j:
        ax = _painel(fig, [0.045, 0.085, 0.56 if x else 0.92, 0.755])
        y = _titulo(ax, 0.985, f'Janela de {j["inicio_dm"]} a {j["fim_dm"]}')
        tem_inicio = bool(j['inicio'])
        colunas = [('ano', 0.0, 'left', True), ('total mm', 0.18, 'right', True), ('dias chuva', 0.33, 'right', True),
                   ('veranico (ferram.)', 0.57, 'right', True),
                   ('maior seq. seca', 0.82 if tem_inicio else 0.9, 'right', True)]
        if tem_inicio:
            colunas.append(('início', 1.0, 'right', True))
        inicio = {l['rotulo']: l for l in (j['inicio']['linhas'] if tem_inicio else [])}
        linhas = []
        for l in j['veranicos']['linhas']:
            f, m = l['da_ferramenta'], l['maior']
            linha = [l['rotulo'], br(l['total']), '—' if l['dias_chuva'] is None else str(l['dias_chuva']),
                     '—' if not f else f'{f["dias"]} d ({dm(f["de"])})' if f['de'] else f'{f["dias"]} d',
                     '—' if not m else f'{m["dias"]} d ({dm(m["de"])}){"*" if m["borda"] else ""}']
            if tem_inicio:
                i = inicio[l['rotulo']]
                linha.append(dm(i['data']) if i['situacao'] == 'ok' else
                             f'{dm(i["data"])} s/ conf.' if i['situacao'] == 'sem conferência' else 'não firmou')
            linhas.append(linha)
        passo = min(0.05, 0.6 / max(len(linhas), 1))
        y = _tabela(ax, y, colunas, linhas, passo=passo, fonte=6.9 if passo > 0.03 else 6.0)
        notas = ['Total e dias de chuva são os que a ferramenta informou. "Veranico (ferram.)" é o veranico máximo '
                 'pela régua da ferramenta; "maior seq. seca" é a maior sequência seca contada aqui, com a régua '
                 f'informada (menos de {br(j["seco_mm"], 0)} mm por dia). Entre parênteses, o dia em que começou. '
                 '"Início" é o início das águas pela regra informada.',
                 '* a sequência encosta na borda da janela: pode ter sido maior.']
        if tem_inicio and any(i['situacao'] == 'sem conferência' for i in inicio.values()):
            notas.append('"s/ conf.": a regra fechou perto do fim da janela e faltaram dias para conferir o falso início.')
        _texto(ax, y - 0.035, notas, 108 if x else 170, fonte=6.4, passo=0.027, marcador='')
    if x:
        ax = _painel(fig, [0.655 if j else 0.045, 0.085, 0.31 if j else 0.5, 0.755])
        y = _titulo(ax, 0.985, f'Fim das águas · {x["inicio_dm"]} a {x["fim_dm"]}')
        dur = {d['rotulo'][-2:]: d for d in (r.get('duracao') or [])}
        colunas = [('ano', 0.0, 'left', True), ('fim das águas', 0.62, 'right', True), ('dias de águas', 1.0, 'right', True)]
        linhas = [[l['rotulo'], dm(l['data']) if l['situacao'] == 'ok' else l['situacao'][:26],
                   str(dur[l['rotulo'][-2:]]['dias']) if l['situacao'] == 'ok' and l['rotulo'][-2:] in dur else '—']
                  for l in x['datas']['linhas']]
        passo = min(0.05, 0.6 / max(len(linhas), 1))
        y = _tabela(ax, y, colunas, linhas, passo=passo, fonte=6.9 if passo > 0.03 else 6.0)
        _texto(ax, y - 0.035, ['"Dias de águas": do início (janela do plantio) ao fim, quando as duas datas fecharam.'],
               60 if j else 100, fonte=6.4, passo=0.027, marcador='')
    pdf.savefig(fig)
    plt.close(fig)


def _paginas_do_relato(pdf, r, sub):
    """O relato em texto, corrido em quantas páginas precisar."""
    fila = [(titulo, list(frases)) for titulo, frases in relato.blocos(r, para_pdf=True)]
    pagina = 0
    while fila:
        pagina += 1
        fig = _pagina('O que o registro mostra' + ('' if pagina == 1 else f' ({pagina})'), sub, [])
        ax = _painel(fig, [0.045, 0.085, 0.92, 0.755])
        y = 0.985
        while fila:
            titulo, frases = fila[0]
            if y < 0.24:        # não começa um bloco no pé da página
                break
            y = _titulo(ax, y, titulo)
            y, coube = _texto(ax, y, frases, 172, fonte=7.0, passo=0.0265, piso=0.0)
            if coube < len(frases):
                fila[0] = (titulo + ' (continua)', frases[coube:])
                break
            fila.pop(0)
            y -= 0.025
        pdf.savefig(fig)
        plt.close(fig)
        if pagina > 12:
            break


def relatorio(caminho, r):
    """Monta o PDF: as páginas de cada bloco pedido e o relato em texto no fim."""
    sub = r.get('local') or 'Local informado pelo usuário'
    with PdfPages(caminho) as pdf:
        if r.get('mensal'):
            _pagina_mensal(pdf, r, sub)
            _pagina_anos(pdf, r, sub)
        if r.get('janela'):
            _pagina_janela(pdf, r, sub)
        if r.get('janela') or r.get('fim'):
            _pagina_por_ano(pdf, r, sub)
        _paginas_do_relato(pdf, r, sub)
        info = pdf.infodict()
        info['Title'] = f'Chuva para decisão — {sub}'
        info['Author'] = 'agrônomo10X (OagronomIA)'


def gravar_tudo(pasta, r):
    """Grava todas as saídas na pasta e devolve a lista de arquivos."""
    os.makedirs(pasta, exist_ok=True)
    if r.get('mensal'):
        gravar_mensal(pasta, r['mensal'])
        figura(os.path.join(pasta, 'calendario.png'), lambda ax: grafico_calendario(ax, r['mensal']['calendario']))
    if r.get('janela'):
        j = r['janela']
        gravar_janela(pasta, j)
        figura(os.path.join(pasta, 'janela_decendios.png'),
               lambda ax: grafico_decendios(ax, j['decendios'], j['cortes'], j['n']), margens=(0.1, 0.26, 0.86, 0.6))
        figura(os.path.join(pasta, 'janela_dias.png'),
               lambda ax: grafico_dias(ax, j['janelas'], j['anos'], j['seco_mm'],
                                       inicio=j['inicio']['linhas'] if j['inicio'] else None),
               tamanho=(11.0, 1.6 + 0.24 * j['n']), margens=(0.07, 0.3, 0.9, 0.52))
    if r.get('fim'):
        gravar_fim(pasta, r['fim'], r.get('duracao'))
    with open(os.path.join(pasta, 'relato.md'), 'w', encoding='utf-8') as f:
        f.write(relato.em_texto(r) + '\n')
    gravar_json(os.path.join(pasta, 'analise.json'), r)
    relatorio(os.path.join(pasta, 'relatorio.pdf'), r)
    return sorted(os.listdir(pasta))


# ------------------------------------------------------------------ autoteste
def _autoteste():
    import tempfile

    import sintetico
    r = sintetico.resultado_demo()
    with tempfile.TemporaryDirectory() as pasta:
        arquivos = gravar_tudo(pasta, r)
        esperados = {'analise.json', 'anos_agricolas.csv', 'calendario.png', 'calendario_mensal.csv',
                     'fim_das_aguas_por_ano.csv', 'janela_decendios.csv', 'janela_decendios.png', 'janela_dias.png',
                     'janela_por_ano.csv', 'relato.md', 'relatorio.pdf'}
        assert set(arquivos) == esperados, set(arquivos) ^ esperados
        for nome in arquivos:
            assert os.path.getsize(os.path.join(pasta, nome)) > 200, nome
        with open(os.path.join(pasta, 'calendario_mensal.csv'), encoding='utf-8-sig') as f:
            linhas = list(csv.reader(f, delimiter=';'))
        assert linhas[0][0] == 'mes' and len(linhas) == 13 and linhas[1][0] == 'jul'
        with open(os.path.join(pasta, 'janela_por_ano.csv'), encoding='utf-8-sig') as f:
            linhas = list(csv.reader(f, delimiter=';'))
        assert len(linhas) == 1 + r['janela']['n'] and linhas[0][-2] == 'inicio_das_aguas_data'
        with open(os.path.join(pasta, 'analise.json'), encoding='utf-8') as f:
            dados = json.load(f)
        assert 'janela' in dados and 'janelas' not in dados['janela'] and 'meses' not in dados['mensal']
        with open(os.path.join(pasta, 'relatorio.pdf'), 'rb') as f:
            assert f.read(5) == b'%PDF-'
    so_mensal = dict(local='Só a tabela', mensal=r['mensal'])
    with tempfile.TemporaryDirectory() as pasta:
        assert 'relatorio.pdf' in gravar_tudo(pasta, so_mensal) and not os.path.exists(os.path.join(pasta, 'janela_dias.png'))
    print('saidas.py: autoteste ok')


if __name__ == '__main__':
    _autoteste()
