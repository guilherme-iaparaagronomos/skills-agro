"""Triagem de vários imóveis: junta numa planilha os fatos que a ferramenta
`dossie_pdf` devolveu para cada um, um imóvel por linha.

  conferir o que já foi feito e o que falta da lista:
     python scripts/triagem.py --pasta respostas --lista lista.txt --conferir
  montar a planilha:
     python scripts/triagem.py --pasta respostas --saida saida
  marcar os imóveis por um critério que o USUÁRIO informou:
     python scripts/triagem.py --pasta respostas --criterio "prodes_2020_ha > 0" --criterio "embargos_n > 0"
  demonstração com imóveis inventados:
     python scripts/triagem.py --demo --saida saida-demo

A pasta tem um arquivo .txt por imóvel, com a resposta da ferramenta colada
como veio e, no alto, as linhas IMOVEL: e FICHA:. Como montar: SKILL.md.

A planilha só tem fatos. Não há semáforo, nota nem classificação: a coluna de
critério só existe quando o usuário diz a regra, e leva o nome da regra dele.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import leitura as L  # noqa: E402

CRITERIO = re.compile(r'^\s*([a-z0-9_]+)\s*(>=|<=|>|<|=)\s*(-?\d+(?:[.,]\d+)?)\s*$')
OPERADORES = {'>': lambda a, b: a > b, '>=': lambda a, b: a >= b, '<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
              '=': lambda a, b: a == b}
# as colunas que vão para o quadro da conversa (a planilha leva todas)
RESUMO = ['imovel', 'municipio', 'area_ha', 'nativa_pct', 'aberta_depois_2008_ha', 'aberta_depois_2019_ha', 'prodes_2020_ha',
          'deter_alertas', 'uc_ha', 'ti_ha', 'embargos_n', 'nao_saiu']
ROTULO = dict(L.COLUNAS)
CURTO = {'imovel': 'Imóvel', 'municipio': 'Município', 'area_ha': 'Área (ha)', 'nativa_pct': 'Nativa (%)',
         'aberta_depois_2008_ha': 'Nativa aberta depois de 2008 (ha)', 'aberta_depois_2019_ha': 'Depois de 2019 (ha)',
         'prodes_2020_ha': 'PRODES 2020 em diante (ha)', 'deter_alertas': 'Alertas DETER', 'uc_ha': 'UC (ha)', 'ti_ha': 'TI (ha)',
         'embargos_n': 'Embargos', 'nao_saiu': 'Seções que não saíram'}


class PedidoInvalido(Exception):
    pass


def ler_criterios(textos):
    criterios = []
    for t in textos:
        m = CRITERIO.match(t)
        if not m:
            raise PedidoInvalido(f'critério "{t}": escreva como "coluna operador número", por exemplo "prodes_2020_ha > 0"')
        coluna, op, valor = m.group(1), m.group(2), float(m.group(3).replace(',', '.'))
        if coluna not in L.NUMERICAS:
            raise PedidoInvalido(f'critério "{t}": "{coluna}" não é coluna de número. As que servem: {", ".join(sorted(L.NUMERICAS))}')
        criterios.append({'texto': f'{coluna} {op} {m.group(3)}', 'coluna': coluna, 'op': op, 'valor': valor})
    return criterios


def aplicar(criterio, imovel):
    """'sim', 'não' ou 'sem dado' (a seção não saiu: não dá para dizer que não)."""
    v = imovel[criterio['coluna']]
    if v is None:
        return 'sem dado'
    return 'sim' if OPERADORES[criterio['op']](v, criterio['valor']) else 'não'


def ler_pasta(caminho):
    raiz = Path(caminho)
    if not raiz.is_dir():
        raise PedidoInvalido(f'não achei a pasta {caminho}')
    imoveis, vistos = [], {}
    for arq in sorted(raiz.glob('*.txt')):
        im = L.ler_dossie(arq.read_text(encoding='utf-8-sig'), arq.name)
        im['arquivo'] = arq.name
        chave = im['imovel'].strip().upper()
        if chave in vistos:
            raise PedidoInvalido(f'{arq.name} e {vistos[chave]} são do mesmo imóvel ({im["imovel"]}). Fique com um.')
        vistos[chave] = arq.name
        imoveis.append(im)
    if not imoveis:
        raise PedidoInvalido(f'{caminho}: nenhum arquivo .txt na pasta')
    return imoveis


def ler_lista(caminho):
    """Um imóvel por linha (CAR, ou nome). Linha vazia e linha com # não contam."""
    linhas = [l.strip() for l in Path(caminho).read_text(encoding='utf-8-sig').splitlines()]
    itens = [l.split(';')[0].split('\t')[0].strip() for l in linhas if l and not l.startswith('#')]
    repetidos = sorted({i for i in itens if [x.upper() for x in itens].count(i.upper()) > 1})
    return itens, repetidos


