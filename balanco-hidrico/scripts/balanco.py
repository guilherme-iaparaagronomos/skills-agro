"""Balanço hídrico climatológico de Thornthwaite e Mather (1955): o ano normal e o sequencial.

Três etapas, nesta ordem:

  1. DIAGNÓSTICO (não calcula o balanço): confere a transcrição das tabelas, mostra as
     normais, a ETP por método e o que o usuário precisa decidir.
       python scripts/balanco.py --diagnostico --mensal mensal.txt [--diario diario.txt]

  2. ANO NORMAL, por mês, com a CAD e o método de ETP que o usuário escolheu:
       python scripts/balanco.py --normal --mensal mensal.txt --cad 100 --etp thornthwaite \\
           --chuva referencia --nome "Fazenda X" --fonte conector

  3. SEQUENCIAL de uma safra, por decêndio (ou por mês), com o armazenamento inicial informado:
       python scripts/balanco.py --sequencial --diario diario.txt --mensal mensal.txt --cad 100 \\
           --etp thornthwaite --arm-inicial normal --chuva referencia --nome "Fazenda X" --fonte conector

  Exemplo pronto, com dados inventados:  python scripts/balanco.py --demo

As tabelas: o texto da ferramenta de clima colado como veio, o formato compacto
(uma linha por dia ou por mês) ou planilha de estação com cabeçalho (CSV, TXT, XLSX).
O formato e as linhas de controle estão no começo de scripts/entrada.py.
"""

import argparse
import datetime
import json
import math
import sys
from pathlib import Path

import bh
import caso
import entrada
import etp
import saidas
import sintetico
from entrada import MESES
from saidas import num, sinal

ERROS = (entrada.ErroDeEntrada, caso.ErroDeCaso, etp.ErroDeMetodo, bh.ErroDeBalanco)
METODOS = etp.METODOS + ('informada',)


class Recusa(Exception):
    """Pedido incompleto ou que não fecha; a mensagem vai para o usuário como está."""


def argumentos(lista=None):
    p = argparse.ArgumentParser(description='Balanço hídrico de Thornthwaite e Mather (1955): ano normal e sequencial.')
    p.add_argument('--diagnostico', action='store_true', help='confere as tabelas e mostra as opções; não calcula o balanço')
    p.add_argument('--normal', action='store_true', help='balanço do ano normal, por mês')
    p.add_argument('--sequencial', action='store_true', help='balanço sequencial, por decêndio ou por mês')
    p.add_argument('--demo', action='store_true', help='roda um exemplo com dados inventados')
    p.add_argument('--mensal', help='tabela mensal de chuva e temperatura (vários anos)')
    p.add_argument('--diario', help='tabela diária de chuva e temperatura (a safra)')
    p.add_argument('--normais', help='tabela de 12 normais do usuário (mês, chuva, temperatura), no lugar da mensal')
    p.add_argument('--planilha', help='nome da planilha, quando o XLSX tem mais de uma')
    p.add_argument('--latitude', help='latitude em graus decimais (sul é negativo); sai da linha "local:" quando é um ponto')
    p.add_argument('--cad', help='capacidade de água disponível, em mm, INFORMADA PELO USUÁRIO')
    p.add_argument('--etp', help='método de ETP, ESCOLHIDO PELO USUÁRIO: ' + ', '.join(METODOS))
    p.add_argument('--chuva', help='chuva do ano normal, ESCOLHIDA PELO USUÁRIO: referencia (média histórica informada '
                   'pela ferramenta) ou periodo (média dos anos da tabela)')
    p.add_argument('--anos', help='anos da tabela mensal que entram nas médias: 2001-2020 (padrão: todos os completos)')
    p.add_argument('--passo', choices=('decendio', 'mes'), help='passo do sequencial (padrão: decendio com tabela diária)')
    p.add_argument('--arm-inicial', dest='arm_inicial', help='armazenamento no começo do sequencial, INFORMADO PELO '
                   'USUÁRIO: cad (solo cheio), normal (o do ano normal naquela época) ou o valor em mm')
    p.add_argument('--de', help='começo do sequencial: AAAA-MM-DD (ou AAAA-MM na tabela mensal)')
    p.add_argument('--ate', help='fim do sequencial')
    p.add_argument('--sem-dado', dest='sem_dado', choices=('zero',), help='conta como zero os dias sem dado de chuva '
                   '(sem isto, o balanço recusa)')
    p.add_argument('--nome', default='', help='título do relatório (fazenda, município)')
    p.add_argument('--fonte', default='', help='de onde vieram os dados: "conector" ou o nome da estação')
    p.add_argument('--saida', default='saida-balanco')
    return p.parse_args(lista)


