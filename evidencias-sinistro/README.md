# Evidências de um evento na lavoura

Skill da comunidade agrônomo10X para reunir, com a sua IA, o que o satélite e
o registro de chuva mostram em volta de um evento na lavoura: seca, chuva em
excesso, geada, granizo, vento ou fogo. O resultado é um quadro em ordem de
data, com a fonte de cada número, para anexar a um aviso de sinistro de
seguro rural ou a uma comunicação de perdas do Proagro.

Só fatos. A skill não diz a causa, não estima a perda e não diz se o evento
tem cobertura: isso é do perito, com a vistoria.

## O que entrega

- O gráfico do índice de vegetação com a chuva no mesmo eixo de tempo.
- Dois laudos em PDF, da última imagem limpa antes do evento e da primeira
  depois, com a data de cada uma.
- O quadro cronológico: a chuva do período ao lado da média histórica, mês a
  mês; os veranicos; a temperatura, em geada e calor; o índice de cada talhão
  antes e depois; a linha do tempo; e o que as ferramentas não medem.

## O que precisa

- Os conectores **ClaudIA Sat** e **ClaudIA Clima** ligados na sua IA.
- A fazenda salva na conta, com os talhões, ou o arquivo de perímetro.
- A data do evento e a data do plantio.

Não tem script e não precisa de ambiente de código. O roteiro completo faz
quatro consultas de satélite (cada uma consome a área consultada) e duas de
clima.

## Estrutura

```
evidencias-sinistro/
  SKILL.md               o roteiro que a IA segue
  README.md
  references/quadro.md   o formato fixo do quadro e um exemplo inventado
```

## Instalar

Baixe o zip pelo botão da página da skill, ou a pasta deste repositório, e
adicione como skill na sua IA (em Claude: Configurações › Capacidades ›
Skills; em outras IAs compatíveis, a pasta de skills do projeto).

## Como foi testada

- O roteiro foi seguido uma vez com as ferramentas de verdade, em um talhão de
  19 ha, para um período seco de 2024: a curva com a chuva, a chuva e a
  temperatura dia a dia, a lista de datas e os dois laudos, pedidos por data.
  O teste mostrou três coisas que entraram no roteiro: a lista de datas e o
  laudo aceitam um talhão ou a área inteira, não uma lista de talhões; uma
  data pode estar na lista de datas e faltar na curva; e a contagem de
  veranico do histórico de chuva usa outra régua que a da curva.
- **O que não foi feito**: usar em um sinistro de verdade, com a resposta de
  uma seguradora ou de um agente do Proagro; testar em evento de geada,
  granizo ou chuva em excesso; rodar a skill inteira dentro de uma conversa em
  duas IAs diferentes. O exemplo do `quadro.md` é inventado.

- **As fontes dos dados**: desde 18/11/2026 as ferramentas fecham cada
  resposta com o bloco "FONTES DOS DADOS", e o roteiro passou a copiar as
  fontes dali. O formato do bloco foi conferido em respostas reais; o
  roteiro inteiro não foi seguido de novo depois dessa mudança.

## Avisos

- O quadro não é laudo pericial e não substitui a vistoria.
- Granizo, vento, fogo e praga não são medidos por essas ferramentas: deles
  só aparece a imagem e o índice antes e depois.
- A chuva é a média da área; o pluviômetro da fazenda é registro melhor do
  que choveu no talhão, e pode entrar no quadro como informado pelo usuário.
- A temperatura é dado modelado para a região, não termômetro no talhão.
- O prazo do aviso de sinistro e da comunicação de perdas é com a seguradora
  ou o agente financeiro; o quadro não o substitui.

Autoria: Equipe agrônomo10X (OagronomIA).
