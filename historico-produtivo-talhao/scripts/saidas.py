"""Arquivos de saída do histórico: tabelas em CSV, o quadro em Markdown, uma
figura por talhão e o relatório em PDF, no formato dos documentos da casa.

Os CSV saem com ponto e vírgula e vírgula decimal (abrem direto na planilha).

Teste embutido: python scripts/saidas.py
"""

import csv
import re
import textwrap
import unicodedata
from datetime import timedelta
from pathlib import Path

import matplotlib

matplotlib.use('Agg')

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

import historico as H  # noqa: E402

# tokens do design system da casa (tema claro de impressão) e paleta de dataviz
T = dict(pagina='#FBFCF9', fg1='#121810', fg2='#3C4636', fg3='#6B7562', line='#D4DBCA', line_forte='#B4BFA8',
         verde='#2E8B1E', faixa='#EEF2E8', ciclo='#DCEBD3')
DATAVIZ = ['#2E8B1E', '#C26A3D', '#4FB7C9', '#E8B33B', '#7D5BA6', '#8A7556', '#D1495B', '#3B6FB6']
ROTULO_DOC = 'agrônomo10X · Histórico por satélite'
MONO = 'DejaVu Sans Mono'
MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
RODAPE = ('Descreve o que o satélite e o registro de chuva mostram. Índice de vegetação não é produtividade, e a cultura '
          'de cada ciclo não é identificada; a interpretação é do responsável técnico.')


def espacado(texto):
    return ' '.join(str(texto).upper())


def nome_de_arquivo(texto):
    base = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', base.lower()).strip('-') or 'area'


def _curto(texto, teto):
    texto = str(texto)
    return texto if len(texto) <= teto else texto[:teto - 1].rstrip() + '…'


# ------------------------------------------------------------------ CSV e Markdown
def _br(v, casas=2):
    return '' if v is None else format(v, f'.{casas}f').replace('.', ',')


def _d(d):
    return '' if d is None else f'{d:%d/%m/%Y}'


