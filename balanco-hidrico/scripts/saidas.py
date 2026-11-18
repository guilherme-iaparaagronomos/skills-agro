"""Arquivos de saída do balanço hídrico: a tabela em CSV, a figura e o relatório
em PDF, no formato dos documentos da casa.

Os CSV saem com ponto e vírgula e vírgula decimal (abrem direto na planilha).

Teste embutido: python scripts/saidas.py
"""

import csv
import math
import textwrap

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

import etp as mod_etp  # noqa: E402

# tokens do design system da casa (tema claro de impressão) e paleta de dataviz
T = dict(pagina='#FBFCF9', fg1='#121810', fg2='#3C4636', fg3='#6B7562', line='#D4DBCA', line_forte='#B4BFA8',
         verde='#2E8B1E', faixa='#EEF2E8')
COR = dict(chuva='#4FB7C9', excedente='#4FB7C9', deficiencia='#C26A3D', etp='#C26A3D', etr='#2E8B1E', arm='#2E8B1E')
ROTULO_DOC = 'agrônomo10X · Balanço hídrico'
MONO = 'DejaVu Sans Mono'
LINHAS_POR_PAGINA = 22
SEM_FONTE_DA_FERRAMENTA = ('ferramentas de clima da comunidade agrônomo10X (OagronomIA); a fonte de cada dado não veio '
                           'nos arquivos lidos')
QUADRO_DAS_FONTES = 'Fontes dos dados'
RESSALVA = ('A CAD e o método de ETP foram escolhidos pelo usuário. O relatório descreve o balanço; a decisão de '
            'manejo é do responsável técnico.')


def espacado(texto):
    return ' '.join(str(texto).upper())


