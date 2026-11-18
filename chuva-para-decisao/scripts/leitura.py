"""Leitura do texto das ferramentas de clima e conferência da transcrição.

Dois tipos de arquivo, os dois em texto simples:

1. Tabela mensal (uma chamada longa da `clima_historico`, escala `mes`). Cada
   mês em uma linha, como a ferramenta devolveu
       1998-10: 180,4 mm (média 148,2 mm → +22%) · temp média 20.2–29.4°C · graus-dia 458.7
   ou resumido em `1998-10 180,4 458.7` (mês, chuva e, se quiser, graus-dia).
   No alto, as linhas RESUMO e TEMPERATURA da ferramenta, ou `total:`,
   `gdd_total:`, `base_gdd:` e `normal:` (12 valores, de janeiro a dezembro).

2. Janela dia a dia (uma chamada da `clima_historico`, escala `dia`, por ano).
   De cada resposta: as linhas `Chuva — ...`, `RESUMO` e `AGRO` como vieram e
   os milímetros de cada dia, na ordem, em linhas `mm:` (ou as próprias linhas
   `AAAA-MM-DD: chuva X mm` da ferramenta).

Nada é calculado antes de a transcrição fechar com o que a ferramenta informou:
número de dias, total do período, dia da maior chuva e o veranico máximo.

Teste embutido: python scripts/leitura.py
"""

import datetime as dt
import math
import re


class Recusa(Exception):
    """Entrada que não dá para usar. A mensagem diz o motivo e o que fazer."""


MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
SEM_DADO = ('sd', 'sem', 'x', '-', '—', 'nd', 'sem_dado')


# ------------------------------------------------------------------ números e datas
def numero(texto, onde='número'):
    """Número como a ferramenta escreve (1.234,5 ou 384.9). Recusa o que é ambíguo."""
    t = str(texto).strip().replace('−', '-')
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'-?\d{1,3}(\.\d{3})+', t):
        raise Recusa(f'{onde}: "{texto}" é ambíguo (pode ser milhar ou decimal). Escreva com vírgula decimal, '
                     'como a ferramenta devolve.')
    try:
        v = float(t)
    except ValueError:
        raise Recusa(f'{onde}: não entendi "{texto}" como número.') from None
    if not math.isfinite(v):
        raise Recusa(f'{onde}: "{texto}" não é um número válido.')
    return v


def data(texto, onde='data'):
    t = str(texto).strip().rstrip(':,.;)')
    m = re.fullmatch(r'(\d{2})/(\d{2})/(\d{4})', t)
    try:
        if m:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', t)
        if m:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        pass
    raise Recusa(f'{onde}: "{texto}" não é uma data (use dd/mm/aaaa).')


def br(v, casas=1):
    """Número para mostrar: vírgula decimal e ponto de milhar."""
    if v is None:
        return '—'
    s = f'{v:,.{casas}f}'
    return s.replace(',', '§').replace('.', ',').replace('§', '.')


def dm(d):
    return '—' if d is None else f'{d.day:02d}/{d.month:02d}'


def dma(d):
    return '—' if d is None else f'{d.day:02d}/{d.month:02d}/{d.year}'


def tolerancia(n):
    """Folga da soma: cada valor vem arredondado a 0,1 mm."""
    return 1.0 + 0.12 * math.sqrt(max(n, 1))


def _linhas(texto):
    return [l.strip() for l in str(texto).replace('\r\n', '\n').split('\n')]


RE_BLOCO_DE_FONTES = re.compile(r'^FONTES DOS DADOS\b')       # o bloco com que a ferramenta fecha a resposta
RE_FONTE_SOLTA = re.compile(r'^Fontes?:\s*(.+)$', re.I)       # a linha "Fonte: ..." avulsa
RE_ANO_DA_FONTE = re.compile(r'\((\d{4})\)')
RE_INSTRUCAO = re.compile(r'\s+(?:NÃO|NUNCA|SEMPRE)\b')