def _gravar(caminho, cabecalho, linhas):
    with open(caminho, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(cabecalho)
        w.writerows(linhas)
    return len(linhas)


def gravar_ciclos(caminho, h):
    linhas = []
    for nome, t in h['talhoes'].items():
        for c in t['ciclos']:
            ie, fe = c['inicio_entre'] or (None, None), c['fim_entre'] or (None, None)
            linhas.append([nome, c['safra'], c['numero'], _d(c['inicio']), _d(ie[0]), _d(ie[1]), _d(c['pico_data']),
                           _br(c['pico_valor']), _d(c['fim']), _d(fe[0]), _d(fe[1]),
                           '' if c['duracao_dias'] is None else c['duracao_dias'], _br(c['base_antes']),
                           _br(c['base_depois']), '; '.join(c['obs'])])
    return _gravar(caminho, ['talhao', 'safra', 'ciclo', 'inicio_provavel', 'inicio_imagem_antes', 'inicio_imagem_depois',
                             'pico_data', 'pico_valor', 'fim_provavel', 'fim_imagem_antes', 'fim_imagem_depois',
                             'duracao_dias', 'base_antes', 'base_depois', 'observacoes'], linhas)


def gravar_safras(caminho, h):
    chuva = {s['rotulo']: s for s in h['safras']}
    linhas = []
    for nome, t in h['talhoes'].items():
        for r in t['por_safra']:
            s = chuva[r['safra']]
            v = s['maior_veranico']
            linhas.append([nome, r['safra'], _d(s['inicio']), _d(s['fim']), r['imagens'],
                           r.get('maior_intervalo', ''), _d(r.get('intervalo_de')), _d(r.get('intervalo_ate')),
                           _br(r.get('maximo')), _d(r.get('maximo_data')), r.get('ciclos', ''), r.get('tiradas', ''),
                           _br(s['chuva_mm'], 1), _br(s['normal_mm'], 1), '' if s['dif_pct'] is None else s['dif_pct'],
                           'sim' if s['abaixo'] else ('' if s['dif_pct'] is None else 'não'),
                           '' if s['dias_chuva'] is None else s['dias_chuva'], '' if s['veranicos'] is None else s['veranicos'],
                           v['dias'] if v else '', _d(v['de']) if v else '', _d(v['ate']) if v else ''])
    return _gravar(caminho, ['talhao', 'safra', 'janela_inicio', 'janela_fim', 'imagens', 'maior_intervalo_sem_imagem_dias',
                             'intervalo_de', 'intervalo_ate', 'maior_valor', 'maior_valor_data', 'ciclos_com_pico_na_safra',
                             'quedas_isoladas_tiradas', 'chuva_mm', 'media_historica_mm', 'diferenca_pct',
                             f'chuva_{h["abaixo_pct"]}pct_ou_mais_abaixo', 'dias_de_chuva', 'veranicos',
                             'maior_veranico_dias', 'maior_veranico_de', 'maior_veranico_ate'], linhas)


def gravar_quadro(caminho, h, nome=None):
    Path(caminho).write_text(H.quadro_md(h, nome), encoding='utf-8')


# ------------------------------------------------------------------ moldura e tabelas
def _moldura(fig, titulo, subtitulo, kpis, rodape):
    fig.text(0.035, 0.955, espacado(ROTULO_DOC), fontsize=6.4, color=T['verde'], va='center', fontweight='bold')
    fig.text(0.035, 0.915, _curto(titulo, 44), fontsize=15.5, color=T['fg1'], va='center', fontstyle='italic', fontweight='bold')
    fig.text(0.035, 0.878, _curto(subtitulo, 84), fontsize=9.5, color=T['fg2'], va='center')
    x = 0.965
    for rotulo, valor, unidade in reversed(kpis):
        fig.text(x, 0.955, espacado(rotulo), fontsize=5.8, color=T['fg3'], va='center', ha='right')
        fig.text(x, 0.918, valor, fontsize=14, color=T['fg1'], va='center', ha='right', family=MONO, fontweight='bold')
        fig.text(x, 0.885, unidade, fontsize=7, color=T['fg3'], va='center', ha='right', family=MONO)
        x -= 0.028 + 0.0118 * max(len(valor), len(unidade) * 0.55, 7)
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.86, 0.86], color=T['line'], linewidth=0.8))
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.062, 0.062], color=T['line'], linewidth=0.8))
    fig.text(0.035, 0.044, rodape, fontsize=7, color=T['fg3'], va='center')
    fig.text(0.035, 0.026, RODAPE, fontsize=6.2, color=T['fg3'], va='center')
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
    return y - 0.055


def _tabela(ax, y, colunas, linhas, passo=0.05, fonte=7.2, destaque=None):
    """colunas = [(título, x, 'left'|'right', mono?)]. Devolve o y do fim."""
    for titulo, xc, alinh, _ in colunas:
        ax.text(xc, y, espacado(titulo), fontsize=5.2, color=T['fg3'], va='center', ha=alinh)
    y -= 0.028
    ax.plot([0, 1], [y, y], color=T['line'], linewidth=0.8)
    for k, linha in enumerate(linhas):
        if destaque and k in destaque:
            ax.fill_between([0, 1], y - passo, y, color=T['faixa'], linewidth=0)
        for (_, xc, alinh, mono), texto in zip(colunas, linha):
            ax.text(xc, y - passo / 2, texto, fontsize=fonte, color=T['fg1'], va='center', ha=alinh,
                    family=MONO if mono else None)
        y -= passo
        ax.plot([0, 1], [y, y], color=T['line'], linewidth=0.4)
    return y


def _texto(ax, y, linhas, largura, fonte=6.9, cor='fg2', passo=0.034, piso=0.0):
    for k, linha in enumerate(linhas):
        partes = textwrap.wrap(linha, largura) or ['']
        if y - passo * len(partes) < piso:
            ax.text(0, y, f'… (mais {len(linhas) - k} no quadro.md)', fontsize=fonte, color=T['fg3'], va='top')
            return y - passo
        ax.text(0, y, '\n'.join(partes), fontsize=fonte, color=T[cor], va='top', linespacing=1.4)
        y -= passo * len(partes) + 0.016
    return y


