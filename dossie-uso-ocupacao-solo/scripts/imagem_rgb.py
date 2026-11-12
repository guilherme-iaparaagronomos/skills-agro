"""Lê o GeoTIFF de cor real que a imagem_satelite entrega e faz dele uma figura.

O arquivo vem em 16 bits por banda (refletância), que nenhum leitor de imagem
comum mostra direito. Aqui ele é lido em Python puro + numpy e esticado para
8 bits, para entrar no dossiê como PNG.

Cobre o que a ferramenta gera: 3 bandas intercaladas, 8 ou 16 bits, em tiras ou
em ladrilhos, sem compressão ou com Deflate, com ou sem preditor horizontal.
Fora disso levanta ValueError e o dossiê segue sem a imagem.
"""

import struct
import zlib

import numpy as np

_TAMANHO = {1: 1, 2: 1, 3: 2, 4: 4, 16: 8}
_FORMATO = {1: 'B', 3: 'H', 4: 'I', 16: 'Q'}


def _etiquetas(dados):
    if dados[:2] not in (b'II', b'MM') or len(dados) < 8:
        raise ValueError('não é um TIFF')
    ordem = '<' if dados[:2] == b'II' else '>'
    if struct.unpack(ordem + 'H', dados[2:4])[0] != 42:
        raise ValueError('TIFF de formato não coberto (BigTIFF?)')
    pos = struct.unpack(ordem + 'I', dados[4:8])[0]
    n = struct.unpack(ordem + 'H', dados[pos:pos + 2])[0]
    etiquetas = {}
    for i in range(n):
        p = pos + 2 + i * 12
        tag, tipo, quantos = struct.unpack(ordem + 'HHI', dados[p:p + 8])
        if tipo not in _FORMATO:
            continue
        tamanho = _TAMANHO[tipo] * quantos
        if tamanho <= 4:
            bruto = dados[p + 8:p + 8 + tamanho]
        else:
            inicio = struct.unpack(ordem + 'I', dados[p + 8:p + 12])[0]
            bruto = dados[inicio:inicio + tamanho]
        if len(bruto) < tamanho:
            raise ValueError('TIFF truncado')
        etiquetas[tag] = struct.unpack(ordem + _FORMATO[tipo] * quantos, bruto)
    return etiquetas, ordem


