---
name: relatorio-credito-rural
description: >-
  Monta o quadro de fatos de uma área para análise de crédito rural pelas
  ferramentas da ClaudIA Sat e da ClaudIA Clima: o dossiê do imóvel em PDF, as
  últimas safras por satélite e a chuva dos últimos anos. Conduz a conversa: o
  que perguntar, quais ferramentas chamar, em que ordem, e como relatar só os
  fatos, cada um com a fonte. Reúne a identificação, o que o CAR declara, o uso
  do solo e as datas-marco, PRODES e DETER, unidades de conservação, terras
  indígenas e termos de embargo, o relevo, o índice de vegetação e a chuva de
  cada safra, os veranicos e a chuva de cada ano ao lado do normal. Não dá
  parecer, nota nem veredito de crédito e não estima produtividade. Acione com
  "relatório para crédito rural", "análise da área para financiamento",
  "relatório da fazenda para o banco", "custeio", "histórico das safras por
  satélite", "o que levo ao banco sobre a área" ou quando o usuário trouxer um
  CAR ou um perímetro pedindo o levantamento para crédito.
---

# Relatório da área para crédito rural

Esta skill não tem script. Quem produz cada dado são as ferramentas dos
conectores da comunidade agrônomo10X; a skill é o roteiro: o que perguntar, o
que chamar, em que ordem, e como montar o **quadro de fatos** no fim.

O usuário recebe três coisas:

1. o **dossiê do imóvel em PDF** (ferramenta `dossie_pdf`);
2. **um gráfico por safra**, com o índice de vegetação e a chuva no mesmo
   eixo de tempo (ferramenta `curva_com_chuva`);
3. o **quadro de fatos** escrito na conversa, no formato fixo de
   `references/quadro.md`.

## A regra que vale para tudo: só fatos

O quadro **mostra o dado e para aí**. Quem analisa o crédito é o analista da
instituição; quem responde pela área é o responsável técnico.

- NUNCA diga que a área ou o produtor está apto, inapto, aprovado, reprovado,
  regular, irregular, sem pendência, com pendência, de risco alto, médio ou
  baixo. Não dê nota, faixa, semáforo nem recomendação de conceder ou negar.
- NUNCA use palavra que qualifica: bom, ruim, melhor, pior, preocupante,
  tranquilo, apenas, só, excelente, fraco. Não ordene as safras da melhor para
  a pior e não escreva "tendência".
- **Índice de vegetação não é produtividade.** Não converta NDVI em sacas,
  toneladas, receita ou capacidade de pagamento, e não diga que uma safra foi
  boa ou ruim por causa dele. O índice mostra o vigor da vegetação na área
  consultada, no dia de cada imagem.
- **Coincidir no tempo não prova a causa.** Queda do índice durante um
  veranico pode ser falta de água, mas também colheita, dessecação, fim de
  ciclo ou nuvem que sobrou na imagem. Diga isso quando as datas coincidirem.
- **Chuva é registro, não previsão.** Não diga quanto vai chover nem que o ano
  será igual a outro. O quadro não é o Zoneamento Agrícola de Risco Climático
  (ZARC) e não o substitui.
- **Restrições**: diga "pelas bases públicas, na data de cada uma". Não é
  certidão. Os termos de embargo vêm sem nome e sem documento de pessoa: não
  procure, não deduza nem escreva quem é o embargado.
- **Solo**: é estimativa de um mapa mundial de 250 m, não medição.
- Diferença entre o declarado no CAR e o observado é uma subtração. Não
  interprete.
- Cada número vai com a fonte, nas palavras que a ferramenta usou.
- Se o usuário pedir a conclusão ("passa no banco?", "a área é boa?"), diga
  que o quadro não conclui, entregue os dados e devolva a decisão ao analista
  e ao responsável técnico.

## O que precisa estar disponível

- **Conector ClaudIA Sat**, com `dossie_pdf` e `curva_com_chuva`. Sem ele,
  avise o usuário e pare.
- **Conector ClaudIA Clima**, com `clima_historico` e `contexto_chuva`. Sem
  ele, o quadro sai sem o bloco "Chuva dos últimos anos" e diz isso; a chuva
  de cada safra continua vindo da `curva_com_chuva`.
- **O imóvel**: número do CAR, arquivo de perímetro (GeoJSON, KML ou WKT;
  shapefile, converta para GeoJSON) ou fazenda salva na conta
  (`listar_fazendas` mostra os nomes).
- Só áreas no Brasil.

## Antes de chamar: as perguntas (numa mensagem só)

