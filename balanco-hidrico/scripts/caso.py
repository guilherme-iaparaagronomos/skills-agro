"""Monta o balanço a partir das tabelas lidas: as normais, a ETP de cada período,
o balanço do ano normal e o sequencial, e os avisos que acompanham cada um.

Nada aqui escolhe pelo usuário: a CAD, o método de ETP, de onde vem a chuva
normal e o armazenamento inicial chegam prontos da linha de comando.

Teste embutido: python scripts/caso.py
"""

import datetime
import math

import bh
import entrada
import etp
from entrada import MESES

ANO_DE_REFERENCIA = 2001        # ano sem 29 de fevereiro, para os dias e o fotoperíodo do ano normal
CADS_DO_PAINEL = (25, 50, 75, 100, 125, 150, 200, 300)
LIMITES = {
    'thornthwaite': 'usa só a temperatura média do período; feito para clima úmido e para o mês: em clima seco '
                    'costuma subestimar a ETP',
    'thornthwaite-tef': 'o mesmo Thornthwaite com a temperatura efetiva, 0,36 × (3 × máxima − mínima), proposta por '
                        'Camargo et al. (1999) para o método valer também em clima seco; pede mínima e máxima',
    'hargreaves': 'usa a mínima, a máxima e a radiação no topo da atmosfera; feito para clima seco: em clima úmido '
                  'costuma superestimar a ETP',
    'informada': 'a ETP veio na tabela do usuário (de estação ou de outro método); a skill não recalcula',
}


class ErroDeCaso(Exception):
    """Pedido que não fecha; a mensagem vai para o usuário como está."""


def _mes_de_referencia(mes):
    return datetime.date(ANO_DE_REFERENCIA, mes, 1), entrada.fim_do_mes(ANO_DE_REFERENCIA, mes)


# ------------------------------------------------------------------ normais
def normais(tab, anos=None, chuva=None):
    """As 12 normais de chuva e temperatura, com a origem de cada uma escrita por extenso.

    tab é a tabela mensal (médias dos anos completos) ou a tabela de 12 normais do usuário.
    chuva = 'referencia' usa a linha "normal:" (a média histórica que a ferramenta informa);
    chuva = 'periodo' usa a média dos anos da própria tabela.
    """
    if tab['tipo'] == 'normais':
        if chuva == 'referencia':
            raise ErroDeCaso('A tabela de 12 normais do usuário só tem uma chuva: --chuva referencia não se aplica.')
        n = entrada.normais_da_tabela(tab['registros'])
        n.update(origem_chuva='tabela de normais do usuário', origem_temperatura='tabela de normais do usuário',
                 chuva_referencia=None, chuva_periodo=n['chuva'], opcoes_de_chuva=['periodo'], escolha_chuva='periodo')
        return n
    if tab['tipo'] != 'mensal':
        raise ErroDeCaso('As normais saem da tabela mensal (ou de uma tabela de 12 normais), não da diária.')
    n = entrada.normais_do_mensal(tab['registros'], anos)
    faixa = f'{n["anos"][0]} a {n["anos"][-1]}' if len(n['anos']) > 1 else str(n['anos'][0])
    periodo = f'média de {len(n["anos"])} ano(s) completo(s) da tabela ({faixa})'
    referencia = tab['meta']['normal']
    n.update(chuva_periodo=n['chuva'], chuva_referencia=referencia, origem_temperatura=periodo,
             opcoes_de_chuva=(['referencia'] if referencia else []) + ['periodo'])
    if referencia and chuva is None:
        raise ErroDeCaso(
            'A tabela traz duas chuvas normais e a escolha é do usuário (--chuva): "referencia" é a média histórica '
            f'informada pela ferramenta ({_mm(sum(referencia))} mm por ano); "periodo" é a {periodo} '
            f'({_mm(sum(n["chuva_periodo"]))} mm por ano).')
    escolha = chuva or 'periodo'
    if escolha == 'referencia' and not referencia:
        raise ErroDeCaso('A tabela não traz a linha "normal:" com a média histórica da chuva: use --chuva periodo.')
    if escolha not in ('referencia', 'periodo'):
        raise ErroDeCaso('--chuva aceita "referencia" ou "periodo".')
    n['escolha_chuva'] = escolha
    n['chuva'] = list(referencia) if escolha == 'referencia' else n['chuva_periodo']
    n['origem_chuva'] = 'média histórica (1991–2020) informada pela ferramenta' if escolha == 'referencia' else periodo
    return n


