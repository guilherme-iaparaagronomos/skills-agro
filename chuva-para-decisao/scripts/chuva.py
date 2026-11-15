"""Chuva para decisão: o que o registro de chuva de um local mostra, em contagem de anos.

Lê o texto que as ferramentas de clima devolveram (salvo em arquivo pela IA),
confere a transcrição contra os totais da própria ferramenta e só então calcula.
Não acessa a internet nem chama ferramenta nenhuma.

Duas etapas:

  1. Conferir e ver as escolhas que faltam (não calcula nada):
       python scripts/chuva.py --conferir --mensal mensal.txt --janela janela.txt

  2. Calcular, com as escolhas do usuário:
       python scripts/chuva.py --mensal mensal.txt --corte-mes 50,100 --firme-mm 100 \\
           --janela janela.txt --seco-mm 2 --veranico-dias 7,10,15 --corte-decendio 20,40 \\
           --inicio-mm 20 --inicio-dias 3 --falso-dias 10 --falso-janela 30 --saida saida_chuva

  Demonstração com dados inventados:  python scripts/chuva.py --demo

Os números das regras (dia seco, veranico, cortes, regra do início e do fim das
águas) são do usuário: sem eles o bloco correspondente não é calculado.
"""

import argparse
import os
import sys

import janela as J
import leitura as L
import mensal as M
from leitura import Recusa, br, dm

USUAIS = ('Valores de uso comum, para CONFIRMAR com o usuário (não são padrão da skill): dia seco = menos de 1 ou de '
          '2 mm; veranico de 7, 10 e 15 dias; corte do decêndio conforme a cultura e o solo (10, 20, 30 mm); início '
          'das águas = 20 mm em 1 a 3 dias, sem 7 a 10 dias secos nos 30 dias seguintes; fim das águas = primeira '
          'sequência de 15 a 20 dias secos; mês de águas = 100 mm.')


def _ler(caminho):
    if not os.path.isfile(caminho):
        raise Recusa(f'Arquivo não encontrado: {caminho}')
    with open(caminho, encoding='utf-8-sig', errors='replace') as f:
        return f.read()


def _lista(texto, nome, inteiro=False):
    try:
        valores = [L.numero(x, nome) for x in str(texto).replace(';', ',').split(',') if x.strip()]
    except Recusa as e:
        raise Recusa(f'{nome}: {e}') from None
    if not valores or any(v <= 0 for v in valores):
        raise Recusa(f'{nome}: informe um ou mais valores maiores que zero, separados por vírgula.')
    if inteiro:
        if any(v != int(v) for v in valores):
            raise Recusa(f'{nome}: use números inteiros de dias.')
        valores = [int(v) for v in valores]
    return sorted(set(valores))


