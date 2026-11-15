---
name: boletim-safra
description: >-
  Monta o boletim periódico de uma fazenda pelas ferramentas da ClaudIA Sat e
  da ClaudIA Clima, talhão por talhão, num formato fixo. Traz o índice de
  vegetação da última imagem ao lado da imagem anterior e da mesma época das
  safras passadas, a chuva do período e da safra ao lado da média histórica, a
  previsão dos próximos dias e o laudo em PDF da última imagem. Conduz a conversa: o que perguntar, quais
  ferramentas chamar, em que ordem, e como escrever o boletim num formato fixo,
  que se repete toda semana, quinzena ou mês. Só fatos, cada um com a fonte:
  não recomenda manejo e não aponta talhão bom ou ruim. Acione com "boletim da
  fazenda", "boletim da safra", "como está a fazenda esta semana", "resumo
  semanal dos talhões", "acompanhamento da lavoura" ou quando o usuário pedir
  o acompanhamento periódico de uma área.
---

# Boletim da safra

Esta skill não tem script. Quem produz cada dado são as ferramentas dos
conectores da comunidade agrônomo10X; a skill é o roteiro: o que perguntar, o
que chamar, em que ordem, e como montar o **boletim** no formato fixo de
`references/boletim.md`. Formato fixo é o que deixa um boletim comparável com
o da semana anterior.

O usuário recebe:

1. o **boletim** escrito na conversa: imagens, talhão a talhão, chuva e
   previsão;
2. o **laudo em PDF** da última imagem limpa, com o mapa do índice
   (`laudo_pdf`).

## A regra que vale para tudo: só fatos

O boletim mostra o número e para aí. Quem lê a lavoura e decide o manejo é o
responsável técnico.

- NUNCA recomende aplicação, irrigação, adubação, replantio, colheita nem
  vistoria. Não escreva "atenção ao talhão X", "talhão preocupante", "bom
  desenvolvimento", "abaixo do esperado".
- Não use palavra que qualifica: bom, ruim, melhor, pior, forte, fraco,
  normal, anormal, apenas, só.
- **Índice de vegetação não é produtividade** e não é diagnóstico. Diferença
  entre duas imagens é uma subtração; a causa pode ser crescimento, colheita,
  dessecação, estresse, praga, nuvem que sobrou ou hora diferente da imagem.
- **Comparar com o ano passado compara calendários.** Se o talhão estava em
  pousio, com outra cultura ou plantado em outra data, a diferença é disso.
  Escreva essa frase embaixo da tabela sempre que houver comparação entre
  anos.
- Não ordene os talhões do melhor para o pior. A tabela segue a ordem do
  arquivo. Se o usuário pedir, ordene pela diferença e diga que é só a ordem
  do número.
- **Chuva é registro; previsão é estimativa.** Repasse a previsão com as
  palavras da ferramenta e a linha da fonte que ela manda. Não some a
  previsão ao que já choveu e não indique horário de pulverizar.
- Cada número vai com a data da imagem ou do período.
- Se o usuário pedir a leitura ("o que eu faço?", "qual talhão está pior?"),
  diga que o boletim não conclui, mostre os números e devolva a decisão ao
  responsável técnico.

## O que precisa estar disponível

- **Conector ClaudIA Sat**, com `curva_indice` e `laudo_pdf`. Sem ele, avise
  o usuário e pare.
- **Conector ClaudIA Clima**, com `clima_historico` e `previsao_dias`. Sem
  ele, o boletim sai só com as imagens e diz isso.
- **A área**: fazenda salva na conta (`listar_fazendas` mostra os nomes e os
  talhões) ou arquivo de perímetro com os talhões nos atributos (GeoJSON, KML
  ou WKT; shapefile, converta para GeoJSON sem perder os atributos).

## Antes de chamar: as perguntas (numa mensagem só)

Na primeira vez:

1. **A área**: a fazenda salva ou o arquivo. Todos os talhões ou quais.
2. **O período do boletim**: semanal (7 dias), quinzenal (15, o padrão) ou
   mensal (30).
3. **Quando a safra começou**: o mês do plantio. Sem isso, a chuva da safra
   conta desde 1º de julho, e o boletim diz que a janela foi essa.
4. **Comparar com quantas safras passadas**: o padrão são 2. Aceite de 0 a 3.
5. **O índice**: `ndvi`, a não ser que ele peça outro. O mesmo em todos os
   boletins, para dar para comparar.

Nas vezes seguintes, na mesma conversa ou quando ele disser "o boletim de
sempre", use as mesmas respostas e só confirme a área.

## A conta do consumo (diga antes de chamar)

- Satélite: a curva recente e a de cada safra passada consomem a **soma das
  áreas dos talhões pedidos**; o laudo consome a área inteira (ou a do talhão,
  se o boletim for de um só). Com 2 safras passadas, são 3 curvas e 1 laudo.
- Clima: 3 consultas (a chuva do período, a chuva da safra e a previsão).

Diga o total em hectares e só então chame. Boletim semanal de fazenda grande
gasta franquia depressa: diga quanto dá por mês nesse ritmo e ofereça menos
safras passadas, só os talhões em acompanhamento ou o laudo a cada dois
boletins. Se a ferramenta recusar por limite, repita o motivo como ela disse.

