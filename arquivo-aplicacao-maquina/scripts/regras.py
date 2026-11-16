"""As regras do arquivo de aplicação que não dependem de geometria: leitura da
dose, unidade, conversão, degrau, limites, nome do arquivo e do campo.

A dose é do usuário. Nada aqui calcula ou recomenda dose: as funções só leem,
convertem unidade, arredondam e limitam QUANDO o usuário informa o valor, e
devolvem a lista do que mudou.

Teste embutido: python scripts/regras.py
"""

import math
import re
import unicodedata

# fator para a unidade de base de cada tipo de produto
UNIDADES = {
    'solido': {'kg/ha': 1.0, 't/ha': 1000.0},
    'liquido': {'l/ha': 1.0, 'm3/ha': 1000.0},
    'semente': {'sem/ha': None, 'sem/m': None},     # a conversão depende do espaçamento entre linhas
}
NOME_DO_PRODUTO = {'solido': 'sólido', 'liquido': 'líquido', 'semente': 'semente'}
# faixas largas, só para avisar de unidade trocada (não são limite agronômico)
GRANDEZA = {'kg/ha': (1.0, 20000.0), 't/ha': (0.001, 20.0), 'l/ha': (0.05, 2000.0), 'm3/ha': (0.001, 500.0),
            'sem/ha': (1000.0, 2000000.0), 'sem/m': (0.5, 100.0)}


def g(v):
    """Número sem zeros sobrando e com vírgula decimal: 120, 180,5, 0,00005."""
    t = f'{float(v):.8f}'.rstrip('0').rstrip('.')
    return (t or '0').replace('.', ',').replace('-', '−')


class Recusa(Exception):
    """O pedido não segue. A mensagem diz por quê e o que o usuário precisa informar."""


def unidade_canonica(texto):
    t = str(texto).strip().lower().replace(' ', '').replace('³', '3').replace('litros', 'l').replace('lt', 'l')
    t = t.replace('sementes', 'sem').replace('semente', 'sem').replace('ton', 't').replace('m^3', 'm3')
    return {'kg/ha': 'kg/ha', 't/ha': 't/ha', 'l/ha': 'l/ha', 'm3/ha': 'm3/ha', 'sem/ha': 'sem/ha', 'sem/m': 'sem/m'}.get(t)


def produto_canonico(texto):
    t = unicodedata.normalize('NFKD', str(texto).strip().lower())
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return {'solido': 'solido', 'adubo': 'solido', 'calcario': 'solido', 'gesso': 'solido', 'fertilizante': 'solido',
            'liquido': 'liquido', 'calda': 'liquido', 'semente': 'semente', 'sementes': 'semente'}.get(t)


def conferir_unidade(produto, unidade):
    if produto not in UNIDADES:
        raise Recusa('diga o tipo do produto com --produto: solido, liquido ou semente')
    if unidade not in UNIDADES[produto]:
        raise Recusa(f'a unidade "{unidade}" não combina com produto {NOME_DO_PRODUTO[produto]}. '
                     f'Para {NOME_DO_PRODUTO[produto]}: {" ou ".join(UNIDADES[produto])}')


