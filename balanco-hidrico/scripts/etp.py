"""Evapotranspiração potencial (ETP) pelos três métodos que a skill oferece, todos
só com temperatura e latitude:

  thornthwaite      Thornthwaite (1948), com a temperatura média do período
  thornthwaite-tef  o mesmo, com a temperatura efetiva de Camargo et al. (1999)
  hargreaves        Hargreaves e Samani (1985), com a mínima, a máxima e a
                    radiação no topo da atmosfera

A astronomia (declinação, fotoperíodo e radiação no topo da atmosfera) segue as
equações do boletim FAO 56. O que cada método faz e os limites: references/metodo.md.

Teste embutido: python scripts/etp.py
"""

import datetime
import math

METODOS = ('thornthwaite', 'thornthwaite-tef', 'hargreaves')
NOMES = {'thornthwaite': 'Thornthwaite (1948)',
         'thornthwaite-tef': 'Thornthwaite com temperatura efetiva (Camargo et al., 1999)',
         'hargreaves': 'Hargreaves e Samani (1985)',
         'informada': 'ETP informada pelo usuário'}
T_QUENTE = 26.5     # acima disso o método troca a potência pelo polinômio de Willmott et al. (1985)
T_TETO = 37.5       # vértice do polinômio: acima dele a ETP padrão fica constante


class ErroDeMetodo(Exception):
    """Conta que o método não faz; a mensagem vai para o usuário como está."""


# ------------------------------------------------------------------ astronomia
def dia_do_ano(data):
    return min(365, data.timetuple().tm_yday)


def declinacao(j):
    return 0.409 * math.sin(2 * math.pi * j / 365 - 1.39)


def _angulo_do_por_do_sol(latitude, j):
    x = -math.tan(math.radians(latitude)) * math.tan(declinacao(j))
    return math.acos(max(-1.0, min(1.0, x)))


def fotoperiodo(latitude, j):
    """Horas entre o nascer e o pôr do sol no dia j do ano."""
    return 24 / math.pi * _angulo_do_por_do_sol(latitude, j)


def radiacao_no_topo(latitude, j):
    """Radiação solar no topo da atmosfera, em mm de evaporação por dia (MJ/m²/dia × 0,408)."""
    fi, delta, ws = math.radians(latitude), declinacao(j), _angulo_do_por_do_sol(latitude, j)
    dr = 1 + 0.033 * math.cos(2 * math.pi * j / 365)
    ra = 24 * 60 / math.pi * 0.0820 * dr * (ws * math.sin(fi) * math.sin(delta)
                                            + math.cos(fi) * math.cos(delta) * math.sin(ws))
    return max(0.0, ra) * 0.408


def _dias(inicio, fim):
    return [inicio + datetime.timedelta(days=k) for k in range((fim - inicio).days + 1)]


def astronomia(latitude, inicio, fim):
    """Médias do período: (fotoperíodo em horas, radiação no topo em mm/dia, número de dias)."""
    if not -66.0 <= latitude <= 66.0:
        raise ErroDeMetodo(f'Latitude {latitude}: fora da faixa em que as contas valem (66° sul a 66° norte). '
                           'Confira o sinal: latitude sul é negativa.')
    dias = _dias(inicio, fim)
    n = sum(fotoperiodo(latitude, dia_do_ano(d)) for d in dias) / len(dias)
    qo = sum(radiacao_no_topo(latitude, dia_do_ano(d)) for d in dias) / len(dias)
    return n, qo, len(dias)


# ------------------------------------------------------------------ Thornthwaite
def indice_de_calor(t_normais):
    """Índice de calor I e expoente a, das 12 temperaturas médias mensais normais do lugar."""
    if len(t_normais) != 12:
        raise ErroDeMetodo('O índice de calor de Thornthwaite pede as 12 temperaturas médias mensais normais.')
    i = sum((t / 5.0) ** 1.514 for t in t_normais if t > 0)
    a = 6.75e-7 * i ** 3 - 7.71e-5 * i ** 2 + 1.7912e-2 * i + 0.49239
    return i, a


def etp_padrao(t, i, a):
    """ETP de um mês padrão (30 dias, 12 horas de luz) para a temperatura t, em mm."""
    if t <= 0 or i <= 0:
        return 0.0
    if t < T_QUENTE:
        return 16.0 * (10.0 * t / i) ** a
    t = min(t, T_TETO)
    return -415.85 + 32.24 * t - 0.43 * t * t


def thornthwaite(t, i, a, horas_de_luz, dias):
    return etp_padrao(t, i, a) * horas_de_luz / 12.0 * dias / 30.0


