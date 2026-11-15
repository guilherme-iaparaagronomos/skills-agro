"""Leitura da tabela do ensaio: CSV, TSV ou TXT (separador e vírgula decimal
detectados) e XLSX simples (primeira planilha, ou a que for pedida).

O que sai daqui é a tabela em colunas, cada uma como texto e, quando é número,
também como vetor numérico. Não decide o que é resposta, fator ou bloco: isso
é do módulo `delineamento`, e quem confirma é o usuário.

Teste embutido: python scripts/leitura.py
"""

import csv
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np

TETO_DE_LINHAS = 200000
VAZIOS = ('', '-', '--', '.', 'na', 'n/a', 'nan', 'null', 'nd', '#n/d', '#n/a', 'perdida', 'perdido')


class ErroDeLeitura(Exception):
    """Arquivo que não deu para ler; a mensagem vai para o usuário como está."""


def chave(nome):
    sem_acento = unicodedata.normalize('NFKD', str(nome)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', sem_acento.lower())


def numero(texto):
    """Converte '1.234,5', '12,5', '12.5', '35 %' em número; o que não for número vira NaN."""
    t = str(texto).strip().replace(' ', '').replace(' ', '')
    if t.endswith('%'):
        t = t[:-1]
    if not t:
        return float('nan')
    if ',' in t and '.' in t:
        t = t.replace('.', '').replace(',', '.') if t.rfind(',') > t.rfind('.') else t.replace(',', '')
    elif ',' in t:
        t = t.replace(',', '.')
    try:
        return float(t)
    except ValueError:
        return float('nan')


def _decodificar(bruto):
    for codificacao in ('utf-8-sig', 'cp1252'):
        try:
            return bruto.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return bruto.decode('latin-1', 'replace')


def _separador(linhas):
    """O separador que divide as primeiras linhas no mesmo número de colunas (mais de uma)."""
    melhor, nota = None, 0
    for sep in (';', '\t', ',', '|'):
        contagens = [len(next(csv.reader([l], delimiter=sep))) for l in linhas[:30]]
        if contagens[0] < 2:
            continue
        iguais = sum(1 for c in contagens if c == contagens[0]) / len(contagens)
        pontos = iguais * 100 + contagens[0] + (5 if sep in (';', '\t') else 0)  # empate: ';' e tab antes da vírgula
        if iguais >= 0.8 and pontos > nota:
            melhor, nota = sep, pontos
    return melhor


def _grade_de_texto(caminho):
    texto = _decodificar(Path(caminho).read_bytes())
    linhas = [l for l in texto.splitlines() if l.strip()]
    if len(linhas) < 2:
        raise ErroDeLeitura('O arquivo tem menos de duas linhas: precisa do cabeçalho e dos dados.')
    sep = _separador(linhas)
    if sep is None:
        if len(linhas[0].split()) >= 2:
            return [l.split() for l in linhas], 'espaços'
        raise ErroDeLeitura('Não achei o separador de colunas (ponto e vírgula, tabulação, vírgula ou barra). '
                            'Confira se o arquivo é uma tabela com cabeçalho na primeira linha.')
    return list(csv.reader(io.StringIO('\n'.join(linhas)), delimiter=sep)), {'\t': 'tabulação'}.get(sep, sep)


# ------------------------------------------------------------------ xlsx
_NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
       'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
       'p': 'http://schemas.openxmlformats.org/package/2006/relationships'}


def _coluna_da_referencia(ref):
    letras = re.match(r'[A-Z]+', ref.upper()).group(0)
    n = 0
    for letra in letras:
        n = n * 26 + ord(letra) - 64
    return n - 1


def planilhas_do_xlsx(caminho):
    with zipfile.ZipFile(caminho) as z:
        raiz = ET.fromstring(z.read('xl/workbook.xml'))
        return [s.get('name') for s in raiz.find('m:sheets', _NS)]


