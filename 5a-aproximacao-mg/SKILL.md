---
name: 5a-aproximacao-mg
description: >-
  Recomendações para o uso de corretivos e fertilizantes em Minas Gerais
  (5ª Aproximação, CFSEMG, 1999). Use para interpretar análise de solo
  (P por argila/P-rem, K, Ca, Mg, S, micros, m%, V%), calcular calagem por
  DOIS métodos (Al+Ca/Mg e saturação por bases), gesso agrícola, mistura/
  fórmula NPK, e recomendar N-P-K e demais elementos por cultura (hortaliças,
  frutíferas, grandes culturas, floricultura, pastagens). Acione com laudo de
  solo de MG/cerrado ou pedido de "adubação/calagem pela 5ª Aproximação".
---

# 5ª Aproximação (CFSEMG/MG) — Corretivos e Fertilizantes em Minas Gerais

Skill que operacionaliza as **Recomendações para o uso de corretivos e fertilizantes
em Minas Gerais — 5ª Aproximação** (Ribeiro, Guimarães & Alvarez V., eds., CFSEMG,
Viçosa, 1999) — a referência oficial de fertilidade para MG e muito usada no cerrado.

## Para que serve
- Interpretar laudos no padrão CFSEMG (classes Muito baixo → Muito bom).
- Calcular **necessidade de calagem** pelos **dois métodos oficiais**:
  (1) neutralização do Al³⁺ e elevação de Ca+Mg; (2) saturação por bases.
- Calcular **gesso agrícola** por textura, por P-rem ou a partir da NC; e a quantidade real (QC/QG).
- Converter recomendação **N:P₂O₅:K₂O** em mistura de simples ou fórmula comercial, com distribuição por sulco/cova.
- Recomendar **N, P, K, S, Ca, Mg e micronutrientes por cultura**, ajustando a dose pela classe, textura e P-rem.

## Para que NÃO serve
- Não é para **São Paulo** pelo Boletim 100 → use a skill `boletim-100-sp`.
- Não substitui a análise de solo de laboratório nem o agrônomo responsável (ART).
- Não recomenda sem dados de solo; não cobre culturas ausentes do boletim.

## Fluxo de trabalho (siga nesta ordem)

1. **Receba o laudo** (cátions em cmolc/dm³; P/K/S/micros em mg/dm³; argila em % e/ou P-rem em mg/L).
2. **Calcule os índices** SB, t (CTC efetiva), T (CTC pH7), V% e m% → `scripts/fertilidade_solo.py`.
3. **Classifique** cada elemento (Quadros 5.1–5.5) — P por **argila ou P-rem**, K, S por P-rem, Ca, Mg, micros → `references/interpretacao-solo.md`.
4. **Calagem:** obtenha `mt`, `X` e `Ve` da cultura (Quadro 8.1, em `scripts/calagem.py`).
   - Método 8.2.1: `NC = Y·[Al − mt·t/100] + [X − (Ca+Mg)]` (Y por argila ou P-rem).
   - Método 8.2.2: `NC = (Ve/100)·T − SB`.
   - Escolha o método (ou compare os dois) e calcule a **quantidade real** `QC` (SC, PF, PRNT).
5. **Gesso (se preciso):** subsolo com Ca²⁺ ≤ 0,4 e/ou Al³⁺ > 0,5 cmolc/dm³ e/ou m > 30% → `scripts/gessagem.py` (por textura, P-rem ou 0,25·NC) e `QG`.
6. **Adubação:** dose básica da cultura (`references/culturas-*.md`) **ajustada** pela classe, textura e P-rem (`scripts/fertilidade_solo.py`), incluindo **S, Ca, Mg e micronutrientes**.
7. **Fertilizante:** converta N:P₂O₅:K₂O em mistura de simples ou fórmula e distribua por sulco/cova → `scripts/adubacao_npk.py`.

> **Sempre cite o quadro e a página**, explique a classe e diga qual método de calagem foi usado.
> Nunca invente números; onde a tabela do PDF estiver ambígua, sinalize.

## Scripts (Python, sem dependências externas)
| Script | O que faz |
|---|---|
| `scripts/fertilidade_solo.py` | SB, t, T, V%, m%; classificação (Quadros 5.2/5.3); fatores de ajuste de dose por classe/textura/P-rem. |
| `scripts/calagem.py` | NC pelos dois métodos + `Y_por_argila`/`Y_por_prem`; `QC`; Quadro 8.1 (mt, X, Ve) por cultura. |
| `scripts/gessagem.py` | Indicação e NG por textura, por P-rem e por 0,25·NC; `QG`. |
| `scripts/adubacao_npk.py` | Mistura de simples, razão/fórmula NPK, g/m de sulco e g/cova. |

Rodar: `python scripts/calagem.py` (traz os exemplos resolvidos do próprio boletim, já validados).

## Referências (tabelas transcritas do boletim)
- `references/interpretacao-solo.md` — Quadros 5.1–5.5 (acidez, MO, complexo de troca, P por argila/P-rem, K, S, micros) + fatores de ajuste de dose.
- `references/diagnose-foliar.md` — padrões de referência foliar (Cap. 17).
- `references/culturas-hortalicas.md` — item 18.1.
- `references/culturas-frutiferas.md` — item 18.2.
- `references/culturas-floricultura.md` — item 18.3.
- `references/culturas-grandes-culturas.md` — item 18.4 (grãos, café, cana, algodão, etc.).
- `references/culturas-pastagens.md` — item 18.5.

## Fórmulas-chave (referência rápida)
- **Índices:** SB=Ca+Mg+K+Na · t=SB+Al · T=SB+(H+Al) · V=100·SB/T · m=100·Al/t.
- **Calagem 8.2.1:** `NC = Y·[Al − mt·t/100] + [X − (Ca+Mg)]` (CA e CD nunca negativos).
  - Y(argila) = 0,0302 + 0,06532·Arg − 0,000257·Arg² · Y(P-rem) = 4,002 − 0,125901·P + 0,001205·P² − 0,00000362·P³.
- **Calagem 8.2.2:** `NC = (Ve/100)·T − SB`.
- **Quantidade real:** `QC = NC·(SC/100)·(PF/20)·(100/PRNT)`.
- **Gesso:** por textura `NG = 0,00034 − 0,002445·√X + 0,0338886·X − 0,00176366·X^1,5`; ou `NG = 0,25·NC`; `QG = NG·(SC/100)·(EC/20)`.

## Escopo / avisos
Recomendação técnica de referência; decisão final do **engenheiro agrônomo** responsável.
Válido para Minas Gerais; a base por P-rem é especialmente útil em solos de cerrado.
