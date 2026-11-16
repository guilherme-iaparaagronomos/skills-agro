"""Adequa o mapa de aplicação ao monitor da máquina: confere o arquivo, corrige
o formato e entrega o zip para extrair na raiz do pen drive.

  1. olhar o que o arquivo tem (não grava nada):
     python scripts/aplicacao.py mapa.zip --diagnostico [--campo-dose DOSE]
  2. gerar, com as escolhas do usuário:
     python scripts/aplicacao.py mapa.zip --controlador stara --produto solido --unidade kg/ha \
         --campo-dose DOSE --nome ADUBO01 --saida saida
  com as zonas da skill zonas-de-manejo e a dose de cada zona informada pelo usuário:
     python scripts/aplicacao.py zonas.geojson --campo-zona zona --tabela-doses "1=120;2=180;3=240" ...
  demonstração com talhão inventado:
     python scripts/aplicacao.py --demo --saida saida-demo

A dose é do usuário: a skill não calcula, não recomenda e não muda dose por
conta própria. Conversão de unidade, degrau e limites só rodam com o valor que
ele informar, e o relatório lista o que mudou.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import conserto  # noqa: E402
import controladores as C  # noqa: E402
import geom  # noqa: E402
import kml_gpx  # noqa: E402
import pacote  # noqa: E402
import projecao  # noqa: E402
import regras as R  # noqa: E402
import shapefile  # noqa: E402
import texto  # noqa: E402
import uniao  # noqa: E402

EXTENSOES = {'.shp': 'shp', '.dbf': 'shp', '.shx': 'shp', '.zip': 'zip', '.kml': 'kml', '.kmz': 'kmz', '.geojson': 'geojson', '.json': 'geojson'}
LIMITE_SOBREPOSICAO = 2500      # acima disso a conferência de sobreposição demora demais e não é feita
TOL_DIVISA = 0.05               # metros: divisas a menos disso contam como a mesma


def num(v, casas=2):
    return f'{v:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def sinal(v, casas=2):
    """Número com o sinal na frente: +12,50 ou −3,20."""
    return ('+' if v >= 0 else '−') + num(abs(v), casas)


# ---------------------------------------------------------------- leitura

def _camada(nome, formato, bruto):
    return {'nome': nome, 'formato': formato, 'feicoes': bruto['feicoes'], 'campos': list(bruto['campos']),
            'avisos': list(bruto.get('avisos', [])), 'prj': bruto.get('prj'), 'epsg': bruto.get('epsg')}


def _de_bytes(nome, formato, dados):
    if formato == 'kml':
        return _camada(nome, 'kml', kml_gpx.ler_kml(dados))
    if formato == 'kmz':
        return _camada(nome, 'kmz', kml_gpx.ler_kmz(dados))
    return _camada(nome, 'geojson', texto.ler_geojson(dados))


def ler_entrada(caminho):
    """Devolve as camadas do arquivo (um zip pode trazer mais de uma)."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise R.Recusa(f'arquivo não encontrado: {caminho}')
    formato = EXTENSOES.get(caminho.suffix.lower())
    if formato is None:
        raise R.Recusa(f'extensão "{caminho.suffix}" não é lida. A skill lê o mapa em shapefile (.zip ou .shp), GeoJSON (.geojson, .json), KML e KMZ')
    try:
        if formato == 'shp':
            partes = {}
            for irmao in caminho.parent.iterdir():
                if irmao.stem.lower() == caminho.stem.lower() and irmao.suffix.lower()[1:] in ('shp', 'shx', 'dbf', 'prj', 'cpg'):
                    partes[irmao.suffix.lower()[1:]] = irmao.read_bytes()
            if 'shp' not in partes:
                raise R.Recusa(f'não achei o arquivo {caminho.stem}.shp na mesma pasta')
            return [_camada(caminho.stem, 'shp', shapefile.ler(partes))]
        dados = caminho.read_bytes()
        if not dados.strip():
            raise R.Recusa(f'o arquivo {caminho.name} está vazio')
        if formato != 'zip':
            return [_de_bytes(caminho.stem, formato, dados)]
        membros = kml_gpx.ler_do_zip(dados, {'shp', 'shx', 'dbf', 'prj', 'cpg', 'kml', 'geojson', 'json'})
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
            if ext.lower() in ('kml', 'geojson', 'json') and conteudo.strip():
                try:
                    camadas.append(_de_bytes(base.split('/')[-1], EXTENSOES['.' + ext.lower()], conteudo))
                except ValueError as e:
                    if ext.lower() != 'json':
                        raise R.Recusa(f'{nome}: {e}')
        if not camadas:
            raise R.Recusa('o zip não tem shapefile, GeoJSON nem KML que a skill leia')
        return camadas
    except ValueError as e:
        raise R.Recusa(f'{caminho.name}: {e}')


def escolher_camada(camadas, pedida):
    if pedida:
        achada = next((c for c in camadas if c['nome'].lower() == pedida.lower()), None)
        if achada is None:
            raise R.Recusa(f'o arquivo não tem a camada "{pedida}". Camadas: {", ".join(c["nome"] for c in camadas)}')
        return achada
    if len(camadas) > 1:
        raise R.Recusa('o arquivo traz mais de uma camada: ' + ', '.join(f'{c["nome"]} ({len(c["feicoes"])} feições)' for c in camadas)
                       + '. Pergunte ao usuário qual é o mapa de aplicação e repita com --camada')
    return camadas[0]


