"""Monta o histórico de cada talhão a partir das safras lidas: emenda as janelas
numa série só, acha os ciclos e põe cada safra lado a lado, com a chuva.

Só descreve. Não compara safra "melhor" e "pior", não estima produtividade e
não diz a cultura: o satélite mostra o verde, não o que foi plantado.

Teste embutido: python scripts/historico.py
"""

from datetime import date, timedelta

import ciclos as C
import leitura as L

EMENDA_DIAS = 20      # janelas separadas por até 20 dias são lidas como uma série só


def trechos(safras):
    """Agrupa as safras em trechos de janelas emendadas."""
    grupos = []
    for s in safras:
        if grupos and (s['inicio'] - grupos[-1][-1]['fim']).days <= EMENDA_DIAS:
            grupos[-1].append(s)
        else:
            grupos.append([s])
    return grupos


def _safra_da_data(safras, d):
    for s in safras:
        if s['inicio'] <= d <= s['fim']:
            return s['rotulo']
    return min(safras, key=lambda s: min(abs((d - s['inicio']).days), abs((d - s['fim']).days)))['rotulo']


def _chuva(s, abaixo_pct):
    c, n, v = s['chuva'], s['normal'], s['veranicos']
    total = n['total_mm'] if n else (c['total_mm'] if c else None)
    dif = n['dif_pct'] if n else None
    maior = max(v['lista'], key=lambda x: x['dias']) if v and v['lista'] else None
    return {
        'chuva_mm': total, 'normal_mm': n['normal_mm'] if n else None, 'dif_pct': dif,
        'abaixo': dif is not None and dif <= -abs(abaixo_pct),
        'dias_chuva': c['dias_chuva'] if c else None, 'sem_dado': c['sem_dado'] if c else 0,
        'veranicos': v['n'] if v else None, 'regua_veranico': v['regua'] if v else None,
        'maior_veranico': maior,
    }


def montar(safras, parametros=None, abaixo_pct=20):
    """Devolve o histórico: {'indice', 'parametros', 'abaixo_pct', 'safras', 'talhoes', 'avisos'}."""
    p = C.conferir_parametros({**C.PADRAO, **(parametros or {})})
    saida = {
        'indice': safras[0]['indice'], 'parametros': p, 'abaixo_pct': abs(abaixo_pct), 'avisos': [],
        'safras': [{'rotulo': s['rotulo'], 'inicio': s['inicio'], 'fim': s['fim'], 'dias': s['dias'], 'origem': s['origem'],
                    'periodo_informado': s['periodo_informado'], 'avisos': list(s['avisos']), **_chuva(s, abaixo_pct)}
                   for s in safras],
        'talhoes': {},
    }
    grupos = trechos(safras)
    if len(grupos) > 1:
        saida['avisos'].append(
            f'as janelas não estão emendadas: {len(grupos)} trechos separados. Ciclo que atravessa o intervalo entre '
            'dois trechos sai cortado. Para o calendário completo, consulte o ano agrícola inteiro de cada safra.')
    regras = {s['regua_veranico'] for s in saida['safras'] if s['regua_veranico']}
    if len(regras) > 1:
        saida['avisos'].append('as safras foram consultadas com réguas de veranico diferentes: ' + '; '.join(sorted(regras)))
    for nome in L.talhoes_de(safras):
        t = {'ciclos': [], 'por_safra': [], 'avisos': [], 'serie': [], 'tirados': []}
        for grupo in grupos:
            pontos = [pt for s in grupo for pt in s['curvas'].get(nome, [])]
            if not pontos:
                continue
            r = C.achar_ciclos(pontos, p)
            t['serie'].extend(r['pontos'])
            t['tirados'].extend(r['tirados'])
            for a in r['avisos']:
                t['avisos'].append(a if len(grupos) == 1 else f'{grupo[0]["rotulo"]} a {grupo[-1]["rotulo"]}: {a}')
            for c in r['ciclos']:
                c['safra'] = _safra_da_data(grupo, c['pico_data'])
                t['ciclos'].append(c)
        for k, c in enumerate(t['ciclos'], 1):
            c['numero'] = k
        for s in safras:
            pontos = C.juntar_mesmo_dia(s['curvas'].get(nome, []))
            if not pontos:
                t['por_safra'].append({'safra': s['rotulo'], 'imagens': 0})
                continue
            resumo = C.resumo_das_imagens(pontos, s['inicio'], s['fim'])
            resumo.update(safra=s['rotulo'], ciclos=sum(1 for c in t['ciclos'] if c['safra'] == s['rotulo']),
                          tiradas=sum(1 for d, _ in t['tirados'] if s['inicio'] <= d <= s['fim']))
            t['por_safra'].append(resumo)
        saida['talhoes'][nome] = t
    return saida


