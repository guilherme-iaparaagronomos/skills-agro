"""Escrita de GeoTIFF (float32, single-band) em Python puro.

Sem GDAL/rasterio: o arquivo é montado byte a byte no padrão TIFF 6.0 +
chaves GeoTIFF (ModelPixelScale, ModelTiepoint, GeoKeyDirectory com o EPSG).
QGIS/GDAL leem normalmente. NoData = -9999 via tag GDAL_NODATA.
"""

import struct

import numpy as np

_NODATA = -9999.0


def escrever_geotiff(caminho, malha, x_oeste, y_norte, pixel, epsg):
    """Grava a malha (linha 0 = norte) como GeoTIFF float32 georreferenciado.

    x_oeste/y_norte = canto SUPERIOR-ESQUERDO da grade (borda, não centro);
    pixel em metros; epsg = código do CRS projetado (ex.: 31983).
    """
    arr = np.asarray(malha, dtype=np.float32)
    ny, nx = arr.shape
    pixels = np.where(np.isfinite(arr), arr, np.float32(_NODATA)).astype('<f4').tobytes()

    n_entradas = 15
    base_ext = 8 + 2 + n_entradas * 12 + 4  # cabeçalho + contagem + entradas + próximo-IFD
    externos = bytearray()

    def externo(dados):
        off = base_ext + len(externos)
        externos.extend(dados)
        return off

    off_escala = externo(struct.pack('<3d', pixel, pixel, 0.0))
    off_amarra = externo(struct.pack('<6d', 0, 0, 0, x_oeste, y_norte, 0))
    off_chaves = externo(struct.pack(
        '<16H',
        1, 1, 0, 3,          # versão do diretório de chaves GeoTIFF
        1024, 0, 1, 1,       # GTModelType = projetado
        1025, 0, 1, 1,       # GTRasterType = PixelIsArea
        3072, 0, 1, epsg,    # ProjectedCSType = EPSG
    ))
    texto_nodata = f'{_NODATA:g}\x00'.encode('ascii')
    n_nodata = len(texto_nodata)
    if len(texto_nodata) % 2:
        texto_nodata += b'\x00'
    off_nodata = externo(texto_nodata)
    if len(externos) % 2:
        externos.extend(b'\x00')
    off_pixels = base_ext + len(externos)

    def curto(v):
        return struct.pack('<HH', v, 0)

    def longo(v):
        return struct.pack('<I', v)

    entradas = [  # (tag, tipo, contagem, valor/offset) — ordem crescente de tag
        (256, 4, 1, longo(nx)),            # ImageWidth
        (257, 4, 1, longo(ny)),            # ImageLength
        (258, 3, 1, curto(32)),            # BitsPerSample
        (259, 3, 1, curto(1)),             # sem compressão
        (262, 3, 1, curto(1)),             # BlackIsZero
        (273, 4, 1, longo(off_pixels)),    # StripOffsets (faixa única)
        (277, 3, 1, curto(1)),             # SamplesPerPixel
        (278, 4, 1, longo(ny)),            # RowsPerStrip
        (279, 4, 1, longo(len(pixels))),   # StripByteCounts
        (284, 3, 1, curto(1)),             # PlanarConfiguration
        (339, 3, 1, curto(3)),             # SampleFormat = float
        (33550, 12, 3, longo(off_escala)),   # ModelPixelScale
        (33922, 12, 6, longo(off_amarra)),   # ModelTiepoint
        (34735, 3, 16, longo(off_chaves)),   # GeoKeyDirectory
        (42113, 2, n_nodata, longo(off_nodata)),  # GDAL_NODATA
    ]
    assert len(entradas) == n_entradas

    with open(caminho, 'wb') as f:
        f.write(b'II*\x00' + struct.pack('<I', 8))
        f.write(struct.pack('<H', n_entradas))
        for tag, tipo, contagem, valor in entradas:
            f.write(struct.pack('<HHI', tag, tipo, contagem) + valor)
        f.write(struct.pack('<I', 0))
        f.write(externos)
        f.write(pixels)


def _ler_tags(caminho):
    """Leitor mínimo p/ os testes: devolve {tag: (tipo, contagem, bruto)}."""
    dados = open(caminho, 'rb').read()
    assert dados[:4] == b'II*\x00'
    off = struct.unpack('<I', dados[4:8])[0]
    n = struct.unpack('<H', dados[off:off + 2])[0]
    tags = {}
    for i in range(n):
        p = off + 2 + i * 12
        tag, tipo, contagem = struct.unpack('<HHI', dados[p:p + 8])
        tags[tag] = (tipo, contagem, dados[p + 8:p + 12])
    return tags, dados


if __name__ == '__main__':
    # exemplo embutido: grava 3×2 e relê validando georreferência e pixels
    import os
    import tempfile

    malha = np.array([[1.0, 2.0, np.nan], [4.0, 5.0, 6.0]])
    with tempfile.TemporaryDirectory() as d:
        arq = os.path.join(d, 't.tif')
        escrever_geotiff(arq, malha, x_oeste=700000, y_norte=7466000, pixel=5.0, epsg=31983)
        tags, dados = _ler_tags(arq)
        assert struct.unpack('<I', tags[256][2])[0] == 3   # largura
        assert struct.unpack('<I', tags[257][2])[0] == 2   # altura
        off_esc = struct.unpack('<I', tags[33550][2])[0]
        assert struct.unpack('<3d', dados[off_esc:off_esc + 24])[0] == 5.0
        off_chv = struct.unpack('<I', tags[34735][2])[0]
        chaves = struct.unpack('<16H', dados[off_chv:off_chv + 32])
        assert chaves[-1] == 31983  # EPSG embutido
        off_px = struct.unpack('<I', tags[273][2])[0]
        px = np.frombuffer(dados[off_px:off_px + 24], dtype='<f4')
        assert px[0] == 1.0 and px[2] == _NODATA and px[5] == 6.0
        print('geotiff OK:', px.tolist())
