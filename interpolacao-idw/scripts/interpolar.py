"""Pipeline completo: perímetro + pontos + laudo → mapas de fertilidade por IDW,
em classes, com a apostila em PDF.

Uso típico (sempre em duas etapas — conferir primeiro, interpolar depois):

  1) python interpolar.py --perimetro talhao.kml --pontos amostras.shp \
       --laudo laudo.csv --tabela mg --so-casamento --saida ./saida
     → revise com o usuário o casamento dos IDs (saida/casamento.csv) e as
       classes propostas para cada coluna (qual quadro, que unidade, o que
       ficou sem tabela e por quê).

  2) python interpolar.py --perimetro talhao.kml --pontos amostras.shp \
       --laudo laudo.csv --tabela mg --elementos "K (mg/dm3),V (%)" \
       --fazenda "Fazenda Exemplo" --saida ./saida
     → por elemento: interpola por IDW (potência 2, pixel 5 m), mede o erro
       por validação cruzada, classifica e grava <elemento>.tif (valores),
       <elemento>.pdf e <elemento>.png (mapa em classes com ha e %).
       No fim: apostila.pdf (capa, resumo e um mapa por página),
       resumo_classes.csv e relatorio.json.

Laudo: CSV com uma linha por amostra e a UNIDADE no cabeçalho de cada coluna
(ex.: "K (mg/dm3)") — sem a unidade não há classe oficial. Decimais com vírgula
e valores "<0,1" (metade do limite) são tratados.
"""

import argparse
import csv
import datetime
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

import casamento  # noqa: E402
import classes  # noqa: E402
import geometria  # noqa: E402
import idw  # noqa: E402
import mapa  # noqa: E402
from raster import escrever_geotiff  # noqa: E402

GRUPOS_SP = ('florestais', 'perenes', 'anuais', 'hortalicas')


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


def unidade_bonita(unidade):
    """'mg/dm3' → 'mg/dm³' (só para exibir; os cálculos usam a forma simples)."""
    return unidade.replace('dm3', 'dm³').replace('cm3', 'cm³') if unidade else unidade


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
        'sugestoes_para_os_sem_par': ctx.get('sugestoes', {}),
        'duplicados_laudo': ctx['duplicados_laudo'],
    }
    if ctx['duplicados_laudo']:
        resumo['atencao'] = ('o laudo tem ids repetidos (profundidades?) — '
                             'escolha uma com --filtro-laudo, ex.: --filtro-laudo "0-20"')
    return resumo


# ------------------------------------------------------------------ classes
def _mapa_de_opcoes(itens, nome):
    """['K (mg/dm3)=k', ...] → {'K (mg/dm3)': 'k'}; o '=' final separa coluna e valor."""
    saida = {}
    for item in itens or []:
        coluna, sep, valor = item.rpartition('=')
        if not sep or not coluna.strip():
            raise SystemExit(f'{nome} no formato "COLUNA=valor" (recebido: {item!r})')
        saida[coluna.strip()] = valor.strip()
    return saida


def auxiliares(ctx, args, numericas):
    """Quais colunas servem de argila e de P-rem para as classes de P e S de MG."""
    col_argila = args.argila or next(
        (c for c in numericas if classes.chave_da_coluna(c)[0] == 'argila'), None)
    col_prem = args.prem or next(
        (c for c in numericas if classes.chave_da_coluna(c)[0] == 'prem'), None)
    avisos = []
    fator_argila = None
    if col_argila and args.argila_fixa is None:
        unidade = classes.separar_cabecalho(col_argila)[1]
        fator_argila = classes.fator_de_unidade('%', unidade, 'argila')
        if fator_argila is None:
            avisos.append(f'{col_argila}: sem unidade (% ou g/kg) no cabeçalho — não serve '
                          'para as classes de P por argila')
            col_argila = None
    return {
        'col_argila': col_argila, 'fator_argila': fator_argila, 'col_prem': col_prem,
        'tem_argila': args.argila_fixa is not None or bool(col_argila),
        'tem_prem': args.prem_fixo is not None or bool(col_prem),
        'avisos': avisos,
    }


