"""Visita INVENTADA para a demonstração e os testes: fotos desenhadas, um
perímetro, uma imagem de satélite de mentira e o visita.json. Nada aqui é de
fazenda de verdade.

Teste embutido: python scripts/sintetico.py
"""

import json
import math
import struct
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

# canto de um talhão inventado (UTM 22S) e as paradas, em graus
X0, Y0, PIXEL, LARGURA, ALTURA = 500_000.0, 7_489_250.0, 10.0, 180, 130
PARADAS = [(1, -22.70752, -50.99510, '09:10', 'Pivô 1'), (2, -22.70930, -50.98890, '10:11', 'Baixada'),
           (3, -22.71345, -50.99200, '11:12', 'Talhão 12')]


def gravar_tif(caminho, bandas, x_oeste, y_norte, pixel, epsg):
    """GeoTIFF sem compressão, real de 32 bits, com 1 ou mais bandas (altura, largura, bandas) e NaN onde não há dado."""
    dados = np.asarray(bandas, dtype='<f4')
    if dados.ndim == 2:
        dados = dados[:, :, None]
    h, w, b = dados.shape
    corpo = dados.tobytes()
    escala = struct.pack('<3d', pixel, pixel, 0.0)
    amarra = struct.pack('<6d', 0.0, 0.0, 0.0, x_oeste, y_norte, 0.0)
    chaves = struct.pack('<16H', 1, 1, 0, 3, 1024, 0, 1, 1, 1025, 0, 1, 1, 3072, 0, 1, epsg)
    bits, formato = struct.pack(f'<{b}H', *([32] * b)), struct.pack(f'<{b}H', *([3] * b))
    n = 13
    fim_ifd = 8 + 2 + n * 12 + 4
    extras, pos = [], fim_ifd

    def fora(conteudo):
        nonlocal pos
        extras.append(conteudo)
        p = pos
        pos += len(conteudo) + (len(conteudo) % 2)
        return p

    p_bits = fora(bits) if b > 2 else None
    p_formato = fora(formato) if b > 2 else None
    p_escala, p_amarra, p_chaves = fora(escala), fora(amarra), fora(chaves)
    p_dados = pos

    def curto(valores):
        return struct.pack(f'<{len(valores)}H', *valores).ljust(4, b'\0')

    entradas = [
        (256, 4, 1, struct.pack('<I', w)), (257, 4, 1, struct.pack('<I', h)),
        (258, 3, b, struct.pack('<I', p_bits) if b > 2 else curto([32] * b)),
        (259, 3, 1, curto([1])), (262, 3, 1, curto([1])), (273, 4, 1, struct.pack('<I', p_dados)),
        (277, 3, 1, curto([b])), (278, 4, 1, struct.pack('<I', h)), (279, 4, 1, struct.pack('<I', len(corpo))),
        (339, 3, b, struct.pack('<I', p_formato) if b > 2 else curto([3] * b)),
        (33550, 12, 3, struct.pack('<I', p_escala)), (33922, 12, 6, struct.pack('<I', p_amarra)),
        (34735, 3, 16, struct.pack('<I', p_chaves)),
    ]
    with open(caminho, 'wb') as f:
        f.write(b'II' + struct.pack('<HI', 42, 8) + struct.pack('<H', n))
        for etiqueta, tipo, quantos, valor in entradas:
            f.write(struct.pack('<HHI', etiqueta, tipo, quantos) + valor)
        f.write(struct.pack('<I', 0))
        for e in extras:
            f.write(e + (b'\0' if len(e) % 2 else b''))
        f.write(corpo)


def _foto_lavoura(cor_chao, linhas=18):
    im = Image.new('RGB', (1600, 1200), (168, 198, 226))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 420, 1600, 1200], fill=cor_chao)
    escura = tuple(max(0, c - 28) for c in cor_chao)
    for i in range(linhas + 1):
        d.line([(800, 420), (int(1600 * i / linhas), 1200)], fill=escura, width=4)
    return im


def _foto_folha():
    im = Image.new('RGB', (1200, 1600), (58, 110, 44))
    d = ImageDraw.Draw(im)
    d.ellipse([150, 250, 1050, 1350], fill=(86, 150, 60))
    d.line([(600, 250), (600, 1350)], fill=(60, 110, 44), width=10)
    for k in range(14):
        x, y = 300 + (k * 137) % 620, 420 + (k * 211) % 760
        d.ellipse([x, y, x + 46, y + 40], fill=(120, 84, 40))
    return im