def fontes_do_texto(texto):
    """As linhas de fonte que a ferramenta escreveu no texto (o bloco "FONTES DOS DADOS" do fim de cada resposta, ou
    uma linha "Fonte: ..."), inteiras e sem repetir. Linhas que só mudam no ano entre parênteses viram uma só."""
    achadas, em_bloco = [], False
    for l in _linhas(texto):
        if RE_BLOCO_DE_FONTES.match(l):
            em_bloco = True
            continue
        item = None
        if em_bloco and l[:2] in ('- ', '• '):
            item = l[2:]
        else:
            em_bloco = False
            m = RE_FONTE_SOLTA.match(l)
            # na linha avulsa, o que vem depois da fonte em maiúsculas ("NÃO nomeie...") é instrução para a IA, não fonte
            item = RE_INSTRUCAO.split(m.group(1))[0] if m else None
        item = ' '.join(item.split()) if item else ''
        if item:
            achadas.append(item)
    anos, ordem = {}, []
    for linha in achadas:
        marcas = RE_ANO_DA_FONTE.findall(linha)
        chave = RE_ANO_DA_FONTE.sub('(@)', linha) if len(marcas) == 1 else linha
        if chave not in anos:
            anos[chave] = set()
            ordem.append(chave)
        if len(marcas) == 1:
            anos[chave].add(marcas[0])
    return [c.replace('(@)', '(' + ', '.join(sorted(anos[c])) + ')') if anos[c] else c for c in ordem]


RE_PERIODO = re.compile(r'(\d{2}/\d{2}/\d{4})\s+a\s+(\d{2}/\d{2}/\d{4})(?:,\s*(\d+)\s*dias?)?')
RE_TOTAL = re.compile(r'\btotal:?\s+(-?[\d.,]*\d)(?:\s*mm)?', re.I)


# ------------------------------------------------------------------ tabela mensal
RE_MES = re.compile(r'^(\d{4})-(\d{2})\s*[:;\s]\s*(SEM DADO|-?[\d.,]*\d)(?:\s*mm)?(.*)$', re.I)


def ler_mensal(texto):
    """Lê a tabela mensal. Devolve um dicionário; não confere nada (ver conferir_mensal)."""
    d = dict(local='', periodo=None, total=None, gdd_total=None, base_gdd=None, normal={}, meses=[], avisos=[],
             confianca_baixa=[])
    normais = {}
    for l in _linhas(texto):
        if not l or l.startswith('#'):
            continue
        baixo = l.lower()
        m = RE_MES.match(l)
        if m:
            ano, mes = int(m.group(1)), int(m.group(2))
            if not 1 <= mes <= 12:
                raise Recusa(f'Linha "{l[:40]}": mês {mes} não existe.')
            chuva = None if m.group(3).upper() == 'SEM DADO' else numero(m.group(3), f'chuva de {ano}-{mes:02d}')
            resto = m.group(4)
            gdd = None
            g = re.search(r'graus-dia\s+(-?[\d.,]*\d)', resto)
            if g:
                gdd = numero(g.group(1), f'graus-dia de {ano}-{mes:02d}')
            else:
                g = re.fullmatch(r'\s*[;\s]\s*(-?[\d.,]*\d)\s*', resto)
                if g:
                    gdd = numero(g.group(1), f'graus-dia de {ano}-{mes:02d}')
                elif resto.strip() and not re.search(r'média|temp|confiança|→', resto):
                    raise Recusa(f'Linha "{l[:60]}": não entendi o que vem depois da chuva. Use "AAAA-MM chuva" '
                                 'ou "AAAA-MM chuva graus-dia", ou cole a linha como a ferramenta devolveu.')
            n = re.search(r'média\s+(-?[\d.,]*\d)\s*mm', resto)
            if n:
                normais.setdefault(mes, []).append(numero(n.group(1), f'média de {ano}-{mes:02d}'))
            if 'confiança baixa' in resto:
                d['confianca_baixa'].append((ano, mes))
            d['meses'].append(dict(ano=ano, mes=mes, chuva=chuva, gdd=gdd))
            continue
        if baixo.startswith('chuva') and RE_PERIODO.search(l):
            p = RE_PERIODO.search(l)
            d['periodo'] = (data(p.group(1)), data(p.group(2)))
            antes = l[:p.start()].rstrip(' (')
            d['local'] = re.sub(r'^chuva\s*[—–-]\s*', '', antes, flags=re.I).strip()
        elif baixo.startswith('periodo:') or baixo.startswith('período:'):
            p = RE_PERIODO.search(l)
            if not p:
                raise Recusa('Linha "periodo:": escreva dd/mm/aaaa a dd/mm/aaaa.')
            d['periodo'] = (data(p.group(1)), data(p.group(2)))
        elif baixo.startswith('local:'):
            d['local'] = l.split(':', 1)[1].strip()
        elif baixo.startswith('resumo:') or baixo.startswith('total:'):
            t = RE_TOTAL.search(l)
            if t:
                d['total'] = numero(t.group(1), 'total do período')
        elif baixo.startswith('temperatura:'):
            g = re.search(r'graus-dia\s+(-?[\d.,]*\d)(?:\s*\(base\s+(-?[\d.,]*\d))?', l)
            if g:
                d['gdd_total'] = numero(g.group(1), 'graus-dia do período')
                if g.group(2):
                    d['base_gdd'] = numero(g.group(2), 'base dos graus-dia')
        elif baixo.startswith('gdd_total:'):
            d['gdd_total'] = numero(l.split(':', 1)[1], 'gdd_total')
        elif baixo.startswith('base_gdd:'):
            d['base_gdd'] = numero(l.split(':', 1)[1], 'base_gdd')
        elif baixo.startswith('normal:'):
            valores = l.split(':', 1)[1].replace(';', ' ').split()
            if len(valores) != 12:
                raise Recusa(f'Linha "normal:": esperava 12 valores (janeiro a dezembro), vieram {len(valores)}.')
            d['normal'] = {k + 1: numero(v, f'normal de {MESES[k]}') for k, v in enumerate(valores)}
        elif baixo.startswith('avisos:'):
            d['avisos'].append(l.split(':', 1)[1].strip())
    if normais and not d['normal']:
        # a média de um mês cortado nas pontas do período é parcial: fica o valor que mais se repete
        d['normal'] = {mes: max(set(v), key=v.count) for mes, v in normais.items()}
    return d


