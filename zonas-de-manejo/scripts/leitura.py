"""Leitura dos pontos brutos (CSV, TXT ou shapefile de pontos, soltos ou em .zip).

O que sai daqui é uma tabela em colunas (vetores do numpy), as coordenadas
como vieram, o palpite de qual coluna é o quê (valor, velocidade, umidade,
largura, hora, passada) e a hora convertida em segundos. Palpite é palpite:
quem confirma a coluna do valor é o usuário.

Teste embutido: python scripts/leitura.py
"""

import csv
import re
import tempfile
import unicodedata
import zipfile
from pathlib import Path

import numpy as np

import geometria

NOMES_X = ('longitude', 'long', 'lon', 'lng', 'x', 'coordx', 'xcoord', 'easting', 'este', 'leste', 'coordenadax',
           'utmx', 'pointx')
NOMES_Y = ('latitude', 'lat', 'y', 'coordy', 'ycoord', 'northing', 'norte', 'coordenaday', 'utmy', 'pointy')
# pistas no nome da coluna, na ordem de preferência
PISTAS = {
    'valor': (r'^prod', r'produt', r'yld', r'yield', r'rendim', r'^rend', r'tch', r'^cea', r'^eca', r'condut',
              r'ndvi', r'ndre'),
    'velocidade': (r'veloc', r'speed', r'^spd', r'^vel'),
    'umidade': (r'umid', r'moist', r'humid'),
    'largura': (r'largur', r'swath', r'swth', r'width'),
    'tempo': (r'isotime', r'datahora', r'datetime', r'timestamp', r'gpstime', r'^hora', r'time', r'tempo'),
    'passada': (r'passada', r'passnum', r'^pass', r'^tiro'),
}


