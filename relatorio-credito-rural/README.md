# Relatório da área para crédito rural

Skill que monta o **quadro de fatos de uma área para análise de crédito
rural** pelas ferramentas dos conectores ClaudIA Sat e ClaudIA Clima. Ela
conduz a conversa: o que perguntar, quais ferramentas chamar, em que ordem, e
como relatar o resultado **só com fatos**, cada um com a fonte.

**O que o usuário recebe:**

- o **dossiê do imóvel em PDF**: o que o CAR declara, o uso do solo de 1985 a
  hoje e as datas-marco de 2008, 2019 e 2020, PRODES e DETER, unidades de
  conservação, terras indígenas e termos de embargo, relevo, imagem e solo;
- **um gráfico por safra**, com o índice de vegetação e a chuva no mesmo eixo
  de tempo;
- o **quadro de fatos** na conversa, em formato fixo: identificação, CAR, uso
  do solo, registros socioambientais, a tabela das safras (imagens, pico do
  índice, chuva, dias de chuva e veranicos), a chuva de cada ano ao lado do
  normal, relevo e retrato atual.

Entra pelo **número do CAR**, por um **arquivo de perímetro** ou por uma
**fazenda salva** na conta. Para as safras, o ideal é enviar também o
perímetro da lavoura que será financiada.

## O que precisa

Os conectores **ClaudIA Sat** e **ClaudIA Clima** da comunidade agrônomo10X
ligados na sua IA. A skill não tem script: cada dado vem de uma ferramenta dos
conectores.

Cada chamada de satélite consome hectares da franquia da conta: o dossiê, uma
vez a área do imóvel; as curvas, o número de safras vezes a área consultada. A
skill faz a conta e avisa antes de chamar.

## Estrutura

- [`SKILL.md`](SKILL.md) — o roteiro que a IA segue e as regras de "só fatos".
- `references/quadro.md` — o formato fixo do quadro e um exemplo inventado.
- `references/fontes.md` — o que é cada fonte e até onde ela vai.

## Instalar

Baixe [`relatorio-credito-rural.zip`](../../../releases/latest/download/relatorio-credito-rural.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Como foi testada

O roteiro foi seguido de ponta a ponta com os conectores ligados, em duas
áreas: um imóvel de 1.670 ha pelo número do CAR e uma lavoura de 90 ha com
cinco safras, mais uma safra em andamento e uma safra antiga com poucas
imagens. O formato do quadro saiu desses testes. A skill ainda não foi usada
em um processo de crédito de verdade.

- **As fontes dos dados**: desde 18/11/2026 as ferramentas fecham cada
  resposta com o bloco "FONTES DOS DADOS", e o roteiro passou a copiar as
  fontes dali. O formato do bloco foi conferido em respostas reais; o
  roteiro inteiro não foi seguido de novo depois dessa mudança.

## Avisos

O quadro reúne registros de bases públicas e de satélite. Não é parecer,
laudo nem recomendação, não conclui sobre o crédito e não estima
produtividade. O índice de vegetação mostra o vigor da lavoura, não o que foi
colhido. Não equivale a certidão e não substitui vistoria. A análise é do
analista da instituição e do responsável técnico. Divergências ou melhorias?
Abra uma [issue](../../../issues/new/choose).
