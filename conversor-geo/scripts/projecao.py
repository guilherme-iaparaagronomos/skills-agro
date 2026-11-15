"""Sistemas de referência (SRC) e projeção UTM, só com numpy.

O que este módulo sabe converter, com certeza:
- graus (SIRGAS 2000 ou WGS 84) <-> UTM (qualquer fuso, norte ou sul), pelas
  séries de Krüger (as mesmas que as bibliotecas de geodésia usam; erro bem
  abaixo de 1 mm dentro do fuso);
- UTM de um fuso -> UTM de outro, passando pelos graus.

SIRGAS 2000 e WGS 84 são tratados como equivalentes: a diferença entre os dois
é de centímetros, abaixo do que um GPS de campo mede. Nenhuma coordenada muda
de um para o outro; só o rótulo.

O que este módulo RECUSA, com o motivo: SAD 69, Córrego Alegre, outros datums e
outras projeções (Policônica, Albers, Lambert, Web Mercator, Mercator
transversa com parâmetros que não são os do UTM). Trocar de datum exige
parâmetros oficiais de transformação e desloca dezenas de metros; isso se faz
no QGIS, não aqui.

Um SRC é um dicionário:
  {'tipo': 'geo' | 'utm', 'datum': 'SIRGAS 2000' | 'WGS 84', 'zona': int,
   'sul': bool, 'origem': de onde veio a informação}
"""

import math
import re

import numpy as np

ELIPSOIDES = {'SIRGAS 2000': (6378137.0, 1 / 298.257222101), 'WGS 84': (6378137.0, 1 / 298.257223563)}
K0 = 0.9996
# caixa folgada do Brasil (com as ilhas oceânicas), para os avisos de "fora do Brasil"
BRASIL = (-74.5, -34.5, -28.0, 6.0)


class SrcRecusado(ValueError):
    """SRC que a skill não converte com certeza."""


class SrcAmbiguo(ValueError):
    """Falta informação para saber o SRC (o usuário precisa dizer)."""


# ---------------------------------------------------------------- séries de Krüger

def _serie(f):
    n = f / (2 - f)
    n2, n3, n4 = n * n, n ** 3, n ** 4
    raio = (1 + n2 / 4 + n4 / 64) / (1 + n)  # vezes o semieixo maior
    alfa = (n / 2 - 2 * n2 / 3 + 5 * n3 / 16 + 41 * n4 / 180,
            13 * n2 / 48 - 3 * n3 / 5 + 557 * n4 / 1440,
            61 * n3 / 240 - 103 * n4 / 140,
            49561 * n4 / 161280)
    beta = (n / 2 - 2 * n2 / 3 + 37 * n3 / 96 - n4 / 360,
            n2 / 48 + n3 / 15 - 437 * n4 / 1440,
            17 * n3 / 480 - 37 * n4 / 840,
            4397 * n4 / 161280)
    return raio, alfa, beta


def meridiano_central(zona):
    return zona * 6 - 183


def zona_de(lon, lat=0.0):
    """(fuso, sul?) do ponto em graus."""
    return int(min(60, max(1, math.floor((lon + 180) / 6) + 1))), lat < 0


def utm_direta(lons, lats, zona, sul, datum='SIRGAS 2000'):
    """Graus -> UTM (E, N em metros), vetorizada."""
    a, f = ELIPSOIDES[datum]
    raio, alfa, _ = _serie(f)
    e = math.sqrt(f * (2 - f))
    lam = np.radians(np.asarray(lons, dtype=float)) - math.radians(meridiano_central(zona))
    fi = np.radians(np.asarray(lats, dtype=float))
    s = np.sin(fi)
    t = np.sinh(np.arctanh(s) - e * np.arctanh(e * s))
    xi = np.arctan2(t, np.cos(lam))
    eta = np.arctanh(np.sin(lam) / np.sqrt(1 + t * t))
    x, y = eta.copy(), xi.copy()
    for j, c in enumerate(alfa, 1):
        x = x + c * np.cos(2 * j * xi) * np.sinh(2 * j * eta)
        y = y + c * np.sin(2 * j * xi) * np.cosh(2 * j * eta)
    return 500000 + K0 * a * raio * x, (10000000 if sul else 0) + K0 * a * raio * y


