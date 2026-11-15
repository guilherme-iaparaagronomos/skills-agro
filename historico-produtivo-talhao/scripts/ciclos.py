"""Acha os ciclos de vegetação numa curva de índice (data e valor de cada imagem)
e estima quando cada um começou, chegou ao pico e terminou.

A curva é o que o satélite viu: a média do índice na área, no dia de cada imagem
limpa. Entre duas imagens não há dado; por isso cada data estimada sai com as
duas imagens entre as quais ela caiu.

As regras (todas ajustáveis, todas escritas no relatório):

1. Imagens do mesmo dia viram uma (a média).
2. Queda isolada: uma imagem que fica `queda` ou mais abaixo da anterior e
   também da seguinte, com as duas a até `vizinhanca` dias dela, sai da conta
   (costuma ser nuvem ou sombra que sobrou na imagem). Queda que não volta na
   imagem seguinte fica: pode ser colheita. O relatório diz quantas saíram.
3. Pico: ponto mais alto que os vizinhos e que sobe pelo menos `amplitude_min`
   acima do menor valor de cada lado (até um ponto maior que ele, ou até a
   borda da janela). No lado em que a curva foi cortada pela janela basta
   metade. Dois picos a menos de `distancia_min` dias, ou sem um vale de
   `amplitude_min` entre eles: fica o maior (empate: o primeiro).
4. Base de cada lado do pico: o menor valor entre ele e o pico vizinho (ou a
   borda da janela).
5. Início do ciclo: quando a curva, subindo, passa de base + fração × (pico −
   base). Fim: quando, descendo, passa do mesmo nível calculado com a base do
   outro lado. A data sai por interpolação entre as duas imagens.
6. As janelas emendadas (um ano agrícola depois do outro) são lidas como uma
   série só, para o ciclo que atravessa a virada da janela não sair cortado.
   Nas pontas da série, o que foi cortado é dito: ciclo que começou antes do
   período consultado, ciclo em aberto no fim.

Teste embutido: python scripts/ciclos.py
"""

from datetime import date, timedelta

PADRAO = dict(fracao=0.30, amplitude_min=0.20, distancia_min=45, queda=0.10, vizinhanca=20, pico_min=None)


class ParametroInvalido(Exception):
    pass


def conferir_parametros(p):
    if not 0.05 <= p['fracao'] <= 0.60:
        raise ParametroInvalido('a fração vai de 0,05 a 0,60 (0,30 = 30% da subida entre a base e o pico)')
    if not 0.05 <= p['amplitude_min'] <= 0.80:
        raise ParametroInvalido('a amplitude mínima vai de 0,05 a 0,80')
    if not 10 <= p['distancia_min'] <= 200:
        raise ParametroInvalido('a distância mínima entre picos vai de 10 a 200 dias')
    if not 0.02 <= p['queda'] <= 0.50:
        raise ParametroInvalido('a queda isolada vai de 0,02 a 0,50')
    return p


def juntar_mesmo_dia(pontos):
    """[(data, valor)] -> ordenado, uma linha por data (média das repetidas)."""
    por_dia = {}
    for d, v in pontos:
        por_dia.setdefault(d, []).append(v)
    return [(d, sum(vs) / len(vs)) for d, vs in sorted(por_dia.items())]


def tirar_quedas(pontos, queda, vizinhanca):
    """Tira as quedas isoladas. Devolve (pontos que ficam, pontos tirados)."""
    ficam, tirados = list(pontos), []
    mudou = True
    while mudou:
        mudou = False
        for i in range(1, len(ficam) - 1):
            (da, va), (d, v), (db, vb) = ficam[i - 1], ficam[i], ficam[i + 1]
            if (d - da).days > vizinhanca or (db - d).days > vizinhanca:
                continue
            if va - v >= queda - 1e-9 and vb - v >= queda - 1e-9:
                tirados.append(ficam.pop(i))
                mudou = True
                break
    return ficam, sorted(tirados)


def _lados(v, i):
    """Para o ponto i: quanto ele sobe acima do menor valor de cada lado, e se o lado acabou na borda
    da janela (True) ou num ponto maior que ele (False)."""
    esq, borda_esq = v[i], True
    for j in range(i - 1, -1, -1):
        if v[j] > v[i]:
            borda_esq = False
            break
        esq = min(esq, v[j])
    dir_, borda_dir = v[i], True
    for j in range(i + 1, len(v)):
        if v[j] > v[i]:
            borda_dir = False
            break
        dir_ = min(dir_, v[j])
    return v[i] - esq, borda_esq, v[i] - dir_, borda_dir


