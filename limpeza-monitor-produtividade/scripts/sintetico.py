"""Talhão de exemplo com erros PLANTADOS, para a demonstração e para medir os filtros.

Não é dado de máquina: é uma colheita simulada (passadas de ida e volta, um
ponto por segundo) sobre uma superfície de produtividade conhecida, com os
erros clássicos de monitor colocados em pontos sabidos. Serve para duas coisas:
  - a demonstração (limpar.py --demo), que roda sem arquivo do usuário;
  - o teste que confere quanto dos erros plantados a limpeza tira e quanto de
    ponto bom ela leva junto.

Teste embutido: python scripts/sintetico.py
"""

import csv
import json
import math

import numpy as np

from areas import utm_inversa

ZONA, SUL = 22, True
ORIGEM = (642300.0, 7541800.0)  # canto do talhão, em UTM 22S (interior de SP)
GIRO = math.radians(18)


def _girar(u, v):
    return (ORIGEM[0] + u * math.cos(GIRO) - v * math.sin(GIRO),
            ORIGEM[1] + u * math.sin(GIRO) + v * math.cos(GIRO))


def _superficie(u, v):
    """Produtividade verdadeira (t/ha): ondulação suave e uma mancha baixa."""
    mancha = 1.45 * np.exp(-(((u - 260) / 70) ** 2 + ((v - 380) / 110) ** 2))
    return 3.7 + 0.45 * np.sin(u / 140) + 0.35 * np.cos(v / 190) - mancha