# ------------------------------------------------------------------ montagem dos blocos
def montar_mensal(texto, inicia=7, cortes=(), firme_mm=None, gdd_de=None, gdd_ate=None, gdd_alvo=None):
    d = L.ler_mensal(texto)
    meses, notas = L.conferir_mensal(d)
    if not 1 <= inicia <= 12:
        raise Recusa('--ano-inicia: informe o mês de 1 a 12.')
    anos = M.anos_agricolas(meses, inicia)
    if len(anos) < 3:
        raise Recusa(f'A tabela tem {len(anos)} ano(s) agrícola(s) inteiro(s) começando em {L.MESES[inicia - 1]}. '
                     'São precisos pelo menos 3; peça um período maior.')
    cal = M.calendario(meses, cortes, d['normal'], inicia)
    gdd = None
    if gdd_de or gdd_ate or gdd_alvo:
        if not (gdd_de and gdd_ate):
            raise Recusa('Graus-dia: informe --gdd-de e --gdd-ate (mês do plantio e mês final, de 1 a 12).')
        if not (1 <= gdd_de <= 12 and 1 <= gdd_ate <= 12):
            raise Recusa('Graus-dia: os meses vão de 1 a 12.')
        if any(m['gdd'] is None for m in meses):
            raise Recusa('Graus-dia pedidos, mas a tabela mensal não traz a coluna dos graus-dia. Copie também o '
                         'valor de "graus-dia" de cada mês.')
        gdd = M.graus_dia(meses, gdd_de, gdd_ate, gdd_alvo)
        if gdd is None:
            raise Recusa('Graus-dia: nenhum ano tem todos os meses do período pedido.')
        if d['base_gdd'] is None:
            notas.append('A base dos graus-dia não foi informada no arquivo: confira a que foi usada na chamada.')
    if len(anos) < 15:
        notas.append(f'São {len(anos)} anos agrícolas: P20 e P80 de tão poucos anos mudam muito com um ano a mais. '
                     'A série da ferramenta começa em 1998; peça o período inteiro.')
    if d['confianca_baixa']:
        notas.append(f'A ferramenta marcou confiança baixa em {len(d["confianca_baixa"])} dos {len(meses)} meses.')
    notas += [f'Aviso da ferramenta na tabela mensal: {a}' for a in d['avisos']]
    aguas = M.aguas(meses, firme_mm, inicia) if firme_mm else None
    return dict(local=d['local'], meses=meses, anos=anos, calendario=cal, totais=M.totais(anos), aguas=aguas, gdd=gdd,
                cortes=list(cortes), inicia=inicia, base_gdd=d['base_gdd'], notas=notas,
                mais_seco=M.mes_mais_seco(cal)['mes'])


def _conjunto(texto, salteados):
    janelas, notas = L.conferir_conjunto(L.ler_janelas(texto), salteados)
    ref = janelas[-1]
    n = len(ref['mm'])
    if n > 180:
        raise Recusa(f'A janela tem {n} dias. Use janela de até 180 dias (de preferência até 92): a partir de 6 meses a '
                     'ferramenta muda a régua dos milímetros diários.')
    anos = [L.rotulo(j) for j in janelas]
    faltam = len(set(range(janelas[0]['inicio'].year, ref['inicio'].year + 1))) != len(janelas)
    avisos = sorted({a for j in janelas for a in j['avisos']})
    notas += [f'Aviso da ferramenta em pelo menos um ano da janela: {a}' for a in avisos[:3]]
    return janelas, notas, anos, faltam


def montar_janela(texto, seco_mm, veranico_dias, cortes, regra_inicio=None, salteados=False):
    janelas, notas, anos, faltam = _conjunto(texto, salteados)
    ref = janelas[-1]
    n = len(ref['mm'])
    if max(veranico_dias) > n:
        raise Recusa(f'--veranico-dias: {max(veranico_dias)} dias não cabem numa janela de {n} dias.')
    inicio = None
    if regra_inicio:
        g = dict(regra_inicio, seco_mm=seco_mm)
        if g['falso_janela'] + g['acum_dias'] >= n:
            raise Recusa(f'A regra do início pede {g["falso_janela"]} dias de conferência depois da chuva, e a janela '
                         f'tem {n} dias: não sobra onde procurar o início. Aumente a janela ou reduza --falso-janela.')
        inicio = J.datas_por_ano(janelas, lambda j: J.inicio_das_aguas(j, **g))
        inicio['regra'] = g
        limite = ref['fim'].toordinal() - g['falso_janela']
        import datetime as dt
        notas.append(f'Com esta janela, o início das águas só fica conferido quando a regra fecha até '
                     f'{dm(dt.date.fromordinal(limite))}.')
    return dict(local=ref['local'], janelas=janelas, n=len(janelas), anos=anos, salteados=faltam,
                inicio_dm=dm(ref['inicio']), fim_dm=dm(ref['fim']), seco_mm=seco_mm, cortes=list(cortes),
                decendios=J.por_decendio(janelas, cortes, seco_mm),
                veranicos=J.veranicos(janelas, seco_mm, veranico_dias), inicio=inicio, notas=notas)