def _aceita(v, i, amplitude_min):
    """Pico vale se sobe `amplitude_min` acima dos dois lados. Do lado que acaba na borda da janela
    (ciclo cortado por ela) basta metade, desde que o outro lado tenha a amplitude inteira."""
    sobe_esq, borda_esq, sobe_dir, borda_dir = _lados(v, i)
    e = amplitude_min - 1e-9
    if sobe_esq >= e and sobe_dir >= e:
        return True
    if borda_esq and sobe_esq >= e / 2 and sobe_dir >= e:
        return True
    return bool(borda_dir and sobe_dir >= e / 2 and sobe_esq >= e)


def achar_picos(pontos, amplitude_min, distancia_min, pico_min=None):
    """Índices dos picos na lista de pontos. Borda da janela não é pico."""
    v = [x for _, x in pontos]
    n = len(v)
    candidatos = []
    i = 1
    while i < n - 1:
        if v[i] > v[i - 1]:
            j = i
            while j + 1 < n and v[j + 1] == v[i]:   # patamar: vale a primeira data
                j += 1
            if j < n - 1 and v[j + 1] < v[i]:
                candidatos.append(i)
            i = j + 1
        else:
            i += 1
    bons = [i for i in candidatos if _aceita(v, i, amplitude_min) and (pico_min is None or v[i] >= pico_min)]
    # dois picos perto demais: fica o maior
    bons.sort(key=lambda i: -v[i])
    aceitos = []
    for i in bons:
        if all(abs((pontos[i][0] - pontos[k][0]).days) >= distancia_min for k in aceitos):
            aceitos.append(i)
    aceitos.sort()
    # dois picos sem um vale de `amplitude_min` entre eles são o mesmo ciclo (patamar com ondulação)
    mudou = True
    while mudou:
        mudou = False
        for a, b in zip(aceitos, aceitos[1:]):
            if min(v[a], v[b]) - min(v[a:b + 1]) < amplitude_min - 1e-9:
                aceitos.remove(b if v[b] <= v[a] else a)
                mudou = True
                break
    return aceitos


def _cruzamento(pontos, a, b, nivel, subindo):
    """Primeiro trecho entre os índices a..b em que a curva cruza o nível. Devolve (data, data_antes, data_depois) ou None."""
    passo = 1 if b >= a else -1
    i = a
    while i != b:
        (d0, v0), (d1, v1) = pontos[i], pontos[i + passo]
        if passo < 0:
            (d0, v0), (d1, v1) = (d1, v1), (d0, v0)       # sempre em ordem de data
        if subindo and v0 < nivel <= v1 or (not subindo) and v0 >= nivel > v1:
            dias = (d1 - d0).days
            f = 0.0 if v1 == v0 else (nivel - v0) / (v1 - v0)
            return d0 + timedelta(days=round(f * dias)), d0, d1
        i += passo
    return None