def conferir_mensal(d):
    """Confere a tabela mensal e devolve (meses aproveitados, notas). Recusa o que não fecha."""
    meses = list(d['meses'])
    if not meses:
        raise Recusa('Não achei nenhuma linha de mês (formato "AAAA-MM chuva"). O arquivo é o da tabela mensal?')
    vistos = set()
    for m in meses:
        chave = (m['ano'], m['mes'])
        if chave in vistos:
            raise Recusa(f'O mês {m["ano"]}-{m["mes"]:02d} aparece duas vezes.')
        vistos.add(chave)
    meses.sort(key=lambda m: (m['ano'], m['mes']))
    for a, b in zip(meses, meses[1:]):
        esperado = (a['ano'] + (a['mes'] == 12), a['mes'] % 12 + 1)
        if (b['ano'], b['mes']) != esperado:
            raise Recusa(f'Falta mês entre {a["ano"]}-{a["mes"]:02d} e {b["ano"]}-{b["mes"]:02d}: a tabela precisa '
                         'ser contínua. Confira a transcrição contra o texto da ferramenta.')
    notas = []
    soma = sum(m['chuva'] for m in meses if m['chuva'] is not None)
    if d['total'] is None:
        notas.append('SEM CONFERÊNCIA DA SOMA: o total do período (linha RESUMO da ferramenta) não foi informado.')
    else:
        folga = tolerancia(len(meses))
        if abs(soma - d['total']) > folga:
            por_ano = {}
            for m in meses:
                por_ano[m['ano']] = por_ano.get(m['ano'], 0.0) + (m['chuva'] or 0.0)
            lista = ' · '.join(f'{a}: {br(v)}' for a, v in sorted(por_ano.items()))
            raise Recusa(f'A soma dos meses ({br(soma)} mm) não fecha com o total que a ferramenta informou '
                         f'({br(d["total"])} mm; folga de {br(folga)} mm). Há mês copiado errado, faltando ou a mais. '
                         f'Soma por ano, para achar onde: {lista}.')
        notas.append(f'Soma dos {len(meses)} meses: {br(soma)} mm; total informado pela ferramenta: '
                     f'{br(d["total"])} mm (fecha).')
    com_gdd = [m for m in meses if m['gdd'] is not None]
    if com_gdd and len(com_gdd) != len(meses):
        raise Recusa(f'Graus-dia em {len(com_gdd)} de {len(meses)} meses: ou todos os meses têm, ou nenhum.')
    if com_gdd and d['gdd_total'] is not None:
        soma_g = sum(m['gdd'] for m in com_gdd)
        if abs(soma_g - d['gdd_total']) > tolerancia(len(meses)):
            raise Recusa(f'A soma dos graus-dia ({br(soma_g)}) não fecha com o total da ferramenta '
                         f'({br(d["gdd_total"])}). Confira a coluna dos graus-dia.')
        notas.append(f'Soma dos graus-dia: {br(soma_g)}; total da ferramenta: {br(d["gdd_total"])} (fecha).')
    # mês cortado nas pontas não entra nas estatísticas
    if d['periodo']:
        ini, fim = d['periodo']
        if (ini.year, ini.month) != (meses[0]['ano'], meses[0]['mes']) or \
                (fim.year, fim.month) != (meses[-1]['ano'], meses[-1]['mes']):
            raise Recusa(f'O período informado ({dma(ini)} a {dma(fim)}) não bate com os meses da tabela '
                         f'({meses[0]["ano"]}-{meses[0]["mes"]:02d} a {meses[-1]["ano"]}-{meses[-1]["mes"]:02d}).')
        if ini.day != 1:
            notas.append(f'O período começa em {dma(ini)}: o mês {meses[0]["ano"]}-{meses[0]["mes"]:02d} está '
                         'incompleto e ficou fora das estatísticas.')
            meses = meses[1:]
        if (fim + dt.timedelta(days=1)).day != 1:
            notas.append(f'O período termina em {dma(fim)}: o mês {meses[-1]["ano"]}-{meses[-1]["mes"]:02d} está '
                         'incompleto e ficou fora das estatísticas.')
            meses = meses[:-1]
    else:
        notas.append('Período não informado: confira se o primeiro e o último mês da tabela estão inteiros.')
    sem = [m for m in meses if m['chuva'] is None]
    if sem:
        notas.append(f'{len(sem)} mês(es) SEM DADO: ' + ', '.join(f'{m["ano"]}-{m["mes"]:02d}' for m in sem[:12]) + '.')
    if len(meses) < 36:
        raise Recusa(f'A tabela tem {len(meses)} meses inteiros. Para descrever o calendário é preciso pelo menos '
                     '3 anos; peça um período maior (a série começa em 1998).')
    return meses, notas