def resolver_src(camada, informado):
    """O sistema de coordenadas da camada. Para e pergunta quando o arquivo não diz (metros sem fuso)."""
    try:
        if camada['formato'] in ('kml', 'kmz'):
            return projecao.geo('WGS 84', 'o formato é sempre em graus (WGS 84)')
        if informado:
            src = projecao.src_informado(informado)
            src['origem'] = 'informado pelo usuário'
            return src
        if camada.get('prj'):
            return projecao.src_do_prj(camada['prj'])
        if camada.get('epsg'):
            return projecao.src_do_epsg(camada['epsg'], 'declarado no arquivo')
        xs = [p[0] for f in camada['feicoes'] if f['geometry'] for s in geom.partes(f['geometry']) for p in s]
        ys = [p[1] for f in camada['feicoes'] if f['geometry'] for s in geom.partes(f['geometry']) for p in s]
        return projecao.deduzir(xs, ys)
    except projecao.SrcAmbiguo as e:
        raise R.Recusa(f'sistema de coordenadas: {e}')
    except projecao.SrcRecusado as e:
        raise R.Recusa(f'sistema de coordenadas: {e}')


def preparar(camada, src):
    """Separa os polígonos, conserta o que é seguro e mede. Devolve o dicionário de trabalho."""
    todas = camada['feicoes']
    pols = [(i, f) for i, f in enumerate(todas, 1) if f['geometry'] and geom.familia(f['geometry']) == 'polígono']
    outras = [i for i, f in enumerate(todas, 1) if f['geometry'] and geom.familia(f['geometry']) != 'polígono']
    vazias = [i for i, f in enumerate(todas, 1) if not f['geometry']]
    if not pols:
        raise R.Recusa('o arquivo não tem polígono nenhum. O mapa de aplicação precisa ser de polígonos (zonas ou grade), cada um com a dose')
    novas, linhas, resumo = conserto.consertar_feicoes([f for _, f in pols], True, lambda f, i: f'polígono {i}')
    perdidos = [pols[k][0] for k, f in enumerate(novas) if f['geometry'] is None]
    mantidos = [(pols[k][0], f) for k, f in enumerate(novas) if f['geometry'] is not None]
    if not mantidos:
        raise R.Recusa('nenhum polígono do arquivo tem área')
    feicoes = [f for _, f in mantidos]
    areas, _, alvo = geom.medir(feicoes, src)
    return {'indices': [i for i, _ in mantidos], 'feicoes': feicoes, 'areas': areas, 'src': src, 'src_medida': alvo,
            'outras': outras, 'vazias': vazias, 'perdidos': perdidos, 'consertos': linhas, 'resumo_conserto': resumo,
            'vertices': sum(geom.n_vertices(f['geometry']) for f in feicoes)}


def conferir_sobreposicao(feicoes, src):
    """Sobreposição e frestas entre os polígonos. None quando o arquivo é grande demais para a conferência."""
    if len(feicoes) > LIMITE_SOBREPOSICAO:
        return None
    plano = projecao.conversor(src, geom.src_de_medida(feicoes, src))
    _, r = uniao.dissolver([(geom.mapear(f['geometry'], plano), f['geometry']) for f in feicoes], TOL_DIVISA)
    return r


# ---------------------------------------------------------------- dose

def campo_real(feicoes, campo):
    nomes = []
    for f in feicoes:
        for k in f['properties']:
            if k not in nomes:
                nomes.append(k)
    achado = next((k for k in nomes if k.lower() == str(campo).lower()), None)
    if achado is None:
        raise R.Recusa(f'o arquivo não tem o campo "{campo}". Campos: {", ".join(nomes) or "nenhum"}')
    return achado


def situacao_do_campo(feicoes, campo):
    """Conta o que há no campo: números, textos que são número, vazios e inválidos."""
    lidos = [R.ler_dose(f['properties'].get(campo)) for f in feicoes]
    conta = {s: sum(1 for _, x in lidos if x == s) for s in ('numero', 'texto', 'vazio', 'invalido')}
    return lidos, conta


def doses_do_campo(trabalho, campo, sem_dose, indices):
    """Lê a dose de cada polígono. Devolve (doses, posições que ficam, relato). Para no que só o usuário resolve."""
    feicoes = trabalho['feicoes']
    lidos, conta = situacao_do_campo(feicoes, campo)
    relato = []
    if conta['invalido']:
        amostra = [f'polígono {indices[k]}: "{feicoes[k]["properties"].get(campo)}"' for k, (_, s) in enumerate(lidos) if s == 'invalido'][:8]
        raise R.Recusa(f'o campo "{campo}" tem {conta["invalido"]} valor(es) que não são número ({"; ".join(amostra)}). '
                       'A dose tem de ser só o número: corrija no arquivo, ou pergunte ao usuário qual é o campo da dose')
    if conta['texto']:
        relato.append(f'o campo "{campo}" trazia {conta["texto"]} dose(s) escrita(s) como texto (por exemplo com vírgula decimal): '
                      'lidas como número, sem mudar o valor')
    ficam = list(range(len(feicoes)))
    if conta['vazio']:
        quais = [indices[k] for k, (_, s) in enumerate(lidos) if s == 'vazio']
        if sem_dose == 'zero':
            lidos = [(0.0, 'numero') if s == 'vazio' else (d, s) for d, s in lidos]
            relato.append(f'{len(quais)} polígono(s) sem dose saíram com dose ZERO, por escolha do usuário: ' + _lista(quais))
        elif sem_dose == 'tirar':
            ficam = [k for k, (_, s) in enumerate(lidos) if s != 'vazio']
            relato.append(f'{len(quais)} polígono(s) sem dose ficaram FORA do arquivo, por escolha do usuário: ' + _lista(quais))
        else:
            raise R.Recusa(f'{len(quais)} polígono(s) estão sem dose no campo "{campo}" ({_lista(quais)}). Pergunte ao usuário: '
                           'dose zero neles (--sem-dose zero) ou tirá-los do arquivo (--sem-dose tirar)? Não escolha por ele')
    doses = [lidos[k][0] for k in ficam]
    negativas = [(indices[k], lidos[k][0]) for k in ficam if lidos[k][0] < 0]
    if negativas:
        raise R.Recusa(f'{len(negativas)} polígono(s) com dose negativa ({"; ".join(f"polígono {i}: {R.g(d)}" for i, d in negativas[:8])}). '
                       'Dose negativa não existe: o arquivo precisa ser corrigido por quem fez a recomendação')
    return doses, ficam, relato


