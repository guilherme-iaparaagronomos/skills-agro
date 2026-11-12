"""Classes de interpretação para os mapas: tabelas oficiais, limites do usuário
ou classes livres.

Duas tabelas oficiais (os números vêm das skills `5a-aproximacao-mg` e
`boletim-100-sp`, conferidos nos boletins):
- 'mg': 5ª Aproximação (CFSEMG, 1999), Quadros 5.1 a 5.5;
- 'sp': Boletim 100 (IAC, 1997), Quadros 4.1 a 4.4.

Regra de segurança: classe oficial só entra quando a COLUNA do laudo traz a
unidade no cabeçalho e ela é a da tabela (ou conversível). Unidade ausente ou
estranha, extrator trocado (P resina × Mehlich, pH em água × CaCl2) → a coluna
cai em classes livres e o motivo vai para os avisos. Classificar K em mg/dm³
com limites de mmolc/dm³ daria um mapa bonito e errado.
"""

import re
import unicodedata

import numpy as np

N5 = ['Muito baixo', 'Baixo', 'Médio', 'Bom', 'Muito bom']
N5_ALTO = ['Muito baixo', 'Baixo', 'Médio', 'Alto', 'Muito alto']
N5_MICRO = ['Muito baixo', 'Baixo', 'Médio', 'Bom', 'Alto']
N3 = ['Baixo', 'Médio', 'Alto']

# faixas (limite inferior exclusivo, superior inclusivo) → limites superiores das classes
_P_ARGILA_MG = [((60, 100), [2.7, 5.4, 8.0, 12.0]), ((35, 60), [4.0, 8.0, 12.0, 18.0]),
                ((15, 35), [6.6, 12.0, 20.0, 30.0]), ((0, 15), [10.0, 20.0, 30.0, 45.0])]
_P_PREM_MG = [((0, 4), [3.0, 4.3, 6.0, 9.0]), ((4, 10), [4.0, 6.0, 8.3, 12.5]),
              ((10, 19), [6.0, 8.3, 11.4, 17.5]), ((19, 30), [8.0, 11.4, 15.8, 24.0]),
              ((30, 44), [11.0, 15.8, 21.8, 33.0]), ((44, 60), [15.0, 21.8, 30.0, 45.0])]
_S_PREM_MG = [((0, 4), [1.7, 2.5, 3.6, 5.4]), ((4, 10), [2.4, 3.6, 5.0, 7.5]),
              ((10, 19), [3.3, 5.0, 6.9, 10.3]), ((19, 30), [4.6, 6.9, 9.4, 14.2]),
              ((30, 44), [6.4, 9.4, 13.0, 19.6]), ((44, 60), [8.9, 13.0, 18.0, 27.0])]


def _item(rotulo, unidade, limites, nomes, fonte, sentido='alto_bom', **extra):
    return {'rotulo': rotulo, 'unidade': unidade, 'limites': limites, 'nomes': nomes,
            'fonte': fonte, 'sentido': sentido, **extra}