def br(v, casas=1):
    if v is None:
        return ''
    if isinstance(v, str):
        return v
    if float(v).is_integer() and casas <= 1:
        return f'{int(v):,}'.replace(',', '.')
    return f'{v:,.{casas}f}'.replace(',', '§').replace('.', ',').replace('§', '.')


def gravar_csv(caminho, imoveis, criterios):
    with open(caminho, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow([c for c, _ in L.COLUNAS] + [f'criterio_do_usuario: {k["texto"]}' for k in criterios] + ['arquivo_lido'])
        w.writerow([r for _, r in L.COLUNAS] + [f'Critério do usuário: {k["texto"]}' for k in criterios] + ['Arquivo lido'])
        for im in imoveis:
            linha = []
            for c, _ in L.COLUNAS:
                v = im[c]
                linha.append('' if v is None else (v if isinstance(v, str) else format(v, '.10g').replace('.', ',')))
            w.writerow(linha + [aplicar(k, im) for k in criterios] + [im['arquivo']])


def quadro_md(imoveis, criterios, pendentes=None):
    total = sum(im['area_ha'] or 0 for im in imoveis)
    linhas = [f'# Triagem de {len(imoveis)} imóvel(is)', '',
              f'Área somada: {br(total)} ha. Cada linha vem do dossiê do imóvel (a ficha em PDF), na data em que foi gerado.', '']
    cab = [CURTO[c] for c in RESUMO] + [f'Critério do usuário: {k["texto"]}' for k in criterios]
    linhas += ['| ' + ' | '.join(cab) + ' |', '|' + '---|' * len(cab)]
    for im in imoveis:
        celulas = [br(im[c]) if im[c] is not None else ('—' if c != 'nao_saiu' else '') for c in RESUMO]
        linhas.append('| ' + ' | '.join(celulas + [aplicar(k, im) for k in criterios]) + ' |')
    linhas += ['', '— = a seção não veio na resposta da ferramenta: não quer dizer zero.']
    if criterios:
        linhas += ['', 'As colunas de critério aplicam a regra que o usuário informou. "sem dado" = a seção daquele número não '
                       'saiu. Não são parecer nem classificação do imóvel.']
        for k in criterios:
            n = sum(1 for im in imoveis if aplicar(k, im) == 'sim')
            s = sum(1 for im in imoveis if aplicar(k, im) == 'sem dado')
            linhas.append(f'- {k["texto"]}: {n} de {len(imoveis)} imóvel(is)' + (f'; {s} sem dado' if s else '') + '.')
    avisos = [(im['imovel'], a) for im in imoveis for a in im['avisos']]
    if avisos:
        linhas += ['', 'Avisos da leitura:'] + [f'- {i}: {a}.' for i, a in avisos]
    if pendentes:
        linhas += ['', f'Ainda não consultados ({len(pendentes)}): ' + ', '.join(pendentes) + '.']
    linhas += ['', 'A planilha reúne fatos de bases públicas e de satélite. Não é laudo, parecer nem certidão, e não diz que um '
                   'imóvel está regular ou irregular. As fontes de cada número estão na última página da ficha em PDF. Os termos '
                   'de embargo vêm sem nome e sem documento de pessoa.']
    return '\n'.join(linhas) + '\n'


def argumentos(lista=None):
    p = argparse.ArgumentParser(description='Planilha de fatos de vários imóveis, a partir das respostas do dossiê.')
    p.add_argument('--pasta', help='pasta com um .txt por imóvel')
    p.add_argument('--lista', help='arquivo com a lista completa (um CAR ou nome por linha), para saber o que falta')
    p.add_argument('--conferir', action='store_true', help='só mostra o que foi lido e o que falta')
    p.add_argument('--criterio', action='append', default=[], help='regra do usuário, por exemplo "prodes_2020_ha > 0" (pode repetir)')
    p.add_argument('--colunas', action='store_true', help='lista as colunas da planilha e sai')
    p.add_argument('--saida', default='saida-triagem', help='pasta de saída (padrão: saida-triagem)')
    p.add_argument('--demo', action='store_true', help='roda com quatro imóveis inventados')
    return p.parse_args(lista)


def principal(lista=None):
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, 'reconfigure'):
            fluxo.reconfigure(encoding='utf-8')
    a = argumentos(lista)
    if a.colunas:
        for c, r in L.COLUNAS:
            print(f'{c:32s} {r}' + ('   (número: serve em --criterio)' if c in L.NUMERICAS else ''))
        return 0
    try:
        criterios = ler_criterios(a.criterio)
        if a.demo:
            import sintetico
            imoveis = []
            for nome, texto in sintetico.respostas():
                im = L.ler_dossie(texto, nome)
                im['arquivo'] = nome
                imoveis.append(im)
        elif a.pasta:
            imoveis = ler_pasta(a.pasta)
        else:
            print('Informe --pasta com as respostas coladas, ou --demo. Ajuda: --help', file=sys.stderr)
            return 2
        pendentes, repetidos = [], []
        if a.lista:
            itens, repetidos = ler_lista(a.lista)
            feitos = {im['imovel'].strip().upper() for im in imoveis}
            pendentes = [i for i in dict.fromkeys(itens) if i.upper() not in feitos]
    except (L.LeituraInvalida, PedidoInvalido) as e:
        print(f'Não rodei: {e}', file=sys.stderr)
        return 2

    total = sum(im['area_ha'] or 0 for im in imoveis)
    if a.conferir:
        print(f'{len(imoveis)} imóvel(is) lido(s), {br(total)} ha somados:')
        for im in imoveis:
            faltam = '' if not im['nao_saiu'] else f' · NÃO SAIU: {im["nao_saiu"]}'
            print(f'  {im["imovel"]} ({im["arquivo"]}): {br(im["area_ha"])} ha, {im["municipio"] or "município não informado"}; '
                  f'seções lidas: {", ".join(sorted(im["secoes"])) or "nenhuma"}{faltam}')
            for aviso in im['avisos']:
                print(f'    aviso: {aviso}')
        for r in repetidos:
            print(f'  repetido na lista: {r}')
        if a.lista:
            print(f'Faltam {len(pendentes)} da lista' + (': ' + ', '.join(pendentes) if pendentes else '.'))
        return 0

    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    gravar_csv(saida / 'triagem.csv', imoveis, criterios)
    (saida / 'triagem.md').write_text(quadro_md(imoveis, criterios, pendentes), encoding='utf-8')
    print(f'{len(imoveis)} imóvel(is), {br(total)} ha somados. Gravado em {saida}: triagem.csv (todas as colunas) e triagem.md (o quadro).')
    for k in criterios:
        n = sum(1 for im in imoveis if aplicar(k, im) == 'sim')
        print(f'  critério do usuário "{k["texto"]}": {n} de {len(imoveis)}')
    sem = [im['imovel'] for im in imoveis if im['nao_saiu']]
    if sem:
        print(f'  com seção que não saiu: {", ".join(sem)} (a célula fica vazia, não é zero)')
    if pendentes:
        print(f'  faltam {len(pendentes)} da lista: {", ".join(pendentes)}')
    print('A planilha só tem fatos: não é parecer e não classifica imóvel.')
    return 0