def temperatura_efetiva(tmin, tmax):
    return 0.36 * (3.0 * tmax - tmin)


# ------------------------------------------------------------------ Hargreaves e Samani
def hargreaves(tmin, tmax, qo, dias, tmed=None):
    if tmax < tmin:
        raise ErroDeMetodo(f'Temperatura máxima ({tmax}) menor que a mínima ({tmin}): confira as colunas.')
    tmed = (tmin + tmax) / 2.0 if tmed is None else tmed
    return max(0.0, 0.0023 * qo * math.sqrt(tmax - tmin) * (tmed + 17.8) * dias)


# ------------------------------------------------------------------ um período
def calcular(metodo, latitude, inicio, fim, tmed=None, tmin=None, tmax=None, calor=None):
    """ETP do período [inicio, fim], em mm. `calor` = (I, a) de Thornthwaite."""
    if metodo not in METODOS:
        raise ErroDeMetodo(f'Método de ETP "{metodo}" não existe. Os que há: {", ".join(METODOS)}.')
    horas, qo, dias = astronomia(latitude, inicio, fim)
    tem_extremos = tmin is not None and tmax is not None
    if metodo == 'hargreaves':
        if not tem_extremos:
            raise ErroDeMetodo('Hargreaves e Samani pede a temperatura mínima e a máxima; a tabela só tem a média.')
        return hargreaves(tmin, tmax, qo, dias, tmed)
    if calor is None:
        raise ErroDeMetodo('Thornthwaite pede o índice de calor do lugar, que sai das 12 temperaturas médias normais.')
    if metodo == 'thornthwaite-tef':
        if not tem_extremos:
            raise ErroDeMetodo('A temperatura efetiva pede a mínima e a máxima; a tabela só tem a média.')
        return thornthwaite(temperatura_efetiva(tmin, tmax), calor[0], calor[1], horas, dias)
    if tmed is None:
        if not tem_extremos:
            raise ErroDeMetodo('Falta a temperatura do período.')
        tmed = (tmin + tmax) / 2.0
    return thornthwaite(tmed, calor[0], calor[1], horas, dias)


def metodos_possiveis(tem_media, tem_extremos, tem_normais):
    saida = []
    if tem_normais and (tem_media or tem_extremos):
        saida.append('thornthwaite')
    if tem_normais and tem_extremos:
        saida.append('thornthwaite-tef')
    if tem_extremos:
        saida.append('hargreaves')
    return saida


