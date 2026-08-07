# Como contribuir

Obrigado pelo interesse em melhorar as skills! O fluxo é simples, mas a régua técnica é
alta: **a fonte oficial (o boletim) sempre tem a palavra final.**

## Pedir uma revisão (o caminho mais comum)

Abra uma [issue de revisão técnica](../../issues/new/choose) com:

- **Qual skill e qual arquivo** (ex.: `5a-aproximacao-mg/scripts/calagem.py`);
- **O que está divergente** (o número/classe/fórmula que você obteve vs. o esperado);
- **A fonte**: quadro e página do boletim que sustenta a correção.

Sem a referência do boletim a issue vira discussão, não correção — os mantenedores vão
pedir a página antes de mudar qualquer número.

## Propor mudança por Pull Request

1. Faça o fork e crie um branch a partir da `main`.
2. Edite a skill mantendo a estrutura: `SKILL.md` (playbook) + `scripts/` (cálculos) +
   `references/` (tabelas de interpretação e por cultura).
3. **Regra de ouro dos scripts**: todo script tem exemplos embutidos no final (rode
   `python scripts/<nome>.py`). Se você mexer numa fórmula, os exemplos precisam
   continuar batendo com os **exemplos resolvidos do próprio boletim** — e se o boletim
   tiver um exemplo que ainda não usamos, adicione-o.
4. No PR, cite quadro e página da fonte para cada mudança de número.

## Sugerir uma skill nova

Abra uma issue de sugestão dizendo **qual fonte oficial** a skill operacionalizaria
(boletim estadual, manual de cultura, norma técnica) e o que ela deveria calcular.
Fontes com exemplos resolvidos facilitam muito a validação.

## Escopo e postura

- Português brasileiro em tudo (código pode ter identificadores em inglês).
- As skills recomendam **com base na fonte**; nada de "regra de bolso" sem referência.
- A decisão agronômica final é do engenheiro agrônomo responsável (ART) — as skills
  são apoio técnico, e o texto delas deve sempre deixar isso claro.