def chave(nome):
    sem_acento = unicodedata.normalize('NFKD', str(nome)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', sem_acento.lower())


def _numero(texto):
    texto = texto.strip()
    if not texto:
        return np.nan
    if ',' in texto and '.' not in texto:
        texto = texto.replace(',', '.')
    try:
        return float(texto)
    except ValueError:
        return np.nan


def _coluna(valores):
    """Vetor de float se pelo menos 80% dos valores preenchidos forem número; senão, texto."""
    try:
        return np.asarray(valores, dtype=float), True
    except (ValueError, TypeError):
        pass
    textos = ['' if v is None else str(v) for v in valores]
    numeros = np.array([_numero(v) for v in textos])
    preenchidos = sum(1 for v in textos if v.strip())
    if preenchidos and np.isfinite(numeros).sum() >= 0.8 * preenchidos:
        return numeros, True
    return np.array(textos, dtype=object), False


def _abrir(caminho):
    """Devolve o arquivo de dados; se for .zip, extrai e acha o .shp ou o .csv lá dentro."""
    caminho = Path(caminho)
    if caminho.suffix.lower() != '.zip':
        return caminho
    pasta = Path(tempfile.mkdtemp(prefix='pontos_'))
    with zipfile.ZipFile(caminho) as z:
        for nome in z.namelist():
            destino = (pasta / nome).resolve()
            if pasta.resolve() not in destino.parents:  # nome malicioso tentando sair da pasta
                continue
            z.extract(nome, pasta)
    for ext in ('.shp', '.csv', '.txt'):
        achados = sorted(pasta.rglob('*' + ext))
        if achados:
            return achados[0]
    raise ValueError('o .zip não traz .shp, .csv nem .txt')


def _ler_texto(caminho):
    bruto = Path(caminho).read_bytes()
    for codificacao in ('utf-8-sig', 'latin-1'):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    primeira = texto.split('\n', 1)[0]
    separador = max((';', '\t', ',', '|'), key=primeira.count)
    linhas = list(csv.reader(texto.splitlines(), delimiter=separador))
    linhas = [l for l in linhas if any(c.strip() for c in l)]
    if len(linhas) < 2:
        raise ValueError('o arquivo não tem linhas de dados')
    cabecalho = [c.strip() or f'coluna{i + 1}' for i, c in enumerate(linhas[0])]
    largura = len(cabecalho)
    corpo = [l + [''] * (largura - len(l)) for l in linhas[1:]]
    return cabecalho, {nome: [l[i] for l in corpo] for i, nome in enumerate(cabecalho)}


def ler_pontos(caminho, coluna_x=None, coluna_y=None):
    """Lê os pontos. Devolve dict com: colunas (ordem do arquivo), dados {nome: vetor},
    numericas (nomes), x, y (como vieram), crs ('geo' | 'utm'), zona ((n, sul) | None), n, origem."""
    arquivo = _abrir(caminho)
    zona = None
    if arquivo.suffix.lower() == '.shp':
        from shapefile_min import ler_shp
        tipo, geoms, atributos, zona = ler_shp(str(arquivo))
        if tipo != 'ponto':
            raise ValueError('o shapefile precisa ser de PONTOS (um ponto por leitura da máquina)')
        nomes = list(atributos[0]) if atributos else []
        bruto = {n: [a.get(n) for a in atributos] for n in nomes}
        x = np.array([g[0] for g in geoms], dtype=float)
        y = np.array([g[1] for g in geoms], dtype=float)
    else:
        nomes, bruto = _ler_texto(arquivo)
        x = y = None
    dados, numericas = {}, []
    for nome in nomes:
        dados[nome], numerica = _coluna(bruto[nome])
        if numerica:
            numericas.append(nome)
    if x is None:
        por_chave = {chave(n): n for n in numericas}
        coluna_x = coluna_x or next((por_chave[k] for k in NOMES_X if k in por_chave), None)
        coluna_y = coluna_y or next((por_chave[k] for k in NOMES_Y if k in por_chave), None)
        if not coluna_x or not coluna_y or coluna_x not in dados or coluna_y not in dados:
            raise ValueError('não achei as colunas de coordenada: informe --x e --y. Colunas: ' + ', '.join(nomes))
        x, y = dados[coluna_x].astype(float), dados[coluna_y].astype(float)
    bons = np.isfinite(x) & np.isfinite(y)
    geo = bool(bons.any()) and bool((np.abs(x[bons]) <= 180).all() and (np.abs(y[bons]) <= 90).all())
    return {'colunas': nomes, 'dados': dados, 'numericas': numericas, 'x': x, 'y': y,
            'crs': 'geo' if geo else 'utm', 'zona': zona, 'n': len(x), 'origem': arquivo.name,
            'coluna_x': coluna_x, 'coluna_y': coluna_y}


def adivinhar(tabela):
    """Palpite de qual coluna faz cada papel: {'valor': nome | None, 'velocidade': …}."""
    usadas = {tabela.get('coluna_x'), tabela.get('coluna_y')}
    papeis = {}
    for papel, pistas in PISTAS.items():
        candidatas = [n for n in tabela['colunas'] if n not in usadas
                      and (papel in ('tempo', 'passada') or n in tabela['numericas'])]
        achada = next((n for pista in pistas for n in candidatas if re.search(pista, chave(n))), None)
        papeis[papel] = achada
        usadas.add(achada)
    return papeis


_HORA = re.compile(r'(\d{1,2}):(\d{2}):(\d{2}(?:[.,]\d+)?)')
_DATA_ISO = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
_DATA_BR = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})')


def segundos(valores):
    """Converte a coluna de hora em segundos corridos. Aceita número (já em segundos) e texto com
    HH:MM:SS, com ou sem data na frente. Devolve None se menos de 80% das linhas forem lidas."""
    valores = np.asarray(valores)
    if valores.dtype.kind in 'fiu':
        t = valores.astype(float)
        return t if np.isfinite(t).mean() >= 0.8 else None
    t = np.full(len(valores), np.nan)
    tem_data = False
    for i, texto in enumerate(valores):
        texto = str(texto)
        hora = _HORA.search(texto)
        if not hora:
            continue
        s = int(hora.group(1)) * 3600 + int(hora.group(2)) * 60 + float(hora.group(3).replace(',', '.'))
        data = _DATA_ISO.search(texto)
        dia = None
        if data:
            dia = (int(data.group(1)), int(data.group(2)), int(data.group(3)))
        else:
            data = _DATA_BR.search(texto)
            if data:
                dia = (int(data.group(3)), int(data.group(2)), int(data.group(1)))
        if dia:
            tem_data = True
            s += (dia[0] * 372 + dia[1] * 31 + dia[2]) * 86400.0  # só precisa crescer com o calendário
        t[i] = s
    if np.isfinite(t).mean() < 0.8:
        return None
    if not tem_data:  # virou a meia-noite: soma um dia dali em diante
        volta = np.r_[0, np.cumsum(np.diff(np.nan_to_num(t, nan=0.0)) < -43200)]
        t = t + volta * 86400.0
    return t - np.nanmin(t)


