# 5ª Aproximação (CFSEMG/MG)

Skill que operacionaliza as **Recomendações para o uso de corretivos e fertilizantes em
Minas Gerais — 5ª Aproximação** (Ribeiro, Guimarães & Alvarez V., eds., CFSEMG, Viçosa,
1999) — a referência oficial de fertilidade para MG, muito usada também no cerrado.

**O que ela faz:** interpreta o laudo no padrão CFSEMG (P por argila/P-rem, K, Ca, Mg,
S, micros, V%, m%), calcula a **calagem pelos dois métodos oficiais** (neutralização do
Al³⁺ + elevação de Ca/Mg; saturação por bases), **gesso agrícola** (3 métodos),
converte a recomendação em **mistura de simples ou fórmula comercial** e recomenda
N-P-K e demais elementos **por cultura** (hortaliças, frutíferas, grandes culturas,
floricultura, pastagens) — sempre citando o quadro e a página.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue (escopo, limites e fluxo de trabalho).
- `scripts/` — `fertilidade_solo.py` (índices e classes) · `calagem.py` (2 métodos + QC)
  · `gessagem.py` (3 métodos + QG) · `adubacao_npk.py` (mistura/fórmula, sulco/cova).
  Todos com os **exemplos resolvidos do boletim** embutidos: `python scripts/calagem.py`.
- `references/` — interpretação (Quadros 5.1–5.5), diagnose foliar e tabelas por cultura.

## Instalar

Baixe [`5a-aproximacao-mg.zip`](../../../releases/latest/download/5a-aproximacao-mg.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Abrangência e avisos

Vale para **Minas Gerais** e é amplamente usada no cerrado. Para São Paulo, use a skill
[`boletim-100-sp`](../boletim-100-sp/). As saídas são referência técnica — a decisão
final é do engenheiro agrônomo responsável (ART). Divergências? Abra uma
[issue de revisão](../../../issues/new/choose) citando quadro e página.
