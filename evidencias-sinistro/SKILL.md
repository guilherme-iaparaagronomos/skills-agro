---
name: evidencias-sinistro
description: >-
  Reúne, em ordem de data, o que o satélite e o registro de chuva mostram em
  volta de um evento na lavoura, para anexar a um aviso de sinistro de seguro
  rural ou a uma comunicação de perdas do Proagro. Serve para seca, chuva em
  excesso, geada, granizo, vento e fogo. Conduz a conversa e chama as ferramentas
  da ClaudIA Sat e da ClaudIA Clima: a chuva dia a dia ao lado da média
  histórica, os veranicos, a temperatura, o índice de vegetação de cada talhão
  antes e depois, e os laudos em PDF das imagens datadas. Só fatos, cada um
  com a fonte: não diz a causa, não estima a perda e não diz se o evento tem
  cobertura. Acione com "evidências para o sinistro", "dossiê do sinistro",
  "preciso provar a seca para o seguro", "comunicação de perdas do Proagro",
  "o que o satélite mostra da geada" ou quando o usuário relatar um evento na
  lavoura e pedir o levantamento.
---

# Evidências de um evento na lavoura

Esta skill não tem script. Quem produz cada dado são as ferramentas dos
conectores da comunidade agrônomo10X; a skill é o roteiro: o que perguntar, o
que chamar, em que ordem, e como montar o **quadro cronológico** no fim.

O usuário recebe:

1. o **gráfico do índice de vegetação com a chuva** no mesmo eixo de tempo
   (`curva_com_chuva`);
2. **dois laudos em PDF**, um da última imagem limpa antes do evento e um da
   primeira depois (`laudo_pdf`), com a data de cada imagem;
3. o **quadro cronológico** escrito na conversa, no formato fixo de
   `references/quadro.md`.

## A regra que vale para tudo: só fatos

Quem decide se houve sinistro, qual foi a causa e quanto se perdeu é o perito
da seguradora ou do agente do Proagro, com a vistoria. O quadro entrega o
registro e para aí.

- NUNCA escreva que o evento "causou", "provocou", "comprova", "confirma" ou
  "caracteriza" a perda, nem que a perda "se deve a" ele. Escreva o que foi
  medido e quando.
- **Coincidir no tempo não prova a causa.** Queda do índice depois de um
  veranico pode ser falta de água, mas também colheita, dessecação, fim de
  ciclo, praga, doença ou nuvem que sobrou na imagem. Diga isso sempre que as
  datas coincidirem.
- **Índice de vegetação não é produtividade.** Não converta a queda do índice
  em sacas, percentual de perda ou valor de indenização.
- NUNCA diga que o evento tem ou não tem cobertura, que o pedido será aceito
  ou negado, nem interprete a apólice, o Manual de Crédito Rural ou o
  Zoneamento Agrícola de Risco Climático.
- O que o usuário informou (cultura, data de plantio, data e tipo do evento)
  entra no quadro marcado como **"segundo o usuário"**. As ferramentas não
  confirmam cultura nem data de plantio.
- Não use palavra que qualifica: severo, grave, forte, leve, atípico,
  anormal, apenas, só. Diga o número e a média histórica ao lado.
- **Diga o que as ferramentas não medem** (seção abaixo). Deixar isso de fora
  faz o quadro parecer mais do que é.
- Cada número vai com a fonte, nas palavras que a ferramenta usou.
- Se o usuário pedir a conclusão ("dá para provar?", "o seguro vai pagar?"),
  diga que o quadro não conclui, entregue os dados e devolva a decisão ao
  perito e ao responsável técnico.

## O que as ferramentas medem e o que não medem

| Evento | O que o quadro traz | O que não traz |
|---|---|---|
| Seca, veranico | chuva dia a dia, total ao lado da média histórica, veranicos com datas, índice antes e depois | umidade do solo, déficit hídrico, perda |
| Chuva em excesso | chuva de cada dia, maior chuva, acumulados, total ao lado da média, índice antes e depois | alagamento, enxurrada, erosão, dias sem poder entrar com máquina |
| Geada, frio | temperatura mínima de cada dia, índice antes e depois | a temperatura no talhão: o dado é de um modelo, para a região, e baixada costuma ser mais fria |
| Calor | temperatura máxima de cada dia, índice antes e depois | temperatura da folha, abortamento |
| Granizo, vento, fogo, praga | só o índice e a imagem antes e depois | o evento em si: as ferramentas não registram granizo, rajada no talhão, foco de fogo nem praga |

A chuva é a média da área, por pluviômetros e satélites. Chuva de verão varia
em poucos quilômetros: o pluviômetro da fazenda, se houver, é registro melhor
do que choveu no talhão. Peça ao usuário e ponha ao lado, como "informado
pelo usuário".