def doses_da_tabela(trabalho, campo_zona, tabela, indices):
    feicoes = trabalho['feicoes']
    chaves = [R.chave_de_zona(f['properties'].get(campo_zona)) if f['properties'].get(campo_zona) not in (None, '') else None for f in feicoes]
    faltam = sorted({c for c in chaves if c is not None and c not in tabela})
    sem_zona = [indices[k] for k, c in enumerate(chaves) if c is None]
    if sem_zona:
        raise R.Recusa(f'{len(sem_zona)} polígono(s) estão sem valor no campo "{campo_zona}": {_lista(sem_zona)}')
    if faltam:
        raise R.Recusa(f'a tabela de doses não tem a(s) zona(s) {", ".join(faltam)}, que estão no arquivo. Peça ao usuário a dose de cada '
                       f'zona. Zonas do arquivo: {", ".join(sorted(set(chaves)))}')
    relato = [f'dose de cada zona informada pelo usuário: ' + '; '.join(f'zona {z} = {R.g(tabela[z])}' for z in sorted(set(chaves)))]
    sobram = sorted(set(tabela) - set(chaves))
    if sobram:
        relato.append(f'a tabela trazia zona(s) que não estão no arquivo e não foram usadas: {", ".join(sobram)}')
    return [tabela[c] for c in chaves], list(range(len(feicoes))), relato


def _lista(indices, teto=12):
    return ', '.join(str(i) for i in indices[:teto]) + ('…' if len(indices) > teto else '')


def juntar_por_dose(feicoes, doses, casas, src):
    """Junta os polígonos de MESMA dose que dividem divisa. Devolve (geometrias, doses, relato)."""
    plano = projecao.conversor(src, geom.src_de_medida(feicoes, src))
    grupos = {}
    for f, d in zip(feicoes, doses):
        grupos.setdefault(round(d, casas), []).append(f)
    geoms, novas_doses, relato = [], [], []
    for dose in sorted(grupos):
        itens = grupos[dose]
        if len(itens) == 1:
            geoms.append(itens[0]['geometry'])
            novas_doses.append(dose)
            continue
        polis, r = uniao.dissolver([(geom.mapear(f['geometry'], plano), f['geometry']) for f in itens], TOL_DIVISA)
        if not r['dissolvido']:
            relato.append(f'dose {R.g(dose)}: os {len(itens)} polígonos NÃO foram juntados ({r["motivo"]}); seguiram como estavam')
            geoms += [f['geometry'] for f in itens]
            novas_doses += [dose] * len(itens)
            continue
        for poli in polis:
            geoms.append({'type': 'Polygon', 'coordinates': poli})
            novas_doses.append(dose)
        if r['frestas']:
            relato.append(f'dose {R.g(dose)}: ficaram {r["frestas"]} fresta(s) estreita(s) entre divisas que não coincidem '
                          f'({num(r["area_frestas_m2"], 1)} m²)')
    return geoms, novas_doses, relato


def separar_partes(geoms, doses):
    g2, d2 = [], []
    for g, d in zip(geoms, doses):
        for poli in geom.poligonos_de(g):
            g2.append({'type': 'Polygon', 'coordinates': poli})
            d2.append(d)
    return g2, d2


# ---------------------------------------------------------------- diagnóstico