# ------------------------------------------------------------------ janela dia a dia
RE_DIA = re.compile(r'^(\d{4}-\d{2}-\d{2})\s*[:;\s]\s*(?:chuva\s+)?(SEM DADO|-?[\d.,]*\d)(?:\s*mm)?', re.I)
RE_VERANICO = re.compile(r'veranico máx\s+(\d+)\s+dia\(s\)(?:\s*\((\d{2}/\d{2}/\d{4})\s+a\s+(\d{2}/\d{2}/\d{4})\))?')
RE_MAIOR = re.compile(r'maior chuva\s+(-?[\d.,]*\d)\s*mm\s+em\s+(\d{2}/\d{2}/\d{4})')


def _nova_janela():
    return dict(local='', inicio=None, fim=None, n_dias=None, total=None, dias_chuva=None, veranico=None, maior=None,
                confianca='', avisos=[], sem_dado_informado=0, provisorio=None, mm=[], _datas=[], _tem_mm=False)


def ler_janelas(texto):
    """Lê uma ou mais respostas dia a dia (um bloco por ano). Não confere (ver conferir_janela)."""
    janelas, j = [], None
    for l in _linhas(texto):
        if not l or l.startswith('#'):
            continue
        baixo = l.lower()
        if baixo.startswith('chuva') and RE_PERIODO.search(l):
            p = RE_PERIODO.search(l)
            j = _nova_janela()
            j['inicio'], j['fim'] = data(p.group(1)), data(p.group(2))
            j['n_dias'] = int(p.group(3)) if p.group(3) else None
            antes = l[:p.start()].rstrip(' (')
            j['local'] = re.sub(r'^chuva\s*[—–-]\s*', '', antes, flags=re.I).strip()
            janelas.append(j)
            continue
        if j is None:
            if RE_DIA.match(l) or baixo.startswith(('mm:', 'resumo:', 'agro:')):
                raise Recusa('O arquivo da janela precisa começar, para cada ano, pela linha "Chuva — ... '
                             '(dd/mm/aaaa a dd/mm/aaaa, N dias):" que a ferramenta devolve.')
            continue
        if baixo.startswith('resumo:'):
            t = RE_TOTAL.search(l)
            if t:
                j['total'] = numero(t.group(1), 'total do período')
            c = re.search(r'confiança\s+(alta|média|media|baixa)', l)
            if c:
                j['confianca'] = c.group(1).replace('media', 'média')
            s = re.search(r'(\d+)\s+dia\(s\)\s+SEM DADO', l)
            if s:
                j['sem_dado_informado'] = int(s.group(1))
            p = re.search(r'desde\s+(\d{2}/\d{2}/\d{4})\s+ainda podem ser revisados', l)
            if p:
                j['provisorio'] = data(p.group(1))
        elif baixo.startswith('agro:'):
            c = re.search(r'(\d+)\s+dia\(s\)\s+de chuva', l)
            if c:
                j['dias_chuva'] = int(c.group(1))
            v = RE_VERANICO.search(l)
            if v:
                j['veranico'] = dict(dias=int(v.group(1)), de=data(v.group(2)) if v.group(2) else None,
                                     ate=data(v.group(3)) if v.group(3) else None)
            m = RE_MAIOR.search(l)
            if m:
                j['maior'] = dict(mm=numero(m.group(1), 'maior chuva'), data=data(m.group(2)))
        elif baixo.startswith('avisos:'):
            j['avisos'].append(l.split(':', 1)[1].strip())
        elif baixo.startswith('mm:') or re.fullmatch(r'[-\d.,;\sA-Za-z_—]+', l) and re.search(r'\d', l) \
                and not RE_DIA.match(l) and not re.match(r'[A-Za-zÀ-ú]{3,}', l):
            corpo = l.split(':', 1)[1] if baixo.startswith('mm:') else l
            for tok in corpo.replace(';', ' ').split():
                j['mm'].append(None if tok.lower() in SEM_DADO else numero(tok, f'mm da janela de {j["inicio"].year}'))
            j['_tem_mm'] = True
        else:
            m = RE_DIA.match(l)
            if m:
                j['_datas'].append(data(m.group(1)))
                j['mm'].append(None if m.group(2).upper() == 'SEM DADO'
                               else numero(m.group(2), f'chuva de {m.group(1)}'))
    if not janelas:
        raise Recusa('Não achei nenhuma resposta da ferramenta no arquivo (linha "Chuva — ... (dd/mm/aaaa a '
                     'dd/mm/aaaa, N dias):").')
    return janelas


