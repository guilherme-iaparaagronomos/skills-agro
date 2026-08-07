# Interpretação da análise de solo — Boletim 100 (IAC/SP)

Tabelas de interpretação (Cap. 3 e 4). Use para **classificar** cada elemento
antes de recomendar. Todos os teores no Sistema Internacional de Unidades.

> Fonte: van Raij, B.; Cantarella, H.; Quaggio, J.A.; Furlani, Â.M.C. (1997).
> *Recomendações de Adubação e Calagem para o Estado de São Paulo*, 2ª ed.,
> Boletim Técnico 100, IAC, Campinas.

---

## Quadro 3.1 — Conversão de unidades (Nova = Antiga × Fator)

| Unidade antiga | Unidade nova | Fator |
|---|---|---|
| % | g/kg, g/dm³, g/L | 10 |
| ppm | mg/kg, mg/dm³, mg/L | 1 |
| meq/100 cm³ | mmolc/dm³ | 10 |
| meq/100 g | mmolc/kg | 10 |
| P₂O₅ | P | 0,437 |
| K₂O | K | 0,830 |
| CaO | Ca | 0,715 |
| MgO | Mg | 0,602 |

Inverso (elemento → óxido): P→P₂O₅ ×2,29 · K→K₂O ×1,205 · Ca→CaO ×1,399 · Mg→MgO ×1,661.

---

## Quadro 4.1 — Fósforo (resina) e Potássio trocável

P é interpretado por **4 grupos de culturas** com exigência crescente.

| Teor | Produção relativa (%) | K⁺ (mmolc/dm³) | P florestais (mg/dm³) | P perenes | P anuais | P hortaliças |
|---|---|---|---|---|---|---|
| Muito baixo | 0–70 | 0,0–0,7 | 0–2 | 0–5 | 0–6 | 0–10 |
| Baixo | 71–90 | 0,8–1,5 | 3–5 | 6–12 | 7–15 | 11–25 |
| Médio | 91–100 | 1,6–3,0 | 6–8 | 13–30 | 16–40 | 26–60 |
| Alto | >100 | 3,1–6,0 | 9–16 | 31–60 | 41–80 | 61–120 |
| Muito alto | >100 | >6,0 | >16 | >60 | >80 | >120 |

P por resina trocadora de íons; K por qualquer extrator usual (resultados comparáveis).

---

## Quadro 4.2 — Acidez (camada arável)

| pH em CaCl₂ | Classe | Saturação por bases V (%) | Classe |
|---|---|---|---|
| ≤ 4,3 | Acidez muito alta | 0–25 | Muito baixa |
| 4,4–5,0 | Acidez alta | 26–50 | Baixa |
| 5,1–5,5 | Acidez média | 51–70 | Média |
| 5,6–6,0 | Acidez baixa | 71–90 | Alta |
| > 6,0 | Acidez muito baixa | > 90 | Muito alta |

---

## Quadro 4.3 — Cálcio, Magnésio e Enxofre

| Teor | Ca²⁺ (mmolc/dm³) | Mg²⁺ (mmolc/dm³) | S-SO₄²⁻ (mg/dm³) |
|---|---|---|---|
| Baixo | 0–3 | 0–4 | 0–4 |
| Médio | 4–7 | 5–8 | 5–10 |
| Alto | > 7 | > 8 | > 10 |

- Ca: valores mínimos desejáveis; deficiências de Ca são raras a campo (a calagem supre).
- Mg: garantir ≥ 5 mmolc/dm³ (≥ 9 mmolc/dm³ em culturas muito adubadas com K).
- Relação Ca/Mg: **não** é critério — irrelevante entre ~0,5:1 e 30:1 se nenhum estiver deficiente.
- S: acumula abaixo da camada arável; avaliar também 20–40 cm.

---

## Quadro 4.4 — Micronutrientes

B por água quente; Cu, Fe, Mn, Zn por **DTPA**.

| Teor | B | Cu | Fe | Mn | Zn |
|---|---|---|---|---|---|
| Baixo | 0–0,20 | 0–0,2 | 0–4 | 0–1,2 | 0–0,5 |
| Médio | 0,21–0,60 | 0,3–0,8 | 5–12 | 1,3–5,0 | 0,6–1,2 |
| Alto | > 0,6 | > 0,8 | > 12 | > 5,0 | > 1,2 |

(mg/dm³)

---

## Matéria orgânica e argila (4.6)

- M.O. **não** é usada para prever N em SP. Serve como indício de textura:
  - ≤ 15 g/dm³ → arenoso · 16–30 → textura média · 31–60 → argiloso · > 60 → acúmulo (má drenagem/acidez).
- Argila expressa em g/kg; medir também em profundidade.

## Nitrogênio (4.1) — classes de resposta esperada

Não há análise de solo para N em SP. Usa-se **classe de resposta esperada** (Alta/Média/Baixa),
combinada com a produtividade esperada, definida pelo histórico da gleba:
- **Alta:** solos corrigidos com muitos anos de gramíneas/não-leguminosas; 1ºs anos de plantio direto; arenosos (lixiviação). Perenes com N foliar baixo.
- **Média:** solos muito ácidos a corrigir; leguminosa esporádica; pousio de 1 ano; adubo orgânico moderado. Perenes com N foliar médio.
- **Baixa:** pousio ≥ 2 anos; após pastagem (exceto arenosos); cultivo intenso anterior de leguminosas/adubação verde; muito adubo orgânico. Perenes com N foliar alto.

## Interpretação do subsolo (4.7) — condições desfavoráveis à raiz (20–40 cm)

- Ca²⁺ < 4 mmolc/dm³
- Al³⁺ > 5 mmolc/dm³ associado a **saturação por Al (m) > 40%**
→ indicam necessidade de gesso (ver `scripts/calagem.py`).

---

### Como usar com os scripts
- `scripts/fertilidade_solo.py` calcula SB, CTC (T e efetiva), V% e m% e classifica a acidez.
- `scripts/calagem.py` calcula NC (necessidade de calagem), qualidade do corretivo e gesso.
- As **metas de V₂** para calagem e as doses de P₂O₅/K₂O/N por cultura estão nas referências `culturas-*.md`.
