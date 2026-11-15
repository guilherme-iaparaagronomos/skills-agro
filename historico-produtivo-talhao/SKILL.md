---
name: historico-produtivo-talhao
description: >-
  Monta o histórico por satélite de cada talhão em várias safras: os ciclos de
  vegetação de cada ano, com início, pico e fim prováveis, e a chuva de cada
  safra ao lado da média histórica. Usa as ferramentas da ClaudIA Sat e da
  ClaudIA Clima (`curva_com_chuva` e `clima_historico`) e um script que lê as
  respostas, acha os ciclos por regras declaradas e grava o quadro, as tabelas,
  uma figura por talhão e o relatório em PDF. Só descreve: não diz a cultura,
  não estima produtividade e não compara safra melhor e pior. Acione com
  "histórico do talhão", "calendário das safras por satélite", "quantos ciclos
  o talhão teve", "quando o talhão foi plantado nos últimos anos", "teve
  segunda safra?", "histórico produtivo da fazenda" ou quando o usuário quiser
  ver o que cada talhão fez nos últimos anos.
---

# Histórico por satélite de cada talhão

O usuário recebe, para cada talhão e cada safra consultada:

1. os **ciclos de vegetação** que o satélite viu: início provável, pico (valor
   e dia), fim provável e duração;
2. as **imagens** de cada safra: quantas, o maior intervalo sem imagem e o
   maior valor do índice;
3. a **chuva** de cada safra ao lado da média histórica do mesmo período, os
   dias de chuva e os veranicos;
4. os arquivos: `quadro.md` (o texto para a conversa), `ciclos.csv`,
   `safras.csv`, uma figura por talhão e `historico.pdf`.

Quem produz o dado são as ferramentas dos conectores da comunidade
agrônomo10X. O script desta skill só lê o que elas devolveram e faz a conta
dos ciclos.

## A regra que vale para tudo: só fatos

- **Índice de vegetação não é produtividade.** Não converta em sacas,
  toneladas nem receita, e não diga que uma safra foi boa ou ruim.
- **O satélite não diz a cultura.** Fale em "ciclo de vegetação", nunca em
  "safra de soja" ou "milho safrinha", a não ser que o usuário tenha dito o
  que plantou; nesse caso escreva "segundo o usuário".
- **Início do ciclo não é plantio; fim não é colheita.** O início é quando o
  verde aparece para o satélite, dias ou semanas depois do plantio. O fim é
  quando ele some: maturação, dessecação, colheita ou seca.
- **Cada data estimada vai com as duas imagens entre as quais ela caiu.**
  Quando há muitos dias sem imagem em volta, diga.
- Não ordene os talhões nem as safras do melhor para o pior, não calcule
  média entre safras nem tendência, e não use palavra que qualifica (bom,
  ruim, fraco, excelente, preocupante).
- **Coincidir no tempo não prova a causa.** Safra com menos chuva e pico
  menor: mostre os dois números e pare aí.
