"""Geometria no molde do GeoJSON, só com numpy.

Toda feição que a skill lê vira {'geometry': {...}, 'properties': {...}}, com a
geometria em duas dimensões:
  Point [x, y] · MultiPoint [[x, y], …] · LineString [[x, y], …] ·
  MultiLineString [[[x, y], …], …] · Polygon [externo, furo, …] ·
  MultiPolygon [[externo, furo, …], …]
Altitude e medida (Z e M) são descartadas na leitura, e isso é avisado.

Convenção interna dos polígonos: anel externo no sentido anti-horário, furo no
horário, primeiro ponto repetido no fim. Cada gravador vira o sentido para o
que o formato dele pede.
"""

import math

import numpy as np

import projecao

NOME_DO_TIPO = {'Point': 'ponto', 'MultiPoint': 'ponto', 'LineString': 'linha', 'MultiLineString': 'linha',
                'Polygon': 'polígono', 'MultiPolygon': 'polígono'}
PLURAL = {'ponto': 'pontos', 'linha': 'linhas', 'polígono': 'polígonos'}


def familia(geom):
    """'ponto', 'linha' ou 'polígono' (None para geometria vazia)."""
    return NOME_DO_TIPO.get(geom['type']) if geom else None


# ---------------------------------------------------------------- anéis

def area_assinada(anel):
    """Área com sinal (positiva = anti-horário), em unidades do plano."""
    a = np.asarray(anel, dtype=float)
    if len(a) < 3:
        return 0.0
    # tirar a origem evita perder casas com coordenadas UTM de 7 dígitos
    x, y = a[:, 0] - a[0, 0], a[:, 1] - a[0, 1]
    return float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2


def fechar(anel):
    anel = [tuple(map(float, p[:2])) for p in anel]
    if anel and anel[0] != anel[-1]:
        anel.append(anel[0])
    return anel


def orientar(anel, anti_horario):
    return anel if (area_assinada(anel) > 0) == anti_horario else anel[::-1]


