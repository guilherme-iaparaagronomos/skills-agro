"""Monta o dossiê de uso e ocupação do solo em PDF.

Entradas (só o perímetro e o uso do solo são obrigatórios):

  python montar_dossie.py --perimetro perimetro.geojson --nome "Fazenda Exemplo" \
      --uso uso_do_solo.txt --cobertura cobertura_do_solo.txt \
      --prodes prodes_fazenda.txt --relevo relevo_fazenda.txt \
      --car car.json --car-temas car-temas.geojson \
      --imagem imagem_satelite.txt --figuras ./figuras --saida ./dossie

- --uso/--cobertura/--prodes/--relevo/--imagem: o TEXTO que cada ferramenta da ClaudIA Sat
  devolveu, colado num arquivo como veio (sem resumir nem arredondar).
- --car/--car-temas: saída de `car.py` (dispensável quando o usuário só tem o
  perímetro).
- Figuras: o script tenta BAIXAR SOZINHO os mapas e a imagem de satélite pelos
  links que estão no texto das ferramentas (por isso os links ficam no texto;
  valem 1 hora). A imagem de satélite chega em GeoTIFF de 16 bits e é
  convertida em figura aqui. Onde o ambiente não tem internet, o dossiê sai
  sem figuras e avisa; aí o usuário baixa os arquivos e a pasta entra com
  --figuras (uso_solo_situacao.png, relevo_altitude.png, rgb_AAAA-MM-DD.tif…).
  --sem-baixar desliga a tentativa.

Saídas em --saida: dossie.pdf, dossie.json (os números lidos) e
dossie_tabelas.csv; com --png, também uma imagem por página. O script só organiza e confere somas; não interpreta.
"""

import argparse
import csv
import datetime
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import car as modulo_car  # noqa: E402
import geometria  # noqa: E402
import imagem_rgb  # noqa: E402
import leitura  # noqa: E402
import paginas  # noqa: E402

# arquivo gerado pela ferramenta → (legenda, fonte)
FIGURAS_CONHECIDAS = [
    (r'imagem_rgb|rgb_\d{4}-\d{2}-\d{2}', 'Imagem de satélite em cor real', 'imagem'),
    (r'uso_solo_situacao', 'Uso do solo: situação frente às datas-marco', 'uso'),
    (r'uso_solo_mapas', 'Uso do solo: mapas dos anos-marco', 'uso'),
    (r'uso_solo_historico', 'Uso do solo: histórico ano a ano', 'uso'),
    (r'cobertura_classes', 'Cobertura do solo recente: classes', 'cobertura'),
    (r'cobertura_confianca', 'Cobertura do solo recente: probabilidade da classe', 'cobertura'),
    (r'prodes_deter', 'PRODES e DETER no perímetro', 'prodes'),
    (r'relevo_altitude', 'Relevo: altitude e curvas de nível', 'relevo'),
    (r'relevo_declividade', 'Relevo: declividade', 'relevo'),
    (r'^restricoes\.', 'Restrições: unidades de conservação, terras indígenas e termos de embargo', 'restricoes'),
    (r'solo_textura_carbono', 'Solo: textura e carbono (estimativa do SoilGrids)', 'solo'),
]
# o que vale baixar dos links das ferramentas (o resto — GeoPackage, curvas — é para o QGIS)
BAIXAR = re.compile(r'^(uso_solo_(situacao|mapas|historico)|cobertura_(classes|confianca)|prodes_deter'
                    r'|relevo_(altitude|declividade)|restricoes|solo_textura_carbono)\.png$'
                    r'|^rgb_\d{4}-\d{2}-\d{2}\.tif$')
TETO_DO_ARQUIVO = 12 * 1024 * 1024
ASSINATURAS = {'.png': (b'\x89PNG',), '.tif': (b'II*\x00', b'MM\x00*')}


def links_dos_arquivos(texto):
    """Linhas '- nome.png (126 KB): https://…' do texto da ferramenta → [(nome, link)]."""
    return [(nome, link.rstrip('.,;')) for nome, link in
            re.findall(r'^- ([A-Za-z0-9_.-]+) \([^)]*\): (https://\S+)', texto, re.M)]


