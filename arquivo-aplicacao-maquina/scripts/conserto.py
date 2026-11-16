"""Conserto de geometria: faz só o que é seguro e conta o resto.

Consertos seguros (não mudam a área, ou só tiram o que não tinha área):
- tirar vértice com coordenada inválida (vazia, infinita);
- tirar vértice repetido em seguida;
- fechar o anel (repetir o primeiro ponto no fim);
- tirar vértice de ida e volta (o contorno vai a um ponto e volta pelo mesmo caminho);
- dividir o anel que se toca num vértice em anéis simples;
- descartar anel, polígono ou linha que ficou sem área ou sem comprimento;
- acertar o sentido dos anéis (quem grava cada formato usa o sentido dele).

O que NÃO é consertado, só relatado, porque exigiria decidir pelo usuário onde
passa a divisa: contorno que se cruza (o "laço" ou "gravata") e furo traçado
fora do anel externo.
"""

import math

import numpy as np

import geom


def _limpar(seq):
    """Tira coordenada inválida e repetição em seguida. Devolve (seq, n_invalidos, n_repetidos)."""
    saida, invalidos, repetidos = [], 0, 0
    for p in seq:
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            invalidos += 1
            continue
        if not (math.isfinite(x) and math.isfinite(y)):
            invalidos += 1
        elif saida and saida[-1] == (x, y):
            repetidos += 1
        else:
            saida.append((x, y))
    return saida, invalidos, repetidos


def sem_area(pts):
    """Anel degenerado: menos de 3 pontos diferentes, ou todos na mesma reta."""
    unicos = set(pts)
    if len(unicos) < 3:
        return True
    a = np.asarray(list(unicos), dtype=float)
    a = a - a[0]
    longe = a[np.argmax((a ** 2).sum(axis=1))]
    desvio = np.abs(a[:, 0] * longe[1] - a[:, 1] * longe[0]) / math.hypot(longe[0], longe[1])
    return float(desvio.max()) <= 1e-9 * max(1.0, math.hypot(longe[0], longe[1]))


def dividir_em_toques(anel):
    """Anel fechado que passa duas vezes pelo mesmo vértice -> anéis simples (laço de ida e
    volta, sem área, some). Devolve a lista de anéis fechados."""
    caminho, pos, saida = [], {}, []
    for p in anel[:-1]:
        if p in pos:
            i = pos[p]
            laco = caminho[i:] + [p]
            for q in caminho[i + 1:]:
                del pos[q]
            caminho = caminho[:i + 1]
            if len(laco) >= 4:
                saida.append(laco)
        else:
            pos[p] = len(caminho)
            caminho.append(p)
    if len(caminho) >= 3:
        saida.append(caminho + [caminho[0]])
    return saida


def cruzamentos(anel, maximo=3):
    """Pontos em que o contorno se cruza ou encosta em si mesmo (fora os vértices vizinhos).
    Devolve até `maximo` pontos (x, y)."""
    a = np.asarray(anel[:-1], dtype=float)
    n = len(a)
    if n < 4:
        return []
    origem = a[0].copy()
    p = a - origem
    q = np.roll(p, -1, axis=0)
    minx, maxx = np.minimum(p[:, 0], q[:, 0]), np.maximum(p[:, 0], q[:, 0])
    miny, maxy = np.minimum(p[:, 1], q[:, 1]), np.maximum(p[:, 1], q[:, 1])
    ordem = np.argsort(minx, kind='stable')
    minx_ord = minx[ordem]
    achados = []
    for k in range(n):
        i = ordem[k]
        fim = np.searchsorted(minx_ord, maxx[i], side='right')
        js = ordem[k + 1:fim]
        if not len(js):
            continue
        js = js[(js != (i + 1) % n) & (js != (i - 1) % n) & (miny[js] <= maxy[i]) & (maxy[js] >= miny[i])]
        if not len(js):
            continue
        d, D = q[i] - p[i], q[js] - p[js]
        d1 = d[0] * (p[js, 1] - p[i, 1]) - d[1] * (p[js, 0] - p[i, 0])
        d2 = d[0] * (q[js, 1] - p[i, 1]) - d[1] * (q[js, 0] - p[i, 0])
        d3 = D[:, 0] * (p[i, 1] - p[js, 1]) - D[:, 1] * (p[i, 0] - p[js, 0])
        d4 = D[:, 0] * (q[i, 1] - p[js, 1]) - D[:, 1] * (q[i, 0] - p[js, 0])
        cruza = (d1 * d2 < 0) & (d3 * d4 < 0)

        def sobre(lo_x, hi_x, lo_y, hi_y, pt):
            return (pt[..., 0] >= lo_x) & (pt[..., 0] <= hi_x) & (pt[..., 1] >= lo_y) & (pt[..., 1] <= hi_y)
        toca = (((d1 == 0) & sobre(minx[i], maxx[i], miny[i], maxy[i], p[js])) | ((d2 == 0) & sobre(minx[i], maxx[i], miny[i], maxy[i], q[js]))
                | ((d3 == 0) & sobre(minx[js], maxx[js], miny[js], maxy[js], p[i])) | ((d4 == 0) & sobre(minx[js], maxx[js], miny[js], maxy[js], q[i])))
        for j, c, t in zip(js.tolist(), cruza.tolist(), toca.tolist()):
            if c:
                den = (d[0] * (q[j, 1] - p[j, 1]) - d[1] * (q[j, 0] - p[j, 0]))
                s = ((p[j, 0] - p[i, 0]) * (q[j, 1] - p[j, 1]) - (p[j, 1] - p[i, 1]) * (q[j, 0] - p[j, 0])) / den
                achados.append((float(p[i, 0] + s * d[0] + origem[0]), float(p[i, 1] + s * d[1] + origem[1])))
            elif t:
                achados.append((float(p[j, 0] + origem[0]), float(p[j, 1] + origem[1])))
            if len(achados) >= maximo:
                return achados
    return achados


