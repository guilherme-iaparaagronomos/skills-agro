"""Relatório de visita de campo: monta o PDF e o texto a partir do visita.json
que a IA escreveu com as fotos, as notas e as transcrições do usuário.

  ver a data, a hora e o GPS gravados nas fotos:
     python scripts/montar.py --fotos pasta_das_fotos
  conferir o visita.json (não grava nada):
     python scripts/montar.py --dados visita.json --conferir
  montar o relatório:
     python scripts/montar.py --dados visita.json --saida saida
  baixar a imagem que a ferramenta de satélite devolveu (precisa de internet):
     python scripts/montar.py --baixar "<link do .tif>" --para sat/rgb.tif
  demonstração com uma visita inventada:
     python scripts/montar.py --demo --saida saida-demo

O formato do visita.json está em references/relatorio.md.
"""

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fotos as F  # noqa: E402
import visita as V  # noqa: E402

TETO_DO_DOWNLOAD = 60 * 1024 * 1024


def baixar(link, destino):
    """Baixa o GeoTIFF do link (só https) para `destino`. Devolve o tamanho em bytes; levanta ValueError com o motivo."""
    if not str(link).lower().startswith('https://'):
        raise ValueError('o link tem de começar com https://')
    destino = Path(destino)
    if destino.suffix.lower() not in ('.tif', '.tiff'):
        raise ValueError('o arquivo de destino tem de terminar em .tif')
    pedido = urllib.request.Request(link, headers={'User-Agent': 'relatorio-visita-campo'})
    try:
        with urllib.request.urlopen(pedido, timeout=60) as resposta:          # noqa: S310 (só https, conferido acima)
            if not resposta.geturl().lower().startswith('https://'):
                raise ValueError('o link redirecionou para um endereço que não é https')
            dados = resposta.read(TETO_DO_DOWNLOAD + 1)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f'não consegui baixar ({type(e).__name__}). Sem internet neste ambiente? O link vale 1 hora: peça ao '
                         'usuário para baixar o arquivo e enviar aqui')
    if len(dados) > TETO_DO_DOWNLOAD:
        raise ValueError('arquivo maior que 60 MB: não é a imagem de uma área de visita')
    if dados[:4] not in (b'II*\x00', b'MM\x00*'):
        raise ValueError('o que veio do link não é um GeoTIFF (o link pode ter expirado: ele vale 1 hora)')
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(dados)
    return len(dados)


def argumentos(lista=None):
    p = argparse.ArgumentParser(description='Monta o relatório de visita de campo em PDF.')
    p.add_argument('--dados', help='o visita.json')
    p.add_argument('--conferir', action='store_true', help='só confere o visita.json e mostra o que falta')
    p.add_argument('--saida', default='saida-visita', help='pasta de saída (padrão: saida-visita)')
    p.add_argument('--fotos', help='pasta de fotos: mostra a data, a hora e o GPS de cada uma')
    p.add_argument('--baixar', help='link https do .tif devolvido pela ferramenta de satélite')
    p.add_argument('--para', help='onde gravar o arquivo baixado (termina em .tif)')
    p.add_argument('--demo', action='store_true', help='monta o relatório de uma visita inventada')
    return p.parse_args(lista)


