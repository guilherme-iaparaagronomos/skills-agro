"""Arquivos de saída das zonas: polígonos (GeoJSON, KML, shapefile), raster, tabelas e o
relatório em PDF, no formato dos documentos da casa.

Teste embutido: python scripts/saidas.py
"""

import csv
import datetime
import struct
import textwrap
import zipfile
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from matplotlib.path import Path as Caminho  # noqa: E402

from areas import utm_inversa  # noqa: E402

T = dict(pagina='#FBFCF9', fg1='#121810', fg2='#3C4636', fg3='#6B7562', line='#D4DBCA',
         line_forte='#B4BFA8', verde='#2E8B1E', mapa='#FFFFFF')
# do marrom ao verde: a zona 1 (menor média da camada de ordenação) é a mais marrom
CORES = ['#8C510A', '#BF812D', '#DFC27D', '#F6E8C3', '#C7EAE5', '#80CDC1', '#35978F', '#01665E']
CLASSES = ['#d73027', '#fc8d59', '#fee08b', '#91cf60', '#1a9850']
ROTULO_DOC = 'agrônomo10X · Zonas de manejo'
MONO = 'DejaVu Sans Mono'
PRJ_SIRGAS = ('GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
              'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')


def num(v, casas=2):
    if v is None or not np.isfinite(v):
        return '—'
    texto = f'{float(v):,.{casas}f}'
    return texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def espacado(texto):
    return ' '.join(str(texto).upper())


def cor_da_zona(zona, total):
    if total <= 1:
        return CORES[-2]
    return CORES[round((zona - 1) * (len(CORES) - 1) / (total - 1))]


