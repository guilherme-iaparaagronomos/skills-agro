"""O diagnóstico e a limpeza, em cima dos vetores já lidos.

  PERFIS            os dois conjuntos de parâmetros de partida (colheita e sensor)
  diagnosticar()    o que o arquivo mostra ANTES de qualquer filtro
  limpar()          os filtros em ordem, cada um com o parâmetro e a contagem

A limpeza só REMOVE pontos: não corrige, não desloca e não interpola valor.
Cada ponto removido fica com o motivo (o primeiro filtro que o tirou).

Teste embutido: python scripts/limpeza.py   (mede a limpeza no talhão sintético)
"""

import numpy as np
from scipy.spatial import cKDTree

import filtros
from areas import dentro, distancia_da_borda

PERFIS = {
    # monitor de colheita: tem passada, velocidade e enchimento da máquina
    'colheita': {'minimo': 0.0, 'minimo_incluso': False, 'maximo': None, 'borda': 0.0,
                 'vel_min': None, 'vel_max': None, 'vel_faixa': (0.5, 1.5), 'vel_variacao': None,
                 'largura_min': None, 'umid_min': None, 'umid_max': None,
                 'inicio': 'auto', 'fim': 'auto', 'passada_min': 5,
                 'global_metodo': 'mad', 'global_k': None,
                 'local_metodo': 'pct', 'local_limite': 30.0, 'local_raio': None, 'local_viz': 4},
    # sensor embarcado (condutividade elétrica, sensor de dossel, altimetria): sem enchimento
    'sensor': {'minimo': None, 'minimo_incluso': True, 'maximo': None, 'borda': 0.0,
               'vel_min': None, 'vel_max': None, 'vel_faixa': None, 'vel_variacao': None,
               'largura_min': None, 'umid_min': None, 'umid_max': None,
               'inicio': 0, 'fim': 0, 'passada_min': 0,
               'global_metodo': 'mad', 'global_k': None,
               'local_metodo': 'mad', 'local_limite': 4.0, 'local_raio': None, 'local_viz': 4},
}
NOME_GLOBAL = {'mad': 'mediana ± {k:g} desvios robustos', 'dp': 'média ± {k:g} desvios-padrão',
               'iqr': 'quartis ± {k:g} × distância interquartil', 'pct': 'mediana ± {k:g}%'}
TETO_DA_RAMPA = 12