# ------------------------------------------------------------------ apoio
def _tabela_txt(cabecalho, linhas, recuo='  '):
    larguras = [max(len(str(c)), *(len(str(l[k])) for l in linhas)) if linhas else len(str(c))
                for k, c in enumerate(cabecalho)]

    def monta(l):
        return recuo + '  '.join(str(c).ljust(w) if k == 0 else str(c).rjust(w) for k, (c, w) in enumerate(zip(l, larguras)))
    return '\n'.join([monta(cabecalho), recuo + '  '.join('-' * w for w in larguras)] + [monta(l) for l in linhas])


def _numero_do_usuario(texto, o_que):
    try:
        v = entrada.numero(texto)
    except entrada.ErroDeEntrada:
        v = float('nan')
    if math.isnan(v):
        raise Recusa(f'{o_que}: "{texto}" não é número.')
    return v


def _anos(texto):
    if not texto:
        return None
    partes = [p for p in str(texto).replace('a', '-').replace(' ', '').split('-') if p]
    if len(partes) not in (1, 2) or not all(p.isdigit() and len(p) == 4 for p in partes):
        raise Recusa('--anos aceita um intervalo de anos, por exemplo 2001-2020.')
    return int(partes[0]), int(partes[-1])


def _limite(texto, mensal):
    if not texto:
        return None
    data, ano_mes = entrada._data(texto), entrada._ano_mes(texto)
    if mensal:
        if ano_mes is None and data is None:
            raise Recusa(f'"{texto}": na tabela mensal o limite é AAAA-MM.')
        return ano_mes or (data.year, data.month)
    if data is None:
        raise Recusa(f'"{texto}": na tabela diária o limite é AAAA-MM-DD.')
    return data


def _ler(caminho, a, esperado):
    tab = entrada.ler(caminho, a.planilha)
    if tab['tipo'] not in esperado:
        nomes = {'diario': 'diária', 'mensal': 'mensal', 'normais': 'de 12 normais'}
        raise Recusa(f'O arquivo {tab["arquivo"]} é uma tabela {nomes[tab["tipo"]]}; neste lugar entra a '
                     + ' ou a '.join(nomes[e] for e in esperado) + '.')
    return tab


def _mostrar_conferencia(tab, titulo):
    ok, ruim, notas = entrada.conferir(tab)
    print(f'{titulo}: {tab["arquivo"]} ({", ".join(tab["formatos"])})')
    print('  Conferência da transcrição:')
    for texto in ok:
        print(f'    fecha: {texto}')
    for texto in ruim:
        print(f'    NÃO FECHA: {texto}')
    for texto in notas:
        print(f'    nota: {texto}')
    for texto in tab['meta']['avisos_da_ferramenta']:
        print(f'    aviso da ferramenta: {texto}')
    return ok, ruim, notas