def _coord(p):
    # graus com 6 casas, metros com 1
    return f'({p[0]:.6f}, {p[1]:.6f})' if abs(p[0]) <= 180 and abs(p[1]) <= 90 else f'({p[0]:.1f}, {p[1]:.1f})'


def _anel(seq, completo, mud, pend):
    """Conserta um anel. Devolve a lista de anéis fechados que ele virou (vazia = descartado)."""
    pts, invalidos, repetidos = _limpar(seq)
    if invalidos:
        mud['vértice(s) com coordenada inválida removido(s)'] = mud.get('vértice(s) com coordenada inválida removido(s)', 0) + invalidos
    if len(pts) >= 2 and pts[0] != pts[-1]:
        mud['anel(éis) fechado(s): faltava repetir o primeiro ponto'] = mud.get('anel(éis) fechado(s): faltava repetir o primeiro ponto', 0) + 1
        pts.append(pts[0])
    if repetidos:
        mud['vértice(s) repetido(s) em seguida removido(s)'] = mud.get('vértice(s) repetido(s) em seguida removido(s)', 0) + repetidos
    if len(pts) < 4 or sem_area(pts):
        mud['anel(éis) sem área descartado(s)'] = mud.get('anel(éis) sem área descartado(s)', 0) + 1
        return []
    aneis = [pts]
    if len(set(pts[:-1])) < len(pts) - 1:  # passa duas vezes por um mesmo vértice
        if completo:
            partes = [a for a in dividir_em_toques(pts) if not sem_area(a)]
            tirados = (len(pts) - 1) - sum(len(a) - 1 for a in partes) - (len(partes) - 1)
            if len(partes) > 1:
                mud['anel(éis) que se tocava(m) num vértice dividido(s) em anéis simples'] = mud.get('anel(éis) que se tocava(m) num vértice dividido(s) em anéis simples', 0) + 1
            if tirados > 0:
                mud['vértice(s) de ida e volta removido(s)'] = mud.get('vértice(s) de ida e volta removido(s)', 0) + tirados
            aneis = partes
        else:
            pend.append('o contorno passa duas vezes pelo mesmo vértice (--consertar divide em anéis simples)')
    for a in aneis:
        if len(a) - 1 > 200000:
            pend.append(f'anel com {len(a) - 1} vértices: o cruzamento do contorno não foi conferido')
            continue
        onde = list(dict.fromkeys(cruzamentos(a)))
        if onde:
            pend.append('o contorno se cruza ou encosta nele mesmo perto de ' + ', '.join(_coord(p) for p in onde)
                        + ': NÃO foi consertado (redesenhe a divisa no QGIS ou use Vetor > Geometria > Corrigir geometrias)')
    return aneis


