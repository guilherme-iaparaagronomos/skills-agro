"""Leitura das tabelas de chuva e temperatura e a conferência da transcrição.

Três tipos de tabela, reconhecidos pelo jeito da primeira coluna:

  diária    2024-10-01 12,4 19 31          data, chuva, mínima, máxima
  mensal    2024-10 231,0 21.8 31.6        mês, chuva, média das mínimas, média das máximas
  normais   10 161,5 25.9                  mês do ano (1 a 12 ou jan a dez), chuva, temperatura

Três jeitos de escrever, que podem se misturar no mesmo arquivo:

  - o texto da ferramenta `clima_historico` colado como veio;
  - o formato compacto acima (espaço, ponto e vírgula ou tabulação entre as colunas);
  - tabela com cabeçalho (CSV, TXT ou XLSX), para dado de estação própria. Colunas
    reconhecidas pelo nome: data (ou ano e mês), chuva, tmin, tmax, tmed, etp.

Linhas de controle, que servem para conferir a transcrição:

  local: -17.8, -50.93
  periodo: 01/07/2024 a 30/06/2025
  total: 1.518,2                 a soma que a ferramenta informou na linha RESUMO
  temperatura: 10 40             a mínima e a máxima do período (linha TEMPERATURA, escala de dia)
  normal: 267,6 229,1 ...        as 12 médias históricas da chuva, de janeiro a dezembro
  avisos: texto                  o que a ferramenta avisou, para sair no relatório

Teste embutido: python scripts/entrada.py
"""

import calendar
import csv
import datetime
import io
import math
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MESES = ('jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez')
_MESES_EN = {'feb': 2, 'apr': 4, 'may': 5, 'aug': 8, 'sep': 9, 'oct': 10, 'dec': 12}
VAZIOS = ('', '-', '--', 'sd', 'semdado', 'na', 'nan', 'null', 'nd', '#n/d', '#n/a')
CAMPOS = ('chuva', 'tmin', 'tmax', 'tmed', 'etp')
NAN = float('nan')


class ErroDeEntrada(Exception):
    """Arquivo que não deu para ler ou que não fecha; a mensagem vai para o usuário como está."""


def chave(texto):
    sem_acento = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', sem_acento.lower())


def numero(texto):
    """'1.234,5' → 1234.5; '12,5' e '12.5' → 12.5; vazio ou 'sd' → NaN. Recusa '1.234' (pode ser 1234 ou 1,234)."""
    t = str(texto).strip().replace('−', '-').replace(' ', '').replace(' ', '')
    t = re.sub(r'(mm|°c|ºc|%)$', '', t, flags=re.I)
    if chave(t) in VAZIOS or t.lower() in VAZIOS:
        return NAN
    if re.fullmatch(r'-?[1-9]\d{0,2}(\.\d{3})+', t):
        raise ErroDeEntrada(f'O número "{t}" pode ser lido de dois jeitos (milhar ou decimal). Escreva sem ponto de '
                            'milhar, por exemplo 1234 ou 1,234.')
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    try:
        return float(t)
    except ValueError:
        raise ErroDeEntrada(f'"{texto}" não é número.')


def _data(texto):
    t = str(texto).strip()
    m = re.fullmatch(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T].*)?', t)
    if m:
        a, me, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})(?: .*)?', t)
        if m:
            d, me, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        elif re.fullmatch(r'\d{5}(\.0+)?', t) and 20000 <= float(t) <= 80000:      # data do Excel
            return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(t)))
        else:
            return None
    try:
        return datetime.date(a, me, d)
    except ValueError:
        raise ErroDeEntrada(f'A data "{t}" não existe no calendário.')


def _ano_mes(texto):
    t = str(texto).strip()
    m = re.fullmatch(r'(\d{4})[-/](\d{1,2})', t)
    if m:
        a, me = int(m.group(1)), int(m.group(2))
    else:
        m = re.fullmatch(r'(\d{1,2})/(\d{4})', t)
        if not m:
            return None
        me, a = int(m.group(1)), int(m.group(2))
    if not 1 <= me <= 12:
        raise ErroDeEntrada(f'O mês "{t}" não existe.')
    return a, me


def _mes(texto):
    t = chave(texto)
    if re.fullmatch(r'\d{1,2}', t) and 1 <= int(t) <= 12:
        return int(t)
    if t[:3] in MESES:
        return MESES.index(t[:3]) + 1
    return _MESES_EN.get(t[:3])


def fim_do_mes(ano, mes):
    return datetime.date(ano, mes, calendar.monthrange(ano, mes)[1])


# ------------------------------------------------------------------ o texto da ferramenta
_NUM = r'-?\d+(?:[.,]\d+)*'
_RE_DIA = re.compile(r'^(\d{4}-\d{2}-\d{2}):\s*chuva\s*(SEM DADO|' + _NUM + r')(?:\s*mm)?(.*)$', re.I)
_RE_MES = re.compile(r'^(\d{4}-\d{2}):\s*(SEM DADO|' + _NUM + r')(?:\s*mm)?(.*)$', re.I)
_RE_TEMP = re.compile(r'temp(?:\s+m[eé]dia)?\s*(' + _NUM + r')\s*[–—-]\s*(' + _NUM + r')\s*°\s*C', re.I)
_RE_NORMAL = re.compile(r'm[eé]dia\s*(' + _NUM + r')\s*mm', re.I)
_RE_TITULO = re.compile(r'^Chuva\s*[—–-]\s*(.*?)\s*\((\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4}),\s*(\d+)\s*dias\)', re.I)
_RE_TOTAL = re.compile(r'RESUMO:\s*total\s*(' + _NUM + r')\s*mm', re.I)
_RE_EXTREMOS = re.compile(r'm[ií]n\s*(' + _NUM + r')\s*°\s*C\s*e\s*m[aá]x\s*(' + _NUM + r')\s*°\s*C\s*no per[ií]odo', re.I)
_RE_DA_FERRAMENTA = re.compile(r'^(RESUMO|AGRO|TEMPERATURA|COMO DIZER|MÉDIA ANUAL|ANOS INCOMPLETOS|Fonte)\b')
_RE_CHAVE = re.compile(r'^([A-Za-zÀ-ÿ_ ]{3,24}):\s*(.*)$')


