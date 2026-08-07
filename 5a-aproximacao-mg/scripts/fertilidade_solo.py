#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fertilidade_solo.py — 5a Aproximação (CFSEMG/MG), Cap. 5 e 6.
Índices do complexo de troca e classificação de fertilidade + fatores de
ajuste das doses de adubação (P e K) por classe, textura e P-rem.

Unidades: cátions em cmolc/dm3 ; P, K, S, micros em mg/dm3.

Definições (Quadro 5.2, notas):
    SB = Ca2+ + Mg2+ + K+ + Na+
    t  = CTC efetiva = SB + Al3+
    T  = CTC a pH 7  = SB + (H + Al)
    m  = 100 * Al3+ / t        (saturação por alumínio)
    V  = 100 * SB / T          (saturação por bases)

Referência: Ribeiro, Guimarães & Alvarez V. (eds., 1999), 5a Aproximação, CFSEMG.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Índices do complexo de troca
# ---------------------------------------------------------------------------
def soma_bases(ca, mg, k, na=0.0):        # cmolc/dm3
    return ca + mg + k + na

def ctc_efetiva(sb, al):                  # t
    return sb + al

def ctc_ph7(sb, h_al):                    # T
    return sb + h_al

def sat_bases(sb, T):                     # V %
    return 100.0 * sb / T if T > 0 else 0.0

def sat_aluminio(al, t):                  # m %
    return 100.0 * al / t if t > 0 else 0.0

def indices(ca, mg, k, al, h_al, na=0.0) -> dict:
    sb = soma_bases(ca, mg, k, na)
    t = ctc_efetiva(sb, al)
    T = ctc_ph7(sb, h_al)
    return {
        "SB": round(sb, 2), "t": round(t, 2), "T": round(T, 2),
        "V_%": round(sat_bases(sb, T), 1), "m_%": round(sat_aluminio(al, t), 1),
    }

# ---------------------------------------------------------------------------
# Classificação de fertilidade (Quadro 5.2) — limites superiores de cada classe
# classes: Muito baixo, Baixo, Médio, Bom, Muito bom
# ---------------------------------------------------------------------------
_CLASSES = ["Muito baixo", "Baixo", "Médio", "Bom", "Muito bom"]

# limites superiores (o último é "acima disso = Muito bom")
_LIM_5_2 = {
    "MO_dag_kg":   [0.70, 2.00, 4.00, 7.00],
    "Ca_cmolc":    [0.40, 1.20, 2.40, 4.00],
    "Mg_cmolc":    [0.15, 0.45, 0.90, 1.50],
    "Al_cmolc":    [0.20, 0.50, 1.00, 2.00],   # nesta característica: alto/muito alto
    "SB_cmolc":    [0.60, 1.80, 3.60, 6.00],
    "HAl_cmolc":   [1.00, 2.50, 5.00, 9.00],
    "t_cmolc":     [0.80, 2.30, 4.60, 8.00],
    "T_cmolc":     [1.60, 4.30, 8.60, 15.00],
    "m_pct":       [15.0, 30.0, 50.0, 75.0],   # saturação por Al
    "V_pct":       [20.0, 40.0, 60.0, 80.0],   # saturação por bases
}

def classificar(caracteristica: str, valor: float) -> str:
    """Classifica um valor conforme o Quadro 5.2 (chaves em _LIM_5_2)."""
    lim = _LIM_5_2[caracteristica]
    for i, teto in enumerate(lim):
        if valor <= teto:
            return _CLASSES[i]
    return _CLASSES[-1]

# P disponível (Mehlich-1) por P-rem (Quadro 5.3) — limites superiores por faixa de P-rem
# faixa P-rem (mg/L): (limMB, limB, limM(nív.crít.), limBom)
_P_POR_PREM = [
    ((0, 4),   (3.0, 4.3, 6.0, 9.0)),
    ((4, 10),  (4.0, 6.0, 8.3, 12.5)),
    ((10, 19), (6.0, 8.3, 11.4, 17.5)),
    ((19, 30), (8.0, 11.4, 15.8, 24.0)),
    ((30, 44), (11.0, 15.8, 21.8, 33.0)),
    ((44, 60), (15.0, 21.8, 30.0, 45.0)),
]

