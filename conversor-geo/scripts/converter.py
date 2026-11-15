#!/usr/bin/env python3
"""conversor-geo: converte arquivos geográficos de um formato para outro.

Formatos: Shapefile (zip ou .shp com os irmãos), KML, KMZ, GeoJSON, GPX, CSV e
WKT. Também reprojeta (graus <-> UTM), mede a área em hectares, une talhões e
conserta o que é seguro na geometria.

Uso:
  python converter.py <arquivo> --listar
  python converter.py <arquivo> --para geojson|kml|kmz|shp|gpx|csv|wkt [opções]
  python converter.py <arquivo> --para-sat           (GeoJSON em graus, para colar na ClaudIA Sat)
  python converter.py --demo --saida demo            (fazenda inventada, todos os formatos)

Sempre rode --listar primeiro e mostre ao usuário o que o arquivo tem.
"""

import argparse
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import conserto
import geom
import kml_gpx
import projecao
import shapefile
import sintetico
import texto
import uniao

EXTENSOES = {'.shp': 'shp', '.dbf': 'shp', '.shx': 'shp', '.zip': 'zip', '.kml': 'kml', '.kmz': 'kmz', '.geojson': 'geojson',
             '.json': 'geojson', '.gpx': 'gpx', '.csv': 'csv', '.tsv': 'csv', '.txt': 'txt', '.wkt': 'wkt'}
NOMES = {'shp': 'Shapefile', 'kml': 'KML', 'kmz': 'KMZ', 'geojson': 'GeoJSON', 'gpx': 'GPX', 'csv': 'CSV', 'wkt': 'WKT'}
SO = {'pontos': 'ponto', 'linhas': 'linha', 'poligonos': 'polígono', 'polígonos': 'polígono'}


class Parou(Exception):
    """A conversão não segue: falta uma resposta do usuário, ou o arquivo foi recusado."""


def num(v, casas=2):
    return f'{v:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def limpo(nome):
    s = unicodedata.normalize('NFKD', str(nome))
    s = re.sub(r'[^A-Za-z0-9_-]+', '_', ''.join(c for c in s if not unicodedata.combining(c))).strip('_')
    return s or 'camada'


# ---------------------------------------------------------------- leitura

def _camada(nome, formato, bruto):
    return {'nome': nome, 'formato': formato, 'feicoes': bruto['feicoes'], 'campos': list(bruto['campos']),
            'avisos': list(bruto.get('avisos', [])), 'prj': bruto.get('prj'), 'epsg': bruto.get('epsg'), 'codificacao': bruto.get('codificacao')}


def _ler_bytes(nome, formato, dados, args):
    if formato == 'txt':
        cabeca = texto.decodificar(dados[:400])
        formato = 'wkt' if re.match(r'\s*(SRID\s*=|POINT|LINESTRING|POLYGON|MULTI|GEOMETRYCOLLECTION)', cabeca, re.I) else 'csv'
    if formato == 'kml':
        return _camada(nome, 'kml', kml_gpx.ler_kml(dados))
    if formato == 'kmz':
        return _camada(nome, 'kmz', kml_gpx.ler_kmz(dados))
    if formato == 'gpx':
        return _camada(nome, 'gpx', kml_gpx.ler_gpx(dados))
    if formato == 'geojson':
        return _camada(nome, 'geojson', texto.ler_geojson(dados))
    if formato == 'wkt':
        return _camada(nome, 'wkt', texto.ler_wkt(dados))
    if formato == 'csv':
        return _camada(nome, 'csv', texto.ler_csv(dados, args.x, args.y, args.wkt))
    raise Parou(f'formato "{formato}" não é lido')