TABELAS = {
    'mg': {
        'nome': '5ª Aproximação (CFSEMG, 1999)',
        'itens': {
            'ph': _item('pH em água', None, [4.5, 5.4, 6.0, 7.0],
                        ['Muito baixo', 'Baixo', 'Bom', 'Alto', 'Muito alto'],
                        'Quadro 5.1', 'otimo_meio', metodo='agua'),
            'mo': _item('Matéria orgânica', 'dag/kg', [0.70, 2.00, 4.00, 7.00], N5, 'Quadro 5.2'),
            'co': _item('Carbono orgânico', 'dag/kg', [0.40, 1.16, 2.32, 4.06], N5, 'Quadro 5.2'),
            'ca': _item('Cálcio trocável', 'cmolc/dm3', [0.40, 1.20, 2.40, 4.00], N5, 'Quadro 5.2'),
            'mg': _item('Magnésio trocável', 'cmolc/dm3', [0.15, 0.45, 0.90, 1.50], N5, 'Quadro 5.2'),
            'al': _item('Acidez trocável (Al)', 'cmolc/dm3', [0.20, 0.50, 1.00, 2.00], N5_ALTO,
                        'Quadro 5.2', 'alto_ruim'),
            'sb': _item('Soma de bases', 'cmolc/dm3', [0.60, 1.80, 3.60, 6.00], N5, 'Quadro 5.2'),
            'hal': _item('Acidez potencial (H+Al)', 'cmolc/dm3', [1.00, 2.50, 5.00, 9.00], N5_ALTO,
                         'Quadro 5.2', 'alto_ruim'),
            't': _item('CTC efetiva (t)', 'cmolc/dm3', [0.80, 2.30, 4.60, 8.00], N5, 'Quadro 5.2'),
            'T': _item('CTC a pH 7 (T)', 'cmolc/dm3', [1.60, 4.30, 8.60, 15.00], N5, 'Quadro 5.2'),
            'm': _item('Saturação por alumínio', '%', [15.0, 30.0, 50.0, 75.0], N5_ALTO,
                       'Quadro 5.2', 'alto_ruim'),
            'v': _item('Saturação por bases', '%', [20.0, 40.0, 60.0, 80.0], N5, 'Quadro 5.2'),
            'k': _item('Potássio disponível', 'mg/dm3', [15, 40, 70, 120], N5, 'Quadro 5.3',
                       pressupoe='Mehlich-1'),
            'p': _item('Fósforo disponível', 'mg/dm3', None, N5, 'Quadro 5.3',
                       pressupoe='Mehlich-1', metodo='mehlich',
                       por_argila=_P_ARGILA_MG, por_prem=_P_PREM_MG),
            's': _item('Enxofre disponível', 'mg/dm3', None, N5, 'Quadro 5.4', por_prem=_S_PREM_MG),
            'zn': _item('Zinco', 'mg/dm3', [0.4, 0.9, 1.5, 2.2], N5_MICRO, 'Quadro 5.5',
                        pressupoe='Mehlich-1'),
            'mn': _item('Manganês', 'mg/dm3', [2, 5, 8, 12], N5_MICRO, 'Quadro 5.5',
                        pressupoe='Mehlich-1'),
            'fe': _item('Ferro', 'mg/dm3', [8, 18, 30, 45], N5_MICRO, 'Quadro 5.5',
                        pressupoe='Mehlich-1'),
            'cu': _item('Cobre', 'mg/dm3', [0.3, 0.7, 1.2, 1.8], N5_MICRO, 'Quadro 5.5',
                        pressupoe='Mehlich-1'),
            'b': _item('Boro', 'mg/dm3', [0.15, 0.35, 0.60, 0.90], N5_MICRO, 'Quadro 5.5',
                       pressupoe='água quente'),
            'argila': _item('Argila', '%', [15, 35, 60],
                            ['Arenosa', 'Média', 'Argilosa', 'Muito argilosa'],
                            'faixas de argila do Quadro 5.3', 'neutra'),
        },
    },
    'sp': {
        'nome': 'Boletim 100 (IAC, 1997)',
        'itens': {
            'ph': _item('pH em CaCl2', None, [4.3, 5.0, 5.5, 6.0],
                        ['Acidez muito alta', 'Acidez alta', 'Acidez média', 'Acidez baixa',
                         'Acidez muito baixa'], 'Quadro 4.2', metodo='cacl2'),
            'v': _item('Saturação por bases', '%', [25, 50, 70, 90],
                       ['Muito baixa', 'Baixa', 'Média', 'Alta', 'Muito alta'], 'Quadro 4.2'),
            'k': _item('Potássio trocável', 'mmolc/dm3', [0.7, 1.5, 3.0, 6.0], N5_ALTO, 'Quadro 4.1'),
            'p': _item('Fósforo (resina)', 'mg/dm3', None, N5_ALTO, 'Quadro 4.1',
                       pressupoe='resina', metodo='resina',
                       por_grupo={'florestais': [2, 5, 8, 16], 'perenes': [5, 12, 30, 60],
                                  'anuais': [6, 15, 40, 80], 'hortalicas': [10, 25, 60, 120]}),
            'ca': _item('Cálcio trocável', 'mmolc/dm3', [3, 7], N3, 'Quadro 4.3'),
            'mg': _item('Magnésio trocável', 'mmolc/dm3', [4, 8], N3, 'Quadro 4.3'),
            's': _item('Enxofre (S-SO4)', 'mg/dm3', [4, 10], N3, 'Quadro 4.3'),
            'b': _item('Boro', 'mg/dm3', [0.20, 0.60], N3, 'Quadro 4.4', pressupoe='água quente'),
            'cu': _item('Cobre', 'mg/dm3', [0.2, 0.8], N3, 'Quadro 4.4', pressupoe='DTPA'),
            'fe': _item('Ferro', 'mg/dm3', [4, 12], N3, 'Quadro 4.4', pressupoe='DTPA'),
            'mn': _item('Manganês', 'mg/dm3', [1.2, 5.0], N3, 'Quadro 4.4', pressupoe='DTPA'),
            'zn': _item('Zinco', 'mg/dm3', [0.5, 1.2], N3, 'Quadro 4.4', pressupoe='DTPA'),
        },
    },
}

