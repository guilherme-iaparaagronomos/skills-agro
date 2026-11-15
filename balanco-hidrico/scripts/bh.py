"""Balanço hídrico climatológico de Thornthwaite e Mather (1955).

Duas contas:

  normal(p, etp, cad)                o ano normal, cíclico: dezembro emenda em janeiro
  sequencial(p, etp, cad, arm0)      uma sequência de períodos reais, a partir de um
                                     armazenamento inicial informado

Em cada período, com D = P − ETP:
  D < 0   o solo seca:   ARM = ARM anterior × exp(D / CAD)       (Mendonça, 1958)
  D >= 0  o solo repõe:  ARM = menor entre CAD e ARM anterior + D
  ALT = ARM − ARM anterior
  ETR = ETP se D >= 0; senão P + |ALT|
  DEF = ETP − ETR        EXC = o que passou da CAD
  NEG.AC = CAD × ln(ARM / CAD)

No ano normal o armazenamento de partida é o único que fecha o ciclo (o de
dezembro que reproduz a si mesmo um ano depois). Ele é achado de forma exata, e
cai no critério de Mendonça quando a chuva do ano não enche o solo.

Teste embutido: python scripts/bh.py   (inclui cinco tabelas publicadas)
"""

import math

COLUNAS = ('p', 'etp', 'dif', 'neg', 'arm', 'alt', 'etr', 'def', 'exc')


class ErroDeBalanco(Exception):
    """Entrada que não dá balanço; a mensagem vai para o usuário como está."""


def _conferir(p, etp, cad):
    if len(p) != len(etp) or not p:
        raise ErroDeBalanco('Chuva e ETP precisam ter o mesmo número de períodos, e pelo menos um.')
    if not (isinstance(cad, (int, float)) and math.isfinite(cad) and cad > 0):
        raise ErroDeBalanco('A CAD precisa ser um número maior que zero, em mm.')
    for nome, serie in (('chuva', p), ('ETP', etp)):
        for k, v in enumerate(serie):
            if v is None or not math.isfinite(v):
                raise ErroDeBalanco(f'Falta o valor de {nome} no período {k + 1}: o balanço não pula período.')
            if v < 0:
                raise ErroDeBalanco(f'Valor negativo de {nome} no período {k + 1} ({v}).')


def _passo(arm, d, cad):
    if d < 0:
        return arm * math.exp(d / cad), False
    return (cad, True) if arm + d >= cad else (arm + d, False)


def _volta(difs, cad, arm):
    """Uma passada pelos períodos. Devolve o armazenamento do fim e se o solo encheu em algum deles."""
    encheu = False
    for d in difs:
        arm, cheio = _passo(arm, d, cad)
        encheu = encheu or cheio
    return arm, encheu


def _tabela(p, etp, cad, arm):
    linhas = []
    for pk, ek in zip(p, etp):
        d = pk - ek
        novo, cheio = _passo(arm, d, cad)
        alt = novo - arm
        if d < 0:
            etr, exc = pk - alt, 0.0
        else:
            etr, exc = ek, (arm + d - cad if cheio else 0.0)
        linhas.append({'p': pk, 'etp': ek, 'dif': d,
                       'neg': 0.0 if novo >= cad else (cad * math.log(novo / cad) if novo > 0 else None),
                       'arm': novo, 'alt': alt, 'etr': etr, 'def': max(0.0, ek - etr), 'exc': max(0.0, exc)})
        arm = novo
    return linhas


def _somas(linhas):
    return {c: sum(l[c] for l in linhas) for c in ('p', 'etp', 'dif', 'alt', 'etr', 'def', 'exc')}


def afericao(linhas, arm_inicial):
    """As identidades do balanço. Os resíduos devem ser zero (a menos do arredondamento da máquina)."""
    s = _somas(linhas)
    variacao = linhas[-1]['arm'] - arm_inicial
    return {'somas': s, 'variacao_do_armazenamento': variacao,
            'residuo_p': s['p'] - (s['etr'] + s['exc'] + variacao),      # ΣP = ΣETR + ΣEXC + ΔARM
            'residuo_etp': s['etp'] - (s['etr'] + s['def']),             # ΣETP = ΣETR + ΣDEF
            'residuo_alt': s['alt'] - variacao}                          # ΣALT = ΔARM (zero no ano normal)


