#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adubacao_npk.py — 5a Aproximação (CFSEMG/MG), Cap. 6 (Relações básicas entre nutrientes).
Converte a recomendação N:P2O5:K2O (kg/ha) em quantidade de fertilizantes,
seja por mistura de adubos simples, seja por fórmula comercial, e distribui
por metro de sulco ou por cova.

Referência: Ribeiro, Guimarães & Alvarez V. (eds., 1999), 5a Aproximação, CFSEMG.

Uso rápido:
    python adubacao_npk.py
"""
from __future__ import annotations
from math import gcd
from functools import reduce

# Teores comerciais usuais (dag/kg = %); ajuste conforme o rótulo do produto
FONTES = {
    "ureia":               {"N": 44},
    "sulfato de amonio":   {"N": 20, "S": 24},
    "superfosfato simples":{"P2O5": 18, "Ca": 16, "S": 12},
    "superfosfato triplo": {"P2O5": 41, "Ca": 14},
    "map":                 {"N": 11, "P2O5": 52},
    "cloreto de potassio": {"K2O": 58},
    "sulfato de potassio": {"K2O": 50, "S": 17},
}


def qtd_fertilizante(dose_nutriente: float, teor_pct: float) -> float:
    """kg de fertilizante = dose do nutriente (kg/ha) / (teor%/100)."""
    if teor_pct <= 0:
        raise ValueError("teor deve ser > 0")
    return round(dose_nutriente * 100.0 / teor_pct, 1)


def mistura_simples(n: float, p2o5: float, k2o: float,
                    fonte_n="ureia", fonte_p="superfosfato simples",
                    fonte_k="cloreto de potassio") -> dict:
    """Mistura de adubos simples para atender N:P2O5:K2O (kg/ha)."""
    qn = qtd_fertilizante(n, FONTES[fonte_n]["N"]) if n else 0.0
    qp = qtd_fertilizante(p2o5, FONTES[fonte_p]["P2O5"]) if p2o5 else 0.0
    qk = qtd_fertilizante(k2o, FONTES[fonte_k]["K2O"]) if k2o else 0.0
    return {
        fonte_n: qn, fonte_p: qp, fonte_k: qk,
        "total_kg_ha": round(qn + qp + qk, 1),
    }


def razao_npk(n: float, p2o5: float, k2o: float) -> tuple:
    """Reduz a recomendação (ou uma fórmula) à menor razão inteira quando possível.
    Ex.: 20:80:40 -> 1:4:2 ; 24:8:12 -> 3:1:1,5."""
    vals = [n, p2o5, k2o]
    nz = [v for v in vals if v > 0]
    if not nz:
        return (0, 0, 0)
    menor = min(nz)
    return tuple(round(v / menor, 2) for v in vals)


def quantidade_formula(n: float, p2o5: float, k2o: float, formula: tuple) -> float:
    """kg/ha de uma fórmula (fn, fp, fk) para suprir a recomendação N:P2O5:K2O.
    Só é válido quando as razões coincidem. Usa o 1o nutriente não nulo."""
    alvo = [n, p2o5, k2o]
    for dose, teor in zip(alvo, formula):
        if dose > 0 and teor > 0:
            return round(dose / teor * 100.0, 1)
    raise ValueError("Fórmula/recomendação incompatível")


def por_metro_de_sulco(qtd_kg_ha: float, espacamento_entrelinhas_m: float) -> dict:
    """g/m de sulco a partir de kg/ha e do espaçamento entre linhas (m)."""
    metros_sulco_ha = 10000.0 / espacamento_entrelinhas_m   # m de sulco em 1 ha
    g_por_m = qtd_kg_ha * 1000.0 / metros_sulco_ha
    return {"m_sulco_por_ha": round(metros_sulco_ha, 0), "g_por_m": round(g_por_m, 1)}


def por_cova(qtd_kg_ha: float, esp_entrelinhas_m: float, esp_na_linha_m: float) -> dict:
    """g/cova a partir de kg/ha e do espaçamento (entrelinhas x na linha)."""
    area_cova = esp_entrelinhas_m * esp_na_linha_m
    covas_ha = 10000.0 / area_cova
    g_por_cova = qtd_kg_ha * 1000.0 / covas_ha
    return {"covas_por_ha": round(covas_ha, 0), "g_por_cova": round(g_por_cova, 2)}


if __name__ == "__main__":
    # Exemplo do boletim (Cap. 6): recomendação 20:80:40 kg/ha de N:P2O5:K2O
    print("== Mistura de adubos simples (20:80:40) ==")
    m = mistura_simples(20, 80, 40)
    for k, v in m.items():
        print(f"  {k}: {v}")
    print("  (esperado ~45,5 ureia + 444,4 SS + 69 KCl = 558,9 kg/ha)")

    print("\n== Razão e fórmula comercial ==")
    print("  Razão 20:80:40 ->", razao_npk(20, 80, 40), "(esperado 1,0 : 4,0 : 2,0)")
    q = quantidade_formula(20, 80, 40, (4, 16, 8))
    print(f"  Fórmula 4-16-8 -> {q} kg/ha  (esperado 500)")

    print("\n== Distribuição (milho, 0,8 x 0,2 m) ==")
    print("  Mistura:", por_metro_de_sulco(558.9, 0.8))
    print("  Fórmula 4-16-8:", por_metro_de_sulco(500, 0.8), "(esperado ~40 g/m)")
    print("  Fórmula 4-16-8 por cova:", por_cova(500, 0.8, 0.2), "(esperado ~8 g/cova)")