# ------------------------------------------------------------------ unidades
# família, fator (quantas unidades destas valem 1 da unidade-base da família)
_UNIDADES = {
    'mg/dm3': ('massa', 1), 'ppm': ('massa', 1), 'mg/kg': ('massa', 1), 'mg/l': ('massa', 1),
    'cmolc/dm3': ('carga', 1), 'cmolc/kg': ('carga', 1), 'meq/100cm3': ('carga', 1),
    'meq/100g': ('carga', 1), 'meq/100ml': ('carga', 1),
    'mmolc/dm3': ('carga', 10), 'mmolc/kg': ('carga', 10),
    '%': ('fracao', 1), 'dag/kg': ('fracao', 1), 'dag/dm3': ('fracao', 1),
    'g/kg': ('fracao', 10), 'g/dm3': ('fracao', 10), 'g/l': ('fracao', 10),
}
_MG_POR_CMOLC_K = 391.0  # 1 cmolc de K = 391 mg


def sem_acento(s):
    s = unicodedata.normalize('NFKD', str(s))
    return ''.join(c for c in s if not unicodedata.combining(c))


def separar_cabecalho(coluna):
    """'K (mg/dm³)' → ('K', 'mg/dm3'); 'V%' → ('V', '%'); 'pH CaCl2' → ('pH CaCl2', None)."""
    texto = str(coluna).strip()
    nome, unidade = texto, None
    m = re.search(r'[\(\[]([^\)\]]*)[\)\]]\s*$', texto)
    if m:
        nome, unidade = texto[:m.start()].strip(), m.group(1)
    elif texto.endswith('%'):
        nome, unidade = texto[:-1].strip(), '%'
    else:
        m = re.search(r'\s([A-Za-zµ%]+\s*[/.]\s*\S+|\S+-[13])\s*$', texto)
        if m and re.search(r'dm|kg|/l|100', sem_acento(m.group(1)).lower()):
            nome, unidade = texto[:m.start()].strip(), m.group(1)
    return nome, normalizar_unidade(unidade)


def normalizar_unidade(unidade):
    if unidade is None:
        return None
    u = sem_acento(unidade).lower().replace('³', '3')
    u = re.sub(r'[\s.]', '', u)
    u = u.replace('dm-3', '/dm3').replace('kg-1', '/kg').replace('l-1', '/l').replace('//', '/')
    u = u.replace('cm3', 'cm3').replace('mmol(c)', 'mmolc').replace('cmol(c)', 'cmolc')
    return u or None


def fator_de_unidade(unid_tabela, unid_dado, chave):
    """Multiplicador que leva os limites da tabela para a unidade do dado.
    None = unidades incompatíveis (ou desconhecidas)."""
    if unid_tabela is None:
        return 1.0
    if unid_dado is None or unid_dado not in _UNIDADES:
        return None
    fam_t, f_t = _UNIDADES[unid_tabela]
    fam_d, f_d = _UNIDADES[unid_dado]
    if fam_t == fam_d:
        return f_d / f_t
    if chave == 'k' and {fam_t, fam_d} == {'massa', 'carga'}:
        if fam_t == 'massa':  # tabela em mg/dm3, dado em (c|m)molc/dm3
            return f_d / _MG_POR_CMOLC_K
        return _MG_POR_CMOLC_K / f_t  # tabela em (c|m)molc/dm3, dado em mg/dm3
    return None


