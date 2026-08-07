#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calagem.py — 5a Aproximação (CFSEMG/MG), Cap. 8.
Necessidade de calagem por DOIS métodos oficiais e quantidade real de calcário.

Unidades: cátions (Al, Ca, Mg, K, Na, H+Al, t, T) em cmolc/dm3.
NC em t/ha equivale a CaCO3 (PRNT = 100 %) incorporado na camada 0-20 cm
(1 ha = 2.000.000 dm3).

Método 8.2.1 — Neutralização do Al3+ e elevação de Ca2+ + Mg2+:
    NC = Y * [Al3+ - (mt * t / 100)] + [X - (Ca2+ + Mg2+)]
       CA = Y * [Al3+ - (mt*t/100)]           (se < 0, usar 0)
       CD = X - (Ca2+ + Mg2+)                 (se < 0, usar 0)
    Y (capacidade tampão) por argila:  Y = 0,0302 + 0,06532*Arg - 0,000257*Arg^2
    Y (capacidade tampão) por P-rem:   Y = 4,002 - 0,125901*Prem + 0,001205*Prem^2 - 0,00000362*Prem^3
    mt = máxima saturação por Al tolerada pela cultura (%)  [Quadro 8.1]
    X  = teor mínimo desejado de Ca+Mg (cmolc/dm3)          [Quadro 8.1]
    t  = CTC efetiva = SB + Al3+

Método 8.2.2 — Saturação por bases:
    NC = T * (Ve - Va) / 100 = (Ve/100)*T - SB
       T  = CTC a pH 7 = SB + (H+Al)
       Va = 100*SB/T ; Ve = saturação desejada pela cultura (%) [Quadro 8.1]

Quantidade real de calcário (8.3):
    QC = NC * (SC/100) * (PF/20) * (100/PRNT)
       SC = % da superfície coberta ; PF = profundidade de incorporação (cm) ;
       PRNT = poder relativo de neutralização total do corretivo (%).

Referência: Ribeiro, A.C.; Guimarães, P.T.G.; Alvarez V., V.H. (eds., 1999).
Recomendações para o uso de corretivos e fertilizantes em Minas Gerais —
5a Aproximação. CFSEMG, Viçosa.

Uso rápido:
    python calagem.py
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Capacidade tampão da acidez (Y) — método 8.2.1
# ---------------------------------------------------------------------------
def Y_por_argila(argila_pct: float) -> float:
    """Y = 0,0302 + 0,06532*Arg - 0,000257*Arg^2  (Arg = argila em %)."""
    a = argila_pct
    return 0.0302 + 0.06532 * a - 0.000257 * a ** 2


def Y_por_prem(prem: float) -> float:
    """Y = 4,002 - 0,125901*Prem + 0,001205*Prem^2 - 0,00000362*Prem^3 (P-rem em mg/L)."""
    p = prem
    return 4.002 - 0.125901 * p + 0.001205 * p ** 2 - 0.00000362 * p ** 3


# ---------------------------------------------------------------------------
# Método 8.2.1 — Al3+ e Ca2+ + Mg2+
# ---------------------------------------------------------------------------
def nc_al_camg(al: float, ca: float, mg: float, t: float,
               mt: float, X: float, Y: float) -> dict:
    """NC (t/ha) pelo método do Al e do Ca+Mg trocáveis.

    al : acidez trocável Al3+ (cmolc/dm3)
    ca, mg : Ca2+ e Mg2+ trocáveis (cmolc/dm3)
    t  : CTC efetiva = SB + Al3+ (cmolc/dm3)
    mt : máxima saturação por Al tolerada pela cultura (%)  [Quadro 8.1]
    X  : teor mínimo desejado de Ca+Mg (cmolc/dm3)          [Quadro 8.1]
    Y  : capacidade tampão (use Y_por_argila ou Y_por_prem)
    """
    ca_corr = Y * (al - (mt * t / 100.0))     # correção da acidez
    cd = X - (ca + mg)                        # correção da deficiência de Ca+Mg
    ca_corr = max(ca_corr, 0.0)
    cd = max(cd, 0.0)
    nc = ca_corr + cd
    return {"CA": round(ca_corr, 3), "CD": round(cd, 3), "NC_t_ha": round(nc, 2)}