- **Chuva é registro, não previsão.**
- Se o usuário pedir a conclusão ("qual talhão é o melhor?", "a área é
  produtiva?"), diga que o histórico não conclui, entregue os números e
  devolva a leitura ao responsável técnico.

## O que precisa estar disponível

- **Conector ClaudIA Sat**, com `curva_com_chuva`. Sem ele, avise e pare.
- **Conector ClaudIA Clima**, com `clima_historico`. Sem ele, a chuva de cada
  safra sai sem a média histórica, e o quadro diz isso.
- **A área**: fazenda salva na conta (`listar_fazendas` mostra os nomes e os
  talhões) ou arquivo de perímetro com os talhões nos atributos (GeoJSON, KML
  ou WKT; shapefile, converta para GeoJSON sem perder os atributos).
- **Ambiente que roda Python**, com numpy e matplotlib, para o script. Sem
  ele, veja "Sem ambiente de código".

## Antes de chamar: as perguntas (numa mensagem só)

1. **A área e os talhões**: a fazenda salva ou o arquivo. Todos os talhões ou
   quais? Sem talhões no arquivo, o histórico é da área inteira, que pode
   misturar lavoura, pasto e mata; escreva isso no quadro.
2. **Quantas safras**: o padrão são as 4 últimas completas. Aceite de 2 a 8.
3. **Quando a janela começa**: o padrão é o ano agrícola, de 1º de julho a 30
   de junho. Outro mês de início serve, desde que as janelas fiquem
   **emendadas**, uma terminando na véspera da outra: é isso que deixa o
   script acompanhar o ciclo que atravessa a virada.
4. **O índice**: `ndvi`, a não ser que ele peça outro. O mesmo em todas.

O que ele já disse, não pergunte de novo.

## A conta do consumo (diga antes de chamar)

- Satélite: cada chamada de `curva_com_chuva` consome a área consultada. Com
  talhões, é a **soma das áreas dos talhões pedidos**. Total = número de
  safras × essa área.
- Clima: uma consulta por safra.

Diga o total em hectares e o número de consultas e só então chame. Se a
ferramenta recusar por limite, repita o motivo como ela disse e ofereça menos
safras, menos talhões ou continuar no dia seguinte.

## Fluxo de trabalho (siga nesta ordem)

1. **Talhões.** Fazenda salva: `listar_fazendas`. Arquivo: `listar_talhoes`
   com a `geometria`; guarde o `geometria_id` (vale 1 hora) para as próximas
   chamadas.
2. **Uma chamada de `curva_com_chuva` por safra**, da mais antiga para a mais
   recente, com:
   - a área (`fazenda` ou `geometria_id`);
   - `todos_talhoes`: `true`, ou `talhoes` com a lista, ou `talhao` para um
     só. Para a área inteira, não envie nenhum dos três;
   - `data_inicio` e `data_fim`: os doze meses da janela (até 400 dias por
     chamada). Não use uma chamada para vários anos: a ferramenta recusa;
   - `indice`: o escolhido.
3. **Uma chamada de `clima_historico` por safra**, na mesma área e com as
   mesmas datas, `escala`: `mes`. Dela interessa a linha `RESUMO`, que traz a
   chuva e a média histórica (1991–2020) do período.
4. **Grave um arquivo de texto por safra** numa pasta (`respostas/`), com,
   nesta ordem e como vieram:
   - a primeira linha da resposta da `curva_com_chuva` (a que tem "cruzado
     com a chuva de ... a ...");
   - a linha `CHUVA:`;
   - a linha `VERANICOS (...)` e as linhas de cada veranico, que podem ser
     cortadas depois de "no total)";
   - as linhas da curva: `Área: ...` ou uma `Talhão ...: ...` por talhão,
     **inteiras**, sem resumir e sem redigitar número de memória;
   - a linha `RESUMO:` da `clima_historico`.
5. **Confira a cópia**:
   `python scripts/calendario.py --pasta respostas --conferir`.
   Ele mostra, por safra e talhão, quantas imagens leu e a primeira e a
   última. Compare com as respostas das ferramentas. Se não bater, corrija o
   arquivo antes de seguir.
6. **Rode**:
   `python scripts/calendario.py --pasta respostas --nome "<nome da fazenda>" --saida saida`.
7. **Entregue**: escreva na conversa o conteúdo de `quadro.md` (pode encurtar
   as tabelas de imagens se forem muitos talhões, dizendo que o resto está nos
   arquivos) e entregue `historico.pdf`, os dois CSV e as figuras.
8. **Repita os avisos** que vieram: os do script (ciclo que começou antes do
   período, ciclo em aberto no fim, dias sem imagem em volta de uma data,
   janelas não emendadas) e os das ferramentas, com as palavras delas
   (confiança da chuva, dias sem dado, dias que "ainda podem ser revisados").

## As regras do script e quando mudar

O script acha os ciclos por quatro números. Os padrões estão escritos no
quadro e no PDF. **Diga ao usuário quais foram usados**; quem muda é ele.

| Opção | Padrão | O que é |
|---|---|---|
| `--amplitude-min` | 0,20 | quanto o índice precisa subir e descer para contar como ciclo |
| `--fracao` | 0,30 | o início e o fim são o dia em que a curva passa de 30% do caminho entre a base e o pico |
| `--distancia-min` | 45 dias | picos mais próximos que isso contam como um ciclo só |
| `--queda` | 0,10 | imagem isolada este tanto abaixo das duas vizinhas sai da conta (nuvem que sobrou) |
| `--abaixo-pct` | 20 | marca com ▼ a safra com chuva este tanto por cento ou mais abaixo da média |

Quando faz sentido oferecer a mudança: talhão em que o usuário sabe que houve
segunda safra e o script achou um ciclo só (baixar a amplitude ou a
distância); pasto ou cultura perene, em que o índice oscila pouco (baixar a
amplitude, e dizer que aí o "ciclo" é a estação do ano); índice diferente do
NDVI, com outra faixa de valores. Rode de novo com o número que ele escolher
e diga o que mudou. Não troque os números por conta própria para "achar" um
ciclo. O método completo: `references/metodo.md`.

## Sem ambiente de código

Faça as chamadas do mesmo jeito e monte à mão, por talhão e safra, só o que
dá para ler com segurança: quantas imagens, o maior valor do índice e o dia,
o maior intervalo sem imagem, a chuva, a média histórica e os veranicos. Diga
que o início e o fim de cada ciclo saem do script, que precisa de um ambiente
que rode Python, e não estime essas datas de cabeça.

## O que a skill não faz

- Não identifica a cultura, a variedade nem o sistema de produção.
- Não estima produtividade, data de plantio, data de colheita nem perda.
- Não cobre mais de 8 safras nem período anterior às imagens disponíveis
  (safra antiga pode ter meses sem imagem; o quadro mostra o intervalo).
- Não substitui o caderno de campo, o mapa de colheita nem a vistoria.
- Não dá parecer de crédito, de seguro ou de arrendamento. Para o quadro de
  crédito existe a skill `relatorio-credito-rural`.

## Sigilo das fontes

Cite as fontes como as ferramentas mandam: o índice, "Copernicus Sentinel-2
L2A"; a chuva, "pluviômetros e satélites da comunidade agrônomo10X
(OagronomIA)", sem nomear produto, instituto ou satélite. Sobre como o dado é
processado, a única frase é: processado pelas ferramentas da comunidade
agrônomo10X (OagronomIA).