def _eixo(ax, titulo=None):
    for lado in ('top', 'right'):
        ax.spines[lado].set_visible(False)
    for lado in ('bottom', 'left'):
        ax.spines[lado].set_color(T['line_forte'])
    ax.tick_params(labelsize=6.8, colors=T['fg3'])
    ax.set_facecolor('#FFFFFF')
    ax.grid(axis='y', color=T['line'], linewidth=0.4)
    ax.set_axisbelow(True)
    if titulo:
        ax.set_title(espacado(titulo), fontsize=7.2, color=T['fg1'], fontweight='bold', loc='left', pad=8)


# ------------------------------------------------------------------ gráficos
def linha_do_tempo(ax, h, nome):
    """A série inteira do talhão, com os ciclos sombreados do início ao fim e o pico marcado."""
    t = h['talhoes'][nome]
    _eixo(ax, f'{h["indice"]} · todas as imagens')
    for s in h['safras']:
        ax.axvline(s['inicio'], color=T['line_forte'], linewidth=0.6, linestyle=(0, (2, 3)))
    ax.axvline(h['safras'][-1]['fim'], color=T['line_forte'], linewidth=0.6, linestyle=(0, (2, 3)))
    for c in t['ciclos']:
        if c['inicio'] and c['fim']:
            ax.axvspan(c['inicio'], c['fim'], color=T['ciclo'], linewidth=0)
        elif c['inicio'] or c['fim']:
            a = c['inicio'] or t['serie'][0][0]
            b = c['fim'] or t['serie'][-1][0]
            ax.axvspan(a, b, facecolor='none', edgecolor=T['line_forte'], hatch='////', linewidth=0)
    # a linha quebra onde as janelas não estão emendadas
    grupo, anterior = [], None
    for d, v in t['serie']:
        if anterior and (d - anterior).days > 75:
            ax.plot(*zip(*grupo), color=T['verde'], linewidth=1.2, marker='o', markersize=2.2)
            grupo = []
        grupo.append((d, v))
        anterior = d
    if grupo:
        ax.plot(*zip(*grupo), color=T['verde'], linewidth=1.2, marker='o', markersize=2.2)
    if t['tirados']:
        ax.plot(*zip(*t['tirados']), linestyle='none', marker='x', markersize=4, color=T['fg3'])
    for c in t['ciclos']:
        ax.plot([c['pico_data']], [c['pico_valor']], marker='v', markersize=5, color=T['fg1'], linestyle='none')
        ax.annotate(H.br(c['pico_valor']), (c['pico_data'], c['pico_valor']), textcoords='offset points', xytext=(0, 6),
                    ha='center', fontsize=6.2, color=T['fg1'], family=MONO)
    valores = [v for _, v in t['serie']] + [v for _, v in t['tirados']]
    topo = max(valores) + 0.22
    ax.set_ylim(min(0.0, min(valores) - 0.05), min(1.12, topo))
    for s in h['safras']:
        meio = s['inicio'] + (s['fim'] - s['inicio']) / 2
        rotulo = s['rotulo'] + ('' if s['chuva_mm'] is None else f' · {H.mm(s["chuva_mm"])}') + \
            ('' if s['dif_pct'] is None else f' ({s["dif_pct"]:+d}%)'.replace('-', '−')) + (' ▼' if s['abaixo'] else '')
        ax.text(meio, ax.get_ylim()[1] - 0.01, rotulo, fontsize=6, color=T['fg2'], ha='center', va='top')
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
    ax.set_xlim(h['safras'][0]['inicio'] - timedelta(days=5), h['safras'][-1]['fim'] + timedelta(days=5))


