"""União de talhões: junta polígonos vizinhos e some com a divisa interna.

Como funciona (sem biblioteca de geometria): cada polígono é uma volta de
segmentos com o lado de dentro à esquerda. Onde dois talhões dividem a mesma
divisa, o segmento aparece duas vezes, uma em cada sentido, e os dois se
anulam. O que sobra é o contorno de fora (e os furos de verdade), que é
costurado de novo em anéis.

O que é EXATO: divisas que coincidem (os mesmos vértices, ou vértices de um
talhão caindo em cima da linha do outro, dentro da tolerância) somem sem
mover nada além da tolerância, e a área da união é a soma das áreas.

O que NÃO é feito: recortar SOBREPOSIÇÃO. Se dois polígonos se sobrepõem de
verdade (um entra no outro), a união exata exigiria recortá-los; a skill
detecta, avisa quais são e devolve o grupo junto, sem dissolver.
Fresta entre divisas que não coincidem (mais larga que a tolerância) fica como
furo estreito, e é relatada: conta como fresta o furo com menos de 1 m de
largura média (duas vezes a área dividida pelo perímetro).
"""

import math
from collections import Counter, defaultdict

import numpy as np

import conserto
import geom


LARGURA_DE_FRESTA = 1.0  # metros: furo mais estreito que isso é relatado como fresta entre divisas


def _agrupar_vertices(aneis, tol):
    """Dá um número (nó) a cada vértice, juntando os que estão a menos de tol.
    Devolve (aneis em nós, coordenadas dos nós, originais dos nós, movidos, maior ajuste)."""
    celulas, xy, orig = {}, [], []
    movidos, maior = 0, 0.0
    saida = []
    for plano, original in aneis:
        ids = []
        if len(plano) > 1 and tuple(plano[0]) == tuple(plano[-1]):  # o ponto que fecha o anel não conta de novo
            plano, original = plano[:-1], original[:-1]
        for p, o in zip(plano, original):
            cx, cy = math.floor(p[0] / tol), math.floor(p[1] / tol)
            achado, dist = None, None
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for k in celulas.get((cx + dx, cy + dy), ()):
                        d = math.hypot(xy[k][0] - p[0], xy[k][1] - p[1])
                        if d <= tol and (dist is None or d < dist):
                            achado, dist = k, d
            if achado is None:
                achado = len(xy)
                xy.append((p[0], p[1]))
                orig.append(o)
                celulas.setdefault((cx, cy), []).append(achado)
            elif dist > 0:
                movidos += 1
                maior = max(maior, dist)
            if not ids or ids[-1] != achado:
                ids.append(achado)
        if len(ids) > 1 and ids[0] == ids[-1]:
            ids.pop()
        saida.append(ids)
    return saida, xy, orig, movidos, maior


def _inserir_nos(aneis, xy, tol):
    """Vértice de um anel que cai em cima do lado de outro vira vértice dos dois (divisa em T)."""
    pts = np.asarray(xy, dtype=float)
    lados = [math.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1]) for ids in aneis for a, b in zip(ids, ids[1:] + ids[:1])]
    if not lados:
        return aneis, 0
    ext = max(pts[:, 0].max() - pts[:, 0].min(), pts[:, 1].max() - pts[:, 1].min(), 1.0)
    g = max(float(np.median(lados)), ext / 300, tol * 4)
    grade = defaultdict(list)
    for k, (x, y) in enumerate(xy):
        grade[(math.floor(x / g), math.floor(y / g))].append(k)
    novos, inseridos = [], 0
    for ids in aneis:
        saida = []
        for a, b in zip(ids, ids[1:] + ids[:1]):
            saida.append(a)
            ax, ay, bx, by = xy[a][0], xy[a][1], xy[b][0], xy[b][1]
            comp = math.hypot(bx - ax, by - ay)
            if comp <= 2 * tol:
                continue
            cand = []
            for cx in range(math.floor((min(ax, bx) - tol) / g), math.floor((max(ax, bx) + tol) / g) + 1):
                for cy in range(math.floor((min(ay, by) - tol) / g), math.floor((max(ay, by) + tol) / g) + 1):
                    cand += grade.get((cx, cy), ())
            no_meio = []
            for k in cand:
                if k == a or k == b:
                    continue
                t = ((xy[k][0] - ax) * (bx - ax) + (xy[k][1] - ay) * (by - ay)) / comp
                if tol < t < comp - tol:
                    d = abs((xy[k][0] - ax) * (by - ay) - (xy[k][1] - ay) * (bx - ax)) / comp
                    if d <= tol:
                        no_meio.append((t, k))
            for _, k in sorted(set(no_meio)):
                if saida[-1] != k:
                    saida.append(k)
                    inseridos += 1
        novos.append(saida)
    return novos, inseridos