def normal(p, etp, cad):
    """Balanço do ano normal (cíclico), com 12 meses ou outro número de períodos que feche um ano."""
    p, etp = [float(v) for v in p], [float(v) for v in etp]
    _conferir(p, etp, cad)
    difs = [a - b for a, b in zip(p, etp)]
    positivos, negativos = sum(d for d in difs if d > 0), sum(d for d in difs if d < 0)
    if negativos == 0:
        arm, partida = float(cad), 'sem período de P − ETP negativo: o armazenamento fica na CAD o ano todo'
    else:
        arm, partida = float(cad), None
        for _ in range(len(difs) + 4):
            fim, encheu = _volta(difs, cad, arm)
            if not encheu:
                # nenhuma reposição enche o solo: a volta é uma função afim do armazenamento de partida,
                # e o que fecha o ciclo sai direto (com uma estação seca só, é o critério de Mendonça, 1958)
                arm = _volta(difs, cad, 0.0)[0] / (1.0 - math.exp(negativos / cad))
                partida = 'a reposição do ano não enche o solo: partida pelo critério de Mendonça (1958)'
                break
            if abs(fim - arm) < 1e-12:
                partida = 'o solo chega à CAD na estação úmida'
                break
            arm = fim
        if partida is None or abs(_volta(difs, cad, arm)[0] - arm) > 1e-8:
            raise ErroDeBalanco('O balanço do ano normal não fechou o ciclo. Envie a tabela usada para conferência.')
    linhas = _tabela(p, etp, cad, arm)
    return {'cad': float(cad), 'arm_inicial': arm, 'linhas': linhas, 'partida': partida,
            'positivos': positivos, 'negativos': negativos, 'afericao': afericao(linhas, arm),
            'cheios': [k for k, l in enumerate(linhas) if l['arm'] >= cad]}


def sequencial(p, etp, cad, arm_inicial):
    """Balanço de uma sequência de períodos reais, a partir do armazenamento inicial informado (mm)."""
    p, etp = [float(v) for v in p], [float(v) for v in etp]
    _conferir(p, etp, cad)
    if not (math.isfinite(arm_inicial) and 0 <= arm_inicial <= cad + 1e-9):
        raise ErroDeBalanco(f'O armazenamento inicial ({arm_inicial}) precisa ficar entre 0 e a CAD ({cad}).')
    arm0 = min(float(arm_inicial), float(cad))
    linhas = _tabela(p, etp, cad, arm0)
    return {'cad': float(cad), 'arm_inicial': arm0, 'linhas': linhas, 'afericao': afericao(linhas, arm0)}


def depende_do_inicio(p, etp, cad, tolerancia=1.0):
    """Até que período o resultado depende do armazenamento inicial: compara a partida com o solo cheio e
    com o solo vazio. Devolve o índice do primeiro período em que as duas diferem menos que a tolerância
    (None se isso não acontece na série) e a diferença no último período."""
    cheio, vazio = sequencial(p, etp, cad, cad)['linhas'], sequencial(p, etp, cad, 0.0)['linhas']
    difs = [a['arm'] - b['arm'] for a, b in zip(cheio, vazio)]
    primeiro = next((k for k, d in enumerate(difs) if abs(d) < tolerancia), None)
    return primeiro, difs[-1]


