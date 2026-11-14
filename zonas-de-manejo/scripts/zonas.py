"""Zonas de manejo a partir de camadas de dados do talhão.

Duas etapas, sempre nesta ordem:

  1. DIAGNÓSTICO (não gera zonas): as camadas disponíveis, o quanto se repetem e o
     que cada número de zonas daria.
       python scripts/zonas.py --perimetro talhao.geojson --pontos grade.csv --diagnostico

  2. ZONAS, depois de o usuário confirmar as camadas e o número de zonas:
       python scripts/zonas.py --perimetro talhao.geojson --pontos grade.csv \\
           --colunas argila,prod,altitude --k 3 --nome "Talhão 12"

  As camadas vêm de colunas de um arquivo de pontos (--pontos, --colunas), de
  rasters GeoTIFF (--raster nome=arquivo.tif, repetível) ou dos dois juntos.
  Exemplo pronto, com zonas plantadas:  python scripts/zonas.py --demo
"""

import argparse
import datetime
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

import agrupamento
import areas as mod_areas
import geometria
import geotiff
import leitura
import saidas
import zoneamento
from saidas import num


def _zona(texto):
    if not texto:
        return None
    texto = texto.strip().upper()
    return int(texto.rstrip('NS')), not texto.endswith('N')


def argumentos():
    p = argparse.ArgumentParser(description='Zonas de manejo a partir de camadas de dados.')
    p.add_argument('--perimetro', help='polígono(s) do talhão: GeoJSON, KML ou shapefile')
    p.add_argument('--pontos', help='CSV/TXT, .shp ou .zip de pontos com as camadas em colunas')
    p.add_argument('--colunas', help='colunas do arquivo de pontos que entram como camadas, separadas por vírgula')
    p.add_argument('--raster', action='append', default=[], metavar='NOME=ARQUIVO[:BANDA]',
                   help='camada em GeoTIFF (repetível)')
    p.add_argument('--pesos', help='peso de cada camada, ex.: argila=2,altitude=0.5 (padrão 1)')
    p.add_argument('--diagnostico', action='store_true', help='só mostra as camadas e as opções; não gera zonas')
    p.add_argument('--demo', action='store_true', help='roda o exemplo com zonas plantadas')
    p.add_argument('--k', default=None, help='número de zonas: um número ou "auto" (o de maior silhueta)')
    p.add_argument('--k-min', type=int, default=2), p.add_argument('--k-max', type=int, default=8)
    p.add_argument('--area-minima', type=float, default=10.0, help='menor zona e menor parte, em %% da área (padrão 10)')
    p.add_argument('--vizinhos', type=int, default=8)
    p.add_argument('--frag-total', type=float, default=3.0, help='%% do total de pontos (padrão 3)')
    p.add_argument('--frag-classe', type=float, default=20.0, help='%% dos pontos da classe (padrão 20)')
    p.add_argument('--variancia-pca', type=float, default=90.0, help='%% da variação guardada (padrão 90)')
    p.add_argument('--espacamento', type=float, help='grade de pontos, em metros, quando só há rasters')
    p.add_argument('--agregar', default='auto', help='média por célula de N metros em dado denso: auto, N ou nenhum')
    p.add_argument('--pixel', type=float, help='célula da grade das zonas, em metros')
    p.add_argument('--suavizar', type=float, help='tolerância das divisas, em metros (0 = sem suavizar)')
    p.add_argument('--ordenar-por', help='camada que dá a ordem dos números das zonas (padrão: a primeira)')
    p.add_argument('--separar-partes', action='store_true', help='no shapefile, uma feição por parte de zona')
    p.add_argument('--x'), p.add_argument('--y')
    p.add_argument('--zona', help='zona UTM quando as coordenadas estão em metros sem .prj (ex.: 22S)')
    p.add_argument('--nome', default='', help='título do relatório')
    p.add_argument('--casas', type=int, default=2)
    p.add_argument('--saida', default='saida-zonas')
    return p.parse_args()