# ------------------------------------------------------- coluna → item da tabela
_PADROES = [  # ordem importa: o mais específico primeiro
    ('argila', r'\bargila\b'),
    ('prem', r'\bp[\s\-_.]*rem\b'),
    ('ph', r'^ph\b'),
    ('hal', r'h\s*\+\s*al|^hal\b|acidez potencial'),
    ('sb', r'^sb\b|soma de bases'),
    ('mo', r'^m\.?\s?o\.?(\b|$)|materia organica'),
    ('co', r'^c\.?\s?o\.?(\b|$)|carbono'),
    ('mn', r'^mn\b|manganes'),
    ('mg', r'^mg\b|magnesio'),
    ('zn', r'^zn\b|zinco'),
    ('fe', r'^fe\b|ferro'),
    ('cu', r'^cu\b|cobre'),
    ('ca', r'^ca\b|calcio'),
    ('al', r'^al\b|aluminio trocavel|^aluminio'),
    ('v', r'^v\b|saturacao (por|de) bases'),
    ('m', r'^m\b|saturacao (por|de) al'),
    ('p', r'^p\b|fosforo'),
    ('k', r'^k\b|potassio'),
    ('s', r'^s\b|enxofre'),
    ('b', r'^b\b|boro'),
]


def chave_da_coluna(coluna):
    """Qual item de tabela a coluna parece ser. Devolve (chave|None, metodo|None).
    metodo: 'agua'/'cacl2' para pH, 'resina'/'mehlich' para P, quando o cabeçalho diz."""
    nome, _ = separar_cabecalho(coluna)
    bruto = nome.strip()
    baixo = sem_acento(bruto).lower()
    if bruto == 'T' or re.search(r'ctc\s*(a\s*)?(ph\s*7|total|potencial)', baixo):
        return 'T', None
    if bruto == 't' or 'ctc efetiva' in baixo:
        return 't', None
    if re.fullmatch(r'ctc', baixo):
        return 'T', None
    chave = next((c for c, padrao in _PADROES if re.search(padrao, baixo)), None)
    metodo = None
    if chave == 'ph':
        if 'cacl' in baixo:
            metodo = 'cacl2'
        elif re.search(r'h2o|agua', baixo):
            metodo = 'agua'
        elif 'smp' in baixo or 'kcl' in baixo:
            return None, None  # pH SMP/KCl não tem classe nas duas tabelas
    if chave == 'p':
        if 'resina' in baixo or re.search(r'\bres\b', baixo):
            metodo = 'resina'
        elif re.search(r'mehlich|\bmeh\b|\bm1\b', baixo):
            metodo = 'mehlich'
    return chave, metodo


def _escala(valor):
    return [round(v, 4) for v in valor]