def gravar(pasta):
    """Grava a visita inventada na pasta e devolve o caminho do visita.json."""
    import fotos as F
    pasta = Path(pasta)
    (pasta / 'fotos').mkdir(parents=True, exist_ok=True)
    (pasta / 'sat').mkdir(exist_ok=True)
    dia = datetime(2025, 11, 17)
    F.gravar_com_exif(_foto_lavoura((96, 140, 62)), pasta / 'fotos' / 'foto-01.jpg', dia.replace(hour=9, minute=14), PARADAS[0][1], PARADAS[0][2])
    F.gravar_com_exif(_foto_lavoura((150, 118, 80)), pasta / 'fotos' / 'foto-02.jpg', dia.replace(hour=9, minute=21), PARADAS[0][1], PARADAS[0][2])
    F.gravar_com_exif(_foto_lavoura((120, 150, 70), 12), pasta / 'fotos' / 'foto-03.jpg', dia.replace(hour=10, minute=15))
    _foto_folha().save(pasta / 'fotos' / 'foto-04.png')
    F.gravar_com_exif(_foto_lavoura((88, 132, 58), 24), pasta / 'fotos' / 'foto-05.jpg', dia.replace(hour=11, minute=20))

    # dois talhões inventados, em graus, e a "imagem de satélite" de mentira (textura suave)
    perimetro = {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'talhao': 'Pivô 1'}, 'geometry': {'type': 'Polygon', 'coordinates': [[
            [-50.99800, -22.70550], [-50.99200, -22.70550], [-50.99200, -22.71050], [-50.99800, -22.71050], [-50.99800, -22.70550]]]}},
        {'type': 'Feature', 'properties': {'talhao': 'Baixada'}, 'geometry': {'type': 'Polygon', 'coordinates': [[
            [-50.99120, -22.70600], [-50.98600, -22.70680], [-50.98650, -22.71250], [-50.99150, -22.71180], [-50.99120, -22.70600]]]}},
    ]}
    (pasta / 'talhoes.geojson').write_text(json.dumps(perimetro), encoding='utf-8')
    yy, xx = np.mgrid[0:ALTURA, 0:LARGURA]
    verde = 0.5 + 0.35 * np.sin(xx / 23.0) * np.cos(yy / 17.0) + 0.1 * np.sin((xx + yy) / 9.0)
    verde = np.clip(verde, 0.05, 0.95)
    rgb = np.dstack([1900 - 1300 * verde, 1500 - 500 * verde + 200 * np.sin(xx / 40.0), 1100 - 700 * verde]).astype('float32')
    borda = (np.hypot(xx - LARGURA / 2, (yy - ALTURA / 2) * 1.3) > LARGURA * 0.62)
    rgb[borda] = np.nan
    gravar_tif(pasta / 'sat' / 'rgb_2025-11-12.tif', rgb, X0, Y0, PIXEL, 32722)
    ndvi = (0.2 + 0.7 * verde).astype('float32')
    ndvi[borda] = np.nan
    gravar_tif(pasta / 'sat' / 'ndvi_2025-11-12.tif', ndvi, X0, Y0, PIXEL, 32722)

    visita = {
        'fazenda': 'Fazenda Exemplo (dados inventados)', 'cidade': 'Cidade Exemplo', 'estado': 'SP', 'data': '2025-11-17',
        'visitante': 'Responsável técnico de exemplo', 'empresa': 'Consultoria de exemplo', 'proprietario': 'Produtor de exemplo',
        'safra': '2025/26', 'cultura': 'Soja', 'talhoes': 'Pivô 1, Baixada e Talhão 12', 'tipo': 'Vistoria geral',
        'resumo': 'Soja em V4 no Pivô 1, com falhas de plantio na cabeceira. Na Baixada, quem visitou relatou solo encharcado em '
                  'cerca de dois hectares, com plantas amareladas. No Talhão 12 foi relatada a presença de percevejo-marrom.',
        'observacoes': ['Quem visitou indicou reavaliar o estande do Pivô 1 em sete dias.',
                        'Quem visitou indicou coletar solo na área encharcada da Baixada.',
                        'A contagem de percevejos do Talhão 12 foi feita em pano de batida, segundo o áudio das 11:18.'],
        'paradas': [{'n': n, 'lat': lat, 'lon': lon, 'hora': hora, 'nome': nome, 'origem': 'foto' if n == 1 else 'usuario'}
                    for n, lat, lon, hora, nome in PARADAS],
        'grupos': [
            {'titulo': 'Pivô 1: estande e falhas', 'parada': 1,
             'texto': 'Soja em V4, com estande uniforme na maior parte da área e falhas pontuais na cabeceira, segundo quem visitou.',
             'notas': [{'hora': '09:25', 'texto': 'Produtor relata chuva de 40 mm na madrugada de sábado.'}],
             'fotos': [{'arquivo': 'fotos/foto-01.jpg', 'descricao': 'Linhas de soja em fase inicial, com o dossel ainda aberto.'},
                       {'arquivo': 'fotos/foto-02.jpg', 'descricao': 'Solo exposto entre as linhas na cabeceira, com falhas de plantio, como citado no áudio.'}]},
            {'titulo': 'Baixada: solo encharcado', 'parada': 2,
             'texto': 'Área de cerca de dois hectares com solo encharcado e plantas amareladas, segundo quem visitou.',
             'fotos': [{'arquivo': 'fotos/foto-03.jpg', 'descricao': 'Lavoura com linhas espaçadas e vegetação de tom mais claro.'},
                       {'arquivo': 'fotos/foto-04.png', 'descricao': 'Folha com manchas marrons arredondadas.', 'hora': '10:22'}]},
            {'titulo': 'Talhão 12: percevejo', 'parada': 3,
             'texto': 'Quem visitou relatou percevejo-marrom acima do nível de controle adotado na fazenda.',
             'notas': [{'hora': '11:18', 'texto': 'Média de 2,4 percevejos por pano de batida em cinco pontos.'}],
             'fotos': [{'arquivo': 'fotos/foto-05.jpg', 'descricao': 'Linhas de soja fechando o dossel.'}]},
        ],
        'transcricoes': [{'hora': '09:16', 'texto': 'Aqui no pivô um a soja está em V4, estande bom, só a cabeceira com umas falhas.'},
                         {'hora': '11:18', 'texto': 'No talhão doze deu média de dois vírgula quatro percevejos por pano em cinco pontos.'}],
        'incluir_transcricoes': True, 'audios': 2, 'perimetro': 'talhoes.geojson',
        'satelite': {'rgb': 'sat/rgb_2025-11-12.tif', 'ndvi': 'sat/ndvi_2025-11-12.tif', 'data': '2025-11-12', 'sem_nuvem_pct': 98,
                     'credito': 'Imagem INVENTADA para o exemplo: não é de satélite.'},
    }
    arq = pasta / 'visita.json'
    arq.write_text(json.dumps(visita, ensure_ascii=False, indent=2), encoding='utf-8')
    return arq