def _autoteste():
    import tempfile

    import sintetico
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        (pasta / 'r').mkdir()
        for nome, texto in sintetico.respostas():
            (pasta / 'r' / nome).write_text(texto, encoding='utf-8')
        (pasta / 'lista.txt').write_text('\n'.join([i for i, _ in sintetico.IMOVEIS] + ['# comentário', 'MT-5100000-FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF']),
                                         encoding='utf-8')
        assert principal(['--pasta', str(pasta / 'r'), '--lista', str(pasta / 'lista.txt'), '--saida', str(pasta / 's'),
                          '--criterio', 'prodes_2020_ha > 0', '--criterio', 'ti_ha>0']) == 0
        linhas = list(csv.reader((pasta / 's' / 'triagem.csv').open(encoding='utf-8-sig'), delimiter=';'))
        assert len(linhas) == 2 + 4 and linhas[0][0] == 'imovel' and linhas[0][-3] == 'criterio_do_usuario: prodes_2020_ha > 0'
        por_imovel = {l[0]: l for l in linhas[2:]}
        # o 1º tem PRODES depois de 2019; o 3º não trouxe a seção: "sem dado", nunca "não"
        assert [por_imovel[i][-3] for i, _ in sintetico.IMOVEIS] == ['sim', 'não', 'sem dado', 'não'], [l[-3] for l in linhas[2:]]
        i3 = sintetico.IMOVEIS[2][0]
        coluna = [c for c, _ in L.COLUNAS].index('prodes_2020_ha')
        assert por_imovel[i3][coluna] == '' and 'PRODES' in por_imovel[i3][[c for c, _ in L.COLUNAS].index('nao_saiu')]
        md = (pasta / 's' / 'triagem.md').read_text(encoding='utf-8')
        assert 'Ainda não consultados (1): MT-5100000-' in md and 'não é zero' not in md.split('\n')[0] and '— = a seção não veio' in md
        assert 'regular ou irregular' in md and 'semáforo' not in md.lower()
        assert principal(['--pasta', str(pasta / 'r'), '--criterio', 'municipio > 0']) == 2
        assert principal(['--pasta', str(pasta / 'r'), '--criterio', 'qualquer coisa']) == 2
        (pasta / 'r' / 'copia.txt').write_text(sintetico.respostas()[0][1], encoding='utf-8')
        assert principal(['--pasta', str(pasta / 'r'), '--conferir']) == 2
    assert aplicar({'coluna': 'uc_ha', 'op': '>', 'valor': 0}, {'uc_ha': None}) == 'sem dado'
    print('triagem.py: autoteste ok (planilha de 4 imóveis, critérios do usuário, pendentes da lista, 3 recusas)')


if __name__ == '__main__':
    sys.exit(_autoteste() if len(sys.argv) == 1 else principal())