def calor_das_normais(n):
    if n['tmed'] is None:
        raise ErroDeCaso('As normais não têm temperatura: sem ela não há índice de calor para Thornthwaite.')
    return etp.indice_de_calor(n['tmed'])


def metodos_do_caso(n=None, periodos=None):
    """Os métodos de ETP que os dados permitem."""
    alvo = periodos if periodos is not None else [{'tmed': t, 'tmin': a, 'tmax': b} for t, a, b in zip(
        n['tmed'] or [None] * 12, n['tmin'] or [None] * 12, n['tmax'] or [None] * 12)]
    media = all(p['tmed'] is not None for p in alvo)
    extremos = all(p['tmin'] is not None and p['tmax'] is not None for p in alvo)
    saida = etp.metodos_possiveis(media, extremos, n is not None and n['tmed'] is not None)
    informada = all(p.get('etp') is not None for p in periodos) if periodos is not None else n.get('etp') is not None
    return saida + (['informada'] if informada else [])


def _etp_do_periodo(metodo, latitude, p, calor):
    if metodo == 'informada':
        if p.get('etp') is None:
            raise ErroDeCaso('--etp informada pede a coluna de ETP em todos os períodos da tabela.')
        return p['etp']
    try:
        return etp.calcular(metodo, latitude, p['inicio'], p['fim'], p['tmed'], p['tmin'], p['tmax'], calor)
    except etp.ErroDeMetodo as erro:
        raise ErroDeCaso(str(erro))


def _linhas(periodos, balanco, rotulos):
    saida = []
    for p, linha, texto in zip(periodos, balanco['linhas'], rotulos):
        saida.append(dict(linha, rotulo=texto, inicio=p['inicio'], fim=p['fim'], dias=p['dias'], t=p['tmed'],
                          tmin=p['tmin'], tmax=p['tmax']))
    return saida


def _avisos_da_etp(metodo, periodos, o_que):
    avisos = []
    if metodo.startswith('thornthwaite'):
        t = [(etp.temperatura_efetiva(p['tmin'], p['tmax']) if metodo.endswith('tef') else p['tmed']) for p in periodos]
        quentes = sum(1 for v in t if v >= etp.T_QUENTE)
        if quentes:
            avisos.append(f'Em {quentes} {o_que} a temperatura usada passou de 26,5 °C: neles a ETP padrão sai do '
                          'polinômio de Willmott et al. (1985), não da equação de potência.')
    return avisos


# ------------------------------------------------------------------ ano normal
def periodos_do_ano_normal(n):
    periodos = []
    for mes in range(1, 13):
        inicio, fim = _mes_de_referencia(mes)
        periodos.append({'inicio': inicio, 'fim': fim, 'dias': (fim - inicio).days + 1, 'chuva': n['chuva'][mes - 1],
                         'tmed': n['tmed'][mes - 1] if n['tmed'] else None,
                         'tmin': n['tmin'][mes - 1] if n['tmin'] else None,
                         'tmax': n['tmax'][mes - 1] if n['tmax'] else None,
                         'etp': n['etp'][mes - 1] if n.get('etp') else None})
    return periodos


def ano_normal(n, metodo, latitude, cad):
    """Balanço hídrico climatológico normal, por mês."""
    periodos = periodos_do_ano_normal(n)
    if metodo != 'informada' and metodo not in metodos_do_caso(n):
        raise ErroDeCaso(f'O método "{metodo}" não roda com esta tabela. Os que rodam: '
                         + (', '.join(metodos_do_caso(n)) or 'nenhum (falta temperatura)') + '.')
    calor = calor_das_normais(n) if metodo.startswith('thornthwaite') else None
    etps = [_etp_do_periodo(metodo, latitude, p, calor) for p in periodos]
    try:
        balanco = bh.normal([p['chuva'] for p in periodos], etps, cad)
    except bh.ErroDeBalanco as erro:
        raise ErroDeCaso(str(erro))
    avisos = _avisos_da_etp(metodo, periodos, 'mês(es)') if metodo != 'informada' else []
    if n.get('escolha_chuva') == 'referencia' and n.get('anos'):
        avisos.append('A chuva normal é a média histórica de 1991 a 2020 e a temperatura é a média de '
                      f'{n["anos"][0]} a {n["anos"][-1]}: são períodos diferentes.')
    return {'tipo': 'normal', 'passo': 'mes', 'cad': float(cad), 'metodo': metodo, 'latitude': latitude, 'calor': calor,
            'linhas': _linhas(periodos, balanco, [MESES[k] for k in range(12)]), 'balanco': balanco, 'normais': n,
            'avisos': avisos}