def utm_inversa(es, ns, zona, sul, datum='SIRGAS 2000'):
    """UTM -> graus (lon, lat), vetorizada."""
    a, f = ELIPSOIDES[datum]
    raio, _, beta = _serie(f)
    e = math.sqrt(f * (2 - f))
    xi = (np.asarray(ns, dtype=float) - (10000000 if sul else 0)) / (K0 * a * raio)
    eta = (np.asarray(es, dtype=float) - 500000) / (K0 * a * raio)
    xi1, eta1 = xi.copy(), eta.copy()
    for j, c in enumerate(beta, 1):
        xi1 = xi1 - c * np.sin(2 * j * xi) * np.cosh(2 * j * eta)
        eta1 = eta1 - c * np.cos(2 * j * xi) * np.sinh(2 * j * eta)
    chi = np.arcsin(np.sin(xi1) / np.cosh(eta1))
    # latitude conforme -> geodésica: a relação é exata e a iteração fecha em poucas voltas
    fi = chi.copy()
    for _ in range(8):
        es_ = e * np.sin(fi)
        fi = 2 * np.arctan(np.tan(np.pi / 4 + chi / 2) * ((1 + es_) / (1 - es_)) ** (e / 2)) - np.pi / 2
    lam = np.arctan2(np.sinh(eta1), np.cos(xi1))
    return np.degrees(lam) + meridiano_central(zona), np.degrees(fi)


# ---------------------------------------------------------------- descrição do SRC

def geo(datum='SIRGAS 2000', origem='informado'):
    return {'tipo': 'geo', 'datum': datum, 'zona': None, 'sul': None, 'origem': origem}


def utm(zona, sul, datum='SIRGAS 2000', origem='informado'):
    if not 1 <= int(zona) <= 60:
        raise SrcRecusado(f'fuso UTM {zona} não existe (vai de 1 a 60)')
    return {'tipo': 'utm', 'datum': datum, 'zona': int(zona), 'sul': bool(sul), 'origem': origem}


def epsg(src):
    """Código EPSG do SRC, ou None quando não há código para aquele fuso."""
    if src['tipo'] == 'geo':
        return 4674 if src['datum'] == 'SIRGAS 2000' else 4326
    z, sul = src['zona'], src['sul']
    if src['datum'] == 'WGS 84':
        return (32700 if sul else 32600) + z
    if sul and 17 <= z <= 25:
        return 31960 + z
    if sul and z == 26:
        return 5396
    if not sul and 11 <= z <= 22:
        return 31954 + z
    if not sul and z in (23, 24):
        return 6187 + z  # 6210 e 6211
    return None


def nome(src):
    """'SIRGAS 2000 / UTM fuso 22S (EPSG:31982)'."""
    if src['tipo'] == 'geo':
        base = f"{src['datum']}, em graus"
    else:
        base = f"{src['datum']} / UTM fuso {src['zona']}{'S' if src['sul'] else 'N'}"
    codigo = epsg(src)
    return f'{base} (EPSG:{codigo})' if codigo else base


