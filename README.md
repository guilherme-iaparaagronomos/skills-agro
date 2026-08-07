# Skills Agro — agrônomo10X · OagronomIA

Skills de agronomia no **formato oficial de Skills do Claude**, criadas pela equipe da
comunidade [agrônomo10X](https://comunidade.agronomos.ia.br) (powered by **OagronomIA**).
Cada skill transforma um boletim oficial de recomendação de corretivos e fertilizantes
em um pacote que a IA sabe **aplicar**: interpreta o laudo de solo, roda os cálculos nos
scripts e cita o quadro e a página da fonte.

| Skill | Fonte oficial | Instalar |
|---|---|---|
| [`5a-aproximacao-mg`](5a-aproximacao-mg/) | **5ª Aproximação (CFSEMG/MG)** — Recomendações para o uso de corretivos e fertilizantes em Minas Gerais (Ribeiro, Guimarães & Alvarez V., eds., 1999) | [Releases](../../releases/latest) |
| [`boletim-100-sp`](boletim-100-sp/) | **Boletim 100 (IAC/SP)** — Recomendações de adubação e calagem para o Estado de São Paulo, 2ª ed. (van Raij et al., 1997) | [Releases](../../releases/latest) |

## Como instalar no Claude

1. Baixe o `.zip` da skill na página de [**Releases**](../../releases/latest).
2. No **claude.ai**, abra **Configurações → Capacidades → Skills** e envie o `.zip`
   (*Upload skill*). Se usar Skills dentro de um **Projeto**, envie o `.zip` lá.
3. Ative a skill. Ao colar um laudo de solo de MG ou SP (ou pedir "calcule a calagem
   pela 5ª Aproximação / pelo Boletim 100"), o Claude aciona a skill certa, roda os
   scripts e responde citando os quadros do boletim.

> Membros da comunidade agrônomo10X também baixam estas skills prontas no catálogo
> interno, em **Soluções → Skills**.

## Como cada skill foi construída

Cada boletim foi dividido em três camadas:

1. **Fórmulas de recomendação → scripts Python** (a parte de maior risco). Transcritas
   das páginas de fórmulas e **validadas contra os exemplos resolvidos do próprio
   boletim** — batem número a número. Rode qualquer script para ver os exemplos:
   `python scripts/calagem.py`.
2. **Interpretação agronômica → referências.** As classes de interpretação (baixo/médio/
   alto etc.) de todos os elementos — P, K, Ca, Mg, S, micros, acidez/V%/m% — em
   `references/interpretacao-solo.md`.
3. **Recomendações por cultura → referências.** As tabelas por cultura, incluindo os
   elementos além de NPK (S, micronutrientes, parcelamento, época/modo, diagnose
   foliar), nos arquivos `references/culturas-*.md`.

O `SKILL.md` de cada uma é o playbook: para que serve, para que **não** serve, e o fluxo
interpretar → calagem → gesso → adubação por cultura.

## Revisão e contribuições

Encontrou um número que diverge do boletim, um quadro mal interpretado ou um caso que a
skill resolve errado? **Abra uma [issue de revisão técnica](../../issues/new/choose)**
citando o quadro/página da fonte — toda correção é validada contra o boletim original
antes de entrar. Sugestões de novas skills (outros boletins estaduais, manuais de
cultura) também são bem-vindas pelas issues. Detalhes em
[CONTRIBUTING.md](CONTRIBUTING.md).

## Avisos importantes

- As saídas são **recomendações técnicas de referência**; a decisão final é sempre do
  **engenheiro agrônomo responsável (ART)**, considerando histórico da gleba, cultivar,
  clima e manejo.
- `5a-aproximacao-mg` vale para **Minas Gerais**/cerrado; `boletim-100-sp` para
  **São Paulo**. Fora desses contextos, use a referência regional adequada.
- Os números foram transcritos com fidelidade da fonte; pontos em que o texto original
  era ambíguo estão sinalizados nos arquivos. Confirme decisões críticas no boletim.
- Este repositório não reproduz os boletins — apenas operacionaliza suas recomendações,
  com citação da fonte. Os direitos das obras originais pertencem aos seus editores
  (CFSEMG e IAC).

---

Feito pela equipe **agrônomo10X · OagronomIA** — IA aplicada à agronomia, do laudo à
recomendação. Conheça a comunidade: <https://comunidade.agronomos.ia.br>