def montar_fim(texto, seco_mm, fim_dias, salteados=False):
    janelas, notas, anos, _ = _conjunto(texto, salteados)
    ref = janelas[-1]
    if fim_dias >= len(ref['mm']):
        raise Recusa(f'--fim-dias: {fim_dias} dias não cabem numa janela de {len(ref["mm"])} dias.')
    datas = J.datas_por_ano(janelas, lambda j: J.fim_das_aguas(j, seco_mm, fim_dias))
    return dict(local=ref['local'], janelas=janelas, anos=anos, inicio_dm=dm(ref['inicio']), fim_dm=dm(ref['fim']),
                datas=datas, regra=dict(seco_mm=seco_mm, fim_dias=fim_dias), notas=notas)


def duracao_das_aguas(r):
    if r.get('janela') and r['janela']['inicio'] and r.get('fim'):
        return J.duracao(r['janela']['inicio'], r['fim']['datas']) or None
    return None


def ler_contexto(texto):
    """As frases da ferramenta `contexto_chuva`, como vieram (sem a instrução final para a IA)."""
    frases = []
    for l in str(texto).replace('\r\n', '\n').split('\n'):
        l = l.strip()
        if l.upper().startswith('COMO RESPONDER'):
            break
        if l:
            frases.append(l[1:].strip() if l[0] in '-•' else l)
    return frases or None


# ------------------------------------------------------------------ etapa 1: conferir
def conferir(a):
    """Lê, confere e mostra o que há e as escolhas que faltam. Não calcula."""
    if a.mensal:
        d = L.ler_mensal(_ler(a.mensal))
        meses, notas = L.conferir_mensal(d)
        anos = M.anos_agricolas(meses, a.ano_inicia)
        cal = M.calendario(meses, (), d['normal'], a.ano_inicia)
        seco = M.mes_mais_seco(cal)
        print(f'TABELA MENSAL: {d["local"] or "local não informado"}')
        print(f'  {len(meses)} meses inteiros, de {meses[0]["ano"]}-{meses[0]["mes"]:02d} a '
              f'{meses[-1]["ano"]}-{meses[-1]["mes"]:02d}; {len(anos)} anos agrícolas inteiros começando em '
              f'{L.MESES[a.ano_inicia - 1]}.')
        for n in notas:
            print('  ' + n)
        print('  Mediana por mês (mm): ' + ' · '.join(f'{l["nome"]} {br(l["mediana"], 0)}' for l in cal))
        print(f'  Mês mais seco pela mediana: {seco["nome"]}. O ano agrícola está começando em '
              f'{L.MESES[a.ano_inicia - 1]} (--ano-inicia); confirme com o usuário se serve para a região.')
        tem_gdd = all(m['gdd'] is not None for m in meses)
        print(f'  Graus-dia na tabela: {"sim" if tem_gdd else "não"}'
              + (f' (base {br(d["base_gdd"], 0)} °C)' if tem_gdd and d['base_gdd'] is not None else '') + '.')
        print('  ESCOLHAS DO USUÁRIO para este bloco: --corte-mes (cortes de chuva do mês, opcional); --firme-mm '
              '(corte da regra mensal das águas; sem ele o mês das águas não é calculado); --gdd-de, --gdd-ate e '
              '--gdd-alvo (se quiser graus-dia).')
        print()
    for caminho, nome in ((a.janela, 'JANELA'), (a.janela_fim, 'JANELA DO FIM DAS ÁGUAS')):
        if not caminho:
            continue
        janelas, notas, anos, _ = _conjunto(_ler(caminho), a.anos_salteados)
        ref = janelas[-1]
        print(f'{nome}: {ref["local"] or "local não informado"}')
        print(f'  {len(janelas)} anos ({anos[0]} a {anos[-1]}), de {dm(ref["inicio"])} a {dm(ref["fim"])} '
              f'({len(ref["mm"])} dias). Contagem de dias, soma, dia da maior chuva e veranico da ferramenta: '
              'conferidos em todos os anos.')
        for j in janelas:
            v = j['veranico']
            print(f'    {L.rotulo(j)}: total {br(j["total"])} mm · {j["dias_chuva"]} dias de chuva · veranico máx da '
                  f'ferramenta {v["dias"] if v else "?"} dias' + (f' · confiança {j["confianca"]}' if j['confianca'] else ''))
        for n in notas:
            print('  ' + n)
        inteiros = [d['nome'] for d in J.decendios(ref) if d['inteiro']]
        print(f'  Decêndios inteiros na janela: {", ".join(inteiros) or "nenhum"}.')
        if nome == 'JANELA':
            print('  ESCOLHAS DO USUÁRIO para este bloco (obrigatórias): --seco-mm (abaixo de quantos mm o dia conta '
                  'como seco), --veranico-dias (tamanhos de veranico a contar) e --corte-decendio (mm no decêndio).')
            print('  Para a data do início das águas (opcional), os quatro juntos: --inicio-mm, --inicio-dias, '
                  '--falso-dias e --falso-janela.')
        else:
            print('  ESCOLHAS DO USUÁRIO para este bloco (obrigatórias): --seco-mm e --fim-dias.')
        print()
    if not (a.mensal or a.janela or a.janela_fim):
        raise Recusa('Informe --mensal, --janela ou --janela-fim para conferir.')
    print(USUAIS)
    print('Nada foi calculado. Mostre isto ao usuário, confirme as escolhas e rode de novo sem --conferir.')