# ------------------------------------------------------------------ geometria em graus
def em_graus(zonas, zona_utm, sul):
    """Os polígonos de cada zona em longitude e latitude: [{zona, poligonos: [[anel, …], …]}],
    cada anel fechado (o primeiro ponto repetido no fim), externo anti-horário e furos horários."""
    saida = []
    for z in zonas:
        poligonos = []
        for p in z['poligonos']:
            aneis = []
            for anel in [p['externo']] + list(p['furos']):
                lon, lat = utm_inversa(anel[:, 0], anel[:, 1], zona_utm, sul)
                pontos = [[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]
                aneis.append(pontos + [pontos[0]])
            poligonos.append(aneis)
        saida.append({'zona': z['zona'], 'poligonos': poligonos})
    return saida


def _atributos(z, nomes, casas=4):
    props = {'zona': z['zona'], 'area_ha': round(z['ha'], 2), 'pct': round(z['pct'], 1), 'partes': z['partes']}
    for nome in nomes:
        props[f'm_{nome}'] = round(z['estat'][nome]['media'], casas) if z['estat'] else None
    return props


def gravar_geojson(caminho, zonas, graus, nomes):
    import json

    feicoes = [{'type': 'Feature', 'properties': _atributos(z, nomes),
                'geometry': {'type': 'MultiPolygon', 'coordinates': g['poligonos']}}
               for z, g in zip(zonas, graus)]
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump({'type': 'FeatureCollection', 'name': 'zonas_de_manejo', 'features': feicoes}, f, ensure_ascii=False)


def gravar_kml(caminho, zonas, graus, titulo):
    total = len(zonas)
    partes = ['<?xml version="1.0" encoding="UTF-8"?>', '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
              f'<name>{escape(titulo)}</name>']
    for z in zonas:
        cor = cor_da_zona(z['zona'], total).lstrip('#')
        partes.append(f'<Style id="z{z["zona"]}"><LineStyle><color>ff000000</color><width>1.2</width></LineStyle>'
                      f'<PolyStyle><color>b3{cor[4:6]}{cor[2:4]}{cor[0:2]}</color></PolyStyle></Style>')
    for z, g in zip(zonas, graus):
        partes.append(f'<Placemark><name>Zona {z["zona"]}</name><description>{num(z["ha"])} ha ({num(z["pct"], 1)}%)'
                      f'</description><styleUrl>#z{z["zona"]}</styleUrl><MultiGeometry>')
        for poligono in g['poligonos']:
            partes.append('<Polygon>')
            for k, anel in enumerate(poligono):
                marca = 'outerBoundaryIs' if k == 0 else 'innerBoundaryIs'
                coordenadas = ' '.join(f'{x},{y},0' for x, y in anel)
                partes.append(f'<{marca}><LinearRing><coordinates>{coordenadas}</coordinates></LinearRing></{marca}>')
            partes.append('</Polygon>')
        partes.append('</MultiGeometry></Placemark>')
    partes.append('</Document></kml>')
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write('\n'.join(partes))


def _nome_dbf(nome, usados):
    limpo = ''.join(ch if ch.isascii() and (ch.isalnum() or ch == '_') else '_' for ch in str(nome))[:10] or 'campo'
    base, k = limpo, 1
    while limpo.upper() in usados:
        k += 1
        limpo = base[:10 - len(str(k))] + str(k)
    usados.add(limpo.upper())
    return limpo


def shapefile_de_poligonos(registros):
    """`registros` = [(aneis em graus (externo e furos de um ou mais polígonos, já na ordem), atributos)].
    No shapefile o anel externo é horário e o furo, anti-horário: os anéis são invertidos aqui."""
    shp, shx, caixas = bytearray(), bytearray(), []
    posicao = 50
    for n, (poligonos, _) in enumerate(registros, 1):
        aneis = [np.asarray(anel, float)[::-1] for poligono in poligonos for anel in poligono]
        pontos = np.vstack(aneis)
        inicio = np.cumsum([0] + [len(a) for a in aneis[:-1]])
        caixa = (pontos[:, 0].min(), pontos[:, 1].min(), pontos[:, 0].max(), pontos[:, 1].max())
        caixas.append(caixa)
        conteudo = (struct.pack('<i4d2i', 5, *caixa, len(aneis), len(pontos))
                    + struct.pack(f'<{len(aneis)}i', *inicio.tolist()) + pontos.astype('<f8').tobytes())
        shx += struct.pack('>2i', posicao, len(conteudo) // 2)
        shp += struct.pack('>2i', n, len(conteudo) // 2) + conteudo
        posicao += 4 + len(conteudo) // 2
    caixas = np.array(caixas) if caixas else np.zeros((1, 4))
    total = (caixas[:, 0].min(), caixas[:, 1].min(), caixas[:, 2].max(), caixas[:, 3].max())

    def cabecalho(tamanho_em_bytes):
        return struct.pack('>7i', 9994, 0, 0, 0, 0, 0, tamanho_em_bytes // 2) + struct.pack('<2i8d', 1000, 5, *total, 0, 0, 0, 0)

    usados, campos = set(), []
    chaves = list(registros[0][1]) if registros else []
    for chave in chaves:
        valores = [r[1][chave] for r in registros]
        inteiro = all(isinstance(v, (int, np.integer)) for v in valores if v is not None)
        campos.append((chave, _nome_dbf(chave, usados), 12 if inteiro else 18, 0 if inteiro else 4))
    hoje = datetime.date.today()
    dbf = struct.pack('<B3BIHH20x', 3, hoje.year - 1900, hoje.month, hoje.day, len(registros), 32 + 32 * len(campos) + 1,
                      1 + sum(c[2] for c in campos))
    for _, nome, largura, casas in campos:
        dbf += struct.pack('<11sc4xBB14x', nome.encode('ascii'), b'N', largura, casas)
    dbf += b'\r'
    for _, atributos in registros:
        linha = ' '
        for chave, _, largura, casas in campos:
            valor = atributos[chave]
            linha += (' ' * largura if valor is None else f'{valor:{largura}.{casas}f}'[-largura:])
        dbf += linha.encode('ascii')
    dbf += b'\x1a'
    return {'.shp': cabecalho(100 + len(shp)) + bytes(shp), '.shx': cabecalho(100 + len(shx)) + bytes(shx), '.dbf': dbf,
            '.prj': PRJ_SIRGAS.encode('ascii')}


def gravar_shapefile_zip(caminho, zonas, graus, nomes, separar_partes=False, base='zonas'):
    registros = []
    for z, g in zip(zonas, graus):
        if separar_partes:
            for k, poligono in enumerate(g['poligonos'], 1):
                registros.append(([poligono], {'zona': z['zona'], 'parte': k}))
        elif g['poligonos']:
            registros.append((g['poligonos'], _atributos(z, nomes)))
    with zipfile.ZipFile(caminho, 'w', zipfile.ZIP_DEFLATED) as arquivo:
        for ext, dados in shapefile_de_poligonos(registros).items():
            arquivo.writestr(base + ext, dados)
    return len(registros)


def gravar_resumo(caminho, zonas, nomes):
    with open(caminho, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['zona', 'area_ha', 'pct_da_area', 'partes', 'pontos']
                   + [f'{n}_{s}' for n in nomes for s in ('media', 'desvio', 'minimo', 'maximo')])
        for z in zonas:
            linha = [z['zona'], num(z['ha']), num(z['pct'], 1), z['partes'], z['pontos']]
            for n in nomes:
                e = z['estat'].get(n, {})
                linha += [num(e.get(c), 4) for c in ('media', 'dp', 'min', 'max')]
            w.writerow(linha)


def gravar_pontos(caminho, xy, X, nomes, zona_do_ponto, zona_utm, sul):
    lon, lat = utm_inversa(xy[:, 0], xy[:, 1], zona_utm, sul)
    with open(caminho, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['longitude', 'latitude'] + list(nomes) + ['zona'])
        for i in range(len(xy)):
            w.writerow([f'{lon[i]:.7f}', f'{lat[i]:.7f}'] + [format(float(v), '.8g') for v in X[i]] + [int(zona_do_ponto[i])])


# ------------------------------------------------------------------ desenho
def _moldura(fig, titulo, subtitulo, kpis, rodape):
    titulo = titulo if len(titulo) <= 46 else titulo[:45].rstrip() + '…'
    fig.text(0.035, 0.955, espacado(ROTULO_DOC), fontsize=6.4, color=T['verde'], va='center', fontweight='bold')
    fig.text(0.035, 0.915, titulo, fontsize=15.5, color=T['fg1'], va='center', fontstyle='italic', fontweight='bold')
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
    fig.text(0.035, 0.026, 'As zonas são um agrupamento estatístico das camadas informadas. O que fazer em cada uma é '
             'decisão do responsável técnico.', fontsize=6.4, color=T['fg3'], va='center')
    fig.text(0.965, 0.036, 'OagronomIA', fontsize=10.5, color=T['fg1'], va='center', ha='right', fontstyle='italic',
             fontweight='bold')


def _painel(fig, caixa):
    ax = fig.add_axes(caixa)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    return ax


def _mapa(fig, caixa, titulo=None):
    ax = fig.add_axes(caixa, facecolor=T['mapa'])
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_color(T['line'])
    if titulo:
        ax.set_title(espacado(titulo), fontsize=7.2, color=T['fg1'], fontweight='bold', loc='left', pad=5)
    return ax


def _contorno(ax, areas, largura=0.9):
    for a in areas or []:
        for anel in a['aneis']:
            ax.plot([p[0] for p in anel] + [anel[0][0]], [p[1] for p in anel] + [anel[0][1]], color=T['fg1'],
                    linewidth=largura, zorder=6)


def _caminho(poligono):
    vertices, codigos = [], []
    for anel in [poligono['externo']] + list(poligono['furos']):
        vertices += anel.tolist() + [anel[0].tolist()]
        codigos += [Caminho.MOVETO] + [Caminho.LINETO] * (len(anel) - 1) + [Caminho.CLOSEPOLY]
    return Caminho(vertices, codigos)


def desenhar_zonas(ax, zonas, areas, numeros=True, preenchido=True, largura=0.7):
    total = len(zonas)
    for z in zonas:
        for p in z['poligonos']:
            ax.add_patch(PathPatch(_caminho(p), facecolor=cor_da_zona(z['zona'], total) if preenchido else 'none',
                                   edgecolor=T['fg1'], linewidth=largura, zorder=3 if preenchido else 5))
        if numeros and z.get('rotulo'):
            ax.annotate(str(z['zona']), z['rotulo'], ha='center', va='center', fontsize=10, fontweight='bold',
                        color=T['fg1'], zorder=7, bbox={'boxstyle': 'circle,pad=0.25', 'facecolor': T['pagina'],
                                                        'edgecolor': T['fg1'], 'linewidth': 0.7})
    _contorno(ax, areas)
    ax.autoscale_view()
    ax.margins(0.04)


def _camadas(fig, caixa, xy, X, nomes, zonas, areas):
    """Uma miniatura por camada: os pontos em cinco classes (quintis) com o contorno das zonas por cima."""
    quantas = min(len(nomes), 6)
    colunas = 3 if quantas > 2 else quantas
    linhas = -(-quantas // colunas)
    x0, y0, w, h = caixa
    fatia = slice(None, None, max(1, len(xy) // 40000))
    tamanho = float(np.clip(0.6 * 60000 / max(len(xy[fatia]), 1), 0.4, 14))
    for k in range(quantas):
        li, co = divmod(k, colunas)
        ax = _mapa(fig, [x0 + co * w / colunas + 0.006, y0 + (linhas - 1 - li) * h / linhas + 0.012,
                         w / colunas - 0.012, h / linhas - 0.05], nomes[k])
        classe = np.searchsorted(np.percentile(X[:, k], [20, 40, 60, 80]), X[:, k], side='right')
        ax.scatter(xy[fatia, 0], xy[fatia, 1], c=np.array(CLASSES)[classe[fatia]], s=tamanho, linewidths=0,
                   rasterized=True, zorder=2)
        desenhar_zonas(ax, zonas, areas, numeros=False, preenchido=False, largura=0.8)
    return quantas


def relatorio(caminho_pdf, caminho_png, r, areas, xy, X, nomes, meta):
    """Relatório em três páginas A4 deitadas: o mapa e a tabela; como foi feito; as camadas."""
    zonas, casas = r['zonas'], meta.get('casas', 2)
    kpis = [('Zonas', str(r['k_final']), 'no mapa'), ('Área', num(r['area_ha'], 1), 'ha'),
            ('Camadas', str(len(nomes)), 'usadas'), ('Silhueta', num(r['silhueta'], 2), 'de -1 a 1')]
    rodape = f'comunidade agrônomo10X · gerado em {meta["data"]} · SIRGAS 2000 / UTM {meta["utm"]}'
    with PdfPages(caminho_pdf) as pdf:
        # ---- página 1: mapa e tabela
        fig = plt.figure(figsize=(11.69, 8.27), facecolor=T['pagina'])
        _moldura(fig, meta['titulo'], f'{r["k_final"]} zonas · numeradas da menor para a maior média de '
                 f'{r["ordenado_por"]}', kpis, rodape)
        desenhar_zonas(_mapa(fig, [0.035, 0.085, 0.555, 0.755]), zonas, areas)
        lado = _painel(fig, [0.62, 0.085, 0.345, 0.755])
        y = 0.985
        lado.text(0, y, espacado('As zonas'), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
        y -= 0.05
        for titulo, xc, alinh in (('Zona', 0.07, 'left'), ('ha', 0.52, 'right'), ('% da área', 0.78, 'right'),
                                  ('Partes', 1.0, 'right')):
            lado.text(xc, y, espacado(titulo), fontsize=5.4, color=T['fg3'], va='center', ha=alinh)
        y -= 0.02
        lado.plot([0, 1], [y, y], color=T['line'], linewidth=0.8)
        for z in zonas:
            y -= 0.037
            lado.add_patch(plt.Rectangle((0, y - 0.012), 0.045, 0.024, facecolor=cor_da_zona(z['zona'], len(zonas)),
                                         edgecolor=T['fg1'], linewidth=0.5))
            lado.text(0.07, y, f'Zona {z["zona"]}', fontsize=8, color=T['fg1'], va='center')
            for xc, valor in ((0.52, num(z['ha'])), (0.78, num(z['pct'], 1)), (1.0, str(z['partes']))):
                lado.text(xc, y, valor, fontsize=7.6, color=T['fg1'], va='center', ha='right', family=MONO)
        y -= 0.07
        lado.text(0, y, espacado('Média de cada camada, por zona'), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
        y -= 0.05
        mostradas = zonas[:8]
        passo = 0.62 / max(len(mostradas), 1)
        for k, z in enumerate(mostradas):
            lado.text(0.38 + (k + 1) * passo, y, espacado(f'Z{z["zona"]}'), fontsize=5.4, color=T['fg3'], va='center', ha='right')
        y -= 0.02
        lado.plot([0, 1], [y, y], color=T['line'], linewidth=0.8)
        for nome in nomes[:9]:
            y -= 0.036
            lado.text(0, y, nome if len(nome) <= 19 else nome[:18] + '…', fontsize=7.4, color=T['fg1'], va='center')
            for k, z in enumerate(mostradas):
                valor = z['estat'][nome]['media'] if z['estat'] else None
                lado.text(0.38 + (k + 1) * passo, y, num(valor, casas if valor is None or abs(valor) < 1000 else 0),
                          fontsize=6.8 if len(mostradas) > 5 else 7.4, color=T['fg1'], va='center', ha='right', family=MONO)
        if len(nomes) > 9:
            y -= 0.036
            lado.text(0, y, f'… e mais {len(nomes) - 9} camada(s), no zonas-resumo.csv', fontsize=6.8, color=T['fg3'], va='center')
        y -= 0.065
        lado.text(0, y, espacado('Como ler'), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
        y -= 0.045
        for linha in ('Cada zona junta os lugares parecidos nas camadas usadas. O número da zona é só a ordem da '
                      f'média de {r["ordenado_por"]}: não é nota nem recomendação.',
                      'Partes = quantos pedaços separados a zona tem no talhão.'):
            texto = textwrap.wrap(linha, 62)
            lado.text(0, y, '\n'.join(texto), fontsize=6.9, color=T['fg2'], va='top', linespacing=1.4)
            y -= 0.027 * len(texto) + 0.012
        pdf.savefig(fig)
        fig.savefig(caminho_png, dpi=140)
        plt.close(fig)

        # ---- página 2: como foi feito
        fig = plt.figure(figsize=(11.69, 8.27), facecolor=T['pagina'])
        _moldura(fig, meta['titulo'], 'Como as zonas foram feitas', kpis, rodape)
        ax = fig.add_axes([0.06, 0.50, 0.26, 0.28])
        ks = [t['k'] for t in r['tabela_k']]
        ax.bar(ks, [t['silhueta'] for t in r['tabela_k']],
               color=[T['verde'] if k == r['k_escolhido'] else T['line_forte'] for k in ks], width=0.7)
        ax.set_xticks(ks)
        ax.set_xlabel('número de grupos', fontsize=7, color=T['fg2'])
        ax.set_ylabel('silhueta', fontsize=7, color=T['fg2'])
        ax.set_title(espacado('Silhueta por número de grupos'), fontsize=7.2, color=T['fg1'], fontweight='bold', loc='left', pad=6)
        ax = fig.add_axes([0.42, 0.50, 0.22, 0.28])
        ordem = sorted(nomes, key=lambda n: r['reducao'][n] if np.isfinite(r['reducao'][n]) else -1)
        ax.barh([n if len(n) <= 16 else n[:15] + '…' for n in ordem], [100 * max(r['reducao'][n], 0) for n in ordem],
                color=T['verde'], height=0.6)
        ax.set_xlim(0, 100)
        ax.set_xlabel('% da variação da camada que as zonas explicam', fontsize=7, color=T['fg2'])
        ax.set_title(espacado('O que as zonas separam'), fontsize=7.2, color=T['fg1'], fontweight='bold', loc='left', pad=6)
        for eixo in fig.axes[-2:]:
            eixo.tick_params(labelsize=6.5, colors=T['fg3'])
            for nome_lado in ('top', 'right'):
                eixo.spines[nome_lado].set_visible(False)
            for nome_lado in ('bottom', 'left'):
                eixo.spines[nome_lado].set_color(T['line'])
        passos = _painel(fig, [0.06, 0.09, 0.58, 0.33])
        e, p = r['etapas'], r['parametros']
        linhas = [
            f'1. {num(e["pontos"], 0)} pontos com {len(nomes)} camada(s), padronizadas'
            + (' e com peso' if p['pesos'] else '') + '.',
            f'2. Componentes principais: {r["pca"]["componentes"]} componente(s) guardam '
            f'{num(100 * sum(r["pca"]["explicada"][:r["pca"]["componentes"]]), 0)}% da variação.',
            f'3. K-Means: {r["k_escolhido"]} grupos ' + ('(o de maior silhueta, testando de '
                                                           f'{p["k_min"]} a {p["k_max"]})' if r['k_automatico'] else '(número fixado por quem pediu)')
            + f', silhueta {num(r["silhueta"], 2)}.',
            f'4. Grupo com menos de {num(100 * p["area_minima"], 0)}% dos pontos é absorvido pelos vizinhos: '
            f'{e["classes_absorvidas"]} absorvido(s).',
            f'5. Pedaço solto e pequeno de um grupo passa para o grupo ao redor ({p["vizinhos"]} vizinhos): '
            f'{e["fragmentos_reatribuidos"]} reatribuído(s).',
            f'6. Cada célula de {num(r["pixel"], 1)} m recebe a zona do ponto mais próximo; parte com menos de '
            f'{num(100 * p["area_minima"], 0)}% da área é fundida à vizinha de maior divisa: {e["partes_fundidas"]} fundida(s).',
            f'7. Divisas entre zonas simplificadas em {num(r["suavizar"], 0)} m e suavizadas (a mesma linha serve às duas '
            f'vizinhas); a borda de fora segue o perímetro do talhão.',
        ]
        y = 0.98
        passos.text(0, y, espacado('Passo a passo'), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
        y -= 0.11
        for linha in linhas:
            texto = textwrap.wrap(linha, 118)
            passos.text(0, y, '\n'.join(texto), fontsize=7.2, color=T['fg2'], va='top', linespacing=1.4)
            y -= 0.075 * len(texto) + 0.03
        avisos = _painel(fig, [0.69, 0.09, 0.275, 0.72])
        y = 0.985
        avisos.text(0, y, espacado('Avisos'), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
        y -= 0.05
        for aviso in r['alertas'] or ['Nenhum aviso neste zoneamento.']:
            texto = textwrap.wrap(aviso, 52)
            if y - 0.03 * len(texto) < 0.02:
                avisos.text(0, y, '… (os demais avisos estão no zonas.json)', fontsize=6.8, color=T['fg3'], va='top')
                break
            avisos.text(0, y, '\n'.join(texto), fontsize=6.9, color=T['fg2'], va='top', linespacing=1.4)
            y -= 0.03 * len(texto) + 0.02
        pdf.savefig(fig)
        plt.close(fig)

        # ---- página 3: as camadas com o contorno das zonas
        fig = plt.figure(figsize=(11.69, 8.27), facecolor=T['pagina'])
        _moldura(fig, meta['titulo'], 'As camadas usadas, em cinco classes (quintis), com o contorno das zonas', kpis, rodape)
        mostradas = _camadas(fig, [0.035, 0.11, 0.93, 0.72], xy, X, nomes, zonas, areas)
        legenda = _painel(fig, [0.035, 0.068, 0.93, 0.035])
        marcas = [plt.Line2D([], [], marker='s', linestyle='', color=cor, markersize=6) for cor in CLASSES]
        legenda.legend(marcas, ['20% menores', '', 'meio', '', '20% maiores'], loc='center', ncol=5, frameon=False, fontsize=7,
                       handletextpad=0.2, columnspacing=1.2)
        if len(nomes) > mostradas:
            fig.text(0.965, 0.84, f'mostradas as {mostradas} primeiras de {len(nomes)} camadas', fontsize=6.8, color=T['fg3'],
                     ha='right')
        pdf.savefig(fig, dpi=200)
        plt.close(fig)


if __name__ == '__main__':
    import json
    import os
    import tempfile

    import shapefile_min
    import sintetico
    import vetor
    import zoneamento

    assert num(1234.5) == '1.234,50' and cor_da_zona(1, 3) == CORES[0] and cor_da_zona(3, 3) == CORES[-1]
    ex = sintetico.talhao()
    nomes = ['argila_g_kg', 'prod_t_ha', 'altitude_m']
    X = np.column_stack([ex['colunas'][n] for n in nomes])
    xy = np.column_stack([ex['x'], ex['y']])
    areas = [{'nome': 'Exemplo', 'aneis': [ex['perimetro_utm']]}]
    r = zoneamento.zonear(xy, X, nomes, areas)
    graus = em_graus(r['zonas'], 22, True)
    assert all(p[0][0] == p[0][-1] for g in graus for p in g['poligonos']) and -50 < graus[0]['poligonos'][0][0][0][0] < -49
    with tempfile.TemporaryDirectory() as pasta:
        p = os.path.join
        gravar_geojson(p(pasta, 'z.geojson'), r['zonas'], graus, nomes)
        lido = json.load(open(p(pasta, 'z.geojson'), encoding='utf-8'))
        assert [f['properties']['zona'] for f in lido['features']] == [1, 2, 3]
        assert abs(sum(f['properties']['area_ha'] for f in lido['features']) - r['area_ha']) < 0.05
        assert lido['features'][0]['geometry']['type'] == 'MultiPolygon' and 'm_argila_g_kg' in lido['features'][0]['properties']
        gravar_kml(p(pasta, 'z.kml'), r['zonas'], graus, 'Talhão & exemplo')
        kml = open(p(pasta, 'z.kml'), encoding='utf-8').read()
        assert kml.count('<Placemark>') == 3 and 'Talhão &amp; exemplo' in kml and '<outerBoundaryIs>' in kml
        assert gravar_shapefile_zip(p(pasta, 'z.zip'), r['zonas'], graus, nomes) == 3
        with zipfile.ZipFile(p(pasta, 'z.zip')) as arquivo:
            assert sorted(arquivo.namelist()) == ['zonas.dbf', 'zonas.prj', 'zonas.shp', 'zonas.shx']
            arquivo.extractall(pasta)
        tipo, geoms, atributos, _ = shapefile_min.ler_shp(p(pasta, 'zonas.shp'))
        assert tipo == 'poligono' and len(geoms) == 3 and int(float(atributos[2]['zona'])) == 3
        assert abs(float(atributos[0]['area_ha']) - round(r['zonas'][0]['ha'], 2)) < 1e-6
        # o anel externo do shapefile é horário (área com sinal negativa no mapa)
        assert vetor._area_com_sinal(np.array(geoms[0][0])) < 0
        partes = sum(z['partes'] for z in r['zonas'])
        assert gravar_shapefile_zip(p(pasta, 'p.zip'), r['zonas'], graus, nomes, separar_partes=True) == partes
        gravar_resumo(p(pasta, 'r.csv'), r['zonas'], nomes)
        assert len(open(p(pasta, 'r.csv'), encoding='utf-8-sig').read().splitlines()) == 4
        gravar_pontos(p(pasta, 'pts.csv'), xy, X, nomes, r['zona_do_ponto'], 22, True)
        assert len(open(p(pasta, 'pts.csv'), encoding='utf-8').read().splitlines()) == len(xy) + 1
        meta = {'titulo': 'Talhão de exemplo', 'data': '14/11/2026', 'utm': '22S', 'casas': 2}
        relatorio(p(pasta, 'r.pdf'), p(pasta, 'r.png'), r, areas, xy, X, nomes, meta)
        assert os.path.getsize(p(pasta, 'r.pdf')) > 30000 and os.path.getsize(p(pasta, 'r.png')) > 30000
    print('saidas OK')