# ------------------------------------------------------------------ texto
def br(v, casas=2):
    return '—' if v is None else format(v, f'.{casas}f').replace('.', ',')


def mm(v):
    if v is None:
        return '—'
    return f'{v:,.0f}'.replace(',', '.') + ' mm'


def dmy(d):
    return '—' if d is None else f'{d:%d/%m/%Y}'


def data_com_entre(d, entre):
    if d is None:
        return '—'
    return f'{d:%d/%m/%Y} (entre {entre[0]:%d/%m} e {entre[1]:%d/%m})'


def dif_txt(s):
    if s['dif_pct'] is None:
        return '—'
    return f'{s["dif_pct"]:+d}%'.replace('-', '−') + (' ▼' if s['abaixo'] else '')


def texto_das_regras(h):
    p = h['parametros']
    return [
        f'Ciclo = subida e descida do índice com pelo menos {br(p["amplitude_min"])} de amplitude; picos a menos de '
        f'{p["distancia_min"]} dias um do outro, ou sem um vale dessa amplitude entre eles, contam como um só (fica o maior).',
        f'Início e fim = o dia em que a curva passa de {round(p["fracao"] * 100)}% do caminho entre a base e o pico, '
        'na subida e na descida. A data sai por interpolação entre duas imagens: as duas vão entre parênteses.',
        f'Queda isolada = imagem que fica {br(p["queda"])} ou mais abaixo da anterior e também da seguinte, com as '
        f'duas a até {p["vizinhanca"]} dias: sai da conta (costuma ser nuvem que sobrou na imagem).',
        'O início do ciclo é quando o verde aparece para o satélite, dias ou semanas depois do plantio; o fim é quando '
        'ele some (maturação, dessecação, colheita ou seca). Não são as datas de plantio e de colheita.',
    ]