def painel_da_cad(n, metodo, latitude, cads=CADS_DO_PAINEL):
    """O que muda no ano normal com a CAD: deficiência e excedente do ano e meses com deficiência."""
    saida = []
    for cad in cads:
        r = ano_normal(n, metodo, latitude, cad)
        s = r['balanco']['afericao']['somas']
        saida.append({'cad': cad, 'def': s['def'], 'exc': s['exc'], 'etr': s['etr'],
                      'meses_com_deficiencia': sum(1 for l in r['linhas'] if l['def'] >= 0.05)})
    return saida


# ------------------------------------------------------------------ sequencial
def rotulo_do_periodo(p, passo):
    if passo == 'mes':
        return f'{MESES[p["inicio"].month - 1]}/{p["inicio"]:%y}'
    return f'{p["inicio"]:%d}–{p["fim"]:%d}/{MESES[p["inicio"].month - 1]}/{p["inicio"]:%y}'


def armazenamento_do_ano_normal(n, metodo, latitude, cad, inicio):
    """O armazenamento do ano normal no fim do mês anterior à data de início."""
    r = ano_normal(n, metodo, latitude, cad)
    mes_anterior = 12 if inicio.month == 1 else inicio.month - 1
    return r['linhas'][mes_anterior - 1]['arm'], mes_anterior


def em_sequencia(periodos, passo, metodo, latitude, cad, arm_inicial, n=None):
    """Balanço sequencial. arm_inicial: 'cad', 'normal' ou o valor em mm."""
    if metodo != 'informada' and metodo not in metodos_do_caso(n, periodos):
        raise ErroDeCaso(f'O método "{metodo}" não roda com estes dados. Os que rodam: '
                         + (', '.join(metodos_do_caso(n, periodos)) or 'nenhum') + '. Thornthwaite pede também as '
                         'temperaturas normais do lugar (a tabela mensal ou a de normais).')
    calor = calor_das_normais(n) if metodo.startswith('thornthwaite') else None
    etps = [_etp_do_periodo(metodo, latitude, p, calor) for p in periodos]
    chuvas = [p['chuva'] for p in periodos]
    avisos = _avisos_da_etp(metodo, periodos, 'período(s)') if metodo != 'informada' else []
    texto = str(arm_inicial).strip().lower()
    if texto == 'cad':
        arm0, origem = float(cad), 'solo cheio (igual à CAD), como informado'
    elif texto == 'normal':
        if n is None:
            raise ErroDeCaso('--arm-inicial normal pede as normais do lugar (a tabela mensal ou a de normais).')
        arm0, mes = armazenamento_do_ano_normal(n, metodo, latitude, cad, periodos[0]['inicio'])
        origem = f'o do balanço do ano normal no fim de {MESES[mes - 1]} ({_mm(arm0)} mm)'
        if periodos[0]['inicio'].day != 1:
            avisos.append('A série não começa no dia 1º: o armazenamento inicial é o do ano normal no fim do mês '
                          'anterior, não o do dia exato.')
    else:
        try:
            arm0 = entrada.numero(texto)
        except entrada.ErroDeEntrada:
            arm0 = float('nan')
        if math.isnan(arm0):
            raise ErroDeCaso('--arm-inicial aceita "cad", "normal" ou o valor em mm.')
        origem = f'{_mm(arm0)} mm, como informado'
    try:
        balanco = bh.sequencial(chuvas, etps, cad, arm0)
        primeiro, no_fim = bh.depende_do_inicio(chuvas, etps, cad)
    except bh.ErroDeBalanco as erro:
        raise ErroDeCaso(str(erro))
    rotulos = [rotulo_do_periodo(p, passo) for p in periodos]
    if primeiro is None:
        dependencia = ('Partindo do solo cheio ou do solo vazio, o armazenamento ainda difere '
                       f'{_mm(abs(no_fim))} mm no último período: toda a série depende do armazenamento inicial.')
    elif primeiro == 0:
        dependencia = 'O resultado não depende do armazenamento inicial: o solo enche já no primeiro período.'
    else:
        dependencia = (f'Até {rotulos[primeiro - 1]} o resultado depende do armazenamento inicial; de {rotulos[primeiro]} '
                       'em diante, partir do solo cheio ou do solo vazio dá o mesmo armazenamento (diferença menor que 1 mm).')
    if metodo.startswith('thornthwaite') and passo == 'decendio':
        avisos.append('Thornthwaite foi feito para o mês; no decêndio é uma aproximação de uso corrente.')
    sem = sum(p['sem_dado'] for p in periodos)
    if sem:
        avisos.append(f'{sem} dia(s) sem dado de chuva entraram como zero, por decisão do usuário.')
    sem_t = sum(p['sem_temperatura'] for p in periodos)
    if sem_t and metodo != 'informada':
        avisos.append(f'{sem_t} dia(s) sem temperatura: a média do período saiu dos outros dias.')
    return {'tipo': 'sequencial', 'passo': passo, 'cad': float(cad), 'metodo': metodo, 'latitude': latitude,
            'calor': calor, 'linhas': _linhas(periodos, balanco, rotulos), 'balanco': balanco, 'normais': n,
            'origem_do_armazenamento': origem, 'dependencia': dependencia, 'avisos': avisos}