def consertar(g, completo=True):
    """Devolve (geometria nova ou None, mudanças {descrição: quantas}, pendências [texto])."""
    mud, pend = {}, []
    if g is None:
        return None, mud, pend
    t, c = g['type'], g['coordinates']
    if t in ('Point', 'MultiPoint'):
        pts, invalidos, _ = _limpar([c] if t == 'Point' else c)
        if invalidos:
            mud['ponto(s) com coordenada inválida removido(s)'] = invalidos
        if not pts:
            return None, mud, pend
        return ({'type': 'Point', 'coordinates': pts[0]} if t == 'Point' or len(pts) == 1 and t == 'Point'
                else {'type': 'MultiPoint', 'coordinates': pts}), mud, pend
    if t in ('LineString', 'MultiLineString'):
        linhas = []
        for seq in ([c] if t == 'LineString' else c):
            pts, invalidos, repetidos = _limpar(seq)
            if invalidos:
                mud['vértice(s) com coordenada inválida removido(s)'] = mud.get('vértice(s) com coordenada inválida removido(s)', 0) + invalidos
            if repetidos and completo:
                mud['vértice(s) repetido(s) em seguida removido(s)'] = mud.get('vértice(s) repetido(s) em seguida removido(s)', 0) + repetidos
            elif repetidos:
                pts = [tuple(map(float, p[:2])) for p in seq if all(isinstance(v, (int, float)) and math.isfinite(v) for v in p[:2])]
            if len(set(pts)) >= 2:
                linhas.append(pts)
            else:
                mud['linha(s) com menos de 2 pontos descartada(s)'] = mud.get('linha(s) com menos de 2 pontos descartada(s)', 0) + 1
        if not linhas:
            return None, mud, pend
        return ({'type': 'LineString', 'coordinates': linhas[0]} if len(linhas) == 1 else {'type': 'MultiLineString', 'coordinates': linhas}), mud, pend
    saida = []
    for poli in geom.poligonos_de(g):
        dividiu, aneis = False, []
        for k, seq in enumerate(poli):
            partes = _anel(seq, completo, mud, pend)
            if k == 0 and not partes:
                mud['polígono(s) sem área descartado(s)'] = mud.get('polígono(s) sem área descartado(s)', 0) + 1
                aneis = []
                break
            dividiu = dividiu or len(partes) > 1
            aneis.append(partes)
        if not aneis:
            continue
        if dividiu:  # os papéis (externo ou furo) são refeitos pelo aninhamento
            saida += geom.organizar_aneis([a for partes in aneis for a in partes])
            continue
        externo = geom.orientar(aneis[0][0], True)
        furos = []
        for partes in aneis[1:]:
            for furo in partes:
                px, py = geom.ponto_interno(furo)
                if not geom.dentro(externo, [(px, py)])[0]:
                    pend.append('há furo traçado fora do anel externo: foi mantido como está')
                furos.append(geom.orientar(furo, False))
        saida.append([externo] + furos)
    return geom.de_poligonos(saida), mud, pend


def consertar_feicoes(feicoes, completo, rotulo):
    """Aplica o conserto a todas. Devolve (feições novas, linhas do relatório, resumo).
    rotulo(feição, índice) dá o nome que aparece no relatório."""
    novas, linhas = [], []
    resumo = {'mudadas': 0, 'com_pendencia': 0, 'sem_geometria': 0, 'perderam_geometria': 0}
    for i, f in enumerate(feicoes, 1):
        g, mud, pend = consertar(f['geometry'], completo)
        if f['geometry'] is None:
            resumo['sem_geometria'] += 1
        elif g is None:
            resumo['perderam_geometria'] += 1
        if mud or pend:
            partes = [f'{n} {desc}' for desc, n in mud.items()] + pend
            linhas.append(f'feição {i} ({rotulo(f, i)}): ' + '; '.join(partes))
            resumo['mudadas'] += 1 if mud else 0
            resumo['com_pendencia'] += 1 if pend else 0
        novas.append({'geometry': g, 'properties': f['properties']})
    return novas, linhas, resumo


