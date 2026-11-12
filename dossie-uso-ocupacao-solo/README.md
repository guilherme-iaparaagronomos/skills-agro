# Dossiê de uso e ocupação do solo

Skill que gera o **dossiê de um imóvel rural em PDF** pela ferramenta
`dossie_pdf` do conector ClaudIA Sat e conduz a conversa em volta dela: o que
perguntar, como chamar e como contar o resultado **só com fatos**, cada um com
a fonte e a data.

**O que o documento reúne:**

- **CAR** (pelo número): situação do cadastro, condição da análise e as áreas
  declaradas de reserva legal, vegetação nativa, área consolidada e APP.
- **Uso do solo de 1985 a hoje** e a situação frente às datas-marco de 2008,
  2019 e 2020.
- **Cobertura do solo recente**: as classes dos últimos 12 meses, com pixel de
  10 m.
- **PRODES e DETER** (INPE): polígonos de supressão por período e os alertas.
- **Declarado no CAR ao lado do observado**: os dois números e a diferença.
- **Relevo** e **imagem de satélite**, inclusive a de 2 m quando existe.
- **Restrições**: unidades de conservação, terras indígenas e termos de
  embargo que o perímetro sobrepõe ou que ficam perto. Os termos saem pelo
  número, sem nome nem documento de pessoa.
- **Solo**: textura e carbono por profundidade, como estimativa de um mapa
  mundial de 250 m.

Entra pelo **número do CAR**, por um **arquivo de perímetro** ou por uma
**fazenda salva** na conta.

## O que precisa

O conector **ClaudIA Sat** da comunidade agrônomo10X ligado na sua IA. A skill
não tem script: quem monta o PDF é a ferramenta do conector, em uma chamada.

## Estrutura

- [`SKILL.md`](SKILL.md) — o roteiro que a IA segue e as regras de "só fatos".
- `references/fontes.md` — o que é cada fonte, as datas-marco e os limites.

## Instalar

Baixe [`dossie-uso-ocupacao-solo.zip`](../../../releases/latest/download/dossie-uso-ocupacao-solo.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Avisos

O dossiê reúne fatos de bases públicas e de satélite. Não é laudo, parecer nem
recomendação, não equivale a certidão e não substitui vistoria. A interpretação
é do responsável técnico. Divergências ou melhorias? Abra uma
[issue](../../../issues/new/choose).
