#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calagem.py — Boletim 100 (IAC/SP), Cap. 6.
Necessidade de calagem pelo método da SATURAÇÃO POR BASES, qualidade de
corretivos (PN, PRNT, RE) e necessidade de gesso para o subsolo.

Fórmulas (Boletim 100, 2a ed.):
  NC (t/ha) = CTC * (V2 - V1) / (10 * PRNT)
      CTC em mmolc/dm3 ; V1, V2 e PRNT em % ; profundidade padrão 0-20 cm.
      Se o PRNT não for conhecido, adota-se PRNT = 67% (calcário moído).
      Arredondar para inteiro; não aplicar menos de 1 t/ha.

  PN (%)  = CaO(%) * 1,79 + MgO(%) * 2,48
  RE (%)  = 0,2*x + 0,6*y + z     (x=% retido ABNT nº20; y=% retido ABNT nº50;
                                   z=% que passa ABNT nº50; retido ABNT nº10 = 0)
  PRNT (%) = PN * RE / 100

  Gesso (subsolo): NG (kg/ha) = 6 * argila(g/kg)
      Indicado quando Ca2+ < 4 mmolc/dm3 e/ou saturação por Al (m) > 40%.

Versão no Sistema Internacional (Cap. 6.5):
  PN (molc/kg) = Ca/20,0 + Mg/12,2      (Ca, Mg em g/kg do corretivo)
  RE           = (0,2x + 0,6y + z)/1000
  PNE          = PN * RE
  NC (t/ha)    = 2 * CTC * (V2 - V1) / (100 * PNE)

Uso rápido:
    python calagem.py
"""
from __future__ import annotations
import math

PRNT_PADRAO = 67.0  # % — valor médio para calcário moído quando não determinado


# ---------------------------------------------------------------------------
# Necessidade de calagem — método da saturação por bases
# ---------------------------------------------------------------------------
def necessidade_calagem(ctc: float, v1: float, v2: float,
                        prnt: float = PRNT_PADRAO,
                        arredondar: bool = True) -> float:
    """NC (t/ha) = CTC * (V2 - V1) / (10 * PRNT).

    ctc  : CTC a pH 7 (T), em mmolc/dm3
    v1   : saturação por bases atual (%)
    v2   : saturação por bases desejada para a cultura (%)  (ver tabelas por cultura)
    prnt : poder relativo de neutralização total do corretivo (%)
    """
    if prnt <= 0:
        raise ValueError("PRNT deve ser > 0")
    nc = ctc * (v2 - v1) / (10.0 * prnt)
    if nc <= 0:
        return 0.0
    if arredondar:
        nc = math.ceil(nc)          # arredonda para cima
        nc = max(nc, 1.0)           # nunca aplicar menos de 1 t/ha
    return round(nc, 2)


def necessidade_calagem_SI(ctc: float, v1: float, v2: float, pne: float) -> float:
    """Versão no Sistema Internacional: NC = 2*CTC*(V2-V1)/(100*PNE).
    'pne' (poder de neutralização efetivo) em molc/kg."""
    if pne <= 0:
        raise ValueError("PNE deve ser > 0")
    nc = 2.0 * ctc * (v2 - v1) / (100.0 * pne)
    return round(max(nc, 0.0), 2)


# ---------------------------------------------------------------------------
# Qualidade do corretivo — PN, RE, PRNT
# ---------------------------------------------------------------------------
def poder_neutralizacao(cao_pct: float, mgo_pct: float) -> float:
    """PN (% equiv. CaCO3) = CaO(%)*1,79 + MgO(%)*2,48."""
    return cao_pct * 1.79 + mgo_pct * 2.48


def reatividade(x_ret20: float, y_ret50: float, z_passa50: float) -> float:
    """RE (%) = 0,2*x + 0,6*y + z.
    x = % retido na peneira ABNT nº20 (0,84 mm)
    y = % retido na peneira ABNT nº50 (0,30 mm)
    z = % que passa na peneira ABNT nº50
    (o material retido na ABNT nº10 / 2 mm tem reatividade nula)."""
    return 0.2 * x_ret20 + 0.6 * y_ret50 + z_passa50


def prnt(pn: float, re: float) -> float:
    """PRNT (%) = PN * RE / 100."""
    return pn * re / 100.0


def pn_SI(ca_g_kg: float, mg_g_kg: float) -> float:
    """PN (molc/kg) = Ca/20,0 + Mg/12,2  (Ca, Mg em g/kg do corretivo)."""
    return ca_g_kg / 20.0 + mg_g_kg / 12.2


# ---------------------------------------------------------------------------
# Gesso agrícola para o subsolo (Cap. 6.4)
# ---------------------------------------------------------------------------
def necessidade_gesso(argila_g_kg: float) -> float:
    """NG (kg/ha) = 6 * argila(g/kg)."""
    return round(6.0 * argila_g_kg, 1)


def indicar_gesso(ca_mmolc: float | None = None, m_pct: float | None = None) -> bool:
    """Indica gesso quando Ca2+ < 4 mmolc/dm3 e/ou saturação por Al (m) > 40%."""
    cond = False
    if ca_mmolc is not None and ca_mmolc < 4:
        cond = True
    if m_pct is not None and m_pct > 40:
        cond = True
    return cond


if __name__ == "__main__":
    print("== Necessidade de calagem (saturação por bases) ==")
    # Ex.: CTC=52 mmolc/dm3, V1=45%, meta V2=70%, calcário PRNT=80%
    nc = necessidade_calagem(ctc=52, v1=45, v2=70, prnt=80)
    print(f"  CTC=52, V1=45%, V2=70%, PRNT=80% -> NC = {nc} t/ha")
    nc2 = necessidade_calagem(ctc=52, v1=45, v2=70)  # PRNT padrão 67%
    print(f"  Mesmo solo, PRNT não informado (67%) -> NC = {nc2} t/ha")

    print("\n== Qualidade do corretivo ==")
    pn = poder_neutralizacao(cao_pct=30, mgo_pct=18)
    re = reatividade(x_ret20=20, y_ret50=20, z_passa50=55)
    print(f"  PN={pn:.1f}%  RE={re:.1f}%  PRNT={prnt(pn, re):.1f}%")

    print("\n== Gesso para subsolo ==")
    print("  Indicado?", indicar_gesso(ca_mmolc=3, m_pct=45))
    print(f"  argila=350 g/kg -> NG = {necessidade_gesso(350)} kg/ha")