## O que precisa estar disponível

- **Conector ClaudIA Sat**, com `curva_com_chuva`, `datas_disponiveis` e
  `laudo_pdf`. Sem ele, avise o usuário e pare.
- **Conector ClaudIA Clima**, com `clima_historico`. Sem ele, o quadro sai sem
  a chuva dia a dia, sem a média histórica e sem a temperatura, e diz isso.
- **A área**: fazenda salva na conta (`listar_fazendas`) ou arquivo de
  perímetro, de preferência com os talhões (GeoJSON, KML ou WKT; shapefile,
  converta para GeoJSON sem perder os atributos).

## Antes de chamar: as perguntas (numa mensagem só)

1. **A área e os talhões atingidos**: a fazenda salva ou o arquivo; todos os
   talhões ou quais.
2. **O evento**: o que foi (seca, chuva, geada, granizo, vento, fogo, outro)
   e **quando**: o dia, ou o primeiro e o último dia. Se ele não souber o dia,
   peça o intervalo mais curto de que tem certeza.
3. **A cultura e a data do plantio** (ou da emergência). Entram como
   informadas por ele e definem onde a janela começa.
4. **Se a seguradora ou o agente define veranico de outro jeito** (quantos
   dias, abaixo de quantos mm). Sem isso, vale o padrão da ferramenta: 7 ou
   mais dias seguidos com menos de 2 mm por dia.
5. Se houver: os registros do pluviômetro da fazenda e as datas que ele quer
   na cronologia (aviso de sinistro, vistoria, replantio, colheita).

O que ele já disse, não pergunte de novo.

## As datas da consulta

- **Janela da safra**: do dia 1º do mês do plantio até 30 dias depois do fim
  do evento (ou até ontem, se o evento é recente). Até 400 dias por chamada.
- **Janela do evento**: de 15 dias antes do início a 15 dias depois do fim.
- **Imagem de antes**: a mais recente nos 40 dias que terminam na véspera do
  evento.
- **Imagem de depois**: a primeira limpa a partir do dia seguinte ao fim.

Evento recente: a imagem de depois pode ainda não existir (o satélite passa a
cada 5 dias e precisa de céu limpo), e a chuva dos últimos dias é provisória.
Diga isso e ofereça repetir a consulta em alguns dias.

## A conta do consumo (diga antes de chamar)

Cada chamada de satélite consome a área consultada. O roteiro completo faz 4:
a curva, a lista de datas e os dois laudos. A curva aceita uma lista de
talhões e consome a soma das áreas deles; a lista de datas e os laudos
aceitam **um talhão ou a área inteira**. Com um talhão atingido, as quatro
são dele; com vários, a curva é dos talhões e as outras três, da área
inteira (o laudo traz uma página com a média por talhão). As de clima contam
2 consultas. Diga o total em hectares e só então chame. Se a ferramenta
recusar por limite, repita o motivo como ela disse e ofereça fazer um talhão
de cada vez ou continuar no dia seguinte.

## Fluxo de trabalho (siga nesta ordem)

1. **Talhões.** Fazenda salva: `listar_fazendas`. Arquivo: `listar_talhoes`
   com a `geometria`; guarde o `geometria_id` (vale 1 hora).
2. **A curva com a chuva.** `curva_com_chuva` com a área, os talhões
   (`talhoes` com a lista, `todos_talhoes`, ou `talhao` para um só),
   `data_inicio` e `data_fim` da janela da safra e `indice`: `ndvi` (ou
   `ndwi`, água na vegetação, se o usuário pedir). Se ele informou outra
   definição de veranico, passe `veranico_dias` e `limiar_mm`. Dela saem: o
   gráfico, a chuva total, os veranicos e, na lista `CURVA`, o índice de cada
   talhão em cada imagem.
3. **A chuva e a temperatura dia a dia.** `clima_historico` na mesma área,
   com as datas da janela do evento e `escala`: `dia`. Dela saem: a chuva de
   cada dia, a mínima e a máxima de cada dia, o total ao lado da média
   histórica (1991–2020) do mesmo período, os dias sem dado e os avisos.
4. **A chuva da safra mês a mês.** `clima_historico` com as datas da janela
   da safra e `escala`: `mes`: cada mês ao lado da média histórica.
5. **As datas das imagens.** `datas_disponiveis` (com `talhao`, se for um só;
   sem ele, a área inteira) na janela que vai de 40 dias antes do início do
   evento a 40 dias depois do fim. Ela lista cada data com o percentual da
   área livre de nuvem. Escolha: **antes**, a data mais
   recente até a véspera do evento com 90% ou mais de área livre; **depois**,
   a primeira a partir do dia seguinte ao fim com 90% ou mais. Sem nenhuma
   com 90%, mostre as candidatas com o percentual e pergunte ao usuário.
