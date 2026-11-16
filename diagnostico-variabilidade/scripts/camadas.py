"""Lê o perímetro e as camadas, leva tudo para a grade comum e descreve cada
camada antes de qualquer conta (o diagnóstico).

Entradas:
  perímetro  GeoJSON, KML, shapefile ou WKT (graus ou UTM com zona)
  rasters    "nome=arquivo.tif" (ou "nome=arquivo.tif:2" para a banda 2)
  pontos     "arquivo.csv" ou "prefixo=arquivo.csv": cada coluna numérica vira uma
             camada candidata (CSV, TXT, shapefile de pontos, .zip ou GeoJSON)
  classes    "nome=arquivo.geojson" (ou "...:campo"): polígonos com a classe de
             cada um (zona de manejo, variedade, talhão)

Teste embutido: python scripts/camadas.py
"""

import re
from pathlib import Path

import numpy as np

import areas as mod_areas
import geometria
import geotiff
import leitura
import malha
from espacial import Defasagens
from relacoes import QUASE_IGUAL, REDUNDANTE

COBERTURA_BAIXA = 60.0


class EntradaInvalida(Exception):
    """O que foi enviado não serve para a análise. A mensagem diz o que fazer."""


def _zona(texto):
    if not texto:
        return None
    m = re.fullmatch(r'\s*(\d{1,2})\s*([nNsS])\s*', str(texto))
    if not m or not 1 <= int(m.group(1)) <= 60:
        raise EntradaInvalida(f'zona UTM no formato 22S ou 21N (recebido: {texto!r})')
    return int(m.group(1)), m.group(2).upper() == 'S'


def _par(item, opcao, obrigatorio=True):
    nome, sep, resto = str(item).partition('=')
    if not sep or re.match(r'^[A-Za-z]:[\\/]', item) and len(nome) == 1:      # caminho do Windows sem nome
        if obrigatorio:
            raise EntradaInvalida(f'{opcao} no formato nome=arquivo (recebido: {item!r})')
        return None, str(item).strip()
    if not nome.strip():
        raise EntradaInvalida(f'{opcao} no formato nome=arquivo (recebido: {item!r})')
    return nome.strip(), resto.strip()


def _sufixo(resto, padrao):
    """'arquivo.tif:2' -> ('arquivo.tif', '2'), sem confundir com a letra da unidade do Windows."""
    m = re.search(padrao, resto)
    if m and not Path(resto).exists():
        return resto[:m.start()], m.group(1)
    return resto, None


def nome_limpo(texto):
    return re.sub(r'[\s,;=]+', '_', str(texto).strip()).strip('_')


def parece_identificador(v):
    v = v[np.isfinite(v)]
    return len(v) > 10 and bool(np.all(v == np.round(v))) and len(np.unique(v)) > 0.95 * len(v)


def _tabela_de_pontos(caminho, coluna_x, coluna_y):
    """Devolve dict: x, y, crs, zona, origem, colunas {nome: vetor numérico}, ignoradas [nomes]."""
    arq = Path(caminho)
    if not arq.exists():
        raise EntradaInvalida(f'não achei o arquivo de pontos {caminho}')
    if arq.suffix.lower() in ('.geojson', '.json', '.kml'):
        props, coords, crs, zona = geometria.ler_pontos(arq)
        x, y = np.array([c[0] for c in coords], float), np.array([c[1] for c in coords], float)
        chaves = list(dict.fromkeys(k for p in props for k in p))
        dados, numericas = {}, []
        for k in chaves:
            v = np.full(len(props), np.nan)
            for i, p in enumerate(props):
                try:
                    v[i] = float(str(p.get(k, '')).replace(',', '.'))
                except (TypeError, ValueError):
                    pass
            if np.isfinite(v).mean() >= 0.8:
                dados[k] = v
                numericas.append(k)
        cx = cy = None
    else:
        t = leitura.ler_pontos(arq, coluna_x, coluna_y)
        x, y, crs, zona = t['x'], t['y'], t['crs'], t['zona']
        dados, numericas, cx, cy = t['dados'], t['numericas'], t['coluna_x'], t['coluna_y']
    colunas, ignoradas = {}, []
    for k in numericas:
        if k in (cx, cy):
            continue
        v = np.asarray(dados[k], float)
        if parece_identificador(v):
            ignoradas.append(k)
        else:
            colunas[k] = v
    return {'x': x, 'y': y, 'crs': crs, 'zona': zona, 'origem': arq.name, 'colunas': colunas, 'ignoradas': ignoradas}


