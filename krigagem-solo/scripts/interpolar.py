"""Pipeline completo: perímetro + pontos + laudo → mapas interpolados por krigagem.

Uso típico (sempre em duas etapas — casar primeiro, interpolar depois):

  1) python interpolar.py --perimetro talhao.kml --pontos amostras.shp \
       --laudo laudo.csv --so-casamento --saida ./saida
     → revise saida/casamento.csv (confiança por par) com o usuário.

  2) python interpolar.py --perimetro talhao.kml --pontos amostras.shp \
       --laudo laudo.csv --elementos "P,K,V%" --saida ./saida
     → por elemento: testa exponencial/esférico/gaussiano, valida por
       leave-one-out, interpola com o vencedor (pixel 5 m) e grava
       <elemento>.tif (GeoTIFF) + <elemento>.png (mapa com régua).

Laudo: CSV com uma linha por amostra (o assistente extrai do PDF/planilha do
laboratório). Decimais com vírgula e valores "<0,1" (metade do limite) são
tratados. Profundidades duplicadas no laudo pedem --filtro-laudo "0-20".
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

import casamento  # noqa: E402
import geometria  # noqa: E402
import krigagem  # noqa: E402
from mapa import desenhar_mapa  # noqa: E402
from raster import escrever_geotiff  # noqa: E402


def numero_br(texto):
    """Converte número em formato BR: '1.234,56'→1234.56; '<0,4'→0.2 (½ LD)."""
    t = str(texto).strip().replace(' ', '')
    if not t or t.upper() in ('ND', 'NA', 'N/A', '-', '--'):
        return None, False
    menor = t.startswith('<')
    if menor:
        t = t[1:]
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    try:
        v = float(t)
    except ValueError:
        return None, False
    return (v / 2 if menor else v), menor


def slug(nome):
    s = unicodedata.normalize('NFKD', nome)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-') or 'elemento'


def ler_laudo(caminho, filtro=None):
    """Lê o CSV do laudo. Devolve (linhas [dict], colunas na ordem)."""
    with open(caminho, encoding='utf-8-sig', newline='') as f:
        amostra = f.read(4096)
        f.seek(0)
        delim = ';' if amostra.count(';') > amostra.count(',') else ','
        leitor = csv.DictReader(f, delimiter=delim)
        colunas = leitor.fieldnames or []
        linhas = [ln for ln in leitor if any(str(v).strip() for v in ln.values())]
    if filtro:
        # igualdade canônica (ou sufixo com separador) — substring deixaria
        # "0-20" passar junto com "10-20"
        alvo = casamento.canonizar(filtro)

        def bate(v):
            c = casamento.canonizar(v)
            return c == alvo or c.endswith('-' + alvo)

        linhas = [ln for ln in linhas if any(bate(v) for v in ln.values())]
    if not linhas:
        raise SystemExit('laudo vazio (ou o --filtro-laudo não casou com nenhuma linha)')
    return linhas, colunas


def colunas_numericas(linhas, colunas, exceto):
    """Colunas em que ≥70% dos valores preenchidos são números."""
    numericas = []
    for c in colunas:
        if c == exceto:
            continue
        valores = [ln.get(c, '') for ln in linhas if str(ln.get(c, '')).strip()]
        if not valores:
            continue
        ok = sum(1 for v in valores if numero_br(v)[0] is not None)
        if ok / len(valores) >= 0.7:
            numericas.append(c)
    return numericas


def etapa_casamento(args, saida):
    """Lê tudo, casa os IDs e grava casamento.csv. Devolve o contexto inteiro."""
    aneis, crs_per, zona_per = geometria.ler_perimetro(args.perimetro)
    props, coords, crs_pts, zona_pts = geometria.ler_pontos(args.pontos)

    zona_manual = None
    if args.zona:
        m = re.fullmatch(r'(\d{1,2})\s*([NnSs])', args.zona.strip())
        if not m:
            raise SystemExit('--zona no formato 22S / 18N')
        zona_manual = (int(m.group(1)), m.group(2).upper() == 'S')

    aneis_utm, coords_utm, zona, sul, epsg = geometria.unificar_utm(
        (aneis, crs_per, zona_per), (coords, crs_pts, zona_pts), zona_manual)

    linhas, colunas = ler_laudo(args.laudo, args.filtro_laudo)

    campo_pontos, col_laudo = args.id_pontos, args.id_laudo
    score = None
    if not campo_pontos or not col_laudo:
        det_campo, det_col, score = casamento.detectar_campos_id(
            props, {c: [ln.get(c, '') for ln in linhas] for c in colunas})
        campo_pontos = campo_pontos or det_campo
        col_laudo = col_laudo or det_col
    if not campo_pontos or not col_laudo:
        raise SystemExit('não achei o campo de ID — informe --id-pontos e --id-laudo')

    ids_pontos = [str(p.get(campo_pontos, '')) for p in props]
    ids_laudo = [str(ln.get(col_laudo, '')) for ln in linhas]
    resultado = casamento.casar(ids_pontos, ids_laudo)

    # laudo com MAIS DE UMA LINHA pro mesmo id (profundidade em coluna própria):
    # sem filtro, a última linha venceria em silêncio — vira duplicata declarada
    contagem = {}
    for i in ids_laudo:
        contagem[i] = contagem.get(i, 0) + 1
    for i, vezes in contagem.items():
        if vezes > 1:
            resultado['duplicados_laudo'].setdefault(
                casamento.canonizar(i), []).append(f'{i} ({vezes} linhas)')

    # pares manuais do usuário vencem qualquer camada
    for par in args.par or []:
        ponto, _, laudo_id = par.partition('=')
        resultado['pares'] = [p for p in resultado['pares']
                              if p['ponto'] != ponto and p['laudo'] != laudo_id]
        resultado['pares'].append({'ponto': ponto, 'laudo': laudo_id,
                                   'confianca': 1.0, 'metodo': 'manual'})
        for lista in ('pontos_sem_par', 'laudo_sem_uso'):
            resultado[lista] = [v for v in resultado[lista] if v not in (ponto, laudo_id)]

    with open(saida / 'casamento.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ponto', 'laudo', 'confianca', 'metodo'])
        for p in sorted(resultado['pares'], key=lambda p: -p['confianca']):
            w.writerow([p['ponto'], p['laudo'], p['confianca'], p['metodo']])

    return {
        'aneis_utm': aneis_utm, 'coords_utm': coords_utm, 'props': props,
        'zona': f"{zona}{'S' if sul else 'N'}", 'epsg': epsg,
        'linhas': linhas, 'colunas': colunas,
        'campo_pontos': campo_pontos, 'col_laudo': col_laudo, 'score_id': score,
        'ids_pontos': ids_pontos, **resultado,
    }


def resumo_casamento(ctx):
    aprox = [p for p in ctx['pares'] if p['metodo'] == 'aproximado']
    resumo = {
        'campo_id_pontos': ctx['campo_pontos'],
        'coluna_id_laudo': ctx['col_laudo'],
        'zona_utm': ctx['zona'], 'epsg': ctx['epsg'],
        'pontos': len(ctx['ids_pontos']), 'pares': len(ctx['pares']),
        'aproximados_para_confirmar': aprox,
        'pontos_sem_par': ctx['pontos_sem_par'],
        'laudo_sem_uso': ctx['laudo_sem_uso'],
        'duplicados_laudo': ctx['duplicados_laudo'],
    }
    if ctx['duplicados_laudo']:
        resumo['atencao'] = ('o laudo tem ids repetidos (profundidades?) — '
                             'escolha uma com --filtro-laudo, ex.: --filtro-laudo "0-20"')
    return resumo


def interpolar_elemento(ctx, elemento, args, saida):
    """Krigagem de UM elemento do laudo. Devolve o bloco do relatório."""
    valor_por_laudo = {}
    censurados = 0
    for ln in ctx['linhas']:
        chave = str(ln.get(ctx['col_laudo'], ''))
        v, menor = numero_br(ln.get(elemento, ''))
        if v is not None:
            valor_por_laudo[chave] = v
            censurados += int(menor)

    xs, ys, zs = [], [], []
    for par in ctx['pares']:
        if par['confianca'] < args.min_confianca and par['metodo'] != 'manual':
            continue
        if par['laudo'] not in valor_por_laudo:
            continue
        i = ctx['ids_pontos'].index(par['ponto'])
        x, y = ctx['coords_utm'][i]
        xs.append(x)
        ys.append(y)
        zs.append(valor_por_laudo[par['laudo']])

    x, y, z, n_dup = krigagem.remover_duplicados(np.array(xs), np.array(ys), np.array(zs))
    n = len(x)
    if n < 8:
        return {'elemento': elemento, 'erro': f'só {n} pontos com valor válido '
                '(mínimo 8 p/ variograma; confira o casamento e o --min-confianca)'}

    escolha = krigagem.escolher_modelo(x, y, z)
    vencedor = escolha['vencedor']
    params = tuple(escolha['modelos'][vencedor][k]
                   for k in ('pepita', 'patamar_parcial', 'alcance_m'))

    x0, y0, nx, ny, mascara, xc, yc = geometria.grade_e_mascara(
        ctx['aneis_utm'], pixel=args.pixel)
    celulas = int(mascara.sum())
    # vizinhança móvel: em malha grande o custo global é n²×células — o modo
    # local usa só os vizinhos de cada ladrilho (buffer ~ alcance: sem emenda)
    local = args.vizinhanca == 'local' or (args.vizinhanca == 'auto' and n > 120)
    print(f'  {elemento}: modelo {vencedor}, krigando {celulas:,} células '
          f'({celulas * args.pixel**2 / 10000:,.0f} ha)'
          f'{" · vizinhança móvel" if local else ""}…', flush=True)

    def andamento(fracao):
        print(f'\r  {elemento}: {fracao:5.1%}', end='', flush=True)

    if local:
        malha, _ = krigagem.krigar_local(x, y, z, vencedor, params, xc, yc,
                                         mascara, max_pontos=args.max_pontos,
                                         progresso=andamento)
    else:
        malha, _ = krigagem.krigar(x, y, z, vencedor, params, xc, yc, mascara,
                                   progresso=andamento)
    print('\r', end='')

    negativos = int(np.nansum(malha < 0))
    if negativos:
        malha = np.where(malha < 0, 0.0, malha)  # concentração não é negativa

    nome = slug(elemento)
    escrever_geotiff(saida / f'{nome}.tif', malha, x0, y0, args.pixel, ctx['epsg'])
    rmse = escolha['modelos'][vencedor]['rmse_loo']
    desenhar_mapa(
        saida / f'{nome}.png', malha, x0, y0, args.pixel,
        ctx['aneis_utm'], list(zip(x.tolist(), y.tolist())),
        titulo=elemento,
        subtitulo=(f'krigagem ordinária{" (vizinhança móvel)" if local else ""} · '
                   f'pixel {args.pixel:g} m · modelo {vencedor} '
                   f'(RMSE LOO {rmse:.3g}) · n={n} · SIRGAS 2000 UTM {ctx["zona"]}'),
        unidade=elemento, cmap=args.cmap,
    )

    aviso = []
    if n < 25:
        aviso.append(f'n={n} é pouco p/ variograma robusto (ideal ≥ 25–30)')
    if escolha['estrutura_fraca']:
        aviso.append('estrutura espacial fraca (quase pepita pura) — o mapa tende à média')
    if censurados:
        aviso.append(f'{censurados} valores "<LD" entraram como metade do limite')
    if negativos:
        aviso.append(f'{negativos} células negativas truncadas em 0')
    if n_dup:
        aviso.append(f'{n_dup} pontos em coordenada repetida (média)')

    return {
        'elemento': elemento, 'n': n, 'min': float(z.min()), 'max': float(z.max()),
        'media': round(float(z.mean()), 4), 'modelos': escolha['modelos'],
        'vencedor': vencedor, 'dependencia_espacial': escolha['dependencia_espacial'],
        'razao_pepita': escolha['razao_pepita'],
        'vizinhanca': 'local' if local else 'global',
        'arquivos': [f'{nome}.tif', f'{nome}.png'], 'avisos': aviso,
    }


def principal(argv=None):
    p = argparse.ArgumentParser(description='Krigagem de laudo de solo (pixel 5 m)')
    p.add_argument('--perimetro', help='talhão: .kml/.geojson/.shp/.wkt')
    p.add_argument('--pontos', help='amostras: .shp/.geojson/.kml/.csv')
    p.add_argument('--laudo', help='CSV do laudo (uma linha por amostra)')
    p.add_argument('--elementos', default='', help='"P,K,V%%" ou "todos"')
    p.add_argument('--saida', default='./saida-krigagem')
    p.add_argument('--pixel', type=float, default=5.0)
    p.add_argument('--zona', help='zona UTM se as coordenadas vierem em metros sem .prj (ex.: 22S)')
    p.add_argument('--filtro-laudo', help='usa só linhas do laudo contendo o texto (ex.: "0-20")')
    p.add_argument('--id-pontos', help='atributo de ID no shape (senão: detecta)')
    p.add_argument('--id-laudo', help='coluna de ID no laudo (senão: detecta)')
    p.add_argument('--min-confianca', type=float, default=0.85,
                   help='pares abaixo disso ficam fora (confirme-os com --par)')
    p.add_argument('--par', action='append', metavar='PONTO=LAUDO',
                   help='casamento manual confirmado pelo usuário (repetível)')
    p.add_argument('--cmap', default='RdYlGn',
                   help='RdYlGn (alto=verde) | RdYlGn_r p/ Al, m%% (alto=ruim)')
    p.add_argument('--vizinhanca', choices=['auto', 'global', 'local'], default='auto',
                   help='auto: local acima de 120 pontos (malha grande)')
    p.add_argument('--max-pontos', type=int, default=96,
                   help='pontos por vizinhança no modo local')
    p.add_argument('--so-casamento', action='store_true',
                   help='só casa os IDs e mostra o resultado (etapa 1)')
    p.add_argument('--demo', action='store_true', help='roda um exemplo sintético completo')
    args = p.parse_args(argv)

    if args.demo:
        return _demo(args)
    if not (args.perimetro and args.pontos and args.laudo):
        p.error('--perimetro, --pontos e --laudo são obrigatórios (ou use --demo)')

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    ctx = etapa_casamento(args, saida)
    resumo = resumo_casamento(ctx)

    if args.so_casamento:
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
        return 0

    numericas = colunas_numericas(ctx['linhas'], ctx['colunas'], ctx['col_laudo'])
    if args.elementos.strip().lower() in ('', 'todos'):
        pedidos = numericas
    else:
        pedidos = [e.strip() for e in args.elementos.split(',') if e.strip()]
        fora = [e for e in pedidos if e not in ctx['colunas']]
        if fora:
            raise SystemExit(f'elementos fora do laudo: {fora} — colunas: {ctx["colunas"]}')

    relatorio = {'casamento': resumo, 'pixel_m': args.pixel, 'elementos': []}
    for elemento in pedidos:
        bloco = interpolar_elemento(ctx, elemento, args, saida)
        relatorio['elementos'].append(bloco)
        if 'erro' in bloco:
            print(f'✗ {elemento}: {bloco["erro"]}')
        else:
            print(f'✓ {elemento}: modelo {bloco["vencedor"]} '
                  f'(RMSE LOO {bloco["modelos"][bloco["vencedor"]]["rmse_loo"]:.3g}), '
                  f'n={bloco["n"]} → {", ".join(bloco["arquivos"])}')
            for a in bloco['avisos']:
                print(f'  · {a}')

    with open(saida / 'relatorio.json', 'w', encoding='utf-8') as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)
    print(f'\nrelatório completo: {saida / "relatorio.json"}')
    return 0


def _demo(args):
    """Exemplo sintético completo: gera arquivos, roda o pipeline, confere."""
    import json as _json

    saida = Path(args.saida) if args.saida != './saida-krigagem' else Path('./demo-krigagem')
    saida.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)

    # talhão ~28 ha perto de Campinas-SP e 36 pontos em grade perturbada
    lon0, lat0 = -47.05, -22.85
    dlon, dlat = 0.0060, 0.0045  # ~610 × 500 m
    anel = [(lon0, lat0), (lon0 + dlon, lat0 + 0.0004), (lon0 + dlon, lat0 + dlat),
            (lon0 + dlon / 2, lat0 + dlat + 0.0006), (lon0, lat0 + dlat), (lon0, lat0)]
    (saida / 'perimetro.geojson').write_text(_json.dumps({
        'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {},
            'geometry': {'type': 'Polygon', 'coordinates': [[list(p) for p in anel]]}}]}),
        encoding='utf-8')

    feicoes, linhas_laudo = [], []
    k = 0
    for i in range(6):
        for j in range(6):
            k += 1
            lon = lon0 + (i + 0.5) / 6 * dlon + rng.normal(0, 0.00012)
            lat = lat0 + (j + 0.5) / 6 * dlat + rng.normal(0, 0.00012)
            p = round(6 + 5 * np.sin(i / 1.6) + 3.5 * np.cos(j / 1.2)
                      + rng.normal(0, 0.8), 1)
            v = round(48 + 14 * np.cos(i / 1.9) + 8 * np.sin(j / 1.5)
                      + rng.normal(0, 2.5), 1)
            feicoes.append({'type': 'Feature',
                            'properties': {'plot_id': f'T01-{k:02d}'},
                            'geometry': {'type': 'Point', 'coordinates': [lon, lat]}})
            # ids do laudo de propósito "sujos": t1-1, T1 - 2, t01_3...
            estilo = k % 3
            id_laudo = (f't1-{k}' if estilo == 0 else
                        f'T1 - {k}' if estilo == 1 else f't01_{k}')
            linhas_laudo.append({'Amostra': id_laudo,
                                 'P (mg/dm3)': str(p).replace('.', ','),
                                 'V (%)': str(v).replace('.', ',')})
    (saida / 'pontos.geojson').write_text(_json.dumps(
        {'type': 'FeatureCollection', 'features': feicoes}), encoding='utf-8')
    with open(saida / 'laudo.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['Amostra', 'P (mg/dm3)', 'V (%)'],
                           delimiter=';')
        w.writeheader()
        w.writerows(linhas_laudo)

    print('— demo: etapa 1 (casamento) —')
    codigo = principal(['--perimetro', str(saida / 'perimetro.geojson'),
                        '--pontos', str(saida / 'pontos.geojson'),
                        '--laudo', str(saida / 'laudo.csv'),
                        '--so-casamento', '--saida', str(saida)])
    assert codigo == 0
    print('\n— demo: etapa 2 (interpolação) —')
    return principal(['--perimetro', str(saida / 'perimetro.geojson'),
                      '--pontos', str(saida / 'pontos.geojson'),
                      '--laudo', str(saida / 'laudo.csv'),
                      '--elementos', 'todos', '--saida', str(saida)])


if __name__ == '__main__':
    sys.exit(principal())