def _rasters(lista):
    saida = []
    for item in lista:
        nome, sep, resto = item.partition('=')
        if not sep or not nome.strip():
            raise SystemExit(f'--raster no formato nome=arquivo.tif (recebido: {item!r})')
        banda = 1
        m = re.search(r':(\d+)$', resto)
        if m and not Path(resto).exists():
            resto, banda = resto[:m.start()], int(m.group(1))
        saida.append((nome.strip(), resto.strip(), banda))
    return saida


def parece_identificador(v):
    v = v[np.isfinite(v)]
    return len(v) > 10 and bool(np.all(v == np.round(v))) and len(np.unique(v)) > 0.95 * len(v)


def carregar(a, exigir_colunas):
    """Lê perímetro, pontos e rasters. Devolve dict com areas, zona, sul, xy, X, nomes e as contagens."""
    if not a.perimetro:
        raise SystemExit('informe --perimetro (ou rode com --demo)')
    if not a.pontos and not a.raster:
        raise SystemExit('informe as camadas: --pontos com --colunas, --raster nome=arquivo.tif, ou os dois')
    try:
        lidas, crs_per, zona_per = mod_areas.ler_areas(a.perimetro)
        areas, z, sul = mod_areas.para_utm(lidas, crs_per, _zona(a.zona) or zona_per)
    except ValueError as erro:
        raise SystemExit(f'perímetro: {erro}')
    area_m2 = sum(zoneamento._area(x['aneis']) for x in areas)
    info = {'area_ha': area_m2 / 10000, 'n_areas': len(areas), 'utm': f'{z}{"S" if sul else "N"}', 'avisos': [],
            'candidatas': [], 'origem': []}
    rasters = []
    for nome, caminho, banda in _rasters(a.raster):
        try:
            rasters.append((nome, geotiff.ler_geotiff(caminho, banda)))
        except (ValueError, OSError, KeyError) as erro:
            raise SystemExit(f'raster "{nome}": {erro}')
    nomes, colunas = [], []
    if a.pontos:
        try:
            t = leitura.ler_pontos(a.pontos, a.x, a.y)
            X_, Y_, _, _ = leitura.projetar(t['x'], t['y'], t['crs'], (z, sul))
        except ValueError as erro:
            raise SystemExit(f'pontos: {erro}')
        xy = np.column_stack([X_, Y_])
        ok = np.isfinite(xy).all(axis=1)
        dentro = np.zeros(len(xy), dtype=bool)
        for x in areas:
            dentro[ok] |= mod_areas.dentro(x['aneis'], xy[ok])
        candidatas = [n for n in t['numericas'] if n not in (t['coluna_x'], t['coluna_y'])]
        info['candidatas'] = [(n, t['dados'][n][dentro]) for n in candidatas]
        info.update(pontos_lidos=t['n'], pontos_dentro=int(dentro.sum()), arquivo=t['origem'])
        if a.colunas:
            pedidas = [c.strip() for c in a.colunas.split(',') if c.strip()]
            faltam = [c for c in pedidas if c not in candidatas]
            if faltam:
                raise SystemExit(f'coluna(s) que não existem ou não são numéricas: {", ".join(faltam)}. '
                                 f'Numéricas do arquivo: {", ".join(candidatas)}')
        elif exigir_colunas:
            raise SystemExit('informe --colunas com as camadas que o usuário confirmou (rode antes com --diagnostico)')
        else:
            pedidas = [n for n in candidatas if not parece_identificador(t['dados'][n])]
        xy = xy[dentro]
        nomes = list(pedidas)
        colunas = [t['dados'][n][dentro].astype(float) for n in pedidas]
        info['origem'].append(f'{len(pedidas)} coluna(s) de {t["origem"]}')
    else:
        espacamento = a.espacamento or zoneamento.espacamento_automatico(area_m2)
        xy = zoneamento.grade_de_pontos(areas, espacamento)
        info.update(grade_de_pontos_m=espacamento)
    for nome, r in rasters:
        nomes.append(nome)
        colunas.append(geotiff.amostrar(r, xy[:, 0], xy[:, 1], z, sul))
        info['origem'].append(f'raster {nome} ({r["largura"]} × {r["altura"]}, pixel de {r["dx"]:g}'
                              f'{"°" if r["crs"] == "geo" else " m"})')
    if not nomes:
        raise SystemExit('nenhuma camada numérica para usar')
    if len(set(nomes)) != len(nomes):
        raise SystemExit('há camadas com o mesmo nome: dê nomes diferentes em --raster')
    X = np.column_stack(colunas)
    completos = np.isfinite(X).all(axis=1)
    info.update(pontos_no_perimetro=len(xy), sem_valor=int((~completos).sum()),
                sem_valor_por_camada={n: int((~np.isfinite(X[:, j])).sum()) for j, n in enumerate(nomes)})
    xy, X = xy[completos], X[completos]
    if info['pontos_no_perimetro'] and info['sem_valor'] / info['pontos_no_perimetro'] > 0.05:
        info['avisos'].append(f'{info["sem_valor"]} de {info["pontos_no_perimetro"]} pontos ficaram de fora por não '
                              f'terem valor em alguma camada: confira se os rasters cobrem o talhão inteiro.')
    info['agregado_m'] = None
    pedido = str(a.agregar).strip().lower()
    if pedido not in ('nenhum', 'nenhuma', 'nao', 'não', '0'):
        celula = None
        if pedido == 'auto':
            if len(xy) > zoneamento.TETO_PARA_AGREGAR:
                celula = zoneamento.espacamento_automatico(area_m2, alvo=8000)
        else:
            celula = float(pedido.replace(',', '.'))
        if celula:
            antes = len(xy)
            xy, X, _ = zoneamento.agregar(xy, X, celula)
            info.update(agregado_m=celula, pontos_antes_de_agregar=antes)
    info['pontos'] = len(xy)
    pesos = None
    if a.pesos:
        dados = dict(item.split('=') for item in a.pesos.split(',') if '=' in item)
        estranhos = [k for k in dados if k.strip() not in nomes]
        if estranhos:
            raise SystemExit(f'peso para camada que não existe: {", ".join(estranhos)}')
        pesos = [float(str(dados.get(n, 1)).replace(',', '.')) for n in nomes]
    ordenar = 0
    if a.ordenar_por:
        if a.ordenar_por not in nomes:
            raise SystemExit(f'--ordenar-por: "{a.ordenar_por}" não está entre as camadas ({", ".join(nomes)})')
        ordenar = nomes.index(a.ordenar_por)
    return {'areas': areas, 'zona': z, 'sul': sul, 'xy': xy, 'X': X, 'nomes': nomes, 'pesos': pesos,
            'ordenar': ordenar, 'info': info}