# ---------------------------------------------------------------------------
# Método 8.2.2 — Saturação por bases
# ---------------------------------------------------------------------------
def nc_saturacao(sb: float, h_al: float, ve: float) -> dict:
    """NC (t/ha) = (Ve/100)*T - SB, com T = SB + (H+Al).

    sb   : soma de bases atual (Ca+Mg+K+Na), cmolc/dm3
    h_al : acidez potencial H+Al, cmolc/dm3
    ve   : saturação por bases desejada pela cultura (%)  [Quadro 8.1]
    """
    T = sb + h_al
    va = 100.0 * sb / T if T > 0 else 0.0
    nc = (ve / 100.0) * T - sb
    return {"T": round(T, 2), "Va_%": round(va, 1), "NC_t_ha": round(max(nc, 0.0), 2)}


# ---------------------------------------------------------------------------
# Quantidade real de calcário (8.3)
# ---------------------------------------------------------------------------
def quantidade_calcario(nc: float, sc: float = 100.0, pf: float = 20.0,
                        prnt: float = 100.0) -> float:
    """QC (t/ha) = NC * (SC/100) * (PF/20) * (100/PRNT)."""
    if prnt <= 0:
        raise ValueError("PRNT deve ser > 0")
    return round(nc * (sc / 100.0) * (pf / 20.0) * (100.0 / prnt), 3)


# ---------------------------------------------------------------------------
# Quadro 8.1 — mt (%), X (cmolc/dm3) e Ve (%) por cultura (subconjunto amplo)
# ---------------------------------------------------------------------------
# chave: nome simples ; valor: (mt, X, Ve, observação)
QUADRO_8_1 = {
    # Cereais
    "arroz sequeiro": (25, 2.0, 50, "não usar mais de 3 t/ha por aplicação"),
    "arroz irrigado": (25, 2.0, 50, "não usar mais de 4 t/ha por aplicação"),
    "milho": (15, 2.0, 50, "não usar mais de 6 t/ha por aplicação"),
    "sorgo": (15, 2.0, 50, "não usar mais de 6 t/ha por aplicação"),
    "trigo": (15, 2.0, 50, "sequeiro ou irrigado; máx 4 t/ha por aplicação"),
    # Leguminosas / oleaginosas / fibrosas
    "feijao": (20, 2.0, 50, ""),
    "soja": (20, 2.0, 50, ""),
    "adubos verdes": (20, 2.0, 50, ""),
    "amendoim": (5, 3.0, 70, ""),
    "mamona": (10, 2.5, 60, ""),
    "algodao": (10, 2.5, 60, "usar calcário com magnésio"),
    # Industriais
    "cafe": (25, 3.5, 60, ""),
    "cana-de-acucar": (30, 3.5, 60, "não usar mais de 10 t/ha por aplicação"),
    "cha": (25, 1.5, 40, ""),
    # Raízes e tubérculos
    "batata": (15, 2.0, 60, "exigente em magnésio"),
    "batata-doce": (15, 2.0, 60, "exigente em magnésio"),
    "mandioca": (30, 1.0, 40, "não usar mais de 2 t/ha por aplicação"),
    "cara": (10, 2.5, 60, "exigente em magnésio"),
    "inhame": (10, 2.5, 60, "exigente em magnésio"),
    # Tropicais
    "cacau": (15, 2.0, 50, ""),
    "seringueira": (25, 1.0, 50, "usar calcário dolomítico; máx 2 t/ha"),
    "pimenta-do-reino": (5, 3.0, 70, ""),
    # Hortaliças (amostra)
    "tomate": (5, 3.0, 70, "utilizar relação Ca/Mg = 1"),
    "pimentao": (5, 3.0, 70, ""),
    "alface": (5, 3.0, 70, "exigente em magnésio"),
    "melancia": (5, 3.0, 70, "exigente em magnésio"),
    "melao": (5, 3.5, 80, "exigente em magnésio"),
    "chuchu": (5, 3.5, 80, "exigente em magnésio"),
    "milho verde": (10, 2.5, 60, ""),
    "cenoura": (5, 3.0, 65, "exigente em magnésio"),
    "beterraba": (5, 3.0, 65, "exigente em magnésio"),
    "repolho": (5, 3.0, 70, "exigente em magnésio"),
    "couve-flor": (5, 3.0, 70, "exigente em magnésio"),
    "alho": (5, 3.0, 70, ""),
    "cebola": (5, 3.0, 70, ""),
    "morango": (5, 3.0, 70, "exigente em magnésio"),
    # Fruteiras
    "abacaxi": (15, 2.0, 50, ""),
    "banana": (10, 3.0, 70, "usar calcário dolomítico"),
    "citros": (5, 3.0, 70, ""),
    "mamao": (5, 3.5, 80, ""),
    "abacate": (10, 2.5, 60, ""),
    "manga": (10, 2.5, 60, ""),
    "maracuja": (5, 3.0, 70, ""),
    "goiaba": (5, 3.0, 70, ""),
    "videira": (5, 3.5, 80, ""),
    "pessego": (5, 3.0, 70, ""),
    "maca": (5, 3.0, 70, ""),
    # Aromáticas / florestais
    "fumo": (15, 2.0, 50, "Mg mínimo 0,5 cmolc/dm3"),
    "eucalipto": (30, 1.5, 40, "plantios de eucalipto: mt 45 / X 1,0 / Ve 30"),
    # Pastagens (amostra)
    "alfafa": (15, 2.5, 60, "pastagem leguminosa"),
    "leucena": (15, 2.5, 60, "pastagem leguminosa"),
    "estilosantes": (25, 1.0, 40, "pastagem leguminosa"),
    "capim-elefante": (20, 2.0, 50, "gramínea forrageira"),
    "coast-cross": (20, 2.0, 50, "gramínea forrageira"),
    "colonião": (20, 2.0, 50, "gramínea forrageira"),
    "mombaca": (25, 1.5, 45, "gramínea forrageira"),
    "tanzania": (25, 1.5, 45, "gramínea forrageira"),
    "braquiarao": (25, 1.5, 45, "Brachiaria brizantha / marandu"),
    "braquiaria decumbens": (30, 1.0, 40, "gramínea forrageira"),
    "brachiaria humidicola": (30, 1.0, 40, "gramínea forrageira"),
}