def baixar_figuras(textos, pasta):
    """Tenta baixar os mapas e a imagem pelos links dos textos. Devolve (baixados, falhas).
    Só https, só os arquivos da lista BAIXAR, com teto de tamanho e conferência do tipo."""
    baixados, falhas = [], []
    for texto in textos:
        for nome, link in links_dos_arquivos(texto or ''):
            if not BAIXAR.match(nome) or any(b.name == nome for b in baixados):
                continue
            try:
                req = urllib.request.Request(link, headers={'User-Agent': 'dossie-uso-solo-skill/1.0'})
                with urllib.request.urlopen(req, timeout=25) as resp:
                    corpo = resp.read(TETO_DO_ARQUIVO + 1)
                if len(corpo) > TETO_DO_ARQUIVO:
                    raise ValueError('arquivo acima do teto')
                if not corpo.startswith(ASSINATURAS[Path(nome).suffix]):
                    raise ValueError('o conteúdo não é o tipo esperado')
            except (urllib.error.URLError, OSError, ValueError) as e:
                falhas.append((nome, type(e).__name__))
                continue
            pasta.mkdir(parents=True, exist_ok=True)
            destino = pasta / nome
            destino.write_bytes(corpo)
            baixados.append(destino)
    return baixados, falhas


def converter_imagens(pasta, avisos):
    """GeoTIFF de cor real (rgb_AAAA-MM-DD.tif) na pasta → imagem_rgb_AAAA-MM-DD.png."""
    for tif in sorted(Path(pasta).glob('*rgb_*.tif')):
        data = re.search(r'\d{4}-\d{2}-\d{2}', tif.name)
        png = Path(pasta) / f'imagem_rgb_{data.group(0) if data else "cena"}.png'
        if png.exists():
            continue
        try:
            imagem_rgb.geotiff_para_png(tif, png)
        except (ValueError, OSError, KeyError) as e:
            avisos.append(f'a imagem de satélite ({tif.name}) não pôde ser convertida em figura: {e}')
ORDEM_DOS_TEMAS = ['area_consolidada', 'outros', 'vegetacao_nativa', 'reserva_legal', 'uso_restrito', 'app', 'embargo']