def projetar(x, y, crs, zona=None):
    """Coordenadas em metros (UTM). Devolve (X, Y, zona, sul); em 'utm' sem zona, zona e sul vêm None."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if crs == 'utm':
        return x, y, (zona[0] if zona else None), (zona[1] if zona else None)
    bons = np.isfinite(x) & np.isfinite(y) & ~((x == 0) & (y == 0))
    if not bons.any():
        raise ValueError('nenhuma coordenada válida no arquivo')
    if not zona:
        zona = geometria.zona_de(float(np.median(x[bons])), float(np.median(y[bons])))
    X, Y = np.full(len(x), np.nan), np.full(len(y), np.nan)
    X[bons], Y[bons] = geometria.utm_direta(x[bons], y[bons], zona[0], zona[1])
    return X, Y, zona[0], zona[1]


if __name__ == '__main__':
    import os

    assert chave('Produtividade (t/ha)') == 'produtividadetha' and _numero('3,25') == 3.25
    with tempfile.TemporaryDirectory() as pasta:
        arq = os.path.join(pasta, 'colheita.csv')
        with open(arq, 'w', encoding='latin-1') as f:
            f.write('Longitude;Latitude;Hora;Prod (t/ha);Velocidade;Umidade;Largura;Operador\n')
            f.write('-49,61;-22,21;23:59:58;3,52;6,1;13,2;9;João\n')
            f.write('-49,6101;-22,2101;23:59:59;3,60;6,0;13,1;9;João\n')
            f.write('-49,6102;-22,2102;00:00:00;;6,2;13,0;9;João\n')
            f.write('\n')
        t = ler_pontos(arq)
        assert t['n'] == 3 and t['crs'] == 'geo' and t['coluna_x'] == 'Longitude', t
        assert 'Operador' not in t['numericas'] and t['dados']['Operador'][0] == 'João'
        assert np.isnan(t['dados']['Prod (t/ha)'][2]) and t['dados']['Prod (t/ha)'][0] == 3.52
        papeis = adivinhar(t)
        assert papeis == {'valor': 'Prod (t/ha)', 'velocidade': 'Velocidade', 'umidade': 'Umidade',
                          'largura': 'Largura', 'tempo': 'Hora', 'passada': None}, papeis
        assert segundos(t['dados']['Hora']).tolist() == [0.0, 1.0, 2.0]
        X, Y, zona, sul = projetar(t['x'], t['y'], t['crs'])
        assert zona == 22 and sul and 640000 < X[0] < 645000 and abs(np.hypot(X[1] - X[0], Y[1] - Y[0]) - 15.1) < 1

        # separado por vírgula, com data e hora juntas, dentro de um zip
        with open(os.path.join(pasta, 'b.csv'), 'w', encoding='utf-8') as f:
            f.write('x,y,IsoTime,VRYIELDMAS\n500000,7500000,2026-03-01T10:00:00.0Z,4.1\n500002,7500000,2026-03-01T10:00:01.0Z,4.2\n')
        with zipfile.ZipFile(os.path.join(pasta, 'b.zip'), 'w') as z:
            z.write(os.path.join(pasta, 'b.csv'), 'b.csv')
        t = ler_pontos(os.path.join(pasta, 'b.zip'))
        assert t['crs'] == 'utm' and adivinhar(t)['valor'] == 'VRYIELDMAS' and adivinhar(t)['tempo'] == 'IsoTime'
        assert segundos(t['dados']['IsoTime']).tolist() == [0.0, 1.0]
        assert projetar(t['x'], t['y'], 'utm')[2] is None
    assert segundos(np.array(['sem hora', 'x'], dtype=object)) is None
    assert segundos(np.array([10.0, 11.0])).tolist() == [10.0, 11.0]
    print('leitura OK')
