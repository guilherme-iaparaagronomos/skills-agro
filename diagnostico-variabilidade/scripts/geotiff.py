"""GeoTIFF em Python puro + numpy: leitura de uma banda, amostragem em pontos e escrita.

Leitura (ler_geotiff): tiras ou ladrilhos; sem compressão, Deflate ou LZW;
preditor nenhum, horizontal ou de ponto flutuante; inteiros de 8, 16 e 32 bits
e reais de 32 e 64 bits; referência por escala + amarração ou por matriz;
SRC geográfico (graus) ou UTM (SIRGAS 2000 e WGS 84). Fora disso levanta
ValueError dizendo o que não é coberto, para o usuário reexportar o arquivo.

Amostragem (amostrar): valor do raster em pontos dados em UTM, com a
conversão para o SRC do raster quando ele é outro.

Escrita (escrever_geotiff): float32, uma banda, UTM, NoData = -9999.

Teste embutido: python scripts/geotiff.py
"""

import math
import struct
import zlib

import numpy as np

import geometria
from areas import utm_inversa

_TAMANHO = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 16: 8}
_FORMATO = {1: 'B', 3: 'H', 4: 'I', 6: 'b', 8: 'h', 9: 'i', 11: 'f', 12: 'd', 16: 'Q'}
_NODATA = -9999.0
TETO_DE_PIXELS = 80_000_000


def _etiquetas(dados):
    if dados[:2] not in (b'II', b'MM') or len(dados) < 8:
        raise ValueError('o arquivo não é um TIFF')
    ordem = '<' if dados[:2] == b'II' else '>'
    if struct.unpack(ordem + 'H', dados[2:4])[0] != 42:
        raise ValueError('BigTIFF não é coberto: exporte como GeoTIFF comum')
    pos = struct.unpack(ordem + 'I', dados[4:8])[0]
    n = struct.unpack(ordem + 'H', dados[pos:pos + 2])[0]
    etiquetas = {}
    for i in range(n):
        p = pos + 2 + i * 12
        tag, tipo, quantos = struct.unpack(ordem + 'HHI', dados[p:p + 8])
        if tipo not in _TAMANHO:
            continue
        tamanho = _TAMANHO[tipo] * quantos
        if tamanho <= 4:
            bruto = dados[p + 8:p + 8 + tamanho]
        else:
            inicio = struct.unpack(ordem + 'I', dados[p + 8:p + 12])[0]
            bruto = dados[inicio:inicio + tamanho]
        if len(bruto) < tamanho:
            raise ValueError('TIFF truncado')
        if tipo == 2:
            etiquetas[tag] = bruto.split(b'\x00')[0].decode('latin-1')
        elif tipo in _FORMATO:
            etiquetas[tag] = struct.unpack(ordem + _FORMATO[tipo] * quantos, bruto)
    return etiquetas, ordem


def _lzw(dados):
    """Descompressão LZW do TIFF (códigos de 9 a 12 bits, mais significativo primeiro)."""
    saida = bytearray()
    tabela = [bytes([i]) for i in range(256)] + [b'', b'']
    largura, acumulado, bits, anterior = 9, 0, 0, None
    for byte in dados:
        acumulado = (acumulado << 8) | byte
        bits += 8
        while bits >= largura:
            bits -= largura
            codigo = (acumulado >> bits) & ((1 << largura) - 1)
            acumulado &= (1 << bits) - 1
            if codigo == 257:  # fim
                return bytes(saida)
            if codigo == 256:  # limpa a tabela
                tabela = tabela[:258]
                largura, anterior = 9, None
                continue
            if anterior is None:
                trecho = tabela[codigo]
            elif codigo < len(tabela):
                trecho = tabela[codigo]
                tabela.append(tabela[anterior] + trecho[:1])
            else:
                trecho = tabela[anterior] + tabela[anterior][:1]
                tabela.append(trecho)
            saida += trecho
            anterior = codigo
            if len(tabela) >= (1 << largura) - 1 and largura < 12:
                largura += 1
    return bytes(saida)