def classificar_P_por_prem(p_disp: float, prem: float) -> str:
    """Classe de P disponível (mg/dm3) conforme P-rem (Quadro 5.3)."""
    faixa = None
    for (lo, hi), lims in _P_POR_PREM:
        if lo <= prem <= hi:
            faixa = lims; break
    if faixa is None:
        faixa = _P_POR_PREM[-1][1] if prem > 60 else _P_POR_PREM[0][1]
    for i, teto in enumerate(faixa):
        if p_disp <= teto:
            return _CLASSES[i]
    return _CLASSES[-1]

def classificar_K(k_disp: float) -> str:
    """Classe de K disponível (mg/dm3), Mehlich-1 (Quadro 5.3):
    <=15 MB; 16-40 B; 41-70 M(nc); 71-120 Bom; >120 Muito bom."""
    for i, teto in enumerate([15, 40, 70, 120]):
        if k_disp <= teto:
            return _CLASSES[i]
    return _CLASSES[-1]

# ---------------------------------------------------------------------------
# Fatores de ajuste das doses de P e K (Cap. 5, princípio geral da adubação)
# ---------------------------------------------------------------------------
# Por classe de disponibilidade
FATOR_CLASSE_GRANDES = {"Muito baixo": 1.25, "Baixo": 1.00, "Médio": 0.80, "Bom": 0.60, "Muito bom": 0.40}
FATOR_CLASSE_HORTALICAS = {"Muito baixo": 1.20, "Baixo": 1.00, "Médio": 0.77, "Bom": 0.53, "Muito bom": 0.30}

def fator_por_classe(classe: str, hortalica: bool = False) -> float:
    return (FATOR_CLASSE_HORTALICAS if hortalica else FATOR_CLASSE_GRANDES)[classe]

def fator_por_textura(argila_pct: float) -> float:
    """Dose básica = solos argilosos (35-60%). Muito argiloso >60%:1,25;
    textura média 15-35%:0,8; arenoso <15%:0,6."""
    if argila_pct > 60: return 1.25
    if argila_pct >= 35: return 1.00
    if argila_pct >= 15: return 0.80
    return 0.60

def fator_por_prem(prem: float) -> float:
    """Fator de ajuste da adubação fosfatada básica pelo P-rem (Cap. 5)."""
    tab = [((0, 4), 1.30), ((4, 10), 1.15), ((10, 19), 1.00),
           ((19, 30), 0.85), ((30, 44), 0.70), ((44, 60), 0.60)]
    for (lo, hi), f in tab:
        if lo <= prem <= hi:
            return f
    return 0.60 if prem > 60 else 1.30


if __name__ == "__main__":
    print("== Índices (café, exemplo do boletim) ==")
    print(" ", indices(ca=0.1, mg=0.1, k=0.01, al=0.8, h_al=7.8))
    print("\n== Classificação (Quadro 5.2/5.3) ==")
    print("  V=2,6% ->", classificar("V_pct", 2.6))
    print("  Ca=2,0 cmolc ->", classificar("Ca_cmolc", 2.0))
    print("  P=8 mg/dm3 com P-rem=15 ->", classificar_P_por_prem(8, 15))
    print("  K=45 mg/dm3 ->", classificar_K(45))
    print("\n== Fatores de ajuste de dose ==")
    print("  Grandes culturas, classe 'Baixo':", fator_por_classe("Baixo"))
    print("  Hortaliça, classe 'Médio':", fator_por_classe("Médio", hortalica=True))
    print("  Textura arenosa (10% argila):", fator_por_textura(10))
    print("  P-rem 25:", fator_por_prem(25))