if __name__ == '__main__':
    quad = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0), (0.0, 0.0)]
    # anel aberto, com vértice repetido e um inválido
    ruim = {'type': 'Polygon', 'coordinates': [[(0, 0), (100, 0), (100, 0), (100, 100), (float('nan'), 5), (0, 100)]]}
    g, mud, pend = consertar(ruim)
    assert g['coordinates'][0] == quad and not pend and sum(mud.values()) == 3, (g, mud)
    # ida e volta (espinho): some sem mudar a área
    espinho = {'type': 'Polygon', 'coordinates': [[(0, 0), (100, 0), (100, 50), (150, 50), (100, 50), (100, 100), (0, 100), (0, 0)]]}
    g, mud, pend = consertar(espinho)
    assert abs(geom.area_m2(g) - 10000) < 1e-9 and len(g['coordinates'][0]) == 6 and not pend and 'vértice(s) de ida e volta removido(s)' in mud, (g, mud)
    # anel em "8" que se toca num vértice: vira dois polígonos
    oito = {'type': 'Polygon', 'coordinates': [[(0, 0), (50, 0), (50, 50), (100, 50), (100, 100), (50, 100), (50, 50), (0, 50), (0, 0)]]}
    g, mud, pend = consertar(oito)
    assert g['type'] == 'MultiPolygon' and len(g['coordinates']) == 2 and abs(geom.area_m2(g) - 5000) < 1e-9 and not pend
    g2, mud2, pend2 = consertar(oito, completo=False)
    assert g2['type'] == 'Polygon' and pend2 and not mud2
    # furo que encosta no anel externo num vértice (gravado como um anel só): vira externo + furo
    com_toque = {'type': 'Polygon', 'coordinates': [[(0, 0), (100, 0), (100, 100), (0, 100), (0, 0), (20, 20), (20, 60), (60, 20), (20, 20), (0, 0)]]}
    g, mud, pend = consertar(com_toque)
    assert not pend and abs(geom.area_m2(g) - (10000 - 800)) < 1e-9, (g, mud, pend)
    # gravata: o contorno se cruza. Não é consertado, e o relatório diz onde
    gravata = {'type': 'Polygon', 'coordinates': [[(500000, 7456000), (500100, 7456100), (500100, 7456000), (500000, 7456100), (500000, 7456000)]]}
    g, mud, pend = consertar(gravata)
    assert g is not None and not mud and len(pend) == 1 and '(500050.0, 7456050.0)' in pend[0], (mud, pend)
    assert cruzamentos(quad) == [] and cruzamentos(gravata['coordinates'][0]) == [(500050.0, 7456050.0)]
    em_graus = [(-51.20, -23.10), (-51.19, -23.09), (-51.19, -23.10), (-51.20, -23.09), (-51.20, -23.10)]
    assert '(-51.195000, -23.095000)' in consertar({'type': 'Polygon', 'coordinates': [em_graus]})[2][0]
    # contorno que encosta num lado (T): também é relatado
    te = [(0, 0), (100, 0), (100, 100), (50, 0), (0, 100), (0, 0)]
    assert cruzamentos(te), 'devia achar o toque'
    # furo fora do externo: fica, com o aviso
    fora = {'type': 'Polygon', 'coordinates': [quad, [(200, 200), (200, 250), (250, 250), (200, 200)]]}
    g, mud, pend = consertar(fora)
    assert len(g['coordinates']) == 2 and any('furo traçado fora' in p for p in pend)
    # polígono sem área e linha de um ponto só: descartados
    assert consertar({'type': 'Polygon', 'coordinates': [[(0, 0), (10, 10), (0, 0)]]})[0] is None
    assert consertar({'type': 'LineString', 'coordinates': [(1, 1), (1, 1)]})[0] is None
    g, mud, _ = consertar({'type': 'MultiLineString', 'coordinates': [[(0, 0), (0, 0), (5, 5)], [(1, 1)]]})
    assert g == {'type': 'LineString', 'coordinates': [(0.0, 0.0), (5.0, 5.0)]}
    # geometria boa passa igual, sem relato
    bom = {'type': 'MultiPolygon', 'coordinates': [[quad, [(40.0, 40.0), (40.0, 60.0), (60.0, 60.0), (60.0, 40.0), (40.0, 40.0)]]]}
    g, mud, pend = consertar(bom)
    assert not mud and not pend and abs(geom.area_m2(g) - 9600) < 1e-9
    fs, linhas, resumo = consertar_feicoes([{'geometry': ruim, 'properties': {'n': 'A'}}, {'geometry': gravata, 'properties': {'n': 'B'}},
                                            {'geometry': None, 'properties': {'n': 'C'}}, {'geometry': bom, 'properties': {'n': 'D'}}],
                                           True, lambda f, i: f['properties']['n'])
    assert len(fs) == 4 and len(linhas) == 2 and resumo == {'mudadas': 1, 'com_pendencia': 1, 'sem_geometria': 1, 'perderam_geometria': 0}
    assert linhas[0].startswith('feição 1 (A): ') and 'NÃO foi consertado' in linhas[1]
    print('conserto OK: fecha, tira repetido e ida e volta, divide o anel que se toca, relata a gravata e o furo fora')