# ------------------------------------------------------------------ etapa 2: calcular
def calcular(a):
    r = dict(local=a.local or '')
    if a.mensal:
        cortes = _lista(a.corte_mes, '--corte-mes') if a.corte_mes else []
        if a.firme_mm is not None and a.firme_mm <= 0:
            raise Recusa('--firme-mm: informe um valor maior que zero.')
        r['mensal'] = montar_mensal(_ler(a.mensal), a.ano_inicia, cortes, a.firme_mm, a.gdd_de, a.gdd_ate, a.gdd_alvo)
    faltam = []
    if a.janela or a.janela_fim:
        if a.seco_mm is None:
            faltam.append('--seco-mm')
        elif a.seco_mm <= 0:
            raise Recusa('--seco-mm: informe um valor maior que zero (o dia com menos que isso conta como seco).')
    if a.janela:
        faltam += [nome for nome, v in (('--veranico-dias', a.veranico_dias), ('--corte-decendio', a.corte_decendio))
                   if not v]
        partes = dict(acum_mm=a.inicio_mm, acum_dias=a.inicio_dias, falso_dias=a.falso_dias, falso_janela=a.falso_janela)
        dadas = [k for k, v in partes.items() if v is not None]
        if dadas and len(dadas) < 4:
            faltam += [n for n, k in (('--inicio-mm', 'acum_mm'), ('--inicio-dias', 'acum_dias'),
                                      ('--falso-dias', 'falso_dias'), ('--falso-janela', 'falso_janela'))
                       if partes[k] is None]
    if a.janela_fim and a.fim_dias is None:
        faltam.append('--fim-dias')
    if faltam:
        raise Recusa('Falta(m) a(s) escolha(s) do usuário: ' + ', '.join(faltam) + '. A skill não escolhe por ele: '
                     'rode com --conferir, mostre as opções e pergunte. ' + USUAIS)
    if a.janela:
        regra = None
        if dadas:
            if min(partes.values()) <= 0:
                raise Recusa('A regra do início das águas pede valores maiores que zero.')
            regra = dict(acum_mm=float(a.inicio_mm), acum_dias=int(a.inicio_dias), falso_dias=int(a.falso_dias),
                         falso_janela=int(a.falso_janela))
        r['janela'] = montar_janela(_ler(a.janela), a.seco_mm, _lista(a.veranico_dias, '--veranico-dias', True),
                                    _lista(a.corte_decendio, '--corte-decendio'), regra, a.anos_salteados)
    if a.janela_fim:
        if a.fim_dias <= 0:
            raise Recusa('--fim-dias: informe um número de dias maior que zero.')
        r['fim'] = montar_fim(_ler(a.janela_fim), a.seco_mm, int(a.fim_dias), a.anos_salteados)
    if not (r.get('mensal') or r.get('janela') or r.get('fim')):
        raise Recusa('Nada para calcular: informe --mensal, --janela ou --janela-fim (ou --demo).')
    locais = {r[k]['local'] for k in ('mensal', 'janela', 'fim') if r.get(k) and r[k]['local']}
    if len(locais) > 1:
        raise Recusa('Os arquivos são de locais diferentes: ' + ' | '.join(sorted(locais)) + '. Use o mesmo local '
                     'em todas as chamadas.')
    r['local'] = r['local'] or (locais.pop() if locais else '')
    r['duracao'] = duracao_das_aguas(r)
    if a.contexto:
        r['contexto'] = ler_contexto(_ler(a.contexto))
    return r


