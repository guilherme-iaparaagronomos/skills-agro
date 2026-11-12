"""Arquivos de saída da limpeza: CSV, shapefile de pontos, figura do diagnóstico e o
relatório em PDF, no formato dos documentos da casa.

Teste embutido: python scripts/saidas.py
"""

import csv
import datetime
import struct
import textwrap
import zipfile

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from limpeza import num  # noqa: E402

# tokens do design system da casa (tema claro de impressão) e paleta de dataviz
T = dict(pagina='#FBFCF9', fg1='#121810', fg2='#3C4636', fg3='#6B7562', line='#D4DBCA',
         line_forte='#B4BFA8', verde='#2E8B1E', mapa='#FFFFFF')
DATAVIZ = ['#C26A3D', '#4FB7C9', '#E8B33B', '#8A7556', '#2F8B1F', '#7D5BA6', '#D1495B', '#3B6FB6', '#52C937',
           '#6B5A40', '#E07A5F', '#1B998B']
CLASSES = ['#d73027', '#fc8d59', '#fee08b', '#91cf60', '#1a9850']
ROTULO_DOC = 'agrônomo10X · Limpeza de dados densos'
MONO = 'DejaVu Sans Mono'
PRJ_WGS84 = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')
TETO_DE_PONTOS_NO_MAPA = 120000


def prj_utm(zona, sul):
    return ('PROJCS["SIRGAS_2000_UTM_Zone_%d%s",GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",'
            'SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],'
            'UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
            'PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",%s],'
            'PARAMETER["Central_Meridian",%s],PARAMETER["Scale_Factor",0.9996],'
            'PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]'
            % (zona, 'S' if sul else 'N', '10000000.0' if sul else '0.0', float(zona * 6 - 183)))


def espacado(texto):
    return ' '.join(str(texto).upper())


# ------------------------------------------------------------------ tabelas
def _texto_da_coluna(vetor):
    if vetor.dtype.kind in 'fiu':
        return ['' if not np.isfinite(v) else format(float(v), '.10g') for v in vetor.astype(float)]
    return [str(v) for v in vetor]