def _tabelas(a):
    """Lê e confere o que foi enviado. Devolve {'mensal', 'diario', 'normais', 'problemas', 'notas'}."""
    t = {'mensal': None, 'diario': None, 'normais': None, 'problemas': 0, 'notas': []}
    for chave_, caminho, esperado, titulo in (('mensal', a.mensal, ('mensal',), 'TABELA MENSAL'),
                                             ('diario', a.diario, ('diario',), 'TABELA DIÁRIA'),
                                             ('normais', a.normais, ('normais',), 'TABELA DE NORMAIS')):
        if not caminho:
            continue
        tab = _ler(caminho, a, esperado)
        _, ruim, notas = _mostrar_conferencia(tab, titulo)
        print()
        t[chave_] = tab
        t['problemas'] += len(ruim)
        t['notas'] += [f'{titulo.capitalize()}: {n}' for n in notas if 'confiança baixa' in n or 'sem dado' in n]
        if tab['meta']['total'] is None and tab['tipo'] != 'normais' and entrada.chave(a.fonte) == 'conector':
            t['notas'].append(f'{titulo.capitalize()}: a soma da chuva transcrita não foi conferida contra o total da '
                              'ferramenta (faltou a linha "total:").')
        t['notas'] += [f'Aviso da ferramenta ({titulo.lower()}): {x}' for x in tab['meta']['avisos_da_ferramenta']]
    if a.mensal and a.normais:
        raise Recusa('Envie a tabela mensal OU a de 12 normais, não as duas.')
    return t


def _latitude(a, t):
    if a.latitude:
        lat = _numero_do_usuario(a.latitude, '--latitude')
    else:
        achadas = [x['meta']['latitude'] for x in (t['mensal'], t['diario'], t['normais']) if x and x['meta']['latitude'] is not None]
        if not achadas:
            raise Recusa('Falta a latitude (--latitude, em graus decimais, sul negativo): ela entra no fotoperíodo e na '
                         'radiação. Com fazenda salva ou perímetro, use a do centro da área ou a do município.')
        if max(achadas) - min(achadas) > 0.5:
            raise Recusa('As tabelas trazem latitudes diferentes na linha "local:". Elas são do mesmo lugar?')
        lat = achadas[0]
    if lat > 6 and not a.latitude:
        print(f'  (latitude {num(lat, 2)}° lida da linha "local:": positiva é hemisfério norte)')
    return lat


def _das_normais(a, t, chuva):
    origem = t['mensal'] or t['normais']
    return caso.normais(origem, _anos(a.anos), chuva) if origem else None


def _fontes(a, t):
    """As fontes dos dados, para o relatório citar. Com `--fonte conector`, são as linhas que a ferramenta escreveu no
    fim da resposta (o bloco "FONTES DOS DADOS"), como vieram nos arquivos; senão, o que o usuário informou."""
    if not a.fonte:
        return ['fonte não informada']
    if entrada.chave(a.fonte) != 'conector':
        return [a.fonte]
    lidas = []
    for tab in (t['mensal'], t['diario'], t['normais']):
        for f in (tab['meta'].get('fontes', []) if tab else []):
            if f not in lidas:
                lidas.append(f)
    return lidas or [saidas.SEM_FONTE_DA_FERRAMENTA]