def quadro_md(h, nome=None):
    """O quadro em Markdown, no formato fixo de references/quadro.md."""
    s0, s1 = h['safras'][0], h['safras'][-1]
    linhas = [f'# Histórico por satélite{" — " + nome if nome else ""}', '',
              f'Índice: {h["indice"]} · {len(h["safras"])} safra(s), de {dmy(s0["inicio"])} a {dmy(s1["fim"])} · '
              f'{len(h["talhoes"])} talhão(ões) ou área(s).', '']
    linhas += ['## Como ler', ''] + [f'- {r}' for r in texto_das_regras(h)] + ['']
    for a in h['avisos']:
        linhas.append(f'> {a}')
    if h['avisos']:
        linhas.append('')
    linhas += ['## Chuva de cada safra', '',
               '| Safra | Período | Chuva | Média histórica (1991–2020) | Diferença | Dias de chuva | Veranicos | Maior veranico |',
               '|---|---|---|---|---|---|---|---|']
    for s in h['safras']:
        v = s['maior_veranico']
        linhas.append(f'| {s["rotulo"]} | {dmy(s["inicio"])} a {dmy(s["fim"])} | {mm(s["chuva_mm"])} | {mm(s["normal_mm"])} | '
                      f'{dif_txt(s)} | {"—" if s["dias_chuva"] is None else s["dias_chuva"]} | '
                      f'{"—" if s["veranicos"] is None else s["veranicos"]} | '
                      + (f'{v["dias"]} dias, de {v["de"]:%d/%m/%Y} a {v["ate"]:%d/%m/%Y}' if v else '—') + ' |')
    linhas.append('')
    if any(s['abaixo'] for s in h['safras']):
        linhas += [f'▼ = chuva {h["abaixo_pct"]}% ou mais abaixo da média histórica do mesmo período.', '']
    regua = next((s['regua_veranico'] for s in h['safras'] if s['regua_veranico']), None)
    if regua:
        linhas += [f'Veranico = {regua}.', '']
    for nome_t, t in h['talhoes'].items():
        linhas += [f'## {nome_t}', '', '### Ciclos de vegetação', '']
        if t['ciclos']:
            linhas += ['| Safra | Ciclo | Início provável | Pico | Fim provável | Duração | Observações |', '|---|---|---|---|---|---|---|']
            for c in t['ciclos']:
                linhas.append(f'| {c["safra"]} | {c["numero"]} | {data_com_entre(c["inicio"], c["inicio_entre"])} | '
                              f'{br(c["pico_valor"])} em {dmy(c["pico_data"])} | {data_com_entre(c["fim"], c["fim_entre"])} | '
                              f'{"—" if c["duracao_dias"] is None else str(c["duracao_dias"]) + " dias"} | '
                              f'{"; ".join(c["obs"]) or "—"} |')
        else:
            linhas.append('Nenhum ciclo encontrado com as regras acima.')
        linhas.append('')
        for a in t['avisos']:
            linhas.append(f'- {a[0].upper() + a[1:]}.')
        if t['avisos']:
            linhas.append('')
        linhas += ['### Imagens de cada safra', '',
                   '| Safra | Imagens | Maior intervalo sem imagem | Maior valor do índice | Ciclos com pico na safra | Quedas isoladas tiradas |',
                   '|---|---|---|---|---|---|']
        for r in t['por_safra']:
            if not r['imagens']:
                linhas.append(f'| {r["safra"]} | 0 | — | — | — | — |')
                continue
            linhas.append(f'| {r["safra"]} | {r["imagens"]} | {r["maior_intervalo"]} dias, de {r["intervalo_de"]:%d/%m/%Y} a '
                          f'{r["intervalo_ate"]:%d/%m/%Y} | {br(r["maximo"])} em {dmy(r["maximo_data"])} | {r["ciclos"]} | {r["tiradas"]} |')
        linhas.append('')
    linhas += ['## Fontes', '',
               f'- Índice ({h["indice"]}): Copernicus Sentinel-2 L2A, média da área em cada imagem limpa; processado pelas '
               'ferramentas da comunidade agrônomo10X (OagronomIA).',
               '- Chuva: pluviômetros e satélites da comunidade agrônomo10X (OagronomIA).', '',
               'O quadro descreve o que o satélite e o registro de chuva mostram. Índice de vegetação não é '
               'produtividade, e a cultura de cada ciclo não é identificada. A interpretação é do responsável técnico.']
    return '\n'.join(linhas) + '\n'


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    import sintetico
    safras = L.conferir_conjunto([x for texto in sintetico.respostas() for x in L.ler_texto(texto, 'demo')])
    h = montar(safras)
    assert len(h['safras']) == 4 and list(h['talhoes']) == ['Sede', 'Baixada', 'Pasto'], (len(h['safras']), list(h['talhoes']))
    assert not h['avisos'], h['avisos']
    gabarito = sintetico.gabarito()
    for nome in ('Sede', 'Baixada'):
        achados = h['talhoes'][nome]['ciclos']
        esperados = gabarito[nome]
        assert len(achados) == len(esperados), (nome, len(achados), len(esperados))
        for c, (ini, pico, fim) in zip(achados, esperados):
            # o pico é a imagem mais alta: com nuvem em volta, ele pode ficar a alguns dias do pico de verdade
            assert abs((c['pico_data'] - pico).days) <= 15, (nome, c['pico_data'], pico)
            if c['inicio'] is not None:
                assert abs((c['inicio'] - ini).days) <= 8, (nome, 'início', c['inicio'], ini)
            if c['fim'] is not None:
                assert abs((c['fim'] - fim).days) <= 8, (nome, 'fim', c['fim'], fim)
    # a baixada tem dois ciclos por safra; o pasto oscila pouco e não forma ciclo com a amplitude padrão
    assert all(r['ciclos'] == 2 for r in h['talhoes']['Baixada']['por_safra']), h['talhoes']['Baixada']['por_safra']
    assert not h['talhoes']['Pasto']['ciclos'] and h['talhoes']['Pasto']['avisos']
    # ciclo que atravessa a virada da janela não sai cortado quando as janelas estão emendadas
    assert all(c['inicio'] and c['fim'] for c in h['talhoes']['Sede']['ciclos'][1:-1])
    # a safra seca do exemplo fica marcada
    marcadas = [s['rotulo'] for s in h['safras'] if s['abaixo']]
    assert marcadas == ['2022/23'], marcadas
    q = quadro_md(h, 'Fazenda Exemplo')
    assert '## Sede' in q and '▼' in q and 'Copernicus Sentinel-2 L2A' in q and 'produtividade' in q
    # janelas não emendadas: avisa
    so_duas = [safras[0], safras[2]]
    assert 'não estão emendadas' in montar(so_duas)['avisos'][0]
    print(f'historico.py: autoteste ok ({sum(len(t["ciclos"]) for t in h["talhoes"].values())} ciclos achados em 3 talhões e 4 safras, '
          'início e fim a até 8 dias do gabarito)')


if __name__ == '__main__':
    _autoteste()