def rotulo(j):
    """Como o ano da janela aparece nas tabelas: 2024 ou 2024/25 quando vira o ano."""
    a, b = j['inicio'].year, j['fim'].year
    return str(a) if a == b else f'{a}/{str(b)[2:]}'


def conferir_janela(j):
    """Confere UMA janela contra o que a ferramenta informou. Devolve notas; recusa o que não fecha."""
    quem = f'Janela de {dma(j["inicio"])} a {dma(j["fim"])}'
    if j['fim'] < j['inicio']:
        raise Recusa(f'{quem}: a data final vem antes da inicial.')
    n = (j['fim'] - j['inicio']).days + 1
    if j['n_dias'] is not None and j['n_dias'] != n:
        raise Recusa(f'{quem}: a linha diz {j["n_dias"]} dias, mas entre as duas datas há {n}. Copie a primeira '
                     'linha como a ferramenta devolveu.')
    if j['_tem_mm'] and j['_datas']:
        raise Recusa(f'{quem}: o bloco mistura linhas "mm:" com linhas de dia da ferramenta. Use um jeito só.')
    if len(j['mm']) != n:
        raise Recusa(f'{quem}: vieram {len(j["mm"])} valores de chuva para {n} dias. '
                     + ('Falta dia na transcrição.' if len(j['mm']) < n else 'Há dia a mais na transcrição.')
                     + ' Confira os mm contra o texto da ferramenta, mês a mês.')
    if j['_datas']:
        for k, d in enumerate(j['_datas']):
            if d != j['inicio'] + dt.timedelta(days=k):
                raise Recusa(f'{quem}: esperava o dia {dma(j["inicio"] + dt.timedelta(days=k))} e veio {dma(d)}. '
                             'Os dias precisam estar todos, na ordem.')
    mm = j['mm']
    if any(v is not None and (v < 0 or v > 700) for v in mm):
        raise Recusa(f'{quem}: há chuva negativa ou acima de 700 mm em um dia. Confira a transcrição.')
    notas = []
    sem = sum(1 for v in mm if v is None)
    if sem != j['sem_dado_informado'] and (sem or j['sem_dado_informado']):
        raise Recusa(f'{quem}: a ferramenta informou {j["sem_dado_informado"]} dia(s) SEM DADO e a transcrição tem '
                     f'{sem}. Marque dia sem dado com SD.')
    if sem:
        notas.append(f'{rotulo(j)}: {sem} dia(s) sem dado na janela (não entram nas somas e quebram o veranico).')
    soma = sum(v for v in mm if v is not None)
    if j['total'] is None:
        raise Recusa(f'{quem}: falta a linha RESUMO da ferramenta (o total do período). Sem ela não há como '
                     'conferir a transcrição.')
    folga = tolerancia(n)
    if abs(soma - j['total']) > folga:
        raise Recusa(f'{quem}: a soma dos dias ({br(soma)} mm) não fecha com o total da ferramenta '
                     f'({br(j["total"])} mm; folga de {br(folga)} mm). Algum dia foi copiado errado.')
    indice = lambda d: (d - j['inicio']).days  # noqa: E731
    if j['maior']:
        k = indice(j['maior']['data'])
        if not 0 <= k < n:
            raise Recusa(f'{quem}: a maior chuva informada cai em {dma(j["maior"]["data"])}, fora da janela.')
        if mm[k] is None or abs(mm[k] - j['maior']['mm']) > 0.051:
            raise Recusa(f'{quem}: a ferramenta diz que a maior chuva foi {br(j["maior"]["mm"])} mm em '
                         f'{dma(j["maior"]["data"])}, mas na transcrição esse dia tem '
                         f'{"SD" if mm[k] is None else br(mm[k])}. Os dias estão deslocados ou trocados.')
        acima = [v for v in mm if v is not None and v > j['maior']['mm'] + 0.051]
        if acima:
            raise Recusa(f'{quem}: há dia com {br(max(acima))} mm, acima da maior chuva que a ferramenta informou '
                         f'({br(j["maior"]["mm"])} mm). Confira a transcrição.')
    v = j['veranico']
    if v and v['de'] and v['ate'] and not sem:
        a, b = indice(v['de']), indice(v['ate'])
        if not (0 <= a <= b < n) or b - a + 1 != v['dias']:
            raise Recusa(f'{quem}: o veranico máximo informado ({v["dias"]} dias, {dma(v["de"])} a {dma(v["ate"])}) '
                         'não cabe na janela ou as datas não dão esse número de dias. Copie a linha AGRO como veio.')
        # dia "sem chuva" para a ferramenta tem menos de 1 ou de 2 mm, conforme a fonte do dia
        molhado = [k for k in range(a, b + 1) if mm[k] > 2.0 + 1e-9]
        if molhado:
            k = molhado[0]
            raise Recusa(f'{quem}: o dia {dma(j["inicio"] + dt.timedelta(days=k))} está com {br(mm[k])} mm dentro do '
                         f'veranico que a ferramenta informou ({dma(v["de"])} a {dma(v["ate"])}). Os dias desse '
                         'trecho estão deslocados ou trocados.')
        for k in (a - 1, b + 1):
            if 0 <= k < n and mm[k] < 0.9:
                raise Recusa(f'{quem}: o dia {dma(j["inicio"] + dt.timedelta(days=k))} está com {br(mm[k])} mm, mas '
                             f'ele é vizinho do veranico informado ({dma(v["de"])} a {dma(v["ate"])}) e deveria '
                             'ter chuva. Os dias desse trecho estão deslocados.')
    if not j['maior'] or not v:
        notas.append(f'{rotulo(j)}: faltou a linha AGRO da ferramenta (maior chuva e veranico máximo): a soma '
                     'fechou, mas a posição dos dias não foi conferida.')
    if j['confianca'] == 'baixa':
        notas.append(f'{rotulo(j)}: a ferramenta marcou confiança baixa na chuva desta janela.')
    if j['provisorio']:
        notas.append(f'{rotulo(j)}: os dias desde {dma(j["provisorio"])} ainda podem ser revisados pela ferramenta.')
    return notas