def principal(lista=None):
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, 'reconfigure'):
            fluxo.reconfigure(encoding='utf-8')
    a = argumentos(lista)
    if a.fotos:
        try:
            lidas, erros = F.inventario(a.fotos)
        except F.FotoInvalida as e:
            print(f'Não rodei: {e}', file=sys.stderr)
            return 2
        print(F.texto_do_inventario(lidas, erros))
        return 0
    if a.baixar:
        if not a.para:
            print('Não rodei: diga onde gravar com --para sat/rgb.tif', file=sys.stderr)
            return 2
        try:
            tamanho = baixar(a.baixar, a.para)
        except ValueError as e:
            print(f'Não baixei: {e}', file=sys.stderr)
            return 2
        print(f'Baixado em {a.para} ({tamanho // 1024} KB).')
        return 0
    saida = Path(a.saida)
    if a.demo:
        import sintetico
        a.dados = str(sintetico.gravar(saida / 'visita-inventada'))
        print('DEMONSTRAÇÃO com uma visita INVENTADA (fotos desenhadas e imagem de satélite de mentira).')
    if not a.dados:
        print('Informe --dados visita.json, --fotos pasta ou --demo. Ajuda: --help', file=sys.stderr)
        return 2
    try:
        v = V.carregar(a.dados)
    except V.VisitaInvalida as e:
        print(f'O visita.json tem {len(e.problemas)} problema(s). Corrija ou pergunte ao usuário:', file=sys.stderr)
        for problema in e.problemas:
            print(f'  - {problema}', file=sys.stderr)
        return 2

    contagem = (f'{v["n_fotos"]} foto(s), {v["audios"]} áudio(s), {v["n_notas"]} nota(s), {len(v["paradas"])} parada(s), '
                f'{len(v["grupos"])} assunto(s)')
    print(f'{v["fazenda"]} · {v["cidade"]} / {v["estado"]} · {v["data"]:%d/%m/%Y} · {contagem}')
    faltam = [nome for campo, nome in (('proprietario', 'proprietário'), ('cultura', 'cultura'), ('safra', 'safra'),
                                       ('talhoes', 'talhões visitados'), ('tipo', 'tipo de visita'), ('empresa', 'empresa'))
              if not v[campo]]
    if faltam:
        print('Campos opcionais em branco (pergunte uma vez; se o usuário não tiver, o relatório sai sem eles): ' + ', '.join(faltam))
    for aviso in v['avisos']:
        print(f'aviso: {aviso}')
    if a.conferir:
        print('Conferido. Nada gravado: rode sem --conferir para montar o relatório.')
        return 0

    import mapa as M
    import relatorio as R
    saida.mkdir(parents=True, exist_ok=True)
    try:
        paginas = R.gerar(v, saida / 'relatorio.pdf')
    except M.MapaInvalido as e:
        print(f'Não montei: {e}', file=sys.stderr)
        return 2
    (saida / 'relatorio.md').write_text(V.texto_md(v), encoding='utf-8')
    tamanho = (saida / 'relatorio.pdf').stat().st_size
    print(f'Gravado em {saida}: relatorio.pdf ({paginas} página(s), {max(1, tamanho // 1024)} KB) e relatorio.md (o mesmo conteúdo em texto).')
    print('Abra o PDF e olhe antes de entregar. O conteúdo técnico é de quem fez a visita: a skill só organiza o que foi enviado.')
    return 0


def _autoteste():
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        assert principal(['--demo', '--saida', str(pasta / 's')]) == 0
        assert (pasta / 's' / 'relatorio.pdf').stat().st_size > 50_000 and '## Registros da visita' in (pasta / 's' / 'relatorio.md').read_text(encoding='utf-8')
        dados = pasta / 's' / 'visita-inventada' / 'visita.json'
        assert principal(['--dados', str(dados), '--conferir']) == 0
        assert principal(['--fotos', str(pasta / 's' / 'visita-inventada' / 'fotos')]) == 0
        ruim = json.loads(dados.read_text(encoding='utf-8'))
        ruim['visitante'] = ''
        ruim['grupos'][0]['fotos'].append('fotos/nao-existe.jpg')
        (pasta / 's' / 'visita-inventada' / 'ruim.json').write_text(json.dumps(ruim), encoding='utf-8')
        assert principal(['--dados', str(pasta / 's' / 'visita-inventada' / 'ruim.json')]) == 2
        assert principal([]) == 2 and principal(['--baixar', 'https://exemplo.invalid/x.tif']) == 2
        assert principal(['--fotos', str(pasta / 'nao-existe')]) == 2
        for link, destino, trecho in (('http://exemplo.com/a.tif', 'a.tif', 'https'), ('https://exemplo.com/a.tif', 'a.png', '.tif'),
                                      ('file:///etc/passwd', 'a.tif', 'https')):
            try:
                baixar(link, pasta / destino)
            except ValueError as e:
                assert trecho in str(e), (link, str(e))
            else:
                raise AssertionError(f'devia recusar {link}')
    print('montar.py: autoteste ok (demonstração, conferência, inventário das fotos e 7 recusas)')


if __name__ == '__main__':
    sys.exit(_autoteste() if len(sys.argv) == 1 else principal())