def _novo(tipo, **campos):
    r = {'chuva': NAN, 'tmin': None, 'tmax': None, 'tmed': None, 'etp': None, 'baixa': False, 'normal': None}
    r.update(campos)
    r['tipo'] = tipo
    return r


def _da_ferramenta(linha):
    m = _RE_DIA.match(linha)
    tipo = 'diario'
    if not m:
        m, tipo = _RE_MES.match(linha), 'mensal'
    if not m:
        return None
    resto = m.group(3)
    r = _novo(tipo, chuva=NAN if m.group(2).upper().startswith('SEM') else numero(m.group(2)),
              baixa='confiança baixa' in resto.lower() or 'confianca baixa' in resto.lower())
    t = _RE_TEMP.search(resto)
    if t:
        r['tmin'], r['tmax'] = numero(t.group(1)), numero(t.group(2))
    if tipo == 'diario':
        r['data'] = _data(m.group(1))
    else:
        r['ano'], r['mes'] = _ano_mes(m.group(1))
        n = _RE_NORMAL.search(resto)
        r['normal'] = numero(n.group(1)) if n else None
    return r


# ------------------------------------------------------------------ o formato compacto
def _compacta(linha):
    partes = [p for p in re.split(r'[;\t]|\s+', linha.strip()) if p != '']
    if len(partes) < 2:
        return None
    marcas = [p for p in partes[1:] if chave(p) in ('cb', 'pv')]
    valores = [p for p in partes[1:] if chave(p) not in ('cb', 'pv')]
    data, ano_mes = _data(partes[0]), _ano_mes(partes[0])
    mes = _mes(partes[0]) if data is None and ano_mes is None else None
    if data is None and ano_mes is None and mes is None:
        return None
    if not 1 <= len(valores) <= 3:
        raise ErroDeEntrada(f'A linha "{linha.strip()}" tem {len(valores)} valor(es) depois da data. O formato compacto '
                            'aceita: chuva; chuva e temperatura média; ou chuva, mínima e máxima.')
    numeros = [numero(v) for v in valores]
    r = _novo('diario' if data else 'mensal' if ano_mes else 'normais', chuva=numeros[0], baixa='cb' in map(chave, marcas))
    if len(numeros) == 2:
        r['tmed'] = None if math.isnan(numeros[1]) else numeros[1]
    elif len(numeros) == 3:
        r['tmin'] = None if math.isnan(numeros[1]) else numeros[1]
        r['tmax'] = None if math.isnan(numeros[2]) else numeros[2]
    if data:
        r['data'] = data
    elif ano_mes:
        r['ano'], r['mes'] = ano_mes
    else:
        r['mes'] = mes
    return r


# ------------------------------------------------------------------ tabela com cabeçalho
_NOMES = (('etp', ('etp', 'eto', 'et0', 'evapotransp')), ('tmin', ('tmin', 'tempmin', 'minima', 'tn')),
          ('tmax', ('tmax', 'tempmax', 'maxima', 'tx')), ('chuva', ('chuva', 'prec', 'pluv', 'rain', 'ppt')),
          ('tmed', ('tmed', 'tmedia', 'tempmed', 'temperatura', 'temp', 'media')),
          ('data', ('data', 'date', 'dia')), ('ano', ('ano', 'year')), ('mes', ('mes', 'month')))


def _papel(nome):
    c = chave(nome)
    if c in ('p', 'mm'):
        return 'chuva'
    if c in ('t', 'tm'):
        return 'tmed'
    for papel, comecos in _NOMES:
        if any(c.startswith(x) or (papel in ('tmin', 'tmax') and x in c and c.startswith('t')) for x in comecos):
            return papel
    return None


def _de_tabela(grade):
    papeis = [_papel(c) for c in grade[0]]
    onde = {p: k for k, p in reversed(list(enumerate(papeis))) if p}
    if 'chuva' not in onde:
        raise ErroDeEntrada('Não achei a coluna da chuva no cabeçalho (' + ', '.join(str(c) for c in grade[0]) + '). '
                            'Nomes reconhecidos: data (ou ano e mês), chuva, tmin, tmax, tmed, etp.')
    if 'data' not in onde and 'mes' not in onde:
        raise ErroDeEntrada('Não achei a coluna da data (ou do mês) no cabeçalho.')
    registros = []
    for linha in grade[1:]:
        celula = lambda p: str(linha[onde[p]]).strip() if p in onde and onde[p] < len(linha) else ''
        if not any(str(c).strip() for c in linha):
            continue
        if 'data' in onde:
            data, ano_mes = _data(celula('data')), _ano_mes(celula('data'))
            if data is None and ano_mes is None:
                raise ErroDeEntrada(f'Não entendi a data "{celula("data")}". Use AAAA-MM-DD, DD/MM/AAAA ou AAAA-MM.')
            r = _novo('diario', data=data) if data else _novo('mensal', ano=ano_mes[0], mes=ano_mes[1])
        else:
            mes = _mes(celula('mes'))
            if mes is None:
                raise ErroDeEntrada(f'Não entendi o mês "{celula("mes")}". Use 1 a 12 ou jan a dez.')
            if 'ano' in onde:
                r = _novo('mensal', ano=int(numero(celula('ano'))), mes=mes)
            else:
                r = _novo('normais', mes=mes)
        r['chuva'] = numero(celula('chuva'))
        for campo in ('tmin', 'tmax', 'tmed', 'etp'):
            if campo in onde:
                v = numero(celula(campo))
                r[campo] = None if math.isnan(v) else v
        registros.append(r)
    return registros


_NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
       'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
       'p': 'http://schemas.openxmlformats.org/package/2006/relationships'}


def _grade_de_xlsx(caminho, planilha=None):
    try:
        z = zipfile.ZipFile(caminho)
    except zipfile.BadZipFile:
        raise ErroDeEntrada('O arquivo .xlsx não abriu. Se for .xls antigo, salve como .xlsx ou como CSV.')
    with z:
        nomes = set(z.namelist())
        if 'xl/workbook.xml' not in nomes:
            raise ErroDeEntrada('O arquivo não parece uma planilha .xlsx. Salve como CSV e envie de novo.')
        textos = []
        if 'xl/sharedStrings.xml' in nomes:
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', _NS):
                textos.append(''.join(t.text or '' for t in si.iter('{%s}t' % _NS['m'])))
        folhas = [(s.get('name'), s.get('{%s}id' % _NS['r']))
                  for s in ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets', _NS)]
        alvos = {r.get('Id'): r.get('Target')
                 for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')).findall('p:Relationship', _NS)}
        achadas = folhas[:1] if planilha is None else [f for f in folhas if chave(f[0]) == chave(planilha)]
        if not achadas:
            raise ErroDeEntrada(f'Planilha "{planilha}" não existe. As que há: {", ".join(f[0] for f in folhas)}.')
        alvo = alvos[achadas[0][1]].lstrip('/')
        alvo = alvo if alvo.startswith('xl/') else 'xl/' + alvo
        if z.getinfo(alvo).file_size > 80_000_000:
            raise ErroDeEntrada('A planilha é grande demais para este leitor. Salve só a tabela como CSV.')
        grade = []
        for linha in ET.fromstring(z.read(alvo)).iter('{%s}row' % _NS['m']):
            celulas = {}
            for c in linha.findall('m:c', _NS):
                tipo, v = c.get('t'), c.find('m:v', _NS)
                if tipo == 'inlineStr':
                    valor = ''.join(t.text or '' for t in c.iter('{%s}t' % _NS['m']))
                elif v is None or v.text is None:
                    valor = ''
                elif tipo == 's':
                    valor = textos[int(v.text)]
                else:
                    valor = v.text
                letras = re.match(r'[A-Z]+', c.get('r').upper()).group(0)
                coluna = 0
                for letra in letras:
                    coluna = coluna * 26 + ord(letra) - 64
                celulas[coluna - 1] = valor
            if any(str(v).strip() for v in celulas.values()):
                grade.append([celulas.get(k, '') for k in range(max(celulas) + 1)])
    return grade


# ------------------------------------------------------------------ leitura
def _linhas_de_controle(nome, valor, meta):
    c = chave(nome)
    if c == 'local':
        meta['local'] = valor.strip()
        m = re.fullmatch(r'\s*(-?\d+(?:[.,]\d+)?)\s*[,;]\s*(-?\d+(?:[.,]\d+)?)\s*', valor)
        if m and meta.get('latitude') is None:
            meta['latitude'] = float(m.group(1).replace(',', '.'))
    elif c == 'latitude':
        meta['latitude'] = float(valor.strip().replace(',', '.'))
    elif c == 'periodo':
        datas = [_data(p) for p in re.findall(r'\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}', valor)]
        if len(datas) != 2:
            raise ErroDeEntrada(f'A linha "periodo: {valor}" precisa de duas datas: 01/07/2024 a 30/06/2025.')
        meta['periodo'] = (datas[0], datas[1])
    elif c == 'total':
        meta['total'] = numero(valor.split()[0])
    elif c == 'normal':
        valores = [numero(v) for v in re.split(r'[;\s]+', valor.strip()) if v]
        if len(valores) != 12:
            raise ErroDeEntrada(f'A linha "normal:" precisa de 12 valores (janeiro a dezembro); veio com {len(valores)}.')
        meta['normal'] = valores
    elif c == 'temperatura':
        valores = [numero(v) for v in re.split(r'[;\s]+', valor.strip()) if v]
        if len(valores) != 2:
            raise ErroDeEntrada('A linha "temperatura:" precisa de dois valores: a mínima e a máxima do período.')
        meta['extremos'] = (valores[0], valores[1])
    elif c == 'avisos':
        meta['avisos_da_ferramenta'].append(valor.strip())
    else:
        return False
    return True


def ler(caminho, planilha=None):
    """Lê o arquivo. Devolve {'arquivo', 'tipo', 'registros', 'meta', 'formatos', 'ignoradas'}."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise ErroDeEntrada(f'Arquivo não encontrado: {caminho}')
    meta = {'local': None, 'latitude': None, 'periodo': None, 'total': None, 'normal': None, 'extremos': None,
            'dias_declarados': None, 'avisos_da_ferramenta': []}
    registros, formatos, ignoradas = [], set(), []
    if caminho.suffix.lower() in ('.xlsx', '.xlsm'):
        grade = _grade_de_xlsx(caminho, planilha)
        if len(grade) < 2:
            raise ErroDeEntrada('A planilha tem menos de duas linhas preenchidas.')
        registros, formatos = _de_tabela(grade), {'tabela com cabeçalho'}
    elif caminho.suffix.lower() == '.xls':
        raise ErroDeEntrada('O formato .xls antigo não é lido. Salve como .xlsx ou como CSV e envie de novo.')
    else:
        bruto = caminho.read_bytes()
        for codificacao in ('utf-8-sig', 'cp1252'):
            try:
                texto = bruto.decode(codificacao)
                break
            except UnicodeDecodeError:
                texto = bruto.decode('latin-1', 'replace')
        linhas = [l.strip() for l in texto.splitlines() if l.strip() and not l.strip().startswith('#')]
        if not linhas:
            raise ErroDeEntrada('O arquivo está vazio.')
        primeira = re.split(r'[;\t,]|\s+', linhas[0])
        if (_papel(primeira[0]) in ('data', 'ano', 'mes') and len(primeira) >= 2
                and not _RE_CHAVE.match(linhas[0]) and _mes(primeira[0]) is None):
            sep = max((';', '\t', ','), key=lambda s: linhas[0].count(s))
            if linhas[0].count(sep) == 0:
                grade = [l.split() for l in linhas]
            else:
                grade = list(csv.reader(io.StringIO('\n'.join(linhas)), delimiter=sep))
            registros, formatos = _de_tabela(grade), {'tabela com cabeçalho'}
        else:
            for linha in linhas:
                r = _da_ferramenta(linha)
                if r:
                    registros.append(r)
                    formatos.add('texto da ferramenta')
                    continue
                titulo = _RE_TITULO.match(linha)
                if titulo:
                    _linhas_de_controle('local', titulo.group(1), meta)
                    meta['periodo'] = (_data(titulo.group(2)), _data(titulo.group(3)))
                    meta['dias_declarados'] = int(titulo.group(4))
                    continue
                total = _RE_TOTAL.search(linha)
                if total:
                    meta['total'] = numero(total.group(1))
                    continue
                extremos = _RE_EXTREMOS.search(linha)
                if extremos:
                    meta['extremos'] = (numero(extremos.group(1)), numero(extremos.group(2)))
                    continue
                if linha.upper().startswith('AVISOS:'):
                    meta['avisos_da_ferramenta'].append(linha[7:].strip())
                    continue
                if _RE_DA_FERRAMENTA.match(linha):      # linhas de resumo da ferramenta que não entram na conta
                    continue
                controle = _RE_CHAVE.match(linha)
                if controle and _linhas_de_controle(controle.group(1), controle.group(2), meta):
                    continue
                r = None if controle else _compacta(linha)
                if r:
                    registros.append(r)
                    formatos.add('compacto')
                else:
                    ignoradas.append(linha)
    if not registros:
        raise ErroDeEntrada('Não achei nenhuma linha de dado. O formato esperado está no começo de scripts/entrada.py '
                            'e no SKILL.md.')
    tipos = sorted({r['tipo'] for r in registros})
    if len(tipos) > 1:
        raise ErroDeEntrada('O arquivo mistura tabelas de tipos diferentes (' + ', '.join(tipos) + '). Use um arquivo '
                            'para cada: a diária, a mensal e a das normais.')
    for r in registros:
        if r['tmed'] is None and r['tmin'] is not None and r['tmax'] is not None:
            r['tmed'] = (r['tmin'] + r['tmax']) / 2.0
        if r['tmin'] is not None and r['tmax'] is not None and r['tmax'] < r['tmin']:
            raise ErroDeEntrada(f'Máxima menor que a mínima em {rotulo(r)} ({r["tmin"]} e {r["tmax"]}): confira a ordem '
                                'das colunas (a mínima vem antes).')
        if not math.isnan(r['chuva']) and r['chuva'] < 0:
            raise ErroDeEntrada(f'Chuva negativa em {rotulo(r)}.')
    if meta['normal'] is None and tipos[0] == 'mensal':
        por_mes = {}
        for r in registros:
            if r['normal'] is not None:
                por_mes.setdefault(r['mes'], []).append(r['normal'])
        if len(por_mes) == 12:      # o valor que mais se repete: mês cortado no começo ou no fim traz média parcial
            meta['normal'] = [max(set(v), key=v.count) for _, v in sorted(por_mes.items())]
    return {'arquivo': caminho.name, 'tipo': tipos[0], 'registros': registros, 'meta': meta,
            'formatos': sorted(formatos), 'ignoradas': ignoradas}


def rotulo(r):
    if r['tipo'] == 'diario':
        return r['data'].strftime('%d/%m/%Y')
    if r['tipo'] == 'mensal':
        return f'{MESES[r["mes"] - 1]}/{r["ano"]}'
    return MESES[r['mes'] - 1]


# ------------------------------------------------------------------ conferência
def tolerancia_da_soma(n):
    """Folga para a soma de n valores arredondados a 0,1 mm fechar com um total também arredondado:
    cerca de 3,5 desvios do erro de arredondamento somado (0,029 mm por valor)."""
    return max(0.5, 0.1 * math.sqrt(n))


def conferir(tab):
    """Devolve (o que fechou, o que não fechou). Com item na segunda lista, o balanço não roda."""
    reg, meta, ok, ruim = tab['registros'], tab['meta'], [], []
    if tab['tipo'] == 'diario':
        chaves = [r['data'] for r in reg]
        esperadas = [min(chaves) + datetime.timedelta(days=k) for k in range((max(chaves) - min(chaves)).days + 1)]
        nome = lambda c: c.strftime('%d/%m/%Y')
        inicio, fim = min(chaves), max(chaves)
    elif tab['tipo'] == 'mensal':
        chaves = [(r['ano'], r['mes']) for r in reg]
        a, m = min(chaves)
        esperadas = []
        while (a, m) <= max(chaves):
            esperadas.append((a, m))
            a, m = (a, m + 1) if m < 12 else (a + 1, 1)
        nome = lambda c: f'{MESES[c[1] - 1]}/{c[0]}'
        inicio, fim = datetime.date(*min(chaves), 1), fim_do_mes(*max(chaves))
    else:
        chaves, esperadas = [r['mes'] for r in reg], list(range(1, 13))
        nome = lambda c: MESES[c - 1]
        inicio = fim = None
    repetidas = sorted({c for c in chaves if chaves.count(c) > 1}) if len(set(chaves)) < len(chaves) else []
    faltando = [c for c in esperadas if c not in set(chaves)]
    if repetidas:
        ruim.append(f'{len(repetidas)} linha(s) repetida(s): ' + ', '.join(nome(c) for c in repetidas[:6])
                    + ('…' if len(repetidas) > 6 else '') + '.')
    if faltando:
        ruim.append(f'falta(m) {len(faltando)} linha(s) no meio da tabela: ' + ', '.join(nome(c) for c in faltando[:8])
                    + ('…' if len(faltando) > 8 else '') + '.')
    if not repetidas and not faltando:
        o_que = {'diario': 'dias seguidos', 'mensal': 'meses seguidos', 'normais': 'meses do ano'}[tab['tipo']]
        ok.append(f'{len(chaves)} {o_que}, sem falta e sem repetição'
                  + (f' ({nome(min(chaves))} a {nome(max(chaves))}).' if inicio else '.'))
    if meta['periodo'] and inicio:
        de, ate = meta['periodo']
        if tab['tipo'] == 'mensal':
            fecha = (de.year, de.month) == min(chaves) and (ate.year, ate.month) == max(chaves)
        else:
            fecha = de == inicio and ate == fim
        texto = f'período informado ({de:%d/%m/%Y} a {ate:%d/%m/%Y})'
        (ok if fecha else ruim).append(f'{texto} {"bate" if fecha else "NÃO bate"} com a primeira e a última linha '
                                       f'({nome(min(chaves))} e {nome(max(chaves))}).')
    if meta['dias_declarados'] and tab['tipo'] == 'diario' and meta['dias_declarados'] != len(chaves):
        ruim.append(f'a ferramenta informou {meta["dias_declarados"]} dias e a tabela tem {len(chaves)}.')
    com_chuva = [r['chuva'] for r in reg if not math.isnan(r['chuva'])]
    sem = [rotulo(r) for r in reg if math.isnan(r['chuva'])]
    soma = sum(com_chuva)
    if meta['total'] is not None:
        folga = tolerancia_da_soma(len(com_chuva))
        dif = soma - meta['total']
        texto = (f'soma da chuva das linhas = {_br(soma)} mm; total informado = {_br(meta["total"])} mm '
                 f'(diferença {_br(dif, 1)} mm; folga de arredondamento {_br(folga, 1)} mm)')
        if abs(dif) <= folga:
            ok.append(texto + '.')
        else:
            ruim.append(texto + '. A transcrição não fecha: confira os valores linha a linha.')
    if meta['extremos'] and tab['tipo'] == 'diario':
        minimas = [r['tmin'] for r in reg if r['tmin'] is not None]
        maximas = [r['tmax'] for r in reg if r['tmax'] is not None]
        if minimas and maximas:
            fecha = abs(min(minimas) - meta['extremos'][0]) < 0.51 and abs(max(maximas) - meta['extremos'][1]) < 0.51
            texto = (f'menor mínima e maior máxima das linhas = {_br(min(minimas), 1)} e {_br(max(maximas), 1)} °C; '
                     f'informadas = {_br(meta["extremos"][0], 1)} e {_br(meta["extremos"][1], 1)} °C')
            (ok if fecha else ruim).append(texto + ('.' if fecha else '. A coluna de temperatura não fecha: confira.'))
    if tab['tipo'] == 'normais' and (sem or len(chaves) != 12):
        ruim.append('a tabela das normais precisa dos 12 meses, todos com chuva.')
    notas = []
    if meta['total'] is None and tab['tipo'] != 'normais':
        notas.append('sem a linha "total:", a soma da chuva não foi conferida (com dado do conector, informe o total da '
                     'linha RESUMO).')
    if sem:
        notas.append(f'{len(sem)} linha(s) sem dado de chuva: ' + ', '.join(sem[:8]) + ('…' if len(sem) > 8 else '') + '.')
    baixa = sum(1 for r in reg if r['baixa'])
    if baixa:
        notas.append(f'{baixa} linha(s) marcada(s) pela ferramenta com confiança baixa.')
    if tab['ignoradas']:
        notas.append(f'{len(tab["ignoradas"])} linha(s) do arquivo não são dado nem controle e ficaram de fora, por '
                     f'exemplo: "{tab["ignoradas"][0][:60]}".')
    return ok, ruim, notas


def _br(v, casas=1):
    return f'{v:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


# ------------------------------------------------------------------ períodos do balanço
def _media(valores):
    valores = [v for v in valores if v is not None]
    return sum(valores) / len(valores) if valores else None


def _fecha_periodo(inicio, fim, dias, sem_dado):
    faltam = [r['data'] for r in dias if math.isnan(r['chuva'])]
    if faltam and sem_dado != 'zero':
        raise ErroDeEntrada(f'O período de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} tem {len(faltam)} dia(s) sem dado de chuva '
                            f'({", ".join(d.strftime("%d/%m") for d in faltam[:6])}). O balanço não pula dia: ou o '
                            'usuário decide contar esses dias como zero (--sem-dado zero), ou a série começa depois.')
    etps = [r['etp'] for r in dias]
    return {'inicio': inicio, 'fim': fim, 'dias': len(dias),
            'chuva': sum(0.0 if math.isnan(r['chuva']) else r['chuva'] for r in dias),
            'tmin': _media([r['tmin'] for r in dias]), 'tmax': _media([r['tmax'] for r in dias]),
            'tmed': _media([r['tmed'] for r in dias]), 'etp': sum(etps) if all(e is not None for e in etps) else None,
            'sem_dado': len(faltam), 'sem_temperatura': sum(1 for r in dias if r['tmed'] is None)}


def limites_do_decendio(data):
    """O decêndio que contém a data: dias 1 a 10, 11 a 20 e 21 ao fim do mês."""
    if data.day <= 10:
        return data.replace(day=1), data.replace(day=10)
    if data.day <= 20:
        return data.replace(day=11), data.replace(day=20)
    return data.replace(day=21), fim_do_mes(data.year, data.month)


def periodos_do_diario(registros, passo='decendio', de=None, ate=None, sem_dado='recusar'):
    """Agrupa os dias em decêndios (ou meses) COMPLETOS. Devolve (períodos, dias que sobraram nas pontas)."""
    por_data = {r['data']: r for r in registros if (de is None or r['data'] >= de) and (ate is None or r['data'] <= ate)}
    if not por_data:
        raise ErroDeEntrada('Nenhum dia da tabela cai no intervalo pedido.')
    grupos = {}
    for data in sorted(por_data):
        limites = limites_do_decendio(data) if passo == 'decendio' else (data.replace(day=1), fim_do_mes(data.year, data.month))
        grupos.setdefault(limites, []).append(por_data[data])
    periodos, sobras = [], 0
    for (inicio, fim), dias in sorted(grupos.items()):
        if len(dias) == (fim - inicio).days + 1:
            periodos.append(_fecha_periodo(inicio, fim, dias, sem_dado))
        elif periodos and (inicio, fim) != max(grupos):
            raise ErroDeEntrada(f'Faltam dias no meio da série, no período de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}.')
        else:
            sobras += len(dias)
    if not periodos:
        raise ErroDeEntrada('A tabela não cobre nenhum ' + ('decêndio' if passo == 'decendio' else 'mês') + ' inteiro.')
    return periodos, sobras


def periodos_do_mensal(registros, de=None, ate=None):
    """Os meses da tabela mensal como períodos do balanço sequencial (de e ate = (ano, mês))."""
    saida = []
    for r in sorted(registros, key=lambda r: (r['ano'], r['mes'])):
        if (de and (r['ano'], r['mes']) < de) or (ate and (r['ano'], r['mes']) > ate):
            continue
        if math.isnan(r['chuva']):
            raise ErroDeEntrada(f'O mês {rotulo(r)} está sem dado de chuva: o balanço não pula mês.')
        inicio, fim = datetime.date(r['ano'], r['mes'], 1), fim_do_mes(r['ano'], r['mes'])
        saida.append({'inicio': inicio, 'fim': fim, 'dias': (fim - inicio).days + 1, 'chuva': r['chuva'],
                      'tmin': r['tmin'], 'tmax': r['tmax'], 'tmed': r['tmed'], 'etp': r['etp'], 'sem_dado': 0,
                      'sem_temperatura': 0 if r['tmed'] is not None else (fim - inicio).days + 1})
    if not saida:
        raise ErroDeEntrada('Nenhum mês da tabela cai no intervalo pedido.')
    return saida


def anos_completos(registros):
    """Anos da tabela mensal com os 12 meses e com chuva em todos."""
    por_ano = {}
    for r in registros:
        if not math.isnan(r['chuva']):
            por_ano.setdefault(r['ano'], set()).add(r['mes'])
    return sorted(a for a, meses in por_ano.items() if len(meses) == 12)


def normais_do_mensal(registros, anos=None):
    """Médias de cada mês do ano nos anos completos pedidos (todos, se anos=None)."""
    completos = anos_completos(registros)
    usados = [a for a in completos if anos is None or anos[0] <= a <= anos[1]]
    if not usados:
        raise ErroDeEntrada('Nenhum ano completo (12 meses com chuva) no intervalo pedido. Anos completos na tabela: '
                            + (f'{completos[0]} a {completos[-1]}' if completos else 'nenhum') + '.')
    saida = {'anos': usados, 'chuva': [], 'tmin': [], 'tmax': [], 'tmed': [], 'etp': []}
    for mes in range(1, 13):
        do_mes = [r for r in registros if r['mes'] == mes and r['ano'] in usados]
        saida['chuva'].append(sum(r['chuva'] for r in do_mes) / len(do_mes))
        for campo in ('tmin', 'tmax', 'tmed', 'etp'):
            valores = [r[campo] for r in do_mes]
            saida[campo].append(_media(valores) if all(v is not None for v in valores) else None)
    for campo in ('tmin', 'tmax', 'tmed', 'etp'):
        if any(v is None for v in saida[campo]):
            saida[campo] = None
    return saida


def normais_da_tabela(registros):
    """A tabela de 12 normais do usuário, na ordem de janeiro a dezembro."""
    por_mes = {r['mes']: r for r in registros}
    saida = {'anos': None, 'chuva': [por_mes[m]['chuva'] for m in range(1, 13)]}
    for campo in ('tmin', 'tmax', 'tmed', 'etp'):
        valores = [por_mes[m][campo] for m in range(1, 13)]
        saida[campo] = valores if all(v is not None for v in valores) else None
    return saida


if __name__ == '__main__':
    import os
    import tempfile

    assert numero('1.234,5') == 1234.5 and numero('12,5') == 12.5 and numero('20.5') == 20.5 and numero('0,0 mm') == 0
    assert math.isnan(numero('sd')) and math.isnan(numero('SEM DADO')) and numero('−1,5') == -1.5 and numero('0.125') == 0.125
    for ruim in ('1.234', 'abc'):
        try:
            numero(ruim)
            raise AssertionError(ruim)
        except ErroDeEntrada:
            pass
    assert _data('2024-10-01') == datetime.date(2024, 10, 1) == _data('01/10/2024') == _data('45566')
    assert _ano_mes('2024-10') == (2024, 10) == _ano_mes('10/2024') and _mes('Out') == 10 == _mes('10') == _mes('october')
    assert limites_do_decendio(datetime.date(2024, 2, 25)) == (datetime.date(2024, 2, 21), datetime.date(2024, 2, 29))
    assert _papel('Chuva (mm)') == 'chuva' and _papel('T mín') == 'tmin' and _papel('Temp. máxima') == 'tmax'
    assert _papel('ETo') == 'etp' and _papel('Data') == 'data' and _papel('Temperatura média') == 'tmed'

    with tempfile.TemporaryDirectory() as pasta:
        p = lambda nome: os.path.join(pasta, nome)

        def grava(nome, texto):
            open(p(nome), 'w', encoding='utf-8').write(texto)
            return p(nome)

        # o texto da ferramenta, como vem (números inventados)
        t = ler(grava('dia.txt', (
            'Chuva — -10.5, -50.25 (30/09/2024 a 12/10/2024, 13 dias):\n'
            'RESUMO: total 1.043,0 mm · média histórica (1991–2020) do mesmo período: 55,0 mm → +9% · confiança alta\n'
            'AGRO: 5 dia(s) de chuva · veranico máx 6 dia(s)\n'
            'TEMPERATURA: graus-dia 190 (base 10°C) · mín 17°C e máx 39°C no período\n'
            'AVISOS: 2 dia(s) com confiança baixa\n\n'
            '2024-09-30: chuva 0,0 mm · temp 22–39°C · umid 20% · vento 9km/h\n'
            + ''.join(f'2024-10-{d:02d}: chuva {c} mm · temp {a}–{b}°C · umid 50% · vento 9km/h{x}\n' for d, c, a, b, x in (
                (1, '0,0', 21, 38, ''), (2, '0,2', 20, 37, ''), (3, '1.000,5', 20, 30, ' · confiança baixa'),
                (4, '12,3', 19, 29, ''), (5, '0,0', 18, 30, ''), (6, '0,0', 17, 31, ''), (7, '5,0', 19, 30, ''),
                (8, '0,0', 20, 33, ''), (9, '25,0', 21, 30, ' · confiança baixa · provisório'), (10, '0,0', 20, 31, ''),
                (11, '0,0', 21, 32, ''), (12, '0,0', 22, 33, '')))
            + '\nFonte: pluviômetros e satélites da comunidade agrônomo10X (OagronomIA).\n')))
        assert t['tipo'] == 'diario' and len(t['registros']) == 13 and t['formatos'] == ['texto da ferramenta']
        assert t['meta']['total'] == 1043.0 and t['meta']['extremos'] == (17, 39) and t['meta']['latitude'] == -10.5
        assert t['registros'][3]['chuva'] == 1000.5 and t['registros'][3]['baixa'] and t['registros'][0]['tmed'] == 30.5
        ok, ruim, notas = conferir(t)
        assert not ruim and len(ok) == 4 and any('confiança baixa' in n for n in notas) and not t['ignoradas']
        assert t['meta']['avisos_da_ferramenta'] == ['2 dia(s) com confiança baixa']
        periodos, sobras = periodos_do_diario(t['registros'])
        assert len(periodos) == 1 and sobras == 3 and periodos[0]['dias'] == 10 and abs(periodos[0]['chuva'] - 1043.0) < 1e-9
        assert abs(periodos[0]['tmin'] - 19.5) < 1e-9 and periodos[0]['etp'] is None

        # o mesmo em formato compacto, com um erro de transcrição: a soma não fecha
        compacto = ('local: -10.5, -50.25\nperiodo: 30/09/2024 a 12/10/2024\ntotal: 1.043,0\ntemperatura: 17 39\n'
                    '2024-09-30 0,0 22 39\n2024-10-01 0,0 21 38\n2024-10-02 0,2 20 37\n2024-10-03 1.000,5 20 30 cb\n'
                    '2024-10-04 12,3 19 29\n2024-10-05 0,0 18 30\n2024-10-06 0,0 17 31\n2024-10-07 5,0 19 30\n'
                    '2024-10-08 0,0 20 33\n2024-10-09 25,0 21 30\n2024-10-10 0,0 20 31\n2024-10-11 0,0 21 32\n'
                    '2024-10-12 0,0 22 33\n')
        c = ler(grava('c.txt', compacto))
        assert c['formatos'] == ['compacto'] and not conferir(c)[1]
        assert [r['chuva'] for r in c['registros']] == [r['chuva'] for r in t['registros']]
        for errado, trecho in ((compacto.replace('12,3 19 29', '21,3 19 29'), 'não fecha'),
                               (compacto.replace('2024-10-05 0,0 18 30\n', ''), 'falta'),
                               (compacto.replace('2024-10-06 0,0 17 31', '2024-10-06 0,0 18 31'), 'temperatura não fecha'),
                               (compacto.replace('2024-10-08 0,0 20 33', '2024-10-07 0,0 20 33'), 'repetida'),
                               (compacto.replace('30/09/2024 a', '29/09/2024 a'), 'NÃO bate')):
            assert any(trecho in x for x in conferir(ler(grava('e.txt', errado)))[1]), trecho
        # dia sem dado: recusa, a não ser que o usuário mande contar como zero
        s = ler(grava('s.txt', compacto.replace('2024-10-05 0,0 18 30', '2024-10-05 sd 18 30').replace('total: 1.043,0\n', '')))
        try:
            periodos_do_diario(s['registros'])
            raise AssertionError('devia recusar')
        except ErroDeEntrada:
            pass
        assert periodos_do_diario(s['registros'], sem_dado='zero')[0][0]['sem_dado'] == 1
        assert any('sem dado' in n for n in conferir(s)[2]) and any('total:' in n for n in conferir(s)[2])

        # mensal: texto da ferramenta, com a média histórica em cada linha
        linhas = ['Chuva — área de 1.250 ha (01/01/2021 a 31/12/2022, 730 dias):',
                  'COMO DIZER À PESSOA (período de 2,0 anos): choveu em média 1.200,0 mm POR ANO, contra 1.251,0 mm por ano '
                  'do normal da região (a média de 30 anos, 1991–2020) → -4%. Fale em mm POR ANO.',
                  'RESUMO: total 2.400,0 mm · média histórica (1991–2020) do mesmo período: 2.502,0 mm → -4% · confiança alta',
                  'MÉDIA ANUAL dos 2 ano(s) completo(s): 1.200,0 mm × média histórica 1.251,0 mm → -4%',
                  'TEMPERATURA: graus-dia 9800.5 (base 10°C) · médias das mínimas 17.9°C e das máximas 28.6°C (em período '
                  'longo a temperatura vem de dado modelado mensal)',
                  'AVISOS: o pluviômetro de referência mais próximo registrou bem menos que o satélite no mês']
        for ano in (2021, 2022):
            for mes in range(1, 13):
                linhas.append(f'{ano}-{mes:02d}: {100 + (mes if ano == 2021 else -mes)},0 mm (média {90 + mes},5 mm → +5%) · '
                              f'temp média {15 + mes % 5}.5–{27 + mes % 4}°C · graus-dia 400')
        m = ler(grava('m.txt', '\n'.join(linhas)))
        assert m['tipo'] == 'mensal' and len(m['registros']) == 24 and m['meta']['normal'][0] == 91.5 and not conferir(m)[1]
        assert m['meta']['local'] == 'área de 1.250 ha' and m['meta']['latitude'] is None and m['meta']['extremos'] is None
        assert m['meta']['total'] == 2400.0 and len(m['meta']['avisos_da_ferramenta']) == 1 and not m['ignoradas']
        n = normais_do_mensal(m['registros'])
        assert n['anos'] == [2021, 2022] and abs(n['chuva'][4] - 100) < 1e-9 and abs(n['tmin'][0] - 16.5) < 1e-9
        assert normais_do_mensal(m['registros'], (2022, 2022))['chuva'][0] == 99 and anos_completos(m['registros'][:-1]) == [2021]
        assert len(periodos_do_mensal(m['registros'], (2021, 11), (2022, 2))) == 4

        # tabela com cabeçalho, de estação própria, com ETP medida
        e = ler(grava('est.csv', 'Data;Chuva (mm);T mín;T máx;ETo\n01/10/2024;0;19,5;33,1;5,2\n02/10/2024;12,4;20;30;4,1\n'))
        assert e['tipo'] == 'diario' and e['registros'][1]['chuva'] == 12.4 and e['registros'][0]['etp'] == 5.2
        assert e['formatos'] == ['tabela com cabeçalho'] and e['registros'][0]['tmin'] == 19.5
        # as 12 normais do usuário, com nome de mês
        x = ler(grava('n.csv', 'mes,chuva,temperatura\n' + '\n'.join(f'{MESES[k]},{50 + k},{20 + k / 10}' for k in range(12))))
        assert x['tipo'] == 'normais' and normais_da_tabela(x['registros'])['tmed'][11] == 21.1 and not conferir(x)[1]
        y = ler(grava('n2.txt', '\n'.join(f'{k + 1} {50 + k} 15 {25 + k}' for k in range(11))))
        assert any('12 meses' in r for r in conferir(y)[1])
        for texto, trecho in (('2024-10-01 1 2 3 4 5\n', 'valor(es)'), ('2024-10-01 5 30 20\n', 'Máxima menor'),
                              ('nada aqui\n', 'nenhuma linha'), ('2024-10-01 5 20 30\n2024-10 5 20 30\n', 'mistura'),
                              ('data;tmin\n2024-10-01;5\n', 'coluna da chuva'), ('2024-13-01 5\n', 'calendário')):
            try:
                ler(grava('r.txt', texto))
                raise AssertionError('devia recusar: ' + texto)
            except ErroDeEntrada as erro:
                assert trecho in str(erro), (trecho, str(erro))
    print('entrada OK')