def ler_entrada(caminho, args):
    """Devolve a lista de camadas do arquivo (um zip pode trazer várias)."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise Parou(f'arquivo não encontrado: {caminho}')
    formato = EXTENSOES.get(caminho.suffix.lower())
    if formato is None:
        raise Parou(f'extensão "{caminho.suffix}" não reconhecida. A skill lê: .zip (shapefile), .shp, .kml, .kmz, .geojson, .json, .gpx, .csv, .txt e .wkt')
    if formato == 'shp':
        partes = {}
        for irmao in caminho.parent.iterdir():
            if irmao.stem.lower() == caminho.stem.lower() and irmao.suffix.lower()[1:] in ('shp', 'shx', 'dbf', 'prj', 'cpg'):
                partes[irmao.suffix.lower()[1:]] = irmao.read_bytes()
        if 'shp' not in partes:
            raise Parou(f'não achei o arquivo {caminho.stem}.shp na mesma pasta')
        return [_camada(caminho.stem, 'shp', shapefile.ler(partes))]
    dados = caminho.read_bytes()
    if not dados.strip():
        raise Parou(f'o arquivo {caminho.name} está vazio')
    if formato != 'zip':
        return [_ler_bytes(caminho.stem, formato, dados, args)]
    membros = kml_gpx.ler_do_zip(dados, {'shp', 'shx', 'dbf', 'prj', 'cpg', 'kml', 'geojson', 'json', 'gpx', 'csv', 'wkt'})
    grupos, camadas = {}, []
    for nome, conteudo in membros.items():
        base, ext = nome.rsplit('.', 1)
        if ext.lower() in ('shp', 'shx', 'dbf', 'prj', 'cpg'):
            grupos.setdefault(base.lower(), {'_nome': base.split('/')[-1]})[ext.lower()] = conteudo
    for g in grupos.values():
        if 'shp' in g:
            camadas.append(_camada(g['_nome'], 'shp', shapefile.ler(g)))
    for nome, conteudo in membros.items():
        base, ext = nome.rsplit('.', 1)
        if ext.lower() in ('kml', 'geojson', 'json', 'gpx', 'csv', 'wkt') and conteudo.strip():
            try:
                camadas.append(_ler_bytes(base.split('/')[-1], EXTENSOES['.' + ext.lower()], conteudo, args))
            except (ValueError, projecao.SrcAmbiguo) as e:
                if ext.lower() != 'json':
                    raise Parou(f'{nome}: {e}')
    if not camadas:
        raise Parou('o zip não tem nenhum arquivo geográfico que a skill leia (shapefile, KML, GeoJSON, GPX, CSV ou WKT)')
    return camadas


def _coordenadas(feicoes):
    xs = [p[0] for f in feicoes if f['geometry'] for s in geom.partes(f['geometry']) for p in s]
    ys = [p[1] for f in feicoes if f['geometry'] for s in geom.partes(f['geometry']) for p in s]
    return xs, ys


def resolver_src(camada, args):
    """O SRC da camada. Levanta SrcAmbiguo (falta perguntar) ou SrcRecusado (não é convertido)."""
    if camada['formato'] in ('kml', 'kmz', 'gpx'):
        return projecao.geo('WGS 84', 'o formato é sempre em graus (WGS 84)')
    if args.src_entrada:
        src = projecao.src_informado(args.src_entrada)
        src['origem'] = 'informado pelo usuário'
        return src
    if camada.get('prj'):
        return projecao.src_do_prj(camada['prj'])
    if camada.get('epsg'):
        return projecao.src_do_epsg(camada['epsg'], 'declarado no arquivo')
    xs, ys = _coordenadas(camada['feicoes'])
    src = projecao.deduzir(xs, ys)
    if camada['formato'] == 'shp':
        src['origem'] = 'deduzido das coordenadas (parecem graus): o shapefile veio sem o .prj'
    return src


def _centro_em_graus(feicoes, src):
    c = geom.caixa(feicoes)
    x, y = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
    if src['tipo'] == 'utm':
        lon, lat = projecao.utm_inversa([x], [y], src['zona'], src['sul'], src['datum'])
        return float(lon[0]), float(lat[0])
    return x, y


def trocar_xy(feicoes):
    return [{'geometry': geom.mapear(f['geometry'], lambda xs, ys: (ys, xs)) if f['geometry'] else None, 'properties': f['properties']} for f in feicoes]


# ---------------------------------------------------------------- inspeção

def _exemplos(feicoes, campo, n=3):
    vistos = []
    for f in feicoes:
        v = f['properties'].get(campo)
        if v not in (None, '') and str(v) not in vistos:
            vistos.append(str(v))
            if len(vistos) == n:
                break
    return vistos


def _tipo_do_campo(feicoes, campo):
    valores = [f['properties'].get(campo) for f in feicoes if f['properties'].get(campo) not in (None, '')]
    if not valores:
        return 'vazio'
    if all(isinstance(v, bool) for v in valores):
        return 'sim/não'
    return 'número' if all(shapefile._eh_numero(v) for v in valores) else 'texto'


def listar(camada, args, sai=print):
    """Mostra o que o arquivo tem. Não converte nem altera nada."""
    fs = camada['feicoes']
    com_geo = [f for f in fs if f['geometry']]
    contagem = {}
    for f in com_geo:
        contagem[geom.familia(f['geometry'])] = contagem.get(geom.familia(f['geometry']), 0) + 1
    partes = [f'{n} {geom.PLURAL[k] if n != 1 else k}' for k, n in contagem.items()] or ['nenhuma geometria']
    sai(f'CAMADA: {camada["nome"]} ({NOMES[camada["formato"]]})')
    sai(f'FEIÇÕES: {len(fs)}: ' + ', '.join(partes) + (f'; {len(fs) - len(com_geo)} sem geometria' if len(fs) != len(com_geo) else ''))
    perguntar, src = [], None
    try:
        src = resolver_src(camada, args)
        sai(f'SRC: {projecao.nome(src)} — {src["origem"]}')
        if 'deduzido' in src['origem']:
            sai('     (se o arquivo for de outro datum, como o SAD 69, a posição sai deslocada em dezenas de metros: confirme com o usuário)')
            if camada['formato'] == 'shp':
                perguntar.append('se o shapefile, que veio sem o .prj, está mesmo em SIRGAS 2000 ou WGS 84')
    except projecao.SrcAmbiguo as e:
        sai(f'SRC: NÃO IDENTIFICADO — {e}')
        perguntar.append('em que sistema de coordenadas o arquivo está (fuso UTM e hemisfério, ou graus)')
    except projecao.SrcRecusado as e:
        sai(f'SRC: RECUSADO — {e}')
    if camada.get('codificacao') and camada['formato'] == 'shp':
        sai(f'CODIFICAÇÃO DO .dbf: {camada["codificacao"]}')
    if com_geo:
        c = geom.caixa(com_geo)
        if src and src['tipo'] == 'utm':
            sai(f'EXTENSÃO: E {num(c[0], 1)} a {num(c[2], 1)} m · N {num(c[1], 1)} a {num(c[3], 1)} m')
        else:
            sai(f'EXTENSÃO: x de {c[0]:.6f} a {c[2]:.6f} · y de {c[1]:.6f} a {c[3]:.6f}')
        if src:
            lon, lat = _centro_em_graus(com_geo, src)
            sai(f'CENTRO: longitude {lon:.5f}, latitude {lat:.5f}')
            for aviso in projecao.avisos_de_posicao(lon, lat, src):
                sai(f'ATENÇÃO: {aviso}')
                perguntar.append('se as coordenadas estão certas (o arquivo cai fora do Brasil)')
    if camada['campos']:
        sai(f'CAMPOS ({len(camada["campos"])}):')
        for campo in camada['campos']:
            ex = _exemplos(fs, campo)
            sai(f'  - {campo} ({_tipo_do_campo(fs, campo)})' + (': ' + ' | '.join(e[:40] for e in ex) if ex else ''))
    else:
        sai('CAMPOS: nenhum')
    if src and com_geo:
        areas, comps, alvo = geom.medir(fs, src)
        total_a = sum(a for a in areas if a)
        total_c = sum(c for c in comps if c)
        if total_a:
            elip = sum(a for a in geom.areas_no_elipsoide(fs, src) if a)
            sai(f'ÁREA: total {num(total_a)} ha, plana, em {projecao.nome(alvo)} (a medida das skills da casa); '
                f'{num(elip)} ha sobre o elipsoide (a medida do QGIS e do CAR)')
        if total_c:
            sai(f'COMPRIMENTO das linhas: total {num(total_c, 1)} m')
        mostrar = [(i, f) for i, f in enumerate(fs, 1) if areas[i - 1] or comps[i - 1]]
        for i, f in mostrar[:args.linhas]:
            medida = f'{num(areas[i - 1])} ha' if areas[i - 1] else f'{num(comps[i - 1], 1)} m'
            sai(f'  {i:>4}  {kml_gpx.nome_da_feicao(f["properties"], args.campo_nome, i)[:40]:<40}  {medida}')
        if len(mostrar) > args.linhas:
            sai(f'  … e mais {len(mostrar) - args.linhas} (use --linhas N para ver mais)')
    _, linhas, resumo = conserto.consertar_feicoes(fs, True, lambda f, i: kml_gpx.nome_da_feicao(f['properties'], args.campo_nome, i))
    if linhas:
        sai(f'GEOMETRIA: {len(linhas)} feição(ões) com algo a relatar (nada foi alterado; --consertar aplica o que é seguro):')
        for linha in linhas[:args.linhas]:
            sai(f'  - {linha}')
        if len(linhas) > args.linhas:
            sai(f'  … e mais {len(linhas) - args.linhas}')
    else:
        sai('GEOMETRIA: nenhum defeito encontrado')
    for aviso in camada['avisos']:
        sai(f'AVISO: {aviso}')
    if perguntar:
        sai('PERGUNTE AO USUÁRIO ANTES DE CONVERTER: ' + '; '.join(dict.fromkeys(perguntar)))
    return src


# ---------------------------------------------------------------- etapas da conversão

def unir(feicoes, src, campo, tol, campo_nome, sai):
    polis = [f for f in feicoes if geom.familia(f['geometry']) == 'polígono']
    fora = sum(1 for f in feicoes if f['geometry']) - len(polis)
    if not polis:
        raise Parou('a união junta polígonos, e o arquivo não tem nenhum')
    if fora:
        sai(f'UNIÃO: {fora} feição(ões) que não são polígono ficaram de fora')
    if campo:
        real = next((k for k in polis[0]['properties'] if k.lower() == campo.lower()), None)
        if real is None:
            raise Parou(f'o arquivo não tem o campo "{campo}" para unir. Campos: {", ".join(polis[0]["properties"]) or "nenhum"}')
        campo = real
    alvo = geom.src_de_medida(polis, src)
    plano = projecao.conversor(src, alvo)
    grupos = {}
    for i, f in enumerate(polis, 1):
        grupos.setdefault(str(f['properties'].get(campo, '')) if campo else 'união', []).append((i, f))
    novas = []
    for valor, itens in grupos.items():
        pares = [(geom.mapear(f['geometry'], plano), f['geometry']) for _, f in itens]
        polis_novos, r = uniao.dissolver(pares, tol)
        g = geom.de_poligonos(polis_novos)
        area = geom.area_m2(geom.mapear(g, plano)) / 10000
        props = ({campo: itens[0][1]['properties'].get(campo)} if campo else {'nome': 'união'})
        props.update({'feicoes': len(itens), 'area_ha': round(area, 4)})
        novas.append({'geometry': g, 'properties': props})
        rotulo = f'"{valor}"' if campo else 'todas as feições'
        if r['dissolvido']:
            sai(f'UNIÃO de {rotulo}: {len(itens)} feição(ões) viraram {len(polis_novos)} polígono(s), sem as divisas internas. '
                f'Área: {num(r["area_antes_ha"], 4)} ha antes, {num(area, 4)} ha depois')
            if r['movidos']:
                sai(f'  {r["movidos"]} vértice(s) foram ajustados em até {num(r["maior_ajuste"] * 100, 1)} cm (pontos a menos de {num(tol * 100, 0)} cm um do outro contam como o mesmo)')
            if r['frestas']:
                sai(f'  ATENÇÃO: sobraram {r["frestas"]} furo(s) com menos de 1 m de largura, {num(r["area_frestas_m2"], 1)} m² no total. Devem ser frestas entre '
                    f'divisas que não coincidem: confira no mapa; se forem, repita com --tolerancia maior (a atual é {num(tol, 2)} m)')
        else:
            nomes = [' e '.join(kml_gpx.nome_da_feicao(itens[k][1]['properties'], campo_nome, itens[k][0]) for k in par) for par in r['sobrepostos'][:6]]
            sai(f'UNIÃO de {rotulo}: NÃO dissolvida: {r["motivo"]}' + (f' ({"; ".join(nomes)})' if nomes else '')
                + f'. As {len(itens)} feições foram só agrupadas num multipolígono, com as divisas. A área de {num(area, 4)} ha conta duas '
                'vezes o trecho sobreposto. Corrija a sobreposição no QGIS antes de usar essa área')
    return novas, ([campo] if campo else ['nome']) + ['feicoes', 'area_ha']


def simplificar(feicoes, src, tol, sai):
    alvo = geom.src_de_medida(feicoes, src)
    ida, volta = projecao.conversor(src, alvo), projecao.conversor(alvo, src)
    antes = sum(geom.n_vertices(f['geometry']) for f in feicoes)
    area_antes = sum(a for a in geom.medir(feicoes, src)[0] if a)
    novas = []
    for f in feicoes:
        g = f['geometry']
        if g and geom.familia(g) != 'ponto':
            g = geom.mapear(geom.simplificar(geom.mapear(g, ida), tol), volta)
        novas.append({'geometry': g, 'properties': f['properties']})
    depois = sum(geom.n_vertices(f['geometry']) for f in novas)
    area_depois = sum(a for a in geom.medir(novas, src)[0] if a)
    sai(f'SIMPLIFICAÇÃO ({tol} m): {antes} vértices viraram {depois}. Área: {num(area_antes, 4)} ha antes, {num(area_depois, 4)} ha depois. '
        'O contorno mudou: divisas vizinhas podem deixar de coincidir. Use só para enviar o arquivo como texto, não para medir')
    return novas


def src_de_saida(formato, src, feicoes, args):
    """O SRC do arquivo gravado."""
    pedido = (args.src_saida or '').strip().lower()
    if formato in ('kml', 'kmz', 'gpx'):
        if pedido and pedido not in ('geo', 'graus', '4326', 'epsg:4326', 'wgs84'):
            raise Parou(f'{NOMES[formato]} é sempre em graus (WGS 84): tire o --src-saida')
        return projecao.geo('WGS 84', 'padrão do formato')
    if not pedido:
        if formato == 'geojson' or args.para_sat:
            return projecao.geo('WGS 84', 'padrão do GeoJSON')
        return src
    if pedido == 'utm':
        lon, lat = _centro_em_graus(feicoes, src)
        zona, sul = projecao.zona_de(lon, lat)
        return projecao.utm(zona, sul, src['datum'], 'fuso do centro do arquivo')
    try:
        return projecao.src_informado(pedido)
    except (projecao.SrcRecusado, projecao.SrcAmbiguo) as e:
        raise Parou(f'SRC de saída: {e}')


def _zip_de(arquivos):
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for nome, dados in arquivos.items():
            z.writestr(nome, dados)
    return buf.getvalue()


def gravar(feicoes, campos, formato, src, pasta, base, args):
    """Grava no formato pedido. Devolve (arquivos gravados, avisos)."""
    casas = args.decimais if args.decimais is not None else (8 if src['tipo'] == 'geo' else 3)
    avisos, gerados = [], []
    com_geo = [f for f in feicoes if f['geometry']]
    if formato == 'shp':
        familias = []
        for f in com_geo:
            if geom.familia(f['geometry']) not in familias:
                familias.append(geom.familia(f['geometry']))
        if len(familias) > 1:
            avisos.append('o shapefile leva um tipo de geometria por arquivo: saiu um para cada tipo (' + ', '.join(geom.PLURAL[k] for k in familias) + ')')
        dentro = {}
        for k, fam in enumerate(familias or ['ponto']):
            parte = [f for f in feicoes if (f['geometry'] is None and k == 0) or (f['geometry'] and geom.familia(f['geometry']) == fam)]
            nome = base if len(familias) <= 1 else f'{base}_{limpo(geom.PLURAL[fam])}'
            arquivos, av = shapefile.gravar(parte, campos, projecao.prj_de(src))
            avisos += av
            for ext, dados in arquivos.items():
                dentro[f'{nome}.{ext}'] = dados
        if args.solto:
            for nome, dados in dentro.items():
                (pasta / nome).write_bytes(dados)
                gerados.append(pasta / nome)
        else:
            (pasta / f'{base}.zip').write_bytes(_zip_de(dentro))
            gerados.append(pasta / f'{base}.zip')
        return gerados, list(dict.fromkeys(avisos))
    sem_geo = len(feicoes) - len(com_geo)
    if formato == 'geojson':
        codigo = projecao.epsg(src) if src['tipo'] == 'utm' else None
        if src['tipo'] == 'utm':
            avisos.append('GeoJSON em metros foge do padrão (que é graus): o QGIS abre, mas a ClaudIA Sat e os mapas da internet esperam graus')
        dados = texto.gravar_geojson(feicoes, campos, base, casas, codigo).encode('utf-8')
        ext = 'geojson'
    elif formato in ('kml', 'kmz'):
        t = kml_gpx.gravar_kml(feicoes, campos, base, args.campo_nome, casas)
        dados, ext = (kml_gpx.gravar_kmz(t), 'kmz') if formato == 'kmz' else (t.encode('utf-8'), 'kml')
    elif formato == 'gpx':
        t, av = kml_gpx.gravar_gpx(feicoes, campos, base, args.campo_nome, casas, args.gpx_rota)
        avisos += av
        dados, ext = t.encode('utf-8'), 'gpx'
    elif formato == 'csv':
        # com BOM o Excel reconhece os acentos
        dados, ext = ('﻿' + texto.gravar_csv(feicoes, campos, src['tipo'] == 'geo', casas, args.csv_br)).encode('utf-8'), 'csv'
    else:
        dados, ext = texto.gravar_wkt(feicoes, casas, args.wkt_unico).encode('utf-8'), 'wkt'
        if campos and not args.wkt_unico:
            avisos.append('o WKT guarda só a geometria: os atributos não foram junto (para levá-los, use CSV, que sai com a coluna wkt)')
    if sem_geo and formato != 'geojson':
        avisos.append(f'{sem_geo} feição(ões) sem geometria não entraram no arquivo')
    (pasta / f'{base}.{ext}').write_bytes(dados)
    return [pasta / f'{base}.{ext}'], avisos


def conferir(arquivos, formato, esperadas, src, args, sai):
    """Relê o que foi gravado e compara com o que devia ter saído."""
    vazio = argparse.Namespace(x=None, y=None, wkt=None, src_entrada=None)
    lidas = []
    try:
        if formato == 'shp' and args.solto:
            for a in arquivos:
                if a.suffix == '.shp':
                    lidas += ler_entrada(a, vazio)[0]['feicoes']
        else:
            for camada in ler_entrada(arquivos[0], vazio):
                lidas += camada['feicoes']
    except (Parou, ValueError, projecao.SrcAmbiguo) as e:
        sai(f'CONFERÊNCIA: FALHOU ao reler o arquivo gravado ({e})')
        return False
    com_geo = [f for f in esperadas if f['geometry']]
    if formato == 'wkt' and args.wkt_unico:
        n_esperado = 1
    elif formato == 'gpx':  # no GPX cada ponto de um multiponto vira um wpt
        n_esperado = sum(len(f['geometry']['coordinates']) if f['geometry']['type'] == 'MultiPoint' else 1 for f in com_geo)
    else:
        n_esperado = len(com_geo)
    n_lido = sum(1 for f in lidas if f['geometry'])
    ok = n_lido == n_esperado
    texto_ = f'CONFERÊNCIA: o arquivo gravado foi relido: {n_lido} feição(ões) com geometria (esperado: {n_esperado})'
    area_e = sum(a for a in geom.medir(esperadas, src)[0] if a)
    if area_e and formato != 'gpx':
        area_l = sum(a for a in geom.medir(lidas, src)[0] if a)
        dif = abs(area_l - area_e)
        ok = ok and dif <= max(1e-4, area_e * 1e-5)
        texto_ += f'; área {num(area_l, 4)} ha (esperado: {num(area_e, 4)} ha)'
    sai(texto_ + (' — CONFERE' if ok else ' — NÃO CONFERE: não entregue este arquivo sem entender a diferença'))
    return ok


def converter(camada, formato, args, pasta, base, sai=print):
    """Converte uma camada. Devolve os arquivos gravados."""
    fs, campos = camada['feicoes'], list(camada['campos'])
    if args.trocar_xy:
        fs = trocar_xy(fs)
        camada = dict(camada, feicoes=fs)
        sai('COORDENADAS: x e y foram trocados (--trocar-xy)')
    if not any(f['geometry'] for f in fs):
        raise Parou('o arquivo não tem nenhuma geometria para converter')
    try:
        src = resolver_src(camada, args)
    except projecao.SrcAmbiguo as e:
        raise Parou(f'falta saber o sistema de coordenadas. {e}')
    except projecao.SrcRecusado as e:
        raise Parou(str(e))
    sai(f'ENTRADA: {camada["nome"]} ({NOMES[camada["formato"]]}), {len(fs)} feição(ões), SRC {projecao.nome(src)} — {src["origem"]}')
    com_geo = [f for f in fs if f['geometry']]
    lon, lat = _centro_em_graus(com_geo, src)
    for aviso in projecao.avisos_de_posicao(lon, lat, src):
        sai(f'ATENÇÃO: {aviso}')
    if args.so:
        fs = [f for f in fs if f['geometry'] and geom.familia(f['geometry']) == SO[args.so]]
        sai(f'FILTRO: só {args.so}: {len(fs)} feição(ões)')
        if not fs:
            raise Parou(f'o arquivo não tem {args.so}')
    fs, linhas, resumo = conserto.consertar_feicoes(fs, args.consertar, lambda f, i: kml_gpx.nome_da_feicao(f['properties'], args.campo_nome, i))
    if linhas:
        modo = 'consertos seguros aplicados' if args.consertar else 'só o indispensável foi mexido (anel fechado, anel sem área descartado); --consertar faz o resto'
        sai(f'GEOMETRIA: {len(linhas)} feição(ões) com algo a relatar ({modo}):')
        for linha in linhas[:args.linhas]:
            sai(f'  - {linha}')
        if len(linhas) > args.linhas:
            sai(f'  … e mais {len(linhas) - args.linhas} (o relatório completo está no arquivo _relatorio.txt)')
        if resumo['perderam_geometria']:
            sai(f'  {resumo["perderam_geometria"]} feição(ões) ficaram sem geometria (não tinham área ou comprimento)')
    if args.unir or args.unir_por:
        if resumo['com_pendencia']:
            sai('ATENÇÃO: há feição com defeito de geometria que não foi consertado (acima). A união segue, mas pode sair com o mesmo defeito: '
                'o certo é corrigir o contorno no QGIS e unir de novo')
        fs, campos = unir(fs, src, args.unir_por, args.tolerancia, args.campo_nome, sai)
    if args.simplificar:
        fs = simplificar(fs, src, args.simplificar, sai)
    if args.para_sat:
        fs = [f for f in fs if f['geometry']]
    destino = src_de_saida(formato, src, [f for f in fs if f['geometry']], args)
    if (destino['tipo'], destino['zona'], destino['sul']) != (src['tipo'], src['zona'], src['sul']):
        f_conv = projecao.conversor(src, destino)
        fs = [{'geometry': geom.mapear(f['geometry'], f_conv) if f['geometry'] else None, 'properties': f['properties']} for f in fs]
        sai(f'REPROJEÇÃO: de {projecao.nome(src)} para {projecao.nome(destino)}')
    elif destino['datum'] != src['datum']:
        sai(f'SRC: o rótulo passou de {src["datum"]} para {destino["datum"]}; as coordenadas são as mesmas (os dois diferem em centímetros)')
    if destino['tipo'] == 'utm' and projecao.epsg(destino) is None:
        sai(f'AVISO: não há código EPSG para {projecao.nome(destino)}; o .prj descreve o sistema por extenso')
    arquivos, avisos = gravar(fs, campos, formato, destino, pasta, base, args)
    areas, comps, alvo = geom.medir(fs, destino)
    total_a, total_c = sum(a for a in areas if a), sum(c for c in comps if c)
    sai(f'SAÍDA: {NOMES[formato]}, {sum(1 for f in fs if f["geometry"])} feição(ões), SRC {projecao.nome(destino)}'
        + (f', área total {num(total_a, 4)} ha (plana, em {projecao.nome(alvo)})' if total_a else '')
        + (f', linhas com {num(total_c, 1)} m' if total_c else ''))
    for aviso in list(camada['avisos']) + avisos:
        sai(f'AVISO: {aviso}')
    conferir(arquivos, formato, fs, destino, args, sai)
    for a in arquivos:
        sai(f'ARQUIVO: {a} ({a.stat().st_size / 1024:.1f} KB)')
    if args.para_sat:
        vertices = sum(geom.n_vertices(f['geometry']) for f in fs)
        sai(f'PARA A ClaudIA Sat: envie o conteúdo deste GeoJSON no campo de perímetro ({vertices} vértices). '
            + ('O arquivo é grande para ir como texto: repita com --simplificar 2 (ou 5) e confira a área.' if arquivos[0].stat().st_size > 300000 else
               'Os atributos foram mantidos: é por eles que a ferramenta acha cada talhão.'))
    return arquivos


# ---------------------------------------------------------------- demonstração

def demo(pasta):
    entrada = pasta / 'entrada'
    entrada.mkdir(parents=True, exist_ok=True)
    geo_sirgas = projecao.geo()
    fs, campos = sintetico.talhoes(), ['TALHAO', 'CULTURA', 'FAZENDA', 'OBSERVACAO_DE_CAMPO']
    arqs, _ = shapefile.gravar(fs, campos, projecao.prj_de(geo_sirgas))
    (entrada / 'talhoes.zip').write_bytes(_zip_de({f'talhoes.{e}': d for e, d in arqs.items()}))
    (entrada / 'pontos.csv').write_text(texto.gravar_csv(sintetico.pontos(), ['ID', 'ARGILA', 'COLETA'], True, 7, brasileiro=True), encoding='utf-8')
    (entrada / 'carreador.kml').write_text(kml_gpx.gravar_kml(sintetico.carreador(), ['NOME', 'TIPO'], 'carreador', 'NOME'), encoding='utf-8')
    (entrada / 'talhoes_com_defeito.geojson').write_text(_geojson_cru(sintetico.talhoes_com_defeito(), campos), encoding='utf-8')
    passos = [
        ('1. O que o shapefile tem', [str(entrada / 'talhoes.zip'), '--listar']),
        ('2. Shapefile para KML', [str(entrada / 'talhoes.zip'), '--para', 'kml']),
        ('3. Shapefile em graus para shapefile em UTM', [str(entrada / 'talhoes.zip'), '--para', 'shp', '--src-saida', 'utm', '--nome', 'talhoes_utm']),
        ('4. Os quatro talhões unidos num perímetro só', [str(entrada / 'talhoes.zip'), '--para', 'geojson', '--unir', '--nome', 'perimetro']),
        ('5. União por cultura', [str(entrada / 'talhoes.zip'), '--para', 'kmz', '--unir-por', 'CULTURA', '--nome', 'por_cultura']),
        ('6. Pronto para a ClaudIA Sat', [str(entrada / 'talhoes.zip'), '--para-sat', '--nome', 'talhoes_para_sat']),
        ('7. Pontos em CSV (vírgula decimal) para GPX e shapefile', [str(entrada / 'pontos.csv'), '--para', 'gpx']),
        ('', [str(entrada / 'pontos.csv'), '--para', 'shp']),
        ('8. Linha em KML para WKT', [str(entrada / 'carreador.kml'), '--para', 'wkt']),
        ('9. Geometria com defeito: o que o arquivo tem', [str(entrada / 'talhoes_com_defeito.geojson'), '--listar']),
        ('10. Geometria com defeito: conserto do que é seguro', [str(entrada / 'talhoes_com_defeito.geojson'), '--para', 'shp', '--consertar', '--nome', 'talhoes_consertados']),
    ]
    for titulo, args in passos:
        if titulo:
            print(f'\n=== {titulo} ===')
        principal(args + ['--saida', str(pasta)])
    print(f'\nDemonstração pronta em {pasta} (dados inventados).')


def _geojson_cru(feicoes, campos):
    """GeoJSON sem acertar nada (para a demonstração levar os defeitos como estão)."""
    import json
    return json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {k: f['properties'].get(k) for k in campos},
         'geometry': {'type': f['geometry']['type'], 'coordinates': f['geometry']['coordinates']}} for f in feicoes]}, ensure_ascii=False)


# ---------------------------------------------------------------- linha de comando

def argumentos():
    ap = argparse.ArgumentParser(description='Converte arquivos geográficos (shapefile, KML, KMZ, GeoJSON, GPX, CSV, WKT).')
    ap.add_argument('entrada', nargs='?', help='arquivo de entrada')
    ap.add_argument('--listar', action='store_true', help='só mostra o que o arquivo tem')
    ap.add_argument('--para', choices=sorted(NOMES), help='formato de saída')
    ap.add_argument('--para-sat', action='store_true', help='GeoJSON em graus, com os atributos, para a ClaudIA Sat')
    ap.add_argument('--saida', default='saida', help='pasta de saída (padrão: saida)')
    ap.add_argument('--nome', help='nome do arquivo de saída, sem extensão')
    ap.add_argument('--camada', help='quando o zip tem várias camadas, qual converter')
    ap.add_argument('--src-entrada', help='SRC do arquivo quando ele não diz: 4674, 4326, utm22s, 23S, EPSG:31982…')
    ap.add_argument('--src-saida', help='SRC da saída: graus, utm (fuso do centro), utm22s, EPSG:31982…')
    ap.add_argument('--x', help='CSV: coluna da longitude ou do leste')
    ap.add_argument('--y', help='CSV: coluna da latitude ou do norte')
    ap.add_argument('--wkt', help='CSV: coluna com a geometria em WKT')
    ap.add_argument('--trocar-xy', action='store_true', help='troca x e y (latitude e longitude invertidas)')
    ap.add_argument('--so', choices=sorted(SO), help='converte só um tipo de geometria')
    ap.add_argument('--consertar', action='store_true', help='aplica os consertos seguros de geometria')
    ap.add_argument('--unir', action='store_true', help='une todos os polígonos num só')
    ap.add_argument('--unir-por', metavar='CAMPO', help='une os polígonos que têm o mesmo valor no campo')
    ap.add_argument('--tolerancia', type=float, default=0.05, help='união: distância (m) até a qual duas divisas contam como a mesma (padrão 0,05)')
    ap.add_argument('--simplificar', type=float, metavar='M', help='tira vértices que desviam menos que M metros')
    ap.add_argument('--campo-nome', help='campo que dá nome à feição no KML, no GPX e nos relatórios')
    ap.add_argument('--decimais', type=int, help='casas decimais das coordenadas (padrão: 8 em graus, 3 em metros)')
    ap.add_argument('--csv-br', action='store_true', help='CSV com ponto e vírgula e vírgula decimal (Excel em português)')
    ap.add_argument('--wkt-unico', action='store_true', help='WKT: todos os polígonos num MULTIPOLYGON só')
    ap.add_argument('--gpx-rota', action='store_true', help='GPX: linhas como rota (rte) em vez de trilha (trk)')
    ap.add_argument('--solto', action='store_true', help='shapefile: grava os arquivos soltos em vez do zip')
    ap.add_argument('--linhas', type=int, default=30, help='quantas linhas mostrar nas listas (padrão 30)')
    ap.add_argument('--demo', action='store_true', help='roda a demonstração com a fazenda inventada')
    return ap


def principal(argv=None):
    args = argumentos().parse_args(argv)
    pasta = Path(args.saida)
    if args.demo:
        demo(pasta)
        return 0
    if not args.entrada:
        argumentos().print_help()
        return 2
    relatorio = []

    def sai(linha):
        print(linha)
        relatorio.append(linha)
    try:
        if not 0 < args.tolerancia <= 50:
            raise Parou('--tolerancia vai de mais que 0 até 50 metros')
        try:
            camadas = ler_entrada(args.entrada, args)
        except projecao.SrcAmbiguo as e:
            raise Parou(str(e))
        except ValueError as e:
            raise Parou(f'não consegui ler {Path(args.entrada).name}: {e}')
        if args.camada:
            escolhidas = [c for c in camadas if c['nome'].lower() == args.camada.lower()]
            if not escolhidas:
                raise Parou(f'o arquivo não tem a camada "{args.camada}". Camadas: {", ".join(c["nome"] for c in camadas)}')
            camadas = escolhidas
        formato = 'geojson' if args.para_sat else args.para
        if args.listar or not formato:
            if len(camadas) > 1:
                print(f'O arquivo tem {len(camadas)} camadas: ' + ', '.join(c['nome'] for c in camadas) + '\n')
            for c in camadas:
                if args.trocar_xy:
                    c = dict(c, feicoes=trocar_xy(c['feicoes']))
                listar(c, args)
                print()
            if not args.listar:
                print('Nada foi convertido: diga o formato com --para (geojson, kml, kmz, shp, gpx, csv ou wkt).')
            return 0
        pasta.mkdir(parents=True, exist_ok=True)
        for c in camadas:
            base = limpo(args.nome or Path(args.entrada).stem) + (f'_{limpo(c["nome"])}' if len(camadas) > 1 else '')
            if (pasta / f"{base}.{'zip' if formato == 'shp' else formato}").resolve() == Path(args.entrada).resolve():
                base += '_convertido'  # a saída não pode cair em cima do arquivo de entrada
            converter(c, formato, args, pasta, base, sai)
            (pasta / f'{base}_relatorio.txt').write_text('\n'.join(relatorio) + '\n', encoding='utf-8')
            relatorio.clear()
        return 0
    except (Parou, ValueError) as e:  # ValueError: o que os leitores e gravadores recusam, com o motivo
        print(f'NÃO CONVERTIDO: {e}')
        return 2


if __name__ == '__main__':
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    sys.exit(principal())