## Fluxo de trabalho (siga nesta ordem)

1. **Talhões.** Fazenda salva: `listar_fazendas`. Arquivo: `listar_talhoes`
   com a `geometria`; guarde o `geometria_id` (vale 1 hora).
2. **A curva recente.** `curva_indice` com a área, `todos_talhoes`: `true`
   (ou `talhoes` com a lista), `indice`, `data_inicio` = 60 dias atrás e
   `data_fim` = ontem. De cada talhão saem a **última imagem** (data e valor)
   e a **anterior**. Sem talhões, não envie `todos_talhoes`: a curva é da
   área inteira.
3. **A mesma época nas safras passadas.** Para cada safra pedida, uma
   `curva_indice` igual, com `data_inicio` e `data_fim` 15 dias antes e 15
   dias depois do mesmo dia e mês da última imagem, no ano anterior. De cada
   talhão sai o valor da **data mais próxima** desse dia. Sem imagem na
   janela: "sem imagem limpa", e não alargue a janela por conta própria.
4. **A chuva do período.** `clima_historico` na mesma área, com as datas do
   período do boletim (terminando ontem) e `escala`: `dia`. Dela saem o
   total, a média histórica (1991–2020) do mesmo período, os dias de chuva, a
   maior chuva e o dia, e os avisos.
5. **A chuva da safra.** `clima_historico` do dia 1º do mês do plantio até
   ontem, `escala`: `mes`: cada mês e o total ao lado da média histórica.
6. **A previsão.** `previsao_dias` na mesma área, `dias`: 7 (ou 14, se o
   usuário pedir). Repasse o texto pronto que ela devolve.
7. **O laudo.** `laudo_pdf` com `data_inicio` e `data_fim` iguais à data da
   última imagem, `indices`: o índice do boletim, e `nome_propriedade`. Se a
   ferramenta responder que a cena não passa no filtro de nuvem, mostre as
   candidatas que ela listar e pergunte ao usuário; não baixe o filtro
   sozinho.
8. **Escreva o boletim** no formato de `references/boletim.md` e entregue o
   link do laudo. O link **expira em 1 hora**: diga para baixar na hora.
9. **Repita os avisos das ferramentas com as palavras delas**: dias que
   "ainda podem ser revisados (dado provisório)", confiança da chuva, a linha
   `AVISOS`, e que depois de 7 dias a previsão é menos certeira.

As chamadas 2 a 6 não dependem uma da outra, a não ser a 3, que precisa da
data da última imagem.

## Como tirar os números

- **Última imagem e anterior**: as duas últimas datas da lista de cada
  talhão na curva recente. Arredonde o índice para duas casas. A diferença é
  última − anterior, feita com os valores já arredondados, para a conta
  fechar com o que está na tabela. Ponha os dias entre as duas.
- **Imagem antiga**: se a última imagem tem mais de 10 dias, escreva isso no
  alto do bloco: o boletim descreve a lavoura daquela data, não a de hoje.
- **Mesma época**: em cada safra passada, o valor da data mais próxima do dia
  e mês da última imagem, com a data. Diferença = este ano − aquele ano.
- **Talhões com datas diferentes**: se a última imagem de um talhão não é a
  mesma dos outros (nuvem só em parte da fazenda), ponha a data de cada um.
- **Chuva do período**: o total, a média histórica e a diferença em %, como
  vieram na linha `RESUMO`; os dias de chuva e a maior chuva, da linha `AGRO`.
- **Chuva da safra**: a tabela mês a mês e o total. O mês em curso vem
  parcial: escreva até que dia ele vai.
- **Os dois blocos de chuva não fecham entre si** quando a safra já passa de
  6 meses: período curto e período longo saem de contas diferentes da
  ferramenta, e o mesmo mês pode dar dois números, com diferença da ordem de
  10%. Não some um com o outro; cada bloco vale com o seu período.
- **Previsão**: as linhas do texto pronto, sem refazer conta, e a linha da
  fonte no fim do boletim, exatamente como a ferramenta manda.

## O que a skill não faz

- Não recomenda manejo, não diagnostica praga, doença, deficiência ou
  estresse e não estima produtividade.
- Não substitui a visita ao talhão: aponta onde o número mudou, não o porquê.
- Não agenda nem envia o boletim sozinha: cada boletim é um pedido.
- Não guarda o boletim anterior. Para comparar com ele, o usuário cola o
  boletim passado, ou a comparação é a da imagem anterior, que já vem.
- Para o histórico de várias safras inteiras existe a skill
  `historico-produtivo-talhao`; para documentar um evento,
  `evidencias-sinistro`.

## Sigilo das fontes

Cite as fontes como as ferramentas mandam: o índice e as imagens,
"Copernicus Sentinel-2 L2A"; a chuva, "pluviômetros e satélites da comunidade
agrônomo10X (OagronomIA)", sem nomear produto, instituto ou satélite; a
previsão, com a linha de fonte que a `previsao_dias` devolve, sem acrescentar
nada sobre o modelo. Sobre como o dado é processado, a única frase é:
processado pelas ferramentas da comunidade agrônomo10X (OagronomIA).