def dentro(anel, pontos):
    """Quais pontos [n, 2] caem dentro do anel (raio para a direita; a borda fica indefinida)."""
    a = np.asarray(anel, dtype=float)
    p = np.asarray(pontos, dtype=float).reshape(-1, 2)
    x1, y1 = a[:-1, 0], a[:-1, 1]
    x2, y2 = a[1:, 0], a[1:, 1]
    marca = np.zeros(len(p), dtype=bool)
    passo = max(1, 2000000 // max(1, len(x1)))
    for ini in range(0, len(p), passo):
        px, py = p[ini:ini + passo, 0][:, None], p[ini:ini + passo, 1][:, None]
        corta = (y1 > py) != (y2 > py)
        with np.errstate(divide='ignore', invalid='ignore'):
            xc = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
        marca[ini:ini + passo] = (np.count_nonzero(corta & (px < xc), axis=1) % 2) == 1
    return marca


def ponto_interno(anel):
    """Um ponto com certeza dentro do anel (no meio de um corte horizontal)."""
    return ponto_interno_poligono([anel])


def ponto_interno_poligono(aneis):
    """Um ponto dentro do polígono [externo, furo, …] e fora dos furos dele."""
    arrs = [np.asarray(a, dtype=float) for a in aneis if len(a) >= 3]
    ext = arrs[0]
    ys = np.unique(np.concatenate([a[:, 1] for a in arrs]))
    ys = ys[(ys >= ext[:, 1].min()) & (ys <= ext[:, 1].max())]
    if len(ys) < 2:
        return float(ext[0, 0]), float(ext[0, 1])
    melhor = None
    # tenta alguns cortes e fica com o trecho mais largo (longe das bordas)
    for k in sorted(set([len(ys) // 2, len(ys) // 3, 2 * len(ys) // 3, 0, len(ys) - 2])):
        k = min(max(k, 0), len(ys) - 2)
        y = (ys[k] + ys[k + 1]) / 2
        cortes = []
        for a in arrs:
            x1, y1, x2, y2 = a[:-1, 0], a[:-1, 1], a[1:, 0], a[1:, 1]
            corta = (y1 > y) != (y2 > y)
            cortes.append(x1[corta] + (y - y1[corta]) * (x2[corta] - x1[corta]) / (y2[corta] - y1[corta]))
        xs = np.sort(np.concatenate(cortes))
        for i in range(0, len(xs) - 1, 2):
            largura = xs[i + 1] - xs[i]
            if melhor is None or largura > melhor[0]:
                melhor = (largura, (xs[i] + xs[i + 1]) / 2, y)
    if melhor is None:
        return float(ext[0, 0]), float(ext[0, 1])
    return float(melhor[1]), float(melhor[2])


def organizar_aneis(aneis):
    """Recebe anéis soltos (como vêm do shapefile) e devolve polígonos
    [[externo, furo, …], …] pelo aninhamento: anel dentro de um número par de
    outros é externo; ímpar, é furo do menor anel que o contém."""
    aneis = [fechar(a) for a in aneis if len(a) >= 3]
    areas = [abs(area_assinada(a)) for a in aneis]
    caixas = [(min(p[0] for p in a), min(p[1] for p in a), max(p[0] for p in a), max(p[1] for p in a)) for a in aneis]
    n = len(aneis)
    if n == 1:
        return [[orientar(aneis[0], True)]]
    internos = [ponto_interno(a) for a in aneis]
    contem = [[] for _ in range(n)]  # contem[i] = anéis maiores que contêm o anel i
    for i in range(n):
        px, py = internos[i]
        for j in range(n):
            if i == j or areas[j] <= areas[i]:
                continue
            c = caixas[j]
            if c[0] <= px <= c[2] and c[1] <= py <= c[3] and dentro(aneis[j], [(px, py)])[0]:
                contem[i].append(j)
    poligonos, dono = [], {}
    for i in sorted(range(n), key=lambda k: -areas[k]):
        if len(contem[i]) % 2 == 0:
            dono[i] = len(poligonos)
            poligonos.append([orientar(aneis[i], True)])
    for i in range(n):
        if len(contem[i]) % 2 == 1:
            pais = [j for j in contem[i] if len(contem[j]) == len(contem[i]) - 1]
            if pais:
                pai = min(pais, key=lambda j: areas[j])
                poligonos[dono[pai]].append(orientar(aneis[i], False))
    return poligonos


def normalizar_poligono(aneis):
    """Polígono com papéis declarados (1º anel externo, o resto furos): fecha e orienta."""
    saida = []
    for k, anel in enumerate(aneis):
        anel = fechar(anel)
        if len(anel) >= 4:
            saida.append(orientar(anel, k == 0))
    return saida


# ---------------------------------------------------------------- percorrer geometrias

def partes(geom):
    """Lista de sequências de pontos da geometria (cada ponto, linha ou anel)."""
    t, c = geom['type'], geom['coordinates']
    if t == 'Point':
        return [[c]]
    if t in ('MultiPoint', 'LineString'):
        return [c]
    if t in ('MultiLineString', 'Polygon'):
        return list(c)
    return [anel for poli in c for anel in poli]


def mapear(geom, f):
    """Nova geometria com f(xs, ys) -> (xs, ys) aplicada a todas as coordenadas."""
    def leva(seq):
        if not len(seq):
            return []
        a = np.asarray(seq, dtype=float)
        xs, ys = f(a[:, 0], a[:, 1])
        return list(zip(np.asarray(xs, dtype=float).tolist(), np.asarray(ys, dtype=float).tolist()))
    t, c = geom['type'], geom['coordinates']
    if t == 'Point':
        novo = leva([c])[0]
    elif t in ('MultiPoint', 'LineString'):
        novo = leva(c)
    elif t in ('MultiLineString', 'Polygon'):
        novo = [leva(s) for s in c]
    else:
        novo = [[leva(s) for s in poli] for poli in c]
    return {'type': t, 'coordinates': novo}


def poligonos_de(geom):
    """[[externo, furo, …], …] de um Polygon ou MultiPolygon."""
    if geom['type'] == 'Polygon':
        return [geom['coordinates']]
    if geom['type'] == 'MultiPolygon':
        return list(geom['coordinates'])
    return []


def de_poligonos(poligonos):
    poligonos = [p for p in poligonos if p]
    if not poligonos:
        return None
    if len(poligonos) == 1:
        return {'type': 'Polygon', 'coordinates': poligonos[0]}
    return {'type': 'MultiPolygon', 'coordinates': poligonos}


def caixa(feicoes):
    xs = [p[0] for f in feicoes if f['geometry'] for s in partes(f['geometry']) for p in s]
    ys = [p[1] for f in feicoes if f['geometry'] for s in partes(f['geometry']) for p in s]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def n_vertices(geom):
    return sum(len(s) for s in partes(geom)) if geom else 0


# ---------------------------------------------------------------- medidas

def area_m2(geom):
    """Área de um (Multi)Polygon em coordenadas planas: externo menos furos."""
    total = 0.0
    for poli in poligonos_de(geom):
        for k, anel in enumerate(poli):
            total += abs(area_assinada(anel)) * (1 if k == 0 else -1)
    return total


def comprimento_m(geom):
    total = 0.0
    for seq in partes(geom):
        a = np.asarray(seq, dtype=float)
        if len(a) >= 2:
            total += float(np.sqrt(((a[1:] - a[:-1]) ** 2).sum(axis=1)).sum())
    return total


def src_de_medida(feicoes, src):
    """O UTM em que as áreas são medidas: o do próprio arquivo, ou o fuso do centro dele."""
    if src['tipo'] == 'utm':
        return src
    c = caixa(feicoes)
    zona, sul = projecao.zona_de((c[0] + c[2]) / 2, (c[1] + c[3]) / 2)
    return projecao.utm(zona, sul, src['datum'], 'fuso do centro do arquivo')


def medir(feicoes, src):
    """Área (ha) dos polígonos e comprimento (m) das linhas de cada feição, medidos no plano
    do UTM. Devolve (areas_ha, comprimentos_m, src_da_medida); None onde não se aplica."""
    if not any(f['geometry'] for f in feicoes):
        return [None] * len(feicoes), [None] * len(feicoes), None
    alvo = src_de_medida(feicoes, src)
    f = projecao.conversor(src, alvo)
    areas, comprimentos = [], []
    for fe in feicoes:
        g = fe['geometry']
        fam = familia(g)
        if fam in ('polígono', 'linha'):
            plano = mapear(g, f)
            areas.append(area_m2(plano) / 10000 if fam == 'polígono' else None)
            comprimentos.append(comprimento_m(plano) if fam == 'linha' else None)
        else:
            areas.append(None)
            comprimentos.append(None)
    return areas, comprimentos, alvo


def areas_no_elipsoide(feicoes, src):
    """Área (ha) de cada polígono medida sobre o elipsoide, como o QGIS e o CAR medem. As coordenadas
    vão para a projeção cilíndrica equivalente (que conserva a área em qualquer lugar) e a área sai dela.
    None onde não é polígono."""
    a, f = projecao.ELIPSOIDES[src['datum']]
    e2 = f * (2 - f)
    e = math.sqrt(e2)
    para_graus = projecao.conversor(src, projecao.geo(src['datum']))

    def equivalente(xs, ys):
        lons, lats = para_graus(xs, ys)
        s = np.sin(np.radians(lats))
        q = (1 - e2) * (s / (1 - e2 * s * s) - np.log((1 - e * s) / (1 + e * s)) / (2 * e))
        return a * np.radians(lons), a * q / 2
    saida = []
    for fe in feicoes:
        g = fe['geometry']
        saida.append(area_m2(mapear(g, equivalente)) / 10000 if familia(g) == 'polígono' else None)
    return saida


# ---------------------------------------------------------------- simplificação

def _douglas(pontos, tol):
    a = np.asarray(pontos, dtype=float)
    manter = np.zeros(len(a), dtype=bool)
    manter[0] = manter[-1] = True
    pilha = [(0, len(a) - 1)]
    while pilha:
        i, j = pilha.pop()
        if j <= i + 1:
            continue
        d = a[j] - a[i]
        norma = math.hypot(d[0], d[1])
        trecho = a[i + 1:j] - a[i]
        if norma == 0:
            dist = np.hypot(trecho[:, 0], trecho[:, 1])
        else:
            dist = np.abs(trecho[:, 0] * d[1] - trecho[:, 1] * d[0]) / norma
        k = int(np.argmax(dist))
        if dist[k] > tol:
            manter[i + 1 + k] = True
            pilha.append((i, i + 1 + k))
            pilha.append((i + 1 + k, j))
    return [tuple(p) for p in a[manter].tolist()]


def simplificar(geom, tol):
    """Tira vértices que desviam menos que tol (Douglas-Peucker), em coordenadas planas.
    Anel que ficaria com menos de 4 pontos é mantido como estava."""
    fam = familia(geom)
    if fam == 'ponto':
        return geom

    def anel(seq):
        seq = [tuple(p) for p in seq]
        if len(seq) < 5:
            return seq
        # o anel é cortado em dois no ponto mais distante do início, para o início não virar um canto fixo falso
        a = np.asarray(seq, dtype=float)
        meio = int(np.argmax(((a - a[0]) ** 2).sum(axis=1)))
        novo = _douglas(seq[:meio + 1], tol)[:-1] + _douglas(seq[meio:], tol)
        return novo if len(novo) >= 4 else seq

    def linha(seq):
        return _douglas(seq, tol) if len(seq) > 2 else list(seq)

    t, c = geom['type'], geom['coordinates']
    if t == 'LineString':
        return {'type': t, 'coordinates': linha(c)}
    if t == 'MultiLineString':
        return {'type': t, 'coordinates': [linha(s) for s in c]}
    if t == 'Polygon':
        return {'type': t, 'coordinates': [anel(s) for s in c]}
    return {'type': t, 'coordinates': [[anel(s) for s in poli] for poli in c]}


if __name__ == '__main__':
    quad = [(0, 0), (1000, 0), (1000, 1000), (0, 1000), (0, 0)]
    furo = [(400, 400), (400, 600), (600, 600), (600, 400), (400, 400)]
    assert area_assinada(quad) == 1e6 and area_assinada(quad[::-1]) == -1e6
    assert fechar(quad[:-1]) == [tuple(map(float, p)) for p in quad]
    assert dentro(quad, [(10, 10), (1500, 10), (500, 999)]).tolist() == [True, False, True]
    x, y = ponto_interno(furo)
    assert 400 < x < 600 and 400 < y < 600
    x, y = ponto_interno_poligono([quad, furo])
    assert dentro(quad, [(x, y)])[0] and not dentro(furo, [(x, y)])[0]
    # anéis soltos e embaralhados: quadrado, furo, ilha dentro do furo e outro quadrado ao lado
    ilha = [(480, 480), (520, 480), (520, 520), (480, 520), (480, 480)]
    outro = [(2000, 0), (2100, 0), (2100, 100), (2000, 100), (2000, 0)]
    polis = organizar_aneis([ilha, furo[::-1], outro[::-1], quad[::-1]])
    assert len(polis) == 3 and sorted(len(p) for p in polis) == [1, 1, 2]
    maior = max(polis, key=lambda p: abs(area_assinada(p[0])))
    assert area_assinada(maior[0]) > 0 and area_assinada(maior[1]) < 0
    g = de_poligonos(polis)
    assert g['type'] == 'MultiPolygon' and abs(area_m2(g) - (1e6 - 4e4 + 1600 + 1e4)) < 1e-6
    # UTM de 7 dígitos: a área não perde casas
    longe = [(p[0] + 500000, p[1] + 7456000) for p in quad]
    assert area_assinada(longe) == 1e6
    linha = {'type': 'LineString', 'coordinates': [(0, 0), (3, 4), (3, 10)]}
    assert comprimento_m(linha) == 11 and familia(linha) == 'linha' and n_vertices(linha) == 3
    dobro = mapear(g, lambda xs, ys: (xs * 2, ys * 2))
    assert abs(area_m2(dobro) - 4 * area_m2(g)) < 1e-6
    # medida em graus: quadrado de 0,01 grau perto de Campinas, cerca de 113,7 ha
    graus = {'type': 'Polygon', 'coordinates': [[(-47.05, -22.85), (-47.04, -22.85), (-47.04, -22.84), (-47.05, -22.84), (-47.05, -22.85)]]}
    areas, comp, alvo = medir([{'geometry': graus, 'properties': {}}, {'geometry': None, 'properties': {}}], projecao.geo())
    assert 113 < areas[0] < 114.5 and areas[1] is None and (alvo['zona'], alvo['sul']) == (23, True)
    # no elipsoide: 113,6646 ha (o valor do PROJ para este quadrado); a plana em UTM fica 0,03% acima aqui
    elip = areas_no_elipsoide([{'geometry': graus, 'properties': {}}], projecao.geo())[0]
    assert abs(elip - 113.6646) < 0.0002 and abs(areas[0] / elip - 1) < 0.002, (elip, areas[0])
    # simplificação: tira o vértice no meio da reta, mantém os cantos
    com_meio = [(0, 0), (500, 0.01), (1000, 0), (1000, 1000), (0, 1000), (0, 0)]
    s = simplificar({'type': 'Polygon', 'coordinates': [com_meio]}, 0.5)
    assert len(s['coordinates'][0]) == 5 and abs(area_m2(s) - 1e6) < 10
    print('geom OK: área, aninhamento de anéis, ponto dentro, medidas em graus e em metros, simplificação')
