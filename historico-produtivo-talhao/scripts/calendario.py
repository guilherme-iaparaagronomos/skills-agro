"""Histórico por satélite de cada talhão: lê as respostas das ferramentas coladas
em arquivos de texto, acha os ciclos de vegetação e grava as tabelas, as
figuras e o relatório.

  1. conferir o que foi lido (não grava nada):
     python scripts/calendario.py --pasta respostas --conferir
  2. rodar:
     python scripts/calendario.py --pasta respostas --nome "Fazenda Exemplo" --saida saida
  demonstração com dados inventados:
     python scripts/calendario.py --demo --saida saida-demo

Os arquivos da pasta são .txt (ou .md) com a resposta da `curva_com_chuva` de
cada safra, colada como veio, e, se houver, a linha RESUMO da `clima_historico`
do mesmo período. Como montar: SKILL.md.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ciclos as C  # noqa: E402
import historico as H  # noqa: E402
import leitura as L  # noqa: E402


def argumentos(lista=None):
    p = argparse.ArgumentParser(description='Histórico por satélite de cada talhão (ciclos de vegetação por safra).')
    p.add_argument('--pasta', help='pasta com um arquivo de texto por safra (ou um arquivo só)')
    p.add_argument('--conferir', action='store_true', help='só mostra o que foi lido, para comparar com as respostas')
    p.add_argument('--nome', help='nome da fazenda ou da área, para o título')
    p.add_argument('--saida', default='saida-historico', help='pasta de saída (padrão: saida-historico)')
    p.add_argument('--fracao', type=float, default=C.PADRAO['fracao'],
                   help='fração da subida entre a base e o pico que marca o início e o fim (padrão 0,30)')
    p.add_argument('--amplitude-min', type=float, default=C.PADRAO['amplitude_min'],
                   help='amplitude mínima do índice para contar como ciclo (padrão 0,20)')
    p.add_argument('--distancia-min', type=int, default=C.PADRAO['distancia_min'],
                   help='dias mínimos entre dois picos (padrão 45)')
    p.add_argument('--queda', type=float, default=C.PADRAO['queda'],
                   help='queda isolada que sai da conta (padrão 0,10)')
    p.add_argument('--pico-min', type=float, default=None, help='valor mínimo do pico para contar como ciclo (padrão: sem)')
    p.add_argument('--abaixo-pct', type=float, default=20,
                   help='marca a safra com chuva este tanto por cento ou mais abaixo da média (padrão 20)')
    p.add_argument('--so', action='append', default=[], help='só este talhão (pode repetir)')
    p.add_argument('--sem-pdf', action='store_true', help='não grava o relatório em PDF nem as figuras')
    p.add_argument('--demo', action='store_true', help='roda com quatro safras inventadas')
    return p.parse_args(lista)


def mostrar_leitura(safras):
    print(f'{len(safras)} safra(s) lida(s), índice {safras[0]["indice"]}:')
    for s in safras:
        chuva = '' if not s['chuva'] else f' · chuva {H.mm(s["chuva"]["total_mm"])}'
        normal = '' if not s['normal'] or s['normal']['normal_mm'] is None else \
            f' · média histórica {H.mm(s["normal"]["normal_mm"])} ({s["normal"]["dif_pct"]:+d}%)'
        veranicos = '' if not s['veranicos'] else f' · {s["veranicos"]["n"]} veranico(s)'
        print(f'  {s["rotulo"]} ({s["origem"]}): {s["inicio"]:%d/%m/%Y} a {s["fim"]:%d/%m/%Y}{chuva}{normal}{veranicos}')
        for nome, pontos in s['curvas'].items():
            valores = [v for _, v in pontos]
            print(f'    {nome}: {len(pontos)} imagens, de {pontos[0][0]:%d/%m/%Y} ({H.br(pontos[0][1])}) a '
                  f'{pontos[-1][0]:%d/%m/%Y} ({H.br(pontos[-1][1])}); menor {H.br(min(valores))}, maior {H.br(max(valores))}')
        for a in s['avisos']:
            print(f'    aviso: {a}')
    grupos = H.trechos(safras)
    if len(grupos) > 1:
        print(f'  as janelas formam {len(grupos)} trechos separados: ' +
              '; '.join(f'{g[0]["inicio"]:%d/%m/%Y} a {g[-1]["fim"]:%d/%m/%Y}' for g in grupos))
    mostrar_fontes(L.fontes_de(safras))
    print('Compare a primeira e a última imagem de cada linha com a resposta da ferramenta. Se bater, rode sem --conferir.')


def mostrar_fontes(fontes):
    if fontes:
        print('  fontes dos dados lidas das respostas (vão para o quadro como estão):')
        for f in fontes:
            print(f'    - {f}')
    else:
        print('  ATENÇÃO: as respostas coladas não trazem o bloco "FONTES DOS DADOS" do fim da resposta de cada '
              'ferramenta. Cole o bloco no fim de cada arquivo, como veio, para o quadro citar a fonte de cada dado.')


def principal(lista=None):
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, 'reconfigure'):
            fluxo.reconfigure(encoding='utf-8')
    a = argumentos(lista)
    try:
        if a.demo:
            import sintetico
            safras = L.conferir_conjunto([x for texto in sintetico.respostas() for x in L.ler_texto(texto, 'exemplo inventado')])
            a.nome = a.nome or 'Fazenda Exemplo (dados inventados)'
        elif a.pasta:
            safras = L.ler_pasta(a.pasta)
        else:
            print('Informe --pasta com as respostas coladas, ou --demo. Ajuda: --help', file=sys.stderr)
            return 2
        if a.so:
            faltam = [n for n in a.so if n not in L.talhoes_de(safras)]
            if faltam:
                raise L.LeituraInvalida(f'talhão não encontrado: {", ".join(faltam)}. Os lidos: {", ".join(L.talhoes_de(safras))}')
            for s in safras:
                s['curvas'] = {n: p for n, p in s['curvas'].items() if n in a.so}
            safras = [s for s in safras if s['curvas']]
        if a.conferir:
            mostrar_leitura(safras)
            return 0
        parametros = dict(fracao=a.fracao, amplitude_min=a.amplitude_min, distancia_min=a.distancia_min, queda=a.queda,
                          pico_min=a.pico_min)
        h = H.montar(safras, parametros, a.abaixo_pct)
    except (L.LeituraInvalida, C.ParametroInvalido) as e:
        print(f'Não rodei: {e}', file=sys.stderr)
        return 2

    import saidas as S
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    n_ciclos = S.gravar_ciclos(saida / 'ciclos.csv', h)
    S.gravar_safras(saida / 'safras.csv', h)
    S.gravar_quadro(saida / 'quadro.md', h, a.nome)
    gravados = ['quadro.md', 'ciclos.csv', 'safras.csv']
    if not a.sem_pdf:
        for nome in h['talhoes']:
            arquivo = f'talhao-{S.nome_de_arquivo(nome)}.png'
            S.figura_do_talhao(saida / arquivo, h, nome)
            gravados.append(arquivo)
        S.relatorio(saida / 'historico.pdf', h, a.nome)
        gravados.append('historico.pdf')

    print(f'{len(h["safras"])} safra(s), {len(h["talhoes"])} talhão(ões) ou área(s), {n_ciclos} ciclo(s) encontrado(s).')
    for nome, t in h['talhoes'].items():
        por_safra = ', '.join(f'{r["safra"]}: {r.get("ciclos", 0)}' for r in t['por_safra'])
        print(f'  {nome}: ciclos com pico em cada safra — {por_safra}')
        for aviso in t['avisos']:
            print(f'    {aviso}')
    for aviso in h['avisos']:
        print(f'  aviso: {aviso}')
    mostrar_fontes(h['fontes'])
    print(f'Gravado em {saida}: ' + ', '.join(gravados))
    print('O quadro.md é o texto para colar na conversa. Só descreve: índice de vegetação não é produtividade.')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