def _grade_de_xlsx(caminho, planilha=None):
    try:
        z = zipfile.ZipFile(caminho)
    except zipfile.BadZipFile:
        raise ErroDeLeitura('O arquivo .xlsx não abriu. Se for .xls antigo, salve como .xlsx ou como CSV.')
    with z:
        nomes = set(z.namelist())
        if 'xl/workbook.xml' not in nomes:
            raise ErroDeLeitura('O arquivo não parece uma planilha .xlsx. Salve como CSV e envie de novo.')
        textos = []
        if 'xl/sharedStrings.xml' in nomes:
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', _NS):
                textos.append(''.join(t.text or '' for t in si.iter('{%s}t' % _NS['m'])))
        folhas = [(s.get('name'), s.get('{%s}id' % _NS['r']))
                  for s in ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets', _NS)]
        alvos = {r.get('Id'): r.get('Target')
                 for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')).findall('p:Relationship', _NS)}
        if planilha is None:
            nome, rid = folhas[0]
        else:
            achadas = [f for f in folhas if f[0] == planilha or chave(f[0]) == chave(planilha)]
            if not achadas:
                raise ErroDeLeitura(f'Planilha "{planilha}" não existe. As que há: {", ".join(f[0] for f in folhas)}.')
            nome, rid = achadas[0]
        alvo = alvos[rid].lstrip('/')
        alvo = alvo if alvo.startswith('xl/') else 'xl/' + alvo
        if z.getinfo(alvo).file_size > 80_000_000:
            raise ErroDeLeitura('A planilha é grande demais para este leitor. Salve só a tabela do ensaio como CSV.')
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
                elif tipo == 'b':
                    valor = 'VERDADEIRO' if v.text == '1' else 'FALSO'
                elif tipo == 'e':
                    valor = ''
                else:
                    valor = v.text
                    if tipo is None or tipo == 'n':
                        try:  # o Excel guarda 0.1 + 0.2 como 0.30000000000000004: mostra o número curto
                            valor = repr(float(valor)) if float(valor) != int(float(valor)) else str(int(float(valor)))
                        except (ValueError, OverflowError):
                            pass
                celulas[_coluna_da_referencia(c.get('r'))] = valor
            if any(str(v).strip() for v in celulas.values()):
                grade.append([celulas.get(k, '') for k in range(max(celulas) + 1)])
    if len(grade) < 2:
        raise ErroDeLeitura(f'A planilha "{nome}" tem menos de duas linhas preenchidas.')
    return grade, f'planilha "{nome}"' + (f' (de {len(folhas)} no arquivo: {", ".join(f[0] for f in folhas)})'
                                          if len(folhas) > 1 else '')


# ------------------------------------------------------------------ tabela
def ler_tabela(caminho, planilha=None):
    """Lê o arquivo e devolve a tabela em colunas.

    {'arquivo', 'origem', 'colunas': [...], 'texto': {col: [str]}, 'numero': {col: vetor ou None},
     'linhas': n, 'avisos': [...]}. Em 'numero', a coluna é numérica quando pelo menos 80% das
    células preenchidas são número; o que não for vira NaN e é contado nos avisos.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        raise ErroDeLeitura(f'Arquivo não encontrado: {caminho}')
    extensao = caminho.suffix.lower()
    if extensao in ('.xlsx', '.xlsm'):
        grade, origem = _grade_de_xlsx(caminho, planilha)
    elif extensao == '.xls':
        raise ErroDeLeitura('O formato .xls antigo não é lido. Salve como .xlsx ou como CSV e envie de novo.')
    else:
        grade, origem = _grade_de_texto(caminho)
        origem = f'separador "{origem}"'
    cabecalho = [str(c).strip() for c in grade[0]]
    while cabecalho and not cabecalho[-1]:
        cabecalho.pop()
    if len(cabecalho) < 2:
        raise ErroDeLeitura('A tabela precisa de pelo menos duas colunas (o tratamento e a resposta), com o nome de '
                            'cada uma na primeira linha.')
    vistos, colunas = set(), []
    for k, nome in enumerate(cabecalho):
        nome = nome or f'coluna_{k + 1}'
        base, n = nome, 1
        while chave(nome) in vistos:
            n += 1
            nome = f'{base}_{n}'
        vistos.add(chave(nome))
        colunas.append(nome)
    corpo = [[str(c).strip() for c in l[:len(colunas)]] + [''] * (len(colunas) - len(l)) for l in grade[1:]]
    corpo = [l for l in corpo if any(l)]
    if not corpo:
        raise ErroDeLeitura('A tabela só tem o cabeçalho.')
    if len(corpo) > TETO_DE_LINHAS:
        raise ErroDeLeitura(f'A tabela tem {len(corpo)} linhas; este leitor vai até {TETO_DE_LINHAS}.')
    tabela = {'arquivo': caminho.name, 'origem': origem, 'colunas': colunas, 'texto': {}, 'numero': {},
              'linhas': len(corpo), 'avisos': []}
    for k, nome in enumerate(colunas):
        textos = [l[k] for l in corpo]
        preenchidos = [t for t in textos if t.lower() not in VAZIOS]
        numeros = np.array([numero(t) if t.lower() not in VAZIOS else np.nan for t in textos])
        validos = int(np.isfinite(numeros).sum())
        tabela['texto'][nome] = ['' if t.lower() in VAZIOS else t for t in textos]
        if preenchidos and validos >= 0.8 * len(preenchidos):
            tabela['numero'][nome] = numeros
            if validos < len(preenchidos):
                ruins = sorted({t for t in preenchidos if not np.isfinite(numero(t))})[:4]
                tabela['avisos'].append(f'Coluna "{nome}": {len(preenchidos) - validos} célula(s) com texto no lugar '
                                        f'de número ({", ".join(ruins)}) foram tratadas como vazias.')
        else:
            tabela['numero'][nome] = None
    return tabela


if __name__ == '__main__':
    import os
    import tempfile

    assert numero('1.234,5') == 1234.5 and numero('12,5') == 12.5 and numero('1,234.5') == 1234.5
    assert numero(' 35 %') == 35 and np.isnan(numero('abc')) and numero('-0,5') == -0.5 and numero('1e3') == 1000
    assert chave('Repetição 1') == 'repeticao1'
    with tempfile.TemporaryDirectory() as pasta:
        p = os.path.join
        # ponto e vírgula com vírgula decimal, linha em branco, célula vazia e texto no meio dos números
        open(p(pasta, 'a.csv'), 'w', encoding='cp1252').write(
            'Tratamento;Bloco;Produção (kg/ha);Obs\nTestemunha;1;3.250,5;\nTestemunha;2;3100;ok\n\n'
            'Adubo A;1;perdida;\nAdubo A;2;3.890,25;x\nAdubo B;1;4001;\nAdubo B;2;3950,5;\n')
        t = ler_tabela(p(pasta, 'a.csv'))
        assert t['colunas'] == ['Tratamento', 'Bloco', 'Produção (kg/ha)', 'Obs'] and t['linhas'] == 6
        assert t['numero']['Tratamento'] is None and t['numero']['Obs'] is None
        y = t['numero']['Produção (kg/ha)']
        assert y[0] == 3250.5 and np.isnan(y[2]) and y[3] == 3890.25 and t['texto']['Bloco'][1] == '2'
        assert '";"' in t['origem'] and not t['avisos']
        # vírgula com ponto decimal, tabulação e espaços
        open(p(pasta, 'b.csv'), 'w', encoding='utf-8').write(
            'trat,rep,y\nA,1,10.5\nA,2,11\nB,1,12.25\nB,2,x9\nC,1,9\nC,2,8.5\n')
        t = ler_tabela(p(pasta, 'b.csv'))
        assert t['numero']['y'][2] == 12.25 and np.isnan(t['numero']['y'][3]) and 'x9' in t['avisos'][0]
        open(p(pasta, 'c.tsv'), 'w', encoding='utf-8-sig').write('trat\trep\ty\nA\t1\t10,5\nA\t2\t11\n')
        assert ler_tabela(p(pasta, 'c.tsv'))['numero']['y'][0] == 10.5
        open(p(pasta, 'd.txt'), 'w', encoding='utf-8').write('trat rep y\nA 1 10.5\nA 2 11\n')
        assert ler_tabela(p(pasta, 'd.txt'))['colunas'] == ['trat', 'rep', 'y']
        # colunas com nome repetido ou vazio
        open(p(pasta, 'e.csv'), 'w', encoding='utf-8').write('trat;y;y;\nA;1;2;\nB;3;4;\n')
        assert ler_tabela(p(pasta, 'e.csv'))['colunas'] == ['trat', 'y', 'y_2']
        # xlsx mínimo, com texto compartilhado, texto embutido, número, célula pulada e duas planilhas
        folha = ('<worksheet xmlns="%s"><sheetData>'
                 '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="inlineStr"><is><t>y</t></is></c></row>'
                 '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>1</v></c><c r="C2"><v>10.5</v></c></row>'
                 '<row r="3"><c r="A3" t="s"><v>2</v></c><c r="C3"><v>0.30000000000000004</v></c></row>'
                 '</sheetData></worksheet>') % _NS['m']
        with zipfile.ZipFile(p(pasta, 'f.xlsx'), 'w') as z:
            z.writestr('xl/workbook.xml', '<workbook xmlns="%s" xmlns:r="%s"><sheets><sheet name="Dados" sheetId="1" '
                       'r:id="rId1"/><sheet name="Outra" sheetId="2" r:id="rId2"/></sheets></workbook>'
                       % (_NS['m'], _NS['r']))
            z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="%s"><Relationship Id="rId1" '
                       'Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="worksheets/sheet2.xml"/>'
                       '</Relationships>' % _NS['p'])
            z.writestr('xl/sharedStrings.xml', '<sst xmlns="%s"><si><t>trat</t></si><si><t>rep</t></si>'
                       '<si><r><t>Cult</t></r><r><t>ivar A</t></r></si></sst>' % _NS['m'])
            z.writestr('xl/worksheets/sheet1.xml', folha)
            z.writestr('xl/worksheets/sheet2.xml', folha.replace('10.5', '99'))
        t = ler_tabela(p(pasta, 'f.xlsx'))
        assert t['colunas'] == ['trat', 'rep', 'y'] and t['texto']['trat'] == ['Cultivar A', 'Cultivar A']
        assert t['numero']['y'][0] == 10.5 and t['texto']['y'][1] == '0.30000000000000004' and t['texto']['rep'][1] == ''
        assert 'Dados' in t['origem'] and planilhas_do_xlsx(p(pasta, 'f.xlsx')) == ['Dados', 'Outra']
        assert ler_tabela(p(pasta, 'f.xlsx'), 'outra')['numero']['y'][0] == 99
        for ruim, parte in (('nada.csv', 'não encontrado'), ('g.xls', '.xls antigo')):
            if ruim == 'g.xls':
                open(p(pasta, ruim), 'w').write('x')
            try:
                ler_tabela(p(pasta, ruim))
                raise AssertionError(ruim)
            except ErroDeLeitura as e:
                assert parte in str(e), e
        open(p(pasta, 'h.csv'), 'w').write('sozinha\n1\n2\n')
        try:
            ler_tabela(p(pasta, 'h.csv'))
            raise AssertionError('uma coluna só')
        except ErroDeLeitura:
            pass
    print('leitura OK')
