"""Abre as fotos da visita e lê delas, quando existem, a data, a hora e o GPS
gravados pela câmera (EXIF).

Só abre JPEG, PNG e WebP. Foto em HEIC (padrão de alguns celulares) não é
lida: a mensagem pede para exportar em JPEG. A foto entra no relatório
reduzida (lado maior de 1.200 pixels) e já girada para a posição certa.

Teste embutido: python scripts/fotos.py
"""

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

FORMATOS = ('JPEG', 'PNG', 'WEBP')
EXTENSOES = ('.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif')
LADO_MAXIMO = 1200
TETO_DE_PIXELS = 60_000_000
Image.init()                                   # a lista de formatos só vale com todos os leitores registrados
Image.MAX_IMAGE_PIXELS = TETO_DE_PIXELS


class FotoInvalida(Exception):
    """A foto não pôde ser usada. A mensagem diz por quê e o que fazer."""


def _graus(valor, ref):
    try:
        g, m, s = (float(x) for x in valor)
        v = g + m / 60.0 + s / 3600.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if str(ref).strip().upper() in ('S', 'W'):
        v = -v
    return v


def _exif(im):
    """(quando, lat, lon) da foto, cada um None se a câmera não gravou."""
    quando = lat = lon = None
    try:
        exif = im.getexif()
        detalhe = exif.get_ifd(0x8769) or {}
        texto = detalhe.get(0x9003) or detalhe.get(0x9004) or exif.get(0x0132)
        if texto:
            try:
                quando = datetime.strptime(str(texto).strip()[:19], '%Y:%m:%d %H:%M:%S')
            except ValueError:
                quando = None
        gps = exif.get_ifd(0x8825) or {}
        if 2 in gps and 4 in gps:
            lat, lon = _graus(gps[2], gps.get(1, 'N')), _graus(gps[4], gps.get(3, 'E'))
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
                lat = lon = None
    except Exception:                          # EXIF estragado não impede o uso da foto
        pass
    return quando, lat, lon


def ler(caminho, lado=LADO_MAXIMO):
    """Devolve {'imagem', 'largura', 'altura', 'quando', 'lat', 'lon', 'formato', 'arquivo'}; levanta FotoInvalida."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FotoInvalida(f'{caminho.name}: arquivo não encontrado')
    if caminho.suffix.lower() in ('.heic', '.heif'):
        raise FotoInvalida(f'{caminho.name}: foto em HEIC não é lida. Exporte em JPEG (no celular: compartilhar como '
                           '"mais compatível") e envie de novo')
    try:
        with Image.open(caminho, formats=FORMATOS) as im:
            largura, altura = im.size
            quando, lat, lon = _exif(im)
            formato = im.format
            im = ImageOps.exif_transpose(im)
            im.thumbnail((lado, lado), Image.LANCZOS)
            pronta = im.convert('RGB')
    except FotoInvalida:
        raise
    except Image.DecompressionBombError:
        raise FotoInvalida(f'{caminho.name}: imagem grande demais (mais de {TETO_DE_PIXELS // 1_000_000} megapixels)')
    except Exception:
        raise FotoInvalida(f'{caminho.name}: não abre como JPEG, PNG ou WebP. Envie a foto em um desses formatos')
    return {'arquivo': caminho.name, 'imagem': pronta, 'largura': largura, 'altura': altura, 'quando': quando,
            'lat': lat, 'lon': lon, 'formato': formato}


def ler_logo(caminho, lado=900):
    """A logo da empresa de quem fez a visita, pronta para o cabeçalho: sobre fundo branco (a transparência do PNG
    vira branco) e reduzida. Levanta FotoInvalida com o motivo."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FotoInvalida(f'{caminho.name}: arquivo da logo não encontrado')
    if caminho.suffix.lower() in ('.svg', '.pdf', '.ai', '.eps', '.cdr'):
        raise FotoInvalida(f'{caminho.name}: logo em {caminho.suffix[1:].upper()} não é lida. Peça em PNG ou JPEG')
    try:
        with Image.open(caminho, formats=FORMATOS) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((lado, lado), Image.LANCZOS)
            if im.mode in ('RGBA', 'LA', 'P'):
                im = im.convert('RGBA')
                fundo = Image.new('RGBA', im.size, (255, 255, 255, 255))
                im = Image.alpha_composite(fundo, im)
            pronta = im.convert('RGB')
    except Image.DecompressionBombError:
        raise FotoInvalida(f'{caminho.name}: imagem da logo grande demais')
    except Exception:
        raise FotoInvalida(f'{caminho.name}: a logo não abre como PNG, JPEG ou WebP. Peça em um desses formatos')
    if pronta.size[0] < 40 or pronta.size[1] < 16:
        raise FotoInvalida(f'{caminho.name}: logo pequena demais ({pronta.size[0]}×{pronta.size[1]} px) para sair legível')
    return pronta