def _cruzam(aneis, donos, xy):
    """Pares de feições cujos lados se cruzam de verdade (um entra no outro)."""
    seg = [(a, b, d) for ids, d in zip(aneis, donos) for a, b in zip(ids, ids[1:] + ids[:1])]
    if len(seg) < 2:
        return set()
    p = np.asarray([xy[s[0]] for s in seg], dtype=float)
    q = np.asarray([xy[s[1]] for s in seg], dtype=float)
    origem = p.min(axis=0)
    p, q = p - origem, q - origem
    dono = np.asarray([s[2] for s in seg])
    minx, maxx = np.minimum(p[:, 0], q[:, 0]), np.maximum(p[:, 0], q[:, 0])
    miny, maxy = np.minimum(p[:, 1], q[:, 1]), np.maximum(p[:, 1], q[:, 1])
    ordem = np.argsort(minx, kind='stable')
    minx_ord = minx[ordem]
    pares = set()
    for k in range(len(seg)):
        i = ordem[k]
        js = ordem[k + 1:np.searchsorted(minx_ord, maxx[i], side='right')]
        if not len(js):
            continue
        js = js[(dono[js] != dono[i]) & (miny[js] <= maxy[i]) & (maxy[js] >= miny[i])]
        if not len(js):
            continue
        d, D = q[i] - p[i], q[js] - p[js]
        d1 = d[0] * (p[js, 1] - p[i, 1]) - d[1] * (p[js, 0] - p[i, 0])
        d2 = d[0] * (q[js, 1] - p[i, 1]) - d[1] * (q[js, 0] - p[i, 0])
        d3 = D[:, 0] * (p[i, 1] - p[js, 1]) - D[:, 1] * (p[i, 0] - p[js, 0])
        d4 = D[:, 0] * (q[i, 1] - p[js, 1]) - D[:, 1] * (q[i, 0] - p[js, 0])
        for j in js[(d1 * d2 < 0) & (d3 * d4 < 0)].tolist():
            pares.add((min(dono[i], dono[j]), max(dono[i], dono[j])))
    return {(int(a), int(b)) for a, b in pares}


def _costurar(arestas, xy):
    """Arestas dirigidas (com o dentro à esquerda) -> anéis fechados de nós. None se não fecham."""
    saem = defaultdict(list)
    grau = Counter()
    for (a, b), n in arestas.items():
        saem[a] += [b] * n
        grau[a] += n
        grau[b] -= n
    if any(grau.values()):
        return None
    aneis = []
    for inicio in list(saem):
        while saem[inicio]:
            anel, anterior, atual = [inicio], inicio, saem[inicio].pop()
            while atual != inicio:
                anel.append(atual)
                opcoes = saem[atual]
                if not opcoes:
                    return None
                if len(opcoes) == 1:
                    k = 0
                else:  # no vértice em que dois contornos se tocam, vira o máximo para a esquerda
                    ex, ey = xy[atual][0] - xy[anterior][0], xy[atual][1] - xy[anterior][1]
                    melhor = None
                    for i, w in enumerate(opcoes):
                        sx, sy = xy[w][0] - xy[atual][0], xy[w][1] - xy[atual][1]
                        ang = math.atan2(ex * sy - ey * sx, ex * sx + ey * sy)
                        if w == anterior:
                            ang = -math.pi
                        if melhor is None or ang > melhor[0]:
                            melhor = (ang, i)
                    k = melhor[1]
                anterior, atual = atual, opcoes.pop(k)
            aneis.append(anel)
    return aneis