def num(v, casas=1):
    """Número no padrão brasileiro; o que não existe vira travessão."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return '—'
    texto = f'{v:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return '0' + texto[2:] if texto.startswith('-0') and float(texto.replace('.', '').replace(',', '.')) == 0 else texto


def sinal(v, casas=1):
    return ('+' if v > 0 and round(v, casas) != 0 else '') + num(v, casas)


def nome_do_metodo(r):
    return mod_etp.NOMES[r['metodo']]


# ------------------------------------------------------------------ CSV
def _br(v, casas=2):
    return '' if v is None or (isinstance(v, float) and not math.isfinite(v)) else format(float(v), f'.{casas}f').replace('.', ',')


def gravar_csv(caminho, r):
    cabecalho = (['mes'] if r['tipo'] == 'normal' else ['inicio', 'fim']) + [
        'dias', 'temperatura_media', 'chuva', 'etp', 'p_menos_etp', 'negativo_acumulado', 'armazenamento',
        'alteracao', 'etr', 'deficiencia', 'excedente']
    linhas = []
    for l in r['linhas']:
        quando = [l['rotulo']] if r['tipo'] == 'normal' else [l['inicio'].isoformat(), l['fim'].isoformat()]
        linhas.append(quando + [l['dias'], _br(l['t'])] + [_br(l[c]) for c in ('p', 'etp', 'dif', 'neg', 'arm', 'alt',
                                                                              'etr', 'def', 'exc')])
    s = r['balanco']['afericao']['somas']
    total = ['total'] if r['tipo'] == 'normal' else ['total', '']
    linhas.append(total + [sum(l['dias'] for l in r['linhas']), '', _br(s['p']), _br(s['etp']), _br(s['dif']), '', '',
                           _br(s['alt']), _br(s['etr']), _br(s['def']), _br(s['exc'])])
    with open(caminho, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(cabecalho)
        w.writerows(linhas)
    return len(linhas)


# ------------------------------------------------------------------ moldura, tabela e texto
def _moldura(fig, titulo, subtitulo, kpis, rodape):
    fig.text(0.035, 0.955, espacado(ROTULO_DOC), fontsize=6.4, color=T['verde'], va='center', fontweight='bold')
    titulo = titulo if len(titulo) <= 44 else titulo[:43].rstrip() + '…'
    fig.text(0.035, 0.915, titulo, fontsize=15.5, color=T['fg1'], va='center', fontstyle='italic', fontweight='bold')
    subtitulo = subtitulo if len(subtitulo) <= 80 else subtitulo[:79].rstrip() + '…'
    fig.text(0.035, 0.878, subtitulo, fontsize=9.2, color=T['fg2'], va='center')
    x = 0.965
    for rotulo, valor, unidade in reversed(kpis):
        fig.text(x, 0.955, espacado(rotulo), fontsize=5.8, color=T['fg3'], va='center', ha='right')
        fig.text(x, 0.918, valor, fontsize=14, color=T['fg1'], va='center', ha='right', family=MONO, fontweight='bold')
        fig.text(x, 0.885, unidade, fontsize=7, color=T['fg3'], va='center', ha='right', family=MONO)
        x -= 0.028 + 0.0118 * max(len(valor), 9)
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.86, 0.86], color=T['line'], linewidth=0.8))
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.062, 0.062], color=T['line'], linewidth=0.8))
    fig.text(0.035, 0.044, rodape if len(rodape) <= 150 else rodape[:149] + '…', fontsize=7, color=T['fg3'], va='center')
    fig.text(0.035, 0.026, RESSALVA, fontsize=6.4, color=T['fg3'], va='center')
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
        ax.text(xc, y, espacado(titulo), fontsize=5.2, color=T['fg3'], va='center', ha=alinh)
    y -= 0.02
    ax.plot([0, 1], [y, y], color=T['line'], linewidth=0.8)
    for k, linha in enumerate(linhas):
        if destaque is not None and k in destaque:
            ax.fill_between([0, 1], y - passo, y, color=T['faixa'], linewidth=0)
        for (_, xc, alinh, mono), texto in zip(colunas, linha):
            ax.text(xc, y - passo / 2, texto, fontsize=fonte, color=T['fg1'], va='center', ha=alinh,
                    family=MONO if mono else None)
        y -= passo
        ax.plot([0, 1], [y, y], color=T['line'], linewidth=0.4)
    return y


def _texto(ax, y, linhas, largura, fonte=6.9, cor='fg2', passo=0.026, piso=0.0):
    """Parágrafos quebrados na largura. Para antes do piso e diz que há mais. Devolve o y do fim."""
    for k, linha in enumerate(linhas):
        partes = textwrap.wrap(linha, largura) or ['']
        if y - passo * len(partes) < piso:
            ax.text(0, y, f'… (mais {len(linhas) - k} no arquivo .json)', fontsize=fonte, color=T['fg3'], va='top')
            return y - passo
        ax.text(0, y, '\n'.join(partes), fontsize=fonte, color=T[cor], va='top', linespacing=1.4)
        y -= passo * len(partes) + 0.012
    return y


def _blocos(ax, y, blocos, largura, fonte=6.6, passo=0.026, piso=0.02):
    """Desenha os blocos (título, frases) que couberem no painel. Devolve os que sobraram, para a página seguinte."""
    for k, (titulo, frases) in enumerate(blocos):
        cabem, y_teste = [], y - 0.05
        for frase in frases:
            altura = passo * len(textwrap.wrap(frase, largura) or ['']) + 0.012
            if y_teste - altura < piso:
                break
            cabem.append(frase)
            y_teste -= altura
        if cabem:
            y = _titulo(ax, y, titulo)
            y = _texto(ax, y, cabem, largura, fonte=fonte, passo=passo) - 0.02
        if len(cabem) < len(frases):
            segue = titulo if titulo.endswith('(continuação)') or not cabem else titulo + ' (continuação)'
            return [(segue, frases[len(cabem):])] + list(blocos[k + 1:])
    return []


def _fontes_no_painel(ax, y, fontes, largura):
    """O quadro das fontes dos dados (cada linha como a ferramenta escreveu), a partir de y, se couber até o pé do
    painel. Devolve True se desenhou."""
    paragrafos = [textwrap.wrap(f, largura) or [''] for f in fontes]
    altura = 0.045 + sum(0.023 * len(p) + 0.008 for p in paragrafos) - 0.008
    if y - altura < -0.01:
        return False
    y = _titulo(ax, y, QUADRO_DAS_FONTES) + 0.005
    for partes in paragrafos:
        ax.text(0, y, '\n'.join(partes), fontsize=6.4, color=T['fg2'], va='top', linespacing=1.35)
        y -= 0.023 * len(partes) + 0.008
    return True


def _eixo(ax, titulo=None):
    for lado in ('top', 'right'):
        ax.spines[lado].set_visible(False)
    for lado in ('bottom', 'left'):
        ax.spines[lado].set_color(T['line_forte'])
    ax.tick_params(labelsize=7, colors=T['fg3'])
    ax.set_facecolor('#FFFFFF')
    ax.grid(axis='y', color=T['line'], linewidth=0.5, zorder=0)
    if titulo:
        ax.set_title(espacado(titulo), fontsize=7.4, color=T['fg1'], fontweight='bold', loc='left', pad=8)


# ------------------------------------------------------------------ gráficos
def _legenda(ax):
    ax.legend(frameon=False, fontsize=6.6, loc='lower right', bbox_to_anchor=(1.0, 1.0), ncol=3, borderaxespad=0.2,
              handlelength=1.4, columnspacing=1.0)


def _marcas(ax, r):
    linhas = r['linhas']
    x = list(range(len(linhas)))
    if r['tipo'] == 'normal' or len(linhas) <= 14:
        ax.set_xticks(x)
        ax.set_xticklabels([l['rotulo'] for l in linhas], rotation=0 if len(linhas) <= 12 and r['passo'] == 'mes' else 45,
                           ha='center' if len(linhas) <= 12 and r['passo'] == 'mes' else 'right')
        return x
    # série longa: um rótulo por mês (ou por ano, se forem muitos meses)
    por_ano = r['passo'] == 'mes' and len(linhas) > 30
    marcas, textos, visto = [], [], None
    for k, l in enumerate(linhas):
        chave = l['inicio'].year if por_ano else (l['inicio'].year, l['inicio'].month)
        if chave != visto:
            visto = chave
            marcas.append(k)
            textos.append(str(chave) if por_ano else l['rotulo'][-6:])
    ax.set_xticks(marcas)
    ax.set_xticklabels(textos, rotation=45, ha='right')
    return x


def extrato(ax, r):
    """Excedente para cima e deficiência para baixo, em cada período."""
    x = _marcas(ax, r)
    ax.bar(x, [l['exc'] for l in r['linhas']], color=COR['excedente'], width=0.72, zorder=2, label='Excedente')
    ax.bar(x, [-l['def'] for l in r['linhas']], color=COR['deficiencia'], width=0.72, zorder=2, label='Deficiência')
    ax.axhline(0, color=T['line_forte'], linewidth=0.8, zorder=3)
    ax.set_ylabel('mm', fontsize=7.5, color=T['fg2'])
    _legenda(ax)
    _eixo(ax, 'Extrato: excedente e deficiência')


def chuva_e_etp(ax, r):
    x = _marcas(ax, r)
    ax.bar(x, [l['p'] for l in r['linhas']], color=COR['chuva'], width=0.72, zorder=2, alpha=0.55, label='Chuva')
    ax.plot(x, [l['etp'] for l in r['linhas']], color=COR['etp'], linewidth=1.5, marker='o', markersize=2.6, zorder=3,
            label='ETP')
    ax.plot(x, [l['etr'] for l in r['linhas']], color=COR['etr'], linewidth=1.5, marker='o', markersize=2.6, zorder=4,
            label='ETR')
    ax.set_ylabel('mm', fontsize=7.5, color=T['fg2'])
    _legenda(ax)
    _eixo(ax, 'Chuva, ETP e ETR')


def armazenamento(ax, r):
    x = _marcas(ax, r)
    arm = [l['arm'] for l in r['linhas']]
    ax.fill_between(x, arm, color=COR['arm'], alpha=0.18, zorder=2, linewidth=0)
    ax.plot(x, arm, color=COR['arm'], linewidth=1.5, marker='o', markersize=2.6, zorder=3, label='Armazenamento')
    ax.axhline(r['cad'], color=T['fg3'], linewidth=0.9, linestyle='--', zorder=1, label=f'CAD = {num(r["cad"], 0)} mm')
    ax.set_ylim(0, r['cad'] * 1.18)
    ax.set_ylabel('mm', fontsize=7.5, color=T['fg2'])
    _legenda(ax)
    _eixo(ax, 'Armazenamento no solo')


def figura(caminho, r, titulo):
    """Os três gráficos em uma imagem só, para mostrar na conversa."""
    fig = plt.figure(figsize=(11.69, 4.6), facecolor=T['pagina'])
    fig.text(0.035, 0.945, espacado(titulo), fontsize=7.2, color=T['verde'], fontweight='bold', va='center')
    for caixa, desenho in (([0.055, 0.2, 0.27, 0.6], extrato), ([0.385, 0.2, 0.27, 0.6], chuva_e_etp),
                           ([0.715, 0.2, 0.26, 0.6], armazenamento)):
        desenho(fig.add_axes(caixa), r)
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


# ------------------------------------------------------------------ relatório
PERIODOS_NA_TABELA = 96        # série mais longa que isso sai resumida por ano no PDF e na tela (o CSV traz tudo)


def resumo_por_ano(r):
    """Série longa: uma linha por ano, com as somas do ano e o armazenamento do fim dele."""
    por_ano = {}
    for l in r['linhas']:
        por_ano.setdefault(l['inicio'].year, []).append(l)
    saida = []
    for ano, do_ano in sorted(por_ano.items()):
        linha = {c: sum(l[c] for l in do_ano) for c in ('p', 'etp', 'dif', 'alt', 'etr', 'def', 'exc')}
        t = [l['t'] for l in do_ano if l['t'] is not None]
        dias = sum(l['dias'] for l in do_ano)
        linha.update(rotulo=str(ano) + ('' if dias >= 365 else f' ({dias} dias)'), t=sum(t) / len(t) if t else None,
                     neg=None, arm=do_ano[-1]['arm'], inicio=do_ano[0]['inicio'], fim=do_ano[-1]['fim'], dias=dias)
        saida.append(linha)
    return saida


def _linha_da_tabela(l, normal):
    base = [l['rotulo'], num(l['t'], 1), num(l['p']), num(l['etp']), sinal(l['dif'])]
    return base + ([num(l['neg'])] if normal else []) + [num(l['arm']), sinal(l['alt']), num(l['etr']), num(l['def']),
                                                         num(l['exc'])]


def _colunas(normal):
    if normal:
        nomes = ('Mês', 'T °C', 'P', 'ETP', 'P−ETP', 'Neg.ac', 'ARM', 'ALT', 'ETR', 'DEF', 'EXC')
        xs = (0.0, 0.135, 0.225, 0.315, 0.415, 0.52, 0.61, 0.70, 0.80, 0.90, 1.0)
    else:
        nomes = ('Período', 'T °C', 'P', 'ETP', 'P−ETP', 'ARM', 'ALT', 'ETR', 'DEF', 'EXC')
        xs = (0.0, 0.24, 0.335, 0.43, 0.535, 0.63, 0.725, 0.82, 0.91, 1.0)
    return [(n, x, 'left' if k == 0 else 'right', k > 0) for k, (n, x) in enumerate(zip(nomes, xs))]


def _total(r):
    s = r['balanco']['afericao']['somas']
    base = ['Total', '', num(s['p']), num(s['etp']), sinal(s['dif'])]
    return base + ([''] if r['tipo'] == 'normal' else []) + ['', sinal(s['alt']), num(s['etr']), num(s['def']), num(s['exc'])]


def frases_da_afericao(r):
    a, s = r['balanco']['afericao'], r['balanco']['afericao']['somas']
    if r['tipo'] == 'normal':
        primeira = f'ΣP = ΣETR + ΣEXC: {num(s["p"])} = {num(s["etr"])} + {num(s["exc"])}'
    else:
        primeira = (f'ΣP = ΣETR + ΣEXC + variação do armazenamento: {num(s["p"])} = {num(s["etr"])} + {num(s["exc"])} '
                    f'+ ({sinal(a["variacao_do_armazenamento"])})')
    fechou = max(abs(a['residuo_p']), abs(a['residuo_etp']), abs(a['residuo_alt'])) < 0.005
    return [primeira, f'ΣETP = ΣETR + ΣDEF: {num(s["etp"])} = {num(s["etr"])} + {num(s["def"])}',
            'As identidades fecham.' if fechou else 'AS IDENTIDADES NÃO FECHARAM: não use este balanço.']


def frases_das_escolhas(r):
    n = r['normais']
    saida = [f'CAD: {num(r["cad"], 0)} mm (informada pelo usuário).', f'ETP: {nome_do_metodo(r)}.']
    if r['tipo'] == 'sequencial':
        if r.get('origem_dos_periodos'):
            saida.append(f'Chuva e temperatura de cada período: {r["origem_dos_periodos"]}.')
        saida.append(f'Armazenamento inicial: {r["origem_do_armazenamento"]}.')
    if r['tipo'] == 'normal':
        saida.append(f'Chuva normal: {n["origem_chuva"]}.')
        if r['metodo'] != 'informada':
            saida.append(f'Temperatura normal: {n["origem_temperatura"]}.')
    if r['calor']:
        saida.append(f'Índice de calor de Thornthwaite: I = {num(r["calor"][0], 2)}; a = {num(r["calor"][1], 3)}'
                     + (f' (temperaturas normais: {n["origem_temperatura"]})' if r['tipo'] == 'sequencial' else '') + '.')
    if r['metodo'] != 'informada':
        saida.append(f'Latitude usada no fotoperíodo e na radiação: {num(r["latitude"], 2)}°.')
    return saida


def relatorio(caminho_pdf, caminho_png, r, meta):
    """Relatório em A4 deitado: a tabela do balanço com as escolhas e a aferição; depois os gráficos."""
    normal = r['tipo'] == 'normal'
    s = r['balanco']['afericao']['somas']
    unidade = 'mm no ano' if normal else 'mm no período'
    kpis = [('Chuva', num(s['p'], 0), unidade), ('ETP', num(s['etp'], 0), unidade),
            ('Deficiência', num(s['def'], 0), unidade), ('Excedente', num(s['exc'], 0), unidade)]
    fontes = list(meta['fontes'])
    curta = len(fontes) == 1 and len(fontes[0]) <= 90      # uma fonte curta cabe no rodapé; as outras vão para o quadro
    rodape = (f'comunidade agrônomo10X · gerado em {meta["data"]} · '
              + (f'dados: {fontes[0]}' if curta else f'fontes: no quadro "{QUADRO_DAS_FONTES}"'))
    passo_txt = 'por mês' if r['passo'] == 'mes' else 'por decêndio'
    if normal:
        subtitulo = f'Balanço hídrico climatológico normal · CAD {num(r["cad"], 0)} mm · Thornthwaite e Mather (1955)'
    else:
        subtitulo = (f'Balanço hídrico sequencial {passo_txt} · {r["linhas"][0]["inicio"]:%d/%m/%Y} a '
                     f'{r["linhas"][-1]["fim"]:%d/%m/%Y} · CAD {num(r["cad"], 0)} mm')
    resumida = len(r['linhas']) > PERIODOS_NA_TABELA
    linhas = [_linha_da_tabela(l, normal) for l in (resumo_por_ano(r) if resumida else r['linhas'])] + [_total(r)]
    blocos = [('Escolhas e origem dos números', frases_das_escolhas(r)), ('Aferição', frases_da_afericao(r))]
    if not normal:
        blocos.append(('Armazenamento inicial', [r['dependencia']]))
    resumo = (['A tabela deste PDF está resumida por ano (ARM: o armazenamento no fim de cada ano); todos os períodos '
               'estão no arquivo CSV.'] if resumida else [])
    blocos.append(('Avisos', (resumo + r['avisos'] + meta.get('avisos', [])) or ['Nenhum aviso neste balanço.']))
    pendentes = blocos
    with PdfPages(caminho_pdf) as pdf:
        for pagina, ini in enumerate(range(0, len(linhas), LINHAS_POR_PAGINA + 1)):
            parte = linhas[ini:ini + LINHAS_POR_PAGINA + 1]
            fig = _pagina(meta['titulo'], subtitulo, kpis, rodape)
            esq = _painel(fig, [0.035, 0.085, 0.585, 0.755])
            de_ate = '' if len(linhas) <= LINHAS_POR_PAGINA + 1 else f' ({ini + 1} a {min(len(linhas) - 1, ini + len(parte))} de {len(linhas) - 1})'
            nome_da_tabela = ('Balanço do ano normal, em mm' if normal else
                              'Resumo por ano, em mm' if resumida else
                              f'Balanço {passo_txt}, em mm')
            y = _titulo(esq, 0.985, nome_da_tabela + de_ate)
            ultima = ini + len(parte) >= len(linhas)
            y = _tabela(esq, y, _colunas(normal), parte, passo=0.045 if normal else 0.0365, fonte=7.2 if normal else 6.6,
                        destaque={len(parte) - 1} if ultima else None)
            if normal:
                y = _texto(esq, y - 0.03, ['T: temperatura média. P: chuva. ETP: evapotranspiração potencial. Neg.ac: '
                                           'negativo acumulado. ARM: armazenamento. ALT: alteração do armazenamento. ETR: '
                                           'evapotranspiração real. DEF: deficiência. EXC: excedente.',
                                           r['balanco']['partida'][0].upper() + r['balanco']['partida'][1:] + '.'],
                           118, fonte=6.5, cor='fg3')
            if ultima and not curta and not _fontes_no_painel(esq, y - 0.03, fontes, 122):
                pendentes = list(pendentes) + [(QUADRO_DAS_FONTES, fontes)]      # sem lugar embaixo da tabela: depois dos avisos
            pendentes = _blocos(_painel(fig, [0.665, 0.085, 0.30, 0.755]), 0.985, pendentes, 58)
            pdf.savefig(fig)
            if pagina == 0:
                fig.savefig(caminho_png, dpi=140)
            plt.close(fig)
        while pendentes:        # avisos que não couberam ao lado da tabela
            fig = _pagina(meta['titulo'], subtitulo, kpis, rodape)
            antes = pendentes
            pendentes = _blocos(_painel(fig, [0.035, 0.085, 0.93, 0.755]), 0.985, pendentes, 190)
            pdf.savefig(fig)
            plt.close(fig)
            if pendentes == antes:
                break
        fig = _pagina(meta['titulo'], subtitulo, kpis, rodape)
        extrato(fig.add_axes([0.06, 0.50, 0.42, 0.29]), r)
        chuva_e_etp(fig.add_axes([0.545, 0.50, 0.42, 0.29]), r)
        armazenamento(fig.add_axes([0.06, 0.135, 0.42, 0.25]), r)
        nota = _painel(fig, [0.545, 0.10, 0.42, 0.29])
        y = _titulo(nota, 0.98, 'Como ler') - 0.06
        _texto(nota, y, ['Excedente é a água que passa da CAD quando o solo está cheio. Deficiência é o que faltou '
                         'para a evapotranspiração real chegar à potencial.',
                         'O armazenamento cai enquanto a chuva é menor que a ETP e sobe quando é maior, até a CAD.',
                         'O balanço é climatológico: não considera a cultura, a fase da lavoura, irrigação nem '
                         'escorrimento. Do solo, a única informação é a CAD.'], 82, fonte=6.8, cor='fg2', passo=0.085)
        pdf.savefig(fig)
        plt.close(fig)


if __name__ == '__main__':
    import os
    import tempfile

    import caso
    import entrada
    import sintetico

    assert num(1234.56) == '1.234,6' and num(None) == '—' and num(-0.04) == '0,0' and sinal(12.34) == '+12,3'
    assert sinal(-3) == '-3,0' and sinal(0) == '0,0' and _br(1.5) == '1,50' and _br(None) == ''
    with tempfile.TemporaryDirectory() as pasta:
        p = lambda nome: os.path.join(pasta, nome)
        open(p('m.txt'), 'w', encoding='utf-8').write(sintetico.arquivo_mensal())
        open(p('d.txt'), 'w', encoding='utf-8').write(sintetico.arquivo_diario())
        mensal, diario = entrada.ler(p('m.txt')), entrada.ler(p('d.txt'))
        n = caso.normais(mensal, chuva='referencia')
        meta = {'titulo': sintetico.NOME, 'data': '15/11/2026', 'fontes': ['exemplo inventado'], 'avisos': []}
        casos = [caso.ano_normal(n, 'thornthwaite', sintetico.LATITUDE, 100),
                 caso.ano_normal(n, 'hargreaves', sintetico.LATITUDE, 60),
                 caso.em_sequencia(entrada.periodos_do_diario(diario['registros'])[0], 'decendio', 'thornthwaite-tef',
                                   sintetico.LATITUDE, 100, 'normal', n),
                 caso.em_sequencia(entrada.periodos_do_diario(diario['registros'], 'mes')[0], 'mes', 'hargreaves',
                                   sintetico.LATITUDE, 100, 'cad'),
                 caso.em_sequencia(entrada.periodos_do_mensal(mensal['registros']), 'mes', 'thornthwaite',
                                   sintetico.LATITUDE, 150, '75', n)]
        for k, r in enumerate(casos):
            relatorio(p(f'r{k}.pdf'), p(f'r{k}.png'), r, meta)
            figura(p(f'f{k}.png'), r, 'Balanço hídrico')
            assert os.path.getsize(p(f'r{k}.pdf')) > 20000 and os.path.getsize(p(f'f{k}.png')) > 8000, k
            assert gravar_csv(p(f't{k}.csv'), r) == len(r['linhas']) + 1
            assert 'fecham' in frases_da_afericao(r)[-1]
        # várias fontes (o bloco da ferramenta): saem no quadro "Fontes dos dados", e o rodapé aponta para ele
        varias = dict(meta, fontes=['Chuva: instituto de exemplo A e produto de exemplo B (universidade de exemplo).',
                                    'Média histórica de 1991 a 2020: produto de exemplo B.',
                                    'Temperatura, umidade e vento: fonte de exemplo C.'])
        relatorio(p('rf.pdf'), p('rf.png'), casos[0], varias)
        assert os.path.getsize(p('rf.pdf')) > 20000
        texto = open(p('t0.csv'), encoding='utf-8-sig').read().splitlines()
        assert texto[0].startswith('mes;dias;temperatura_media;chuva;etp') and texto[1].startswith('jan;31;')
        assert texto[-1].startswith('total;365;') and len(texto) == 14
        texto = open(p('t2.csv'), encoding='utf-8-sig').read().splitlines()
        assert texto[1].startswith('2024-07-01;2024-07-10;10;') and len(texto) == 38
    print('saidas OK')