def src_do_epsg(codigo, origem='informado'):
    c = int(codigo)
    if c == 4674:
        return geo('SIRGAS 2000', origem)
    if c in (4326, 4979):
        return geo('WGS 84', origem)
    if 31965 <= c <= 31976:
        return utm(c - 31954, False, 'SIRGAS 2000', origem)
    if 31977 <= c <= 31985:
        return utm(c - 31960, True, 'SIRGAS 2000', origem)
    if c in (6210, 6211):
        return utm(c - 6187, False, 'SIRGAS 2000', origem)
    if c == 5396:
        return utm(26, True, 'SIRGAS 2000', origem)
    if 32601 <= c <= 32660:
        return utm(c - 32600, False, 'WGS 84', origem)
    if 32701 <= c <= 32760:
        return utm(c - 32700, True, 'WGS 84', origem)
    recusas = {
        'SAD 69': set(range(29168, 29173)) | set(range(29177, 29186)) | set(range(29187, 29196)) | {4618, 4291, 5527} | set(range(5531, 5536)),
        'Córrego Alegre': set(range(22521, 22526)) | {4225, 5524} | set(range(5536, 5540)),
        'SIRGAS 1995': {4170} | set(range(31986, 32001)),
        'Web Mercator, dos mapas da internet': {3857, 900913, 3785},
        'Policônica do Brasil': {5880},
        'Mercator do Brasil': {5641},
        'Albers da América do Sul': {102033},
    }
    for qual, codigos in recusas.items():
        if c in codigos:
            raise SrcRecusado(_recusa(f'EPSG:{c} ({qual})'))
    raise SrcRecusado(_recusa(f'EPSG:{c}'))


def _recusa(o_que):
    return (f'{o_que} não é convertido por esta skill. Ela trabalha com graus (SIRGAS 2000 ou WGS 84) e com UTM '
            'nesses dois datums. Mudar de datum ou de projeção desloca as coordenadas em dezenas de metros se for '
            'feito sem os parâmetros oficiais: reprojete no QGIS (Exportar > Salvar feições como, SRC EPSG:4674) '
            'e envie de novo.')


def src_informado(texto):
    """O que o usuário digitou: '4674', 'EPSG:31982', 'utm22s', '22S', 'sirgas', 'wgs84', 'graus'."""
    t = re.sub(r'[\s_/]+', '', str(texto).strip().lower()).replace('zona', '').replace('fuso', '')
    datum = 'WGS 84' if 'wgs' in t else 'SIRGAS 2000'
    t = t.replace('-wgs84', '').replace('wgs84', '').replace('wgs', '').replace('-sirgas2000', '').replace('sirgas2000', '').replace('sirgas', '')
    m = re.fullmatch(r'(?:epsg:?)?(\d{4,6})', t)
    if m:
        return src_do_epsg(m.group(1))
    m = re.fullmatch(r'(?:utm)?-?(\d{1,2})(s|n|sul|norte)', t)
    if m:
        return utm(int(m.group(1)), m.group(2).startswith('s'), datum)
    if t in ('', 'geo', 'graus', 'geografico', 'geográfico', 'geograficas', 'geográficas', 'latlon', 'lonlat'):
        return geo(datum)
    raise SrcAmbiguo(f'não entendi o SRC "{texto}". Exemplos: 4674, 4326, EPSG:31982, utm22s, 23S, graus')


# ---------------------------------------------------------------- leitura do .prj