def dissolver(grupos, tol=0.05):
    """grupos = [(geometria plana em metros, geometria original)] das feições a unir.
    Devolve (polígonos [[externo, furo, …], …] nas coordenadas originais, relato)."""
    aneis, donos = [], []
    area_antes = 0.0
    for d, (plana, original) in enumerate(grupos):
        area_antes += geom.area_m2(plana)
        for poli_p, poli_o in zip(geom.poligonos_de(plana), geom.poligonos_de(original)):
            for k, (ap, ao) in enumerate(zip(poli_p, poli_o)):
                ap, ao = list(ap), list(ao)
                if (geom.area_assinada(ap) > 0) != (k == 0):  # externo anti-horário, furo horário
                    ap, ao = ap[::-1], ao[::-1]
                aneis.append((ap, ao))
                donos.append(d)
    relato = {'dissolvido': False, 'sobrepostos': [], 'movidos': 0, 'maior_ajuste': 0.0, 'nos_em_t': 0, 'frestas': 0,
              'area_frestas_m2': 0.0, 'area_antes_ha': area_antes / 10000, 'area_depois_ha': area_antes / 10000, 'motivo': ''}

    def juntos():
        return [poli for _, original in grupos for poli in geom.poligonos_de(original)]

    ids, xy, orig, relato['movidos'], relato['maior_ajuste'] = _agrupar_vertices(aneis, tol)
    validos = [(i, d) for i, d in zip(ids, donos) if len(i) >= 3]
    ids, donos = [v[0] for v in validos], [v[1] for v in validos]
    ids, relato['nos_em_t'] = _inserir_nos(ids, xy, tol)

    arestas, dono_da_aresta = Counter(), defaultdict(set)
    for i, d in zip(ids, donos):
        for a, b in zip(i, i[1:] + i[:1]):
            if a != b:
                arestas[(a, b)] += 1
                dono_da_aresta[(a, b)].add(d)
    sobre = set(_cruzam(ids, donos, xy))
    for (a, b), n in arestas.items():  # o mesmo lado, no mesmo sentido, em duas feições: uma está sobre a outra
        if len(dono_da_aresta[(a, b)]) > 1:
            ds = sorted(dono_da_aresta[(a, b)])
            sobre.update((ds[0], x) for x in ds[1:])
    # uma feição inteira dentro de outra (sem cruzar lados): um ponto de dentro dela cai dentro da outra
    planas = [g[0] for g in grupos]
    caixas = [geom.caixa([{'geometry': g}]) for g in planas]
    internos = [(d, geom.ponto_interno_poligono([geom.fechar(a) for a in poli])) for d, g in enumerate(planas) for poli in geom.poligonos_de(g)]
    for d, (px, py) in internos:
        for outro in range(len(grupos)):
            c = caixas[outro]
            if not (c[0] <= px <= c[2] and c[1] <= py <= c[3]):
                continue
            if outro == d or (min(d, outro), max(d, outro)) in sobre:
                continue
            dentro = False
            for poli in geom.poligonos_de(planas[outro]):
                for a in poli:
                    dentro ^= bool(geom.dentro(geom.fechar(a), [(px, py)])[0])
            if dentro:
                sobre.add((min(d, outro), max(d, outro)))
    if sobre:
        relato['sobrepostos'] = sorted(sobre)
        relato['motivo'] = 'há polígonos que se sobrepõem'
        return juntos(), relato

    for (a, b) in list(arestas):
        n = min(arestas[(a, b)], arestas.get((b, a), 0))
        if n and a < b:
            arestas[(a, b)] -= n
            arestas[(b, a)] -= n
    arestas = Counter({k: v for k, v in arestas.items() if v > 0})
    costura = _costurar(arestas, xy)
    if costura is None:
        relato['motivo'] = 'o contorno não fechou depois de tirar as divisas (geometria com defeito: rode com --consertar)'
        return juntos(), relato
    simples = []
    for anel in costura:
        fechado = [(k,) for k in anel] + [(anel[0],)]
        simples += [[p[0] for p in parte[:-1]] for parte in conserto.dividir_em_toques(fechado)]
    externos, furos = [], []
    for anel in simples:
        plano = [xy[k] for k in anel] + [xy[anel[0]]]
        area = geom.area_assinada(plano)
        if area > 0:
            externos.append((area, anel, plano))
        elif area < 0:
            furos.append((-area, anel, plano))
    externos.sort(key=lambda e: e[0])
    poligonos = {id(e): [[orig[k] for k in e[1]] + [orig[e[1][0]]]] for e in externos}
    area_depois = sum(e[0] for e in externos)
    for area, anel, plano in furos:
        px, py = geom.ponto_interno(plano)
        pai = next((e for e in externos if e[0] > area and geom.dentro(e[2], [(px, py)])[0]), None)
        if pai is None:
            continue
        poligonos[id(pai)].append([orig[k] for k in anel] + [orig[anel[0]]])
        area_depois -= area
        if 2 * area / geom.comprimento_m({'type': 'LineString', 'coordinates': plano}) < LARGURA_DE_FRESTA:
            relato['frestas'] += 1
            relato['area_frestas_m2'] += area
    relato['dissolvido'] = True
    relato['area_depois_ha'] = area_depois / 10000
    return [poligonos[id(e)] for e in sorted(externos, key=lambda e: -e[0])], relato