def resolver(coluna, tabela=None, chave=None, limites=None, nomes=None, sentido=None,
             grupo_cultura=None, tem_argila=False, tem_prem=False):
    """Decide como a coluna será classificada. Devolve um dicionário:
       modo: 'limites' (lista fixa na unidade do dado) | 'por_faixa' (limites
       dependem de argila ou P-rem de cada pixel) | 'livre' (sem tabela);
       + nomes, sentido, fonte, avisos e o que mais a legenda precisa."""
    nome, unidade = separar_cabecalho(coluna)
    base = {'coluna': coluna, 'nome': nome, 'unidade': unidade, 'avisos': []}

    if limites:  # o usuário mandou: vence qualquer tabela
        lim = sorted(float(v) for v in limites)
        return {**base, 'modo': 'limites', 'limites': lim,
                'nomes': nomes if nomes and len(nomes) == len(lim) + 1 else None,
                'sentido': sentido or 'neutra', 'fonte': 'limites informados pelo usuário'}

    if not tabela or tabela == 'nenhuma' or chave == 'nenhuma':
        return {**base, 'modo': 'livre', 'sentido': sentido or 'neutra', 'fonte': None}

    itens = TABELAS[tabela]['itens']
    metodo = None
    if not chave:
        chave, metodo = chave_da_coluna(coluna)
    if chave not in itens:
        motivo = ('não reconhecida' if not chave or chave == 'prem'
                  else f'sem classe para "{chave}" nesta tabela')
        if chave != 'prem':
            base['avisos'].append(f'{coluna}: {motivo} em {TABELAS[tabela]["nome"]} — classes livres')
        return {**base, 'modo': 'livre', 'sentido': sentido or 'neutra', 'fonte': None}

    item = itens[chave]
    fonte = f'{TABELAS[tabela]["nome"]}, {item["fonte"]}'
    livre = {**base, 'modo': 'livre', 'sentido': sentido or 'neutra', 'fonte': None}

    quer = item.get('metodo')  # extrator/meio que a tabela pressupõe
    if quer and metodo and metodo != quer:
        livre['avisos'].append(
            f'{coluna}: a tabela é para {item["rotulo"]} e a coluna indica outro método '
            f'({metodo}) — classes livres')
        return livre
    if quer and not metodo and chave in ('ph', 'p'):
        livre['avisos'].append(
            f'{coluna}: o cabeçalho não diz o método ({item["rotulo"]} é o que a tabela pede). '
            f'Confirme com o usuário e force com --classe "{coluna}={chave}"')
        return livre

    fator = fator_de_unidade(item['unidade'], unidade, chave)
    if fator is None:
        livre['avisos'].append(
            f'{coluna}: unidade "{unidade or "ausente"}" não bate com a da tabela '
            f'({item["unidade"]}) — classes livres. Ponha a unidade no cabeçalho do laudo')
        return livre

    spec = {**base, 'chave': chave, 'tabela': tabela, 'rotulo': item['rotulo'],
            'nomes': item['nomes'], 'sentido': sentido or item['sentido'], 'fonte': fonte,
            'pressupoe': item.get('pressupoe'), 'fator': fator}
    if fator != 1.0:
        spec['avisos'].append(
            f'{coluna}: limites convertidos de {item["unidade"]} para {unidade} (×{fator:g})')

    if item['limites'] is not None:
        return {**spec, 'modo': 'limites', 'limites': _escala(v * fator for v in item['limites'])}

    if 'por_grupo' in item:
        if grupo_cultura not in item['por_grupo']:
            livre['avisos'].append(
                f'{coluna}: o P do Boletim 100 depende do grupo de culturas — informe '
                f'--grupo-cultura ({", ".join(item["por_grupo"])})')
            return livre
        spec['fonte'] += f' ({grupo_cultura})'
        return {**spec, 'modo': 'limites',
                'limites': _escala(v * fator for v in item['por_grupo'][grupo_cultura])}

    # P e S de MG: o limite muda com a argila (ou o P-rem) de cada pixel
    if 'por_argila' in item and tem_argila:
        return {**spec, 'modo': 'por_faixa', 'auxiliar': 'argila',
                'faixas': [(f, _escala(v * fator for v in lim)) for f, lim in item['por_argila']]}
    if 'por_prem' in item and tem_prem:
        return {**spec, 'modo': 'por_faixa', 'auxiliar': 'prem',
                'faixas': [(f, _escala(v * fator for v in lim)) for f, lim in item['por_prem']]}
    falta = 'argila ou P-rem' if 'por_argila' in item else 'P-rem'
    livre['avisos'].append(
        f'{coluna}: a classe de {item["rotulo"]} em MG depende de {falta} — inclua a coluna '
        f'no laudo (--argila/--prem) ou informe um valor único (--argila-fixa/--prem-fixo)')
    return livre


# --------------------------------------------------------------- classificação
def _bonito(v):
    """Passo 'redondo' (1, 2, 2,5, 5 × 10^n) igual ou acima de v."""
    if v <= 0:
        return 1.0
    base = 10 ** np.floor(np.log10(v))
    for mult in (1, 2, 2.5, 5, 10):
        if base * mult >= v:
            return float(base * mult)
    return float(base * 10)


def limites_livres(malha, modo='intervalos', n_classes=5):
    """Limites para colunas sem tabela: intervalos iguais 'redondos' ou quantis."""
    validos = malha[np.isfinite(malha)]
    lo, hi = float(validos.min()), float(validos.max())
    if hi - lo < 1e-12:
        return []
    if modo == 'quantis':
        q = np.quantile(validos, np.linspace(0, 1, n_classes + 1)[1:-1])
        lim = sorted({float(f'{v:.3g}') for v in q})
        return [v for v in lim if lo < v < hi]
    passo = _bonito((hi - lo) / n_classes)
    inicio = np.floor(lo / passo) * passo
    lim = [round(inicio + passo * i, 10) for i in range(1, 60)]
    return [v for v in lim if lo < v < hi]


