# Boletim 100 (IAC/SP)

Skill que operacionaliza o **Boletim Técnico 100 do Instituto Agronômico (IAC)**, 2ª
edição (van Raij, Cantarella, Quaggio & Furlani, 1997) — a referência oficial de
recomendação de adubação e calagem para o Estado de São Paulo.

**O que ela faz:** interpreta o laudo no padrão IAC (P resina, K, Ca, Mg, S, micros,
pH CaCl₂, V%), calcula a **calagem pela saturação por bases** com meta de V₂ por
cultura, avalia a **qualidade do corretivo** (PN, PRNT, RE), indica **gesso** para o
subsolo e recomenda **N-P-K, S e micronutrientes por cultura** (milho, soja, cana,
mandioca, forrageiras, eucalipto…) — sempre citando o quadro e a página.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue (escopo, limites e fluxo de trabalho).
- `scripts/` — `fertilidade_solo.py` (SB, CTC, V%, m%, conversões de unidade) ·
  `calagem.py` (NC por V% + PN/PRNT/RE + gesso). Todos com os **exemplos resolvidos do
  boletim** embutidos: `python scripts/calagem.py`.
- `references/` — interpretação, diagnose foliar e tabelas por cultura (cereais,
  leguminosas/oleaginosas/raízes, cana e florestais, forrageiras).

## Instalar

Baixe [`boletim-100-sp.zip`](../../../releases/latest/download/boletim-100-sp.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Abrangência e avisos

Vale para o **Estado de São Paulo**. Para Minas Gerais/cerrado, use a skill
[`5a-aproximacao-mg`](../5a-aproximacao-mg/). As saídas são referência técnica — a
decisão final é do engenheiro agrônomo responsável (ART). Divergências? Abra uma
[issue de revisão](../../../issues/new/choose) citando quadro e página.