def _autoteste():
    import tempfile

    import geotiff
    with tempfile.TemporaryDirectory() as pasta:
        arq = gravar(pasta)
        v = json.loads(arq.read_text(encoding='utf-8'))
        assert len(v['grupos']) == 3 and len(v['paradas']) == 3
        r = geotiff.ler_geotiff(str(Path(pasta) / 'sat' / 'rgb_2025-11-12.tif'), 2)
        assert (r['largura'], r['altura'], r['bandas'], r['epsg']) == (LARGURA, ALTURA, 3, 32722), r
        assert (r['x0'], r['y0'], r['dx']) == (X0, Y0, PIXEL) and np.isnan(r['dados'][0, 0]) and 900 < r['dados'][65, 90] < 1800
        n = geotiff.ler_geotiff(str(Path(pasta) / 'sat' / 'ndvi_2025-11-12.tif'), 1)
        assert n['bandas'] == 1 and 0.2 <= np.nanmin(n['dados']) and np.nanmax(n['dados']) <= 0.9
        assert sorted(p.name for p in (Path(pasta) / 'fotos').iterdir()) == [f'foto-0{i}.{"png" if i == 4 else "jpg"}' for i in range(1, 6)]
    print('sintetico.py: autoteste ok (5 fotos desenhadas, perímetro, imagem de 3 bandas e NDVI lidos de volta)')


if __name__ == '__main__':
    _autoteste()