def ler_dose(valor):
    """Devolve (número ou None, situação): 'numero', 'texto' (texto que é número), 'vazio' ou 'invalido'."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, 'vazio'
    if isinstance(valor, bool):
        return None, 'invalido'
    if isinstance(valor, (int, float)):
        return (float(valor), 'numero') if math.isfinite(valor) else (None, 'invalido')
    t = str(valor).strip()
    if re.fullmatch(r'[-+]?\d+(\.\d+)?', t):
        return float(t), 'texto'
    if re.fullmatch(r'[-+]?\d{1,3}(\.\d{3})+,\d+', t):          # 1.250,5
        return float(t.replace('.', '').replace(',', '.')), 'texto'
    if re.fullmatch(r'[-+]?\d+,\d+', t):                        # 1,5
        return float(t.replace(',', '.')), 'texto'
    return None, 'invalido'


def fator_de_conversao(produto, de, para, espacamento_m=None):
    """Por quanto multiplicar a dose para ir de uma unidade à outra do mesmo tipo de produto."""
    conferir_unidade(produto, de)
    conferir_unidade(produto, para)
    if de == para:
        return 1.0
    if produto == 'semente':
        if not espacamento_m or espacamento_m <= 0:
            raise Recusa('para converter entre sem/ha e sem/m informe o espaçamento entre linhas, em metros, com --espacamento-m')
        por_metro = espacamento_m / 10000.0                     # sem/ha -> sem/m
        return por_metro if (de, para) == ('sem/ha', 'sem/m') else 1.0 / por_metro
    return UNIDADES[produto][de] / UNIDADES[produto][para]


def arredondar_ao_degrau(dose, degrau):
    """Múltiplo do degrau mais próximo; no meio do caminho, para cima."""
    if degrau is None:
        return dose
    return math.floor(dose / degrau + 0.5 + 1e-9) * degrau


def casas_necessarias(valores, teto=4):
    """Quantas casas decimais (até o teto) bastam para escrever os valores sem perder nada."""
    for casas in range(teto + 1):
        if all(abs(round(v, casas) - v) < 1e-9 * max(1.0, abs(v)) for v in valores):
            return casas
    return teto


def aplicar(doses, produto, unidade, converter_para=None, espacamento_m=None, degrau=None, minimo=None, maximo=None,
            fora='recusar', casas=None):
    """Aplica, nesta ordem, só o que foi pedido: conversão de unidade, degrau, limites e casas decimais.
    doses = lista de números (já lidos). Devolve {'doses', 'unidade', 'casas', 'passos', 'mudancas'}.
    mudancas[i] = lista de (passo, de, para) do polígono i. Dose zero nunca é mexida pelo mínimo."""
    conferir_unidade(produto, unidade)
    for nome, v in (('--degrau', degrau), ('--minimo', minimo), ('--maximo', maximo)):
        if v is not None and (not math.isfinite(v) or v < 0 or (nome == '--degrau' and v == 0)):
            raise Recusa(f'{nome} tem de ser um número maior que zero' if nome == '--degrau' else f'{nome} não pode ser negativo')
    if minimo is not None and maximo is not None and minimo > maximo:
        raise Recusa('--minimo está maior que --maximo')
    atuais, mudancas, passos = list(doses), [[] for _ in doses], []
    final = unidade
    if converter_para and converter_para != unidade:
        k = fator_de_conversao(produto, unidade, converter_para, espacamento_m)
        atuais = [d * k for d in atuais]
        final = converter_para
        extra = f', com {g(espacamento_m)} m entre linhas' if produto == 'semente' else ''
        passos.append(f'unidade convertida de {unidade} para {converter_para} (dose × {g(k)}{extra})')
    if degrau is not None:
        for i, d in enumerate(atuais):
            novo = arredondar_ao_degrau(d, degrau)
            if abs(novo - d) > 1e-9:
                mudancas[i].append(('degrau', d, novo))
                atuais[i] = novo
        passos.append(f'doses arredondadas ao degrau de {g(degrau)} {final} informado pelo usuário')
    if minimo is not None or maximo is not None:
        foras = [(i, d) for i, d in enumerate(atuais)
                 if d != 0 and ((minimo is not None and d < minimo - 1e-9) or (maximo is not None and d > maximo + 1e-9))]
        if foras and fora != 'cortar':
            amostra = ', '.join(f'polígono {i + 1}: {g(d)}' for i, d in foras[:8])
            raise Recusa(f'{len(foras)} polígono(s) têm dose fora do limite informado ({_limites(minimo, maximo, final)}): {amostra}'
                         + ('…' if len(foras) > 8 else '') + '. Mostre a lista ao usuário: para levar essas doses ao limite, '
                         'repita com --fora-do-limite cortar; para manter, tire o limite')
        for i, d in foras:
            novo = minimo if (minimo is not None and d < minimo) else maximo
            mudancas[i].append(('limite', d, novo))
            atuais[i] = novo
        passos.append(f'limites informados pelo usuário: {_limites(minimo, maximo, final)}; dose zero fica zero')
    if casas is None:
        casas = casas_necessarias(atuais)
    else:
        for i, d in enumerate(atuais):
            novo = round(d, casas)
            if abs(novo - d) > 1e-9:
                mudancas[i].append(('casas', d, novo))
                atuais[i] = novo
    atuais = [round(d, casas) + 0.0 for d in atuais]
    return {'doses': atuais, 'unidade': final, 'casas': casas, 'passos': passos, 'mudancas': mudancas}


def _limites(minimo, maximo, unidade):
    partes = ([f'mínimo {g(minimo)}'] if minimo is not None else []) + ([f'máximo {g(maximo)}'] if maximo is not None else [])
    return ' e '.join(partes) + f' {unidade}'


def resumo(doses, areas_ha):
    """Faixa, média ponderada pela área e total de produto (dose × área)."""
    area = sum(areas_ha)
    total = sum(d * a for d, a in zip(doses, areas_ha))
    return {'minima': min(doses), 'maxima': max(doses), 'media': total / area if area else 0.0, 'total': total, 'area_ha': area,
            'valores_distintos': len({round(d, 6) for d in doses}), 'com_zero': sum(1 for d in doses if d == 0)}


def unidade_do_total(unidade):
    """A unidade do total de produto. Para sem/m não há total por área."""
    return {'kg/ha': 'kg', 't/ha': 't', 'l/ha': 'l', 'm3/ha': 'm³', 'sem/ha': 'sementes'}.get(unidade)


def avisos_de_grandeza(doses, unidade):
    """Avisa quando as doses estão fora da faixa usual da unidade (sinal de unidade trocada)."""
    positivas = [d for d in doses if d > 0]
    if not positivas or unidade not in GRANDEZA:
        return []
    baixo, alto = GRANDEZA[unidade]
    avisos = []
    if max(positivas) > alto:
        avisos.append(f'há dose de {g(max(positivas))} {unidade}, acima de {g(alto)}: confirme com o usuário se a unidade é essa mesma')
    if min(positivas) < baixo:
        avisos.append(f'há dose de {g(min(positivas))} {unidade}, abaixo de {g(baixo)}: confirme com o usuário se a unidade é essa mesma')
    return avisos


def nome_limpo(texto, limite=8):
    """Nome de arquivo sem espaço, acento ou símbolo, em maiúsculas, com até `limite` caracteres."""
    s = unicodedata.normalize('NFKD', str(texto))
    s = re.sub(r'[^A-Za-z0-9]', '', ''.join(c for c in s if not unicodedata.combining(c))).upper()
    return s[:limite]


def campo_limpo(texto):
    """Nome de campo do .dbf: até 10 caracteres, letras, números e sublinhado, começando por letra."""
    s = unicodedata.normalize('NFKD', str(texto))
    s = re.sub(r'[^A-Za-z0-9_]', '', ''.join(c for c in s if not unicodedata.combining(c))).upper()
    if not s or not s[0].isalpha():
        s = 'D' + s
    return s[:10]


def ler_tabela(texto):
    """'1=120;2=180,5;3=240' ou linhas 'zona;dose' -> {'1': 120.0, ...} (a chave é o texto da zona)."""
    tabela = {}
    pedacos = [p for linha in str(texto).replace('\r', '').split('\n') for p in (linha.split(';') if '=' in linha else [linha])]
    for p in pedacos:
        p = p.strip()
        if not p or p.lower().startswith(('zona', '#')):
            continue
        m = re.fullmatch(r'(.+?)\s*[=;\t]\s*([-+]?[\d.,]+)', p)
        if not m:
            raise Recusa(f'não entendi "{p}" na tabela de doses. Escreva zona=dose, por exemplo "1=120;2=180;3=240"')
        dose, situacao = ler_dose(m.group(2))
        if dose is None:
            raise Recusa(f'a dose "{m.group(2)}" da zona {m.group(1)} não é um número')
        chave = chave_de_zona(m.group(1))
        if chave in tabela:
            raise Recusa(f'a zona {m.group(1)} aparece duas vezes na tabela de doses')
        tabela[chave] = dose
    if not tabela:
        raise Recusa('a tabela de doses está vazia')
    return tabela


def chave_de_zona(valor):
    """1, 1.0 e '1' são a mesma zona."""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    t = str(valor).strip()
    return t[:-2] if re.fullmatch(r'-?\d+\.0', t) else t


if __name__ == '__main__':
    assert ler_dose(120) == (120.0, 'numero') and ler_dose('120.5') == (120.5, 'texto') and ler_dose('1,5') == (1.5, 'texto')
    assert ler_dose('1.250,5') == (1250.5, 'texto') and ler_dose('') == (None, 'vazio') and ler_dose(None) == (None, 'vazio')
    assert ler_dose('120 kg') == (None, 'invalido') and ler_dose(float('nan')) == (None, 'invalido') and ler_dose(True) == (None, 'invalido')
    assert unidade_canonica('Kg/ha') == 'kg/ha' and unidade_canonica('m³/ha') == 'm3/ha' and unidade_canonica('sementes/ha') == 'sem/ha'
    assert unidade_canonica('L/ha') == 'l/ha' and unidade_canonica('ton/ha') == 't/ha' and unidade_canonica('kg') is None
    assert produto_canonico('Sólido') == 'solido' and produto_canonico('líquido') == 'liquido' and produto_canonico('x') is None
    assert fator_de_conversao('solido', 't/ha', 'kg/ha') == 1000.0 and fator_de_conversao('liquido', 'l/ha', 'm3/ha') == 0.001
    assert abs(fator_de_conversao('semente', 'sem/ha', 'sem/m', 0.5) - 0.00005) < 1e-15            # 300 mil/ha a 0,5 m = 15 sem/m
    assert abs(300000 * fator_de_conversao('semente', 'sem/ha', 'sem/m', 0.5) - 15) < 1e-9
    assert abs(15 * fator_de_conversao('semente', 'sem/m', 'sem/ha', 0.5) - 300000) < 1e-6
    for ruim in (lambda: conferir_unidade('solido', 'l/ha'), lambda: fator_de_conversao('semente', 'sem/ha', 'sem/m'),
                 lambda: aplicar([1.0], 'solido', 'kg/ha', degrau=0), lambda: aplicar([1.0], 'solido', 'kg/ha', minimo=5, maximo=1),
                 lambda: aplicar([10.0, 500.0], 'solido', 'kg/ha', minimo=50, maximo=400), lambda: ler_tabela('1=abc'),
                 lambda: ler_tabela('1=10;1=20'), lambda: ler_tabela('')):
        try:
            ruim()
        except Recusa:
            pass
        else:
            raise AssertionError('devia recusar')
    assert arredondar_ao_degrau(124.9, 10) == 120 and arredondar_ao_degrau(125, 10) == 130 and arredondar_ao_degrau(0, 10) == 0
    assert abs(arredondar_ao_degrau(0.126, 0.05) - 0.15) < 1e-12
    r = aplicar([0.123, 0.25, 0.0], 'solido', 't/ha', converter_para='kg/ha', degrau=10, minimo=150, maximo=200, fora='cortar')
    assert r['doses'] == [150.0, 200.0, 0.0] and r['unidade'] == 'kg/ha' and r['casas'] == 0, r
    assert [m[0] for m in r['mudancas'][0]] == ['degrau', 'limite'] and not r['mudancas'][2] and len(r['passos']) == 3
    r = aplicar([120.0, 180.5], 'solido', 'kg/ha')
    assert r['doses'] == [120.0, 180.5] and r['casas'] == 1 and not r['passos'] and not any(r['mudancas'])
    r = aplicar([1.23456], 'liquido', 'l/ha', casas=2)
    assert r['doses'] == [1.23] and r['mudancas'][0][0][0] == 'casas'
    s = resumo([100.0, 200.0, 0.0], [1.0, 3.0, 1.0])
    assert s['total'] == 700.0 and s['media'] == 140.0 and s['com_zero'] == 1 and s['valores_distintos'] == 3
    assert avisos_de_grandeza([150.0, 300.0], 't/ha') and not avisos_de_grandeza([150.0, 300.0], 'kg/ha')
    assert avisos_de_grandeza([0.2], 'kg/ha') and not avisos_de_grandeza([0.0], 'kg/ha')
    assert nome_limpo('Adubação Talhão São João 2026') == 'ADUBACAO' and nome_limpo('n-1 kcl') == 'N1KCL' and nome_limpo('***') == ''
    assert campo_limpo('Dose (kg/ha)') == 'DOSEKGHA' and campo_limpo('2ª dose') == 'D2ADOSE' and len(campo_limpo('x' * 30)) == 10
    assert ler_tabela('1=120; 2=180,5 ;3=240') == {'1': 120.0, '2': 180.5, '3': 240.0}
    assert ler_tabela('zona;dose\n1;120\n2;180\n') == {'1': 120.0, '2': 180.0}
    assert chave_de_zona(1.0) == '1' and chave_de_zona('1.0') == '1' and chave_de_zona(' A ') == 'A' and chave_de_zona(2) == '2'
    assert unidade_do_total('kg/ha') == 'kg' and unidade_do_total('sem/m') is None
    print('regras OK: leitura da dose, unidades, conversão, degrau, limites, casas, nome do arquivo, tabela por zona, 8 recusas')