if __name__ == '__main__':
    D = datetime.date

    def perto(a, b, tol):
        assert abs(a - b) <= tol, (a, b, tol)

    # exemplos publicados: Sentelhas e Angelocci, LCE 306 (ESALQ/USP), aula 8 de 2012, Piracicaba, 22°42' S
    lat = -(22 + 42 / 60)
    n_jan, qo_jan, d_jan = astronomia(lat, D(2001, 1, 1), D(2001, 1, 31))
    n_jul, qo_jul, d_jul = astronomia(lat, D(2001, 7, 1), D(2001, 7, 31))
    assert (d_jan, d_jul) == (31, 31)
    # o exemplo usa N = 13,4 h em janeiro e 10,6 h em julho, que são os valores dos solstícios nessa latitude;
    # a média do mês pela equação da FAO 56 é 13,2 h e 10,8 h
    perto(fotoperiodo(lat, 355), 13.4, 0.05), perto(fotoperiodo(lat, 172), 10.6, 0.05)
    perto(n_jan, 13.22, 0.02), perto(n_jul, 10.76, 0.02)
    # o exemplo usa I = 12 (0,2 × 21,1)^1,514 = 106,15 e a = 2,33
    i_ex = 12 * (0.2 * 21.1) ** 1.514
    a_ex = 6.75e-7 * i_ex ** 3 - 7.71e-5 * i_ex ** 2 + 1.7912e-2 * i_ex + 0.49239
    perto(i_ex, 106.15, 0.01), perto(a_ex, 2.33, 0.005)
    perto(etp_padrao(24.4, i_ex, a_ex), 111.3, 0.4)                      # publicado: 111,3 mm
    perto(thornthwaite(24.4, i_ex, a_ex, 13.4, 31), 128.4, 0.5)          # publicado: 128,4 mm
    perto(temperatura_efetiva(13, 26), 23.4, 1e-9)                       # publicado: 23,4 °C
    perto(thornthwaite(23.4, i_ex, a_ex, 10.6, 31), 92.1, 0.5)           # publicado: 92,1 mm
    perto(thornthwaite(19.5, i_ex, a_ex, 10.6, 31), 60.2, 0.5)           # publicado: 60,2 mm
    perto(hargreaves(18.8, 30, 16.9, 31, 24.4), 170.2, 0.1)              # publicado: 170,2 mm
    perto(hargreaves(13, 26, 9.6, 31, 19.5), 92.0, 0.1)                  # publicado: 92,0 mm
    # tabela publicada na mesma aula: radiação no topo (mm/dia), latitudes sul de 0 a 30°, janeiro a dezembro
    tabela = {0: [14.5, 15.0, 15.2, 14.7, 13.9, 13.4, 13.5, 14.2, 14.9, 14.9, 14.6, 14.3],
              10: [15.9, 15.7, 15.0, 13.8, 12.4, 11.6, 11.9, 13.0, 14.4, 15.3, 15.7, 15.7],
              20: [16.7, 16.0, 14.5, 12.4, 10.6, 9.6, 10.0, 11.5, 13.5, 15.3, 16.2, 16.8],
              30: [17.2, 15.7, 13.5, 10.8, 8.5, 7.4, 7.8, 9.6, 12.2, 14.7, 16.7, 17.6]}
    # a equação da FAO 56 fica de 1,4% a 4,7% ACIMA dessa tabela em todas as 48 casas (2,5% na média): diferença
    # sistemática, do tamanho que a constante solar e o fator de conversão adotados explicam
    relativas = []
    for lat_t, valores in tabela.items():
        for mes, publicado in enumerate(valores, 1):
            fim = (D(2001, mes + 1, 1) if mes < 12 else D(2002, 1, 1)) - datetime.timedelta(days=1)
            relativas.append(astronomia(-lat_t, D(2001, mes, 1), fim)[1] / publicado - 1)
    assert 0.01 < min(relativas) and max(relativas) < 0.05 and 0.02 < sum(relativas) / 48 < 0.03, relativas
    maior = max(relativas) * 100
    # propriedades
    perto(fotoperiodo(0, 80), 12.0, 0.05)
    assert fotoperiodo(-30, 355) > 13.5 > 10.5 > fotoperiodo(-30, 172)
    i, a = indice_de_calor([25.0] * 12)
    perto(i, 12 * 5 ** 1.514, 1e-9)
    assert etp_padrao(-3, i, a) == 0 and etp_padrao(26.49, i, a) > 0
    assert abs(etp_padrao(26.5, i, a) - (-415.85 + 32.24 * 26.5 - 0.43 * 26.5 ** 2)) < 1e-9
    assert etp_padrao(45, i, a) == etp_padrao(T_TETO, i, a) > etp_padrao(30, i, a)
    # o mesmo janeiro com o fotoperíodo médio do mês (13,2 h) em vez do valor do exemplo (13,4 h): 126,9 mm
    perto(calcular('thornthwaite', lat, D(2001, 1, 1), D(2001, 1, 31), tmed=24.4, calor=(i_ex, a_ex)),
          etp_padrao(24.4, i_ex, a_ex) * n_jan / 12 * 31 / 30, 1e-9)
    perto(calcular('thornthwaite', lat, D(2001, 1, 1), D(2001, 1, 31), tmed=24.4, calor=(i_ex, a_ex)), 126.9, 0.1)
    perto(calcular('hargreaves', lat, D(2001, 7, 1), D(2001, 7, 31), tmin=13, tmax=26),
          hargreaves(13, 26, qo_jul, 31), 1e-9)
    perto(calcular('thornthwaite-tef', lat, D(2001, 7, 1), D(2001, 7, 31), tmin=13, tmax=26, calor=(i_ex, a_ex)),
          thornthwaite(23.4, i_ex, a_ex, n_jul, 31), 1e-9)
    assert metodos_possiveis(True, False, True) == ['thornthwaite']
    assert metodos_possiveis(True, True, False) == ['hargreaves'] and len(metodos_possiveis(True, True, True)) == 3
    for ruim in (lambda: calcular('hargreaves', lat, D(2001, 1, 1), D(2001, 1, 31), tmed=24),
                 lambda: calcular('thornthwaite', lat, D(2001, 1, 1), D(2001, 1, 31), tmed=24),
                 lambda: calcular('penman', lat, D(2001, 1, 1), D(2001, 1, 31), tmed=24),
                 lambda: astronomia(80, D(2001, 1, 1), D(2001, 1, 31)),
                 lambda: hargreaves(30, 20, 15, 31)):
        try:
            ruim()
            raise AssertionError('devia recusar')
        except ErroDeMetodo:
            pass
    print(f'etp OK (radiação no topo: de {min(relativas) * 100:.1f}% a {maior:.1f}% acima da tabela publicada)')