def ler_geotiff_rgb(caminho, teto_pixels=40_000_000):
    """Devolve a imagem como matriz [altura, largura, 3] de inteiros (8 ou 16 bits)."""
    dados = open(caminho, 'rb').read()
    e, ordem = _etiquetas(dados)
    largura, altura = e[256][0], e[257][0]
    bits, amostras = e.get(258, (8,)), e.get(277, (1,))[0]
    compressao, preditor = e.get(259, (1,))[0], e.get(317, (1,))[0]
    if amostras < 3 or len(set(bits)) != 1 or bits[0] not in (8, 16):
        raise ValueError(f'esperava 3 bandas de 8 ou 16 bits (veio {amostras} × {bits})')
    if e.get(284, (1,))[0] != 1:
        raise ValueError('bandas em planos separados: formato não coberto')
    if compressao not in (1, 8, 32946):
        raise ValueError(f'compressão {compressao} não coberta (só sem compressão ou Deflate)')
    if preditor not in (1, 2):
        raise ValueError(f'preditor {preditor} não coberto')
    if largura * altura > teto_pixels:
        raise ValueError('imagem grande demais para virar figura')
    tipo = np.dtype(('u1' if bits[0] == 8 else 'u2')).newbyteorder(ordem)

    def bloco(inicio, tamanho, linhas, colunas):
        bruto = dados[inicio:inicio + tamanho]
        if compressao != 1:
            bruto = zlib.decompress(bruto)
        matriz = np.frombuffer(bruto, dtype=tipo, count=linhas * colunas * amostras)
        matriz = matriz.reshape(linhas, colunas, amostras)
        if preditor == 2:  # cada valor guarda a diferença para o vizinho da esquerda
            matriz = np.cumsum(matriz.astype(np.uint64), axis=1).astype(tipo)
        return matriz

    imagem = np.zeros((altura, largura, amostras), dtype=tipo.newbyteorder('='))
    if 324 in e:  # ladrilhos
        lado_x, lado_y = e[322][0], e[323][0]
        por_linha = -(-largura // lado_x)
        for n, (inicio, tamanho) in enumerate(zip(e[324], e[325])):
            y, x = (n // por_linha) * lado_y, (n % por_linha) * lado_x
            parte = bloco(inicio, tamanho, lado_y, lado_x)
            imagem[y:y + lado_y, x:x + lado_x] = parte[:altura - y, :largura - x]
    else:  # tiras
        por_tira = min(e.get(278, (altura,))[0], altura)
        for n, (inicio, tamanho) in enumerate(zip(e[273], e[279])):
            y = n * por_tira
            linhas = min(por_tira, altura - y)
            imagem[y:y + linhas] = bloco(inicio, tamanho, linhas, largura)
    return imagem[:, :, :3]


def para_figura(imagem, baixo=2.0, alto=98.0):
    """Estica a imagem para 8 bits. O mesmo corte vale para as três bandas (preserva
    a cor) e sai dos percentis dos pixels com dado; pixel sem dado (0 nas três
    bandas) fica branco. Devolve [altura, largura, 3] uint8."""
    valores = imagem.astype(np.float64)
    com_dado = valores.sum(axis=2) > 0
    if not com_dado.any():
        raise ValueError('imagem sem nenhum pixel com dado')
    piso, teto = np.percentile(valores[com_dado], [baixo, alto])
    if teto <= piso:
        teto = piso + 1
    esticada = np.clip((valores - piso) / (teto - piso), 0, 1) ** (1 / 1.15)  # leve clareamento
    figura = (esticada * 255).round().astype(np.uint8)
    figura[~com_dado] = 255
    return figura


def geotiff_para_png(caminho_tif, caminho_png):
    """Converte o GeoTIFF de cor real num PNG pronto para o dossiê."""
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.imsave(str(caminho_png), para_figura(ler_geotiff_rgb(caminho_tif)))
    return caminho_png


def _gravar_tiff_de_teste(caminho, imagem, ladrilho=None, deflate=False, preditor=1):
    """TIFF mínimo de 16 bits e 3 bandas, só para os testes embutidos."""
    altura, largura, _ = imagem.shape
    lado = ladrilho or 0
    blocos = []
    if ladrilho:
        for y in range(0, altura, lado):
            for x in range(0, largura, lado):
                parte = np.zeros((lado, lado, 3), dtype='<u2')
                recorte = imagem[y:y + lado, x:x + lado]
                parte[:recorte.shape[0], :recorte.shape[1]] = recorte
                blocos.append(parte)
    else:
        blocos.append(imagem.astype('<u2'))
    brutos = []
    for parte in blocos:
        if preditor == 2:
            parte = np.concatenate([parte[:, :1], np.diff(parte.astype(np.int64), axis=1)], axis=1).astype('<u2')
        dado = parte.tobytes()
        brutos.append(zlib.compress(dado) if deflate else dado)
    campos = [(256, 4, [largura]), (257, 4, [altura]), (258, 3, [16, 16, 16]),
              (259, 3, [32946 if deflate else 1]), (262, 3, [2]), (277, 3, [3]), (284, 3, [1]),
              (317, 3, [preditor])]
    if ladrilho:
        campos += [(322, 4, [lado]), (323, 4, [lado]), (324, 4, None), (325, 4, [len(b) for b in brutos])]
    else:
        campos += [(273, 4, None), (278, 4, [altura]), (279, 4, [len(b) for b in brutos])]
    campos.sort()
    fim_do_diretorio = 8 + 2 + len(campos) * 12 + 4
    extras = bytearray()
    onde = {}
    for tag, tipo, valores in campos:
        quantos = len(brutos) if valores is None else len(valores)
        if _TAMANHO[tipo] * quantos > 4:
            onde[tag] = fim_do_diretorio + len(extras)
            extras += b'\0' * (_TAMANHO[tipo] * quantos)
    inicio_dos_dados = fim_do_diretorio + len(extras)
    posicoes, cursor = [], inicio_dos_dados
    for b in brutos:
        posicoes.append(cursor)
        cursor += len(b)
    saida = bytearray(b'II*\x00' + struct.pack('<I', 8) + struct.pack('<H', len(campos)))
    for tag, tipo, valores in campos:
        valores = posicoes if valores is None else valores
        corpo = struct.pack('<' + _FORMATO[tipo] * len(valores), *valores)
        saida += struct.pack('<HHI', tag, tipo, len(valores))
        if len(corpo) <= 4:
            saida += corpo.ljust(4, b'\0')
        else:
            saida += struct.pack('<I', onde[tag])
            extras[onde[tag] - fim_do_diretorio:onde[tag] - fim_do_diretorio + len(corpo)] = corpo
    saida += struct.pack('<I', 0) + extras + b''.join(brutos)
    open(caminho, 'wb').write(saida)


if __name__ == '__main__':
    import os
    import tempfile

    rng = np.random.default_rng(3)
    original = rng.integers(200, 3000, size=(40, 50, 3)).astype(np.uint16)
    original[:5, :7] = 0  # canto sem dado (fora do perímetro)
    with tempfile.TemporaryDirectory() as pasta:
        arq = os.path.join(pasta, 't.tif')
        for opcoes in ({}, {'deflate': True}, {'ladrilho': 16, 'deflate': True},
                       {'ladrilho': 16}, {'deflate': True, 'preditor': 2}):
            _gravar_tiff_de_teste(arq, original, **opcoes)
            lida = ler_geotiff_rgb(arq)
            assert lida.shape == (40, 50, 3) and (lida == original).all(), opcoes
        figura = para_figura(lida)
        assert figura.dtype == np.uint8 and figura.shape == (40, 50, 3)
        assert (figura[0, 0] == 255).all() and figura[10:, 10:].min() < 40 and figura.max() == 255
        png = geotiff_para_png(arq, os.path.join(pasta, 'f.png'))
        assert os.path.getsize(png) > 500
        open(arq, 'wb').write(b'PK\x03\x04 nao e tiff')
        try:
            ler_geotiff_rgb(arq)
            raise AssertionError('aceitou arquivo que não é TIFF')
        except ValueError:
            pass
    print('imagem_rgb OK: tiras e ladrilhos, com e sem Deflate, preditor, esticamento para 8 bits')