def _norma(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _datum_do_wkt(wkt):
    nomes = re.findall(r'(?:DATUM|GEOGCS|GEOGCRS|BASEGEOGCRS|GEODCRS)\s*\[\s*"([^"]+)"', wkt, re.I)
    junto = ' '.join(_norma(n) for n in nomes)
    if 'southamerican1969' in junto or 'sad69' in junto or 'sad1969' in junto:
        return None, 'SAD 69'
    if 'corregoalegre' in junto:
        return None, 'Córrego Alegre'
    if 'sirgas2000' in junto or 'americas2000' in junto or 'americadelsur2000' in junto:
        return 'SIRGAS 2000', None
    if 'wgs1984' in junto or 'wgs84' in junto or 'worldgeodeticsystem1984' in junto:
        return 'WGS 84', None
    return None, (nomes[0] if nomes else 'datum não identificado')


def _parametro(wkt, *nomes):
    for n in nomes:
        m = re.search(r'PARAMETER\s*\[\s*"' + n + r'"\s*,\s*([-+0-9.eE]+)', wkt, re.I)
        if m:
            return float(m.group(1))
    return None


def src_do_prj(wkt):
    """Lê o texto de um .prj. Devolve o SRC ou levanta SrcRecusado com a explicação."""
    wkt = wkt.strip()
    if not wkt:
        raise SrcAmbiguo('o .prj está vazio')
    datum, ruim = _datum_do_wkt(wkt)
    projetado = bool(re.match(r'\s*(PROJCS|PROJCRS)', wkt, re.I))
    if datum is None:
        m = re.search(r'(?:AUTHORITY|ID)\s*\[\s*"EPSG"\s*,\s*"?(\d+)"?\s*\]\s*\]\s*$', wkt, re.I)
        if m:
            return src_do_epsg(m.group(1), 'lido do .prj')
        raise SrcRecusado(_recusa(f'O datum do arquivo ({ruim})'))
    if not projetado:
        if not re.match(r'\s*(GEOGCS|GEOGCRS|GEODCRS)', wkt, re.I):
            raise SrcRecusado(_recusa('O sistema do .prj'))
        return geo(datum, 'lido do .prj')
    metodo = re.search(r'(?:PROJECTION|METHOD)\s*\[\s*"([^"]+)"', wkt, re.I)
    nome_metodo = metodo.group(1) if metodo else 'projeção não identificada'
    if _norma(nome_metodo) not in ('transversemercator', 'gausskruger'):
        raise SrcRecusado(_recusa(f'A projeção do arquivo ({nome_metodo})'))
    k = _parametro(wkt, 'scale_factor', 'Scale factor at natural origin')
    fe = _parametro(wkt, 'false_easting', 'False easting')
    fn = _parametro(wkt, 'false_northing', 'False northing')
    mc = _parametro(wkt, 'central_meridian', 'longitude_of_origin', 'Longitude of natural origin')
    lat0 = _parametro(wkt, 'latitude_of_origin', 'Latitude of natural origin') or 0.0
    metro = re.search(r'UNIT\s*\[\s*"(met[er]{2}|m)"\s*,\s*1(\.0*)?\s*[\],]', wkt, re.I) or re.search(r'LENGTHUNIT\s*\[\s*"met', wkt, re.I)
    zona = None if mc is None else (mc + 183) / 6
    eh_utm = (k is not None and abs(k - K0) < 1e-9 and fe is not None and abs(fe - 500000) < 1e-6
              and fn is not None and (abs(fn) < 1e-6 or abs(fn - 10000000) < 1e-6) and abs(lat0) < 1e-9
              and zona is not None and abs(zona - round(zona)) < 1e-9 and 1 <= round(zona) <= 60 and metro)
    if not eh_utm:
        raise SrcRecusado(_recusa('A Mercator transversa do arquivo (os parâmetros não são os do UTM)'))
    return utm(int(round(zona)), abs(fn - 10000000) < 1e-6, datum, 'lido do .prj')


_GCS = {
    'SIRGAS 2000': 'GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
                   'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]',
    'WGS 84': 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
              'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]',
}


def prj_de(src):
    """Texto do .prj (no formato que o QGIS e o ArcGIS reconhecem)."""
    gcs = _GCS[src['datum']]
    if src['tipo'] == 'geo':
        return gcs
    z, sul = src['zona'], src['sul']
    rotulo = ('SIRGAS_2000' if src['datum'] == 'SIRGAS 2000' else 'WGS_1984') + f"_UTM_Zone_{z}{'S' if sul else 'N'}"
    return (f'PROJCS["{rotulo}",{gcs},PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],'
            f'PARAMETER["False_Northing",{10000000.0 if sul else 0.0}],PARAMETER["Central_Meridian",{float(meridiano_central(z))}],'
            'PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]')


# ---------------------------------------------------------------- dedução e conferência

def deduzir(xs, ys):
    """Sem .prj: olha a grandeza das coordenadas. Devolve o SRC em graus, ou levanta
    SrcAmbiguo quando parecem metros (aí só o usuário sabe o fuso)."""
    xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    if not len(xs):
        raise SrcAmbiguo('o arquivo não tem coordenadas')
    if np.all(np.abs(xs) <= 180) and np.all(np.abs(ys) <= 90):
        return geo('SIRGAS 2000', 'deduzido das coordenadas (parecem graus)')
    if np.all((xs > 100000) & (xs < 900000)) and np.all((ys >= 0) & (ys <= 10000000)):
        raise SrcAmbiguo('as coordenadas parecem UTM em metros, mas o arquivo não diz o fuso. Pergunte ao usuário o '
                         'fuso e o hemisfério (ex.: 22S) e repita com --src-entrada utm22s')
    raise SrcAmbiguo('as coordenadas não parecem graus nem UTM (pode ser outra projeção, ou colunas trocadas). '
                     'Pergunte ao usuário em que sistema o arquivo está')


def no_brasil(lon, lat):
    return BRASIL[0] <= lon <= BRASIL[2] and BRASIL[1] <= lat <= BRASIL[3]


def avisos_de_posicao(lon, lat, src):
    """Sinais de coordenada trocada ou de fuso errado, a partir do centro do arquivo em graus."""
    avisos = []
    if no_brasil(lon, lat):
        return avisos
    if src['tipo'] == 'geo' and no_brasil(lat, lon):
        avisos.append(f'o centro do arquivo cai em lon {lon:.4f}, lat {lat:.4f}, fora do Brasil; com as duas trocadas cai '
                      'dentro. Latitude e longitude parecem INVERTIDAS: confira e repita com --trocar-xy')
    elif src['tipo'] == 'utm':
        avisos.append(f'com o fuso {src["zona"]}{"S" if src["sul"] else "N"} o centro do arquivo cai em lon {lon:.4f}, '
                      f'lat {lat:.4f}, fora do Brasil. Confira o fuso e o hemisfério com o usuário')
    else:
        avisos.append(f'o centro do arquivo cai em lon {lon:.4f}, lat {lat:.4f}, fora do Brasil')
    return avisos


def conversor(origem, destino):
    """Função f(xs, ys) -> (xs, ys) que leva as coordenadas de um SRC ao outro."""
    if origem['tipo'] == destino['tipo'] and (origem['tipo'] == 'geo' or (origem['zona'], origem['sul']) == (destino['zona'], destino['sul'])):
        return lambda xs, ys: (np.asarray(xs, dtype=float), np.asarray(ys, dtype=float))

    def f(xs, ys):
        if origem['tipo'] == 'utm':
            xs, ys = utm_inversa(xs, ys, origem['zona'], origem['sul'], origem['datum'])
        if destino['tipo'] == 'utm':
            xs, ys = utm_direta(xs, ys, destino['zona'], destino['sul'], destino['datum'])
        return xs, ys
    return f


if __name__ == '__main__':
    # valores de referência: conferidos contra o PROJ (biblioteca de geodésia do QGIS) em 14/11/2026
    casos = [(-51.0, -23.0, 22, True, 500000.0, 7456480.2365), (-47.05, -22.85, 23, True, 289649.8877, 7471623.3295),
             (-60.5, 3.2, 20, False, 777844.7627, 354038.3710), (-38.9, -9.4, 24, True, 510979.0637, 8960922.8869)]
    for lon, lat, z, sul, e_ref, n_ref in casos:
        e, n = utm_direta([lon], [lat], z, sul)
        assert abs(e[0] - e_ref) < 0.0002 and abs(n[0] - n_ref) < 0.0002, (lon, lat, e[0], n[0])
        lo, la = utm_inversa(e, n, z, sul)
        assert abs(lo[0] - lon) < 1e-10 and abs(la[0] - lat) < 1e-10, (lo, la)
    # ida e volta numa grade que cobre o Brasil, inclusive fora do fuso natural (até 4 graus do meridiano)
    rng = np.random.default_rng(1)
    lons, lats = rng.uniform(-74, -34, 4000), rng.uniform(-34, 5.3, 4000)
    for desvio in (0, 1):
        zs = np.clip(np.floor((lons + 180) / 6).astype(int) + 1 + desvio, 1, 60)
        for z in np.unique(zs):
            m = (zs == z) & (np.abs(lons - meridiano_central(z)) < 4)
            if not m.any():
                continue
            for sul in (True, False):
                e, n = utm_direta(lons[m], lats[m], z, sul)
                lo, la = utm_inversa(e, n, z, sul)
                assert np.max(np.abs(lo - lons[m])) < 1e-9 and np.max(np.abs(la - lats[m])) < 1e-9
    assert zona_de(-51.2, -23) == (22, True) and zona_de(-60.5, 3.2) == (20, False)

    esri = ('PROJCS["SIRGAS_2000_UTM_Zone_22S",GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
            'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],'
            'PARAMETER["False_Northing",10000000.0],PARAMETER["Central_Meridian",-51.0],PARAMETER["Scale_Factor",0.9996],'
            'PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]')
    s = src_do_prj(esri)
    assert (s['tipo'], s['zona'], s['sul'], s['datum']) == ('utm', 22, True, 'SIRGAS 2000') and epsg(s) == 31982
    for src in (geo(), geo('WGS 84'), utm(22, True), utm(20, False), utm(23, True, 'WGS 84'), utm(26, True), utm(23, False)):
        volta = src_do_prj(prj_de(src))
        assert (volta['tipo'], volta['zona'], volta['sul'], volta['datum']) == (src['tipo'], src['zona'], src['sul'], src['datum'])
    assert [epsg(x) for x in (geo(), geo('WGS 84'), utm(22, True), utm(20, False), utm(23, True, 'WGS 84'), utm(26, True), utm(23, False))] \
        == [4674, 4326, 31982, 31974, 32723, 5396, 6210]
    for ruim in ('GEOGCS["GCS_South_American_1969",DATUM["D_South_American_1969",SPHEROID["GRS_1967_Truncated",6378160.0,298.25]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]',
                 'GEOGCS["GCS_Corrego_Alegre",DATUM["D_Corrego_Alegre",SPHEROID["International_1924",6378388.0,297.0]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]',
                 esri.replace('0.9996', '1.0'), esri.replace('Transverse_Mercator', 'Albers').replace('SIRGAS_2000_UTM_Zone_22S', 'Albers'),
                 esri.replace('-51.0', '-50.0')):
        try:
            src_do_prj(ruim)
            raise AssertionError('devia recusar: ' + ruim[:60])
        except SrcRecusado:
            pass
    assert src_informado('utm22s')['zona'] == 22 and src_informado('23 S')['sul'] and not src_informado('utm 20 n')['sul']
    assert src_informado('EPSG:4326')['datum'] == 'WGS 84' and src_informado('31983')['zona'] == 23
    assert src_informado('utm22s-wgs84')['datum'] == 'WGS 84' and src_informado('graus')['tipo'] == 'geo'
    for texto, erro in (('29192', SrcRecusado), ('3857', SrcRecusado), ('abc', SrcAmbiguo)):
        try:
            src_informado(texto)
            raise AssertionError(texto)
        except erro:
            pass
    assert deduzir([-51.2, -51.1], [-23.0, -23.1])['tipo'] == 'geo'
    try:
        deduzir([512000.0], [7455000.0])
        raise AssertionError('devia pedir o fuso')
    except SrcAmbiguo:
        pass
    assert avisos_de_posicao(-23.0, -51.0, geo()) and not avisos_de_posicao(-51.0, -23.0, geo())
    f = conversor(utm(22, True), utm(23, True))
    e, n = f([700000.0], [7456000.0])
    lo, la = utm_inversa([700000.0], [7456000.0], 22, True)
    e2, n2 = utm_direta(lo, la, 23, True)
    assert abs(e[0] - e2[0]) < 1e-6 and abs(n[0] - n2[0]) < 1e-6
    print('projecao OK: UTM de ida e volta (erro < 1e-9 grau), valores de referência, leitura e escrita de .prj, recusas')
