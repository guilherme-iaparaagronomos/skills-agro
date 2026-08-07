#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fertilidade_solo.py — Boletim 100 (IAC/SP), Cap. 3 e 4.
Cálculos de fertilidade do solo: soma de bases, CTC, saturação por bases (V%),
saturação por alumínio (m%) e conversão de unidades (Quadro 3.1).

Unidades padrão do Boletim 100 (Sistema Internacional):
  - cátions trocáveis (Ca, Mg, K, Al, H+Al) em mmolc/dm3
  - P, S e micronutrientes em mg/dm3
  - M.O. e argila em g/kg
  - pH em CaCl2

Referência: van Raij, B. et al. (1997). Recomendações de Adubação e Calagem
para o Estado de São Paulo. 2a ed. Boletim Técnico 100, IAC, Campinas.

Uso rápido:
    python fertilidade_solo.py
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Conversão de unidades — Quadro 3.1 (Unidade Nova = Unidade Antiga x Fator)
# ---------------------------------------------------------------------------
FATORES = {
    "pct_para_g_kg": 10.0,      # %  -> g/kg, g/dm3, g/L
    "meq100_para_mmolc": 10.0,  # meq/100 cm3 -> mmolc/dm3
    "P2O5_para_P": 0.437,
    "K2O_para_K": 0.830,
    "CaO_para_Ca": 0.715,
    "MgO_para_Mg": 0.602,
}
# Fatores inversos (óxido a partir do elemento)
FATORES_INV = {
    "P_para_P2O5": 1.0 / 0.437,   # ~2.291
    "K_para_K2O": 1.0 / 0.830,    # ~1.205
    "Ca_para_CaO": 1.0 / 0.715,   # ~1.399
    "Mg_para_MgO": 1.0 / 0.602,   # ~1.661
}


def soma_de_bases(ca: float, mg: float, k: float, na: float = 0.0) -> float:
    """SB = Ca2+ + Mg2+ + K+ (+ Na+), em mmolc/dm3."""
    return ca + mg + k + na


def ctc_ph7(sb: float, h_al: float) -> float:
    """CTC a pH 7 (T) = SB + (H + Al), em mmolc/dm3.
    'h_al' é a acidez potencial (H+Al) em mmolc/dm3."""
    return sb + h_al


def ctc_efetiva(sb: float, al: float) -> float:
    """CTC efetiva (t) = SB + Al3+, em mmolc/dm3."""
    return sb + al


def saturacao_por_bases(sb: float, ctc: float) -> float:
    """V% = 100 * SB / CTC(pH7)."""
    if ctc <= 0:
        raise ValueError("CTC deve ser > 0")
    return 100.0 * sb / ctc


def saturacao_por_aluminio(al: float, sb: float) -> float:
    """m% = 100 * Al / (SB + Al) = 100 * Al / t."""
    t = sb + al
    if t <= 0:
        return 0.0
    return 100.0 * al / t


def diagnostico_acidez(ph_cacl2: float | None = None, v: float | None = None) -> dict:
    """Interpreta pH em CaCl2 e/ou V% conforme Quadro 4.2 do Boletim 100."""
    out = {}
    if ph_cacl2 is not None:
        if ph_cacl2 <= 4.3:   c = "Acidez muito alta"
        elif ph_cacl2 <= 5.0: c = "Acidez alta"
        elif ph_cacl2 <= 5.5: c = "Acidez média"
        elif ph_cacl2 <= 6.0: c = "Acidez baixa"
        else:                 c = "Acidez muito baixa"
        out["pH_CaCl2"] = c
    if v is not None:
        if v <= 25:   c = "V muito baixa"
        elif v <= 50: c = "V baixa"
        elif v <= 70: c = "V média"
        elif v <= 90: c = "V alta"
        else:         c = "V muito alta"
        out["V"] = c
    return out


def analise_completa(ca, mg, k, h_al, al=0.0, na=0.0, ph_cacl2=None) -> dict:
    """Roda o conjunto de índices a partir dos resultados de análise de solo."""
    sb = soma_de_bases(ca, mg, k, na)
    t = ctc_ph7(sb, h_al)
    te = ctc_efetiva(sb, al)
    v = saturacao_por_bases(sb, t)
    m = saturacao_por_aluminio(al, sb)
    r = {
        "SB (mmolc/dm3)": round(sb, 2),
        "CTC pH7 (T, mmolc/dm3)": round(t, 2),
        "CTC efetiva (t, mmolc/dm3)": round(te, 2),
        "V (%)": round(v, 1),
        "m (%)": round(m, 1),
    }
    r.update(diagnostico_acidez(ph_cacl2, v))
    return r


if __name__ == "__main__":
    # Exemplo: solo com Ca=25, Mg=9, K=3, H+Al=40, Al=2 mmolc/dm3, pH CaCl2 5,2
    print("== Exemplo de análise de solo (Boletim 100) ==")
    for chave, valor in analise_completa(ca=25, mg=9, k=3, h_al=40, al=2, ph_cacl2=5.2).items():
        print(f"  {chave}: {valor}")
    print("\n== Conversões (Quadro 3.1) ==")
    print("  60 mg/dm3 de P  ->", round(60 * FATORES_INV['P_para_P2O5'], 1), "mg/dm3 de P2O5")
    print("  3 mmolc/dm3 de K ->", round(3 * FATORES_INV['K_para_K2O'], 2), "(fator óxido)")