def inventario(pasta):
    """Lê todas as fotos de uma pasta (em ordem de nome). Devolve (lista de fotos lidas, lista de mensagens de erro)."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise FotoInvalida(f'não achei a pasta {pasta}')
    lidas, erros = [], []
    for arq in sorted(p for p in pasta.iterdir() if p.suffix.lower() in EXTENSOES):
        try:
            f = ler(arq)
            f.pop('imagem')
            lidas.append(f)
        except FotoInvalida as e:
            erros.append(str(e))
    return lidas, erros


def texto_do_inventario(lidas, erros):
    linhas = [f'{len(lidas)} foto(s) lida(s):']
    for f in lidas:
        quando = f'{f["quando"]:%d/%m/%Y %H:%M}' if f['quando'] else 'sem data na foto'
        gps = f'GPS {f["lat"]:.5f}, {f["lon"]:.5f}' if f['lat'] is not None else 'sem GPS na foto'
        linhas.append(f'  {f["arquivo"]}: {f["largura"]}×{f["altura"]} px · {quando} · {gps}')
    com_gps = sum(1 for f in lidas if f['lat'] is not None)
    linhas.append(f'{com_gps} de {len(lidas)} com GPS. Foto enviada por aplicativo de mensagem costuma chegar sem data e sem GPS.')
    linhas += [f'  NÃO LIDA: {e}' for e in erros]
    return '\n'.join(linhas)


# ------------------------------------------------------------------ teste embutido
def gravar_com_exif(im, caminho, quando=None, lat=None, lon=None):
    """Grava um JPEG com a data e o GPS no EXIF (usado pelo exemplo e pelos testes)."""
    exif = Image.Exif()
    if quando:
        exif[0x0132] = quando.strftime('%Y:%m:%d %H:%M:%S')
        exif.get_ifd(0x8769)[0x9003] = quando.strftime('%Y:%m:%d %H:%M:%S')
    if lat is not None and lon is not None:
        def partes(v):
            v = abs(v)
            g = int(v)
            m = int((v - g) * 60)
            s = round(((v - g) * 60 - m) * 60, 3)
            return (float(g), float(m), float(s))
        gps = exif.get_ifd(0x8825)
        gps[1], gps[2] = ('S' if lat < 0 else 'N'), partes(lat)
        gps[3], gps[4] = ('W' if lon < 0 else 'E'), partes(lon)
    im.save(caminho, format='JPEG', quality=85, exif=exif)


def _autoteste():
    import tempfile
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        gravar_com_exif(Image.new('RGB', (3000, 2000), (90, 140, 60)), pasta / 'a.jpg', datetime(2025, 11, 17, 10, 4, 30), -22.68545, -50.9854)
        Image.new('RGB', (800, 1200), (150, 110, 70)).save(pasta / 'b.png')
        (pasta / 'c.jpg').write_bytes(b'isto nao e uma foto')
        (pasta / 'd.heic').write_bytes(b'\x00' * 20)
        f = ler(pasta / 'a.jpg')
        assert f['imagem'].size == (1200, 800) and (f['largura'], f['altura']) == (3000, 2000)
        assert f['quando'] == datetime(2025, 11, 17, 10, 4, 30), f['quando']
        assert abs(f['lat'] + 22.68545) < 1e-5 and abs(f['lon'] + 50.9854) < 1e-5, (f['lat'], f['lon'])
        g = ler(pasta / 'b.png')
        assert g['imagem'].size == (800, 1200) and g['quando'] is None and g['lat'] is None
        for nome, trecho in (('c.jpg', 'não abre'), ('d.heic', 'HEIC'), ('nao-existe.jpg', 'não encontrado')):
            try:
                ler(pasta / nome)
            except FotoInvalida as e:
                assert trecho in str(e), (nome, str(e))
            else:
                raise AssertionError(f'devia recusar {nome}')
        lidas, erros = inventario(pasta)
        assert [x['arquivo'] for x in lidas] == ['a.jpg', 'b.png'] and len(erros) == 2
        t = texto_do_inventario(lidas, erros)
        assert '1 de 2 com GPS' in t and 'NÃO LIDA' in t and '17/11/2025 10:04' in t
        # logo: a transparência vira branco; SVG e imagem minúscula são recusadas
        transparente = Image.new('RGBA', (300, 100), (0, 0, 0, 0))
        transparente.paste((35, 117, 20, 255), (20, 20, 120, 80))
        transparente.save(pasta / 'logo.png')
        logo = ler_logo(pasta / 'logo.png')
        assert logo.mode == 'RGB' and logo.getpixel((5, 5)) == (255, 255, 255) and logo.getpixel((60, 50)) == (35, 117, 20)
        (pasta / 'logo.svg').write_text('<svg/>', encoding='utf-8')
        Image.new('RGB', (20, 10)).save(pasta / 'mini.png')
        for nome, trecho in (('logo.svg', 'SVG'), ('mini.png', 'pequena demais'), ('sem.png', 'não encontrado'), ('c.jpg', 'não abre')):
            try:
                ler_logo(pasta / nome)
            except FotoInvalida as e:
                assert trecho in str(e), (nome, str(e))
            else:
                raise AssertionError(f'devia recusar a logo {nome}')
    print('fotos.py: autoteste ok (data e GPS do EXIF, redução, giro, logo sobre branco, 7 recusas)')


if __name__ == '__main__':
    _autoteste()