def plano_de_classes(colunas, args, aux):
    """Como cada coluna pedida será classificada (o que o usuário confere antes)."""
    forcadas = _mapa_de_opcoes(args.classe, '--classe')
    limites = {c: [v for v in re.split(r'[;,\s]+', t) if v]
               for c, t in _mapa_de_opcoes(args.limites, '--limites').items()}
    nomes = {c: [n.strip() for n in t.split('|')]
             for c, t in _mapa_de_opcoes(args.nomes, '--nomes').items()}
    sentidos = _mapa_de_opcoes(args.sentido, '--sentido')
    plano = {}
    for c in colunas:
        plano[c] = classes.resolver(
            c, tabela=args.tabela, chave=forcadas.get(c), limites=limites.get(c),
            nomes=nomes.get(c), sentido=sentidos.get(c), grupo_cultura=args.grupo_cultura,
            tem_argila=aux['tem_argila'], tem_prem=aux['tem_prem'])
    return plano


def resumo_do_plano(plano):
    linhas = []
    for c, spec in plano.items():
        if spec['modo'] == 'limites':
            como = ' | '.join(
                f'{n}: {f}' for n, f in zip(spec.get('nomes') or [''] * 99,
                                            classes.rotulos_de_faixa(spec['limites'])))
        elif spec['modo'] == 'por_faixa':
            como = f'limites variam com {spec["auxiliar"]} de cada pixel'
        else:
            como = 'classes livres (sem tabela oficial)'
        linhas.append({'coluna': c, 'unidade': spec['unidade'], 'fonte': spec.get('fonte'),
                       'classes': como, 'avisos': spec['avisos']})
    return linhas


# -------------------------------------------------------------- interpolação
def valores_do_elemento(ctx, coluna, args):
    valor_por_laudo, censurados = {}, 0
    for ln in ctx['linhas']:
        chave = str(ln.get(ctx['col_laudo'], ''))
        v, menor = numero_br(ln.get(coluna, ''))
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
    x, y, z, n_dup = idw.remover_duplicados(np.array(xs), np.array(ys), np.array(zs))
    return x, y, z, n_dup, censurados


def superficie(ctx, coluna, args, grade, cache):
    """IDW de uma coluna do laudo. Devolve dict (ou {'erro': ...}); guarda no cache
    porque argila e P-rem podem ser pedidos de novo como apoio das classes."""
    if coluna in cache:
        return cache[coluna]
    x, y, z, n_dup, censurados = valores_do_elemento(ctx, coluna, args)
    n = len(z)
    if n < 5:
        cache[coluna] = {'erro': f'só {n} pontos com valor válido (mínimo 5; confira o '
                                 'casamento e o --min-confianca)'}
        return cache[coluna]

    escolha = idw.escolher_potencia(x, y, z, args.vizinhos, args.raio)
    automatica = args.potencia == 'auto'
    potencia = escolha['vencedora'] if automatica else float(args.potencia)
    if not automatica:
        rmse, _, _ = idw.validacao_loo(x, y, z, potencia, args.vizinhos, args.raio)
        ganho = 1 - rmse / escolha['rmse_da_media'] if escolha['rmse_da_media'] else 0.0
        escolha.update({'rmse_loo': rmse, 'ganho_sobre_a_media': round(ganho, 3),
                        'estrutura_fraca': bool(ganho < 0.05)})
    escolha.update({'potencia_usada': potencia, 'automatica': automatica})

    _, _, _, _, mascara, xc, yc = grade
    print(f'  {coluna}: potência {potencia:g}, interpolando {int(mascara.sum()):,} células…',
          flush=True)
    malha = idw.interpolar_grade(x, y, z, potencia, xc, yc, mascara, args.vizinhos, args.raio)

    avisos = []
    melhor = escolha['potencias'][f'{escolha["vencedora"]:g}']['rmse_loo']
    if not automatica and escolha['rmse_loo'] > 1.05 * melhor:
        avisos.append(f'na validação cruzada a potência {escolha["vencedora"]:g} erra '
                      f'{1 - melhor / escolha["rmse_loo"]:.0%} menos que a {potencia:g} usada; '
                      'para adotá-la, --potencia auto')
    if automatica and potencia >= max(idw.POTENCIAS):
        avisos.append(f'a potência {potencia:g} venceu no teto testado: o mapa fica perto do '
                      '"vizinho mais próximo", com manchas em volta de cada amostra. Para um '
                      'mapa mais suave, compare com --potencia 2 (o RMSE de cada potência está '
                      'no relatorio.json)')
    if n < 15:
        avisos.append(f'n={n} é pouco: o mapa é só um esboço da variação')
    if escolha['estrutura_fraca']:
        avisos.append('na validação cruzada o IDW não previu melhor que a média do talhão — '
                      'a malha não captou padrão espacial; o mapa pouco difere da média')
    if censurados:
        avisos.append(f'{censurados} valores "<LD" entraram como metade do limite')
    if n_dup:
        avisos.append(f'{n_dup} pontos em coordenada repetida (média)')
    sem_vizinho = int(np.isnan(malha[mascara]).sum())
    if sem_vizinho:
        avisos.append(f'{sem_vizinho} células sem amostra dentro do raio de {args.raio:g} m '
                      '(ficaram vazias)')
    cache[coluna] = {'malha': malha, 'x': x, 'y': y, 'z': z, 'n': n, 'idw': escolha,
                     'avisos': avisos}
    return cache[coluna]