1. **O imóvel**: CAR, arquivo ou fazenda salva, e o nome da propriedade para
   o título do dossiê.
2. **A área do financiamento**: é o imóvel inteiro ou uma parte dele (a
   lavoura, alguns talhões)? Se for uma parte, peça o perímetro dela (arquivo
   ou fazenda salva). Sem esse perímetro as curvas saem do **imóvel inteiro**,
   que mistura lavoura, pasto e mata; nesse caso escreva isso no quadro.
3. **A cultura e a janela da safra**: mês do plantio e mês da colheita (soja,
   de outubro a março, por exemplo). Quem informa é o usuário: não presuma o
   calendário. Se ele não souber, use o ano agrícola, de 1º de julho a 30 de
   junho, e escreva no quadro que a janela foi essa.
4. **Quantas safras**: o padrão são as 5 últimas já colhidas. Aceite de 1 a 8.
5. Se ele quiser que constem no dossiê: quem pediu e o responsável técnico.

O que ele já disse, não pergunte de novo.

## A conta da franquia (diga antes de chamar)

Cada chamada de satélite consome, da franquia de hectares do usuário, a área
consultada. As de clima contam como consultas, não como hectares.

- dossiê: 1 vez a área do imóvel;
- curvas: número de safras vezes a área da lavoura (ou do imóvel, se a
  lavoura não foi enviada).

Some, diga o total em hectares e o tempo (o dossiê leva até pouco mais de 1
minuto; cada safra, alguns segundos) e só então chame. Imóvel grande com 5
safras pode passar do que a conta do usuário libera por dia: se a ferramenta
recusar, repita o motivo como ela disse e ofereça menos safras, a curva só da
lavoura ou continuar no dia seguinte. Não insista na mesma chamada.

## Fluxo de trabalho (siga nesta ordem)

1. **Dossiê.** Chame `dossie_pdf` com `car`, `geometria` ou `fazenda`, mais
   `nome_propriedade`, `solicitante` e `responsavel` quando informados. Com o
   CAR sozinho, não envie perímetro. Guarde o `geometria_id` que vem no fim da
   resposta: vale 1 hora e serve nas próximas chamadas quando a área do
   financiamento é o imóvel inteiro. Quando o dossiê entra por fazenda salva
   não vem `geometria_id`: repita o nome da fazenda nas próximas chamadas. Não
   monte o dossiê por partes com as outras ferramentas.
2. **Safras.** Uma chamada de `curva_com_chuva` por safra, com:
   - a área: o perímetro ou a fazenda da lavoura; ou o `geometria_id` do
     dossiê, quando é o imóvel inteiro;
   - `data_inicio`: o dia 1º do mês do plantio; `data_fim`: o último dia do
     mês da colheita. Cada chamada aceita até 400 dias;
   - `indice`: `ndvi`, a não ser que o usuário peça outro. Use o mesmo índice
     em todas as safras.
   As chamadas podem ir juntas. Comece pela safra mais recente já colhida e
   volte uma por vez. Não use uma chamada só para vários anos: a ferramenta
   recusa período acima de 400 dias.
3. **Safra em andamento** (opcional): se o usuário quiser a safra que está no
   campo, chame do mesmo jeito. A ferramenta corta o período no último dia
   com dado e avisa que os dias mais recentes ainda podem ser revisados. Ela
   entra no quadro numa linha à parte, marcada "em andamento".
4. **Chuva dos últimos anos.** Chame `clima_historico` com `escala` = `ano`
   para os dez últimos anos completos (de 1º de janeiro do primeiro a 31 de
   dezembro do último), na mesma área das curvas.
5. **O ano em curso.** Chame `contexto_chuva` na mesma área só quando o
   financiamento é para a safra que está começando ou em andamento. Repasse as
   frases dela como vêm.
6. **Entregue os arquivos**: o link do PDF e o do gráfico de cada safra. Os
   links **expiram em 1 hora**: diga para baixar na hora.
7. **Escreva o quadro de fatos** no formato de `references/quadro.md`. Como
   tirar cada número da resposta das ferramentas está na seção abaixo.
8. **Repita os avisos das ferramentas com as palavras delas**: seção do
   dossiê que "NÃO SAIU DESTA VEZ" ou "NÃO INCLUÍDO NESTA EMISSÃO",
   "OBSERVAÇÃO QUE ESTÁ NO DOCUMENTO", a confiança da chuva, "ANOS
   INCOMPLETOS", a linha "AVISOS" do histórico de chuva e os dias que "ainda
   podem ser revisados".