def carregar(perimetro, rasters=(), pontos=(), classes=(), celula=None, zona=None, coluna_x=None, coluna_y=None):
    """Lê tudo e monta a grade. Devolve o estado: grade, zona, camadas numéricas, camadas de classes e avisos."""
    if not perimetro:
        raise EntradaInvalida('informe o perímetro do talhão (--perimetro)')
    if not rasters and not pontos:
        raise EntradaInvalida('informe as camadas: --raster nome=arquivo.tif, --pontos arquivo.csv, ou os dois')
    try:
        lidas, crs, zona_arq = mod_areas.ler_areas(perimetro)
        areas, z, sul = mod_areas.para_utm(lidas, crs, _zona(zona) or zona_arq)
    except (ValueError, OSError) as erro:
        raise EntradaInvalida(f'perímetro: {erro}')
    area_m2 = sum(mod_areas.area_ha(a['aneis']) for a in areas) * 10000
    if area_m2 <= 0:
        raise EntradaInvalida('perímetro: a área deu zero')
    lado = float(celula) if celula else malha.celula_automatica(area_m2)
    if not 1 <= lado <= 500:
        raise EntradaInvalida('a célula vai de 1 a 500 m')
    try:
        g = malha.montar(areas, lado)
    except ValueError as erro:
        raise EntradaInvalida(str(erro))
    estado = {'areas': areas, 'zona': z, 'sul': sul, 'grade': g, 'area_ha': area_m2 / 10000, 'celula': lado,
              'celula_automatica': not celula, 'celulas': int(g['mascara'].sum()), 'camadas': {}, 'classes': {}, 'avisos': [],
              'ignoradas': []}

    def registrar(nome, grade_da_camada, info):
        if nome in estado['camadas'] or nome in estado['classes']:
            raise EntradaInvalida(f'duas camadas com o nome "{nome}": dê nomes diferentes (em --raster, ou um prefixo em --pontos)')
        resumo = malha.descrever(g, grade_da_camada)
        if resumo['celulas'] == 0:
            raise EntradaInvalida(f'a camada "{nome}" não tem nenhum valor dentro do perímetro: confira se o arquivo é deste '
                                  'talhão e o sistema de coordenadas')
        estado['camadas'][nome] = {'malha': grade_da_camada, 'info': info, 'resumo': resumo}

    for item in rasters:
        nome, resto = _par(item, '--raster')
        resto, banda = _sufixo(resto, r':(\d+)$')
        try:
            r = geotiff.ler_geotiff(resto, int(banda) if banda else 1)
        except (ValueError, OSError, KeyError) as erro:
            raise EntradaInvalida(f'raster "{nome}": {erro}')
        grade_da_camada, info = malha.de_raster(g, r, z, sul)
        info['arquivo'] = Path(resto).name
        registrar(nome_limpo(nome), grade_da_camada, info)

    for item in pontos:
        prefixo, resto = _par(item, '--pontos', obrigatorio=False)
        try:
            t = _tabela_de_pontos(resto, coluna_x, coluna_y)
        except ValueError as erro:
            raise EntradaInvalida(f'pontos ({Path(resto).name}): {erro}')
        if t['crs'] == 'utm':
            if t['zona'] and t['zona'] != (z, sul):
                raise EntradaInvalida(f'pontos ({t["origem"]}) em UTM {t["zona"][0]}{"S" if t["zona"][1] else "N"} e perímetro em '
                                      f'UTM {z}{"S" if sul else "N"}: reprojete os pontos para o mesmo sistema')
            if not t['zona']:
                estado['avisos'].append(f'{t["origem"]}: coordenadas em metros sem indicação de fuso; tratadas como UTM '
                                        f'{z}{"S" if sul else "N"}, o do perímetro')
            px, py = np.asarray(t['x'], float), np.asarray(t['y'], float)
        else:
            px, py, _, _ = leitura.projetar(t['x'], t['y'], 'geo', (z, sul))
        if not t['colunas']:
            raise EntradaInvalida(f'pontos ({t["origem"]}): nenhuma coluna numérica além das coordenadas')
        estado['ignoradas'] += [f'{k} ({t["origem"]}: parece identificador)' for k in t['ignoradas']]
        dentro_total = 0
        for coluna, valores in t['colunas'].items():
            grade_da_camada, info = malha.de_pontos(g, px, py, valores)
            dentro_total = max(dentro_total, info['pontos_dentro'])
            if info['pontos_dentro'] == 0:
                continue
            info.update(arquivo=t['origem'], coluna=coluna)
            registrar(nome_limpo(f'{prefixo}.{coluna}' if prefixo else coluna), grade_da_camada, info)
        if dentro_total == 0:
            raise EntradaInvalida(f'pontos ({t["origem"]}): nenhum ponto cai dentro do perímetro. Confira o sistema de '
                                  'coordenadas e se o arquivo é deste talhão')

    for item in classes:
        nome, resto = _par(item, '--classes')
        resto, campo = _sufixo(resto, r':([^:\\/]+)$')
        try:
            lidas_c, crs_c, zona_c = mod_areas.ler_areas(resto, campo)
            if crs_c == 'utm' and zona_c and zona_c != (z, sul):
                raise ValueError(f'polígonos em UTM {zona_c[0]}{"S" if zona_c[1] else "N"} e perímetro em UTM {z}{"S" if sul else "N"}')
            areas_c, _, _ = mod_areas.para_utm(lidas_c, crs_c, (z, sul))
        except (ValueError, OSError) as erro:
            raise EntradaInvalida(f'classes "{nome}": {erro}')
        rotulos, nomes = malha.de_classes(g, areas_c)
        nome = nome_limpo(nome)
        if nome in estado['camadas'] or nome in estado['classes']:
            raise EntradaInvalida(f'duas camadas com o nome "{nome}"')
        com = int((rotulos >= 0).sum())
        if com == 0:
            raise EntradaInvalida(f'classes "{nome}": nenhum polígono cobre o talhão')
        estado['classes'][nome] = {'rotulos': rotulos, 'nomes': nomes, 'arquivo': Path(resto).name,
                                   'cobertura_pct': 100.0 * com / estado['celulas'],
                                   'celulas_por_classe': {c: int((rotulos == i).sum()) for i, c in enumerate(nomes)}}
    if not estado['camadas']:
        raise EntradaInvalida('nenhuma camada numérica para analisar')
    return estado