if __name__ == '__main__':
    def q(x0, y0, x1, y1):
        return {'type': 'Polygon', 'coordinates': [[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]]}

    def une(gs, tol=0.05):
        return dissolver([(g, g) for g in gs], tol)

    # dois talhões com a divisa em comum: um retângulo só, sem a divisa
    polis, r = une([q(0, 0, 100, 100), q(100, 0, 250, 100)])
    assert r['dissolvido'] and len(polis) == 1 and len(polis[0]) == 1 and abs(geom.area_m2(geom.de_poligonos(polis)) - 25000) < 1e-9
    assert (100, 0) in polis[0][0] and r['area_antes_ha'] == r['area_depois_ha'] == 2.5
    # quatro talhões em cruz, o da direita com a divisa dividida em T (vértice no meio do lado do vizinho)
    quatro = [q(0, 0, 100, 100), q(0, 100, 100, 200), {'type': 'Polygon', 'coordinates': [[(100, 0), (200, 0), (200, 200), (100, 200), (100, 0)]]}, q(200, 50, 260, 150)]
    polis, r = une(quatro)
    assert r['dissolvido'] and len(polis) == 1 and len(polis[0]) == 1 and r['nos_em_t'] >= 3, r
    assert abs(geom.area_m2(geom.de_poligonos(polis)) - (20000 + 20000 + 6000)) < 1e-9
    # divisa que não coincide por 2 cm: a tolerância de 5 cm junta
    polis, r = une([q(0, 0, 100, 100), q(100.02, 0, 200, 100)])
    assert r['dissolvido'] and len(polis) == 1 and r['movidos'] == 2 and abs(r['maior_ajuste'] - 0.02) < 1e-9
    # fresta de 1 m: não junta, e os dois continuam separados
    polis, r = une([q(0, 0, 100, 100), q(101, 0, 200, 100)])
    assert r['dissolvido'] and len(polis) == 2
    # anel de quatro talhões em volta de um miolo vazio: o miolo vira furo de verdade
    volta = [q(0, 0, 300, 100), q(0, 200, 300, 300), q(0, 100, 100, 200), q(200, 100, 300, 200)]
    polis, r = une(volta)
    assert len(polis) == 1 and len(polis[0]) == 2 and abs(geom.area_m2(geom.de_poligonos(polis)) - 80000) < 1e-9 and r['frestas'] == 0
    # fresta de 30 cm entre dois talhões, fechada em cima e embaixo por outros dois: fica como furo, relatado como fresta
    polis, r = une([q(0, 0, 100, 100), q(100.3, 0, 200, 100), q(0, -50, 200, 0), q(0, 100, 200, 150)])
    assert r['dissolvido'] and len(polis) == 1 and len(polis[0]) == 2 and r['frestas'] == 1 and abs(r['area_frestas_m2'] - 30) < 1e-6, r
    assert len(une([q(0, 0, 100, 100), q(100.3, 0, 200, 100), q(0, -50, 200, 0), q(0, 100, 200, 150)], tol=0.5)[0][0]) == 1
    # só se encostam num canto: continuam dois polígonos
    polis, r = une([q(0, 0, 100, 100), q(100, 100, 200, 200)])
    assert r['dissolvido'] and len(polis) == 2
    # talhão com furo e a ilha que preenche o furo: fica inteiro
    com_furo = {'type': 'Polygon', 'coordinates': [[(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)], [(40, 40), (40, 60), (60, 60), (60, 40), (40, 40)]]}
    polis, r = une([com_furo, q(40, 40, 60, 60)])
    assert r['dissolvido'] and len(polis) == 1 and len(polis[0]) == 1 and abs(geom.area_m2(geom.de_poligonos(polis)) - 10000) < 1e-9
    # sobreposição de verdade: não dissolve, e diz quais
    polis, r = une([q(0, 0, 100, 100), q(50, 50, 150, 150), q(500, 0, 600, 100)])
    assert not r['dissolvido'] and r['sobrepostos'] == [(0, 1)] and len(polis) == 3
    # um dentro do outro, e dois iguais
    assert une([q(0, 0, 100, 100), q(20, 20, 40, 40)])[1]['sobrepostos'] == [(0, 1)]
    assert une([q(0, 0, 100, 100), q(0, 0, 100, 100)])[1]['sobrepostos'] == [(0, 1)]
    # as coordenadas originais (em graus, por exemplo) voltam intactas
    plano, orig = q(0, 0, 100, 100), q(-51.2, -23.1, -51.199, -23.099)
    plano2, orig2 = q(100, 0, 200, 100), q(-51.199, -23.1, -51.198, -23.099)
    polis, r = dissolver([(plano, orig), (plano2, orig2)])
    assert r['dissolvido'] and (-51.2, -23.1) in polis[0][0] and (-51.198, -23.099) in polis[0][0] and len(polis[0][0]) == 7
    # 400 talhões em grade: a união é um quadrado, em pouco tempo
    import time
    grade = [q(i * 50, j * 50, i * 50 + 50, j * 50 + 50) for i in range(20) for j in range(20)]
    t0 = time.time()
    polis, r = une(grade)
    assert len(polis) == 1 and len(polis[0]) == 1 and abs(geom.area_m2(geom.de_poligonos(polis)) - 1e6) < 1e-6
    print(f'uniao OK: divisa comum, divisa em T, tolerância, furo de verdade, canto, sobreposição detectada, 400 talhões em {time.time() - t0:.2f} s')