if __name__ == '__main__':
    import random

    def perto(a, b, tol=1e-9):
        assert abs(a - b) <= tol, (a, b)

    # ---- tabelas publicadas (valores inteiros, como impressos; tolerância de 1 mm por casa)
    # Sentelhas e Angelocci, LCE 306 (ESALQ/USP), aula 9 de 2012: Posse (GO), Petrolina (PE), Garanhuns (PE) e
    # Passo Fundo (RS), CAD = 100 mm. Pereira (2005), Bragantia 64(2):311-313: Campina Grande (PB), CAD = 125 mm.
    publicadas = {
        'Posse': (100,
                  [271, 215, 230, 119, 20, 9, 5, 12, 30, 123, 223, 280],
                  [116, 97, 104, 88, 78, 63, 62, 90, 94, 109, 106, 106],
                  {'arm': [100, 100, 100, 100, 56, 33, 18, 8, 4, 18, 100, 100],
                   'etr': [116, 97, 104, 88, 64, 32, 20, 22, 34, 109, 106, 106],
                   'def': [0, 0, 0, 0, 14, 31, 42, 68, 60, 0, 0, 0],
                   'exc': [155, 118, 126, 31, 0, 0, 0, 0, 0, 0, 35, 174]}, (898, 215, 639)),
        'Petrolina': (100,
                      [72, 90, 148, 82, 29, 10, 13, 4, 6, 21, 50, 84],
                      [153, 139, 143, 121, 116, 97, 103, 106, 127, 167, 174, 157],
                      {'arm': [0, 0, 5, 3, 1, 1, 0, 0, 0, 0, 0, 0],
                       'etr': [72, 90, 143, 84, 31, 10, 14, 4, 6, 21, 50, 84],
                       'def': [81, 49, 0, 37, 85, 87, 89, 102, 121, 146, 124, 73],
                       'exc': [0] * 12}, (609, 994, 0)),
        'Garanhuns': (100,
                      [45, 58, 100, 115, 104, 122, 133, 74, 47, 33, 18, 22],
                      [96, 80, 94, 75, 76, 63, 60, 63, 60, 83, 89, 98],
                      {'arm': [7, 6, 12, 52, 80, 100, 100, 100, 88, 53, 26, 12],
                       'etr': [50, 59, 94, 75, 76, 63, 60, 63, 59, 68, 45, 36],
                       'def': [46, 21, 0, 0, 0, 0, 0, 0, 1, 15, 44, 62],
                       'exc': [0, 0, 0, 0, 0, 39, 73, 11, 0, 0, 0, 0]}, (748, 189, 123)),
        'Passo Fundo': (100,
                        [143, 148, 121, 118, 131, 129, 153, 166, 207, 167, 141, 162],
                        [105, 92, 90, 64, 44, 35, 36, 43, 47, 68, 82, 100],
                        {'arm': [100] * 12, 'etr': [105, 92, 90, 64, 44, 35, 36, 43, 47, 68, 82, 100],
                         'def': [0] * 12, 'exc': [38, 56, 31, 54, 87, 94, 117, 123, 160, 99, 59, 62]}, (806, 0, 980)),
        'Campina Grande': (125,
                           [41, 55, 100, 129, 95, 107, 124, 58, 38, 17, 19, 21],
                           [108, 109, 115, 107, 95, 80, 62, 78, 77, 102, 108, 117],
                           {'arm': [5, 3, 3, 25, 25, 52, 114, 97, 71, 36, 18, 8],
                            'etr': [44, 57, 100, 107, 95, 80, 62, 75, 64, 52, 37, 31],
                            'def': [64, 52, 15, 0, 0, 0, 0, 3, 13, 50, 71, 86]}, (805, 354, 0)),
    }
    casas, maior = 0, 0.0
    for nome, (cad, chuva, etp_, esperado, (s_etr, s_def, s_exc)) in publicadas.items():
        r = normal(chuva, etp_, cad)
        for coluna, valores in esperado.items():
            for k, publicado in enumerate(valores):
                dif = abs(r['linhas'][k][coluna] - publicado)
                assert dif <= 1.0, (nome, coluna, k + 1, r['linhas'][k][coluna], publicado)
                casas, maior = casas + 1, max(maior, dif)
        s = r['afericao']['somas']
        assert abs(s['etr'] - s_etr) <= 2 and abs(s['def'] - s_def) <= 2 and abs(s['exc'] - s_exc) <= 2, (nome, s)
        a = r['afericao']
        perto(a['residuo_p'], 0, 1e-9), perto(a['residuo_etp'], 0, 1e-9), perto(a['residuo_alt'], 0, 1e-9)
        perto(a['variacao_do_armazenamento'], 0, 1e-9)
    assert 'Mendonça' in normal(*publicadas['Petrolina'][1:3], 100)['partida']
    assert 'Mendonça' in normal(*publicadas['Campina Grande'][1:3], 125)['partida']
    assert 'chega à CAD' in normal(*publicadas['Garanhuns'][1:3], 100)['partida']
    assert 'sem período' in normal(*publicadas['Passo Fundo'][1:3], 100)['partida']
    # Campina Grande: o armazenamento de julho pela fórmula fechada de Mendonça, como na publicação (114 mm)
    perto(normal(*publicadas['Campina Grande'][1:3], 125)['linhas'][6]['arm'], 111 / (1 - math.exp(-465 / 125)), 1e-9)

    # ---- o armazenamento de partida contra a força bruta: 400 anos seguidos a partir do solo cheio
    sorteio = random.Random(7)
    for caso in range(300):
        n = sorteio.choice((12, 12, 36))
        chuva = [max(0.0, sorteio.gauss(60, 70)) * sorteio.choice((0, 1, 1)) for _ in range(n)]
        etp_ = [sorteio.uniform(20, 160) for _ in range(n)]
        cad = sorteio.choice((10, 40, 75, 100, 150, 300))
        if all(a >= b for a, b in zip(chuva, etp_)):
            continue
        r = normal(chuva, etp_, cad)
        arm = float(cad)
        for _ in range(400):
            arm, _encheu = _volta([a - b for a, b in zip(chuva, etp_)], cad, arm)
        perto(r['arm_inicial'], arm, 1e-6)
        a = r['afericao']
        perto(a['residuo_p'], 0, 1e-8), perto(a['residuo_etp'], 0, 1e-8), perto(a['variacao_do_armazenamento'], 0, 1e-8)
        assert all(0 <= l['arm'] <= cad + 1e-12 and l['def'] >= 0 and l['exc'] >= 0 and l['etr'] <= l['etp'] + 1e-12
                   for l in r['linhas'])

    # ---- casos-limite
    r = normal([200] * 12, [100] * 12, 100)                 # chove mais que a ETP o ano todo
    assert all(l['arm'] == 100 and l['def'] == 0 and l['exc'] == 100 and l['neg'] == 0 for l in r['linhas'])
    r = normal([0] * 12, [100] * 12, 100)                   # ano todo sem chuva: o solo não tem de onde repor
    assert all(l['arm'] == 0 and l['etr'] == 0 and l['def'] == 100 and l['neg'] is None for l in r['linhas'])
    r = normal([10] * 12, [100] * 12, 100)                  # chove pouco o ano todo: tudo o que chove evapora
    assert all(l['arm'] == 0 and l['etr'] == 10 and l['def'] == 90 for l in r['linhas'])
    pequena = normal(publicadas['Posse'][1], publicadas['Posse'][2], 5)['afericao']['somas']
    grande = normal(publicadas['Posse'][1], publicadas['Posse'][2], 400)['afericao']['somas']
    assert pequena['def'] > 215 > grande['def'] and pequena['exc'] > 639 > grande['exc']   # CAD maior: menos DEF e menos EXC
    perto(pequena['exc'] - pequena['def'], 424, 1e-9), perto(grande['exc'] - grande['def'], 424, 1e-9)

    # ---- sequencial
    r = sequencial([0, 0, 50, 300], [100, 100, 100, 100], 100, 100)
    l = r['linhas']
    perto(l[0]['arm'], 100 * math.exp(-1)), perto(l[1]['arm'], 100 * math.exp(-2)), perto(l[1]['neg'], -200)
    perto(l[0]['etr'], 100 - 100 * math.exp(-1)), perto(l[2]['etr'], 50 + l[1]['arm'] - l[2]['arm'])
    perto(l[3]['arm'], 100), perto(l[3]['exc'], 200 - (100 - l[2]['arm'])), perto(l[3]['etr'], 100)
    a = r['afericao']
    perto(a['residuo_p'], 0), perto(a['residuo_etp'], 0), perto(a['variacao_do_armazenamento'], 0)
    # as simulações das notas de aula (CAD = 100): 86 → 67 com P = 0 e ETP = 25; 67 → 82 com P = 40; 82 → 65 com P = 2
    perto(sequencial([0], [25], 100, 86)['linhas'][0]['arm'], 67, 0.5)
    perto(sequencial([40], [25], 100, 67)['linhas'][0]['arm'], 82, 0.5)
    perto(sequencial([2], [25], 100, 82)['linhas'][0]['arm'], 65, 0.5)
    perto(sequencial([100], [25], 100, 65)['linhas'][0]['exc'], 40, 0.5)
    # o ano normal repetido como sequência, partindo do armazenamento de partida, devolve a si mesmo
    r = normal(publicadas['Garanhuns'][1], publicadas['Garanhuns'][2], 100)
    s = sequencial(publicadas['Garanhuns'][1] * 3, publicadas['Garanhuns'][2] * 3, 100, r['arm_inicial'])
    for k in range(36):
        perto(s['linhas'][k]['arm'], r['linhas'][k % 12]['arm'], 1e-9)
    primeiro, no_fim = depende_do_inicio(publicadas['Posse'][1] * 2, publicadas['Posse'][2] * 2, 100)
    assert primeiro == 0 and no_fim == 0          # Posse começa em janeiro, com chuva que enche o solo no 1º mês
    primeiro, no_fim = depende_do_inicio([0, 0, 0], [50, 50, 50], 100)
    assert primeiro is None and no_fim > 1
    for ruim in (lambda: normal([1, 2], [1], 100), lambda: normal([1], [1], 0), lambda: normal([-1], [1], 100),
                 lambda: normal([float('nan')], [1], 100), lambda: sequencial([1], [1], 100, 150),
                 lambda: sequencial([1], [1], 100, -1)):
        try:
            ruim()
            raise AssertionError('devia recusar')
        except ErroDeBalanco:
            pass
    print(f'bh OK ({casas} casas de 5 tabelas publicadas, maior diferença {maior:.2f} mm)')
