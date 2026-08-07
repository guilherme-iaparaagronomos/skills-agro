---
name: boletim-100-sp
description: >-
  Recomendações de adubação e calagem para o Estado de São Paulo (Boletim 100,
  IAC). Use para interpretar análise de solo (P resina, K, Ca, Mg, S, micros,
  V%, pH CaCl2), calcular necessidade de calagem pela saturação por bases,
  qualidade de corretivos (PN/PRNT/RE), gesso, e recomendar N-P-K e demais
  elementos por cultura (milho, soja, cana, mandioca, forrageiras, eucalipto,
  etc.). Acione quando o usuário trouxer laudo de solo do estado de SP ou pedir
  "adubação/calagem pelo Boletim 100".
---

# Boletim 100 (IAC/SP) — Adubação e Calagem para São Paulo

Skill que operacionaliza o **Boletim Técnico 100 do Instituto Agronômico (IAC)**,
2ª edição (van Raij, Cantarella, Quaggio & Furlani, 1997) — a referência oficial
de recomendação de adubação e calagem para o Estado de São Paulo.

## Para que serve
- Interpretar laudos de análise de solo no padrão do IAC (SP).
- Calcular **necessidade de calagem** pela saturação por bases (V%).
- Avaliar **qualidade de corretivos** (PN, PRNT, RE) e **gesso** para subsolo.
- Recomendar **N, P₂O₅, K₂O, S, Ca, Mg e micronutrientes por cultura**, com metas
  de V₂ e doses por classe de teor e por produtividade esperada.
- Apoiar diagnose foliar das culturas cobertas.

## Para que NÃO serve
- Não é para **Minas Gerais** nem cerrado por P-rem → use a skill `5a-aproximacao-mg`.
- Não substitui a análise de solo de laboratório nem o agrônomo responsável (ART).
- Não cobre culturas ausentes do boletim; não faz recomendação sem dados de solo.
- Não é modelo agroclimático nem de produtividade — a produtividade esperada é entrada do usuário.

## Fluxo de trabalho (siga nesta ordem)

1. **Receba o laudo** (unidades do IAC: cátions em mmolc/dm³; P/S/micros em mg/dm³; pH CaCl₂; MO e argila em g/kg). Se vier em unidades antigas, converta com o Quadro 3.1 (`fertilidade_solo.py`).
2. **Calcule os índices** SB, CTC (T e efetiva), V% e m% → `scripts/fertilidade_solo.py`.
3. **Classifique cada elemento** (P, K, Ca, Mg, S, B, Cu, Fe, Mn, Zn, acidez) com `references/interpretacao-solo.md`.
4. **Calagem:** pegue a **meta V₂ da cultura** (nas referências `culturas-*.md`) e calcule NC → `scripts/calagem.py`. Verifique qualidade do corretivo (PRNT) e a dose real.
5. **Gesso (se preciso):** subsolo com Ca²⁺ < 4 mmolc/dm³ e/ou m > 40% → `NG = 6 × argila`.
6. **Adubação:** para a cultura, use as doses de N (classe de resposta + produtividade esperada), P₂O₅ e K₂O (por classe de teor), **S, Ca, Mg e micronutrientes** conforme a tabela da cultura em `references/culturas-*.md`.
7. **Implementação:** monte fórmula NPK / mistura de simples e defina modo e época de aplicação.

> **Sempre cite o quadro/tabela e a página** de origem, e explique a classe encontrada
> (ex.: "P resina 8 mg/dm³ → classe Média para anuais → dose X"). Nunca invente números.

## Scripts (Python, sem dependências externas)
| Script | O que faz |
|---|---|
| `scripts/fertilidade_solo.py` | SB, CTC (T/efetiva), V%, m%, diagnóstico de acidez, conversão de unidades (Quadro 3.1). |
| `scripts/calagem.py` | NC pela saturação por bases (padrão e SI); PN/PRNT/RE; gesso `NG=6×argila`; critério de gesso. |

Rodar: `python scripts/calagem.py` (traz exemplos resolvidos). Importe as funções para casos reais.

## Referências (tabelas transcritas do boletim)
- `references/interpretacao-solo.md` — Quadros 3.1, 4.1, 4.2, 4.3, 4.4 (classes de P, K, acidez/V, Ca, Mg, S, micros, MO, subsolo, N por resposta esperada).
- `references/diagnose-foliar.md` — metodologia da diagnose foliar (Cap. 11). **As faixas de teores foliares por cultura (macro e micro) estão dentro de cada `culturas-*.md`** (ex.: Quadro 13.3 em `culturas-cereais.md`).
- `references/culturas-cereais.md` — milho (grãos/silagem/safrinha), sorgo.
- `references/culturas-leguminosas-oleaginosas-raizes.md` — soja, girassol, mandioca.
- `references/culturas-cana-florestais.md` — cana-de-açúcar, Eucalyptus/Pinus.
- `references/culturas-forrageiras.md` — pastagens e forrageiras.

## Fórmulas-chave (referência rápida)
- **Saturação por bases:** V = 100·SB/T · SB = Ca+Mg+K · T = SB+(H+Al) · m = 100·Al/(SB+Al).
- **Calagem:** `NC (t/ha) = CTC·(V₂−V₁) / (10·PRNT)` — CTC em mmolc/dm³; PRNT padrão 67%; arredondar p/ inteiro, mín. 1 t/ha.
- **Corretivo:** PN = CaO%·1,79 + MgO%·2,48 · RE = 0,2x+0,6y+z · PRNT = PN·RE/100.
- **Gesso (subsolo):** NG (kg/ha) = 6 × argila (g/kg).

## Escopo / avisos
Recomendação técnica de referência; a decisão final é do **engenheiro agrônomo** responsável,
considerando histórico da gleba, cultivar, clima e manejo. Válido para o Estado de São Paulo.