def _zona_do_epsg(epsg):
    """EPSG de UTM → (zona, sul). SIRGAS 2000 (31965–31985) e WGS 84 (326xx, 327xx)."""
    if 31978 <= epsg <= 31985:
        return epsg - 31960, True
    if 31965 <= epsg <= 31976:
        return epsg - 31954, False
    if 32701 <= epsg <= 32760:
        return epsg - 32700, True
    if 32601 <= epsg <= 32660:
        return epsg - 32600, False
    return None


def _referencia(e):
    """(x0, y0, dx, dy) do canto superior esquerdo e o SRC ('geo' | 'utm', zona, sul, epsg)."""
    chaves = e.get(34735, ())
    geo = {chaves[i]: chaves[i + 3] for i in range(4, len(chaves) - 3, 4) if chaves[i + 1] == 0}
    centro = geo.get(1025) == 2  # PixelIsPoint: a amarração é o CENTRO do pixel
    if 33550 in e and 33922 in e:
        dx, dy = float(e[33550][0]), float(e[33550][1])
        i, j, _, x, y = e[33922][:5]
        x0, y0 = x - i * dx, y + j * dy
    elif 34264 in e:
        m = e[34264]
        if abs(m[1]) > 1e-12 or abs(m[4]) > 1e-12:
            raise ValueError('raster rotacionado não é coberto: reprojete para norte no topo')
        dx, dy, x0, y0 = float(m[0]), -float(m[5]), float(m[3]), float(m[7])
    else:
        raise ValueError('o TIFF não tem georreferência (não é GeoTIFF)')
    if centro:
        x0, y0 = x0 - dx / 2, y0 + dy / 2
    if dx <= 0 or dy <= 0:
        raise ValueError('georreferência com pixel de tamanho inválido')
    if geo.get(1024) == 2 or (1024 not in geo and abs(x0) <= 180 and abs(y0) <= 90):
        return (x0, y0, dx, dy), ('geo', None, None, geo.get(2048))
    epsg = geo.get(3072)
    zona = _zona_do_epsg(epsg) if epsg else None
    if zona is None:
        raise ValueError(f'SRC do raster não coberto (EPSG {epsg}): exporte em SIRGAS 2000 / UTM, WGS 84 / UTM ou em '
                         f'graus (EPSG 4326 ou 4674)')
    return (x0, y0, dx, dy), ('utm', zona[0], zona[1], epsg)


