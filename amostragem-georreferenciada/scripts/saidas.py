"""Arquivos de saída do plano de amostragem: pontos para o GPS e para o SIG, a
planilha de campo e o mapa.

Os pontos saem em coordenadas geográficas SIRGAS 2000 (graus, sem projeção),
que é o que GPS de mão, aplicativo de campo e monitor de máquina esperam.
Formatos: GeoJSON, KML, GPX (pontos e rota), CSV e shapefile de pontos.
"""

import csv
import io
import json
import struct
import textwrap
import zipfile
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

PRJ_SIRGAS = ('GEOGCS["SIRGAS 2000",DATUM["Sistema_de_Referencia_Geocentrico_para_las_AmericaS_2000",'
              'SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],'
              'UNIT["degree",0.0174532925199433]]')
# tokens do design system da casa (tema claro de impressão) e paleta de dataviz
T = dict(pagina='#FBFCF9', fg1='#121810', fg2='#3C4636', fg3='#6B7562', line='#D4DBCA',
         line_forte='#B4BFA8', verde='#2E8B1E', mapa='#FFFFFF')
DATAVIZ = ['#2F8B1F', '#C26A3D', '#4FB7C9', '#E8B33B', '#8A7556', '#52C937', '#6B5A40']
ROTULO_DOC = 'agrônomo10X · Amostragem georreferenciada'


def br(v, casas=1):
    texto = f'{float(v):,.{casas}f}'
    return texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def espacado(texto):
    return ' '.join(str(texto).upper())


# ------------------------------------------------------------------ arquivos
def gravar_geojson(caminho, pontos):
    feicoes = [{'type': 'Feature',
                'properties': {'id': p['id'], 'area': p['area'], 'amostra': p['amostra'], 'ordem': p['ordem']},
                'geometry': {'type': 'Point', 'coordinates': [round(p['lon'], 7), round(p['lat'], 7)]}}
               for p in pontos]
    caminho.write_text(json.dumps({
        'type': 'FeatureCollection',
        'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:EPSG::4674'}},
        'features': feicoes}, ensure_ascii=False), encoding='utf-8')


def gravar_celulas(caminho, celulas):
    feicoes = [{'type': 'Feature', 'properties': {'amostra': c['id'], 'area': c['area']},
                'geometry': {'type': 'Polygon', 'coordinates': [[[round(x, 7), round(y, 7)] for x, y in c['quadro']]]}}
               for c in celulas]
    caminho.write_text(json.dumps({'type': 'FeatureCollection', 'features': feicoes}, ensure_ascii=False),
                       encoding='utf-8')


def gravar_kml(caminho, pontos, titulo):
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>', '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
              f'<name>{escape(titulo)}</name>']
    por_area = {}
    for p in pontos:
        por_area.setdefault(p['area'], []).append(p)
    for area, lista in por_area.items():
        linhas.append(f'<Folder><name>{escape(area)}</name>')
        for p in lista:
            linhas.append(f'<Placemark><name>{escape(p["id"])}</name><description>amostra {escape(p["amostra"])} · '
                          f'ordem {p["ordem"]}</description><Point><coordinates>{p["lon"]:.7f},{p["lat"]:.7f},0'
                          '</coordinates></Point></Placemark>')
        rota = ' '.join(f'{p["lon"]:.7f},{p["lat"]:.7f},0' for p in lista)
        linhas.append(f'<Placemark><name>rota {escape(area)}</name><LineString><coordinates>{rota}'
                      '</coordinates></LineString></Placemark></Folder>')
    linhas.append('</Document></kml>')
    caminho.write_text('\n'.join(linhas), encoding='utf-8')


def gravar_gpx(caminho, pontos, titulo):
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<gpx version="1.1" creator="amostragem-georreferenciada" xmlns="http://www.topografix.com/GPX/1/1">',
              f'<metadata><name>{escape(titulo)}</name></metadata>']
    for p in pontos:
        linhas.append(f'<wpt lat="{p["lat"]:.7f}" lon="{p["lon"]:.7f}"><name>{escape(p["id"])}</name>'
                      f'<desc>{escape(p["area"])} · amostra {escape(p["amostra"])}</desc></wpt>')
    linhas.append(f'<rte><name>{escape(titulo)}</name>')
    for p in pontos:
        linhas.append(f'<rtept lat="{p["lat"]:.7f}" lon="{p["lon"]:.7f}"><name>{escape(p["id"])}</name></rtept>')
    linhas.append('</rte></gpx>')
    caminho.write_text('\n'.join(linhas), encoding='utf-8')