def diagnosticar(estado):
    """Descreve cada camada e o conjunto, sem escolher nada. Devolve dict pronto para o relato e o JSON."""
    g = estado['grade']
    mascara = g['mascara']
    nomes = list(estado['camadas'])
    linhas = []
    for nome in nomes:
        c = estado['camadas'][nome]
        m, r, info = c['malha'], c['resumo'], c['info']
        linha = {'nome': nome, **{k: info.get(k) for k in ('tipo', 'arquivo', 'coluna', 'src', 'pixel_m', 'espacamento_m',
                                                           'pontos_dentro', 'pontos_por_celula')}, **r, 'notas': []}
        valida = mascara & np.isfinite(m)
        constante = r['desvio'] is not None and (r['desvio'] <= 0 or r['distintos'] < 3)
        linha['constante'] = bool(constante)
        if constante:
            linha['notas'].append('quase constante: não serve para a análise')
        elif r['celulas'] >= 30:
            d = Defasagens(valida, g['celula'])
            s, v = d.somas(m)
            alcance, limitada = d.distancia_de_correlacao(d.correlograma(s, v))
            n_ef, _ = d.tamanho_efetivo(s, v, s, v)
            linha.update(distancia_de_correlacao_m=alcance, distancia_limitada=limitada, unidades_independentes=n_ef)
            if n_ef < 30:
                linha['notas'].append(f'varia devagar no talhão: as {r["celulas"]:,} células valem cerca de {n_ef:.0f} observações independentes'.replace(',', '.'))
        if r['distintos'] <= 10 and not constante:
            linha['notas'].append(f'só {r["distintos"]} valores diferentes: se for uma camada de classes, envie os polígonos em --classes')
        if r['cobertura_pct'] < COBERTURA_BAIXA:
            if info.get('tipo') == 'pontos':
                linha['notas'].append(f'cobre {r["cobertura_pct"]:.0f}% das células: pontos esparsos para esta célula. Interpole antes '
                                      '(skills de interpolação) ou aumente a célula')
            else:
                linha['notas'].append(f'cobre só {r["cobertura_pct"]:.0f}% do talhão')
        if info.get('mais_grossa_que_a_celula'):
            linha['notas'].append(f'pixel de {info["pixel_m"]:.0f} m, maior que a célula de {g["celula"]:g} m: células vizinhas repetem o mesmo pixel')
        linhas.append(linha)
    uteis = [n for n, l in zip(nomes, linhas) if not l['constante']]
    todas = mascara.copy()
    for n in uteis:
        todas &= np.isfinite(estado['camadas'][n]['malha'])
    for c in estado['classes'].values():
        todas &= c['rotulos'] >= 0
    pares = []
    for i, a in enumerate(uteis):
        for b in uteis[i + 1:]:
            ma, mb = estado['camadas'][a]['malha'], estado['camadas'][b]['malha']
            ok = mascara & np.isfinite(ma) & np.isfinite(mb)
            if ok.sum() < 30 or ma[ok].std() <= 0 or mb[ok].std() <= 0:
                continue
            r = float(np.corrcoef(ma[ok], mb[ok])[0, 1])
            if abs(r) >= REDUNDANTE:
                pares.append({'a': a, 'b': b, 'r': r, 'celulas': int(ok.sum()), 'quase_iguais': abs(r) >= QUASE_IGUAL})
    pares.sort(key=lambda p: -abs(p['r']))
    return {'area_ha': estado['area_ha'], 'utm': f'{estado["zona"]}{"S" if estado["sul"] else "N"}', 'celula_m': estado['celula'],
            'celula_automatica': estado['celula_automatica'], 'celulas_no_perimetro': estado['celulas'], 'camadas': linhas,
            'classes': [{'nome': n, 'arquivo': c['arquivo'], 'cobertura_pct': c['cobertura_pct'], 'celulas_por_classe': c['celulas_por_classe']}
                        for n, c in estado['classes'].items()],
            'celulas_completas_com_todas': int(todas.sum()), 'pares_parecidos': pares, 'ignoradas': estado['ignoradas'],
            'avisos': list(estado['avisos'])}


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    import tempfile

    import sintetico
    assert _zona('22S') == (22, True) and _zona('21n') == (21, False) and _zona('') is None
    assert _par('argila=c:/x/a.tif', '--raster') == ('argila', 'c:/x/a.tif')
    assert _par('C:/dados/p.csv', '--pontos', obrigatorio=False) == (None, 'C:/dados/p.csv')
    assert _par('ce=p.csv', '--pontos', obrigatorio=False) == ('ce', 'p.csv')
    assert _sufixo('mapa.tif:2', r':(\d+)$') == ('mapa.tif', '2') and nome_limpo(' prod (t/ha), 2024 ') == 'prod_(t/ha)_2024'
    with tempfile.TemporaryDirectory() as pasta:
        e = sintetico.gravar(pasta)
        p = e['pasta']
        estado = carregar(str(p / 'talhao.geojson'),
                          rasters=[f'argila={p / "argila_g_kg.tif"}', f'argila_outra={p / "argila_outra_g_kg.tif"}',
                                   f'altitude={p / "altitude_m.tif"}', f'ph={p / "ph.tif"}'],
                          pontos=[str(p / 'colheita_limpa.csv')], classes=[f'variedade={p / "variedades.geojson"}:variedade'])
        assert list(estado['camadas']) == ['argila', 'argila_outra', 'altitude', 'ph', 'prod_t_ha'], list(estado['camadas'])
        assert estado['celula'] == 10.0 and 5200 < estado['celulas'] < 5400 and 50 < estado['area_ha'] < 56
        assert estado['ignoradas'] == ['id (colheita_limpa.csv: parece identificador)']
        assert estado['camadas']['argila']['info']['pontos_por_celula'] == 4          # raster de 5 m em célula de 10 m
        assert estado['classes']['variedade']['nomes'] == ['A', 'B']
        d = diagnosticar(estado)
        por_nome = {l['nome']: l for l in d['camadas']}
        assert por_nome['prod_t_ha']['cobertura_pct'] > 97 and por_nome['prod_t_ha']['tipo'] == 'pontos'
        assert por_nome['ph']['notas'] and 'maior que a célula' in por_nome['ph']['notas'][-1]
        assert por_nome['argila']['distancia_de_correlacao_m'] > por_nome['prod_t_ha']['distancia_de_correlacao_m'] > 10
        assert por_nome['argila']['unidades_independentes'] < 100
        assert d['pares_parecidos'][0]['a'] == 'argila' and d['pares_parecidos'][0]['b'] == 'argila_outra' and d['pares_parecidos'][0]['quase_iguais']
        assert d['celulas_completas_com_todas'] > 0.95 * d['celulas_no_perimetro']
        # com célula de 5 m os pontos da colheita ficam esparsos (um ponto a cada 5 × 8 m)
        fino = diagnosticar(carregar(str(p / 'talhao.geojson'), pontos=[str(p / 'colheita_limpa.csv')], celula=5))
        assert fino['camadas'][0]['cobertura_pct'] < 70
        recusas = [
            (dict(perimetro=None, rasters=['a=b.tif']), 'informe o perímetro'),
            (dict(perimetro=str(p / 'talhao.geojson')), 'informe as camadas'),
            (dict(perimetro=str(p / 'talhao.geojson'), rasters=[str(p / 'ph.tif')]), 'nome=arquivo'),
            (dict(perimetro=str(p / 'talhao.geojson'), rasters=[f'ph={p / "nao_existe.tif"}']), 'raster "ph"'),
            (dict(perimetro=str(p / 'talhao.geojson'), rasters=[f'ph={p / "ph.tif"}', f'ph={p / "altitude_m.tif"}']), 'duas camadas com o nome'),
            (dict(perimetro=str(p / 'talhao.geojson'), rasters=[f'ph={p / "ph.tif"}'], celula=0.2), 'a célula vai de'),
            (dict(perimetro=str(p / 'talhao.geojson'), rasters=[f'ph={p / "ph.tif"}'], zona='99X'), 'zona UTM'),
        ]
        # raster de outro lugar: não cobre o talhão
        geotiff.escrever_geotiff(str(p / 'longe.tif'), np.ones((20, 20)), 300000.0, 7000000.0, 10.0, 31982)
        recusas.append((dict(perimetro=str(p / 'talhao.geojson'), rasters=[f'x={p / "longe.tif"}']), 'não tem nenhum valor dentro do perímetro'))
        # pontos de outro lugar
        (p / 'fora.csv').write_text('lon;lat;v\n-40,1;-10,2;1\n-40,2;-10,3;2\n-40,3;-10,4;3\n', encoding='utf-8')
        recusas.append((dict(perimetro=str(p / 'talhao.geojson'), pontos=[str(p / 'fora.csv')]), 'nenhum ponto cai dentro'))
        for argumentos, trecho in recusas:
            try:
                carregar(**argumentos)
            except EntradaInvalida as erro:
                assert trecho in str(erro), (trecho, str(erro))
            else:
                raise AssertionError(f'devia recusar: {trecho}')
    print(f'camadas OK (5 camadas e 1 de classes na grade de 10 m; {len(recusas)} recusas)')


if __name__ == '__main__':
    _autoteste()