6. **Os dois laudos.** `laudo_pdf` duas vezes, com `data_inicio` e `data_fim`
   iguais à data escolhida (a ferramenta devolve a cena mais recente do
   intervalo, por isso o intervalo é de um dia só), `indices`: `["ndvi",
   "ndwi"]`, `nome_propriedade` e, se a data escolhida tem menos de 95% de
   área livre, `cobertura_minima_pct` com o percentual dela. Evento com dias
   de duração: o "antes" é antes do primeiro dia e o "depois", depois do
   último.
7. **Entregue os arquivos**: o gráfico e os dois laudos. Os links **expiram
   em 1 hora**: diga para baixar na hora.
8. **Escreva o quadro cronológico** no formato de `references/quadro.md`.
9. **Repita os avisos das ferramentas com as palavras delas**: confiança da
   chuva, dias sem dado, dias que "ainda podem ser revisados", a linha
   `AVISOS`, e que a temperatura é dado modelado.
10. **Se o usuário pedir o quadro em arquivo** (Word, PDF, documento), monte
    com o MESMO texto e as mesmas tabelas. Não acrescente parecer, conclusão,
    assinatura nem logo que ele não tenha enviado. Os laudos continuam sendo
    os PDFs da ferramenta, como anexos.

## Como tirar os números

- **Índice antes e depois, por talhão**: na lista `CURVA` da
  `curva_com_chuva`, o valor da última data até a véspera do evento e o da
  primeira data depois do fim. A diferença é uma subtração (depois − antes);
  não a chame de perda. Ponha também o número de dias entre as duas imagens.
  Use as datas da própria lista. Elas podem não ser as mesmas dos laudos: a
  curva e a lista de datas filtram as imagens de jeitos diferentes, e uma
  data pode estar numa e faltar na outra. Quando forem outras, escreva as
  duas: a data do índice e a data do laudo.
- **Veranicos**: as linhas da lista `VERANICOS` da `curva_com_chuva`, com
  datas, dias e mm, e a régua que a ferramenta escreveu entre parênteses. A
  linha `AGRO` da `clima_historico` também traz um "veranico máx", contado
  por outra régua e só dentro da janela do evento: não misture os dois. Se
  citar o da linha `AGRO`, diga que a régua é outra.
- **Dias com "confiança baixa"** na lista diária: diga quantos são e em que
  datas caem.
- **Chuva do evento**: da `clima_historico` em escala de dia, o total, a média
  histórica do mesmo período e a diferença em %, como vieram; a maior chuva e
  o dia; os dias sem dado.
- **Janela curta e tabela mensal não fecham entre si.** O total de uma janela
  de menos de 6 meses e os meses de um período longo saem de contas
  diferentes da ferramenta: o mesmo mês pode dar dois números, com diferença
  da ordem de 10%, e a diferença em % contra a média histórica muda junto.
  Ponha os dois blocos, cada um com o período, não some um com o outro e não
  escolha o que mostra mais seca ou mais chuva.
- **Acumulados** (chuva em excesso): some os dias seguidos da lista só se o
  ambiente roda código; se não roda, cite os dias um a um e o total da
  ferramenta.
- **Temperatura** (geada, calor): a menor mínima e a maior máxima da janela,
  com o dia, e a mínima e a máxima do dia do evento. Sempre com a frase: dado
  modelado para a região, não é termômetro no talhão.
- **Cronologia**: uma linha por data, em ordem, juntando o que o usuário
  informou, os dias de chuva que importam para o evento, o começo e o fim de
  cada veranico e cada imagem com o índice. Não pule datas para a história
  ficar mais limpa: imagem que contradiz o relato entra do mesmo jeito.

## O que a skill não faz

- Não dá laudo pericial, não substitui a vistoria e não estima perda,
  produtividade nem indenização.
- Não confirma a cultura, a data de plantio nem o manejo.
- Não registra granizo, rajada de vento no talhão, foco de fogo, praga ou
  doença: desses eventos só mostra a imagem e o índice antes e depois.
- Não consulta a apólice, as regras do Proagro, o ZARC nem prazos de
  comunicação. Lembre o usuário de que o prazo do aviso é com a seguradora ou
  o agente financeiro, e que o quadro não o substitui.
- Não chama de novo para "melhorar" um resultado nem escolhe a imagem que
  favorece o relato.

## Sigilo das fontes

Cite as fontes como as ferramentas mandam: o índice e as imagens,
"Copernicus Sentinel-2 L2A"; a chuva e a temperatura, "pluviômetros e
satélites da comunidade agrônomo10X (OagronomIA)", sem nomear produto,
instituto ou satélite. Sobre como o dado é processado, a única frase é:
processado pelas ferramentas da comunidade agrônomo10X (OagronomIA).