def achar_ciclos(pontos_brutos, parametros=None):
    """Devolve {'pontos', 'tirados', 'ciclos', 'avisos'} para a curva de uma safra de um talhão."""
    p = conferir_parametros({**PADRAO, **(parametros or {})})
    pontos, tirados = tirar_quedas(juntar_mesmo_dia(pontos_brutos), p['queda'], p['vizinhanca'])
    saida = {'pontos': pontos, 'tirados': tirados, 'ciclos': [], 'avisos': []}
    if len(pontos) < 5:
        saida['avisos'].append(f'só {len(pontos)} imagem(ns) no período: não dá para achar ciclo')
        return saida
    v = [x for _, x in pontos]
    picos = achar_picos(pontos, p['amplitude_min'], p['distancia_min'], p['pico_min'])
    for k, ip in enumerate(picos):
        limite_esq = picos[k - 1] if k > 0 else 0
        limite_dir = picos[k + 1] if k + 1 < len(picos) else len(pontos) - 1
        # base de cada lado: o menor valor; do lado esquerdo vale o mais perto do pico, do direito também
        base_esq = min(v[limite_esq:ip + 1])
        ie = max(i for i in range(limite_esq, ip + 1) if v[i] == base_esq)
        base_dir = min(v[ip:limite_dir + 1])
        id_ = min(i for i in range(ip, limite_dir + 1) if v[i] == base_dir)
        nivel_ini = base_esq + p['fracao'] * (v[ip] - base_esq)
        nivel_fim = base_dir + p['fracao'] * (v[ip] - base_dir)
        cortado_esq = k == 0 and v[ip] - base_esq < p['amplitude_min'] - 1e-9
        cortado_dir = k == len(picos) - 1 and v[ip] - base_dir < p['amplitude_min'] - 1e-9
        ini = None if cortado_esq else _cruzamento(pontos, ie, ip, nivel_ini, subindo=True)
        fim = None if cortado_dir else _cruzamento(pontos, ip, id_, nivel_fim, subindo=False)
        lados = [b for b, cortado in ((base_esq, cortado_esq), (base_dir, cortado_dir)) if not cortado]
        ciclo = {
            'numero': k + 1, 'pico_data': pontos[ip][0], 'pico_valor': v[ip],
            'base_antes': None if cortado_esq else base_esq, 'base_depois': None if cortado_dir else base_dir,
            'amplitude': v[ip] - max(lados) if lados else None,
            'inicio': None, 'inicio_entre': None, 'fim': None, 'fim_entre': None, 'duracao_dias': None, 'obs': [],
        }
        if cortado_esq:
            ciclo['obs'].append(f'começou antes do período consultado (a primeira imagem já marca {v[0]:.2f})'.replace('.', ','))
        elif ini:
            ciclo['inicio'], ciclo['inicio_entre'] = ini[0], (ini[1], ini[2])
            vao = (ini[2] - ini[1]).days
            if vao > p['vizinhanca']:
                ciclo['obs'].append(f'início: {vao} dias sem imagem entre {ini[1]:%d/%m} e {ini[2]:%d/%m}')
            if k == 0 and ie == 0 and v[0] - min(v) > p['amplitude_min'] / 2:
                ciclo['obs'].append(f'a primeira imagem do período já marca {v[0]:.2f}: a subida pode ter começado antes'
                                    .replace('.', ','))
        else:
            ciclo['obs'].append('início fora do período consultado')
        if cortado_dir:
            ciclo['obs'].append(f'não terminou dentro do período consultado (a última imagem marca {v[-1]:.2f})'.replace('.', ','))
        elif fim:
            ciclo['fim'], ciclo['fim_entre'] = fim[0], (fim[1], fim[2])
            vao = (fim[2] - fim[1]).days
            if vao > p['vizinhanca']:
                ciclo['obs'].append(f'fim: {vao} dias sem imagem entre {fim[1]:%d/%m} e {fim[2]:%d/%m}')
            if k == len(picos) - 1 and id_ == len(pontos) - 1 and v[-1] - min(v) > p['amplitude_min'] / 2:
                ciclo['obs'].append(f'a última imagem do período ainda marca {v[-1]:.2f}: a descida pode continuar depois'
                                    .replace('.', ','))
        else:
            ciclo['obs'].append('fim fora do período consultado')
        for a, b in ((ip - 1, ip), (ip, ip + 1)):
            vao = (pontos[b][0] - pontos[a][0]).days
            if vao > p['vizinhanca']:
                ciclo['obs'].append(f'pico: {vao} dias sem imagem entre {pontos[a][0]:%d/%m} e {pontos[b][0]:%d/%m}; '
                                    'o valor mais alto pode ter caído nesse intervalo')
        if ciclo['inicio'] and ciclo['fim']:
            ciclo['duracao_dias'] = (ciclo['fim'] - ciclo['inicio']).days
        saida['ciclos'].append(ciclo)
    # o que o período cortou: descida de um ciclo anterior no começo, subida de um ciclo novo no fim
    ate = picos[0] if picos else len(v) - 1
    vale = min(range(0, ate + 1), key=lambda i: (v[i], i))
    topo = max(range(0, vale + 1), key=lambda i: (v[i], -i))
    if v[topo] - v[vale] >= p['amplitude_min'] - 1e-9:
        saida['avisos'].append(f'o período começa com a curva em queda, de {v[topo]:.2f} em {pontos[topo][0]:%d/%m/%Y} a '
                               f'{v[vale]:.2f} em {pontos[vale][0]:%d/%m/%Y}: é o fim de um ciclo que começou antes dele'
                               .replace('.', ','))
    de = picos[-1] if picos else 0
    vale = max(range(de, len(v)), key=lambda i: (-v[i], i))
    topo = max(range(vale, len(v)), key=lambda i: (v[i], -i))
    if v[topo] - v[vale] >= p['amplitude_min'] - 1e-9:
        saida['avisos'].append(f'o período termina com um ciclo em aberto: subiu de {v[vale]:.2f} em {pontos[vale][0]:%d/%m/%Y} a '
                               f'{v[topo]:.2f} em {pontos[topo][0]:%d/%m/%Y} e a última imagem marca {v[-1]:.2f}'
                               .replace('.', ','))
    if not picos and not saida['avisos']:
        amplitude = max(v) - min(v)
        saida['avisos'].append(f'nenhum ciclo com amplitude de {p["amplitude_min"]:.2f} ou mais '
                               f'(o índice foi de {min(v):.2f} a {max(v):.2f}, amplitude {amplitude:.2f})'.replace('.', ','))
    return saida