def classificar(malha, spec, auxiliar=None, modo_livre='intervalos', n_classes=5):
    """Devolve (indices [ny, nx] int16 com -1 fora, limites|None, nomes).
    Classe i = valores em (limite[i-1], limite[i]] — teto incluso, como nas tabelas."""
    fora = ~np.isfinite(malha)
    seguro = np.where(fora, 0.0, malha)

    if spec['modo'] == 'por_faixa':
        if auxiliar is None:
            raise ValueError(f'{spec["coluna"]}: falta a superfície de {spec["auxiliar"]}')
        aux = np.broadcast_to(np.asarray(auxiliar, dtype=float), malha.shape)
        idx = np.full(malha.shape, -1, dtype=np.int16)
        faixas = sorted(spec['faixas'], key=lambda f: f[0][0])
        for n, ((lo, hi), lim) in enumerate(faixas):
            # primeira faixa pega o piso; a última, tudo o que passar do teto
            sel = aux <= hi if n == 0 else (aux > lo) if n == len(faixas) - 1 else (aux > lo) & (aux <= hi)
            sel &= np.isfinite(aux)
            idx[sel] = np.digitize(seguro[sel], lim, right=True)
        idx[fora | ~np.isfinite(aux)] = -1
        return idx, None, spec['nomes']

    if spec['modo'] == 'livre':
        limites = limites_livres(malha, modo_livre, n_classes)
        nomes = None
    else:
        limites, nomes = spec['limites'], spec.get('nomes')
    idx = np.digitize(seguro, limites, right=True).astype(np.int16)
    idx[fora] = -1
    return idx, limites, nomes


def num_br(v, casas=None):
    """Número em formato brasileiro, sem zeros sobrando: 0.7→'0,7'; 120.0→'120'."""
    if casas is None:
        texto = f'{float(v):.4g}' if abs(v) < 10000 else f'{float(v):.0f}'
        if 'e' in texto:
            texto = f'{float(v):.6f}'.rstrip('0').rstrip('.')
    else:
        texto = f'{float(v):.{casas}f}'
    return texto.replace('.', ',')


def rotulos_de_faixa(limites):
    """[15, 40] → ['≤ 15', '15 – 40', '> 40'] (teto incluso em cada classe)."""
    if not limites:
        return ['todos os valores']
    r = [f'≤ {num_br(limites[0])}']
    r += [f'{num_br(a)} – {num_br(b)}' for a, b in zip(limites, limites[1:])]
    return r + [f'> {num_br(limites[-1])}']


