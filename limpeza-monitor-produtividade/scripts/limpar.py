"""Limpeza de dado denso: monitor de colheita e sensores embarcados.

Duas etapas, sempre nesta ordem:

  1. DIAGNÓSTICO (não remove nada): o que o arquivo tem e os números para escolher
     os parâmetros.
       python scripts/limpar.py --pontos colheita.csv --diagnostico

  2. LIMPEZA, depois de o usuário confirmar a coluna do valor e os parâmetros:
       python scripts/limpar.py --pontos colheita.csv --valor Prod_t_ha --unidade t/ha \\
           --perimetro talhao.geojson --nome "Talhão 12 · soja 25/26"

  Exemplo pronto, com erros plantados:  python scripts/limpar.py --demo

Entradas: CSV/TXT com colunas de coordenada, ou shapefile de pontos (.shp ou .zip).
Perímetro (opcional): GeoJSON, KML ou shapefile de polígonos.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

import numpy as np

import areas as mod_areas
import leitura
import limpeza
import saidas
from limpeza import num

TETO_DO_SHAPEFILE = 600000


def _opcional(texto, tipo=float):
    """'nenhum'/'nenhuma' vira False (desligar); número vira número."""
    if texto is None:
        return None
    if str(texto).strip().lower() in ('nenhum', 'nenhuma', 'nao', 'não', 'off'):
        return False
    return tipo(str(texto).replace(',', '.'))


def _zona(texto):
    if not texto:
        return None
    texto = texto.strip().upper()
    return int(texto.rstrip('NS')), not texto.endswith('N')


def argumentos():
    p = argparse.ArgumentParser(description='Limpeza de dado denso (monitor de colheita e sensores embarcados).')
    p.add_argument('--pontos', help='CSV/TXT, .shp ou .zip com os pontos brutos')
    p.add_argument('--perimetro', help='polígono(s) do talhão: GeoJSON, KML ou shapefile')
    p.add_argument('--diagnostico', action='store_true', help='só mostra o retrato do arquivo; não remove nada')
    p.add_argument('--demo', action='store_true', help='roda o exemplo com erros plantados')
    p.add_argument('--perfil', choices=sorted(limpeza.PERFIS), default='colheita')
    p.add_argument('--valor', help='coluna a limpar (produtividade, CEa, índice…)')
    p.add_argument('--unidade', default='', help='unidade do valor, só para os textos (t/ha, sc/ha, mS/m…)')
    p.add_argument('--nome', default='', help='título do relatório (talhão, cultura, safra)')
    p.add_argument('--x'), p.add_argument('--y')
    p.add_argument('--zona', help='zona UTM quando as coordenadas estão em metros sem .prj (ex.: 22S)')
    for papel in ('velocidade', 'umidade', 'largura', 'tempo', 'passada'):
        p.add_argument('--' + papel, help=f'coluna de {papel} (ou "nenhuma" para não usar)')
    p.add_argument('--minimo'), p.add_argument('--maximo')
    p.add_argument('--borda', type=float, help='tirar pontos a menos de N metros da divisa')
    p.add_argument('--vel-min'), p.add_argument('--vel-max')
    p.add_argument('--vel-faixa', help='faixa em fração da mediana, ex.: 0.5,1.5 (ou "nenhuma")')
    p.add_argument('--vel-variacao', help='fração de mudança entre pontos seguidos, ex.: 0.25')
    p.add_argument('--largura-min', help='fração da largura cheia, ex.: 0.9')
    p.add_argument('--umid-min'), p.add_argument('--umid-max')
    p.add_argument('--inicio', help='pontos a cortar no começo de cada passada (número ou "auto")')
    p.add_argument('--fim', help='pontos a cortar no fim de cada passada (número ou "auto")')
    p.add_argument('--passada-min', type=int)
    p.add_argument('--global', dest='global_metodo', choices=('mad', 'dp', 'iqr', 'pct', 'nenhum'))
    p.add_argument('--global-k', type=float)
    p.add_argument('--local', dest='local_metodo', choices=('pct', 'mad', 'nenhum'))
    p.add_argument('--local-limite', type=float), p.add_argument('--local-raio', type=float)
    p.add_argument('--local-viz', type=int)
    p.add_argument('--casas', type=int, default=2)
    p.add_argument('--saida', default='saida-limpeza')
    return p.parse_args()


def configuracao(a):
    cfg = dict(limpeza.PERFIS[a.perfil])
    for chave in ('minimo', 'maximo', 'vel_min', 'vel_max', 'vel_variacao', 'largura_min', 'umid_min', 'umid_max'):
        valor = _opcional(getattr(a, chave))
        if valor is not None:
            cfg[chave] = None if valor is False else valor
    if a.minimo is not None and cfg['minimo'] is not None:
        cfg['minimo_incluso'] = True  # mínimo dado pelo usuário: fica quem é igual ou maior
    if a.vel_faixa is not None:
        faixa = _opcional(a.vel_faixa, tipo=str)
        cfg['vel_faixa'] = None if faixa is False else tuple(float(v) for v in faixa.split(','))
    for chave in ('inicio', 'fim'):
        valor = getattr(a, chave)
        if valor is not None:
            cfg[chave] = 'auto' if valor.strip().lower() == 'auto' else int(valor)
    for chave in ('borda', 'passada_min', 'global_metodo', 'global_k', 'local_metodo', 'local_limite', 'local_raio',
                  'local_viz'):
        if getattr(a, chave) is not None:
            cfg[chave] = getattr(a, chave)
    return cfg


def preparar(a):
    """Lê os arquivos e devolve (tabela, papéis, vetores para a limpeza, avisos de leitura)."""
    tabela = leitura.ler_pontos(a.pontos, a.x, a.y)
    papeis = leitura.adivinhar(tabela)
    avisos = []
    for papel in ('velocidade', 'umidade', 'largura', 'tempo', 'passada'):
        pedido = getattr(a, papel)
        if pedido is None:
            continue
        if pedido.strip().lower() in ('nenhuma', 'nenhum'):
            papeis[papel] = None
        elif pedido in tabela['dados']:
            papeis[papel] = pedido
        else:
            raise SystemExit(f'coluna "{pedido}" não existe. Colunas: {", ".join(tabela["colunas"])}')
    if a.valor:
        if a.valor not in tabela['dados']:
            raise SystemExit(f'coluna "{a.valor}" não existe. Colunas: {", ".join(tabela["colunas"])}')
        papeis['valor'] = a.valor
        papeis.update({k: None for k, v in papeis.items() if k != 'valor' and v == a.valor})
    for papel in ('valor', 'velocidade', 'umidade', 'largura'):
        if papeis[papel] and papeis[papel] not in tabela['numericas']:
            raise SystemExit(f'a coluna "{papeis[papel]}" ({papel}) não é numérica')
    zona = _zona(a.zona) or tabela['zona']
    X, Y, z, sul = leitura.projetar(tabela['x'], tabela['y'], tabela['crs'], zona)
    d = {'x': X, 'y': Y, 'areas': None, 't': None, 'passada': None}
    for papel in ('valor', 'velocidade', 'umidade', 'largura'):
        d[papel] = tabela['dados'][papeis[papel]].astype(float) if papeis[papel] else None
    if papeis['tempo']:
        d['t'] = leitura.segundos(tabela['dados'][papeis['tempo']])
        if d['t'] is None:
            avisos.append(f'Não consegui ler a hora na coluna "{papeis["tempo"]}": ela não foi usada.')
            papeis['tempo'] = None
    if papeis['passada']:
        d['passada'] = tabela['dados'][papeis['passada']]
    if a.perimetro:
        lidas, crs_per, zona_per = mod_areas.ler_areas(a.perimetro)
        if crs_per == 'geo':
            if z is None:
                raise SystemExit('pontos em metros sem zona e perímetro em graus: informe --zona (ex.: 22S)')
            d['areas'], _, _ = mod_areas.para_utm(lidas, 'geo', (z, sul))
        else:
            if tabela['crs'] == 'geo' and not zona_per:
                raise SystemExit('perímetro em metros sem .prj: informe --zona (ex.: 22S)')
            d['areas'], _, _ = mod_areas.para_utm(lidas, 'utm', zona_per or (z or 22, True if sul is None else sul))
    tabela.update(zona_n=z, sul=sul)
    return tabela, papeis, d, avisos


def _para_json(o):
    if isinstance(o, dict):
        return {str(k): _para_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_para_json(v) for v in o]
    if isinstance(o, np.ndarray):
        return _para_json(o.tolist())
    if isinstance(o, (np.floating, float)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def _colunas_com_exemplo(tabela):
    linhas = []
    for nome in tabela['colunas']:
        vetor = tabela['dados'][nome]
        if nome in tabela['numericas']:
            ok = vetor[np.isfinite(vetor)]
            exemplo = (f'número · {format(float(ok.min()), ".7g")} a {format(float(ok.max()), ".7g")}'.replace('.', ',')
                       if len(ok) else 'número · vazia')
        else:
            exemplo = 'texto · ' + ', '.join(str(v) for v in vetor[:2])
        linhas.append(f'  - {nome}: {exemplo}')
    return linhas


def rodar_diagnostico(a, tabela, papeis, d, avisos, cfg, pasta):
    if not papeis['valor']:
        print('Não deu para adivinhar a coluna do valor. Colunas do arquivo:')
        print('\n'.join(_colunas_com_exemplo(tabela)))
        print('Pergunte ao usuário qual coluna limpar e rode de novo com --valor.')
        return 2
    diag = limpeza.diagnosticar(d, cfg)
    meta = {'titulo': a.nome or 'Diagnóstico', 'arquivo': tabela['origem'], 'coluna': papeis['valor'],
            'unidade': a.unidade, 'perfil': a.perfil, 'data': datetime.date.today().strftime('%d/%m/%Y'),
            'casas': a.casas}
    saidas.figura_do_diagnostico(pasta / 'diagnostico.png', d, diag, meta)
    (pasta / 'diagnostico.json').write_text(json.dumps(_para_json({'meta': meta, 'papeis': papeis, 'diagnostico': diag}),
                                                       ensure_ascii=False, indent=1), encoding='utf-8')
    e, c = diag['valor'], a.casas
    print(f'DIAGNÓSTICO — {tabela["origem"]} · {diag["pontos"]:,} pontos · nada foi removido'.replace(',', '.'))
    print('Colunas do arquivo:')
    print('\n'.join(_colunas_com_exemplo(tabela)))
    print('Palpite de cada coluna (CONFIRME COM O USUÁRIO, principalmente a do valor):')
    for papel, nome in papeis.items():
        print(f'  - {papel}: {nome or "não achei"}')
    print(f'Coordenadas: {"graus (longitude e latitude)" if tabela["crs"] == "geo" else "metros"}'
          + (f' · zona UTM {tabela["zona_n"]}{"S" if tabela["sul"] else "N"}' if tabela.get('zona_n') else ''))
    print(f'Valor ({papeis["valor"]}): mediana {num(e.get("mediana"), c)}, média {num(e.get("media"), c)}, '
          f'CV {num(e.get("cv"), 1)}%, de {num(e.get("min"), c)} a {num(e.get("max"), c)}; '
          f'1% abaixo de {num(e.get("p1"), c)} e 1% acima de {num(e.get("p99"), c)}')
    print(f'  sem valor: {diag["valor_ausente"]} · zero ou negativo: {diag["valor_zero_ou_negativo"]}')
    print(f'Posição: {diag["posicao_invalida"]} sem coordenada · {diag["duplicados"]} repetidos'
          + ('' if diag['fora_do_perimetro'] is None else f' · {diag["fora_do_perimetro"]} fora do perímetro'))
    ps = diag['passadas']
    print(f'Passadas: {ps.get("passadas")} detectadas · {num(ps.get("pontos_por_passada"), 0)} pontos na passada típica · '
          f'passo de {num(ps.get("passo_m"), 1)} m'
          + (f' · um ponto a cada {num(ps["intervalo_s"], 1)} s' if ps.get('intervalo_s') else ' · sem relógio'))
    rampa = diag['rampa']
    if rampa['entrada'] is None:
        print('Entrada e saída das passadas: sem passadas longas o bastante para medir.')
    else:
        print(f'Entrada das passadas (valor ÷ trecho vizinho, do 1º ponto em diante): '
              f'{" ".join(num(v, 2) for v in rampa["entrada"][:8])}')
        print(f'Saída das passadas (do último ponto para trás): {" ".join(num(v, 2) for v in rampa["saida"][:8])}')
        print(f'  SUGESTÃO: cortar {rampa["sugestao_inicio"]} ponto(s) no começo e {rampa["sugestao_fim"]} no fim '
              f'(até o valor se firmar em 90% do trecho vizinho)')
    vel = diag['velocidade']
    if vel:
        print(f'Velocidade ({papeis["velocidade"]}): mediana {num(vel.get("mediana"))}'
              + (f' · parece estar em {vel["unidade_provavel"]}' if vel.get('unidade_provavel') else '')
              + f' · {num(vel["pct_fora_de_50_a_150_da_mediana"], 1)}% dos pontos fora de 50% a 150% da mediana · '
              f'{num(vel["pct_variacao_acima_de_25"], 1)}% com mudança acima de 25% de um ponto para o seguinte')
    larg = diag['largura']
    if larg and larg['cheia']:
        print(f'Largura ({papeis["largura"]}): cheia = {num(larg["cheia"])} · {num(larg["pct_abaixo_de_90"], 1)}% dos '
              f'pontos abaixo de 90% dela'
              + (f' · mediana do valor nesses pontos: {num(larg["mediana_do_valor_na_parcial"], c)} '
                 f'(na largura cheia: {num(larg["mediana_do_valor_na_cheia"], c)})'
                 if larg['mediana_do_valor_na_parcial'] is not None else ''))
    if diag['umidade']:
        u = diag['umidade']
        print(f'Umidade ({papeis["umidade"]}): mediana {num(u.get("mediana"), 1)}, de {num(u.get("p1"), 1)} (1%) a '
              f'{num(u.get("p99"), 1)} (99%)')
    previsto = diag.get('limites_globais_previstos')
    if previsto:
        print(f'Limites do conjunto com o padrão do perfil (aproximados; a limpeza recalcula depois dos outros filtros): '
              f'{num(previsto["inferior"], c)} a {num(previsto["superior"], c)}')
    print(f'Raio do filtro local (automático): {num(diag["raio_automatico_m"], 0)} m')
    for linha in diag['o_que_falta'] + avisos:
        print('ATENÇÃO:', linha)
    print(f'Figura: {pasta / "diagnostico.png"} · números: {pasta / "diagnostico.json"}')
    return 0


def rodar_limpeza(a, tabela, papeis, d, avisos, cfg, pasta):
    if not a.valor:
        raise SystemExit('informe --valor com a coluna que o usuário confirmou (rode antes com --diagnostico)')
    r = limpeza.limpar(d, cfg)
    r['alertas'] = avisos + r['alertas']
    ficou = r['motivo'] == 0
    nomes = np.array([''] + [e['nome'] for e in r['etapas']], dtype=object)
    arquivos = ['pontos-limpos.csv', 'pontos-removidos.csv', 'relatorio-limpeza.pdf', 'relatorio-limpeza.png',
                'relatorio.json']
    saidas.gravar_csv(pasta / 'pontos-limpos.csv', tabela, ficou)
    saidas.gravar_csv(pasta / 'pontos-removidos.csv', tabela, ~ficou, {'motivo': nomes[r['motivo']]})
    if r['mantidos'] and r['mantidos'] <= TETO_DO_SHAPEFILE:
        if tabela['crs'] == 'geo':
            prj = saidas.PRJ_WGS84
        else:
            prj = saidas.prj_utm(tabela['zona_n'], tabela['sul']) if tabela.get('zona_n') else None
        saidas.gravar_shapefile_zip(pasta / 'pontos-limpos.zip', tabela['x'][ficou], tabela['y'][ficou],
                                    {n: np.asarray(tabela['dados'][n])[ficou] for n in tabela['colunas']}, prj)
        arquivos.insert(1, 'pontos-limpos.zip')
    meta = {'titulo': a.nome or 'Limpeza de dados', 'arquivo': tabela['origem'], 'coluna': papeis['valor'],
            'unidade': a.unidade, 'perfil': a.perfil, 'data': datetime.date.today().strftime('%d/%m/%Y'),
            'casas': a.casas}
    saidas.relatorio(pasta / 'relatorio-limpeza.pdf', pasta / 'relatorio-limpeza.png', d, r, meta)
    resumo = {'meta': meta, 'papeis': papeis, 'parametros': cfg, 'pontos': r['pontos'], 'mantidos': r['mantidos'],
              'removidos': r['removidos'], 'etapas': r['etapas'], 'antes': r['antes'], 'depois': r['depois'],
              'alertas': r['alertas'], 'info': {k: v for k, v in r['info'].items()}}
    (pasta / 'relatorio.json').write_text(json.dumps(_para_json(resumo), ensure_ascii=False, indent=1), encoding='utf-8')

    n, c = r['pontos'], a.casas
    print(f'LIMPEZA — {tabela["origem"]} · {papeis["valor"]}{" (" + a.unidade + ")" if a.unidade else ""} · '
          f'perfil {a.perfil}')
    print(f'Pontos lidos: {num(n, 0)} · mantidos: {num(r["mantidos"], 0)} ({num(100 * r["mantidos"] / n, 1)}%) · '
          f'removidos: {num(r["removidos"], 0)} ({num(100 * r["removidos"] / n, 1)}%)')
    print('Filtros, na ordem:')
    for k, e in enumerate(r['etapas'], 1):
        if e['pulado']:
            print(f'  {k:>2}. {e["nome"]} — não rodou: {e["pulado"]}')
        else:
            print(f'  {k:>2}. {e["nome"]} — {e["removidos"]} ({num(100 * e["removidos"] / n, 1)}%) — {e["parametro"]}')
    antes, depois = r['antes'], r['depois']
    print(f'Antes → depois: média {num(antes.get("media"), c)} → {num(depois.get("media"), c)} · mediana '
          f'{num(antes.get("mediana"), c)} → {num(depois.get("mediana"), c)} · CV {num(antes.get("cv"), 1)}% → '
          f'{num(depois.get("cv"), 1)}% · mínimo {num(antes.get("min"), c)} → {num(depois.get("min"), c)} · máximo '
          f'{num(antes.get("max"), c)} → {num(depois.get("max"), c)}')
    for aviso in r['alertas']:
        print('AVISO:', aviso)
    if not r['alertas']:
        print('Nenhum aviso.')
    print(f'Arquivos em {pasta}: ' + ', '.join(arquivos))
    return r


def demo(a, pasta):
    import sintetico

    exemplo = sintetico.talhao()
    sintetico.gravar_csv(pasta / 'exemplo-colheita.csv', exemplo)
    sintetico.gravar_perimetro(pasta / 'exemplo-perimetro.geojson', exemplo)
    a.pontos, a.perimetro = str(pasta / 'exemplo-colheita.csv'), str(pasta / 'exemplo-perimetro.geojson')
    a.unidade, a.nome = 't/ha', a.nome or 'Talhão de exemplo · colheita simulada'
    cfg = configuracao(a)
    tabela, papeis, d, avisos = preparar(a)
    rodar_diagnostico(a, tabela, papeis, d, avisos, cfg, pasta)
    print()
    a.valor = papeis['valor']
    r = rodar_limpeza(a, tabela, papeis, d, avisos, cfg, pasta)
    saiu, verdade = r['motivo'] > 0, exemplo['verdade']
    print()
    print('Este exemplo é uma colheita SIMULADA, com erros plantados de propósito em pontos sabidos.')
    print(f'A limpeza tirou {num(100 * saiu[verdade != ""].mean(), 1)}% dos erros plantados e '
          f'{num(100 * saiu[verdade == ""].mean(), 2)}% dos pontos bons. Dado de máquina de verdade é mais sujo: '
          f'olhe sempre o mapa do que saiu.')
    return 0


def principal():
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    a = argumentos()
    pasta = Path(a.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    if a.demo:
        return demo(a, pasta)
    if not a.pontos:
        raise SystemExit('informe --pontos (ou rode com --demo)')
    cfg = configuracao(a)
    try:
        tabela, papeis, d, avisos = preparar(a)
    except ValueError as erro:
        raise SystemExit(str(erro))
    if a.diagnostico:
        return rodar_diagnostico(a, tabela, papeis, d, avisos, cfg, pasta)
    rodar_limpeza(a, tabela, papeis, d, avisos, cfg, pasta)
    return 0


if __name__ == '__main__':
    sys.exit(principal())
