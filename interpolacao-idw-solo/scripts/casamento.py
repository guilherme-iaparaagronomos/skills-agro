"""Casamento dos IDs entre o shape de amostras e o laudo do laboratório.

O mundo real: no shape "T01-03", no laudo "t1-3"; "Ponto 12" vs "12";
"AM-07" vs "7"; laudo com duas profundidades por ponto ("T1 0-20" e
"T1 20-40"). A estratégia é canonizar e casar em camadas, da mais segura
para a mais frouxa, sempre 1:1 e reportando a confiança de cada par —
quem decide sobre os casos duvidosos é o usuário.
"""

import re
import unicodedata
from difflib import SequenceMatcher

# palavras que não distinguem pontos ("Ponto 3" ≡ "3")
PALAVRAS_RUIDO = {'PONTO', 'PONTOS', 'PT', 'AMOSTRA', 'AMOSTRAS', 'AM', 'SAMPLE', 'ID', 'N', 'NO', 'NUM'}


def canonizar(s):
    """"T01-03" → "T-1-3"; "t1_3" → "T-1-3"; remove acento, zeros à esquerda."""
    s = unicodedata.normalize('NFKD', str(s).strip().upper())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    tokens = re.findall(r'[A-Z]+|\d+', s)
    return '-'.join(str(int(t)) if t.isdigit() else t for t in tokens)


def canon_reduzido(s):
    """Canônico sem as palavras-ruído ("PONTO-12" → "12")."""
    partes = [t for t in canonizar(s).split('-') if t not in PALAVRAS_RUIDO]
    return '-'.join(partes)


def assinatura_numerica(s):
    """Só os números, na ordem: "T01-03" → (1, 3)."""
    return tuple(int(t) for t in re.findall(r'\d+', str(s)))


def profundidade_de(s):
    """Detecta sufixo de profundidade: "T1 0-20cm" → ((0, 20), "T-1").

    Heurística p/ não confundir com numeração de ponto ("T01-03" e "STC05-10"
    NÃO são profundidade): os dois números finais precisam ser múltiplos de 5,
    crescentes, com camada de 5–60 cm — e o que sobra do id ainda precisa ter
    um número (id de ponto sem número algum é sinal de que os números finais
    eram a numeração do próprio ponto, não uma camada).
    """
    tokens = canonizar(s).split('-')
    if tokens and tokens[-1] == 'CM':
        tokens = tokens[:-1]
    if len(tokens) >= 2 and tokens[-1].isdigit() and tokens[-2].isdigit():
        a, b = int(tokens[-2]), int(tokens[-1])
        resto = tokens[:-2]
        if (a % 5 == 0 and b % 5 == 0 and 5 <= b - a <= 60 and b <= 100
                and any(t.isdigit() for t in resto)):
            return (a, b), '-'.join(resto)
    return None, '-'.join(tokens)


def _unico(mapa):
    """Filtra um dict chave→[itens] para as chaves com item único."""
    return {k: v[0] for k, v in mapa.items() if len(v) == 1}


def _agrupa(ids, funcao):
    grupos = {}
    for i in ids:
        grupos.setdefault(funcao(i), []).append(i)
    return grupos


def casar(ids_pontos, ids_laudo):
    """Casa cada ponto com no máximo um id do laudo (1:1).

    Camadas: canônico exato (1.0) → canônico sem ruído (0.95) → assinatura
    numérica (0.90) → similaridade textual (0.60–0.85, marcado p/ confirmação).

    Devolve dict com: pares [{ponto, laudo, confianca, metodo}], pontos_sem_par,
    laudo_sem_uso e duplicados_laudo (ids do laudo que colidem no canônico —
    tipicamente profundidades: o usuário precisa escolher uma).
    """
    pontos = list(dict.fromkeys(str(i) for i in ids_pontos))
    laudo = list(dict.fromkeys(str(i) for i in ids_laudo))

    # duplicatas: mesmo id-base repetido no laudo (tipicamente profundidades —
    # "T1 0-20" e "T1 20-40" têm o mesmo resto depois de tirar a profundidade)
    duplicados = {k: v
                  for k, v in _agrupa(laudo, lambda s: profundidade_de(s)[1]).items()
                  if len(v) > 1}

    pares, usados_p, usados_l = [], set(), set()

    def rodada(funcao, confianca, metodo):
        gp = _unico(_agrupa([p for p in pontos if p not in usados_p], funcao))
        gl = _unico(_agrupa([l for l in laudo if l not in usados_l], funcao))
        for chave, p in gp.items():
            if chave and chave in gl:
                pares.append({'ponto': p, 'laudo': gl[chave],
                              'confianca': confianca, 'metodo': metodo})
                usados_p.add(p)
                usados_l.add(gl[chave])

    rodada(canonizar, 1.0, 'canonico')
    rodada(canon_reduzido, 0.95, 'sem-ruido')
    rodada(assinatura_numerica, 0.90, 'numerico')

    # última camada: similaridade textual, melhor par primeiro, nunca abaixo de 0.6
    livres_p = [p for p in pontos if p not in usados_p]
    livres_l = [l for l in laudo if l not in usados_l]
    candidatos = sorted(
        ((SequenceMatcher(None, canon_reduzido(p), canon_reduzido(l)).ratio(), p, l)
         for p in livres_p for l in livres_l),
        reverse=True,
    )
    for razao, p, l in candidatos:
        if razao < 0.6:
            break
        if p in usados_p or l in usados_l:
            continue
        pares.append({'ponto': p, 'laudo': l,
                      'confianca': round(min(razao, 0.85), 2), 'metodo': 'aproximado'})
        usados_p.add(p)
        usados_l.add(l)

    # material p/ a camada FINAL do casamento — o julgamento semântico do
    # assistente (LLM) sobre os órfãos: top-3 candidatos por similaridade,
    # mesmo abaixo do corte (quem decide é o assistente COM o usuário)
    sem_par = [p for p in pontos if p not in usados_p]
    sem_uso = [l for l in laudo if l not in usados_l]
    sugestoes = {}
    for p in sem_par:
        ranque = sorted(
            ((SequenceMatcher(None, canon_reduzido(p), canon_reduzido(l)).ratio(), l)
             for l in sem_uso),
            reverse=True,
        )[:3]
        if ranque:
            sugestoes[p] = [{'laudo': l, 'similaridade': round(r, 2)} for r, l in ranque]

    return {
        'pares': pares,
        'pontos_sem_par': sem_par,
        'laudo_sem_uso': sem_uso,
        'sugestoes': sugestoes,
        'duplicados_laudo': duplicados,
    }