9. **Se o usuário pedir o quadro em arquivo** (Word, PDF, documento), monte
   com o MESMO texto e as mesmas tabelas. Não acrescente análise, capa com
   selo, assinatura nem logo que ele não tenha enviado. O dossiê continua
   sendo o PDF da ferramenta, como anexo: não copie as páginas dele.

## Como tirar cada número da tabela das safras

A resposta da `curva_com_chuva` tem a linha `CHUVA`, a lista `VERANICOS` e a
lista `CURVA` (data e valor de cada imagem). De cada safra saem:

| Coluna | De onde vem |
|---|---|
| Período | as datas que a ferramenta devolveu no título (podem ser mais curtas que as pedidas) |
| Imagens | quantas DATAS diferentes há na lista `CURVA`. A mesma data pode aparecer mais de uma vez: conte uma |
| Maior intervalo sem imagem | a maior distância, em dias, entre duas datas seguidas da lista, com as duas datas |
| Pico do índice | o maior valor da lista e a data dele. Mesmo valor em mais de uma data: a primeira |
| Chuva | o total em mm da linha `CHUVA` |
| Dias de chuva | da linha `CHUVA` |
| Veranicos | o número que vem depois de `VERANICOS (...)` |
| Maior veranico | o de mais dias da lista, com as datas e os mm |

Regras da leitura:

- As listas são longas. Se o ambiente roda código, tire as colunas com
  código a partir do texto da lista; se não roda, conte com calma e releia a
  lista para conferir o pico e o intervalo.
- **Intervalo sem imagem de 30 dias ou mais** em alguma safra: escreva
  embaixo da tabela que, nessas safras, o pico de verdade pode ter caído no
  intervalo e não aparecer. Em safras antigas e em meses de muita nuvem isso
  é comum.
- Não calcule média entre safras, variação percentual de uma para outra nem
  linha de tendência. A tabela põe as safras lado a lado e para aí.
- Com a janela do ano agrícola, os veranicos do inverno seco entram na
  contagem. Diga isso embaixo da tabela.
- Se a área foi o imóvel inteiro, diga embaixo da tabela que o índice é a
  média de tudo o que há no perímetro e, pelo dossiê, quanto dele é vegetação
  nativa e quanto é pastagem.
- Safra que a ferramenta recusou ou que voltou sem imagem: a linha fica, com
  "não consultada" ou "sem imagem no período" e o motivo que ela deu.
- Se o ambiente desenha gráficos, você pode sobrepor as curvas das safras num
  gráfico só (dias desde o início da janela no eixo horizontal), usando
  apenas os números da lista `CURVA`. É figura de apoio: os gráficos da
  ferramenta continuam sendo os anexos.

## Como tirar os números da chuva dos últimos anos

Da resposta da `clima_historico` em escala de ano: uma linha por ano
completo, com a chuva do ano, a média histórica (1991–2020) e a diferença em
%, como a ferramenta devolveu; e a frase "COMO DIZER À PESSOA", que traz a
média anual do período ao lado do normal. Ano parcial não entra na tabela.
Fale em mm por ano. Não some os anos e não conte "anos ruins".

## O que a skill não faz

- Não dá parecer, laudo, nota de risco nem veredito de crédito, e não calcula
  produtividade, receita, garantia, valor da terra ou capacidade de
  pagamento.
- Não consulta o ZARC, as regras do Manual de Crédito Rural, a política da
  instituição, matrícula, CCIR, ITR, certidões, cadastros de restrição de
  pessoas nem listas de trabalho análogo à escravidão. Se o usuário pedir,
  diga que o quadro não cobre e que são consultas dele ou da instituição.
- Não cobre o que as bases do dossiê não cobrem: territórios quilombolas,
  assentamentos, florestas públicas, embargos de órgãos estaduais e a zona de
  amortecimento das unidades de conservação.
- Não gera PDF próprio do dossiê, não edita o PDF da ferramenta e não chama
  de novo para "melhorar" um resultado.
- Não substitui vistoria, laudo técnico, análise de solo nem a análise do
  banco ou do órgão ambiental.

## Sigilo das fontes

Cite as fontes exatamente como cada ferramenta manda: as do dossiê, como
estão na última página do PDF; o índice, "Copernicus Sentinel-2 L2A"; a
chuva, "pluviômetros e satélites da comunidade agrônomo10X (OagronomIA)", sem
nomear produto, instituto, índice ou satélite. Sobre como o dado é
processado, a única frase é: processado pelas ferramentas da comunidade
agrônomo10X (OagronomIA). Não deduza nem cite plataforma, biblioteca ou nuvem.

O que é cada fonte e até onde ela vai: `references/fontes.md`.