def gravar_csv(caminho, pontos):
    with open(caminho, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['ordem', 'id', 'area', 'amostra', 'latitude', 'longitude', 'utm_x', 'utm_y'])
        for p in pontos:
            w.writerow([p['ordem'], p['id'], p['area'], p['amostra'], f'{p["lat"]:.7f}', f'{p["lon"]:.7f}',
                        f'{p["x"]:.2f}', f'{p["y"]:.2f}'])


def _ascii(texto, tamanho):
    return str(texto).encode('ascii', 'replace')[:tamanho].ljust(tamanho)


def shapefile_de_pontos(pontos):
    """Shapefile de pontos (.shp, .shx, .dbf, .prj) em graus SIRGAS 2000. Devolve {extensão: bytes}."""
    campos = [('ID', 'C', 24, 0), ('AREA', 'C', 24, 0), ('AMOSTRA', 'C', 24, 0), ('ORDEM', 'N', 6, 0)]
    registros = b''.join(struct.pack('>ii', i + 1, 10) + struct.pack('<idd', 1, p['lon'], p['lat'])
                         for i, p in enumerate(pontos))
    lons, lats = [p['lon'] for p in pontos], [p['lat'] for p in pontos]

    def cabecalho(palavras):
        return (struct.pack('>i', 9994) + b'\x00' * 20 + struct.pack('>i', palavras) + struct.pack('<ii', 1000, 1)
                + struct.pack('<8d', min(lons), min(lats), max(lons), max(lats), 0, 0, 0, 0))

    shp = cabecalho((100 + len(registros)) // 2) + registros
    shx = cabecalho((100 + 8 * len(pontos)) // 2) + b''.join(
        struct.pack('>ii', (100 + 28 * i) // 2, 10) for i in range(len(pontos)))
    tamanho_reg = 1 + sum(c[2] for c in campos)
    dbf = io.BytesIO()
    dbf.write(struct.pack('<BBBBIHH20x', 3, 126, 1, 1, len(pontos), 32 + 32 * len(campos) + 1, tamanho_reg))
    for nome, tipo, tam, dec in campos:
        dbf.write(struct.pack('<11sc4xBB14x', nome.encode('ascii'), tipo.encode('ascii'), tam, dec))
    dbf.write(b'\r')
    for p in pontos:
        dbf.write(b' ' + _ascii(p['id'], 24) + _ascii(p['area'], 24) + _ascii(p['amostra'], 24)
                  + str(p['ordem']).rjust(6).encode('ascii'))
    dbf.write(b'\x1a')
    return {'.shp': shp, '.shx': shx, '.dbf': dbf.getvalue(), '.prj': PRJ_SIRGAS.encode('ascii')}


def gravar_shapefile_zip(caminho, pontos, base='pontos'):
    with zipfile.ZipFile(caminho, 'w', zipfile.ZIP_DEFLATED) as z:
        for ext, dados in shapefile_de_pontos(pontos).items():
            z.writestr(base + ext, dados)


def gravar_planilha_de_campo(caminho, amostras, camadas):
    """Uma linha por amostra de laboratório e por camada, com os campos de campo em branco."""
    with open(caminho, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['amostra', 'area', 'camada', 'subamostras', 'latitude', 'longitude',
                    'data', 'coletor', 'observacao'])
        for a in amostras:
            for camada in camadas or ['']:
                w.writerow([a['id'], a['area'], camada, a['n_pontos'], f'{a["lat"]:.6f}', f'{a["lon"]:.6f}',
                            '', '', ''])


# ---------------------------------------------------------------------- mapa
def _escala_e_norte(ax):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    largura, altura = x1 - x0, y1 - y0
    alvo = largura / 4
    base = 10 ** int(np.floor(np.log10(alvo)))
    comprimento = next((base * m for m in (5, 2, 1) if base * m <= alvo), base)
    bx, by = x0 + largura * 0.03, y0 + altura * 0.04
    ax.plot([bx, bx + comprimento], [by, by], color=T['fg1'], linewidth=2.5, solid_capstyle='butt')
    rotulo = f'{comprimento / 1000:g} km'.replace('.', ',') if comprimento >= 1000 else f'{comprimento:g} m'
    ax.annotate(rotulo, (bx + comprimento / 2, by), xytext=(0, 4), textcoords='offset points', ha='center',
                fontsize=7, color=T['fg1'])
    ax.annotate('N', xy=(0.965, 0.95), xycoords='axes fraction', ha='center', fontsize=9, fontweight='bold')
    ax.annotate('', xy=(0.965, 0.94), xycoords='axes fraction', xytext=(0.965, 0.87), textcoords='axes fraction',
                arrowprops={'arrowstyle': '-|>', 'color': T['fg1'], 'linewidth': 1.1})


def mapa(caminho_pdf, caminho_png, areas, pontos, r):
    """Página A4 deitada, no formato dos documentos da casa. `r` é o resumo do plano."""
    fig = plt.figure(figsize=(11.69, 8.27), facecolor=T['pagina'])
    mono = 'DejaVu Sans Mono'
    fig.text(0.035, 0.955, espacado(ROTULO_DOC), fontsize=6.4, color=T['verde'], va='center', fontweight='bold')
    fig.text(0.035, 0.915, r['titulo'], fontsize=18, color=T['fg1'], va='center', fontstyle='italic',
             fontweight='bold')
    fig.text(0.035, 0.878, r['subtitulo'], fontsize=9.5, color=T['fg2'], va='center')
    x = 0.965
    for rotulo, valor, unidade in reversed(r['kpis']):
        fig.text(x, 0.955, espacado(rotulo), fontsize=5.8, color=T['fg3'], va='center', ha='right')
        fig.text(x, 0.918, valor, fontsize=17, color=T['fg1'], va='center', ha='right', family=mono, fontweight='bold')
        fig.text(x, 0.885, unidade, fontsize=7, color=T['fg3'], va='center', ha='right', family=mono)
        x -= 0.115
    fig.add_artist(plt.Line2D([0.035, 0.965], [0.86, 0.86], color=T['line'], linewidth=0.8))

    ax = fig.add_axes([0.035, 0.085, 0.63, 0.755], facecolor=T['mapa'])
    for a in areas:
        for anel in a['aneis']:
            ax.plot([p[0] for p in anel] + [anel[0][0]], [p[1] for p in anel] + [anel[0][1]],
                    color=T['fg1'], linewidth=0.9)
    por_amostra = {}
    for p in pontos:
        por_amostra.setdefault((p['area'], p['amostra']), []).append(p)
    composto = any(len(v) > 1 for v in por_amostra.values())
    por_area = {}
    for p in pontos:
        por_area.setdefault(p['area'], []).append(p)
    for lista in por_area.values():
        ax.plot([p['x'] for p in lista], [p['y'] for p in lista], color=T['line_forte'], linewidth=0.6, zorder=2)
    for n, (chave, lista) in enumerate(por_amostra.items()):
        cor = DATAVIZ[n % len(DATAVIZ)] if composto else T['verde']
        ax.scatter([p['x'] for p in lista], [p['y'] for p in lista], s=11 if composto else 14, color=cor,
                   edgecolors='white', linewidths=0.4, zorder=3)
        if composto:
            cx, cy = np.mean([p['x'] for p in lista]), np.mean([p['y'] for p in lista])
            ax.annotate(chave[1], (cx, cy), fontsize=6.5, color=T['fg1'], ha='center', va='center', zorder=4,
                        bbox={'boxstyle': 'round,pad=0.2', 'facecolor': T['pagina'], 'edgecolor': cor, 'linewidth': 0.6})
    if not composto and len(pontos) <= 160:
        for p in pontos:
            ax.annotate(p['id'], (p['x'], p['y']), xytext=(0, 4), textcoords='offset points', fontsize=4.8,
                        color=T['fg2'], ha='center', zorder=4)
    ax.set_aspect('equal')
    ax.set_anchor('NW')
    ax.margins(0.04)
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_color(T['line'])
    _escala_e_norte(ax)

    painel = fig.add_axes([0.69, 0.085, 0.275, 0.755])
    painel.set_xlim(0, 1)
    painel.set_ylim(0, 1)
    painel.axis('off')
    y = 0.985
    painel.text(0, y, espacado('Por área'), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
    y -= 0.05
    colunas = (('Área', 0.0, 'left'), ('ha', 0.56, 'right'), ('Amostras', 0.80, 'right'), ('Pontos', 1.0, 'right'))
    for titulo, xc, alinh in colunas:
        painel.text(xc, y, espacado(titulo), fontsize=5.4, color=T['fg3'], va='center', ha=alinh)
    y -= 0.02
    painel.plot([0, 1], [y, y], color=T['line'], linewidth=0.8)
    linhas = r['por_area'][:16]
    for linha in linhas:
        y -= 0.036
        painel.text(0, y, linha['area'][:22], fontsize=8, color=T['fg1'], va='center')
        for xc, valor in ((0.56, br(linha['ha'])), (0.80, str(linha['amostras'])), (1.0, str(linha['pontos']))):
            painel.text(xc, y, valor, fontsize=7.6, color=T['fg1'], va='center', ha='right', family=mono)
    if len(r['por_area']) > 16:
        y -= 0.036
        painel.text(0, y, f'… e mais {len(r["por_area"]) - 16} áreas (na planilha)', fontsize=7, color=T['fg3'], va='center')
    y -= 0.06
    painel.text(0, y, espacado('Como foi desenhado'), fontsize=7.6, fontweight='bold', color=T['fg1'], va='top')
    y -= 0.045
    for linha in r['metodo']:
        partes = textwrap.wrap(linha, 46)
        painel.text(0, y, '\n'.join(partes), fontsize=7.6, color=T['fg2'], va='top', linespacing=1.4)
        y -= 0.03 * len(partes) + 0.008

    fig.add_artist(plt.Line2D([0.035, 0.965], [0.062, 0.062], color=T['line'], linewidth=0.8))
    fig.text(0.035, 0.044, f'comunidade agrônomo10X · gerado em {r["data"]} · SIRGAS 2000 / UTM {r["zona"]}',
             fontsize=7, color=T['fg3'], va='center')
    fig.text(0.035, 0.026, 'Plano de coleta. A densidade e o desenho são decisão do responsável técnico.',
             fontsize=6.4, color=T['fg3'], va='center')
    fig.text(0.965, 0.036, 'OagronomIA', fontsize=10.5, color=T['fg1'], va='center', ha='right',
             fontstyle='italic', fontweight='bold')
    fig.savefig(caminho_pdf)
    fig.savefig(caminho_png, dpi=140)
    plt.close(fig)


if __name__ == '__main__':
    import os
    import tempfile

    pts = [{'id': f'T01-{i + 1:02d}', 'area': 'T01', 'amostra': f'T01-{i + 1:02d}', 'ordem': i + 1,
            'lon': -47.05 + i * 0.001, 'lat': -22.85 + (i % 3) * 0.001, 'x': 290000 + i * 100.0,
            'y': 7472000 + (i % 3) * 100.0} for i in range(6)]
    partes = shapefile_de_pontos(pts)
    assert struct.unpack('>i', partes['.shp'][24:28])[0] * 2 == len(partes['.shp'])  # tamanho declarado bate
    assert struct.unpack('<i', partes['.shp'][32:36])[0] == 1 and len(partes['.shx']) == 100 + 8 * 6
    assert struct.unpack('<dd', partes['.shp'][112:128]) == (pts[0]['lon'], pts[0]['lat'])
    n_reg, tam_cab, tam_reg = struct.unpack('<IHH', partes['.dbf'][4:12])
    assert (n_reg, tam_cab, tam_reg) == (6, 32 + 32 * 4 + 1, 79)
    assert len(partes['.dbf']) == tam_cab + n_reg * tam_reg + 1 and b'T01-03' in partes['.dbf']
    with tempfile.TemporaryDirectory() as pasta:
        from pathlib import Path
        p = Path(pasta)
        gravar_geojson(p / 'a.geojson', pts)
        gravar_kml(p / 'a.kml', pts, 'Teste & cia')
        gravar_gpx(p / 'a.gpx', pts, 'Teste')
        gravar_csv(p / 'a.csv', pts)
        gravar_shapefile_zip(p / 'a.zip', pts)
        gravar_planilha_de_campo(p / 'campo.csv', [{'id': 'T01-01', 'area': 'T01', 'n_pontos': 1, 'lat': -22.85,
                                                    'lon': -47.05}], ['0-20', '20-40'])
        assert json.loads((p / 'a.geojson').read_text(encoding='utf-8'))['features'][2]['properties']['id'] == 'T01-03'
        assert 'Teste &amp; cia' in (p / 'a.kml').read_text(encoding='utf-8')
        assert (p / 'a.gpx').read_text(encoding='utf-8').count('<wpt') == 6
        assert sorted(zipfile.ZipFile(p / 'a.zip').namelist()) == ['pontos.dbf', 'pontos.prj', 'pontos.shp', 'pontos.shx']
        assert len((p / 'campo.csv').read_text(encoding='utf-8-sig').splitlines()) == 3
        mapa(p / 'm.pdf', p / 'm.png', [{'nome': 'T01', 'aneis': [[(289900, 7471900), (290700, 7471900),
                                                                      (290700, 7472400), (289900, 7472400)]]}], pts,
             {'titulo': 'Fazenda Exemplo', 'subtitulo': 'Grade regular · 1 ponto a cada 2 ha', 'data': '12/11/2026',
              'zona': '23S', 'kpis': [('Pontos', '6', 'no total'), ('Rota', '0,6', 'km')],
              'por_area': [{'area': 'T01', 'ha': 40.0, 'amostras': 6, 'pontos': 6}],
              'metodo': ['Grade quadrada de 141 m.', 'Pontos a pelo menos 15 m da divisa.']})
        assert os.path.getsize(p / 'm.png') > 20000 and os.path.getsize(p / 'm.pdf') > 5000
    print('saidas OK: GeoJSON, KML, GPX, CSV, shapefile de pontos, planilha de campo e mapa')