def num(v, casas=2):
    if v is None or not np.isfinite(v):
        return '—'
    texto = f'{float(v):,.{casas}f}'
    return texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def estatisticas(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if not len(v):
        return {'n': 0}
    media, dp = float(v.mean()), float(v.std(ddof=1)) if len(v) > 1 else 0.0
    return {'n': int(len(v)), 'media': media, 'mediana': float(np.median(v)), 'dp': dp,
            'cv': 100 * dp / abs(media) if media else None, 'min': float(v.min()), 'max': float(v.max()),
            'p1': float(np.percentile(v, 1)), 'p5': float(np.percentile(v, 5)),
            'p95': float(np.percentile(v, 95)), 'p99': float(np.percentile(v, 99))}


def _posicao_ruim(d):
    x, y = d['x'], d['y']
    ruim = ~np.isfinite(x) | ~np.isfinite(y)
    bons = np.flatnonzero(~ruim)
    repetido = np.zeros(len(x), dtype=bool)
    repetido[bons] = filtros.duplicados(x[bons], y[bons])
    return ruim, repetido


def _fora(d):
    if not d.get('areas'):
        return None
    xy = np.column_stack([d['x'], d['y']])
    ok = np.isfinite(xy).all(axis=1)
    em_alguma = np.zeros(len(xy), dtype=bool)
    for a in d['areas']:
        em_alguma[ok] |= dentro(a['aneis'], xy[ok])
    return ~em_alguma


def _passadas(d, vivo):
    """Passadas sobre os pontos vivos (ordem do arquivo). Devolve vetores do tamanho total."""
    i = np.flatnonzero(vivo)
    n = len(d['x'])
    ids = np.full(n, -1)
    ini, fim, tam = np.zeros(n, int), np.zeros(n, int), np.zeros(n, int)
    t = d['t'][i] if d.get('t') is not None else None
    coluna = d['passada'][i] if d.get('passada') is not None else None
    ids_vivos, info = filtros.passadas(d['x'][i], d['y'][i], t, coluna)
    ids[i] = ids_vivos
    ini[i], fim[i] = filtros.posicao_na_passada(ids_vivos)
    tam[i] = ini[i] + fim[i] + 1
    info['pontos_por_passada'] = float(np.median(tam[i][ini[i] == 0])) if len(i) else None
    return ids, ini, fim, tam, info


def _velocidade_gps(d, ids):
    """Velocidade em m/s pela posição e pelo relógio, dentro de cada passada."""
    if d.get('t') is None:
        return None
    passo = np.hypot(np.diff(d['x']), np.diff(d['y']))
    dt = np.diff(d['t'])
    v = np.full(len(d['x']), np.nan)
    ok = (ids[1:] == ids[:-1]) & (ids[1:] >= 0) & (dt > 0)
    v[1:][ok] = passo[ok] / dt[ok]
    return v


def _unidade_da_velocidade(coluna, gps):
    if coluna is None or gps is None:
        return None
    ok = np.isfinite(coluna) & np.isfinite(gps) & (gps > 0.2)
    if ok.sum() < 30:
        return None
    razao = float(np.median(coluna[ok]) / np.median(gps[ok]))
    for nome, alvo in (('m/s', 1.0), ('km/h', 3.6), ('mph', 2.237)):
        if 0.85 * alvo <= razao <= 1.15 * alvo:
            return nome
    return None


def diagnosticar(d, cfg):
    """O retrato do arquivo antes da limpeza: o que tem, o que falta e os números que ajudam a
    escolher os parâmetros. Não remove nada."""
    n = len(d['x'])
    ruim, repetido = _posicao_ruim(d)
    fora = _fora(d)
    vivo = ~ruim & ~repetido & (~fora if fora is not None else True)
    ids, ini, fim, tam, info = _passadas(d, vivo)
    v = d['valor']
    r = {'pontos': n, 'posicao_invalida': int(ruim.sum()), 'duplicados': int(repetido.sum()),
         'fora_do_perimetro': None if fora is None else int((fora & ~ruim & ~repetido).sum()),
         'valor': estatisticas(v), 'valor_ausente': int((~np.isfinite(v)).sum()),
         'valor_zero_ou_negativo': int((np.isfinite(v) & (v <= 0)).sum()), 'passadas': info}
    entrada, saida, usadas = filtros.rampa(v[vivo], ids[vivo])
    r['rampa'] = {'passadas_usadas': usadas,
                  'entrada': None if entrada is None else [round(float(a), 3) for a in entrada],
                  'saida': None if saida is None else [round(float(a), 3) for a in saida],
                  'sugestao_inicio': filtros.sugerir_pontas(entrada), 'sugestao_fim': filtros.sugerir_pontas(saida)}
    vel = d.get('velocidade')
    gps = _velocidade_gps(d, ids)
    if vel is not None:
        e = estatisticas(vel[vivo])
        med = e.get('mediana')
        fora_da_faixa = (vel < 0.5 * med) | (vel > 1.5 * med) if med else np.zeros(n, bool)
        brusca = filtros.variacao_brusca(vel, ids, 0.25)
        r['velocidade'] = {**e, 'unidade_provavel': _unidade_da_velocidade(vel, gps),
                           'pct_fora_de_50_a_150_da_mediana': round(100 * float(fora_da_faixa[vivo].mean()), 2),
                           'pct_variacao_acima_de_25': round(100 * float(brusca[vivo].mean()), 2)}
    else:
        r['velocidade'] = None
        if gps is not None and np.isfinite(gps).any():
            r['velocidade_pelo_gps_ms'] = estatisticas(gps[vivo])
    larg = d.get('largura')
    if larg is not None:
        cheia = filtros.largura_cheia(larg[vivo])
        parcial = vivo & np.isfinite(larg) & (larg < 0.9 * cheia) if cheia else np.zeros(n, bool)
        inteira = vivo & ~parcial
        r['largura'] = {'cheia': cheia, 'pct_abaixo_de_90': round(100 * float(parcial[vivo].mean()), 2),
                        'mediana_do_valor_na_parcial': float(np.nanmedian(v[parcial])) if parcial.any() else None,
                        'mediana_do_valor_na_cheia': float(np.nanmedian(v[inteira])) if inteira.any() else None}
    else:
        r['largura'] = None
    r['umidade'] = estatisticas(d['umidade'][vivo]) if d.get('umidade') is not None else None
    xy = np.column_stack([d['x'][vivo], d['y'][vivo]])
    r['raio_automatico_m'] = filtros.raio_automatico(xy)
    bons = v[vivo & np.isfinite(v) & ((v > 0) if cfg.get('minimo') == 0 and not cfg.get('minimo_incluso') else True)]
    if len(bons) > 10 and cfg.get('global_metodo') not in (None, 'nenhum'):
        lo, hi = filtros.limites_globais(bons, cfg['global_metodo'], cfg.get('global_k'))
        r['limites_globais_previstos'] = {'metodo': cfg['global_metodo'], 'inferior': lo, 'superior': hi}
    falta = []
    if d.get('t') is None and d.get('passada') is None:
        falta.append('sem coluna de hora nem de passada: as passadas são separadas pela distância e pelo rumo')
    if vel is None:
        falta.append('sem coluna de velocidade: o filtro de velocidade não roda')
    if larg is None:
        falta.append('sem coluna de largura de trabalho: o filtro de largura parcial não roda')
    if not d.get('areas'):
        falta.append('sem perímetro: os filtros de ponto fora do talhão e de bordadura não rodam')
    r['o_que_falta'] = falta
    return r


def limpar(d, cfg):
    """Aplica os filtros em ordem. Devolve dict com `motivo` (0 = ficou; k = saiu na etapa k),
    `etapas` [{chave, nome, parametro, removidos, pulado}], `antes`, `depois`, `alertas` e `info`."""
    n = len(d['x'])
    v = d['valor']
    vivo = np.ones(n, dtype=bool)
    motivo = np.zeros(n, dtype=np.int16)
    etapas, alertas = [], []

    def aplica(chave, nome, parametro, mascara):
        tira = mascara & vivo
        etapas.append({'chave': chave, 'nome': nome, 'parametro': parametro, 'removidos': int(tira.sum()),
                       'pulado': None})
        motivo[tira] = len(etapas)
        vivo[tira] = False

    def pula(chave, nome, porque):
        etapas.append({'chave': chave, 'nome': nome, 'parametro': '', 'removidos': 0, 'pulado': porque})

    # 1 e 2: posição
    ruim, repetido = _posicao_ruim(d)
    aplica('posicao', 'Posição inválida ou repetida', 'sem coordenada, ou mesma coordenada de um ponto anterior',
           ruim | repetido)
    fora = _fora(d)
    if fora is None:
        pula('perimetro', 'Fora do perímetro', 'sem perímetro')
    else:
        aplica('perimetro', 'Fora do perímetro', 'ponto fora dos talhões enviados', fora)

    # as passadas saem dos pontos com posição boa; tudo o que vem depois usa essa divisão
    ids, ini, fim, tam, info = _passadas(d, vivo)
    entrada, saida, usadas = filtros.rampa(v[vivo], ids[vivo])
    info['passadas_na_rampa'] = usadas

    # 3: valor ausente ou impossível
    minimo, maximo = cfg.get('minimo'), cfg.get('maximo')
    texto = ['sem valor']
    if minimo is not None:
        texto.append(('abaixo de ' if cfg.get('minimo_incluso', True) else 'menor ou igual a ') + num(minimo))
    if maximo is not None:
        texto.append('acima de ' + num(maximo))
    aplica('valor', 'Valor ausente ou impossível', '; '.join(texto),
           filtros.fora_da_faixa(v, minimo, maximo, cfg.get('minimo_incluso', True)))

    # 4: bordadura
    borda = cfg.get('borda') or 0
    if borda > 0 and d.get('areas'):
        xy = np.column_stack([d['x'], d['y']])
        perto = np.zeros(n, dtype=bool)
        i = np.flatnonzero(vivo)
        menor = np.full(len(i), np.inf)
        for a in d['areas']:
            menor = np.minimum(menor, distancia_da_borda(a['aneis'], xy[i]))
        perto[i] = menor < borda
        aplica('borda', 'Bordadura', f'a menos de {num(borda, 0)} m da divisa', perto)
    else:
        pula('borda', 'Bordadura', 'não pedida' if d.get('areas') else 'sem perímetro')

    # 5 e 6: velocidade
    vel = d.get('velocidade')
    if vel is None:
        pula('velocidade', 'Velocidade fora da faixa', 'sem coluna de velocidade')
        pula('aceleracao', 'Variação brusca de velocidade', 'sem coluna de velocidade')
    else:
        lo, hi, origem = cfg.get('vel_min'), cfg.get('vel_max'), ''
        if lo is None and hi is None and cfg.get('vel_faixa'):
            mediana = float(np.nanmedian(vel[vivo])) if vivo.any() else np.nan
            lo, hi = cfg['vel_faixa'][0] * mediana, cfg['vel_faixa'][1] * mediana
            origem = (f' ({num(100 * cfg["vel_faixa"][0], 0)}% a {num(100 * cfg["vel_faixa"][1], 0)}% da mediana, '
                      f'{num(mediana)})')
        if lo is None and hi is None:
            pula('velocidade', 'Velocidade fora da faixa', 'não pedida')
        else:
            faixa = ' e '.join(p for p in (f'abaixo de {num(lo)}' if lo is not None else '',
                                           f'acima de {num(hi)}' if hi is not None else '') if p)
            aplica('velocidade', 'Velocidade fora da faixa', faixa + origem, filtros.fora_da_faixa(vel, lo, hi))
        if cfg.get('vel_variacao'):
            aplica('aceleracao', 'Variação brusca de velocidade',
                   f'mudou mais de {num(100 * cfg["vel_variacao"], 0)}% de um ponto para o seguinte',
                   filtros.variacao_brusca(vel, ids, cfg['vel_variacao']))
        else:
            pula('aceleracao', 'Variação brusca de velocidade', 'não pedida')

    # 7: largura parcial
    larg = d.get('largura')
    if larg is None:
        pula('largura', 'Largura de trabalho parcial', 'sem coluna de largura')
    elif not cfg.get('largura_min'):
        pula('largura', 'Largura de trabalho parcial', 'não pedida')
    else:
        cheia = filtros.largura_cheia(larg[vivo])
        aplica('largura', 'Largura de trabalho parcial',
               f'abaixo de {num(100 * cfg["largura_min"], 0)}% da largura cheia ({num(cheia)})',
               np.isfinite(larg) & (larg < cfg['largura_min'] * (cheia or 0)))

    # 8: umidade
    umid = d.get('umidade')
    if umid is None:
        pula('umidade', 'Umidade fora da faixa', 'sem coluna de umidade')
    elif cfg.get('umid_min') is None and cfg.get('umid_max') is None:
        pula('umidade', 'Umidade fora da faixa', 'não pedida')
    else:
        faixa = ' e '.join(p for p in (f'abaixo de {num(cfg["umid_min"], 1)}' if cfg.get('umid_min') is not None else '',
                                       f'acima de {num(cfg["umid_max"], 1)}' if cfg.get('umid_max') is not None else '')
                           if p)
        aplica('umidade', 'Umidade fora da faixa', faixa,
               np.isfinite(umid) & filtros.fora_da_faixa(umid, cfg.get('umid_min'), cfg.get('umid_max')))

    # 9: pontas de passada (enchimento e esvaziamento da máquina)
    def pontas(pedido, curva, qual):
        if pedido != 'auto':
            return int(pedido or 0), ''
        sugerido = filtros.sugerir_pontas(curva)
        if sugerido is None:
            alertas.append(f'Não deu para medir o {qual} das passadas (poucas passadas longas): nenhum ponto foi '
                           f'cortado nessa ponta. Informe o número de pontos se quiser cortar.')
            return 0, ' (sem medida)'
        return min(sugerido, TETO_DA_RAMPA), ' (medido no arquivo)'

    k_ini, de_onde_ini = pontas(cfg.get('inicio'), entrada, 'começo')
    k_fim, de_onde_fim = pontas(cfg.get('fim'), saida, 'fim')
    info.update(inicio=k_ini, fim=k_fim, rampa_entrada=None if entrada is None else [float(a) for a in entrada],
                rampa_saida=None if saida is None else [float(a) for a in saida])
    if k_ini or k_fim:
        segundos = ''
        if info.get('intervalo_s'):
            segundos = f' (cerca de {num(k_ini * info["intervalo_s"], 0)} s e {num(k_fim * info["intervalo_s"], 0)} s)'
        aplica('pontas', 'Começo e fim de passada',
               f'{k_ini} ponto(s) no começo{de_onde_ini} e {k_fim} no fim{de_onde_fim}{segundos}',
               (ids >= 0) & ((ini < k_ini) | (fim < k_fim)))
    else:
        pula('pontas', 'Começo e fim de passada', 'nenhum ponto a cortar')

    # 10: passada curta
    if cfg.get('passada_min'):
        aplica('passada_curta', 'Passada curta', f'passada com menos de {cfg["passada_min"]} pontos',
               (ids >= 0) & (tam < cfg['passada_min']))
    else:
        pula('passada_curta', 'Passada curta', 'não pedida')

    # 11: limites do talhão inteiro
    metodo = cfg.get('global_metodo')
    if metodo in (None, 'nenhum') or vivo.sum() < 10:
        pula('global', 'Fora dos limites do conjunto', 'não pedido')
        info['limites_globais'] = None
    else:
        k = cfg.get('global_k') if cfg.get('global_k') is not None else filtros.PADRAO_K[metodo]
        lo, hi = filtros.limites_globais(v[vivo], metodo, k)
        info['limites_globais'] = (lo, hi)
        antes_do_global = vivo.copy()
        aplica('global', 'Fora dos limites do conjunto',
               f'{NOME_GLOBAL[metodo].format(k=k)}: fora de {num(lo)} a {num(hi)}', (v < lo) | (v > hi))
        # erro de máquina costuma ser espalhado; ponto removido cercado de removidos pode ser mancha real
        saiu_aqui = motivo == len(etapas)
        info['global_em_mancha'] = 0
        if saiu_aqui.sum() >= max(20, 0.005 * n):
            i = np.flatnonzero(antes_do_global)
            xy = np.column_stack([d['x'][i], d['y'][i]])
            _, viz = cKDTree(xy).query(xy[saiu_aqui[i]], k=min(9, len(i)))
            cercado = saiu_aqui[i][viz[:, 1:]].mean(axis=1) >= 0.5
            info['global_em_mancha'] = int(cercado.sum())
            if cercado.mean() > 0.4:
                alertas.append(
                    f'{int(cercado.sum())} dos {int(saiu_aqui.sum())} pontos tirados pelo limite do conjunto estão '
                    f'agrupados (a maioria dos vizinhos também saiu). Erro de máquina costuma ser espalhado: ponto '
                    f'agrupado pode ser mancha real da área ou uma passada inteira com problema. Veja o mapa do que '
                    f'saiu antes de aceitar; se for mancha real, afrouxe o limite do conjunto.')

    # 12: contra os vizinhos
    metodo = cfg.get('local_metodo')
    if metodo in (None, 'nenhum') or vivo.sum() < 10:
        pula('local', 'Diferente dos vizinhos', 'não pedido')
    else:
        i = np.flatnonzero(vivo)
        xy = np.column_stack([d['x'][i], d['y'][i]])
        raio = cfg.get('local_raio') or filtros.raio_automatico(xy)
        tira, sozinho, _ = filtros.filtro_local(xy, v[i], raio, cfg['local_limite'], metodo, cfg.get('local_viz', 4))
        mascara = np.zeros(n, dtype=bool)
        mascara[i] = tira
        info.update(local_raio=raio, sem_vizinhos=int(sozinho.sum()))
        regra = (f'mais de {num(cfg["local_limite"], 0)}% da mediana dos vizinhos' if metodo == 'pct'
                 else f'mais de {num(cfg["local_limite"], 1)} desvios robustos dos vizinhos')
        aplica('local', 'Diferente dos vizinhos', f'{regra}, num raio de {num(raio, 0)} m', mascara)
        if len(i) and sozinho.mean() > 0.05:
            alertas.append(f'{num(100 * sozinho.mean(), 1)}% dos pontos têm menos de {cfg.get("local_viz", 4)} vizinhos '
                           f'no raio de {num(raio, 0)} m e não foram julgados pelo filtro local: aumente o raio.')

    antes, depois = estatisticas(v), estatisticas(v[vivo])
    removidos = n - int(vivo.sum())
    if n and removidos / n > 0.35:
        alertas.append(f'A limpeza tirou {num(100 * removidos / n, 1)}% dos pontos. É muito: confira os parâmetros e a '
                       f'coluna do valor antes de usar o resultado.')
    for e in etapas:
        if e['chave'] in ('global', 'local') and n and e['removidos'] / n > 0.10:
            alertas.append(f'O filtro "{e["nome"]}" tirou {num(100 * e["removidos"] / n, 1)}% dos pontos: o limite '
                           f'está apertado para este dado.')
    if d.get('t') is None and d.get('passada') is None:
        alertas.append('Sem coluna de hora nem de passada: as passadas foram separadas só pela distância e pelo rumo.')
    return {'motivo': motivo, 'etapas': etapas, 'antes': antes, 'depois': depois, 'alertas': alertas, 'info': info,
            'pontos': n, 'mantidos': int(vivo.sum()), 'removidos': removidos, 'passada': ids}


if __name__ == '__main__':
    import sintetico

    ex = sintetico.talhao()
    c = ex['colunas']
    dados = {'x': ex['x'], 'y': ex['y'], 'valor': c['Prod_t_ha'].astype(float), 'velocidade': c['Veloc_kmh'],
             'umidade': c['Umidade'], 'largura': c['Largura_m'],
             't': np.array([int(h[:2]) * 3600 + int(h[3:5]) * 60 + int(h[6:]) for h in c['Hora']], dtype=float),
             'passada': None, 'areas': None}
    import areas as _areas
    per, zona, sul = _areas.para_utm([{'nome': 'Exemplo', 'aneis': [ex['perimetro']]}], 'geo')
    dados['areas'] = per

    diag = diagnosticar(dados, PERFIS['colheita'])
    assert diag['duplicados'] == 12 and diag['fora_do_perimetro'] == 25, diag
    assert diag['passadas']['passadas'] == 46 and diag['passadas']['intervalo_s'] == 1.0, diag['passadas']
    assert diag['rampa']['sugestao_inicio'] == 4 and diag['rampa']['sugestao_fim'] == 2, diag['rampa']
    assert diag['velocidade']['unidade_provavel'] == 'km/h' and diag['largura']['cheia'] == 9.0
    assert diag['largura']['mediana_do_valor_na_parcial'] < 0.6 * diag['largura']['mediana_do_valor_na_cheia']

    r = limpar(dados, PERFIS['colheita'])
    saiu = r['motivo'] > 0
    verdade = ex['verdade']
    limpos = verdade == ''
    acerto = {k: float(saiu[verdade == k].mean()) for k in sorted(set(verdade)) if k}
    falso = float(saiu[limpos].mean())
    print('removidos por classe de erro plantado:', {k: round(a, 3) for k, a in acerto.items()})
    print(f'ponto bom removido: {100 * falso:.2f}% · total removido: {100 * saiu.mean():.2f}%')
    for e in r['etapas']:
        print(f'  {e["nome"]:<32} {e["removidos"]:>6}  {e["pulado"] or e["parametro"]}')
    for classe in ('duplicado', 'fora', 'zero', 'pico', 'rampa', 'lenta', 'largura'):
        assert acerto[classe] >= 0.95, (classe, acerto[classe])
    assert acerto['local'] >= 0.90, acerto['local']
    assert falso <= 0.03, falso
    media_certa = float(c['Prod_t_ha'][limpos].mean())
    assert r['depois']['cv'] < r['antes']['cv'] and abs(r['depois']['media'] - media_certa) < 0.03, (r['depois'], media_certa)
    # a passada inteira com meia plataforma saiu pelo limite do conjunto, agrupada: o aviso tem de aparecer
    assert r['info']['global_em_mancha'] > 200 and any('agrupados' in a for a in r['alertas']), r['alertas']
    # com o filtro de largura pedido, a passada sai pelo motivo certo e o aviso some
    r3 = limpar(dados, {**PERFIS['colheita'], 'largura_min': 0.9})
    por_chave = {e['chave']: e['removidos'] for e in r3['etapas']}
    falso3 = float((r3['motivo'] > 0)[limpos].mean())
    print(f'com --largura-min 0.9: largura {por_chave["largura"]}, global {por_chave["global"]}, '
          f'agrupados {r3["info"]["global_em_mancha"]}, ponto bom removido {100 * falso3:.2f}%, alertas {len(r3["alertas"])}')
    assert por_chave['largura'] >= 330 and falso3 <= 0.03

    # perfil de sensor, sem velocidade, sem hora e sem perímetro: roda e explica o que pulou
    sensor = {'x': ex['x'], 'y': ex['y'], 'valor': c['Prod_t_ha'].astype(float), 'areas': None}
    r2 = limpar(sensor, PERFIS['sensor'])
    pulados = {e['chave'] for e in r2['etapas'] if e['pulado']}
    assert {'perimetro', 'borda', 'velocidade', 'largura', 'umidade', 'pontas', 'passada_curta'} <= pulados, pulados
    assert r2['removidos'] > 100 and any('hora' in a for a in r2['alertas'])
    assert diagnosticar(sensor, PERFIS['sensor'])['o_que_falta']
    print('limpeza OK')