def talhao(semente=7, largura=420.0, comprimento=600.0, plataforma=9.0, velocidade=1.7):
    """Devolve o dicionário do exemplo: colunas do arquivo, a verdade de cada ponto e o perímetro."""
    g = np.random.default_rng(semente)
    us, vs, ts, passada = [], [], [], []
    relogio = 8 * 3600.0
    n_passadas = int(largura // plataforma)
    por_passada = int(comprimento / velocidade)
    for k in range(n_passadas):
        v = np.arange(por_passada) * velocidade + 2.0
        if k % 2:
            v = v[::-1]
        us.append(np.full(por_passada, plataforma * (k + 0.5)))
        vs.append(v)
        ts.append(relogio + np.arange(por_passada))
        passada.append(np.full(por_passada, k))
        relogio += por_passada + 18  # manobra de cabeceira com a plataforma erguida: 18 s sem gravar
    u, v, t, passada = (np.concatenate(a) for a in (us, vs, ts, passada))
    n = len(u)
    prod = _superficie(u, v) * (1 + 0.04 * g.standard_normal(n))
    vel = velocidade * 3.6 * (1 + 0.03 * g.standard_normal(n))  # km/h
    umid = 13.5 + 0.6 * g.standard_normal(n)
    larg = np.full(n, plataforma)
    verdade = np.full(n, '', dtype=object)
    na_passada = np.concatenate([np.arange(por_passada)] * n_passadas)
    do_fim = por_passada - 1 - na_passada

    # 1. enchimento e esvaziamento da máquina nas pontas de cada passada
    for k, fator in enumerate((0.15, 0.40, 0.65, 0.85)):
        prod[na_passada == k] *= fator
        verdade[na_passada == k] = 'rampa'
    for k, fator in enumerate((0.50, 0.78)):
        prod[do_fim == k] *= fator
        verdade[do_fim == k] = 'rampa'
    miolo = np.flatnonzero((na_passada > 12) & (do_fim > 12))

    def sorteia(quantos):
        livres = miolo[verdade[miolo] == '']
        return g.choice(livres, size=quantos, replace=False)

    # 2. máquina quase parada: a velocidade cai e a produtividade calculada dispara
    for i in sorteia(int(0.004 * n)):
        trecho = slice(i, i + 3)
        livre = verdade[trecho] == ''
        vel[trecho] = np.where(livre, vel[trecho] * 0.35, vel[trecho])
        prod[trecho] = np.where(livre, prod[trecho] * 1.8, prod[trecho])
        verdade[trecho] = np.where(livre, 'lenta', verdade[trecho])
    # 3. picos absurdos e zeros
    i = sorteia(int(0.006 * n))
    prod[i] *= g.uniform(2.5, 4.0, len(i))
    verdade[i] = 'pico'
    i = sorteia(int(0.003 * n))
    prod[i] = 0.0
    verdade[i] = 'zero'
    # 4. erro local: dentro dos limites do talhão, mas fora do que os vizinhos mostram
    i = sorteia(int(0.015 * n))
    prod[i] *= np.where(g.random(len(i)) < 0.5, 1.45, 0.58)
    verdade[i] = 'local'
    # 5. última passada com meia plataforma, sem o operador avisar o monitor
    ultima = passada == n_passadas - 1
    livre = ultima & (verdade == '')
    larg[ultima] = round(plataforma * 0.4, 2)
    prod[livre] *= 0.45
    verdade[livre] = 'largura'
    # 6. salto de GPS para fora do talhão
    i = sorteia(25)
    u[i] = -g.uniform(40, 80, len(i))
    verdade[i] = 'fora'

    x, y = _girar(u, v)
    # 7. posição repetida: o mesmo ponto gravado duas vezes
    rep = np.sort(sorteia(12))
    ordem = np.sort(np.r_[np.arange(n), rep])
    marca = np.r_[False, ordem[1:] == ordem[:-1]]
    x, y, t, prod, vel, umid, larg, passada, verdade = (a[ordem] for a in (x, y, t, prod, vel, umid, larg, passada,
                                                                           verdade))
    verdade = np.where(marca, 'duplicado', verdade)
    lon, lat = utm_inversa(x, y, ZONA, SUL)
    cantos = [_girar(a, b) for a, b in ((0, 0), (largura, 0), (largura, comprimento + 4), (0, comprimento + 4))]
    plon, plat = utm_inversa([c[0] for c in cantos], [c[1] for c in cantos], ZONA, SUL)
    horas = [f'{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}' for s in t]
    return {
        'colunas': {'Longitude': np.round(lon, 7), 'Latitude': np.round(lat, 7), 'Hora': np.array(horas, dtype=object),
                    'Prod_t_ha': np.round(prod, 3), 'Veloc_kmh': np.round(vel, 2), 'Umidade': np.round(umid, 1),
                    'Largura_m': larg},
        'verdade': verdade, 'x': x, 'y': y, 'passada': passada,
        'perimetro': list(zip(plon.tolist(), plat.tolist())),
    }


def gravar_csv(caminho, exemplo):
    nomes = list(exemplo['colunas'])
    with open(caminho, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(nomes)
        w.writerows(zip(*(exemplo['colunas'][n].tolist() for n in nomes)))


def gravar_perimetro(caminho, exemplo):
    anel = [list(p) for p in exemplo['perimetro']]
    anel.append(anel[0])
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump({'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'properties': {'talhao': 'Exemplo'},
             'geometry': {'type': 'Polygon', 'coordinates': [anel]}}]}, f)


if __name__ == '__main__':
    ex = talhao()
    n = len(ex['verdade'])
    assert 15000 < n < 20000, n
    conta = {k: int((ex['verdade'] == k).sum()) for k in sorted(set(ex['verdade']))}
    assert conta['fora'] == 25 and conta['duplicado'] == 12 and conta['rampa'] == 46 * 6, conta
    limpos = ex['verdade'] == ''
    assert 0.90 < limpos.mean() < 0.96, limpos.mean()
    bons = ex['colunas']['Prod_t_ha'][limpos]
    assert 2.0 < bons.min() and bons.max() < 5.5, (bons.min(), bons.max())
    assert all(-51 < v < -48 for v in ex['colunas']['Longitude'][:5]) and len(ex['perimetro']) == 4
    assert all(-23 < v < -21 for v in ex['colunas']['Latitude'][:5])
    print('sintetico OK ·', n, 'pontos ·', conta)