def sobreposicao(ax, h, nome):
    """Cada safra contra os dias desde o início da sua janela."""
    t = h['talhoes'][nome]
    _eixo(ax, 'As safras no mesmo eixo')
    maior = 0
    for k, s in enumerate(h['safras']):
        pontos = [((d - s['inicio']).days, v) for d, v in t['serie'] if s['inicio'] <= d <= s['fim']]
        if not pontos:
            continue
        ax.plot(*zip(*pontos), color=DATAVIZ[k % len(DATAVIZ)], linewidth=1.1, marker='o', markersize=1.8, label=s['rotulo'])
        maior = max(maior, s['dias'])
    inicio = h['safras'][0]['inicio']
    marcas, rotulos, d = [], [], inicio.replace(day=1)
    while (d - inicio).days <= maior:
        if (d - inicio).days >= 0:
            marcas.append((d - inicio).days)
            rotulos.append(MESES[d.month - 1])
        d = (d.replace(day=28) + timedelta(days=5)).replace(day=1)
    ax.set_xticks(marcas)
    ax.set_xticklabels(rotulos)
    ax.set_xlim(0, max(maior, 30))
    ax.legend(fontsize=6.2, frameon=False, ncol=min(4, len(h['safras'])), loc='upper center', bbox_to_anchor=(0.5, -0.14),
              labelcolor=T['fg2'], handlelength=1.4, columnspacing=1.2)


def figura_do_talhao(caminho, h, nome):
    fig = plt.figure(figsize=(11, 6.2), facecolor=T['pagina'])
    linha_do_tempo(fig.add_axes([0.06, 0.56, 0.91, 0.34]), h, nome)
    sobreposicao(fig.add_axes([0.06, 0.12, 0.91, 0.30]), h, nome)
    fig.text(0.06, 0.955, _curto(nome, 70), fontsize=11, color=T['fg1'], fontweight='bold', fontstyle='italic')
    fig.savefig(caminho, dpi=160, facecolor=T['pagina'])
    plt.close(fig)


# ------------------------------------------------------------------ PDF
def _linhas_de_chuva(h):
    linhas, destaque = [], set()
    for k, s in enumerate(h['safras']):
        v = s['maior_veranico']
        linhas.append([s['rotulo'], f'{s["inicio"]:%d/%m/%y}–{s["fim"]:%d/%m/%y}', H.mm(s['chuva_mm']), H.mm(s['normal_mm']),
                       H.dif_txt(s), '—' if s['dias_chuva'] is None else str(s['dias_chuva']),
                       '—' if s['veranicos'] is None else str(s['veranicos']), f'{v["dias"]} d' if v else '—'])
        if s['abaixo']:
            destaque.add(k)
    return linhas, destaque


def _celula(t, rotulo):
    ciclos = [c for c in t['ciclos'] if c['safra'] == rotulo]
    if not any(r['safra'] == rotulo and r['imagens'] for r in t['por_safra']):
        return 'sem imagem'
    if not ciclos:
        return '—'
    return ' · '.join(f'{H.br(c["pico_valor"])} {c["pico_data"]:%d/%m}' for c in ciclos)