def superficie_auxiliar(spec, ctx, args, grade, cache, aux):
    """Argila (em %) ou P-rem (mg/L) de cada pixel, para as classes que dependem deles."""
    if spec['auxiliar'] == 'argila':
        if args.argila_fixa is not None:
            return float(args.argila_fixa), f'argila única de {classes.num_br(args.argila_fixa)}%'
        s = superficie(ctx, aux['col_argila'], args, grade, cache)
        if 'erro' in s:
            return None, s['erro']
        return s['malha'] / aux['fator_argila'], f'argila de cada pixel ({aux["col_argila"]})'
    if args.prem_fixo is not None:
        return float(args.prem_fixo), f'P-rem único de {classes.num_br(args.prem_fixo)} mg/L'
    s = superficie(ctx, aux['col_prem'], args, grade, cache)
    if 'erro' in s:
        return None, s['erro']
    return s['malha'], f'P-rem de cada pixel ({aux["col_prem"]})'


def processar_elemento(ctx, coluna, spec, args, grade, cache, aux, saida, data):
    """Interpola, classifica e grava os arquivos de UM elemento."""
    s = superficie(ctx, coluna, args, grade, cache)
    if 'erro' in s:
        return {'elemento': coluna, 'erro': s['erro']}
    x0, y0, _, _, mascara, _, _ = grade
    malha, avisos = s['malha'], list(s['avisos']) + list(spec['avisos'])

    observacao, auxiliar = None, None
    if spec['modo'] == 'por_faixa':
        auxiliar, como = superficie_auxiliar(spec, ctx, args, grade, cache, aux)
        if auxiliar is None:
            avisos.append(f'classes oficiais indisponíveis ({como}) — classes livres')
            spec = {**spec, 'modo': 'livre', 'fonte': None, 'sentido': 'neutra'}
        else:
            observacao = f'Os limites de cada classe variam com a {como}.'

    indices, limites, nomes = classes.classificar(
        malha, spec, auxiliar, args.classes_livres, args.n_classes)
    n_classes = len(nomes) if nomes else len(limites or []) + 1
    ha_por_celula = args.pixel ** 2 / 10000
    areas = [float((indices == i).sum() * ha_por_celula) for i in range(n_classes)]

    nome = slug(coluna)
    escrever_geotiff(saida / f'{nome}.tif', malha, x0, y0, args.pixel, ctx['epsg'])
    arquivos = [f'{nome}.tif']
    if args.tif_classes:
        em_classes = np.where(indices >= 0, indices + 1.0, np.nan)
        escrever_geotiff(saida / f'{nome}-classes.tif', em_classes, x0, y0, args.pixel, ctx['epsg'])
        arquivos.append(f'{nome}-classes.tif')

    e = s['idw']
    origem = ' (validação cruzada)' if e['automatica'] else ''
    metodo = [f'IDW · potência {classes.num_br(e["potencia_usada"])}{origem} · '
              f'{args.vizinhos} vizinhos · pixel {classes.num_br(args.pixel)} m',
              f'RMSE da validação cruzada: {classes.num_br(e["rmse_loo"])} · ganho sobre '
              f'a média: {e["ganho_sobre_a_media"]:.0%}'.replace('.', ',')]
    if e['estrutura_fraca']:
        metodo.append('Atenção: o mapa pouco difere da média do talhão.')
    fonte = spec.get('fonte')
    if fonte and spec.get('pressupoe'):
        fonte += f' · pressupõe {spec["pressupoe"]}'
    unidade = unidade_bonita(spec['unidade'])
    curto = spec.get('rotulo') or spec['nome'] or coluna
    titulo = f'{curto} ({unidade})' if unidade else curto
    validos = malha[np.isfinite(malha)]
    estat = {'n': s['n'],
             'mapa': (float(validos.min()), float(validos.mean()), float(validos.max())),
             'amostras': (float(s['z'].min()), float(s['z'].mean()), float(s['z'].max()))}
    pagina = {
        'indices': indices, 'x_oeste': x0, 'y_norte': y0, 'pixel': args.pixel,
        'aneis_utm': ctx['aneis_utm'],
        'pontos_xy': None if args.sem_pontos else list(zip(s['x'].tolist(), s['y'].tolist())),
        'titulo': titulo,
        'subtitulo': ' · '.join(t for t in (args.fazenda, args.camada or args.filtro_laudo) if t),
        'unidade': unidade, 'nomes': nomes, 'limites': limites,
        'sentido': spec['sentido'], 'areas_ha': areas, 'estat': estat, 'metodo': metodo,
        'fonte': fonte, 'observacao': observacao, 'logo': args.logo, 'data': data,
        'referencia': f'SIRGAS 2000 / UTM {ctx["zona"]} (EPSG {ctx["epsg"]})',
    }
    fig = mapa.pagina_mapa(pagina)
    fig.savefig(saida / f'{nome}.pdf')
    fig.savefig(saida / f'{nome}.png', dpi=150)
    mapa.plt.close(fig)
    arquivos += [f'{nome}.pdf', f'{nome}.png']

    rotulos = (classes.rotulos_de_faixa(limites) if limites is not None
               else ['conforme o pixel'] * n_classes)
    total = sum(areas) or 1.0
    maior = int(np.argmax(areas))
    return {
        'elemento': coluna, 'n': s['n'], 'min': estat['mapa'][0], 'media': estat['mapa'][1],
        'max': estat['mapa'][2], 'amostras': dict(zip(('min', 'media', 'max'), estat['amostras'])),
        'idw': e, 'unidade': unidade, 'nome_curto': curto,
        'classes': {'modo': spec['modo'], 'fonte': fonte,
                    'linhas': [{'classe': nomes[i] if nomes else rotulos[i], 'faixa': rotulos[i],
                                'area_ha': round(areas[i], 2),
                                'pct': round(100 * areas[i] / total, 1)}
                               for i in range(n_classes)]},
        'predominante': f'{nomes[maior] if nomes else rotulos[maior]} '
                        f'({classes.num_br(100 * areas[maior] / total, 1)}%)',
        'arquivos': arquivos, 'avisos': avisos, '_pagina': pagina,
    }