def configuracao(a, d):
    k = a.k if a.k is None or str(a.k).lower() == 'auto' else int(a.k)
    return {'k': 'auto' if k is None else k, 'k_min': a.k_min, 'k_max': a.k_max, 'area_minima': a.area_minima / 100,
            'vizinhos': a.vizinhos, 'frag_total': a.frag_total / 100, 'frag_classe': a.frag_classe / 100,
            'variancia_pca': a.variancia_pca / 100, 'pesos': d['pesos'], 'pixel': a.pixel, 'suavizar': a.suavizar,
            'ordenar_por': d['ordenar']}


def _para_json(o):
    if isinstance(o, dict):
        return {str(k): _para_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_para_json(v) for v in o]
    if isinstance(o, np.ndarray):
        return _para_json(o.tolist())
    if isinstance(o, (np.floating, float)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def _cabecalho(d):
    i = d['info']
    print(f'Perímetro: {num(i["area_ha"], 1)} ha em {i["n_areas"]} área(s) · SIRGAS 2000 / UTM {i["utm"]}')
    if 'arquivo' in i:
        print(f'Pontos: {i["arquivo"]} · {i["pontos_lidos"]} lidos · {i["pontos_dentro"]} dentro do perímetro')
    else:
        print(f'Sem arquivo de pontos: os rasters foram lidos numa grade de {num(i["grade_de_pontos_m"], 0)} m '
              f'({i["pontos_no_perimetro"]} pontos)')
    if i['sem_valor']:
        print(f'  {i["sem_valor"]} ponto(s) sem valor em alguma camada ficaram de fora: {i["sem_valor_por_camada"]}')
    if i['agregado_m']:
        print(f'  dado denso: média por célula de {num(i["agregado_m"], 0)} m ({i["pontos_antes_de_agregar"]} pontos → '
              f'{i["pontos"]})')
    print(f'Pontos usados: {i["pontos"]} · espaçamento típico: {num(zoneamento.espacamento_tipico(d["xy"]), 1)} m')


def rodar_diagnostico(a, d, cfg, pasta):
    i, X, nomes = d['info'], d['X'], d['nomes']
    print('DIAGNÓSTICO — nenhuma zona foi gerada')
    _cabecalho(d)
    if i['candidatas']:
        print('Colunas numéricas do arquivo de pontos (CONFIRME COM O USUÁRIO quais são camadas):')
        for nome, v in i['candidatas']:
            bons = v[np.isfinite(v)]
            marca = '  [parece identificador: não use]' if parece_identificador(v) else ''
            faixa = f'de {num(bons.min())} a {num(bons.max())}, média {num(bons.mean())}' if len(bons) else 'vazia'
            print(f'  - {nome}: {faixa}{marca}')
    print(f'Camadas neste diagnóstico ({len(nomes)}): ' + '; '.join(i['origem']))
    for j, nome in enumerate(nomes):
        media, dp = float(X[:, j].mean()), float(X[:, j].std())
        print(f'  - {nome}: de {num(X[:, j].min())} a {num(X[:, j].max())}, média {num(media)}, '
              f'CV {num(100 * dp / abs(media), 1) if media else "—"}%')
    if len(nomes) > 1:
        corr = np.corrcoef(X.T)
        pares = sorted(((abs(corr[p, q]), nomes[p], nomes[q], corr[p, q]) for p in range(len(nomes))
                        for q in range(p + 1, len(nomes))), reverse=True)
        print('Correlação entre as camadas (as mais altas): '
              + '; '.join(f'{b} × {c} = {num(r, 2)}' for _, b, c, r in pares[:6]))
        for _, b, c, r in pares:
            if abs(r) > 0.9:
                print(f'  ATENÇÃO: "{b}" e "{c}" andam juntas ({num(r, 2)}): a mesma informação entra duas vezes.')
    Z, _, _ = agrupamento.padronizar(X, d['pesos'])
    comp = agrupamento.pca(Z, cfg['variancia_pca'])
    print(f'Componentes principais: {comp["componentes"]} guardam '
          f'{num(100 * sum(comp["explicada"][:comp["componentes"]]), 0)}% da variação '
          f'(cada uma: {", ".join(num(100 * e, 0) + "%" for e in comp["explicada"][:comp["componentes"]])})')
    tabela = agrupamento.escolher_k(comp['escores'], a.k_min, a.k_max, 0)
    min_pontos = max(int(math.ceil(cfg['area_minima'] * len(X))), 1)
    print(f'Número de grupos (área mínima de {num(a.area_minima, 0)}% = {num(i["area_ha"] * cfg["area_minima"], 1)} ha '
          f'por zona e por parte):')
    linhas = []
    for t in tabela:
        rot = agrupamento.tamanho_minimo(d['xy'], t['rotulos'], min_pontos, cfg['vizinhos'])
        rot, _ = agrupamento.refinar_fragmentos(d['xy'], rot, cfg['vizinhos'], cfg['frag_total'], cfg['frag_classe'])
        restam = len(np.unique(rot))
        explica = float(np.nanmean([agrupamento.reducao_de_variancia(X[:, j], rot) for j in range(len(nomes))])) \
            if restam > 1 else 0.0
        linhas.append({'k': t['k'], 'silhueta': t['silhueta'], 'zonas_depois_do_refino': restam, 'explicam': explica})
        print(f'  k = {t["k"]}: silhueta {num(t["silhueta"], 2)} · depois do refino sobram {restam} zona(s) · '
              f'explicam em média {num(100 * explica, 0)}% da variação das camadas')
    melhor = max(tabela, key=lambda t: t['silhueta'] if np.isfinite(t['silhueta']) else -9)
    print(f'SUGESTÃO pela maior silhueta: k = {melhor["k"]} (silhueta {num(melhor["silhueta"], 2)}). É um critério '
          f'estatístico: quem decide quantas zonas dá para manejar é o usuário.')
    if melhor['silhueta'] < 0.25:
        print('  ATENÇÃO: silhueta abaixo de 0,25 em todos os casos. As camadas não formam grupos nítidos.')
    for aviso in i['avisos']:
        print('ATENÇÃO:', aviso)
    (pasta / 'diagnostico.json').write_text(json.dumps(_para_json({
        'area_ha': i['area_ha'], 'pontos': i['pontos'], 'camadas': nomes, 'origem': i['origem'],
        'componentes': comp['componentes'], 'explicada': comp['explicada'], 'opcoes': linhas,
        'sugestao_k': melhor['k'], 'avisos': i['avisos']}), ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'Números: {pasta / "diagnostico.json"}')
    return 0


def rodar_zonas(a, d, cfg, pasta):
    if a.k is None:
        raise SystemExit('informe --k com o número de zonas que o usuário escolheu, ou --k auto para ficar com o de '
                         'maior silhueta (rode antes com --diagnostico)')
    try:
        r = zoneamento.zonear(d['xy'], d['X'], d['nomes'], d['areas'], cfg)
    except ValueError as erro:
        raise SystemExit(str(erro))
    r['alertas'] = d['info']['avisos'] + r['alertas']
    nomes, z, sul = d['nomes'], d['zona'], d['sul']
    graus = saidas.em_graus(r['zonas'], z, sul)
    saidas.gravar_geojson(pasta / 'zonas.geojson', r['zonas'], graus, nomes)
    saidas.gravar_kml(pasta / 'zonas.kml', r['zonas'], graus, a.nome or 'Zonas de manejo')
    saidas.gravar_shapefile_zip(pasta / 'zonas-shapefile.zip', r['zonas'], graus, nomes, a.separar_partes)
    g = r['grade']
    geotiff.escrever_geotiff(pasta / 'zonas.tif', np.where(r['grade_de_zonas'] > 0, r['grade_de_zonas'], np.nan),
                             g['x0'], g['y0'], g['pixel'], geometria.epsg_utm(z, sul))
    saidas.gravar_resumo(pasta / 'zonas-resumo.csv', r['zonas'], nomes)
    saidas.gravar_pontos(pasta / 'pontos-com-zona.csv', d['xy'], d['X'], nomes, r['zona_do_ponto'], z, sul)
    meta = {'titulo': a.nome or 'Zonas de manejo', 'data': datetime.date.today().strftime('%d/%m/%Y'),
            'utm': d['info']['utm'], 'casas': a.casas}
    saidas.relatorio(pasta / 'relatorio-zonas.pdf', pasta / 'relatorio-zonas.png', r, d['areas'], d['xy'], d['X'], nomes, meta)
    resumo = {k: v for k, v in r.items() if k not in ('zonas', 'grade', 'grade_de_zonas', 'zona_do_ponto', 'correlacao')}
    resumo['zonas'] = [{k: v for k, v in zona.items() if k not in ('poligonos', 'rotulo')} for zona in r['zonas']]
    resumo.update(meta=meta, camadas=nomes, origem=d['info']['origem'])
    (pasta / 'zonas.json').write_text(json.dumps(_para_json(resumo), ensure_ascii=False, indent=1), encoding='utf-8')

    print(f'ZONAS DE MANEJO — {meta["titulo"]}')
    _cabecalho(d)
    print(f'Camadas ({len(nomes)}): {", ".join(nomes)}' + (f' · pesos: {d["pesos"]}' if d['pesos'] else ''))
    e = r['etapas']
    print(f'K-Means: {r["k_escolhido"]} grupos ' + ('(maior silhueta)' if r['k_automatico'] else '(fixado)')
          + f', silhueta {num(r["silhueta"], 2)} · classes absorvidas: {e["classes_absorvidas"]} · fragmentos '
          f'reatribuídos: {e["fragmentos_reatribuidos"]} · partes fundidas: {e["partes_fundidas"]}')
    print(f'Resultado: {r["k_final"]} zona(s) em {num(r["area_ha"], 1)} ha · numeradas da menor para a maior média de '
          f'{r["ordenado_por"]}')
    for zona in r['zonas']:
        medias = ' · '.join(f'{n} {num(zona["estat"][n]["media"], a.casas)}' for n in nomes) if zona['estat'] else ''
        print(f'  Zona {zona["zona"]}: {num(zona["ha"])} ha ({num(zona["pct"], 1)}%) em {zona["partes"]} parte(s) · {medias}')
    print('O que as zonas explicam de cada camada: '
          + ' · '.join(f'{n} {num(100 * v, 0)}%' for n, v in r['reducao'].items()))
    for aviso in r['alertas']:
        print('AVISO:', aviso)
    if not r['alertas']:
        print('Nenhum aviso.')
    print(f'Arquivos em {pasta}: zonas.geojson, zonas.kml, zonas-shapefile.zip, zonas.tif, zonas-resumo.csv, '
          f'pontos-com-zona.csv, relatorio-zonas.pdf, relatorio-zonas.png, zonas.json')
    return r


def demo(a, pasta):
    import sintetico

    exemplo = sintetico.talhao()
    sintetico.gravar_csv(pasta / 'exemplo-pontos.csv', exemplo)
    sintetico.gravar_perimetro(pasta / 'exemplo-perimetro.geojson', exemplo)
    sintetico.gravar_raster(pasta / 'exemplo-indice.tif', exemplo)
    a.perimetro, a.pontos = str(pasta / 'exemplo-perimetro.geojson'), str(pasta / 'exemplo-pontos.csv')
    a.raster = [f'indice_vegetacao={pasta / "exemplo-indice.tif"}']
    a.nome = a.nome or 'Talhão de exemplo · zonas plantadas'
    d = carregar(a, exigir_colunas=False)
    rodar_diagnostico(a, d, configuracao(a, d), pasta)
    print()
    a.colunas, a.k = 'argila_g_kg,prod_t_ha,altitude_m', 'auto'
    d = carregar(a, exigir_colunas=True)
    r = rodar_zonas(a, d, configuracao(a, d), pasta)
    certo = sintetico.acerto(r['zona_do_ponto'], exemplo['verdade'])
    print()
    print('Este exemplo é um talhão INVENTADO, com três zonas plantadas de propósito e ruído por cima.')
    print(f'O método pôs {num(100 * certo, 1)}% dos pontos na zona plantada. Em talhão de verdade não existe gabarito: '
          f'a conferência é no campo.')
    return 0


def principal():
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    a = argumentos()
    pasta = Path(a.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    if a.demo:
        return demo(a, pasta)
    d = carregar(a, exigir_colunas=not a.diagnostico)
    cfg = configuracao(a, d)
    if a.diagnostico:
        return rodar_diagnostico(a, d, cfg, pasta)
    rodar_zonas(a, d, cfg, pasta)
    return 0


if __name__ == '__main__':
    sys.exit(principal())