def _json(obj):
    if isinstance(obj, dict):
        return {str(k): _json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json(v) for v in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def _escolhas_obrigatorias(a, sequencial=False):
    faltam = []
    if not a.cad:
        faltam.append('--cad (a capacidade de água disponível, em mm)')
    if not a.etp:
        faltam.append('--etp (o método: ' + ', '.join(METODOS) + ')')
    if sequencial and not a.arm_inicial:
        faltam.append('--arm-inicial (cad, normal ou o valor em mm)')
    if faltam:
        raise Recusa('Quem escolhe é o usuário, e a skill não tem padrão para: ' + '; '.join(faltam)
                     + '. Rode o diagnóstico, mostre as opções e pergunte.')
    if a.etp not in METODOS:
        raise Recusa(f'--etp "{a.etp}" não existe. Os métodos: ' + ', '.join(METODOS) + '.')
    cad = _numero_do_usuario(a.cad, '--cad')
    if not 5 <= cad <= 500:
        raise Recusa(f'CAD de {num(cad, 1)} mm: fora da faixa que a skill aceita (5 a 500 mm). Confira a unidade.')
    return cad


# ------------------------------------------------------------------ diagnóstico
def rodar_diagnostico(a, pasta):
    print('BALANÇO HÍDRICO · DIAGNÓSTICO (não calcula o balanço)\n')
    t = _tabelas(a)
    if not (t['mensal'] or t['diario'] or t['normais']):
        raise Recusa('Envie ao menos uma tabela: --mensal, --diario ou --normais.')
    if t['problemas']:
        print('A TRANSCRIÇÃO NÃO FECHA. Corrija as linhas apontadas acima e rode o diagnóstico de novo; sem isso o '
              'balanço não roda.')
        return 2
    lat = _latitude(a, t)
    print(f'LATITUDE USADA: {num(lat, 2)}° (hemisfério {"sul" if lat < 0 else "norte"}). Confira o sinal: sul é negativo.')
    print()
    relato = {'latitude': lat, 'tabelas': {k: t[k]['arquivo'] for k in ('mensal', 'diario', 'normais') if t[k]}}
    origem = t['mensal'] or t['normais']
    n = None
    if origem:
        opcoes = caso.normais(origem, _anos(a.anos), 'periodo')
        referencia = opcoes['chuva_referencia']
        if opcoes['anos']:
            print(f'ANOS COMPLETOS USADOS NAS MÉDIAS: {opcoes["anos"][0]} a {opcoes["anos"][-1]} ({len(opcoes["anos"])} anos).')
        print('NORMAIS DE CADA MÊS (chuva em mm, temperatura em °C):')
        cabecalho = ['mês'] + (['chuva de referência'] if referencia else []) + [
            'chuva do período' if origem['tipo'] == 'mensal' else 'chuva', 'mínima', 'máxima', 'média']
        linhas = []
        for k in range(12):
            linhas.append([MESES[k]] + ([num(referencia[k])] if referencia else []) + [
                num(opcoes['chuva_periodo'][k]), num(opcoes['tmin'][k] if opcoes['tmin'] else None),
                num(opcoes['tmax'][k] if opcoes['tmax'] else None), num(opcoes['tmed'][k] if opcoes['tmed'] else None)])
        linhas.append(['ano'] + ([num(sum(referencia))] if referencia else []) + [num(sum(opcoes['chuva_periodo'])), '', '',
                      num(sum(opcoes['tmed']) / 12) if opcoes['tmed'] else '—'])
        print(_tabela_txt(cabecalho, linhas))
        if referencia:
            print('  chuva de referência = a média histórica (1991–2020) que a ferramenta informa em cada mês;')
            print(f'  chuva do período = {opcoes["origem_temperatura"]}. A temperatura é sempre a do período.')
        metodos = caso.metodos_do_caso(opcoes)
        relato['normais'] = {k: opcoes[k] for k in ('anos', 'chuva_periodo', 'chuva_referencia', 'tmin', 'tmax', 'tmed')}
        relato['metodos'] = metodos
        if not metodos:
            print('\nA tabela não tem temperatura nem ETP: não há como estimar a ETP.')
        else:
            print('\nETP DO ANO NORMAL, POR MÉTODO (mm):')
            por_metodo = {m: [l['etp'] for l in caso.ano_normal(opcoes, m, lat, 100)['linhas']] for m in metodos}
            linhas = [[MESES[k]] + [num(por_metodo[m][k]) for m in metodos] for k in range(12)]
            linhas.append(['ano'] + [num(sum(por_metodo[m])) for m in metodos])
            print(_tabela_txt(['mês'] + list(metodos), linhas))
            relato['etp_por_metodo'] = por_metodo
            if opcoes['tmed']:
                i, exp = etp.indice_de_calor(opcoes['tmed'])
                print(f'  Índice de calor de Thornthwaite: I = {num(i, 2)}; a = {num(exp, 3)}.')
            print('  O que cada método é:')
            for m in metodos:
                print(f'    - {m}: {caso.LIMITES[m]}.')
            pediu_chuva = a.chuva or ('periodo' if not referencia else None)
            if a.etp and pediu_chuva:
                if a.etp not in metodos:
                    raise Recusa(f'--etp "{a.etp}" não roda com esta tabela. Os que rodam: {", ".join(metodos)}.')
                n = caso.normais(origem, _anos(a.anos), pediu_chuva)
                painel = caso.painel_da_cad(n, a.etp, lat)
                print(f'\nO QUE MUDA COM A CAD (ano normal; ETP por {a.etp}; chuva: {n["origem_chuva"]}):')
                print(_tabela_txt(['CAD (mm)', 'ETR (mm)', 'deficiência (mm)', 'excedente (mm)', 'meses com deficiência'],
                                  [[x['cad'], num(x['etr']), num(x['def']), num(x['exc']), x['meses_com_deficiencia']]
                                   for x in painel]))
                print('  É só o efeito da conta. A CAD certa é a do solo e da profundidade de raiz que o usuário informar.')
                relato['painel_da_cad'] = painel
            else:
                print('\n  Para ver o que muda com a CAD, repita o diagnóstico com --etp'
                      + (' e --chuva' if referencia else '') + ' já escolhidos pelo usuário.')
    if t['diario']:
        registros = t['diario']['registros']
        de, ate = _limite(a.de, False), _limite(a.ate, False)
        for passo, nome in (('decendio', 'decêndios'), ('mes', 'meses')):
            try:
                periodos, sobras = entrada.periodos_do_diario(registros, passo, de, ate, 'zero')
            except entrada.ErroDeEntrada as erro:
                print(f'\nSEQUENCIAL POR {nome.upper()}: {erro}')
                continue
            print(f'\nSEQUENCIAL POR {nome.upper()}: {len(periodos)} {nome} completos, de {periodos[0]["inicio"]:%d/%m/%Y} a '
                  f'{periodos[-1]["fim"]:%d/%m/%Y}' + (f'; {sobras} dia(s) das pontas ficam de fora' if sobras else '') + '.')
            sem = sum(p['sem_dado'] for p in periodos)
            if sem:
                print(f'  {sem} dia(s) sem dado de chuva: o balanço só roda se o usuário mandar contá-los como zero '
                      '(--sem-dado zero) ou se a série começar depois deles.')
            metodos = caso.metodos_do_caso(n or (caso.normais(origem, _anos(a.anos), 'periodo') if origem else None), periodos)
            relato.setdefault('sequencial', {})[passo] = {'periodos': len(periodos), 'sobras': sobras, 'metodos': metodos}
            print('  Métodos de ETP que rodam: ' + (', '.join(metodos) or 'nenhum')
                  + ('' if origem else ' (Thornthwaite pede também a tabela mensal ou a de normais, para o índice de calor)') + '.')
            if passo == 'mes' and t['mensal']:
                comparacao = caso.mensal_contra_diaria(t['mensal'], periodos)
                if comparacao:
                    quantos, soma_m, soma_d = comparacao
                    dif = (soma_d / soma_m - 1) * 100 if soma_m else 0.0
                    print(f'  Os mesmos {quantos} meses somam {num(soma_m)} mm na tabela mensal e {num(soma_d)} mm na diária '
                          f'({sinal(dif, 1)}%). As duas séries não precisam fechar: cada balanço usa a sua e diz qual.')
                    relato['mensal_contra_diaria'] = {'meses': quantos, 'mensal': soma_m, 'diaria': soma_d}
    print('\nO QUE O USUÁRIO PRECISA DECIDIR (a skill não escolhe):')
    print('  1. A CAD, em mm (--cad): depende do solo e da profundidade das raízes. Faixas de referência no SKILL.md.')
    print('  2. O método de ETP (--etp), entre os que rodam com os dados.')
    if origem and origem['tipo'] == 'mensal' and origem['meta']['normal']:
        print('  3. A chuva do ano normal (--chuva): referencia ou periodo.')
    if t['diario'] or t['mensal']:
        print('  No sequencial: o armazenamento inicial (--arm-inicial): cad, normal ou o valor em mm.')
    (pasta / 'diagnostico.json').write_text(json.dumps(_json(relato), ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\nArquivo em {pasta}: diagnostico.json')
    return 0


# ------------------------------------------------------------------ balanço
def _imprimir(r):
    normal = r['tipo'] == 'normal'
    cabecalho = ['mês' if normal else 'período', 'T', 'P', 'ETP', 'P−ETP'] + (['neg.ac'] if normal else []) + [
        'ARM', 'ALT', 'ETR', 'DEF', 'EXC']
    linhas = r['linhas']
    if len(linhas) > saidas.PERIODOS_NA_TABELA:
        print(f'  (a série tem {len(linhas)} períodos: abaixo, o resumo por ano; cada período está no CSV)')
        linhas = saidas.resumo_por_ano(r)
    corpo = [saidas._linha_da_tabela(l, normal) for l in linhas] + [saidas._total(r)]
    print(_tabela_txt(cabecalho, corpo))


def _concluir(a, pasta, r, t, prefixo, aviso_do_exemplo=None):
    titulo = a.nome or ('Balanço hídrico normal' if r['tipo'] == 'normal' else 'Balanço hídrico sequencial')
    meta = {'titulo': titulo, 'data': datetime.date.today().strftime('%d/%m/%Y'), 'fontes': _fontes(a, t), 'avisos': t['notas']}
    if aviso_do_exemplo:
        meta['avisos'] = [aviso_do_exemplo] + meta['avisos']
    print(f'{"BALANÇO HÍDRICO DO ANO NORMAL" if r["tipo"] == "normal" else "BALANÇO HÍDRICO SEQUENCIAL"} · {titulo}\n')
    print('ESCOLHAS E ORIGEM DOS NÚMEROS:')
    for frase in saidas.frases_das_escolhas(r):
        print(f'  - {frase}')
    print('\nFONTES DOS DADOS (cite como estão):')
    for fonte in meta['fontes']:
        print(f'  - {fonte}')
    if meta['fontes'] == [saidas.SEM_FONTE_DA_FERRAMENTA]:
        print('  ATENÇÃO: os arquivos não trazem o bloco "FONTES DOS DADOS" do fim da resposta da ferramenta. Cole o '
              'bloco no arquivo (ou uma linha "fonte: ..." para cada fonte) e rode de novo, para o relatório citar a '
              'fonte de cada dado.')
    print('\nTABELA (mm; T em °C):')
    _imprimir(r)
    if r['tipo'] == 'normal':
        print(f'  {r["balanco"]["partida"][0].upper() + r["balanco"]["partida"][1:]}.')
    print('\nAFERIÇÃO:')
    for frase in saidas.frases_da_afericao(r):
        print(f'  - {frase}')
    if r['tipo'] == 'sequencial':
        print(f'\nARMAZENAMENTO INICIAL: {r["dependencia"]}')
    avisos = r['avisos'] + meta['avisos']
    print('\nAVISOS:' if avisos else '\nAVISOS: nenhum.')
    for texto in avisos:
        print(f'  - {texto}')
    saidas.gravar_csv(pasta / f'{prefixo}.csv', r)
    saidas.relatorio(pasta / f'{prefixo}.pdf', pasta / f'{prefixo}.png', r, meta)
    saidas.figura(pasta / f'{prefixo}_graficos.png', r, titulo)
    registro = dict(r, meta=meta)
    registro.pop('normais', None)
    registro['normais'] = {k: v for k, v in (r['normais'] or {}).items() if k != 'etp'} or None
    (pasta / f'{prefixo}.json').write_text(json.dumps(_json(registro), ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\nArquivos em {pasta}: {prefixo}.pdf, {prefixo}.png, {prefixo}_graficos.png, {prefixo}.csv, {prefixo}.json')
    print('O balanço é climatológico: descreve chuva, evapotranspiração e armazenamento para a CAD informada. Não é '
          'recomendação de irrigação, de época de plantio nem de cultura.')
    return 0


def rodar_normal(a, pasta, aviso=None):
    cad = _escolhas_obrigatorias(a)
    t = _tabelas(a)
    if t['problemas']:
        raise Recusa('A transcrição não fecha (veja acima). Corrija a tabela antes de calcular.')
    if not (t['mensal'] or t['normais']):
        raise Recusa('O ano normal pede a tabela mensal (--mensal) ou a de 12 normais (--normais).')
    n = _das_normais(a, t, a.chuva)
    r = caso.ano_normal(n, a.etp, _latitude(a, t) if a.etp != 'informada' else 0.0, cad)
    return _concluir(a, pasta, r, t, 'balanco_normal', aviso)


def rodar_sequencial(a, pasta, aviso=None):
    cad = _escolhas_obrigatorias(a, sequencial=True)
    t = _tabelas(a)
    if t['problemas']:
        raise Recusa('A transcrição não fecha (veja acima). Corrija a tabela antes de calcular.')
    passo = a.passo or ('decendio' if t['diario'] else 'mes')
    if t['diario']:
        periodos, sobras = entrada.periodos_do_diario(t['diario']['registros'], passo, _limite(a.de, False),
                                                      _limite(a.ate, False), a.sem_dado or 'recusar')
        if sobras:
            t['notas'].append(f'{sobras} dia(s) das pontas da tabela ficaram de fora, por não fecharem um período inteiro.')
    elif t['mensal']:
        if passo != 'mes':
            raise Recusa('O sequencial por decêndio pede a tabela diária (--diario). Com a mensal, use --passo mes.')
        periodos = entrada.periodos_do_mensal(t['mensal']['registros'], _limite(a.de, True), _limite(a.ate, True))
    else:
        raise Recusa('O sequencial pede a tabela diária (--diario) ou a mensal (--mensal).')
    usa_normal = entrada.chave(a.arm_inicial) == 'normal'
    n = _das_normais(a, t, a.chuva or (None if usa_normal else 'periodo'))
    r = caso.em_sequencia(periodos, passo, a.etp, _latitude(a, t) if a.etp != 'informada' else 0.0, cad, a.arm_inicial, n)
    r['origem_dos_periodos'] = (f'tabela diária ({t["diario"]["arquivo"]}), somada por ' + ('decêndio' if passo == 'decendio'
                                else 'mês') if t['diario'] else f'tabela mensal ({t["mensal"]["arquivo"]})')
    return _concluir(a, pasta, r, t, 'balanco_sequencial', aviso)


def rodar_demo(a, pasta):
    print('EXEMPLO COM DADOS INVENTADOS — nenhum número aqui veio de estação, de satélite ou de fazenda de verdade.\n')
    (pasta / 'exemplo-inventado-mensal.txt').write_text(sintetico.arquivo_mensal(), encoding='utf-8')
    (pasta / 'exemplo-inventado-diario.txt').write_text(sintetico.arquivo_diario(), encoding='utf-8')
    a.mensal, a.diario = str(pasta / 'exemplo-inventado-mensal.txt'), str(pasta / 'exemplo-inventado-diario.txt')
    a.nome, a.fonte = a.nome or sintetico.NOME, 'exemplo inventado'
    a.etp, a.chuva = a.etp or 'thornthwaite', a.chuva or 'referencia'
    rodar_diagnostico(a, pasta)
    a.cad, a.arm_inicial = a.cad or '100', a.arm_inicial or 'normal'
    aviso = (f'NO EXEMPLO, a CAD de {a.cad} mm, a ETP por {a.etp}, a chuva "{a.chuva}" e o armazenamento inicial '
             f'"{a.arm_inicial}" foram fixados só para mostrar as saídas. Em uso real, quem escolhe é o usuário.')
    print('\n' + '=' * 78 + '\n')
    diario, a.diario = a.diario, None
    rodar_normal(a, pasta, aviso)
    print('\n' + '=' * 78 + '\n')
    a.diario = diario
    return rodar_sequencial(a, pasta, aviso)


def main(lista=None):
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, 'reconfigure'):
            fluxo.reconfigure(encoding='utf-8', errors='replace')
    a = argumentos(lista)
    pasta = Path(a.saida)
    modos = [m for m in ('diagnostico', 'normal', 'sequencial', 'demo') if getattr(a, m)]
    try:
        if len(modos) != 1:
            print('Escolha um modo: --diagnostico, --normal, --sequencial ou --demo. Comece pelo diagnóstico.')
            return 2
        pasta.mkdir(parents=True, exist_ok=True)
        return {'diagnostico': rodar_diagnostico, 'normal': rodar_normal, 'sequencial': rodar_sequencial,
                'demo': rodar_demo}[modos[0]](a, pasta)
    except ERROS + (Recusa,) as erro:
        print(f'NÃO RODOU: {erro}')
        return 2


if __name__ == '__main__':
    sys.exit(main())