def montar_apostila(blocos, ctx, args, grade, saida, data):
    from matplotlib.backends.backend_pdf import PdfPages

    mascara = grade[4]
    area = float(mascara.sum() * args.pixel ** 2 / 10000)
    tabela = (classes.TABELAS[args.tabela]['nome'] if args.tabela in classes.TABELAS
              else 'sem tabela oficial (classes livres ou do usuário)')
    capa = {
        'titulo': args.titulo, 'fazenda': args.fazenda, 'cliente': args.cliente,
        'responsavel': args.responsavel, 'logo': args.logo, 'data': data,
        'linhas': [('Área mapeada', f'{classes.num_br(area, 1)} ha'),
                   ('Amostras', str(len(ctx['pares']))),
                   ('Camada', args.camada or args.filtro_laudo or '—'),
                   ('Mapas', str(len(blocos))),
                   ('Classes', tabela),
                   ('Interpolação', f'IDW, pixel de {classes.num_br(args.pixel)} m'),
                   ('Referência', f'SIRGAS 2000 / UTM {ctx["zona"]} (EPSG {ctx["epsg"]})')],
    }
    por_pagina = 22
    n_resumo = -(-len(blocos) // por_pagina)
    linhas = [{'elemento': b['nome_curto'], 'unidade': b['unidade'], 'n': b['n'], 'min': b['min'],
               'media': b['media'], 'max': b['max'], 'predominante': b['predominante'],
               'pagina': 2 + n_resumo + i} for i, b in enumerate(blocos)]
    with PdfPages(saida / 'apostila.pdf') as pdf:
        for fig in [mapa.pagina_capa(capa), *mapa.paginas_resumo(linhas, args.logo, data, por_pagina)]:
            pdf.savefig(fig)
            mapa.plt.close(fig)
        for b in blocos:
            fig = mapa.pagina_mapa(b['_pagina'])
            pdf.savefig(fig)
            mapa.plt.close(fig)


def principal(argv=None):
    p = argparse.ArgumentParser(description='Mapas por IDW de dados pontuais, em classes, com apostila')
    p.add_argument('--perimetro', help='talhão: .kml/.geojson/.shp/.wkt')
    p.add_argument('--pontos', help='amostras: .shp/.geojson/.kml/.csv')
    p.add_argument('--laudo', help='CSV do laudo (uma linha por amostra, unidade no cabeçalho)')
    p.add_argument('--elementos', default='', help='"K (mg/dm3),V (%%)" ou "todos"')
    p.add_argument('--saida', default='./saida-idw')
    p.add_argument('--pixel', type=float, default=5.0)
    p.add_argument('--zona', help='zona UTM se as coordenadas vierem em metros sem .prj (ex.: 22S)')
    p.add_argument('--filtro-laudo', help='usa só linhas do laudo contendo o texto (ex.: "0-20")')
    p.add_argument('--id-pontos', help='atributo de ID no shape (senão: detecta)')
    p.add_argument('--id-laudo', help='coluna de ID no laudo (senão: detecta)')
    p.add_argument('--min-confianca', type=float, default=0.85,
                   help='pares abaixo disso ficam fora (confirme-os com --par)')
    p.add_argument('--par', action='append', metavar='PONTO=LAUDO',
                   help='casamento manual confirmado pelo usuário (repetível)')
    # IDW
    p.add_argument('--potencia', default='2',
                   help='2 (padrão, o usual) · outro número · auto (escolhe por validação cruzada)')
    p.add_argument('--vizinhos', type=int, default=12, help='amostras usadas em cada célula')
    p.add_argument('--raio', type=float, help='raio máximo de busca em metros (padrão: sem limite)')
    # classes
    p.add_argument('--tabela', choices=['mg', 'sp', 'nenhuma'], default='nenhuma',
                   help='mg = 5ª Aproximação · sp = Boletim 100 · nenhuma = classes livres')
    p.add_argument('--grupo-cultura', choices=GRUPOS_SP,
                   help='grupo de culturas para o P do Boletim 100')
    p.add_argument('--classe', action='append', metavar='COLUNA=ITEM',
                   help='força o item da tabela (k, p, ph…) ou "nenhuma" (repetível)')
    p.add_argument('--limites', action='append', metavar='COLUNA=a,b,c',
                   help='limites próprios do usuário, na unidade da coluna (repetível)')
    p.add_argument('--nomes', action='append', metavar='COLUNA=n1|n2|n3',
                   help='nomes das classes dos --limites (um a mais que os limites)')
    p.add_argument('--sentido', action='append', metavar='COLUNA=alto_bom|alto_ruim|neutra',
                   help='cores: alto é bom (verde), alto é ruim (vermelho) ou neutra')
    p.add_argument('--argila', help='coluna de argila para o P de MG (senão: detecta)')
    p.add_argument('--argila-fixa', type=float, help='argila única da área, em %%')
    p.add_argument('--prem', help='coluna de P-rem para P e S de MG (senão: detecta)')
    p.add_argument('--prem-fixo', type=float, help='P-rem único da área, em mg/L')
    p.add_argument('--classes-livres', choices=['intervalos', 'quantis'], default='intervalos',
                   help='colunas sem tabela: intervalos iguais ou quantis')
    p.add_argument('--n-classes', type=int, default=5, help='nº de classes livres')
    # apresentação
    p.add_argument('--titulo', help='título da capa (padrão: "Mapas de fertilidade do solo" com tabela\n'
                                    'de MG ou SP; senão, "Mapas interpolados")')
    p.add_argument('--fazenda', help='nome da fazenda ou do talhão (capa e subtítulos)')
    p.add_argument('--cliente', help='produtor ou empresa (capa)')
    p.add_argument('--responsavel', help='responsável técnico (rodapé da capa)')
    p.add_argument('--camada', help='camada amostrada, ex.: "0–20 cm" (subtítulo)')
    p.add_argument('--logo', help='imagem PNG/JPG para o canto superior direito')
    p.add_argument('--data', help='data nas páginas (padrão: hoje)')
    p.add_argument('--sem-pontos', action='store_true', help='não desenha as amostras no mapa')
    p.add_argument('--sem-apostila', action='store_true', help='não monta a apostila.pdf')
    p.add_argument('--tif-classes', action='store_true',
                   help='grava também <elemento>-classes.tif (1 = primeira classe)')
    p.add_argument('--so-casamento', action='store_true',
                   help='só casa os IDs e mostra as classes propostas (etapa 1)')
    p.add_argument('--demo', action='store_true', help='roda um exemplo sintético completo')
    args = p.parse_args(argv)

    if args.demo:
        return _demo(args)
    if not (args.perimetro and args.pontos and args.laudo):
        p.error('--perimetro, --pontos e --laudo são obrigatórios (ou use --demo)')
    if args.potencia != 'auto':
        try:
            if not 0 < float(args.potencia) <= 10:
                raise ValueError
        except ValueError:
            p.error('--potencia: "auto" ou um número entre 0 e 10')
    if args.vizinhos < 1 or args.pixel <= 0:
        p.error('--vizinhos e --pixel precisam ser positivos')
    if not args.titulo:
        args.titulo = ('Mapas de fertilidade do solo' if args.tabela in classes.TABELAS
                       else 'Mapas interpolados')

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    ctx = etapa_casamento(args, saida)
    resumo = resumo_casamento(ctx)

    numericas = colunas_numericas(ctx['linhas'], ctx['colunas'], ctx['col_laudo'])
    if args.elementos.strip().lower() in ('', 'todos'):
        pedidos = numericas
    else:
        pedidos = [e.strip() for e in args.elementos.split(',') if e.strip()]
        fora = [e for e in pedidos if e not in ctx['colunas']]
        if fora:
            raise SystemExit(f'elementos fora do laudo: {fora} — colunas: {ctx["colunas"]}')
    aux = auxiliares(ctx, args, numericas)
    plano = plano_de_classes(pedidos, args, aux)

    if args.so_casamento:
        resumo['colunas_numericas'] = numericas
        resumo['classes_propostas'] = resumo_do_plano(plano)
        resumo['avisos_de_apoio'] = aux['avisos']
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
        return 0

    data = args.data or datetime.date.today().strftime('%d/%m/%Y')
    grade = geometria.grade_e_mascara(ctx['aneis_utm'], pixel=args.pixel)
    cache, blocos = {}, []
    relatorio = {'casamento': resumo, 'pixel_m': args.pixel, 'tabela': args.tabela,
                 'area_ha': round(float(grade[4].sum() * args.pixel ** 2 / 10000), 2),
                 'elementos': []}
    for coluna in pedidos:
        bloco = processar_elemento(ctx, coluna, plano[coluna], args, grade, cache, aux, saida, data)
        if 'erro' in bloco:
            print(f'✗ {coluna}: {bloco["erro"]}')
        else:
            blocos.append(bloco)
            print(f'✓ {coluna}: potência {bloco["idw"]["potencia_usada"]:g} '
                  f'(RMSE {bloco["idw"]["rmse_loo"]:.3g}, ganho '
                  f'{bloco["idw"]["ganho_sobre_a_media"]:.0%}), n={bloco["n"]} → '
                  f'{", ".join(bloco["arquivos"])}')
            for a in bloco['avisos']:
                print(f'  · {a}')
        relatorio['elementos'].append({k: v for k, v in bloco.items() if k != '_pagina'})

    if blocos:
        with open(saida / 'resumo_classes.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['elemento', 'unidade', 'classe', 'faixa', 'area_ha', 'pct'])
            for b in blocos:
                for ln in b['classes']['linhas']:
                    w.writerow([b['elemento'], b['unidade'] or '', ln['classe'], ln['faixa'],
                                classes.num_br(ln['area_ha'], 2), classes.num_br(ln['pct'], 1)])
        if not args.sem_apostila:
            montar_apostila(blocos, ctx, args, grade, saida, data)
            relatorio['apostila'] = 'apostila.pdf'
            print(f'apostila: {saida / "apostila.pdf"} ({len(blocos)} mapas)')

    with open(saida / 'relatorio.json', 'w', encoding='utf-8') as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)
    print(f'relatório completo: {saida / "relatorio.json"}')
    return 0 if blocos else 1


def _demo(args):
    """Exemplo sintético completo: gera arquivos, roda o pipeline, confere."""
    saida = Path(args.saida) if args.saida != './saida-idw' else Path('./demo-idw')
    saida.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)

    # talhão ~28 ha perto de Lavras-MG e 36 pontos em grade perturbada
    lon0, lat0 = -45.00, -21.25
    dlon, dlat = 0.0060, 0.0045
    anel = [(lon0, lat0), (lon0 + dlon, lat0 + 0.0004), (lon0 + dlon, lat0 + dlat),
            (lon0 + dlon / 2, lat0 + dlat + 0.0006), (lon0, lat0 + dlat), (lon0, lat0)]
    (saida / 'perimetro.geojson').write_text(json.dumps({
        'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {},
            'geometry': {'type': 'Polygon', 'coordinates': [[list(p) for p in anel]]}}]}),
        encoding='utf-8')

    feicoes, linhas_laudo = [], []
    colunas = ['Amostra', 'K (mg/dm3)', 'P Mehlich (mg/dm3)', 'Argila (g/kg)', 'V (%)', 'Areia']
    k = 0
    for i in range(6):
        for j in range(6):
            k += 1
            lon = lon0 + (i + 0.5) / 6 * dlon + rng.normal(0, 0.00012)
            lat = lat0 + (j + 0.5) / 6 * dlat + rng.normal(0, 0.00012)
            potassio = 65 + 45 * np.sin(i / 1.6) + 30 * np.cos(j / 1.2) + rng.normal(0, 4)
            fosforo = 9 + 6 * np.cos(i / 1.9) + 3 * np.sin(j / 1.5) + rng.normal(0, 0.6)
            argila = 250 + 70 * i + rng.normal(0, 15)          # 250 a 600 g/kg, de oeste a leste
            v = 48 + 14 * np.cos(i / 1.9) + 8 * np.sin(j / 1.5) + rng.normal(0, 2.5)
            feicoes.append({'type': 'Feature', 'properties': {'plot_id': f'T01-{k:02d}'},
                            'geometry': {'type': 'Point', 'coordinates': [lon, lat]}})
            estilo = k % 3  # ids do laudo "sujos" de propósito: t1-1, T1 - 2, t01_3…
            id_laudo = (f't1-{k}' if estilo == 0 else f'T1 - {k}' if estilo == 1 else f't01_{k}')
            linha = [id_laudo] + [f'{v_:.1f}'.replace('.', ',')
                                  for v_ in (max(potassio, 3), max(fosforo, 0.5), argila, v,
                                             1000 - argila - 80)]
            linhas_laudo.append(dict(zip(colunas, linha)))
    (saida / 'pontos.geojson').write_text(json.dumps(
        {'type': 'FeatureCollection', 'features': feicoes}), encoding='utf-8')
    with open(saida / 'laudo.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=colunas, delimiter=';')
        w.writeheader()
        w.writerows(linhas_laudo)

    comuns = ['--perimetro', str(saida / 'perimetro.geojson'),
              '--pontos', str(saida / 'pontos.geojson'),
              '--laudo', str(saida / 'laudo.csv'), '--tabela', 'mg', '--saida', str(saida)]
    print('— demo: etapa 1 (casamento e classes propostas) —')
    assert principal([*comuns, '--so-casamento']) == 0
    print('\n— demo: etapa 2 (interpolação, classes e apostila) —')
    codigo = principal([*comuns, '--elementos', 'todos', '--fazenda', 'Fazenda Demonstração',
                        '--camada', '0–20 cm'])
    assert all(e['idw']['potencia_usada'] == 2.0 and not e['idw']['automatica']
               for e in json.loads((saida / 'relatorio.json').read_text(encoding='utf-8'))['elementos'])
    rel = json.loads((saida / 'relatorio.json').read_text(encoding='utf-8'))
    por_nome = {e['elemento']: e for e in rel['elementos']}
    for e in rel['elementos']:
        total = sum(ln['area_ha'] for ln in e['classes']['linhas'])
        assert abs(total - rel['area_ha']) < 0.05, (e['elemento'], total, rel['area_ha'])
    assert por_nome['K (mg/dm3)']['classes']['modo'] == 'limites'
    assert por_nome['P Mehlich (mg/dm3)']['classes']['modo'] == 'por_faixa'
    assert por_nome['Areia']['classes']['modo'] == 'livre'      # sem unidade nem tabela
    assert (saida / 'apostila.pdf').stat().st_size > 20000
    print(f'demo OK: {len(rel["elementos"])} mapas, {rel["area_ha"]} ha, áreas por classe fecham')
    return codigo


if __name__ == '__main__':
    sys.exit(principal())