def resumo_das_imagens(pontos, inicio, fim):
    """Quantas datas, o maior intervalo sem imagem (contando as bordas da janela) e o maior valor."""
    datas = [d for d, _ in pontos]
    marcos = [inicio] + datas + [fim]
    maior, de, ate = 0, None, None
    for a, b in zip(marcos, marcos[1:]):
        if (b - a).days > maior:
            maior, de, ate = (b - a).days, a, b
    topo = max(pontos, key=lambda x: (x[1], -x[0].toordinal()))
    return {'imagens': len(datas), 'maior_intervalo': maior, 'intervalo_de': de, 'intervalo_ate': ate,
            'maximo': topo[1], 'maximo_data': topo[0], 'primeira': datas[0], 'ultima': datas[-1]}


# ------------------------------------------------------------------ teste embutido
def _curva_de_teste(inicio, eventos, passo=5, piso=0.18):
    """Curva de forma conhecida: cada evento (dia_inicio, dia_pico, dia_fim, topo) é um trapézio sobre o piso."""
    pontos = []
    for dia in range(0, 365, passo):
        valor = piso
        for d0, dp, d1, topo in eventos:
            if d0 <= dia <= dp:
                valor = max(valor, piso + (topo - piso) * (dia - d0) / (dp - d0))
            elif dp < dia <= d1:
                valor = max(valor, piso + (topo - piso) * (d1 - dia) / (d1 - dp))
        pontos.append((inicio + timedelta(days=dia), round(valor, 4)))
    return pontos