def conferir_conjunto(janelas, salteados=False):
    """Confere cada janela e o conjunto: mesma janela em todos os anos, sem ano repetido nem faltando."""
    notas = []
    for j in janelas:
        notas += conferir_janela(j)
    janelas = sorted(janelas, key=lambda j: j['inicio'])
    base = janelas[-1]
    for j in janelas:
        if (j['inicio'].month, j['inicio'].day, j['fim'].month, j['fim'].day) != \
                (base['inicio'].month, base['inicio'].day, base['fim'].month, base['fim'].day):
            raise Recusa(f'A janela de {rotulo(j)} vai de {dm(j["inicio"])} a {dm(j["fim"])} e a de {rotulo(base)}, '
                         f'de {dm(base["inicio"])} a {dm(base["fim"])}. Todos os anos precisam da MESMA janela. Se a '
                         'ferramenta cortou o ano em andamento, tire esse ano ou encurte a janela de todos.')
    anos = [j['inicio'].year for j in janelas]
    if len(set(anos)) != len(anos):
        repetido = sorted({a for a in anos if anos.count(a) > 1})
        raise Recusa(f'Ano repetido no arquivo: {", ".join(map(str, repetido))}.')
    faltam = [a for a in range(anos[0], anos[-1] + 1) if a not in anos]
    if faltam and not salteados:
        raise Recusa(f'Falta(m) o(s) ano(s) {", ".join(map(str, faltam))} entre {anos[0]} e {anos[-1]}. Consulte os '
                     'que faltam ou, se a escolha foi essa, rode com --anos-salteados.')
    if faltam:
        notas.append(f'Anos fora da contagem, por escolha: {", ".join(map(str, faltam))}.')
    if len(janelas) < 5:
        raise Recusa(f'Só {len(janelas)} ano(s) de janela. Com menos de 5 anos não dá para falar em frequência; '
                     'consulte mais anos.')
    locais = {j['local'] for j in janelas if j['local']}
    if len(locais) > 1:
        raise Recusa('As respostas são de locais diferentes: ' + ' | '.join(sorted(locais)) + '.')
    return janelas, notas