def ler_geotiff(caminho, banda=1):
    """Lê uma banda. Devolve dict: dados (float64, nan onde não há dado), x0, y0 (canto superior
    esquerdo), dx, dy, crs ('geo' | 'utm'), zona, sul, epsg, largura, altura, bandas."""
    dados = open(caminho, 'rb').read()
    e, ordem = _etiquetas(dados)
    largura, altura = e[256][0], e[257][0]
    amostras = e.get(277, (1,))[0]
    bits = e.get(258, (8,))
    formato = e.get(339, (1,))[0]
    compressao, preditor = e.get(259, (1,))[0], e.get(317, (1,))[0]
    planar = e.get(284, (1,))[0]
    if not 1 <= banda <= amostras:
        raise ValueError(f'o raster tem {amostras} banda(s); pediram a banda {banda}')
    if len(set(bits)) != 1:
        raise ValueError('bandas com tamanhos diferentes não são cobertas')
    letra = {1: 'u', 2: 'i', 3: 'f'}.get(formato)
    if letra is None or (letra, bits[0]) not in {('u', 8), ('u', 16), ('u', 32), ('i', 8), ('i', 16), ('i', 32),
                                                ('f', 32), ('f', 64)}:
        raise ValueError(f'tipo de pixel não coberto (formato {formato}, {bits[0]} bits)')
    if compressao not in (1, 5, 8, 32946):
        raise ValueError(f'compressão {compressao} não coberta: exporte sem compressão, com Deflate ou com LZW')
    if preditor not in (1, 2, 3) or (preditor == 3 and letra != 'f'):
        raise ValueError(f'preditor {preditor} não coberto')
    if largura * altura > TETO_DE_PIXELS:
        raise ValueError(f'raster grande demais ({largura} × {altura}): recorte pelo perímetro antes')
    nbytes = bits[0] // 8
    tipo = np.dtype(f'{letra}{nbytes}').newbyteorder(ordem)
    por_pixel = amostras if planar == 1 else 1

    def bloco(inicio, tamanho, linhas, colunas):
        bruto = dados[inicio:inicio + tamanho]
        if compressao in (8, 32946):
            bruto = zlib.decompress(bruto)
        elif compressao == 5:
            bruto = _lzw(bruto)
        quantos = linhas * colunas * por_pixel
        if preditor == 3:  # ponto flutuante: bytes em planos (mais significativo primeiro), diferenciados
            plano = np.frombuffer(bruto, dtype=np.uint8, count=quantos * nbytes).reshape(linhas, colunas * por_pixel * nbytes)
            plano = np.cumsum(plano.reshape(linhas, -1, por_pixel), axis=1, dtype=np.uint8).reshape(linhas, -1) \
                if por_pixel > 1 else np.cumsum(plano, axis=1, dtype=np.uint8)
            plano = plano.reshape(linhas, nbytes, colunas * por_pixel)
            juntos = np.ascontiguousarray(np.transpose(plano, (0, 2, 1)))  # [linha, valor, byte], grande primeiro
            matriz = juntos.view(np.dtype(f'>f{nbytes}')).reshape(linhas, colunas, por_pixel)
            return matriz.astype(np.float64)
        if preditor == 2:
            # cada valor guarda a diferença para o vizinho da esquerda, feita sobre os BITS do valor
            # (inteiro sem sinal do mesmo tamanho, com volta no estouro), inclusive em raster de reais
            sem_sinal = np.dtype(f'u{nbytes}')
            cru = np.frombuffer(bruto, dtype=sem_sinal.newbyteorder(ordem), count=quantos)
            somado = np.cumsum(cru.reshape(linhas, colunas, por_pixel), axis=1, dtype=sem_sinal)
            return somado.view(np.dtype(f'{letra}{nbytes}'))
        return np.frombuffer(bruto, dtype=tipo, count=quantos).reshape(linhas, colunas, por_pixel)

    imagem = np.zeros((altura, largura), dtype=np.float64)
    canal = banda - 1 if planar == 1 else 0
    if 324 in e:  # ladrilhos
        lado_x, lado_y = e[322][0], e[323][0]
        por_linha, por_coluna = -(-largura // lado_x), -(-altura // lado_y)
        por_plano = por_linha * por_coluna
        desloc = 0 if planar == 1 else (banda - 1) * por_plano
        for n in range(por_plano):
            y, x = (n // por_linha) * lado_y, (n % por_linha) * lado_x
            parte = bloco(e[324][desloc + n], e[325][desloc + n], lado_y, lado_x)[:, :, canal]
            imagem[y:y + lado_y, x:x + lado_x] = parte[:altura - y, :largura - x]
    else:  # tiras
        por_tira = min(e.get(278, (altura,))[0], altura)
        por_plano = -(-altura // por_tira)
        desloc = 0 if planar == 1 else (banda - 1) * por_plano
        for n in range(por_plano):
            y = n * por_tira
            linhas = min(por_tira, altura - y)
            imagem[y:y + linhas] = bloco(e[273][desloc + n], e[279][desloc + n], linhas, largura)[:, :, canal]
    sem_dado = e.get(42113)
    if sem_dado:
        try:
            valor = float(str(sem_dado).strip().replace(',', '.'))
            if math.isfinite(valor):
                imagem[np.isclose(imagem, valor, rtol=0, atol=abs(valor) * 1e-6 + 1e-9)] = np.nan
        except ValueError:
            pass
    (x0, y0, dx, dy), (crs, zona, sul, epsg) = _referencia(e)
    return {'dados': imagem, 'x0': x0, 'y0': y0, 'dx': dx, 'dy': dy, 'crs': crs, 'zona': zona, 'sul': sul,
            'epsg': epsg, 'largura': largura, 'altura': altura, 'bandas': amostras}


def amostrar(raster, x, y, zona, sul):
    """Valor do raster nos pontos (x, y) dados em UTM (zona, sul): bilinear, e o pixel mais próximo
    onde a interpolação esbarra em pixel sem dado. Fora do raster devolve nan."""
    from scipy.ndimage import map_coordinates

    x, y = np.asarray(x, float), np.asarray(y, float)
    if raster['crs'] == 'geo':
        rx, ry = utm_inversa(x, y, zona, sul)
    elif (raster['zona'], raster['sul']) == (zona, sul):
        rx, ry = x, y
    else:
        lon, lat = utm_inversa(x, y, zona, sul)
        rx, ry = geometria.utm_direta(lon, lat, raster['zona'], raster['sul'])
    coluna = (rx - raster['x0']) / raster['dx'] - 0.5
    linha = (raster['y0'] - ry) / raster['dy'] - 0.5
    dados = raster['dados']
    valores = map_coordinates(dados, [linha, coluna], order=1, mode='nearest', cval=np.nan)
    ruim = ~np.isfinite(valores)
    if ruim.any():
        valores[ruim] = map_coordinates(dados, [linha[ruim], coluna[ruim]], order=0, mode='nearest', cval=np.nan)
    fora = (coluna < -0.5) | (coluna > raster['largura'] - 0.5) | (linha < -0.5) | (linha > raster['altura'] - 0.5)
    valores[fora] = np.nan
    return valores


def escrever_geotiff(caminho, malha, x_oeste, y_norte, pixel, epsg):
    """Grava a malha (linha 0 = norte) como GeoTIFF float32, sem compressão.
    x_oeste/y_norte = canto superior esquerdo; pixel em metros; epsg do SRC projetado."""
    arr = np.asarray(malha, dtype=np.float32)
    ny, nx = arr.shape
    pixels = np.where(np.isfinite(arr), arr, np.float32(_NODATA)).astype('<f4').tobytes()
    n_entradas = 15
    base = 8 + 2 + n_entradas * 12 + 4
    externos = bytearray()

    def externo(conteudo):
        posicao = base + len(externos)
        externos.extend(conteudo)
        return posicao

    off_escala = externo(struct.pack('<3d', pixel, pixel, 0.0))
    off_amarra = externo(struct.pack('<6d', 0, 0, 0, x_oeste, y_norte, 0))
    off_chaves = externo(struct.pack('<16H', 1, 1, 0, 3, 1024, 0, 1, 1, 1025, 0, 1, 1, 3072, 0, 1, epsg))
    texto = f'{_NODATA:g}\x00'.encode('ascii')
    n_texto = len(texto)
    off_nodata = externo(texto + (b'\x00' if len(texto) % 2 else b''))
    off_pixels = base + len(externos)
    curto = lambda v: struct.pack('<HH', v, 0)  # noqa: E731
    longo = lambda v: struct.pack('<I', v)  # noqa: E731
    entradas = [(256, 4, 1, longo(nx)), (257, 4, 1, longo(ny)), (258, 3, 1, curto(32)), (259, 3, 1, curto(1)),
                (262, 3, 1, curto(1)), (273, 4, 1, longo(off_pixels)), (277, 3, 1, curto(1)), (278, 4, 1, longo(ny)),
                (279, 4, 1, longo(len(pixels))), (284, 3, 1, curto(1)), (339, 3, 1, curto(3)),
                (33550, 12, 3, longo(off_escala)), (33922, 12, 6, longo(off_amarra)), (34735, 3, 16, longo(off_chaves)),
                (42113, 2, n_texto, longo(off_nodata))]
    with open(caminho, 'wb') as f:
        f.write(b'II*\x00' + struct.pack('<IH', 8, n_entradas))
        for tag, tipo, quantos, valor in entradas:
            f.write(struct.pack('<HHI', tag, tipo, quantos) + valor)
        f.write(struct.pack('<I', 0) + externos + pixels)


def _lzw_comprimir(dados):
    """Compressão LZW simples, só para o teste embutido do leitor."""
    tabela = {bytes([i]): i for i in range(256)}
    proximo, largura, saida, acumulado, bits = 258, 9, bytearray(), 0, 0

    def poe(codigo):
        nonlocal acumulado, bits
        acumulado = (acumulado << largura) | codigo
        bits += largura
        while bits >= 8:
            bits -= 8
            saida.append((acumulado >> bits) & 0xFF)
        acumulado &= (1 << bits) - 1

    poe(256)
    atual = b''
    for byte in dados:
        candidato = atual + bytes([byte])
        if candidato in tabela:
            atual = candidato
            continue
        poe(tabela[atual])
        tabela[candidato] = proximo
        proximo += 1
        if proximo >= (1 << largura) and largura < 12:  # o leitor anda uma entrada atrás de quem grava
            largura += 1
        if proximo >= 4094:
            poe(256)
            tabela = {bytes([i]): i for i in range(256)}
            proximo, largura = 258, 9
        atual = bytes([byte])
    if atual:
        poe(tabela[atual])
    poe(257)
    if bits:
        saida.append((acumulado << (8 - bits)) & 0xFF)
    return bytes(saida)


if __name__ == '__main__':
    import os
    import tempfile

    assert _zona_do_epsg(31982) == (22, True) and _zona_do_epsg(32722) == (22, True) and _zona_do_epsg(4326) is None
    texto = bytes(np.random.default_rng(0).integers(0, 6, 40000, dtype=np.uint8))
    assert _lzw(_lzw_comprimir(texto)) == texto

    malha = np.arange(12, dtype=float).reshape(3, 4) + 0.5
    malha[0, 3] = np.nan
    with tempfile.TemporaryDirectory() as pasta:
        arq = os.path.join(pasta, 'a.tif')
        escrever_geotiff(arq, malha, x_oeste=640000, y_norte=7541000, pixel=10.0, epsg=31982)
        r = ler_geotiff(arq)
        assert r['crs'] == 'utm' and (r['zona'], r['sul'], r['epsg']) == (22, True, 31982)
        assert (r['x0'], r['y0'], r['dx'], r['dy']) == (640000, 7541000, 10.0, 10.0)
        assert np.isnan(r['dados'][0, 3]) and r['dados'][2, 0] == 8.5 and r['dados'].shape == (3, 4)
        # no centro do pixel (linha 1, coluna 1) = 5,5; a meio caminho do vizinho da direita = 6,0
        v = amostrar(r, [640015, 640020, 640025, 639000, 640035], [7540985, 7540985, 7540995, 7540985, 7540995], 22, True)
        assert abs(v[0] - 5.5) < 1e-9 and abs(v[1] - 6.0) < 1e-9 and abs(v[2] - 2.5) < 1e-9, v
        assert np.isnan(v[3]) and np.isnan(v[4]), v  # fora do raster; e em cima do pixel sem dado

        # o mesmo raster em LZW e em Deflate com ladrilhos e preditor: o leitor tem de devolver igual
        bruto = open(arq, 'rb').read()
        e, _ = _etiquetas(bruto)
        pixels = bruto[e[273][0]:e[273][0] + e[279][0]]
        for nome, compactado, codigo in (('lzw', _lzw_comprimir(pixels), 5), ('deflate', zlib.compress(pixels), 8)):
            novo = bytearray(bruto[:e[273][0]]) + compactado
            pos = 10
            for k in range(15):
                tag = struct.unpack('<H', novo[pos + k * 12:pos + k * 12 + 2])[0]
                if tag == 259:
                    novo[pos + k * 12 + 8:pos + k * 12 + 10] = struct.pack('<H', codigo)
                if tag == 279:
                    novo[pos + k * 12 + 8:pos + k * 12 + 12] = struct.pack('<I', len(compactado))
            outro = os.path.join(pasta, nome + '.tif')
            open(outro, 'wb').write(novo)
            lido = ler_geotiff(outro)['dados']
            assert np.array_equal(np.nan_to_num(lido, nan=-1), np.nan_to_num(r['dados'], nan=-1)), nome
    print('geotiff OK')