def _autoteste():
    ini = date(2023, 7, 1)
    # um ciclo: sobe do dia 100 ao 180 (pico 0,82) e desce até o dia 260
    um = achar_ciclos(_curva_de_teste(ini, [(100, 180, 260, 0.82)]))
    assert len(um['ciclos']) == 1, um
    c = um['ciclos'][0]
    assert c['pico_data'] == ini + timedelta(days=180) and abs(c['pico_valor'] - 0.82) < 1e-9
    # nível = 0,18 + 0,3 × 0,64 = 0,372 -> dia 100 + 0,3 × 80 = 124 ; fim: dia 260 − 0,3 × 80 = 236
    assert abs((c['inicio'] - ini).days - 124) <= 1, (c['inicio'] - ini).days
    assert abs((c['fim'] - ini).days - 236) <= 1, (c['fim'] - ini).days
    assert abs(c['duracao_dias'] - 112) <= 2 and not c['obs'], c
    assert (c['inicio_entre'][1] - c['inicio_entre'][0]).days == 5

    # dois ciclos (safra e segunda safra) com vale entre eles
    dois = achar_ciclos(_curva_de_teste(ini, [(95, 150, 200, 0.85), (205, 250, 310, 0.70)]))
    assert [x['numero'] for x in dois['ciclos']] == [1, 2], dois['ciclos']
    assert dois['ciclos'][0]['pico_data'] == ini + timedelta(days=150)
    assert dois['ciclos'][1]['pico_data'] == ini + timedelta(days=250)
    assert dois['ciclos'][0]['fim'] <= dois['ciclos'][1]['inicio']

    # ondulação pequena não vira ciclo; queda isolada sai
    plano = [(ini + timedelta(days=d), 0.55 + (0.04 if (d // 10) % 2 else 0.0)) for d in range(0, 365, 10)]
    r = achar_ciclos(plano)
    assert not r['ciclos'] and 'nenhum ciclo' in r['avisos'][0]
    com_queda = _curva_de_teste(ini, [(100, 180, 260, 0.82)])
    i = next(k for k, (d, _) in enumerate(com_queda) if (d - ini).days == 170)
    com_queda[i] = (com_queda[i][0], 0.40)
    r = achar_ciclos(com_queda)
    assert len(r['tirados']) == 1 and r['tirados'][0][0] == ini + timedelta(days=170)
    assert len(r['ciclos']) == 1 and r['ciclos'][0]['pico_data'] == ini + timedelta(days=180)

    # colheita (cai e não volta na imagem seguinte) não é queda isolada
    colheita = [(ini + timedelta(days=d), x) for d, x in [(0, 0.2), (10, 0.5), (20, 0.79), (30, 0.63), (50, 0.38), (60, 0.41), (70, 0.42)]]
    assert not tirar_quedas(colheita, 0.10, 20)[1]
    # patamar com ondulação: dois topos iguais sem vale entre eles são um ciclo só, com o pico na primeira data
    patamar = _curva_de_teste(ini, [(100, 160, 300, 0.80)])
    patamar = [(d, 0.80 if 160 <= (d - ini).days <= 230 else x) for d, x in patamar]
    patamar = [(d, 0.77 if (d - ini).days == 195 else x) for d, x in patamar]
    r = achar_ciclos(patamar)
    assert len(r['ciclos']) == 1 and r['ciclos'][0]['pico_data'] == ini + timedelta(days=160), r['ciclos']

    # ciclo cortado pela janela: começa alto e termina alto
    cortado = achar_ciclos(_curva_de_teste(ini, [(-60, 20, 90, 0.80)]))
    assert len(cortado['ciclos']) == 1, cortado['ciclos']
    c = cortado['ciclos'][0]
    assert c['inicio'] is None and any('antes do período' in o for o in c['obs']), c
    assert c['fim'] is not None and c['base_antes'] is None and c['duracao_dias'] is None, c
    fim_alto = achar_ciclos(_curva_de_teste(ini, [(200, 330, 500, 0.80)]))
    assert len(fim_alto['ciclos']) == 1, fim_alto['ciclos']
    c = fim_alto['ciclos'][0]
    assert c['fim'] is None and any('não terminou' in o for o in c['obs']) and c['inicio'] is not None, c
    # só subindo até a borda, com uma ondulação no fim: não é pico
    sobe = [(ini + timedelta(days=d), round(0.18 + 0.32 * d / 360, 4)) for d in range(0, 365, 10)]
    sobe[-2] = (sobe[-2][0], sobe[-1][1] + 0.01)
    assert not achar_ciclos(sobe)['ciclos']

    # intervalo grande sem imagem em volta do início vira observação
    furado = [x for x in _curva_de_teste(ini, [(100, 180, 260, 0.82)]) if not 105 <= (x[0] - ini).days <= 150]
    r = achar_ciclos(furado)
    assert any('dias sem imagem' in o for o in r['ciclos'][0]['obs']), r['ciclos'][0]['obs']

    # imagens repetidas e poucas imagens
    assert juntar_mesmo_dia([(ini, 0.4), (ini, 0.6)]) == [(ini, 0.5)]
    assert 'não dá para achar ciclo' in achar_ciclos([(ini, 0.2), (ini + timedelta(days=30), 0.8)])['avisos'][0]
    res = resumo_das_imagens([(ini + timedelta(days=10), 0.3), (ini + timedelta(days=60), 0.7)], ini, ini + timedelta(days=70))
    assert (res['imagens'], res['maior_intervalo'], res['maximo']) == (2, 50, 0.7)
    try:
        achar_ciclos(plano, {'fracao': 0.9})
    except ParametroInvalido:
        pass
    else:
        raise AssertionError('devia recusar a fração 0,9')
    print('ciclos.py: autoteste ok (1 ciclo, 2 ciclos, sem ciclo, queda isolada, janela cortada, intervalo sem imagem)')


if __name__ == '__main__':
    _autoteste()
