#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gessagem.py — 5a Aproximação (CFSEMG/MG), Cap. 10.
Necessidade de gesso agrícola (NG) para correção de camadas subsuperficiais
e quantidade real de gesso (QG).

Critério para indicar gesso (camada de 20-40 cm ou 30-60 cm):
    Ca2+ <= 0,4 cmolc/dm3  E/OU  Al3+ > 0,5 cmolc/dm3  E/OU  m > 30%.

Método 10.3.1 — por textura (argila da camada subsuperficial, X em %):
    NG (t/ha) = 0,00034 - 0,002445*X^0,5 + 0,0338886*X - 0,00176366*X^1,5
    (NG refere-se a camada de 20 cm de espessura)

Método 10.3.2 — por P-rem da camada subsuperficial (mg/L):
    Ca (kg/ha) = 315,8 - 25,5066*Prem^0,5 - 5,70675*Prem + 0,485335*Prem^1,5
    NG (t/ha)  = Ca / (10 * TCa)     TCa = teor de Ca do gesso (dag/kg; padrão 18,75)

Método 10.3.3 — a partir da NC da camada subsuperficial:
    NG (t/ha) = 0,25 * NC

Quantidade real de gesso (QG):
    QG (t/ha) = NG * (SC/100) * (EC/20)
       SC = % da superfície coberta ; EC = espessura da camada a corrigir (cm).

Gesso agrícola padrão: ~15 dag/kg de S e ~18,75 dag/kg de Ca (Quadro 10.2).

Referência: Ribeiro, Guimarães & Alvarez V. (eds., 1999), 5a Aproximação, CFSEMG.

Uso rápido:
    python gessagem.py
"""
from __future__ import annotations

TCa_PADRAO = 18.75  # dag/kg de Ca no gesso agrícola


def indicar_gesso(ca_sub: float | None = None, al_sub: float | None = None,
                  m_sub: float | None = None) -> bool:
    """Indica gesso quando, na camada subsuperficial:
    Ca2+ <= 0,4 e/ou Al3+ > 0,5 cmolc/dm3 e/ou m > 30%."""
    if ca_sub is not None and ca_sub <= 0.4:
        return True
    if al_sub is not None and al_sub > 0.5:
        return True
    if m_sub is not None and m_sub > 30:
        return True
    return False


def ng_por_argila(argila_pct: float) -> float:
    """NG (t/ha) por textura, camada de 20 cm de espessura."""
    x = argila_pct
    return round(0.00034 - 0.002445 * x ** 0.5 + 0.0338886 * x - 0.00176366 * x ** 1.5, 3)


def ng_por_prem(prem: float, tca: float = TCa_PADRAO) -> dict:
    """NG (t/ha) a partir do P-rem (mg/L) e do teor de Ca do gesso (dag/kg)."""
    p = prem
    ca_kg_ha = 315.8 - 25.5066 * p ** 0.5 - 5.70675 * p + 0.485335 * p ** 1.5
    ng = ca_kg_ha / (10.0 * tca)
    return {"Ca_kg_ha": round(ca_kg_ha, 1), "NG_t_ha": round(ng, 3)}


def ng_por_nc(nc: float) -> float:
    """NG (t/ha) = 0,25 * NC (NC da camada subsuperficial, t/ha)."""
    return round(0.25 * nc, 3)


def quantidade_gesso(ng: float, ec: float = 20.0, sc: float = 100.0) -> float:
    """QG (t/ha) = NG * (SC/100) * (EC/20).  EC = espessura da camada (cm)."""
    return round(ng * (sc / 100.0) * (ec / 20.0), 3)


if __name__ == "__main__":
    print("== Indicação de gesso (camada subsuperficial) ==")
    print("  Ca=0,3 / Al=0,6 / m=35% ->", indicar_gesso(ca_sub=0.3, al_sub=0.6, m_sub=35))

    print("\n== Método por textura (argila 45%) — exemplo do boletim ==")
    ng = ng_por_argila(45)
    print(f"  NG = {ng} t/ha  (esperado ~0,977)")
    print(f"  QG p/ camada 20-50 cm (EC=30), SC=75%: {quantidade_gesso(ng, ec=30, sc=75)} t/ha  (esperado ~1,10)")

    print("\n== Método por P-rem (P-rem 15) — exemplo do boletim ==")
    r = ng_por_prem(15)
    print(f"  Ca = {r['Ca_kg_ha']} kg/ha -> NG = {r['NG_t_ha']} t/ha  (esperado ~0,851)")
    print(f"  QG p/ EC=35, SC=75%: {quantidade_gesso(r['NG_t_ha'], ec=35, sc=75)} t/ha  (esperado ~1,12)")

    print("\n== Método a partir da NC (NC=4,8) — exemplo do boletim ==")
    ngc = ng_por_nc(4.8)
    print(f"  NG = {ngc} t/ha -> QG p/ EC=35: {quantidade_gesso(ngc, ec=35)} t/ha  (esperado ~2,1)")