def perimetro_em_metros(caminho):
    """Lê o perímetro e devolve (anéis em UTM, zona, hemisfério sul?, centro lon/lat ou None)."""
    aneis, crs, zona = geometria.ler_perimetro(caminho)
    if crs == 'utm':
        if not zona:
            raise SystemExit('perímetro em metros sem .prj: converta para KML/GeoJSON em graus ou informe o .prj')
        return [[(float(x), float(y)) for x, y in a] for a in aneis], zona[0], zona[1], None
    lons = [p[0] for a in aneis for p in a]
    lats = [p[1] for a in aneis for p in a]
    centro = ((min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2)
    z, sul = zona or geometria.zona_de(sum(lons) / len(lons), sum(lats) / len(lats))
    projetados = []
    for a in aneis:
        xs, ys = geometria.utm_direta([p[0] for p in a], [p[1] for p in a], z, sul)
        projetados.append(list(zip(xs.tolist(), ys.tolist())))
    return projetados, z, sul, centro


def temas_em_metros(caminho, z, sul):
    """car-temas.geojson → [(grupo, [polígono = lista de anéis em UTM])], na ordem de desenho."""
    grupo_de = {c: g for c, _, g in modulo_car.TEMAS}
    grupo_de.update({c: 'app' for c, _ in modulo_car.APPS})
    dados = json.loads(Path(caminho).read_text(encoding='utf-8'))
    por_grupo = {}
    for feicao in dados.get('features', []):
        grupo = grupo_de.get(feicao.get('properties', {}).get('camada'), 'outros')
        geom = feicao.get('geometry') or {}
        partes = ([geom['coordinates']] if geom.get('type') == 'Polygon'
                  else geom.get('coordinates', []) if geom.get('type') == 'MultiPolygon' else [])
        for poligono in partes:
            aneis = []
            for anel in poligono:
                xs, ys = geometria.utm_direta([p[0] for p in anel], [p[1] for p in anel], z, sul)
                aneis.append(list(zip(xs.tolist(), ys.tolist())))
            por_grupo.setdefault(grupo, []).append(aneis)
    return [(g, por_grupo[g]) for g in ORDEM_DOS_TEMAS if g in por_grupo]


def achar_figuras(pasta, avulsas):
    """Devolve [(legenda, caminho, bloco|None)] na ordem do dossiê."""
    achadas = []
    if pasta and Path(pasta).is_dir():
        arquivos = sorted(p for p in Path(pasta).iterdir() if p.is_file())
        for padrao, legenda, bloco in FIGURAS_CONHECIDAS:
            for arq in arquivos:
                if re.search(padrao, arq.name) and arq.suffix.lower() in ('.png', '.jpg', '.jpeg'):
                    achadas.append((legenda, arq, bloco))
                    break
    for item in avulsas or []:
        legenda, sep, caminho = item.partition('=')
        if not sep:
            raise SystemExit(f'--figura no formato "Legenda=arquivo.png" (recebido: {item!r})')
        achadas.append((legenda.strip(), Path(caminho.strip()), None))
    return achadas


def _ler(caminho, funcao, avisos):
    if not caminho:
        return None
    dados, novos = funcao(Path(caminho).read_text(encoding='utf-8'))
    avisos.extend(novos)
    return dados


def principal(argv=None):
    p = argparse.ArgumentParser(description='Dossiê de uso e ocupação do solo (PDF)')
    p.add_argument('--perimetro', help='perímetro: .geojson/.kml/.shp/.wkt')
    p.add_argument('--nome', help='nome do imóvel (capa e cabeçalho)')
    p.add_argument('--uso', help='texto de uso_do_solo')
    p.add_argument('--cobertura', help='texto de cobertura_do_solo (retrato recente, 10 m)')
    p.add_argument('--prodes', help='texto de prodes_fazenda')
    p.add_argument('--relevo', help='texto de relevo_fazenda')
    p.add_argument('--imagem', help='texto de imagem_satelite (data da cena)')
    p.add_argument('--restricoes', help='texto de restricoes_fazenda (unidades de conservação, terras indígenas, embargos)')
    p.add_argument('--solo', help='texto de solo_textura_carbono (SoilGrids: textura e carbono, valores modelados)')
    p.add_argument('--car', help='car.json gerado por car.py')
    p.add_argument('--car-temas', help='car-temas.geojson gerado por car.py')
    p.add_argument('--figuras', help='pasta com os mapas gerados pelas ferramentas')
    p.add_argument('--figura', action='append', metavar='LEGENDA=ARQUIVO', help='figura avulsa (repetível)')
    p.add_argument('--sem-baixar', action='store_true',
                   help='não tenta baixar os mapas pelos links dos textos')
    p.add_argument('--municipio', help='"Cidade/UF", quando não há CAR')
    p.add_argument('--solicitante')
    p.add_argument('--responsavel', help='responsável técnico')
    p.add_argument('--data', help='data do dossiê (padrão: hoje)')
    p.add_argument('--tema', choices=['papel', 'escuro'], default='papel',
                   help='papel = tema claro de impressão (padrão) · escuro = o terminal da marca')
    p.add_argument('--fontes', help='pasta com as fontes do design system (.ttf), se o usuário as tiver')
    p.add_argument('--saida', default='./dossie')
    p.add_argument('--png', action='store_true', help='grava também cada página em PNG (para mostrar no chat)')
    p.add_argument('--demo', action='store_true', help='monta um dossiê de exemplo, sem rede')
    args = p.parse_args(argv)
    if args.demo:
        return _demo(args)
    if not (args.perimetro and args.uso):
        p.error('--perimetro e --uso são obrigatórios (ou use --demo)')

    paginas.usar_tema(args.tema, args.fontes)
    avisos = []
    uso = _ler(args.uso, leitura.ler_uso, avisos)
    if not uso.get('hoje') and not uso.get('marcos'):
        raise SystemExit('não reconheci o texto de uso_do_solo: cole o texto da ferramenta como veio')
    cobertura = _ler(args.cobertura, leitura.ler_cobertura, avisos)
    prodes = _ler(args.prodes, leitura.ler_prodes, avisos)
    relevo = _ler(args.relevo, leitura.ler_relevo, avisos)
    imagem = _ler(args.imagem, leitura.ler_imagem, avisos)
    restricoes = _ler(args.restricoes, leitura.ler_restricoes, avisos)
    solo = _ler(args.solo, leitura.ler_solo, avisos)
    if solo and not solo.get('superficie'):
        solo = None  # texto que não é da ferramenta: a seção não sai (o aviso já foi registrado)
    if restricoes and not any(restricoes[g]['lida'] for g in ('uc', 'ti', 'embargo')) and restricoes['area_ha'] is None:
        restricoes = None
    avisos.extend(leitura.conferir_areas({'uso do solo': uso, 'cobertura do solo': cobertura,
                                          'PRODES': prodes, 'relevo': relevo, 'restrições': restricoes, 'solo': solo}))
    cadastro = json.loads(Path(args.car).read_text(encoding='utf-8')) if args.car else None
    if cadastro and cadastro.get('area_declarada_ha') and uso.get('area_ha'):
        a, b = cadastro['area_declarada_ha'], uso['area_ha']
        if abs(a - b) > 0.03 * max(a, b):
            avisos.append(f'a área declarada no CAR ({a:.1f} ha) e a do perímetro analisado ({b:.1f} ha) '
                          'diferem mais de 3%: o perímetro é o do CAR informado?')

    aneis, z, sul, centro = perimetro_em_metros(args.perimetro)
    zona_txt = f'SIRGAS 2000 / UTM {z}{"S" if sul else "N"} (EPSG {geometria.epsg_utm(z, sul)}).'
    temas_geo = temas_em_metros(args.car_temas, z, sul) if args.car_temas else None

    doc = {
        'nome': args.nome or (cadastro or {}).get('car') or 'Imóvel sem nome',
        'data': args.data or datetime.date.today().strftime('%d/%m/%Y'),
        'municipio': args.municipio, 'solicitante': args.solicitante, 'responsavel': args.responsavel,
        'centro': f'{centro[1]:.5f}, {centro[0]:.5f} (latitude, longitude)'.replace('.', ',') if centro else None,
        'origem_perimetro': ('polígono do imóvel no SICAR' if cadastro else 'arquivo enviado pelo usuário'),
        'imagem': (f"{imagem['satelite']} de {imagem['data']}, com {paginas.br(imagem['livre_pct'])} % do "
                   'perímetro sem nuvem') if imagem else None,
    }
    dados = {'uso': uso, 'cobertura': cobertura, 'prodes': prodes, 'relevo': relevo, 'imagem': imagem,
             'restricoes': restricoes, 'solo': solo, 'car': cadastro}

    folhas = [paginas.pagina_identificacao(doc, dados, aneis, zona_txt)]
    if cadastro:
        folhas.append(paginas.pagina_car(doc, cadastro, aneis, temas_geo))
    folhas += [paginas.pagina_uso(doc, uso), paginas.pagina_marcos(doc, uso)]
    if cobertura and cobertura.get('classes'):
        folhas.append(paginas.pagina_cobertura(doc, cobertura))
    if prodes:
        folhas.append(paginas.pagina_prodes(doc, prodes))
    if cadastro and paginas.linhas_da_comparacao(cadastro, uso):
        folhas.append(paginas.pagina_comparacao(doc, cadastro, uso))
    if relevo:
        folhas.append(paginas.pagina_relevo(doc, relevo))
    if restricoes:
        folhas += paginas.paginas_restricoes(doc, restricoes)
    if solo:
        folhas.append(paginas.pagina_solo(doc, solo))

    fonte_de = {'uso': uso['fonte'], 'prodes': (prodes or {}).get('fonte'), 'relevo': (relevo or {}).get('fonte'),
                'cobertura': (cobertura or {}).get('fonte'), 'imagem': None,
                'restricoes': (restricoes or {}).get('fonte'),
                'solo': (f"{solo['fonte']}, licença {solo['licenca']}; valores modelados, pixel de 250 m" if solo else None)}
    if imagem:
        fonte_de['imagem'] = (f"{imagem['fonte']}; cena de {imagem['data']}, "
                              f"{paginas.br(imagem['livre_pct'])} % do perímetro sem nuvem")
    # figuras: a pasta do usuário ou, sem ela, o que der para baixar pelos links dos textos
    pasta_figuras, notas = (Path(args.figuras) if args.figuras else None), []
    if not pasta_figuras and not args.sem_baixar:
        textos = [Path(c).read_text(encoding='utf-8') for c in (args.imagem, args.uso, args.cobertura, args.prodes, args.relevo, args.restricoes,
                            args.solo) if c]
        baixados, falhas = baixar_figuras(textos, Path(args.saida) / 'figuras')
        if baixados:
            pasta_figuras = Path(args.saida) / 'figuras'
            notas.append(f'{len(baixados)} arquivo(s) baixado(s) pelos links: ' + ', '.join(b.name for b in baixados))
        if falhas:
            notas.append(f'não consegui baixar {len(falhas)} arquivo(s) pelos links ('
                         + ', '.join(n for n, _ in falhas) + '): ambiente sem internet ou links vencidos '
                         '(valem 1 hora). O dossiê saiu sem eles. Para incluí-los, o usuário baixa os '
                         'arquivos e você roda de novo com --figuras <pasta>')
        if not baixados and not falhas:
            notas.append('os textos não trazem os links dos arquivos: o dossiê saiu sem figuras')
    if pasta_figuras and pasta_figuras.is_dir():
        converter_imagens(pasta_figuras, avisos)

    n_figuras = 0
    for legenda, caminho, bloco in achar_figuras(pasta_figuras, args.figura):
        folha, ok = paginas.pagina_figura(doc, legenda, caminho, fonte_de.get(bloco))
        folhas.append(folha)
        n_figuras += int(ok)
        if not ok:
            avisos.append(f'a figura {caminho.name} não pôde ser lida')

    fontes = [('Uso e cobertura do solo', f'{uso["fonte"]}: mapas anuais de 30 m.')]
    if cobertura:
        fontes.append(('Cobertura do solo recente', cobertura['fonte'] + ': classificação de 10 m.'))
    if prodes:
        fontes.append(('Supressão de vegetação nativa', prodes['fonte']
                       + (f', licença {prodes["licenca"]}.' if prodes.get('licenca') else '.')))
    if relevo:
        fontes.append(('Relevo', relevo['fonte'] + '.'))
    if imagem:
        fontes.append(('Imagem de satélite', fonte_de['imagem'] + '.'))
    if restricoes:
        datas = ' · '.join(f'{nome}: {g["data"]}' for nome, g in (('CNUC', restricoes['uc']), ('FUNAI', restricoes['ti']),
                                                                     ('embargos', restricoes['embargo'])) if g['lida'] and g['data'])
        fontes.append(('Unidades de conservação, terras indígenas e termos de embargo',
                       f'{restricoes["fonte"]}: bases públicas' + (f'; data de cada base — {datas}.' if datas else '.')))
    if solo:
        fontes.append(('Solo (textura e carbono)', fonte_de['solo'] + '.'))
    if cadastro:
        fontes.append(('Cadastro Ambiental Rural', 'Consulta pública do SICAR (consulta.car.gov.br), feita em '
                       f'{paginas._data_br(cadastro.get("consultado_em"))}.'))
    fontes.append(('Processamento', 'Consultas e recortes feitos pelas ferramentas da comunidade agrônomo10X '
                   f'(OagronomIA). Dossiê montado em {doc["data"]}.'))
    folhas.append(paginas.pagina_fontes(doc, fontes, avisos))

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(saida / 'dossie.pdf') as pdf:
        for n, folha in enumerate(folhas, 1):
            figura = folha.fechar(n, len(folhas))
            pdf.savefig(figura)
            if args.png:
                figura.savefig(saida / f'pagina-{n:02d}.png', dpi=110)
            paginas.plt.close(figura)
    (saida / 'dossie.json').write_text(
        json.dumps({'documento': doc, **dados, 'avisos': avisos}, ensure_ascii=False, indent=2), encoding='utf-8')
    with open(saida / 'dossie_tabelas.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['bloco', 'ano_ou_item', 'nome', 'valor', 'unidade'])
        if uso.get('hoje'):
            for nome, ha, _ in uso['hoje']['classes']:
                w.writerow(['uso do solo', uso['hoje']['ano'], nome, paginas.br(ha), 'ha'])
        for m in uso.get('marcos', []):
            w.writerow(['vegetação nativa', m['ano'], 'total', paginas.br(m['nativa_ha']), 'ha'])
            for nome, ha, _ in m['classes']:
                w.writerow(['uso do solo', m['ano'], nome, paginas.br(ha), 'ha'])
        for c in (cobertura or {}).get('classes', []):
            w.writerow(['cobertura recente (10 m)', (cobertura.get('periodo') or ('', ''))[1], c['nome'],
                        paginas.br(c['ha']), 'ha'])
        for nome, ha in uso.get('situacao', []):
            w.writerow(['situação frente aos marcos', '', nome, paginas.br(ha), 'ha'])
        for ano, ha in uso.get('abertura_por_ano', []):
            w.writerow(['ano da abertura', ano, '', paginas.br(ha), 'ha'])
        for chave, x in ((prodes or {}).get('faixas') or {}).items():
            w.writerow(['PRODES', chave, f'{x["n"]} polígono(s)', paginas.br(x['ha']), 'ha'])
        for nome, faixa, pct, ha in (relevo or {}).get('classes', []):
            w.writerow(['relevo', faixa, nome, paginas.br(ha), 'ha'])
        for t in (cadastro or {}).get('temas', []):
            if 'area_ha' in t:
                w.writerow(['CAR declarado', t['camada'], t['rotulo'], paginas.br(t['area_ha'], 2), 'ha'])
        for nome, chave in (('unidades de conservação', 'uc'), ('terras indígenas', 'ti'), ('termos de embargo', 'embargo')):
            g = (restricoes or {}).get(chave)
            if g and g['lida']:
                w.writerow(['restrições', g['data'] or '', f'{nome}: {g["n"]} sobrepõe(m)', paginas.br(g['ha']), 'ha'])
        for c in (solo or {}).get('camadas', []):
            w.writerow(['solo (estimativa SoilGrids)', c['camada'], f'argila; textura {c["textura"]}', paginas.br(c['argila']), '%'])
            w.writerow(['solo (estimativa SoilGrids)', c['camada'], 'carbono orgânico', paginas.br(c['carbono_g_kg']), 'g/kg'])

    print(f'dossiê: {saida / "dossie.pdf"} ({len(folhas)} páginas, {n_figuras} figura(s))')
    for nota in notas:
        print(f'  figuras: {nota}')
    for a in avisos:
        print(f'  · {a}')
    if not avisos:
        print('  conferências de soma: tudo fechou')
    return 0


def _demo(args):
    """Dossiê de exemplo com dados inventados (não é um imóvel real)."""
    saida = Path(args.saida) if args.saida != './dossie' else Path('./demo-dossie')
    saida.mkdir(parents=True, exist_ok=True)
    anel = [[-49.62, -22.70], [-49.60, -22.70], [-49.598, -22.685], [-49.61, -22.676], [-49.622, -22.684], [-49.62, -22.70]]
    (saida / 'perimetro.geojson').write_text(json.dumps({
        'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {},
                                                   'geometry': {'type': 'Polygon', 'coordinates': [anel]}}]}),
        encoding='utf-8')
    (saida / 'uso.txt').write_text('''Área completa — 520 ha. USO DO SOLO pelos mapas ANUAIS de 30 m do MapBiomas Coleção 11, de 1985 a 2025:
HOJE (mapa de 2025): Soja 260 ha (50 %) · Formação Florestal 150 ha (29 %) · Pastagem 90 ha (17 %) · Formação Savânica 20 ha (4 %). Vegetação nativa: 170 ha (33 %).

DATAS-MARCO (cada mapa é do ANO inteiro, não do dia do marco):
- 1985 (primeiro mapa): vegetação nativa 300 ha (58 %) · Formação Florestal 260 ha (50 %) · Pastagem 220 ha (42 %) · Formação Savânica 40 ha (8 %)
- 2008 (Código Florestal, marco de 22/07/2008): vegetação nativa 195 ha (38 %) · Pastagem 325 ha (63 %) · Formação Florestal 170 ha (33 %) · Formação Savânica 25 ha (5 %)
- 2019 (crédito rural, marco de 31/07/2019): vegetação nativa 182 ha (35 %) · Soja 240 ha (46 %) · Formação Florestal 160 ha (31 %) · Pastagem 98 ha (19 %) · Formação Savânica 22 ha (4 %)
- 2020 (regra europeia EUDR, marco de 31/12/2020): vegetação nativa 178 ha (34 %) · Soja 250 ha (48 %) · Formação Florestal 157 ha (30 %) · Pastagem 92 ha (18 %) · Formação Savânica 21 ha (4 %)

SITUAÇÃO HOJE (cada pixel numa faixa só): Vegetação nativa 170 ha · Uso que já existia em 2008 325 ha · Aberto de 2009 a 2019 13 ha · Aberto em 2020 4 ha · Aberto depois de 2020 8 ha
ABERTO DEPOIS DE 2008: 25 ha · depois de 2019: 12 ha · depois de 2020: 8 ha.
ANO DA ABERTURA (área hoje em uso que era nativa no ano anterior): 1990 40 ha · 1996 35 ha · 2004 30 ha · 2013 9 ha · 2017 4 ha · 2020 4 ha · 2022 5 ha · 2024 3 ha.

Cite a fonte: MapBiomas Coleção 11.
''', encoding='utf-8')
    (saida / 'prodes.txt').write_text('''Área completa — 520 ha. PRODES e alertas do DETER que tocam a área, recortados nela — bioma: Cerrado:
DEPOIS DE 31/07/2019 (PRODES 2020 em diante): 2 polígono(s), 9,6 ha na área — 8 ha em 1 polígono(s) ACIMA do mínimo da nota do MMA e 1,6 ha em 1 ABAIXO dele.
PRODES 2019 — À PARTE, zona cinzenta (as imagens de 2019 são de antes e de depois de 31/07/2019): nenhum polígono.
PRODES de 2008 a 2018: 1 polígono(s), 9 ha na área — 9 ha em 1 polígono(s) ACIMA do mínimo da nota do MMA e 0 ha em 0 ABAIXO dele.

POLÍGONOS (mais recentes primeiro):
- PRODES 2022 (imagem de 14/08/2022): 8 ha na área (polígono de 21,5 ha) — acima do mínimo de 5 ha
- PRODES 2021: 1,6 ha na área (polígono de 1,6 ha) — ABAIXO do mínimo de 5 ha
- PRODES 2013 (imagem de 02/09/2013): 9 ha na área (polígono de 60 ha) — acima do mínimo de 5 ha

ALERTAS DO DETER (avisos rápidos, NÃO consolidados) desde 01/11/2024: 1 alerta(s), 3 ha na área; depois da última imagem do PRODES (o que o PRODES ainda não cobre): 1 alerta(s), 3 ha. Os anteriores a ela podem já estar no PRODES.
- 12/09/2026 · Desmatamento com solo exposto · 3 ha · depois da última imagem do PRODES

ATÉ ONDE VAI O DADO: Cerrado: PRODES até 2026 (última imagem em 28/08/2026).

Cite a fonte como está: PRODES e DETER (INPE, Programa BiomasBR — TerraBrasilis), licença CC BY-SA 4.0.
''', encoding='utf-8')
    (saida / 'relevo.txt').write_text('''Área completa — 520 ha. RELEVO pelo terreno de 30 m (o chão, sem a vegetação):
ALTITUDE: de 480 a 560 m (média 515 m; desnível 80 m).
DECLIVE: médio 5,2 % · 90 % da área abaixo de 9,8 % · máximo 24 %.
CLASSES DE RELEVO (Embrapa): Plano (0–3%) 30 % = 156 ha · Suave ondulado (3–8%) 52 % = 270,4 ha · Ondulado (8–20%) 17 % = 88,4 ha · Forte ondulado (20–45%) 1 % = 5,2 ha
MECANIZAÇÃO (faixas USUAIS de referência técnica, não regra): sem restrição (até 12%) 94 % · com restrição (12–20%) 5 % · difícil (acima de 20%) 1 %
ENCOSTA ACIMA DE 45° (APP de encosta pelo Código Florestal): nenhuma na leitura do terreno de 30 m.

Cite a fonte como está: ANADEM v1 (UFRGS/ANA), derivado do Copernicus DEM GLO-30.
''', encoding='utf-8')
    (saida / 'restricoes.txt').write_text('''Área completa — 520 ha. RESTRIÇÕES que a área sobrepõe ou que ficam perto dela, pelas bases públicas: unidades de conservação (CNUC, MMA), terras indígenas (FUNAI) e embargos (IBAMA e ICMBio).

UNIDADES DE CONSERVAÇÃO (CNUC, MMA, versão de 31/07/2026):
1 unidade(s) sobrepõe(m) a área: 130 ha, 25% dela (o que se sobrepõe entre unidades conta uma vez).
- Área de Proteção Ambiental Exemplo — Área de Proteção Ambiental, uso sustentável, esfera estadual, criada em 1983; plano de manejo: sim; 130 ha na área (25%); a unidade inteira tem 83.310 ha
PERTO (até 10 km da divisa): 1 unidade(s).
- Parque Estadual Exemplo (Parque, proteção integral, esfera estadual) a 2,88 km

TERRAS INDÍGENAS (FUNAI, base atualizada até 10/11/2026):
Nenhuma terra indígena sobrepõe a área.
Nenhuma terra indígena a até 10 km da divisa.

EMBARGOS (IBAMA, base atualizada até 11/11/2026; ICMBio, até 31/10/2026):
2 termo(s) de embargo toca(m) a área: 1 com contorno (12,4 ha dentro da área, 2,4% dela) e 1 marcado(s) por ponto.
- IBAMA, termo 000001-C, de 20/10/2010 — tipo não informado na base; contorno com 12,4 ha dentro da área (2,4%); área embargada declarada no termo: 57,2 ha (Município Exemplo/SP)
- IBAMA, termo 000002-E, de 26/09/2014 — desmatamento; marcado por PONTO dentro da área (o órgão registrou a coordenada, não o contorno); área embargada declarada no termo: 1 ha (Município Exemplo/SP)
Nenhum termo de embargo a até 1 km da divisa.
Ficam de fora do cruzamento os embargos que a base do IBAMA traz SEM localização (13.767 hoje): estes só aparecem na consulta pública do órgão.

O QUE ESTA LEITURA NÃO COBRE: territórios quilombolas, assentamentos, florestas públicas, embargos de órgãos estaduais e a zona de amortecimento de cada unidade (definida no plano de manejo dela). Para supressão de vegetação nativa existe o PRODES (prodes_fazenda).
Cite a fonte como está: CNUC (MMA), FUNAI, IBAMA e ICMBio. Leitura informativa das bases públicas, na data de cada uma.
''', encoding='utf-8')
    (saida / 'solo.txt').write_text('''Área completa — 520 ha. TEXTURA E CARBONO DO SOLO pelo SoilGrids 2.0 (ISRIC): mapa MUNDIAL feito por modelo, com pixel de 250 m (96 pixel(s) tocam a área).

CAMADA DE 0–30 cm (média pesada pela espessura): argila 35,5%, areia 46,9%, silte 17,6% — textura argilosa; carbono orgânico 16,4 g/kg (cerca de 2,8% de matéria orgânica).
CAMADA DE 30–100 cm: argila 43,9%, areia 40,1%, silte 16% — textura argilosa; carbono orgânico 7,3 g/kg (cerca de 1,3% de matéria orgânica).
ESTOQUE DE CARBONO ORGÂNICO DE 0–30 cm: 36,3 t de carbono por hectare — cerca de 18.876 t de carbono nos 520 ha com dado.
DENTRO DA ÁREA: a argila de 0–30 cm vai de 33,2% a 41,5% (a maior parte entre 34% e 39,8%) e o estoque de carbono, de 31 a 46 t/ha.
FAIXA DE 90% DO PRÓPRIO MODELO, em cada pixel: argila de 0–30 cm entre 4,6% e 75%; estoque entre 10,4 e 86,6 t/ha. A faixa é larga: é o tamanho da incerteza do mapa.

POR CAMADA:
- 0–5 cm: argila 33,2%, areia 47,3%, silte 19,5% — textura média; carbono orgânico 23,4 g/kg (cerca de 4% de matéria orgânica)
- 5–15 cm: argila 34,8%, areia 47%, silte 18,2% — textura média; carbono orgânico 17,9 g/kg (cerca de 3,1% de matéria orgânica)
- 15–30 cm: argila 37%, areia 46,6%, silte 16,4% — textura argilosa; carbono orgânico 12,9 g/kg (cerca de 2,2% de matéria orgânica)
- 30–60 cm: argila 42,5%, areia 41,3%, silte 16,2% — textura argilosa; carbono orgânico 8,6 g/kg (cerca de 1,5% de matéria orgânica)
- 60–100 cm: argila 45%, areia 39,2%, silte 15,8% — textura argilosa; carbono orgânico 6,3 g/kg (cerca de 1,1% de matéria orgânica)
- 100–200 cm: argila 45,8%, areia 38,6%, silte 15,6% — textura argilosa; carbono orgânico 4,9 g/kg (cerca de 0,8% de matéria orgânica)

Cite a fonte como está: SoilGrids 2.0 (ISRIC — World Soil Information), licença CC BY 4.0. Mapa mundial de 250 m, valores modelados.
''', encoding='utf-8')
    codigo = principal(['--perimetro', str(saida / 'perimetro.geojson'), '--nome', 'Fazenda Demonstração (dados inventados)',
                        '--uso', str(saida / 'uso.txt'), '--prodes', str(saida / 'prodes.txt'),
                        '--relevo', str(saida / 'relevo.txt'), '--restricoes', str(saida / 'restricoes.txt'),
                        '--solo', str(saida / 'solo.txt'), '--municipio', 'Município Exemplo/SP', '--sem-baixar',
                        '--saida', str(saida)])
    lido = json.loads((saida / 'dossie.json').read_text(encoding='utf-8'))
    assert lido['avisos'] == [], lido['avisos']
    assert lido['prodes']['faixas']['depois_2019']['ha'] == 9.6 and len(lido['prodes']['poligonos']) == 3
    assert lido['restricoes']['uc']['ha'] == 130 and lido['restricoes']['embargo']['n_ponto'] == 1
    assert lido['restricoes']['ti']['lida'] and lido['restricoes']['ti']['n'] == 0
    assert lido['solo']['superficie']['argila'] == 35.5 and len(lido['solo']['camadas']) == 6
    assert [n for n, _ in links_dos_arquivos('- restricoes.png (90 KB): https://127.0.0.1:9/a/restricoes.png\n'
                                             '- solo_0_30cm.tif (40 KB): https://127.0.0.1:9/a/solo_0_30cm.tif')] \
        == ['restricoes.png', 'solo_0_30cm.tif']
    assert BAIXAR.match('restricoes.png') and BAIXAR.match('solo_textura_carbono.png') and not BAIXAR.match('solo_0_30cm.tif')
    assert (saida / 'dossie.pdf').stat().st_size > 30000
    # links: só https, só os arquivos da lista; falha de rede vira aviso, não erro
    exemplo = ('- uso_solo_situacao.png (126 KB): https://127.0.0.1:9/a/uso_solo_situacao.png?token=x\n'
               '- uso_do_solo.gpkg (596 KB): https://127.0.0.1:9/a/uso_do_solo.gpkg\n'
               '- outro.png (1 KB): http://sem-https/outro.png')
    assert [n for n, _ in links_dos_arquivos(exemplo)] == ['uso_solo_situacao.png', 'uso_do_solo.gpkg']
    baixados, falhas = baixar_figuras([exemplo], saida / 'figuras-teste')
    assert not baixados and [n for n, _ in falhas] == ['uso_solo_situacao.png'], (baixados, falhas)
    print('demo OK: dossiê de exemplo montado, sem aviso de conferência')
    return codigo


if __name__ == '__main__':
    sys.exit(principal())