# ------------------------------------------------------------------ autoteste
def _autoteste():
    assert numero('1.234,5') == 1234.5 and numero('384.9') == 384.9 and numero('0,0') == 0.0
    for ruim in ('1.234', 'abc', ''):
        try:
            numero(ruim)
            raise AssertionError(ruim)
        except Recusa:
            pass
    assert data('05/11/2024') == dt.date(2024, 11, 5) == data('2024-11-05')
    assert br(1234.56) == '1.234,6' and br(None) == '—' and dm(dt.date(2024, 3, 9)) == '09/03'

    # tabela mensal: linha da ferramenta e linha resumida dão o mesmo
    cru = ['Chuva — -10, -50 (01/07/2020 a 30/06/2023, 1095 dias):',
           'RESUMO: total 3.600,0 mm · média histórica (1991–2020) do mesmo período: 3.500,0 mm → +3%',
           'TEMPERATURA: graus-dia 14400 (base 10°C) · médias das mínimas 18°C']
    curto = ['periodo: 01/07/2020 a 30/06/2023', 'total: 3.600,0', 'gdd_total: 14400', 'base_gdd: 10']
    for k in range(36):
        ano, mes = 2020 + (6 + k) // 12, (6 + k) % 12 + 1
        cru.append(f'{ano}-{mes:02d}: 100,0 mm (média 97,2 mm → +3%) · temp média 18–29°C · graus-dia 400'
                   + (' · confiança baixa' if k == 5 else ''))
        curto.append(f'{ano}-{mes:02d} 100,0 400')
    a, b = ler_mensal('\n'.join(cru)), ler_mensal('\n'.join(curto))
    assert a['meses'] == b['meses'] and a['total'] == b['total'] == 3600 and a['gdd_total'] == 14400
    assert a['normal'][1] == 97.2 and a['confianca_baixa'] == [(2020, 12)] and a['base_gdd'] == 10
    meses, notas = conferir_mensal(a)
    assert len(meses) == 36 and any('fecha' in n for n in notas)
    for estrago, pista in ((lambda t: t.replace('2021-03: 100,0', '2021-03: 150,0'), 'não fecha'),
                           (lambda t: t.replace('2021-03: 100,0 mm (média 97,2 mm → +3%) · temp média 18–29°C · '
                                                'graus-dia 400\n', ''), 'Falta mês'),
                           (lambda t: t + '\n2021-03: 100,0 mm', 'duas vezes'),
                           (lambda t: t.replace('graus-dia 14400', 'graus-dia 15000'), 'graus-dia')):
        try:
            conferir_mensal(ler_mensal(estrago('\n'.join(cru))))
            raise AssertionError(pista)
        except Recusa as e:
            assert pista in str(e), (pista, str(e))

    # janela: bloco resumido e bloco com as linhas de dia dão o mesmo, e os estragos são pegos
    mm = [0, 0, 12.5, 30, 0, 0, 0, 0, 0, 0, 0, 0.4, 1.5, 0, 8, 2.2, 0, 0, 5, 1]
    cab = ['Chuva — -10, -50 (01/10/2024 a 20/10/2024, 20 dias):',
           'RESUMO: total 60,6 mm · média histórica (1991–2020) do mesmo período: 80,0 mm → -24% · confiança alta',
           'AGRO: 6 dia(s) de chuva · veranico máx 10 dia(s) (05/10/2024 a 14/10/2024) · maior chuva 30,0 mm em '
           '04/10/2024']
    resumido = '\n'.join(cab + ['mm: ' + ' '.join(str(v).replace('.', ',') for v in mm)])
    dias = '\n'.join(cab + [f'2024-10-{k + 1:02d}: chuva {str(float(v)).replace(".", ",")} mm · temp 20–30°C'
                            for k, v in enumerate(mm)])
    j1, j2 = ler_janelas(resumido)[0], ler_janelas(dias)[0]
    assert j1['mm'] == j2['mm'] == [float(v) for v in mm] and j1['total'] == 60.6 and j1['dias_chuva'] == 6
    assert j1['veranico'] == dict(dias=10, de=dt.date(2024, 10, 5), ate=dt.date(2024, 10, 14))
    assert conferir_janela(j1) == [] and conferir_janela(j2) == [] and rotulo(j1) == '2024'

    # as fontes: o bloco com que a ferramenta fecha cada resposta é lido inteiro e não atrapalha a leitura dos dados
    bloco = ('\n\nFONTES DOS DADOS (cite no fim da resposta a fonte de cada dado que você usar, como está):\n'
             '- Chuva: instituto de exemplo A e produto de exemplo B (universidade de exemplo).\n'
             '- Temperatura: modelo de exemplo C; informação de exemplo ({ano}).\n')
    assert fontes_do_texto(resumido) == [] and fontes_do_texto('Fonte: registro de exemplo.') == ['registro de exemplo.']
    assert fontes_do_texto('Fonte: registro de exemplo (casa X). NÃO nomeie nada ao responder.') == ['registro de exemplo (casa X).']
    dois_anos = dias + bloco.format(ano=2025) + '\n' + dias.replace('2024', '2023') + bloco.format(ano=2026)
    assert fontes_do_texto(dois_anos) == ['Chuva: instituto de exemplo A e produto de exemplo B (universidade de exemplo).',
                                          'Temperatura: modelo de exemplo C; informação de exemplo (2025, 2026).']
    lidas = ler_janelas(dois_anos)
    assert len(lidas) == 2 and all(j['mm'] == [float(v) for v in mm] and conferir_janela(j) == [] for j in lidas)
    com_bloco = ler_mensal('\n'.join(cru) + bloco.format(ano=2026))
    assert com_bloco['meses'] == a['meses'] and com_bloco['avisos'] == a['avisos'] and conferir_mensal(com_bloco)[0] == meses

    def estragado(troca, pista):
        try:
            conferir_janela(ler_janelas(troca(resumido))[0])
            raise AssertionError(pista)
        except Recusa as e:
            assert pista in str(e), (pista, str(e))

    estragado(lambda t: t.replace('mm: 0 0 12,5', 'mm: 0 12,5'), 'Falta dia')
    estragado(lambda t: t.replace('mm: 0 0 12,5', 'mm: 0 0 0 12,5'), 'dia a mais')
    estragado(lambda t: t.replace('12,5 30', '12,5 20'), 'não fecha')
    estragado(lambda t: t.replace('0 0 12,5 30 0', '0 12,5 30 0 0'), 'maior chuva')       # deslocou um dia
    estragado(lambda t: t.replace('0,4 1,5 0 8 2,2', '0,4 0 8 1,5 2,2'), 'veranico')        # trocou dentro do veranico
    estragado(lambda t: t.replace('RESUMO: total 60,6 mm', 'RESUMO: 60,6'), 'falta a linha RESUMO')
    sd = resumido.replace('confiança alta', 'confiança alta · 1 dia(s) SEM DADO (fora do total)') \
                 .replace('2,2 0 0 5 1', '2,2 SD 0 5 1')
    assert any('sem dado' in n for n in conferir_janela(ler_janelas(sd)[0]))
    sem_agro = '\n'.join(l for l in resumido.split('\n') if not l.startswith('AGRO'))
    assert any('faltou a linha AGRO' in n for n in conferir_janela(ler_janelas(sem_agro)[0]))

    # conjunto: mesma janela, anos seguidos
    def ano(a, extra=''):
        return resumido.replace('2024', str(a)) + extra
    cinco = '\n\n'.join(ano(a) for a in range(2020, 2025))
    js, _ = conferir_conjunto(ler_janelas(cinco))
    assert [j['inicio'].year for j in js] == [2020, 2021, 2022, 2023, 2024]
    for texto, pista, kw in ((cinco.replace(ano(2022) + '\n\n', ''), 'Falta(m) o(s) ano(s) 2022', {}),
                             (cinco + '\n\n' + ano(2023), 'Ano repetido', {}),
                             ('\n\n'.join(ano(a) for a in range(2021, 2025)), 'Só 4 ano', {}),
                             (cinco.replace('-10, -50 (01/10/2021', '-11, -50 (01/10/2021'), 'locais diferentes', {})):
        try:
            conferir_conjunto(ler_janelas(texto), **kw)
            raise AssertionError(pista)
        except Recusa as e:
            assert pista in str(e), (pista, str(e))
    seis = cinco + '\n\n' + ano(2026)
    js, notas = conferir_conjunto(ler_janelas(seis), salteados=True)
    assert len(js) == 6 and any('2025' in n for n in notas)
    curto = ano(2024).replace('(01/10/2024 a 20/10/2024, 20 dias)', '(01/10/2024 a 19/10/2024, 19 dias)') \
                     .replace('total 60,6 mm', 'total 59,6 mm').replace('2,2 0 0 5 1', '2,2 0 0 5')
    try:
        conferir_conjunto(ler_janelas('\n\n'.join([ano(a) for a in range(2020, 2024)] + [curto])))
        raise AssertionError('janela diferente')
    except Recusa as e:
        assert 'MESMA janela' in str(e), str(e)
    print('leitura.py: autoteste ok')


if __name__ == '__main__':
    _autoteste()