def detectar_campos_id(props_pontos, colunas_laudo):
    """Descobre qual atributo dos pontos e qual coluna do laudo são o ID comum.

    Testa cada par (atributo, coluna) e pontua pela fração de casamentos
    canônicos, com bônus de unicidade (um campo de ID não repete valor).
    Devolve (campo_pontos, coluna_laudo, score 0–1).
    """
    campos = sorted({k for p in props_pontos for k in p})
    melhor = (None, None, 0.0)
    for campo in campos:
        vals_p = [canon_reduzido(p.get(campo, '')) for p in props_pontos]
        if not any(vals_p):
            continue
        unico_p = len(set(vals_p)) / len(vals_p)
        for coluna, vals in colunas_laudo.items():
            vals_l = {canon_reduzido(v) for v in vals if str(v).strip()}
            if not vals_l:
                continue
            acertos = sum(1 for v in vals_p if v and v in vals_l)
            score = acertos / max(len(vals_p), 1) * (0.5 + 0.5 * unico_p)
            if score > melhor[2]:
                melhor = (campo, coluna, round(score, 3))
    return melhor


if __name__ == '__main__':
    # exemplos embutidos — os casos do mundo real
    assert canonizar('T01-03') == canonizar('t1-3') == 'T-1-3'
    assert canon_reduzido('Ponto 12') == canon_reduzido('12') == '12'
    assert assinatura_numerica('AM_07/2') == (7, 2)
    assert profundidade_de('T1 0-20cm') == ((0, 20), 'T-1')

    r = casar(['T01-01', 'T01-02', 'Ponto 3', 'P4'],
              ['t1-1', 'T1 - 2', '3', 'ponto quatro'])
    casados = {p['ponto']: (p['laudo'], p['metodo']) for p in r['pares']}
    assert casados['T01-01'] == ('t1-1', 'canonico')
    assert casados['T01-02'] == ('T1 - 2', 'canonico')
    assert casados['Ponto 3'] == ('3', 'sem-ruido')
    assert 'P4' in r['pontos_sem_par']  # "ponto quatro" não tem número: não força
    print('casar OK:', casados)

    r2 = casar(['T1', 'T2'], ['T1 0-20', 'T1 20-40', 'T2 0-20', 'T2 20-40'])
    assert set(r2['duplicados_laudo']) == {'T-1', 'T-2'}
    print('duplicados (profundidades) OK:', r2['duplicados_laudo'])

    # "STC05-10" é talhão STC 05, ponto 10 — NÃO é camada 5-10 cm
    assert profundidade_de('STC05-10') == (None, 'STC-5-10')
    r3 = casar(['STC05-10', 'STC05-20'], ['stc5-10', 'stc5-20'])
    assert not r3['duplicados_laudo'] and len(r3['pares']) == 2
    print('falso-positivo de profundidade OK (STC05-10 casa normal)')

    campo, coluna, score = detectar_campos_id(
        [{'plot_id': 'T01-01', 'area': '12'}, {'plot_id': 'T01-02', 'area': '12'}],
        {'Amostra': ['t1-1', 't1-2'], 'P': ['8,1', '12,0']},
    )
    assert (campo, coluna) == ('plot_id', 'Amostra'), (campo, coluna, score)
    print(f'detectar_campos_id OK: {campo} ↔ {coluna} (score {score})')