def parametros_cultura(nome: str):
    """Retorna (mt, X, Ve, obs) do Quadro 8.1 para a cultura (busca simples)."""
    n = nome.strip().lower()
    if n in QUADRO_8_1:
        return QUADRO_8_1[n]
    for k, v in QUADRO_8_1.items():
        if n in k or k in n:
            return v
    raise KeyError(f"Cultura '{nome}' não encontrada no Quadro 8.1 (subconjunto). "
                   f"Consulte references/interpretacao-solo.md para a tabela completa.")


if __name__ == "__main__":
    # Exemplo do próprio boletim (p.52): cafeeiro, argila 60%, P-rem 9,4,
    # Al=0,8; Ca=0,1; Mg=0,1; H+Al=7,8; SB=0,21; t=1,01; T=8,01; V=2,6%.
    print("== Café — exemplo do boletim (Cap. 8) ==")
    mt, X, Ve, obs = parametros_cultura("cafe")
    print(f"  Quadro 8.1 -> mt={mt}%  X={X}  Ve={Ve}%")

    Ya = Y_por_argila(60)
    r1 = nc_al_camg(al=0.8, ca=0.1, mg=0.1, t=1.01, mt=mt, X=X, Y=3.0)
    print(f"  Método 8.2.1 (Y=3,0 por argila 60%): NC = {r1['NC_t_ha']} t/ha  (esperado ~4,94)")

    Yp = Y_por_prem(9.4)
    r2 = nc_al_camg(al=0.8, ca=0.1, mg=0.1, t=1.01, mt=mt, X=X, Y=round(Yp, 2))
    print(f"  Método 8.2.1 (Y={Yp:.2f} por P-rem 9,4): NC = {r2['NC_t_ha']} t/ha  (esperado ~4,92)")

    r3 = nc_saturacao(sb=0.21, h_al=7.8, ve=Ve)
    print(f"  Método 8.2.2 (saturação, Ve={Ve}%): NC = {r3['NC_t_ha']} t/ha  (esperado ~4,6)")

    print("\n== Quantidade real de calcário (8.3) ==")
    qc = quantidade_calcario(nc=6, sc=75, pf=5, prnt=90)
    print(f"  NC=6, SC=75%, PF=5cm, PRNT=90% -> QC = {qc} t/ha  (esperado ~1,25)")
