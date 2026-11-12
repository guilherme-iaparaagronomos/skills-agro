"""Plano de amostragem georreferenciada: do perímetro aos pontos de coleta.

  python amostragem.py --perimetro talhoes.kml --modo grade --ha-por-ponto 2 --saida ./plano
  python amostragem.py --perimetro talhoes.shp --modo celula --ha-por-celula 5 --subamostras 8
  python amostragem.py --perimetro fazenda.geojson --modo zona --zonas zonas.geojson \
      --subamostras 15 --ha-por-amostra 20

Modos:
- grade   um ponto por malha de uma grade regular; cada ponto é uma amostra;
- celula  a área é dividida em células; cada célula é UMA amostra composta;
- zona    cada zona (ou talhão) é uma ou mais amostras compostas.

Saídas em --saida: pontos.geojson, pontos.kml, pontos.gpx, pontos.csv,
pontos-shapefile.zip, planilha_de_campo.csv, mapa_amostragem.pdf/.png,
resumo.json e, no modo celula, celulas.geojson.

O script desenha o plano com os números que o usuário deu. Densidade, modo e
camadas são decisão do responsável técnico.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

import areas as modulo_areas  # noqa: E402
import desenho  # noqa: E402
import saidas  # noqa: E402

NOMES_DO_MODO = {'grade': 'Grade regular', 'celula': 'Células com amostra composta',
                 'zona': 'Amostra composta por zona'}


def _zona_manual(texto):
    if not texto:
        return None
    m = re.fullmatch(r'(\d{1,2})\s*([NnSs])', texto.strip())
    if not m:
        raise SystemExit('--zona no formato 22S / 18N')
    return int(m.group(1)), m.group(2).upper() == 'S'


def planejar(args):
    """Monta o plano. Devolve (areas, pontos, amostras, celulas, resumo)."""
    arquivo = args.zonas if (args.modo == 'zona' and args.zonas) else args.perimetro
    campo = args.campo_zona if (args.modo == 'zona' and args.zonas) else args.campo_area
    lidas, crs, zona_prj = modulo_areas.ler_areas(arquivo, campo)
    lista, z, sul = modulo_areas.para_utm(lidas, crs, _zona_manual(args.zona) or zona_prj)

    pontos, amostras, celulas, por_area, avisos = [], [], [], [], []
    vistos, corrida = {}, 0
    for area in lista:
        codigo = modulo_areas.nome_limpo(area['nome'])[:12] or 'A'
        vistos[codigo] = vistos.get(codigo, 0) + 1
        if vistos[codigo] > 1:  # dois talhões com o mesmo nome não podem gerar o mesmo ID
            codigo = f'{codigo}{vistos[codigo]}'
        ha = modulo_areas.area_ha(area['aneis'])
        grupos = []  # cada grupo = os pontos de UMA amostra de laboratório
        if args.modo == 'grade':
            esp = args.espacamento or desenho.espacamento_de(args.ha_por_ponto, args.arranjo)
            grupos = [np.array([p]) for p in desenho.grade(area['aneis'], esp, args.arranjo, args.angulo, args.borda)]
        elif args.modo == 'celula':
            lado = args.lado or (args.ha_por_celula * 10000) ** 0.5
            for c in desenho.celulas(area['aneis'], lado, args.subamostras, args.angulo, args.borda):
                grupos.append(c['pontos'])
                celulas.append({'area': area['nome'], 'quadro': c['quadro'], '_indice': len(grupos)})
        else:
            n = max(1, round(ha / args.ha_por_amostra)) if args.ha_por_amostra else 1
            grupos = desenho.compostas(area['aneis'], n, args.subamostras, args.borda)
        if not grupos:
            avisos.append(f'{area["nome"]} ({saidas.br(ha)} ha): nenhum ponto coube com estes parâmetros')
        n_pontos = 0
        for i, grupo in enumerate(grupos, 1):
            corrida += 1
            id_amostra = (f'{args.prefixo}{corrida:03d}' if args.numeracao == 'corrida' else f'{codigo}-{i:02d}')
            for k, (x, y) in enumerate(np.asarray(grupo).tolist(), 1):
                pontos.append({'id': id_amostra if len(grupo) == 1 else f'{id_amostra}.{k}', 'area': area['nome'],
                               'amostra': id_amostra, 'x': x, 'y': y})
            centro = np.asarray(grupo).mean(axis=0)
            amostras.append({'id': id_amostra, 'area': area['nome'], 'n_pontos': len(grupo),
                             'x': float(centro[0]), 'y': float(centro[1])})
            n_pontos += len(grupo)
        for c in celulas:
            if c['area'] == area['nome'] and '_indice' in c:
                c['id'] = amostras[len(amostras) - len(grupos) + c.pop('_indice') - 1]['id']
        por_area.append({'area': area['nome'], 'ha': round(ha, 2), 'amostras': len(grupos), 'pontos': n_pontos})

    if not pontos:
        raise SystemExit('nenhum ponto gerado: confira o perímetro e os parâmetros (densidade, borda)')
    for registros in (pontos, amostras):
        lon, lat = modulo_areas.utm_inversa([p['x'] for p in registros], [p['y'] for p in registros], z, sul)
        for p, lo, la in zip(registros, lon.tolist(), lat.tolist()):
            p['lon'], p['lat'] = lo, la
    for i, p in enumerate(pontos, 1):
        p['ordem'] = i
    for c in celulas:
        lon, lat = modulo_areas.utm_inversa([q[0] for q in c['quadro']], [q[1] for q in c['quadro']], z, sul)
        c['quadro'] = [[lo, la] for lo, la in zip(lon.tolist(), lat.tolist())]
        c['quadro'].append(c['quadro'][0])

    rota_m = 0.0
    for linha in por_area:
        do_talhao = np.array([[p['x'], p['y']] for p in pontos if p['area'] == linha['area']])
        linha['rota_km'] = round(desenho.comprimento(do_talhao) / 1000, 2)
        rota_m += linha['rota_km'] * 1000
    area_total = sum(a['ha'] for a in por_area)
    camadas = [c.strip() for c in (args.camadas or '').split(',') if c.strip()]
    n_lab = len(amostras) * max(1, len(camadas))

    if args.modo == 'grade':
        esp = args.espacamento or desenho.espacamento_de(args.ha_por_ponto, args.arranjo)
        metodo = [f'Grade {"triangular" if args.arranjo == "triangular" else "quadrada"} de '
                  f'{saidas.br(esp, 0)} m; cada ponto fica no centro da malha.']
        if args.angulo:
            metodo.append(f'Grade girada em {saidas.br(args.angulo, 0)}°.')
    elif args.modo == 'celula':
        lado = args.lado or (args.ha_por_celula * 10000) ** 0.5
        metodo = [f'Células de {saidas.br(lado, 0)} m de lado ({saidas.br(lado * lado / 10000)} ha).',
                  f'Uma amostra composta por célula, com {args.subamostras} subamostras espalhadas dentro dela.',
                  'Célula com menos de 25 % da área dentro do perímetro não entra.']
    else:
        metodo = [f'Uma amostra composta a cada {saidas.br(args.ha_por_amostra, 0)} ha de cada zona.'
                  if args.ha_por_amostra else 'Uma amostra composta por zona.',
                  f'{args.subamostras} subamostras por amostra, espalhadas por toda a zona.']
    if args.borda:
        metodo.append(f'Pontos a pelo menos {saidas.br(args.borda, 0)} m da divisa.')
    if camadas:
        metodo.append('Camadas: ' + ', '.join(camadas) + ' cm.')
    metodo.append('IDs no formato que as skills de interpolação casam com o laudo.')

    resumo = {
        'titulo': args.fazenda or 'Plano de amostragem',
        'subtitulo': ' · '.join(t for t in (NOMES_DO_MODO[args.modo], args.cliente, args.finalidade) if t),
        'data': args.data or datetime.date.today().strftime('%d/%m/%Y'),
        'zona': f'{z}{"S" if sul else "N"}', 'modo': args.modo,
        'area_ha': round(area_total, 2), 'pontos': len(pontos), 'amostras': len(amostras),
        'camadas': camadas, 'amostras_de_laboratorio': n_lab,
        'ha_por_amostra': round(area_total / len(amostras), 2), 'rota_km': round(rota_m / 1000, 2),
        'por_area': por_area, 'metodo': metodo, 'avisos': avisos,
        'kpis': [('Área', saidas.br(area_total), 'ha'), ('Amostras', str(n_lab), 'para o laboratório'),
                 ('Pontos', str(len(pontos)), 'de coleta'), ('Caminhada', saidas.br(rota_m / 1000), 'km')],
    }
    if args.preco_amostra:
        resumo['custo_de_laboratorio'] = round(n_lab * args.preco_amostra, 2)
        resumo['metodo'].append(f'Laboratório: {n_lab} amostras × R$ {saidas.br(args.preco_amostra, 2)} = '
                                f'R$ {saidas.br(n_lab * args.preco_amostra, 2)}.')
    return lista, pontos, amostras, celulas, resumo


def principal(argv=None):
    p = argparse.ArgumentParser(description='Plano de amostragem georreferenciada (grade, célula ou zona)')
    p.add_argument('--perimetro', help='talhões: .kml/.geojson/.shp/.wkt')
    p.add_argument('--campo-area', help='atributo com o nome do talhão (senão: detecta)')
    p.add_argument('--modo', choices=['grade', 'celula', 'zona'], default='grade')
    p.add_argument('--zona', help='zona UTM se as coordenadas vierem em metros sem .prj (ex.: 22S)')
    # grade
    p.add_argument('--ha-por-ponto', type=float, help='grade: hectares por ponto (ex.: 2)')
    p.add_argument('--espacamento', type=float, help='grade: distância entre pontos, em metros')
    p.add_argument('--arranjo', choices=['quadrado', 'triangular'], default='quadrado')
    # célula
    p.add_argument('--ha-por-celula', type=float, help='celula: hectares por célula')
    p.add_argument('--lado', type=float, help='celula: lado da célula, em metros')
    # zona
    p.add_argument('--zonas', help='zona: arquivo de polígonos das zonas (senão, cada talhão é uma zona)')
    p.add_argument('--campo-zona', help='atributo com o nome da zona (senão: detecta)')
    p.add_argument('--ha-por-amostra', type=float, help='zona: uma amostra composta a cada tantos hectares')
    # comuns
    p.add_argument('--subamostras', type=int, default=15, help='pontos por amostra composta (celula e zona)')
    p.add_argument('--angulo', type=float, default=0.0, help='gira a grade ou as células, em graus')
    p.add_argument('--borda', type=float, default=15.0, help='distância mínima da divisa, em metros')
    p.add_argument('--camadas', help='camadas em cm, ex.: "0-20,20-40" (uma linha por camada na planilha)')
    p.add_argument('--numeracao', choices=['por-area', 'corrida'], default='por-area',
                   help='por-area: T01-03 · corrida: P001, P002…')
    p.add_argument('--prefixo', default='P', help='prefixo da numeração corrida')
    p.add_argument('--preco-amostra', type=float, help='preço da análise por amostra (só para a conta)')
    p.add_argument('--fazenda', help='nome da fazenda (título do mapa)')
    p.add_argument('--cliente')
    p.add_argument('--finalidade', help='ex.: "solo", "nematoides", "pragas" (subtítulo do mapa)')
    p.add_argument('--data')
    p.add_argument('--saida', default='./plano-amostragem')
    p.add_argument('--listar-campos', action='store_true',
                   help='só mostra os atributos do arquivo e os nomes de talhão que seriam usados')
    p.add_argument('--demo', action='store_true', help='roda um exemplo sintético com os três modos')
    args = p.parse_args(argv)
    if args.demo:
        return _demo(args)
    if not args.perimetro:
        p.error('--perimetro é obrigatório (ou use --demo)')
    if args.listar_campos:
        for arquivo, campo in ((args.perimetro, args.campo_area), (args.zonas, args.campo_zona)):
            if not arquivo:
                continue
            lidas = modulo_areas.ler_areas(arquivo, campo)[0]
            print(json.dumps({'arquivo': str(arquivo), 'areas': len(lidas),
                              'nomes_que_seriam_usados': [a['nome'] for a in lidas][:40],
                              'campos': [{'campo': c, 'exemplos': v} for c, v in modulo_areas.campos_de(arquivo)]},
                             ensure_ascii=False, indent=2))
        return 0
    if args.modo == 'grade' and not (args.ha_por_ponto or args.espacamento):
        p.error('grade: informe --ha-por-ponto ou --espacamento (a densidade é decisão do usuário)')
    if args.modo == 'celula' and not (args.ha_por_celula or args.lado):
        p.error('celula: informe --ha-por-celula ou --lado')
    for nome in ('ha_por_ponto', 'espacamento', 'ha_por_celula', 'lado', 'ha_por_amostra'):
        valor = getattr(args, nome)
        if valor is not None and valor <= 0:
            p.error(f'--{nome.replace("_", "-")} precisa ser maior que zero')
    if args.subamostras < 1 or args.borda < 0:
        p.error('--subamostras precisa ser ao menos 1 e --borda não pode ser negativa')

    lista, pontos, amostras, celulas, resumo = planejar(args)
    if len(pontos) > 20000:
        raise SystemExit(f'{len(pontos)} pontos: densidade alta demais para um plano de coleta — confira a unidade')
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    titulo = resumo['titulo']
    saidas.gravar_geojson(saida / 'pontos.geojson', pontos)
    saidas.gravar_kml(saida / 'pontos.kml', pontos, titulo)
    saidas.gravar_gpx(saida / 'pontos.gpx', pontos, titulo)
    saidas.gravar_csv(saida / 'pontos.csv', pontos)
    saidas.gravar_shapefile_zip(saida / 'pontos-shapefile.zip', pontos)
    saidas.gravar_planilha_de_campo(saida / 'planilha_de_campo.csv', amostras, resumo['camadas'])
    if celulas:
        saidas.gravar_celulas(saida / 'celulas.geojson', celulas)
    saidas.mapa(saida / 'mapa_amostragem.pdf', saida / 'mapa_amostragem.png', lista, pontos, resumo)
    (saida / 'resumo.json').write_text(
        json.dumps({k: v for k, v in resumo.items() if k != 'kpis'}, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'{NOMES_DO_MODO[args.modo]}: {resumo["amostras"]} amostra(s), {resumo["pontos"]} ponto(s) em '
          f'{saidas.br(resumo["area_ha"])} ha — 1 amostra a cada {saidas.br(resumo["ha_por_amostra"])} ha; '
          f'caminhada de {saidas.br(resumo["rota_km"])} km')
    if resumo['camadas']:
        print(f'  {resumo["amostras_de_laboratorio"]} amostras para o laboratório ({len(resumo["camadas"])} camadas)')
    for aviso in resumo['avisos']:
        print(f'  · {aviso}')
    print(f'  arquivos em {saida}')
    return 0


def _demo(args):
    """Fazenda sintética de dois talhões; roda os três modos e confere."""
    base = Path(args.saida) if args.saida != './plano-amostragem' else Path('./demo-amostragem')
    base.mkdir(parents=True, exist_ok=True)
    lon0, lat0 = -47.05, -22.85

    def quadro(dx0, dx1, dy0, dy1):
        return [[lon0 + dx0, lat0 + dy0], [lon0 + dx1, lat0 + dy0], [lon0 + dx1, lat0 + dy1],
                [lon0 + dx0, lat0 + dy1], [lon0 + dx0, lat0 + dy0]]

    talhoes = {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'talhao': 'T01'},
         'geometry': {'type': 'Polygon', 'coordinates': [quadro(0, 0.006, 0, 0.005)]}},
        {'type': 'Feature', 'properties': {'talhao': 'T02'},
         'geometry': {'type': 'Polygon', 'coordinates': [quadro(0.006, 0.011, 0, 0.004)]}}]}
    (base / 'talhoes.geojson').write_text(json.dumps(talhoes), encoding='utf-8')
    comuns = ['--perimetro', str(base / 'talhoes.geojson'), '--fazenda', 'Fazenda Demonstração']

    assert principal([*comuns, '--modo', 'grade', '--ha-por-ponto', '1', '--camadas', '0-20,20-40',
                      '--saida', str(base / 'grade')]) == 0
    r = json.loads((base / 'grade' / 'resumo.json').read_text(encoding='utf-8'))
    assert abs(r['area_ha'] - 57.0) < 2.5, r['area_ha']
    assert 0.9 < r['ha_por_amostra'] < 1.6 and r['amostras_de_laboratorio'] == 2 * r['amostras']
    pts = json.loads((base / 'grade' / 'pontos.geojson').read_text(encoding='utf-8'))['features']
    ids = [f['properties']['id'] for f in pts]
    assert ids[0] == 'T01-01' and len(set(ids)) == len(ids) and any(i.startswith('T02-') for i in ids)

    assert principal([*comuns, '--modo', 'celula', '--ha-por-celula', '5', '--subamostras', '8',
                      '--saida', str(base / 'celula')]) == 0
    r = json.loads((base / 'celula' / 'resumo.json').read_text(encoding='utf-8'))
    # célula de borda pode ter menos lugar para as subamostras, nunca mais
    assert 6 * r['amostras'] <= r['pontos'] <= 8 * r['amostras'] and (base / 'celula' / 'celulas.geojson').exists()

    assert principal([*comuns, '--modo', 'zona', '--subamostras', '15', '--ha-por-amostra', '15',
                      '--saida', str(base / 'zona')]) == 0
    r = json.loads((base / 'zona' / 'resumo.json').read_text(encoding='utf-8'))
    assert [a['amostras'] for a in r['por_area']] == [2, 2] and r['pontos'] == 60
    print('demo OK: grade, célula e zona; IDs únicos por talhão e áreas conferidas')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