def gravar_csv(caminho, tabela, linhas, extra=None):
    """Grava as linhas escolhidas com as colunas do arquivo original, na mesma ordem, mais as de `extra`."""
    nomes = list(tabela['colunas'])
    colunas = [_texto_da_coluna(np.asarray(tabela['dados'][n])[linhas]) for n in nomes]
    for nome, vetor in (extra or {}).items():
        nomes.append(nome)
        colunas.append(_texto_da_coluna(np.asarray(vetor)[linhas]))
    with open(caminho, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(nomes)
        w.writerows(zip(*colunas))
    return len(colunas[0]) if colunas else 0


def _nomes_dbf(nomes):
    saida = []
    for nome in nomes:
        limpo = ''.join(c if c.isascii() and (c.isalnum() or c == '_') else '_' for c in str(nome))[:10] or 'campo'
        base, k = limpo, 1
        while limpo.upper() in (s.upper() for s in saida):
            k += 1
            limpo = base[:10 - len(str(k))] + str(k)
        saida.append(limpo)
    return saida


def shapefile_de_pontos(x, y, colunas):
    """Monta .shp, .shx e .dbf de pontos. `colunas` = {nome: vetor}; número vira campo numérico."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    caixa = (x.min(), y.min(), x.max(), y.max()) if n else (0.0, 0.0, 0.0, 0.0)

    def cabecalho(tamanho_em_bytes):
        return struct.pack('>7i', 9994, 0, 0, 0, 0, 0, tamanho_em_bytes // 2) + struct.pack('<2i8d', 1000, 1, *caixa,
                                                                                            0, 0, 0, 0)

    registros = np.zeros(n, dtype=[('num', '>i4'), ('tam', '>i4'), ('tipo', '<i4'), ('x', '<f8'), ('y', '<f8')])
    registros['num'], registros['tam'], registros['tipo'] = np.arange(1, n + 1), 10, 1
    registros['x'], registros['y'] = x, y
    indice = np.zeros(n, dtype=[('pos', '>i4'), ('tam', '>i4')])
    indice['pos'], indice['tam'] = (100 + 28 * np.arange(n)) // 2, 10

    campos, textos = [], []
    for nome, vetor in zip(_nomes_dbf(colunas), colunas.values()):
        vetor = np.asarray(vetor)
        if vetor.dtype.kind in 'fiu':
            v = vetor.astype(float)
            inteiro = bool(np.all(~np.isfinite(v) | (v == np.round(v))))
            largura, casas = (14, 0) if inteiro else (18, 6)
            texto = np.char.mod(f'%{largura}.{casas}f', np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0))
            texto = np.where(np.isfinite(v), texto, ' ' * largura)
            texto = np.array([t[-largura:] for t in texto]) if n else texto
            campos.append((nome, b'N', largura, casas))
        else:
            cru = [str(t).encode('latin-1', 'replace').decode('latin-1') for t in vetor]
            largura = max(1, min(80, max((len(t) for t in cru), default=1)))
            texto = np.array([t[:largura].ljust(largura) for t in cru]) if n else np.array([], dtype=str)
            campos.append((nome, b'C', largura, 0))
        textos.append(texto)
    tamanho_registro = 1 + sum(c[2] for c in campos)
    hoje = datetime.date.today()
    dbf = struct.pack('<B3BIHH20x', 3, hoje.year - 1900, hoje.month, hoje.day, n, 32 + 32 * len(campos) + 1,
                      tamanho_registro)
    for nome, tipo, largura, casas in campos:
        dbf += struct.pack('<11sc4xBB14x', nome.encode('ascii'), tipo, largura, casas)
    dbf += b'\r'
    if n:
        linhas = np.full(n, ' ')
        for texto in textos:
            linhas = np.char.add(linhas, texto)
        dbf += ''.join(linhas.tolist()).encode('latin-1', 'replace')
    dbf += b'\x1a'
    return {'.shp': cabecalho(100 + 28 * n) + registros.tobytes(), '.shx': cabecalho(100 + 8 * n) + indice.tobytes(),
            '.dbf': dbf}


def gravar_shapefile_zip(caminho, x, y, colunas, prj=None, base='pontos-limpos'):
    partes = shapefile_de_pontos(x, y, colunas)
    if prj:
        partes['.prj'] = prj.encode('ascii')
    with zipfile.ZipFile(caminho, 'w', zipfile.ZIP_DEFLATED) as z:
        for ext, dados in partes.items():
            z.writestr(base + ext, dados)


# ------------------------------------------------------------------ desenho
def _moldura(fig, titulo, subtitulo, kpis, rodape):
    fig.text(0.035, 0.955, espacado(ROTULO_DOC), fontsize=6.4, color=T['verde'], va='center', fontweight='bold')
    titulo = titulo if len(titulo) <= 46 else titulo[:45].rstrip() + '…'
    fig.text(0.035, 0.915, titulo, fontsize=15.5, color=T['fg1'], va='center', fontstyle='italic', fontweight='bold')
    fig.text(0.035, 0.878, subtitulo, fontsize=9.5, color=T['fg2'], va='center')
    x = 0.965
    for rotulo, valor, unidade in reversed(kpis):
        fig.text(x, 0.955, espacado(rotulo), fontsize=5.8, color=T['fg3'], va='center', ha='right')
        fig.text(x, 0.918, valor, fontsize=14, color=T['fg1'], va='center', ha='right', family=MONO, fontweight='bold')
        fig.text(x, 0.885, unidade, fontsize=7, color=T['fg3'], va='center', ha='right', family=MONO)
        x -= 0.028 + 0.0118 * max(len(valor), 7)  # cada indicador ocupa a largura do seu número
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.86, 0.86], color=T['line'], linewidth=0.8))
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.062, 0.062], color=T['line'], linewidth=0.8))
    fig.text(0.035, 0.044, rodape, fontsize=7, color=T['fg3'], va='center')
    fig.text(0.035, 0.026, 'A limpeza só remove pontos: não corrige nem estima valor. Os parâmetros são decisão do '
             'responsável técnico.', fontsize=6.4, color=T['fg3'], va='center')
    fig.text(0.965, 0.036, 'OagronomIA', fontsize=10.5, color=T['fg1'], va='center', ha='right', fontstyle='italic',
             fontweight='bold')


def _painel(fig, caixa):
    ax = fig.add_axes(caixa)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    return ax


def _amostra(n, teto=TETO_DE_PONTOS_NO_MAPA):
    return slice(None, None, max(1, int(np.ceil(n / teto))))


def _tamanho_do_ponto(n, area_do_mapa=150000.0):
    """Área do marcador (pontos²) para os pontos cobrirem perto de 60% do quadro do mapa."""
    return float(np.clip(0.6 * area_do_mapa / max(n, 1), 0.3, 12))


def _eixo_de_mapa(fig, caixa, areas, titulo):
    ax = fig.add_axes(caixa, facecolor=T['mapa'])
    for a in areas or []:
        for anel in a['aneis']:
            ax.plot([p[0] for p in anel] + [anel[0][0]], [p[1] for p in anel] + [anel[0][1]], color=T['fg1'],
                    linewidth=0.8, zorder=5)
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_color(T['line'])
    ax.set_title(espacado(titulo), fontsize=7.4, color=T['fg1'], fontweight='bold', loc='left', pad=6)
    return ax


def _por_classe(ax, x, y, v, cortes):
    classe = np.searchsorted(cortes, v, side='right')
    fatia = _amostra(len(x))
    ax.scatter(x[fatia], y[fatia], c=np.array(CLASSES)[classe[fatia]], s=_tamanho_do_ponto(len(x[fatia])),
               linewidths=0, rasterized=True, zorder=2)
    ax.margins(0.03)


def _legenda_de_classes(ax, cortes, unidade, casas):
    limites = [num(c, casas) for c in cortes]
    faixas = ([f'até {limites[0]}'] + [f'{a} a {b}' for a, b in zip(limites[:-1], limites[1:])]
              + [f'acima de {limites[-1]}'])
    marcas = [plt.Line2D([], [], marker='s', linestyle='', color=c, markersize=6) for c in CLASSES]
    ax.legend(marcas, faixas, title=f'Classes (quintis do dado limpo){", " + unidade if unidade else ""}', loc='center',
              ncol=5, frameon=False, fontsize=7, title_fontsize=7, handletextpad=0.2, columnspacing=1.6)


def _histograma(ax, antes, depois, unidade):
    antes, depois = antes[np.isfinite(antes)], depois[np.isfinite(depois)]
    lo, hi = np.percentile(antes, [0.5, 99.5]) if len(antes) else (0, 1)
    if hi <= lo:
        hi = lo + 1
    caixas = np.linspace(lo, hi, 50)
    ax.hist(np.clip(antes, lo, hi), bins=caixas, color=T['line_forte'], label='bruto')
    ax.hist(np.clip(depois, lo, hi), bins=caixas, color=T['verde'], alpha=0.85, label='limpo')
    ax.set_xlabel(unidade or 'valor', fontsize=7, color=T['fg2'])
    ax.tick_params(labelsize=6.5, colors=T['fg3'])
    ax.set_yticks([])
    for lado in ('top', 'right', 'left'):
        ax.spines[lado].set_visible(False)
    ax.spines['bottom'].set_color(T['line'])
    ax.legend(frameon=False, fontsize=7)
    ax.set_title(espacado('Distribuição do valor'), fontsize=7.4, color=T['fg1'], fontweight='bold', loc='left', pad=6)


def _rampa(ax, entrada, saida, k_ini, k_fim):
    ax.set_title(espacado('Entrada e saída das passadas'), fontsize=7.4, color=T['fg1'], fontweight='bold',
                 loc='left', pad=6)
    if entrada is None:
        ax.text(0.5, 0.5, 'sem passadas longas o bastante para medir', ha='center', va='center', fontsize=7.5,
                color=T['fg3'], transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        posicoes = np.arange(1, len(entrada) + 1)
        ax.plot(posicoes, entrada, color=T['verde'], marker='o', markersize=2.6, linewidth=1.1, label='começo')
        ax.plot(posicoes, saida, color=DATAVIZ[0], marker='o', markersize=2.6, linewidth=1.1, label='fim (de trás para frente)')
        ax.axhline(0.9, color=T['line_forte'], linewidth=0.8, linestyle='--')
        for k, cor in ((k_ini, T['verde']), (k_fim, DATAVIZ[0])):
            if k:
                ax.axvline(k + 0.5, color=cor, linewidth=0.8, linestyle=':')
        ax.set_xlabel('posição do ponto na passada', fontsize=7, color=T['fg2'])
        ax.set_ylabel('valor ÷ trecho vizinho', fontsize=7, color=T['fg2'])
        ax.tick_params(labelsize=6.5, colors=T['fg3'])
        ax.legend(frameon=False, fontsize=6.5, loc='lower right')
    for lado in ('top', 'right'):
        ax.spines[lado].set_visible(False)
    for lado in ('bottom', 'left'):
        ax.spines[lado].set_color(T['line'])


def _tabela_de_etapas(ax, etapas, total):
    y = 0.985
    ax.text(0, y, espacado('Filtros, na ordem em que rodaram'), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
    y -= 0.05
    for titulo, xc, alinh in (('Filtro', 0.03, 'left'), ('Regra', 0.33, 'left'), ('Saíram', 0.90, 'right'),
                              ('%', 1.0, 'right')):
        ax.text(xc, y, espacado(titulo), fontsize=5.4, color=T['fg3'], va='center', ha=alinh)
    y -= 0.018
    ax.plot([0, 1], [y, y], color=T['line'], linewidth=0.8)
    for k, e in enumerate(etapas, 1):
        regra = textwrap.wrap(e['pulado'] and f'não rodou: {e["pulado"]}' or e['parametro'], 56) or ['']
        altura = 0.028 * len(regra) + 0.016
        cor = T['fg3'] if e['pulado'] else T['fg1']
        topo = y - 0.022
        ax.text(0, topo, str(k), fontsize=6.6, color=T['fg3'], va='center', family=MONO)
        ax.text(0.03, topo, e['nome'], fontsize=7.4, color=cor, va='center', fontweight='normal' if e['pulado'] else 'bold')
        ax.text(0.33, topo + 0.011, '\n'.join(regra), fontsize=6.8, color=T['fg3'] if e['pulado'] else T['fg2'], va='top',
                linespacing=1.35)
        if not e['pulado']:
            ax.text(0.90, topo, f'{e["removidos"]:,}'.replace(',', '.'), fontsize=7.4, color=T['fg1'], va='center',
                    ha='right', family=MONO)
            ax.text(1.0, topo, num(100 * e['removidos'] / total if total else 0, 1), fontsize=7.4, color=T['fg1'],
                    va='center', ha='right', family=MONO)
        y -= altura
        ax.plot([0, 1], [y, y], color=T['line'], linewidth=0.4)
    return y


def relatorio(caminho_pdf, caminho_png, d, r, meta):
    """Relatório em três páginas A4 deitadas: resumo e filtros; mapa bruto e limpo; o que saiu."""
    v, motivo = d['valor'], r['motivo']
    ficou = motivo == 0
    tem_posicao = np.isfinite(d['x']) & np.isfinite(d['y'])
    unidade, casas = meta.get('unidade', ''), meta.get('casas', 2)
    total = r['pontos']
    pct = 100 * r['removidos'] / total if total else 0
    kpis = [('Pontos lidos', f'{total:,}'.replace(',', '.'), 'no arquivo'),
            ('Mantidos', f'{r["mantidos"]:,}'.replace(',', '.'), f'{num(100 - pct, 1)}%'),
            ('Removidos', f'{r["removidos"]:,}'.replace(',', '.'), f'{num(pct, 1)}%'),
            ('CV', f'{num(r["antes"].get("cv"), 1)} → {num(r["depois"].get("cv"), 1)}', '% antes → depois')]
    rodape = f'comunidade agrônomo10X · gerado em {meta["data"]} · arquivo {meta["arquivo"]}'
    subtitulo = ' · '.join(p for p in (meta.get('coluna'), unidade, f'perfil {meta["perfil"]}') if p)

    with PdfPages(caminho_pdf) as pdf:
        # ---- página 1: resumo
        fig = plt.figure(figsize=(11.69, 8.27), facecolor=T['pagina'])
        _moldura(fig, meta['titulo'], subtitulo, kpis, rodape)
        _tabela_de_etapas(_painel(fig, [0.035, 0.085, 0.585, 0.755]), r['etapas'], total)
        lado = _painel(fig, [0.66, 0.085, 0.305, 0.755])
        y = 0.985
        lado.text(0, y, espacado('Antes e depois'), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
        y -= 0.05
        for titulo, xc in (('Bruto', 0.66), ('Limpo', 1.0)):
            lado.text(xc, y, espacado(titulo), fontsize=5.4, color=T['fg3'], va='center', ha='right')
        y -= 0.018
        lado.plot([0, 1], [y, y], color=T['line'], linewidth=0.8)
        for rotulo, chave, c in (('Pontos com valor', 'n', 0), ('Média', 'media', casas), ('Mediana', 'mediana', casas),
                                 ('Desvio-padrão', 'dp', casas), ('CV (%)', 'cv', 1), ('Mínimo', 'min', casas),
                                 ('Máximo', 'max', casas)):
            y -= 0.036
            lado.text(0, y, rotulo, fontsize=7.6, color=T['fg1'], va='center')
            for xc, bloco in ((0.66, r['antes']), (1.0, r['depois'])):
                valor = bloco.get(chave)
                texto = f'{valor:,}'.replace(',', '.') if chave == 'n' and valor is not None else num(valor, c)
                lado.text(xc, y, texto, fontsize=7.4, color=T['fg1'], va='center', ha='right', family=MONO)
        y -= 0.065
        lado.text(0, y, espacado('Avisos'), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
        y -= 0.045
        avisos = r['alertas'] or ['Nenhum aviso nesta limpeza.']
        for aviso in avisos:
            partes = textwrap.wrap(aviso, 58)
            if y - 0.026 * len(partes) < 0.02:
                lado.text(0, y, '… (os demais avisos estão no relatorio.json)', fontsize=6.8, color=T['fg3'], va='top')
                break
            lado.text(0, y, '\n'.join(partes), fontsize=6.9, color=T['fg2'], va='top', linespacing=1.4)
            y -= 0.026 * len(partes) + 0.014
        pdf.savefig(fig)
        fig.savefig(caminho_png, dpi=140)
        plt.close(fig)

        # ---- página 2: mapa bruto e mapa limpo, nas mesmas classes
        fig = plt.figure(figsize=(11.69, 8.27), facecolor=T['pagina'])
        _moldura(fig, meta['titulo'], 'Mapa de pontos · bruto e limpo nas mesmas classes', kpis, rodape)
        limpos = v[ficou]
        cortes = np.percentile(limpos, [20, 40, 60, 80]) if len(limpos) else np.array([0, 1, 2, 3])
        com_valor = tem_posicao & np.isfinite(v)
        for caixa, titulo, quais in (([0.035, 0.16, 0.455, 0.66], 'Bruto', com_valor),
                                     ([0.51, 0.16, 0.455, 0.66], 'Limpo', ficou)):
            ax = _eixo_de_mapa(fig, caixa, d.get('areas'), f'{titulo} · {int(quais.sum()):,} pontos'.replace(',', '.'))
            _por_classe(ax, d['x'][quais], d['y'][quais], v[quais], cortes)
            if titulo == 'Bruto':
                enquadre = (ax.get_xlim(), ax.get_ylim())
            ax.set_xlim(*enquadre[0])  # os dois mapas no mesmo enquadramento
            ax.set_ylim(*enquadre[1])
        _legenda_de_classes(_painel(fig, [0.035, 0.075, 0.93, 0.07]), cortes, unidade, casas)
        pdf.savefig(fig, dpi=200)
        plt.close(fig)

        # ---- página 3: o que saiu
        fig = plt.figure(figsize=(11.69, 8.27), facecolor=T['pagina'])
        _moldura(fig, meta['titulo'], 'O que saiu, por filtro', kpis, rodape)
        ax = _eixo_de_mapa(fig, [0.035, 0.185, 0.56, 0.645], d.get('areas'), 'Pontos removidos, pela cor do filtro')
        fatia = _amostra(int(ficou.sum()))
        ax.scatter(d['x'][ficou][fatia], d['y'][ficou][fatia], color='#E4E8DD',
                   s=0.5 * _tamanho_do_ponto(int(ficou.sum())), linewidths=0, rasterized=True, zorder=1)
        marcas, nomes = [], []
        for k, e in enumerate(r['etapas'], 1):
            quais = (motivo == k) & tem_posicao
            if not quais.any():
                continue
            cor = DATAVIZ[(k - 1) % len(DATAVIZ)]
            ax.scatter(d['x'][quais], d['y'][quais], color=cor, s=float(np.clip(_tamanho_do_ponto(total), 2.5, 9)),
                       linewidths=0, rasterized=True, zorder=3)
            marcas.append(plt.Line2D([], [], marker='o', linestyle='', color=cor, markersize=4.5))
            nomes.append(f'{e["nome"]} ({e["removidos"]:,})'.replace(',', '.'))
        ax.set_xlim(*enquadre[0])
        ax.set_ylim(*enquadre[1])
        if marcas:
            _painel(fig, [0.035, 0.075, 0.56, 0.095]).legend(marcas, nomes, loc='upper left', ncol=3, frameon=False,
                                                             fontsize=6.6, handletextpad=0.2, columnspacing=1.2,
                                                             borderaxespad=0)
        _histograma(fig.add_axes([0.65, 0.52, 0.315, 0.28]), v[np.isfinite(v)], limpos, unidade)
        info = r['info']
        _rampa(fig.add_axes([0.665, 0.15, 0.30, 0.25]), None if info.get('rampa_entrada') is None
               else np.array(info['rampa_entrada']), None if info.get('rampa_saida') is None
               else np.array(info['rampa_saida']), info.get('inicio'), info.get('fim'))
        pdf.savefig(fig, dpi=200)
        plt.close(fig)


def figura_do_diagnostico(caminho_png, d, diag, meta):
    """Uma página para escolher os parâmetros: distribuição do valor, velocidade, rampa e mapa bruto."""
    v = d['valor']
    unidade = meta.get('unidade', '')
    fig = plt.figure(figsize=(11.69, 8.27), facecolor=T['pagina'])
    e = diag['valor']
    kpis = [('Pontos', f'{diag["pontos"]:,}'.replace(',', '.'), 'no arquivo'),
            ('Passadas', str(diag['passadas'].get('passadas', '—')), 'detectadas'),
            ('Mediana', num(e.get('mediana'), meta.get('casas', 2)), unidade or 'valor'),
            ('CV', num(e.get('cv'), 1), '% bruto')]
    _moldura(fig, meta['titulo'], 'Diagnóstico do arquivo bruto · nada foi removido ainda', kpis,
             f'comunidade agrônomo10X · gerado em {meta["data"]} · arquivo {meta["arquivo"]}')
    ax = fig.add_axes([0.05, 0.52, 0.27, 0.28])
    finitos = v[np.isfinite(v)]
    _histograma(ax, finitos, finitos[:0], unidade)
    ax.get_legend().remove()
    previsto = diag.get('limites_globais_previstos')
    if previsto:
        for limite in (previsto['inferior'], previsto['superior']):
            ax.axvline(limite, color=DATAVIZ[0], linewidth=0.9, linestyle='--')
    ax = fig.add_axes([0.05, 0.14, 0.27, 0.26])
    vel = d.get('velocidade')
    ax.set_title(espacado('Velocidade'), fontsize=7.4, color=T['fg1'], fontweight='bold', loc='left', pad=6)
    if vel is not None and np.isfinite(vel).any():
        bons = vel[np.isfinite(vel)]
        hi = np.percentile(bons, 99.5)
        ax.hist(np.clip(bons, 0, hi), bins=50, color=T['line_forte'])
        mediana = float(np.median(bons))
        for limite in (0.5 * mediana, 1.5 * mediana):
            ax.axvline(limite, color=DATAVIZ[0], linewidth=0.9, linestyle='--')
        ax.set_xlabel(f'velocidade ({diag["velocidade"].get("unidade_provavel") or "unidade do arquivo"})', fontsize=7,
                      color=T['fg2'])
        ax.tick_params(labelsize=6.5, colors=T['fg3'])
        ax.set_yticks([])
    else:
        ax.text(0.5, 0.5, 'sem coluna de velocidade', ha='center', va='center', fontsize=7.5, color=T['fg3'],
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
    for lado in ('top', 'right', 'left'):
        ax.spines[lado].set_visible(False)
    ax.spines['bottom'].set_color(T['line'])
    rampa = diag['rampa']
    _rampa(fig.add_axes([0.38, 0.52, 0.25, 0.28]), None if rampa['entrada'] is None else np.array(rampa['entrada']),
           None if rampa['saida'] is None else np.array(rampa['saida']), rampa['sugestao_inicio'], rampa['sugestao_fim'])
    notas = _painel(fig, [0.38, 0.10, 0.25, 0.32])
    notas.text(0, 0.98, espacado('O que o arquivo não tem'), fontsize=7.4, fontweight='bold', color=T['fg1'], va='top')
    y = 0.86
    for linha in diag['o_que_falta'] or ['Tem tudo o que os filtros usam.']:
        partes = textwrap.wrap(linha, 46)
        notas.text(0, y, '\n'.join(partes), fontsize=6.9, color=T['fg2'], va='top', linespacing=1.4)
        y -= 0.085 * len(partes) + 0.04
    ok = np.isfinite(d['x']) & np.isfinite(d['y']) & np.isfinite(v)
    ax = _eixo_de_mapa(fig, [0.68, 0.16, 0.285, 0.64], d.get('areas'), 'Mapa bruto (quintis)')
    if ok.any():
        _por_classe(ax, d['x'][ok], d['y'][ok], v[ok], np.percentile(v[ok], [20, 40, 60, 80]))
    fig.savefig(caminho_png, dpi=140)
    plt.close(fig)


if __name__ == '__main__':
    import os
    import tempfile

    import limpeza
    import shapefile_min
    import sintetico

    assert _nomes_dbf(['Produtividade (t/ha)', 'Produtividade (kg)', 'Ação']) == ['Produtivid', 'Produtivi2', 'A__o']
    assert 'Central_Meridian",-51.0' in prj_utm(22, True) and 'Zone_22S' in prj_utm(22, True)
    ex = sintetico.talhao()
    c = ex['colunas']
    tabela = {'colunas': list(c), 'dados': c}
    import areas as _areas
    per, _, _ = _areas.para_utm([{'nome': 'Exemplo', 'aneis': [ex['perimetro']]}], 'geo')
    d = {'x': ex['x'], 'y': ex['y'], 'valor': c['Prod_t_ha'].astype(float), 'velocidade': c['Veloc_kmh'],
         'umidade': c['Umidade'], 'largura': c['Largura_m'], 'passada': None, 'areas': per,
         't': np.array([int(h[:2]) * 3600 + int(h[3:5]) * 60 + int(h[6:]) for h in c['Hora']], dtype=float)}
    r = limpeza.limpar(d, limpeza.PERFIS['colheita'])
    meta = {'titulo': 'Talhão de exemplo', 'arquivo': 'exemplo.csv', 'coluna': 'Prod_t_ha', 'unidade': 't/ha',
            'perfil': 'colheita', 'data': '12/11/2026', 'casas': 2}
    with tempfile.TemporaryDirectory() as pasta:
        p = os.path.join
        ficou = r['motivo'] == 0
        assert gravar_csv(p(pasta, 'limpos.csv'), tabela, ficou) == r['mantidos']
        linhas = open(p(pasta, 'limpos.csv'), encoding='utf-8').read().splitlines()
        assert linhas[0] == 'Longitude,Latitude,Hora,Prod_t_ha,Veloc_kmh,Umidade,Largura_m' and len(linhas) == r['mantidos'] + 1
        nomes = np.array([''] + [e['nome'] for e in r['etapas']], dtype=object)
        gravar_csv(p(pasta, 'removidos.csv'), tabela, ~ficou, {'motivo': nomes[r['motivo']]})
        assert 'Fora do perímetro' in open(p(pasta, 'removidos.csv'), encoding='utf-8').read()
        colunas = {n: c[n][ficou] for n in c}
        gravar_shapefile_zip(p(pasta, 'limpos.zip'), c['Longitude'][ficou], c['Latitude'][ficou], colunas, PRJ_WGS84)
        with zipfile.ZipFile(p(pasta, 'limpos.zip')) as z:
            assert sorted(z.namelist()) == ['pontos-limpos.dbf', 'pontos-limpos.prj', 'pontos-limpos.shp',
                                            'pontos-limpos.shx']
            z.extractall(pasta)
        tipo, geoms, atributos, _ = shapefile_min.ler_shp(p(pasta, 'pontos-limpos.shp'))
        assert tipo == 'ponto' and len(geoms) == r['mantidos'] and abs(geoms[0][0] - colunas['Longitude'][0]) < 1e-9
        assert abs(float(atributos[5]['Prod_t_ha']) - colunas['Prod_t_ha'][5]) < 1e-6 and atributos[0]['Hora'] == '08:00:04'
        relatorio(p(pasta, 'r.pdf'), p(pasta, 'r.png'), d, r, meta)
        figura_do_diagnostico(p(pasta, 'd.png'), d, limpeza.diagnosticar(d, limpeza.PERFIS['colheita']), meta)
        assert os.path.getsize(p(pasta, 'r.pdf')) > 30000 and os.path.getsize(p(pasta, 'r.png')) > 30000
        assert os.path.getsize(p(pasta, 'd.png')) > 30000
    print('saidas OK')