def relatorio(caminho_pdf, h, nome=None, caminho_png=None):
    """Grava o PDF (resumo + uma página por talhão). Com `caminho_png`, grava também a 1ª página em PNG."""
    s0, s1 = h['safras'][0], h['safras'][-1]
    n_ciclos = sum(len(t['ciclos']) for t in h['talhoes'].values())
    titulo = nome or 'Histórico por satélite'
    subtitulo = f'{h["indice"]} · {len(h["safras"])} safra(s), de {s0["inicio"]:%d/%m/%Y} a {s1["fim"]:%d/%m/%Y}'
    kpis = [('Safras', str(len(h['safras'])), 'consultadas'), ('Áreas', str(len(h['talhoes'])), 'talhões'),
            ('Ciclos', str(n_ciclos), 'encontrados')]
    nomes = list(h['talhoes'])
    total = 1 + len(nomes) + max(0, (len(nomes) - 1) // 12)
    pagina = 0

    def rodape():
        nonlocal pagina
        pagina += 1
        return f'Histórico por satélite · página {pagina} de {total}'

    with PdfPages(caminho_pdf) as pdf:
        # ---- resumo
        fig = _pagina(titulo, subtitulo, kpis, rodape())
        ax = _painel(fig, [0.035, 0.47, 0.56, 0.37])
        y = _titulo(ax, 1.0, 'Chuva de cada safra')
        colunas = [('Safra', 0.0, 'left', True), ('Janela', 0.12, 'left', True), ('Chuva', 0.47, 'right', True),
                   ('Média 91–20', 0.62, 'right', True), ('Diferença', 0.745, 'right', True),
                   ('Dias de chuva', 0.875, 'right', True), ('Veran.', 0.94, 'right', True), ('Maior', 1.0, 'right', True)]
        linhas, destaque = _linhas_de_chuva(h)
        passo = min(0.085, 0.80 / max(1, len(linhas)))
        y = _tabela(ax, y, colunas, linhas, passo=passo, destaque=destaque)
        notas = []
        if destaque:
            notas.append(f'▼ = chuva {h["abaixo_pct"]}% ou mais abaixo da média histórica do mesmo período.')
        regua = next((s['regua_veranico'] for s in h['safras'] if s['regua_veranico']), None)
        if regua:
            notas.append(f'Veranico = {regua}.')
        if any(s['chuva_mm'] is None for s in h['safras']):
            notas.append('Safra sem chuva na tabela: a resposta colada não trazia a linha da chuva.')
        _texto(ax, y - 0.03, notas, 118, fonte=6.4, cor='fg3', passo=0.04)
        ax = _painel(fig, [0.63, 0.47, 0.335, 0.37])
        y = _titulo(ax, 1.0, 'Como ler')
        y = _texto(ax, y, H.texto_das_regras(h), 68, fonte=6.6, passo=0.047)
        _texto(ax, y, [a[0].upper() + a[1:] for a in h['avisos']], 68, fonte=6.6, cor='fg1', passo=0.047)
        _matriz(fig, h, nomes[:12])
        pdf.savefig(fig, facecolor=T['pagina'])
        if caminho_png:
            fig.savefig(caminho_png, dpi=140, facecolor=T['pagina'])
        plt.close(fig)
        for i in range(12, len(nomes), 12):
            fig = _pagina(titulo, subtitulo, kpis, rodape())
            _matriz(fig, h, nomes[i:i + 12], caixa=[0.035, 0.10, 0.93, 0.74])
            pdf.savefig(fig, facecolor=T['pagina'])
            plt.close(fig)
        # ---- uma página por talhão
        for nome_t in nomes:
            t = h['talhoes'][nome_t]
            fig = _pagina(_curto(nome_t, 44), f'{titulo} · {subtitulo}', kpis, rodape())
            linha_do_tempo(fig.add_axes([0.06, 0.585, 0.905, 0.215]), h, nome_t)
            sobreposicao(fig.add_axes([0.06, 0.165, 0.33, 0.30]), h, nome_t)
            ax = _painel(fig, [0.44, 0.085, 0.525, 0.44])
            y = _titulo(ax, 1.0, 'Ciclos de vegetação')
            colunas = [('Safra', 0.0, 'left', True), ('Nº', 0.135, 'right', True), ('Início provável', 0.16, 'left', True),
                       ('Pico', 0.47, 'left', True), ('Fim provável', 0.67, 'left', True), ('Dias', 1.0, 'right', True)]
            linhas = []
            for c in t['ciclos'][:9]:
                linhas.append([c['safra'], str(c['numero']), _com_entre(c['inicio'], c['inicio_entre']),
                               f'{H.br(c["pico_valor"])} {c["pico_data"]:%d/%m/%y}', _com_entre(c['fim'], c['fim_entre']),
                               '—' if c['duracao_dias'] is None else str(c['duracao_dias'])])
            if linhas:
                y = _tabela(ax, y, colunas, linhas, passo=0.062, fonte=6.6)
            notas = []
            if len(t['ciclos']) > 9:
                notas.append(f'Mais {len(t["ciclos"]) - 9} ciclo(s) no ciclos.csv.')
            if not t['ciclos']:
                notas.append('Nenhum ciclo encontrado com as regras da página 1.')
            notas += [a[0].upper() + a[1:] + '.' for a in t['avisos']]
            notas += [f'Ciclo {c["numero"]}: {"; ".join(c["obs"])}.' for c in t['ciclos'][:9] if c['obs']]
            if t['tirados']:
                notas.append(f'× = {len(t["tirados"])} queda(s) isolada(s) fora da conta.')
            notas.append('Entre parênteses, as duas imagens entre as quais a data caiu. Faixa verde: do início ao fim '
                         'do ciclo; faixa riscada: ciclo cortado pelo período consultado.')
            _texto(ax, y - 0.03, notas, 100, fonte=6.1, cor='fg3', passo=0.036, piso=0.0)
            pdf.savefig(fig, facecolor=T['pagina'])
            plt.close(fig)
    return pagina


def _com_entre(d, entre):
    if d is None:
        return '—'
    return f'{d:%d/%m/%y} ({entre[0]:%d/%m}–{entre[1]:%d/%m})'


def _matriz(fig, h, nomes, caixa=None):
    """Talhão × safra: o pico de cada ciclo (valor e dia)."""
    ax = _painel(fig, caixa or [0.035, 0.085, 0.93, 0.345])
    y = _titulo(ax, 1.0, 'Pico de cada ciclo, por talhão e safra (valor do índice e dia)')
    safras = h['safras'][-8:]
    largura = 0.80 / max(1, len(safras))
    colunas = [('Talhão', 0.0, 'left', False)] + [(s['rotulo'], 0.20 + largura * k, 'left', True) for k, s in enumerate(safras)]
    linhas = [[_curto(n, 24)] + [_curto(_celula(h['talhoes'][n], s['rotulo']), max(10, int(largura * 150))) for s in safras]
              for n in nomes]
    passo = min(0.075, 0.82 / max(1, len(linhas)))
    y = _tabela(ax, y, colunas, linhas, passo=passo, fonte=6.4)
    notas = ['— = safra com imagem e sem ciclo pelas regras acima. Dois valores na mesma safra = dois ciclos.']
    if len(h['safras']) > 8:
        notas.append(f'A tabela mostra as 8 safras mais recentes; as {len(h["safras"]) - 8} anteriores estão no ciclos.csv.')
    _texto(ax, y - 0.03, notas, 190, fonte=6.2, cor='fg3', passo=0.04)


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    import tempfile

    import leitura as L
    import sintetico
    safras = L.conferir_conjunto([x for texto in sintetico.respostas() for x in L.ler_texto(texto, 'demo')])
    h = H.montar(safras)
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        assert gravar_ciclos(pasta / 'ciclos.csv', h) == 12
        assert gravar_safras(pasta / 'safras.csv', h) == 12
        gravar_quadro(pasta / 'quadro.md', h, 'Fazenda Exemplo')
        figura_do_talhao(pasta / 'sede.png', h, 'Sede')
        paginas = relatorio(pasta / 'historico.pdf', h, 'Fazenda Exemplo', pasta / 'historico.png')
        assert paginas == 4, paginas
        cab = (pasta / 'ciclos.csv').read_text(encoding='utf-8-sig').splitlines()
        assert cab[0].startswith('talhao;safra;ciclo;inicio_provavel') and cab[1].startswith('Sede;2021/22;1;')
        for arq in ('historico.pdf', 'historico.png', 'sede.png', 'quadro.md', 'safras.csv'):
            assert (pasta / arq).stat().st_size > 1000, arq
    assert nome_de_arquivo('Pivô 1 / Área nova') == 'pivo-1-area-nova'
    print('saidas.py: autoteste ok (2 CSV, quadro, figura e PDF de 4 páginas)')


if __name__ == '__main__':
    _autoteste()