if __name__ == '__main__':
    # cabeçalhos reais → item + unidade
    assert separar_cabecalho('K (mg/dm³)') == ('K', 'mg/dm3')
    assert separar_cabecalho('Ca [cmolc dm-3]') == ('Ca', 'cmolc/dm3')
    assert separar_cabecalho('V%') == ('V', '%')
    assert separar_cabecalho('pH CaCl2') == ('pH CaCl2', None)
    assert separar_cabecalho('Argila g/kg') == ('Argila', 'g/kg')
    for col, esperado in [('K (mg/dm3)', 'k'), ('Mg (cmolc/dm3)', 'mg'), ('Mn', 'mn'),
                          ('M.O. (dag/kg)', 'mo'), ('m (%)', 'm'), ('H+Al', 'hal'), ('Al', 'al'),
                          ('T', 'T'), ('t', 't'), ('CTC pH 7', 'T'), ('P-rem (mg/L)', 'prem'),
                          ('Fósforo Mehlich', 'p'), ('Argila (g/kg)', 'argila'), ('S', 's'),
                          ('Saturação por bases (%)', 'v'), ('Areia (g/kg)', None)]:
        assert chave_da_coluna(col)[0] == esperado, (col, chave_da_coluna(col))
    assert chave_da_coluna('pH H2O') == ('ph', 'agua')
    assert chave_da_coluna('P resina (mg/dm3)') == ('p', 'resina')

    # exemplos das skills de boletim: K=45 mg/dm3 → Médio (MG); V=2,6% → Muito baixo
    k = resolver('K (mg/dm3)', 'mg')
    idx, lim, nomes = classificar(np.array([[45.0, 15.0, 15.1, 121.0, np.nan]]), k)
    assert [nomes[i] for i in idx[0][:4]] == ['Médio', 'Muito baixo', 'Baixo', 'Muito bom']
    assert idx[0][4] == -1
    v = resolver('V (%)', 'mg')
    assert classificar(np.array([[2.6]]), v)[0][0][0] == 0

    # unidade: Ca em mmolc/dm3 com a tabela de MG (cmolc) → limites ×10
    ca = resolver('Ca (mmolc/dm3)', 'mg')
    assert ca['limites'] == [4.0, 12.0, 24.0, 40.0] and ca['avisos']
    # K em mmolc/dm3 com a tabela de MG (mg/dm3): 70 mg/dm3 = 1,79 mmolc/dm3
    kmm = resolver('K (mmolc/dm3)', 'mg')
    assert abs(kmm['limites'][2] - 1.7903) < 1e-3, kmm['limites']
    # argila em g/kg vira as faixas em g/kg
    assert resolver('Argila (g/kg)', 'mg')['limites'] == [150.0, 350.0, 600.0]
    # sem unidade no cabeçalho não há classe oficial
    assert resolver('K', 'mg')['modo'] == 'livre'
    # extrator trocado e método ausente caem em classes livres, com aviso
    assert resolver('P resina (mg/dm3)', 'mg')['modo'] == 'livre'
    assert resolver('pH', 'sp')['modo'] == 'livre'
    assert resolver('pH CaCl2', 'sp')['modo'] == 'limites'

    # P de MG por argila do pixel: o mesmo P=8 é Médio no muito argiloso e Muito baixo no arenoso
    p = resolver('P Mehlich (mg/dm3)', 'mg', tem_argila=True)
    assert p['modo'] == 'por_faixa' and p['auxiliar'] == 'argila'
    idx, _, nomes = classificar(np.array([[8.0, 8.0, 8.0]]), p, auxiliar=np.array([[65.0, 45.0, 10.0]]))
    assert [nomes[i] for i in idx[0]] == ['Médio', 'Baixo', 'Muito baixo'], idx
    # exemplo da skill de MG: P=8 com P-rem=15 → Baixo
    pr = resolver('P Mehlich (mg/dm3)', 'mg', tem_prem=True)
    assert classificar(np.array([[8.0]]), pr, auxiliar=np.array([[15.0]]))[0][0][0] == 1
    assert resolver('P Mehlich (mg/dm3)', 'mg')['modo'] == 'livre'

    # P de SP por grupo de cultura: 20 mg/dm3 é Médio para anuais e Baixo para hortaliças
    assert resolver('P resina (mg/dm3)', 'sp')['modo'] == 'livre'
    pa = resolver('P resina (mg/dm3)', 'sp', grupo_cultura='anuais')
    ph = resolver('P resina (mg/dm3)', 'sp', grupo_cultura='hortalicas')
    assert classificar(np.array([[20.0]]), pa)[0][0][0] == 2
    assert classificar(np.array([[20.0]]), ph)[0][0][0] == 1

    # limites do usuário e classes livres
    u = resolver('CE (mS/m)', 'mg', limites=['20', '10'])
    assert u['limites'] == [10.0, 20.0] and u['fonte'].startswith('limites informados')
    livre = resolver('Areia (g/kg)', 'mg')
    malha = np.linspace(203, 687, 50).reshape(5, 10)
    idx, lim, _ = classificar(malha, livre)
    assert lim == [300.0, 400.0, 500.0, 600.0] and idx.max() == 4, lim
    assert rotulos_de_faixa([15, 40]) == ['≤ 15', '15 – 40', '> 40']
    assert num_br(0.7) == '0,7' and num_br(120.0) == '120' and num_br(1.7903) == '1,79'
    print('classes OK: tabelas MG e SP, unidades, extratores, P por argila/P-rem/grupo')