def entregar(r, pasta):
    import relato
    import saidas
    arquivos = saidas.gravar_tudo(pasta, r)
    print(relato.em_texto(r))
    print(f'Arquivos em {os.path.abspath(pasta)}: ' + ', '.join(arquivos))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--conferir', action='store_true', help='só lê, confere e mostra as escolhas que faltam')
    p.add_argument('--demo', action='store_true', help='roda com dados inventados')
    p.add_argument('--mensal', help='arquivo com a tabela mensal (clima_historico, escala mes)')
    p.add_argument('--janela', help='arquivo com a janela dia a dia, um bloco por ano (clima_historico, escala dia)')
    p.add_argument('--janela-fim', help='arquivo com a janela do fim das águas, um bloco por ano')
    p.add_argument('--contexto', help='arquivo com as frases da contexto_chuva, como vieram')
    p.add_argument('--local', help='nome do local para o título')
    p.add_argument('--saida', default='saida_chuva', help='pasta das saídas (padrão: saida_chuva)')
    p.add_argument('--ano-inicia', type=int, default=7, help='mês em que o ano agrícola começa (padrão 7, julho)')
    p.add_argument('--corte-mes', help='cortes de chuva do mês, em mm (ex.: 50,100)')
    p.add_argument('--firme-mm', type=float, help='corte da regra mensal das águas, em mm')
    p.add_argument('--gdd-de', type=int, help='mês do plantio para somar graus-dia')
    p.add_argument('--gdd-ate', type=int, help='mês final dos graus-dia')
    p.add_argument('--gdd-alvo', type=float, help='graus-dia a alcançar a partir do dia 1º do mês do plantio')
    p.add_argument('--seco-mm', type=float, help='dia com menos que isso conta como seco')
    p.add_argument('--veranico-dias', help='tamanhos de veranico a contar, em dias (ex.: 7,10,15)')
    p.add_argument('--corte-decendio', help='cortes de chuva do decêndio, em mm (ex.: 20,40)')
    p.add_argument('--inicio-mm', type=float, help='regra do início: chuva acumulada mínima')
    p.add_argument('--inicio-dias', type=int, help='regra do início: em quantos dias a chuva acumula')
    p.add_argument('--falso-dias', type=int, help='regra do início: dias secos seguidos que anulam o início')
    p.add_argument('--falso-janela', type=int, help='regra do início: quantos dias depois são conferidos')
    p.add_argument('--fim-dias', type=int, help='regra do fim: dias secos seguidos que marcam o fim das águas')
    p.add_argument('--anos-salteados', action='store_true', help='aceita anos faltando no meio da janela')
    a = p.parse_args(argv)
    for saida in (sys.stdout, sys.stderr):      # o console do Windows não é UTF-8 por padrão
        if hasattr(saida, 'reconfigure'):
            saida.reconfigure(encoding='utf-8', errors='replace')
    try:
        if a.demo:
            import sintetico
            print('DEMONSTRAÇÃO COM DADOS INVENTADOS. As regras usadas aqui são um exemplo; no uso real quem as '
                  'informa é o usuário.\n')
            entregar(sintetico.resultado_demo(), a.saida)
        elif a.conferir:
            conferir(a)
        else:
            entregar(calcular(a), a.saida)
    except Recusa as e:
        print(f'RECUSADO: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
