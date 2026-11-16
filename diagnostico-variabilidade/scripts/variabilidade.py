"""Diagnóstico da variabilidade de um talhão: o que varia junto com a variável
que o usuário quer entender.

Duas etapas, sempre nesta ordem:

  1. DIAGNÓSTICO (não analisa nada): cada camada na grade comum, a cobertura, a
     resolução, o quanto as camadas se repetem.
       python scripts/variabilidade.py --perimetro talhao.geojson \\
           --raster prod=prod.tif --raster argila=argila.tif --pontos ce.csv --diagnostico

  2. ANÁLISE, depois de o usuário dizer a variável a explicar e as camadas:
       python scripts/variabilidade.py --perimetro talhao.geojson \\
           --raster prod=prod.tif --raster argila=argila.tif --pontos ce.csv \\
           --alvo prod --camadas argila,ce_ms_m --nome "Talhão 12"

  Exemplo pronto, com relações plantadas:  python scripts/variabilidade.py --demo
  Sem argumentos, roda o teste embutido.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

import analise as A  # noqa: E402
import camadas as K  # noqa: E402
import relato as T  # noqa: E402


def argumentos(lista=None):
    p = argparse.ArgumentParser(description='O que acompanha a variabilidade de um talhão (correlações, parte de cada camada e manchas).')
    p.add_argument('--perimetro', help='contorno do talhão: GeoJSON, KML, shapefile ou WKT')
    p.add_argument('--raster', action='append', default=[], metavar='NOME=ARQUIVO.tif', help='camada em GeoTIFF (pode repetir)')
    p.add_argument('--pontos', action='append', default=[], metavar='[PREFIXO=]ARQUIVO', help='pontos densos: CSV, TXT, shapefile, zip ou GeoJSON (pode repetir)')
    p.add_argument('--classes', action='append', default=[], metavar='NOME=ARQUIVO[:CAMPO]', help='polígonos com classe: zonas, variedades (pode repetir)')
    p.add_argument('--x', help='coluna do X ou da longitude nos pontos, se o nome não for óbvio')
    p.add_argument('--y', help='coluna do Y ou da latitude nos pontos')
    p.add_argument('--zona', help='zona UTM do perímetro em metros sem .prj (ex.: 22S)')
    p.add_argument('--celula', type=float, help='lado da célula da grade comum, em metros (padrão: automático, a partir de 10 m)')
    p.add_argument('--diagnostico', action='store_true', help='só descreve as camadas; não analisa')
    p.add_argument('--alvo', help='a variável a explicar (escolha do usuário)')
    p.add_argument('--camadas', help='as camadas numéricas que entram, separadas por vírgula (ou "todas")')
    p.add_argument('--com-classes', dest='com_classes', help='as camadas de classes que entram, separadas por vírgula')
    p.add_argument('--faixas', type=int, default=3, help='número de faixas das manchas, de mesma área (2 a 5; padrão 3)')
    p.add_argument('--cortes', help='cortes das faixas informados pelo usuário, separados por ponto e vírgula (ex.: "3,2;4,0")')
    p.add_argument('--sem-filtro', dest='sem_filtro', action='store_true', help='não passa o filtro de maioria nas manchas')
    p.add_argument('--mancha-minima', dest='mancha_minima', type=float, help='área mínima, em ha, para contar como mancha')
    p.add_argument('--nome', help='nome do talhão, para o título')
    p.add_argument('--saida', default='saida-variabilidade', help='pasta de saída (padrão: saida-variabilidade)')
    p.add_argument('--sem-pdf', dest='sem_pdf', action='store_true', help='não grava as figuras nem o PDF')
    p.add_argument('--demo', action='store_true', help='roda o exemplo inventado, com relações plantadas')
    return p.parse_args(lista)


def _lista(texto):
    return [x.strip() for x in str(texto or '').split(',') if x.strip()]


def _cortes(texto):
    if not texto:
        return None
    try:
        return [float(x.strip().replace(',', '.')) for x in str(texto).split(';') if x.strip()]
    except ValueError:
        raise A.EscolhaInvalida(f'--cortes: números separados por ponto e vírgula, por exemplo "3,2;4,0" (recebido: {texto!r})')


def _json(o):
    if isinstance(o, dict):
        return {str(k): _json(v) for k, v in o.items() if k not in ('valida', 'mapa', 'malha', 'rotulos', 'grade', 'areas')}
    if isinstance(o, (list, tuple)):
        return [_json(v) for v in o]
    if isinstance(o, np.ndarray):
        return [_json(v) for v in o.tolist()]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer, np.bool_)):
        return o.item()
    return o


def rodar(a):
    """Devolve o código de saída. Recusas saem com 2 e o motivo na saída de erro."""
    pasta = Path(a.saida)
    escolhas_do_exemplo = None
    if a.demo:
        import sintetico
        exemplo = sintetico.gravar(pasta / 'dados_inventados')
        d = exemplo['pasta']
        a.perimetro = str(d / 'talhao.geojson')
        a.raster = [f'argila={d / "argila_g_kg.tif"}', f'argila_outra={d / "argila_outra_g_kg.tif"}', f'altitude={d / "altitude_m.tif"}',
                    f'ph={d / "ph.tif"}', f'ndvi_mesma_safra={d / "ndvi_mesma_safra.tif"}']
        a.pontos, a.classes = [str(d / 'colheita_limpa.csv')], [f'variedade={d / "variedades.geojson"}:variedade']
        a.nome = a.nome or 'Talhão de exemplo (dados inventados)'
        if not a.diagnostico and not a.alvo:
            a.alvo, a.camadas, a.com_classes = 'prod_t_ha', 'argila,argila_outra,altitude,ph', 'variedade'
            escolhas_do_exemplo = ('No exemplo as escolhas foram fixadas: variável a explicar = prod_t_ha; camadas = argila, argila_outra, '
                                   'altitude, ph; classes = variedade; ndvi_mesma_safra ficou de fora por ser da mesma safra. Com dado seu, '
                                   'quem escolhe é o usuário, depois do diagnóstico.')
    try:
        estado = K.carregar(a.perimetro, a.raster, a.pontos, a.classes, a.celula, a.zona, a.x, a.y)
        diagnostico = K.diagnosticar(estado)
        if a.diagnostico:
            texto = T.texto_do_diagnostico(diagnostico, a.nome)
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / 'diagnostico.md').write_text(texto, encoding='utf-8')
            (pasta / 'diagnostico.json').write_text(json.dumps(_json(diagnostico), ensure_ascii=False, indent=1), encoding='utf-8')
            print(texto)
            print(f'Gravado em {pasta}: diagnostico.md e diagnostico.json. Nada foi analisado.')
            return 0
        if not a.alvo or not (a.camadas or a.com_classes):
            raise A.EscolhaInvalida('informe --alvo e --camadas com o que o usuário escolheu (rode antes com --diagnostico e mostre a ele)')
        escolhidas = _lista(a.camadas)
        if [c.lower() for c in escolhidas] == ['todas']:
            constantes = {l['nome'] for l in diagnostico['camadas'] if l['constante']}
            escolhidas = [n for n in estado['camadas'] if n != a.alvo and n not in constantes]
        r = A.analisar(estado, a.alvo, escolhidas, _lista(a.com_classes), faixas=a.faixas, cortes=_cortes(a.cortes),
                       filtro=not a.sem_filtro, mancha_minima_ha=a.mancha_minima)
    except (K.EntradaInvalida, A.EscolhaInvalida) as erro:
        print(f'Não rodei: {erro}', file=sys.stderr)
        return 2

    import saidas as S
    pasta.mkdir(parents=True, exist_ok=True)
    texto = T.texto_da_analise(r, a.nome)
    (pasta / 'relato.md').write_text(texto, encoding='utf-8')
    S.gravar_correlacoes(pasta / 'correlacoes.csv', r)
    S.gravar_importancia(pasta / 'importancia.csv', r)
    S.gravar_manchas(pasta / 'manchas.csv', r)
    S.gravar_celulas(pasta / 'celulas.csv', estado, r)
    S.gravar_geotiff_das_manchas(pasta / 'manchas.tif', estado, r)
    gravados = ['relato.md', 'importancia.csv', 'correlacoes.csv', 'manchas.csv', 'celulas.csv', 'manchas.tif']
    if not a.sem_pdf:
        gravados += S.figuras(pasta, estado, r)
        S.relatorio(pasta / 'relatorio.pdf', estado, r, a.nome)
        gravados.append('relatorio.pdf')
    resumo = {'gerado_em': datetime.date.today().isoformat(), 'nome': a.nome,
              'escolhas': {'alvo': r['alvo'], 'camadas': r['camadas'], 'classes': r['classes'], 'celula_m': r['celula_m'],
                           'celula_automatica': estado['celula_automatica'], 'cortes': r['manchas']['cortes'],
                           'cortes_por_quantil': r['manchas']['por_quantil'], 'filtro_de_maioria': r['manchas']['filtro']},
              'diagnostico': diagnostico, 'analise': r}
    (pasta / 'analise.json').write_text(json.dumps(_json(resumo), ensure_ascii=False, indent=1), encoding='utf-8')
    gravados.append('analise.json')
    print(texto)
    if escolhas_do_exemplo:
        print(escolhas_do_exemplo)
    print(f'Gravado em {pasta}: ' + ', '.join(gravados))
    return 0


def _autoteste():
    import contextlib
    import io
    import tempfile

    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            assert rodar(argumentos(['--demo', '--diagnostico', '--saida', str(pasta / 'd')])) == 0
            assert rodar(argumentos(['--demo', '--saida', str(pasta / 'a')])) == 0
            dados = pasta / 'a' / 'dados_inventados'
            base = ['--perimetro', str(dados / 'talhao.geojson'), '--raster', f'argila={dados / "argila_g_kg.tif"}',
                    '--raster', f'altitude={dados / "altitude_m.tif"}', '--pontos', str(dados / 'colheita_limpa.csv')]
            assert rodar(argumentos(base + ['--saida', str(pasta / 'x')])) == 2                       # sem escolha: recusa
            assert rodar(argumentos(base + ['--alvo', 'prod_t_ha', '--camadas', 'todas', '--cortes', '3,3;4,1', '--sem-pdf',
                                            '--saida', str(pasta / 'b')])) == 0
            assert rodar(argumentos(base + ['--alvo', 'prod_t_ha', '--camadas', 'argila', '--cortes', 'abc', '--saida', str(pasta / 'x')])) == 2
        texto = saida.getvalue()
        assert 'Nada foi analisado.' in texto and '# Diagnóstico das camadas — Talhão de exemplo (dados inventados)' in texto
        assert 'ndvi_mesma_safra' in texto and 'argila e argila_outra (r = +0,99, quase iguais)' in texto
        assert 'rode antes com --diagnostico' in erro.getvalue() and '--cortes' in erro.getvalue()
        relato = (pasta / 'a' / 'relato.md').read_text(encoding='utf-8')
        assert relato.startswith('# O que acompanha a variabilidade de prod_t_ha — Talhão de exemplo')
        for trecho in ('## Leitura', '## Camada por camada', '## As manchas', '## Avisos', '## Como ler', 'Variar junto não é causa',
                       'dizem quase a mesma coisa', 'não se distingue de zero', '### prod_t_ha em cada classe de variedade'):
            assert trecho in relato, trecho
        # só descreve: nenhuma palavra de causa (fora da frase que nega) nem de recomendação
        sem_as_negativas = relato.replace('Variar junto não é causa', '')
        for palavra in ('causa', 'explica ', 'explicam', 'recomend', 'corrija', 'aplique', 'deve '):
            assert palavra not in sem_as_negativas.lower(), palavra
        analise = json.loads((pasta / 'a' / 'analise.json').read_text(encoding='utf-8'))
        assert analise['escolhas']['alvo'] == 'prod_t_ha' and 0.6 < analise['analise']['r2_do_conjunto'] < 0.9
        esperados = {'relato.md', 'importancia.csv', 'correlacoes.csv', 'manchas.csv', 'celulas.csv', 'manchas.tif', 'importancia.png',
                     'correlacoes.png', 'manchas.png', 'relatorio.pdf', 'analise.json'}
        assert esperados <= {p.name for p in (pasta / 'a').iterdir()}, sorted(p.name for p in (pasta / 'a').iterdir())
        assert not (pasta / 'b' / 'relatorio.pdf').exists() and (pasta / 'b' / 'relato.md').exists()
        assert 'cortes em 3,30, 4,10' in (pasta / 'b' / 'relato.md').read_text(encoding='utf-8')
    print('variabilidade OK (diagnóstico, exemplo completo, escolha "todas" com cortes informados, 2 recusas). Para usar: --help')


def principal():
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, 'reconfigure'):
            fluxo.reconfigure(encoding='utf-8')
    if len(sys.argv) == 1:
        _autoteste()
        return 0
    return rodar(argumentos())


if __name__ == '__main__':
    sys.exit(principal())