def diagnostico(camada, trabalho, args, sai):
    src, feicoes, areas, indices = trabalho['src'], trabalho['feicoes'], trabalho['areas'], trabalho['indices']
    sai(f'ARQUIVO: camada "{camada["nome"]}" ({camada["formato"]}), {len(camada["feicoes"])} feição(ões): {len(feicoes)} polígono(s) com área')
    sai(f'SISTEMA DE COORDENADAS: {projecao.nome(src)} ({src.get("origem", "")}). O arquivo de máquina sai em graus decimais, sem arquivo de projeção')
    cx = geom.caixa(feicoes)
    centro = ((cx[0] + cx[2]) / 2, (cx[1] + cx[3]) / 2)
    if src['tipo'] == 'utm':
        lon, lat = projecao.utm_inversa([centro[0]], [centro[1]], src['zona'], src['sul'], src['datum'])
        centro = (float(lon[0]), float(lat[0]))
    for aviso in projecao.avisos_de_posicao(centro[0], centro[1], src):
        sai(f'ATENÇÃO: {aviso}')
    sai(f'ÁREA: {num(sum(areas), 2)} ha (medida no plano, {projecao.nome(trabalho["src_medida"])}); {trabalho["vertices"]} vértices; '
        f'o menor polígono tem {num(min(areas), 4)} ha e o maior, {num(max(areas), 4)} ha')
    for aviso in camada['avisos']:
        sai(f'LEITURA: {aviso}')
    if trabalho['outras']:
        sai(f'FORA DO MAPA: {len(trabalho["outras"])} feição(ões) que não são polígono (ponto ou linha) não entram no arquivo de máquina: {_lista(trabalho["outras"])}')
    if trabalho['vazias']:
        sai(f'FORA DO MAPA: {len(trabalho["vazias"])} feição(ões) sem geometria: {_lista(trabalho["vazias"])}')
    if trabalho['perdidos']:
        sai(f'FORA DO MAPA: {len(trabalho["perdidos"])} polígono(s) sem área (degenerados): {_lista(trabalho["perdidos"])}')
    if trabalho['consertos']:
        sai(f'GEOMETRIA: {len(trabalho["consertos"])} polígono(s) com defeito consertado ou a conferir:')
        for linha in trabalho['consertos'][:10]:
            sai(f'  {linha}')
    r = conferir_sobreposicao(feicoes, src)
    if r is None:
        sai(f'SOBREPOSIÇÃO: não conferida (o arquivo tem {len(feicoes)} polígonos; a conferência vai até {LIMITE_SOBREPOSICAO}). Confira no QGIS')
    elif r['sobrepostos']:
        pares = '; '.join(f'{indices[a]} e {indices[b]}' for a, b in r['sobrepostos'][:8])
        sai(f'SOBREPOSIÇÃO: {len(r["sobrepostos"])} par(es) de polígonos se sobrepõem ({pares}). Onde dois polígonos se cobrem, a máquina '
            'recebe duas doses para o mesmo lugar: precisa ser corrigido no QGIS por quem fez o mapa')
    elif not r['dissolvido']:
        sai(f'SOBREPOSIÇÃO: não deu para conferir ({r["motivo"]})')
    else:
        sai('SOBREPOSIÇÃO: nenhuma' + (f'. Frestas estreitas entre polígonos: {r["frestas"]} ({num(r["area_frestas_m2"], 1)} m²); nelas a máquina fica sem dose'
                                       if r['frestas'] else '; os polígonos encostam sem fresta'))
    sai('CAMPOS (o campo da dose é escolha do usuário):')
    nomes = []
    for f in feicoes:
        for k in f['properties']:
            if k not in nomes:
                nomes.append(k)
    for nome in nomes:
        lidos, conta = situacao_do_campo(feicoes, nome)
        exemplos = []
        for f in feicoes:
            v = f['properties'].get(nome)
            if v not in (None, '') and str(v) not in exemplos:
                exemplos.append(str(v))
            if len(exemplos) == 3:
                break
        tipo = ('número' if conta['numero'] and not conta['texto'] and not conta['invalido'] else
                'texto que é número' if conta['texto'] and not conta['invalido'] else 'texto' if conta['invalido'] else 'vazio')
        linha = f'  {nome}: {tipo}; exemplos: {", ".join(exemplos) or "—"}'
        if conta['vazio']:
            linha += f'; {conta["vazio"]} vazio(s)'
        if not conta['invalido'] and (conta['numero'] or conta['texto']):
            pares = [(d, a) for (d, s), a in zip(lidos, areas) if d is not None]
            s = R.resumo([p[0] for p in pares], [p[1] for p in pares])
            linha += (f'; de {R.g(s["minima"])} a {R.g(s["maxima"])}, {s["valores_distintos"]} valor(es) distinto(s); se for dose por hectare: '
                      f'média ponderada pela área {num(s["media"], 2)} e dose × área = {num(s["total"], 1)}')
        sai(linha)
    if args.campo_dose:
        campo = campo_real(feicoes, args.campo_dose)
        lidos, conta = situacao_do_campo(feicoes, campo)
        if not conta['invalido'] and not conta['vazio']:
            doses = [d for d, _ in lidos]
            casas = R.casas_necessarias(doses)
            g, _, _ = juntar_por_dose(feicoes, doses, casas, src)
            sai(f'ARQUIVO LEVE: são {len(feicoes)} polígono(s) e {len({round(d, casas) for d in doses})} dose(s) distinta(s) no campo {campo}. '
                f'Juntando os vizinhos de mesma dose (--juntar) ficariam {len(g)} polígono(s), com a mesma área e o mesmo total de produto')
    else:
        sai(f'ARQUIVO LEVE: são {len(feicoes)} polígono(s). Com --campo-dose o diagnóstico diz quantos ficariam juntando os vizinhos de mesma dose')
    sai('NOME NO PEN DRIVE: até 8 caracteres, só letras e números. Do nome deste arquivo sairia "'
        + (R.nome_limpo(camada['nome']) or 'MAPA') + '"; o usuário pode escolher outro')
    sai('FALTA O USUÁRIO DIZER: o controlador (' + ', '.join(C.CONTROLADORES) + '), o tipo do produto (solido, liquido ou semente), '
        'a unidade da dose do arquivo, o campo da dose e o nome do arquivo. Não escolha por ele')
    sai('O limite de polígonos de cada monitor não foi confirmado em manual: se o usuário souber o do monitor dele, use --juntar e confira o número')


# ---------------------------------------------------------------- execução