def mensal_contra_diaria(tab_mensal, periodos_mensais_do_diario):
    """Os mesmos meses nas duas tabelas: (meses comparados, soma na mensal, soma na diária). None sem mês em comum."""
    da_mensal = {(r['ano'], r['mes']): r['chuva'] for r in tab_mensal['registros'] if not math.isnan(r['chuva'])}
    comuns = [(p, da_mensal[(p['inicio'].year, p['inicio'].month)]) for p in periodos_mensais_do_diario
              if (p['inicio'].year, p['inicio'].month) in da_mensal]
    if not comuns:
        return None
    return len(comuns), sum(m for _, m in comuns), sum(p['chuva'] for p, _ in comuns)


def _mm(v, casas=1):
    return f'{v:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


if __name__ == '__main__':
    import os
    import tempfile

    import sintetico

    def perto(a, b, tol=1e-9):
        assert abs(a - b) <= tol, (a, b)

    def recusa(funcao, trecho):
        try:
            funcao()
            raise AssertionError('devia recusar')
        except ErroDeCaso as erro:
            assert trecho in str(erro), (trecho, str(erro))

    with tempfile.TemporaryDirectory() as pasta:
        def grava(nome, texto):
            caminho = os.path.join(pasta, nome)
            open(caminho, 'w', encoding='utf-8').write(texto)
            return caminho

        mensal = entrada.ler(grava('m.txt', sintetico.arquivo_mensal()))
        diario = entrada.ler(grava('d.txt', sintetico.arquivo_diario()))
        assert not entrada.conferir(mensal)[1] and not entrada.conferir(diario)[1]
        recusa(lambda: normais(mensal), 'duas chuvas normais')
        n_ref, n_per = normais(mensal, chuva='referencia'), normais(mensal, chuva='periodo')
        assert n_ref['chuva'] == list(sintetico.CHUVA) and n_ref['anos'] == list(range(2015, 2025))
        assert n_per['chuva'] != n_ref['chuva'] and n_per['tmed'] == n_ref['tmed'] and 'média de 10' in n_per['origem_chuva']
        assert len(normais(mensal, anos=(2018, 2020), chuva='periodo')['anos']) == 3
        assert metodos_do_caso(n_ref) == ['thornthwaite', 'thornthwaite-tef', 'hargreaves']
        lat = sintetico.LATITUDE
        for metodo in etp.METODOS:
            r = ano_normal(n_ref, metodo, lat, 100)
            a = r['balanco']['afericao']
            perto(a['residuo_p'], 0, 1e-8), perto(a['residuo_etp'], 0, 1e-8), perto(a['variacao_do_armazenamento'], 0, 1e-8)
            assert len(r['linhas']) == 12 and r['linhas'][6]['def'] > 0 and r['linhas'][0]['exc'] > 0
            assert 600 < a['somas']['etp'] < 2200 and r['linhas'][1]['dias'] == 28
        # a ETP de julho vem da conta que o módulo etp faz com as normais
        r = ano_normal(n_ref, 'thornthwaite', lat, 100)
        i, a_ = etp.indice_de_calor(n_ref['tmed'])
        perto(r['linhas'][6]['etp'], etp.calcular('thornthwaite', lat, datetime.date(2001, 7, 1), datetime.date(2001, 7, 31),
                                                tmed=n_ref['tmed'][6], calor=(i, a_)))
        painel = painel_da_cad(n_ref, 'thornthwaite', lat)
        assert [x['cad'] for x in painel] == list(CADS_DO_PAINEL)
        assert all(a['def'] > b['def'] and a['exc'] > b['exc'] for a, b in zip(painel, painel[1:]))
        perto(painel[0]['exc'] - painel[0]['def'], painel[-1]['exc'] - painel[-1]['def'], 1e-8)

        # sequencial por decêndio
        periodos, sobras = entrada.periodos_do_diario(diario['registros'])
        assert len(periodos) == 36 and sobras == 0
        s = em_sequencia(periodos, 'decendio', 'hargreaves', lat, 100, 'cad')
        a = s['balanco']['afericao']
        perto(a['residuo_p'], 0, 1e-8), perto(a['residuo_etp'], 0, 1e-8)
        perto(sum(l['p'] for l in s['linhas']), sum(d[1] for d in sintetico.diaria(datetime.date(2024, 7, 1),
                                                                                  datetime.date(2025, 6, 30))), 1e-6)
        assert s['linhas'][0]['rotulo'] == '01–10/jul/24' and 'solo cheio' in s['origem_do_armazenamento']
        assert 'depende do armazenamento inicial' in s['dependencia']
        t = em_sequencia(periodos, 'decendio', 'thornthwaite', lat, 100, 'normal', n_ref)
        arm_junho = ano_normal(n_ref, 'thornthwaite', lat, 100)['linhas'][5]['arm']
        perto(t['balanco']['arm_inicial'], arm_junho) and None
        assert 'fim de jun' in t['origem_do_armazenamento'] and any('feito para o mês' in x for x in t['avisos'])
        v = em_sequencia(periodos, 'decendio', 'hargreaves', lat, 100, '37,5')
        perto(v['balanco']['arm_inicial'], 37.5)
        recusa(lambda: em_sequencia(periodos, 'decendio', 'thornthwaite', lat, 100, 'cad'), 'temperaturas normais')
        recusa(lambda: em_sequencia(periodos, 'decendio', 'hargreaves', lat, 100, 'normal'), 'pede as normais')
        recusa(lambda: em_sequencia(periodos, 'decendio', 'hargreaves', lat, 100, 'cheio'), '"cad", "normal"')
        recusa(lambda: em_sequencia(periodos, 'decendio', 'hargreaves', lat, 100, '250'), 'entre 0 e a CAD')
        recusa(lambda: em_sequencia(periodos, 'decendio', 'informada', lat, 100, 'cad'), 'coluna de ETP')
        # sequencial por mês, direto da tabela mensal
        meses = entrada.periodos_do_mensal(mensal['registros'], (2020, 1), (2024, 12))
        sm = em_sequencia(meses, 'mes', 'thornthwaite-tef', lat, 75, 'normal', n_per)
        assert len(sm['linhas']) == 60 and sm['linhas'][0]['rotulo'] == 'jan/20'
        # os mesmos meses nas duas tabelas: aqui fecham, porque a mensal inventada é a soma da diária
        do_diario = entrada.periodos_do_diario(diario['registros'], 'mes')[0]
        quantos, soma_m, soma_d = mensal_contra_diaria(mensal, do_diario)
        assert quantos == 6 and abs(soma_m - soma_d) < 0.5

        # tabela de normais do usuário com ETP informada: reproduz a tabela publicada de Posse (GO), CAD 100
        posse = entrada.ler(grava('p.csv', 'mes;chuva;etp\n' + '\n'.join(f'{k + 1};{c};{e}' for k, (c, e) in enumerate(zip(
            [271, 215, 230, 119, 20, 9, 5, 12, 30, 123, 223, 280], [116, 97, 104, 88, 78, 63, 62, 90, 94, 109, 106, 106])))))
        np_ = normais(posse)
        assert metodos_do_caso(np_) == ['informada']
        rp = ano_normal(np_, 'informada', -14.1, 100)
        perto(rp['balanco']['afericao']['somas']['def'], 215, 1.5), perto(rp['balanco']['afericao']['somas']['exc'], 639, 1.5)
        recusa(lambda: ano_normal(np_, 'thornthwaite', -14.1, 100), 'não roda')
    print('caso OK')