def executar(camada, trabalho, args, pasta, sai):
    chave = C.achar(args.controlador or '')
    if chave in C.RECUSADOS:
        raise R.Recusa(C.RECUSADOS[chave][1])
    if chave is None:
        raise R.Recusa(f'{"controlador não reconhecido: " + args.controlador if args.controlador else "falta o controlador (--controlador)"}. '
                       f'Os que a skill atende: {", ".join(C.lista())}. Pergunte ao usuário qual é o monitor dele')
    produto = R.produto_canonico(args.produto or '')
    if produto is None:
        raise R.Recusa('falta o tipo do produto (--produto solido, liquido ou semente). Pergunte ao usuário')
    unidade = R.unidade_canonica(args.unidade or '')
    if unidade is None:
        raise R.Recusa('falta a unidade em que a dose está no arquivo (--unidade): kg/ha ou t/ha para sólido, l/ha ou m3/ha para '
                       'líquido, sem/ha ou sem/m para semente. Pergunte ao usuário: o arquivo não diz')
    R.conferir_unidade(produto, unidade)
    para = None
    if args.converter_para:
        para = R.unidade_canonica(args.converter_para)
        if para is None:
            raise R.Recusa(f'unidade de destino "{args.converter_para}" não reconhecida')
    if not args.nome:
        raise R.Recusa('falta o nome do arquivo no pen drive (--nome), com até 8 letras e números. Pergunte ao usuário')
    nome = R.nome_limpo(args.nome)
    if not nome:
        raise R.Recusa(f'o nome "{args.nome}" não tem letra nem número. Peça outro ao usuário')
    feicoes, indices, src = trabalho['feicoes'], trabalho['indices'], trabalho['src']
    relato_dose = []
    if args.tabela_doses:
        if not args.campo_zona:
            raise R.Recusa('com --tabela-doses informe o campo que identifica a zona (--campo-zona)')
        campo_zona = campo_real(feicoes, args.campo_zona)
        arq = Path(args.tabela_doses)
        tabela = R.ler_tabela(arq.read_text(encoding='utf-8-sig') if arq.exists() else args.tabela_doses)
        doses, ficam, relato_dose = doses_da_tabela(trabalho, campo_zona, tabela, indices)
        origem_dose, campo_saida = f'tabela do usuário pelo campo {campo_zona}', R.campo_limpo(args.campo_saida or 'DOSE')
    elif args.campo_dose:
        campo = campo_real(feicoes, args.campo_dose)
        doses, ficam, relato_dose = doses_do_campo(trabalho, campo, args.sem_dose, indices)
        origem_dose, campo_saida = f'campo {campo} do arquivo', R.campo_limpo(args.campo_saida or campo)
    else:
        raise R.Recusa('falta dizer onde está a dose: o campo do arquivo (--campo-dose) ou a tabela de dose por zona '
                       '(--tabela-doses com --campo-zona). Rode --diagnostico, mostre os campos ao usuário e pergunte')
    if campo_saida == 'ID':
        campo_saida = 'DOSE'
    feicoes = [feicoes[k] for k in ficam]
    indices = [indices[k] for k in ficam]
    areas = [trabalho['areas'][k] for k in ficam]
    if not feicoes:
        raise R.Recusa('não sobrou polígono com dose')

    r = R.aplicar(doses, produto, unidade, para, args.espacamento_m, args.degrau, args.minimo, args.maximo, args.fora_do_limite, args.casas)
    finais, unidade_final, casas = r['doses'], r['unidade'], r['casas']
    fator = R.fator_de_conversao(produto, unidade, unidade_final, args.espacamento_m)
    antes = R.resumo([d * fator for d in doses], areas)          # as doses do arquivo, já na unidade final
    depois = R.resumo(finais, areas)

    sob = conferir_sobreposicao(feicoes, src)
    if sob and sob['sobrepostos']:
        diferentes = [(a, b) for a, b in sob['sobrepostos'] if abs(finais[a] - finais[b]) > 1e-9]
        if diferentes and not args.aceitar_sobreposicao:
            pares = '; '.join(f'polígonos {indices[a]} ({R.g(finais[a])}) e {indices[b]} ({R.g(finais[b])})' for a, b in diferentes[:8])
            raise R.Recusa(f'{len(diferentes)} par(es) de polígonos se sobrepõem com doses diferentes: {pares}. No trecho sobreposto a máquina '
                           'recebe duas doses. Quem fez o mapa precisa corrigir; para gerar assim mesmo, com o usuário ciente, --aceitar-sobreposicao')

    geoms = [f['geometry'] for f in feicoes]
    doses_saida, relato_juncao = list(finais), []
    if args.juntar:
        geoms, doses_saida, relato_juncao = juntar_por_dose(feicoes, finais, casas, src)
    if args.separar_partes:
        geoms, doses_saida = separar_partes(geoms, doses_saida)
    para_graus = projecao.conversor(src, projecao.geo('WGS 84'))
    geoms_graus = [geom.mapear(g, para_graus) for g in geoms]
    areas_saida, _, _ = geom.medir([{'geometry': g, 'properties': {}} for g in geoms_graus], projecao.geo('WGS 84'))
    saida = R.resumo(doses_saida, areas_saida)
    if abs(saida['area_ha'] - depois['area_ha']) > max(1e-4, depois['area_ha'] * 1e-5) or \
            abs(saida['total'] - depois['total']) > max(1e-3, abs(depois['total']) * 1e-5):
        raise R.Recusa(f'a junção mudou a área ou o total de produto (área {depois["area_ha"]:.4f} → {saida["area_ha"]:.4f} ha; '
                       f'dose × área {depois["total"]:.3f} → {saida["total"]:.3f}). Não gravei: rode sem --juntar e avise')

    arquivos = pacote.shapefile_de_maquina(geoms_graus, doses_saida, campo_saida, casas)
    dados_zip = pacote.montar_zip(arquivos, chave, nome)
    ok, conferencia = pacote.conferir(dados_zip, chave, nome, campo_saida, casas, doses_saida, areas_saida)
    if not ok:
        raise R.Recusa('o arquivo gravado não passou na releitura: ' + '; '.join(l for l in conferencia if l.startswith('ERRADO')))
    pasta.mkdir(parents=True, exist_ok=True)
    nome_zip = f'{nome}_{chave}.zip'
    (pasta / nome_zip).write_bytes(dados_zip)

    un_total = R.unidade_do_total(unidade_final)
    mudados = [(indices[k], areas[k], doses[k], finais[k], r['mudancas'][k]) for k in range(len(finais)) if r['mudancas'][k]]
    with open(pasta / 'mudancas.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['poligono_do_arquivo', 'area_ha', 'dose_no_arquivo', 'unidade_do_arquivo', 'dose_final', 'unidade_final', 'o_que_mudou'])
        for k in range(len(finais)):
            passos = '; '.join(f'{p}: {R.g(de)} -> {R.g(ate)}' for p, de, ate in r['mudancas'][k])
            w.writerow([indices[k], f'{areas[k]:.4f}'.replace('.', ','), f'{R.g(doses[k])}'.replace('.', ','), unidade,
                        f'{finais[k]:.{casas}f}'.replace('.', ','), unidade_final, passos])
    with open(pasta / 'conferencia.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['ID', campo_saida, 'unidade', 'area_ha', 'dose_x_area'])
        for k, (d, a) in enumerate(zip(doses_saida, areas_saida), 1):
            w.writerow([k, f'{d:.{casas}f}'.replace('.', ','), unidade_final, f'{a:.4f}'.replace('.', ','), f'{d * a:.3f}'.replace('.', ',')])
    (pasta / 'passo-a-passo.md').write_text('\n'.join(C.passo_a_passo(chave, nome, campo_saida, unidade_final)) + '\n', encoding='utf-8')

    def faixa(s):
        linha = f'{len(finais)} polígono(s); dose de {R.g(s["minima"])} a {R.g(s["maxima"])} {unidade_final}; média ponderada pela área {num(s["media"], 3)} {unidade_final}'
        return linha + (f'; total de produto {num(s["total"], 2)} {un_total}' if un_total else '')
    c = C.CONTROLADORES[chave]
    rel = [f'# Arquivo de aplicação para {c["nome"]}', '',
           f'Entrada: camada "{camada["nome"]}" ({camada["formato"]}), {len(camada["feicoes"])} feição(ões), {projecao.nome(src)} ({src.get("origem", "")}).',
           f'Saída: `{nome_zip}`, para extrair na raiz do pen drive. Dentro dele: `{C.caminho_no_pen_drive(chave, nome)}`, `.shx` e `.dbf`.', '',
           '## Escolhas informadas pelo usuário', '',
           f'- Controlador: {c["nome"]}.', f'- Produto: {R.NOME_DO_PRODUTO[produto]}. Unidade da dose no arquivo: {unidade}.',
           f'- Dose: {origem_dose}.', f'- Nome no pen drive: {nome}' + (f' (pedido: "{args.nome}")' if nome != args.nome else '') + '.',
           f'- Campo da dose no arquivo de máquina: {campo_saida}, numérico, com {casas} casa(s) decimal(is).']
    rel += [f'- {p}.' for p in relato_dose]
    rel += ['', '## O que foi conferido e ajustado', '',
            f'- Só `.shp`, `.shx` e `.dbf` no pacote: sem `.prj`, `.cpg` nem outros.',
            f'- Coordenadas em graus decimais, sem arquivo de projeção' + (f' (o arquivo veio em {projecao.nome(src)} e foi levado a graus)' if src['tipo'] == 'utm' else '') + '; polígonos sem Z nem M.',
            f'- Campo da dose numérico. Campos do `.dbf`: ID e {campo_saida}; os outros campos do arquivo não foram levados.',
            f'- Nome curto, só com letras e números: {nome} ({len(nome)} caracteres).',
            f'- Unidade {unidade_final} coerente com produto {R.NOME_DO_PRODUTO[produto]}.']
    for aviso in R.avisos_de_grandeza(finais, unidade_final):
        rel.append(f'- ATENÇÃO: {aviso}.')
    if trabalho['outras'] or trabalho['vazias'] or trabalho['perdidos']:
        rel.append(f'- Ficaram fora, por não serem polígono com área: {len(trabalho["outras"])} ponto(s) ou linha(s), '
                   f'{len(trabalho["vazias"])} sem geometria e {len(trabalho["perdidos"])} sem área.')
    if trabalho['consertos']:
        rel.append(f'- Geometria: {len(trabalho["consertos"])} polígono(s) consertado(s) ou a conferir (' + ' | '.join(trabalho['consertos'][:5]) + ').')
    if sob is None:
        rel.append(f'- Sobreposição entre polígonos: NÃO conferida (mais de {LIMITE_SOBREPOSICAO} polígonos). Confira no QGIS.')
    elif sob['sobrepostos']:
        rel.append(f'- ATENÇÃO: {len(sob["sobrepostos"])} par(es) de polígonos se sobrepõem. O arquivo saiu assim, com o usuário ciente.')
    elif sob['dissolvido']:
        rel.append('- Sobreposição entre polígonos: nenhuma.' + (f' Frestas estreitas: {sob["frestas"]} ({num(sob["area_frestas_m2"], 1)} m²); nelas a máquina fica sem dose.' if sob['frestas'] else ''))
    if depois['com_zero']:
        rel.append(f'- {depois["com_zero"]} polígono(s) com dose ZERO. Em alguns monitores a dose zero desliga as seções: confirme com o usuário que é isso que ele quer.')
    rel += ['', '## A dose, antes e depois', '', f'- No arquivo recebido (na unidade {unidade_final}): {faixa(antes)}.',
            f'- No arquivo de máquina: {faixa(depois)}.']
    if r['passos']:
        rel += [f'- {p}.' for p in r['passos']]
        dif_media = depois['media'] - antes['media']
        linha = f'- Efeito dos ajustes: {len(mudados)} polígono(s) mudaram; a média ponderada mudou {sinal(dif_media, 3)} {unidade_final}'
        if un_total and antes['total']:
            linha += (f'; o total de produto mudou {sinal(depois["total"] - antes["total"], 2)} {un_total} '
                      f'({sinal((depois["total"] / antes["total"] - 1) * 100, 2)}%)')
        rel.append(linha + '.')
    else:
        rel.append('- Nenhuma dose foi alterada: nem conversão, nem degrau, nem limite foram pedidos.')
    if mudados:
        rel += ['', f'### Polígonos com a dose alterada ({len(mudados)}; a lista inteira está em `mudancas.csv`)', '',
                '| Polígono do arquivo | Área (ha) | Dose recebida | Dose final | O que mudou |', '|---|---|---|---|---|']
        for i, a, d0, d1, passos in mudados[:60]:
            rel.append(f'| {i} | {num(a, 4)} | {R.g(d0 * fator)} | {R.g(d1)} | ' + '; '.join(f'{p}: {R.g(de)} → {R.g(ate)}' for p, de, ate in passos) + ' |')
    rel += ['', '## Polígonos', '',
            f'- Recebidos com dose: {len(finais)}. No arquivo de máquina: {len(doses_saida)}'
            + (' (juntados os vizinhos de mesma dose' if args.juntar else ' (sem junção') + (', partes separadas' if args.separar_partes else '') + ').',
            f'- Área: {num(depois["area_ha"], 4)} ha recebidos, {num(saida["area_ha"], 4)} ha no arquivo de máquina.']
    if un_total:
        rel.append(f'- Total de produto (dose × área): {num(depois["total"], 2)} {un_total} antes da junção, {num(saida["total"], 2)} {un_total} no arquivo de máquina.')
    rel += [f'- {p}.' for p in relato_juncao]
    rel.append(f'- Tamanho: {num(len(arquivos["shp"]) / 1024, 1)} KB o `.shp`, {num(len(arquivos["dbf"]) / 1024, 1)} KB o `.dbf`; '
               f'{sum(geom.n_vertices(g) for g in geoms_graus)} vértices.')
    rel += ['', '## Releitura do arquivo gravado', ''] + [f'- {l}.' for l in conferencia]
    rel += ['', '## O que NÃO foi conferido', '',
            '- O arquivo não foi carregado em monitor nenhum. A conferência é do formato; quem confirma que a máquina leu é o operador, olhando a dose de dois ou três polígonos no monitor.',
            f'- Limite de polígonos e tamanho máximo do arquivo do {c["nome"]}: {C.NAO_CONFIRMADO}.',
            '- Se a unidade informada é a que a recomendação usou: o arquivo não diz a unidade; vale a que o usuário informou.',
            '- A dose em si: a skill não avalia se a dose está certa para a área.', '',
            f'Pasta do pen drive: {c["fonte_pasta"]}.']
    rel += [f'Do fabricante: {o}.' for o in c['oficial']]
    (pasta / 'relatorio.md').write_text('\n'.join(rel) + '\n', encoding='utf-8')

    sai(f'CONTROLADOR: {c["nome"]}. Arquivo: {pasta / nome_zip} (extrair na raiz do pen drive; dentro: {C.caminho_no_pen_drive(chave, nome)}, .shx e .dbf)')
    sai(f'DOSE: {origem_dose}; produto {R.NOME_DO_PRODUTO[produto]}; unidade no arquivo de máquina: {unidade_final}; campo {campo_saida}')
    for p in relato_dose + r['passos'] + relato_juncao:
        sai(f'  {p}')
    sai(f'ANTES:  {faixa(antes)}')
    sai(f'DEPOIS: {faixa(depois)}' + (f'  ({len(mudados)} polígono(s) com a dose alterada: veja relatorio.md)' if mudados else '  (nenhuma dose alterada)'))
    sai(f'POLÍGONOS: {len(finais)} recebidos, {len(doses_saida)} no arquivo de máquina; área {num(saida["area_ha"], 4)} ha')
    for aviso in R.avisos_de_grandeza(finais, unidade_final):
        sai(f'ATENÇÃO: {aviso}')
    if depois['com_zero']:
        sai(f'ATENÇÃO: {depois["com_zero"]} polígono(s) com dose zero: confirme com o usuário')
    sai('CONFERÊNCIA: o zip foi relido: ' + '; '.join(l.replace('certo: ', '') for l in conferencia[-4:]) + ' — CONFERE')
    sai(f'Também em {pasta}: relatorio.md, passo-a-passo.md, conferencia.csv e mudancas.csv')
    sai('NÃO conferido: o arquivo não foi carregado num monitor. O operador confere a dose de dois ou três polígonos na tela antes de aplicar')
    return pasta / nome_zip


def demo(pasta, sai):
    import sintetico
    pasta.mkdir(parents=True, exist_ok=True)
    entrada = pasta / 'mapa_inventado.geojson'
    entrada.write_text(sintetico.geojson(sintetico.grade()), encoding='utf-8')
    sai('DEMONSTRAÇÃO com um talhão INVENTADO de 27 ha, em 300 células de 30 m, com a dose em kg/ha no campo DOSE.')
    sai('O controlador, o produto, a unidade e o nome abaixo foram fixados só para o exemplo: no uso real, quem informa é o usuário.')
    sai('')
    sai('--- 1. diagnóstico ---')
    principal([str(entrada), '--diagnostico', '--campo-dose', 'DOSE'], sai)
    sai('')
    sai('--- 2. arquivo para o controlador, juntando os vizinhos de mesma dose ---')
    return principal([str(entrada), '--controlador', 'stara', '--produto', 'solido', '--unidade', 'kg/ha', '--campo-dose', 'DOSE',
                      '--nome', 'ADUBO01', '--juntar', '--saida', str(pasta)], sai)


def argumentos(argv):
    p = argparse.ArgumentParser(description='Adequa o mapa de aplicação ao monitor da máquina (só formato: a dose é do usuário).')
    p.add_argument('arquivo', nargs='?', help='o mapa: shapefile (.zip ou .shp), GeoJSON, KML ou KMZ')
    p.add_argument('--diagnostico', action='store_true', help='só mostra o que o arquivo tem')
    p.add_argument('--camada', help='qual camada usar, quando o zip traz mais de uma')
    p.add_argument('--src-entrada', help='sistema de coordenadas do arquivo, quando ele não diz (ex.: utm22s)')
    p.add_argument('--controlador', help='o monitor: ' + ', '.join(C.CONTROLADORES))
    p.add_argument('--produto', help='solido, liquido ou semente')
    p.add_argument('--unidade', help='a unidade da dose no arquivo: kg/ha, t/ha, l/ha, m3/ha, sem/ha ou sem/m')
    p.add_argument('--campo-dose', help='o campo do arquivo que traz a dose')
    p.add_argument('--campo-zona', help='o campo que identifica a zona (com --tabela-doses)')
    p.add_argument('--tabela-doses', help='a dose de cada zona, informada pelo usuário: "1=120;2=180;3=240" ou um arquivo zona;dose')
    p.add_argument('--nome', help='nome do arquivo no pen drive (até 8 letras e números)')
    p.add_argument('--campo-saida', help='nome do campo da dose no arquivo de máquina (padrão: o do arquivo, limpo)')
    p.add_argument('--converter-para', help='converte a dose para outra unidade do mesmo tipo de produto')
    p.add_argument('--espacamento-m', type=float, help='espaçamento entre linhas, em metros (só para converter sem/ha e sem/m)')
    p.add_argument('--degrau', type=float, help='arredonda a dose ao múltiplo deste valor (o degrau que a máquina aceita)')
    p.add_argument('--minimo', type=float, help='menor dose que a máquina aplica')
    p.add_argument('--maximo', type=float, help='maior dose que a máquina aplica')
    p.add_argument('--fora-do-limite', choices=['recusar', 'cortar'], default='recusar', help='o que fazer com dose fora do limite (padrão: parar e listar)')
    p.add_argument('--casas', type=int, choices=range(0, 5), help='casas decimais da dose (padrão: as que os valores pedem)')
    p.add_argument('--sem-dose', choices=['zero', 'tirar'], help='polígono sem dose: sai com zero ou fica fora (escolha do usuário)')
    p.add_argument('--juntar', action='store_true', help='junta os polígonos vizinhos de mesma dose (arquivo mais leve)')
    p.add_argument('--separar-partes', action='store_true', help='grava cada parte de um multipolígono como um polígono')
    p.add_argument('--aceitar-sobreposicao', action='store_true', help='gera mesmo com polígonos sobrepostos de doses diferentes')
    p.add_argument('--saida', default='saida-aplicacao', help='pasta de saída')
    p.add_argument('--demo', action='store_true', help='roda com um talhão inventado')
    return p.parse_args(argv)


def principal(argv=None, sai=print):
    args = argumentos(argv)
    try:
        if args.demo:
            return demo(Path(args.saida), sai)
        if not args.arquivo:
            raise R.Recusa('informe o arquivo do mapa de aplicação, ou --demo. Ajuda: --help')
        camada = escolher_camada(ler_entrada(args.arquivo), args.camada)
        src = resolver_src(camada, args.src_entrada)
        trabalho = preparar(camada, src)
        if args.diagnostico:
            diagnostico(camada, trabalho, args, sai)
            return 0
        return executar(camada, trabalho, args, Path(args.saida), sai)
    except R.Recusa as e:
        sai(f'NÃO GEREI: {e}')
        return None


if __name__ == '__main__':
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, 'reconfigure'):
            fluxo.reconfigure(encoding='utf-8')
    if len(sys.argv) == 1:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            linhas = []
            zip_gerado = principal(['--demo', '--saida', tmp], linhas.append)
            assert zip_gerado and Path(zip_gerado).name == 'ADUBO01_stara.zip', linhas[-6:]
            texto_ = '\n'.join(linhas)
            assert 'CONFERE' in texto_ and '300 recebidos' in texto_ and 'nenhuma dose alterada' in texto_, texto_[-900:]
            assert (Path(tmp) / 'relatorio.md').exists() and (Path(tmp) / 'passo-a-passo.md').exists()
            recusas = []
            assert principal([str(Path(tmp) / 'mapa_inventado.geojson'), '--controlador', 'verion', '--produto', 'solido', '--unidade', 'kg/ha',
                              '--campo-dose', 'DOSE', '--nome', 'A'], recusas.append) is None and 'formato próprio' in recusas[-1]
            assert principal([str(Path(tmp) / 'mapa_inventado.geojson'), '--controlador', 'stara', '--produto', 'solido',
                              '--campo-dose', 'DOSE', '--nome', 'A'], recusas.append) is None and 'falta a unidade' in recusas[-1]
        print('aplicacao OK: demonstração do diagnóstico ao zip conferido, Verion recusado, unidade exigida')
        sys.exit(0)
    sys.exit(0 if principal() is not None else 2)
