---
name: estatistica-experimental
description: >-
  Analisa ensaios agronômicos: lê a tabela, descreve o delineamento e confere
  os pressupostos; com o teste e a significância que o usuário escolher,
  entrega a análise de variância, as médias com letras e o relatório.
  Cobre DIC, DBC, fatorial duplo (em DIC ou em blocos, com desdobramento da
  interação), parcela subdividida em blocos e regressão polinomial para fator
  quantitativo. Testes de médias: Tukey, t (LSD), SNK, Duncan, Scott-Knott e
  Dunnett. Mostra Shapiro-Wilk, Bartlett, Levene, resíduos discrepantes e o
  que cada transformação faria. Nunca escolhe o teste, a significância, a
  transformação nem o grau da regressão: pergunta. Saídas: quadro da ANOVA,
  CV, médias com letras, gráfico, CSV e PDF. Acione com "análise de
  variância", "ANOVA", "teste de Tukey", "Scott-Knott", "comparação de
  médias", "analisar meu experimento", "estatística do ensaio", "DBC", "DIC",
  "fatorial", "parcela subdividida", "regressão de doses" ou quando o usuário
  enviar a planilha de um ensaio com tratamentos e repetições.
---

# Estatística experimental

Faz a análise estatística de um ensaio agronômico a partir da planilha das
parcelas: o quadro da análise de variância, o coeficiente de variação, os
pressupostos, a comparação de médias com letras (ou a regressão, quando o
fator é dose) e o relatório em PDF.

## Para que serve
- Descrever o delineamento que está no arquivo e conferir se ele fecha.
- Conferir os pressupostos da análise de variância sobre os resíduos.
- Rodar o teste de médias **que o usuário escolher**, na significância **que
  ele escolher**, e entregar a tabela com letras, o gráfico e o relatório.

## Para que NÃO serve
- **Não escolhe o teste nem a significância.** Também não escolhe a
  transformação nem o grau da regressão. Mostra os números e pergunta.
- **Não recomenda** cultivar, produto, dose nem manejo. Descreve o resultado
  estatístico; a interpretação agronômica é do responsável técnico.
- **Não cobre**: três fatores ou mais; parcela perdida em blocos; fatorial
  desbalanceado; blocos incompletos; quadrado latino; faixas; fatorial com
  tratamento adicional; medidas repetidas no tempo; análise conjunta de
  ensaios; testes não paramétricos; modelos para contagem ou proporção. O
  script recusa e diz por quê: repasse a recusa, não contorne.
- Não planeja nem sorteia experimento.

## O que pedir ao usuário
1. A **planilha do ensaio**, com **uma linha por parcela** e o cabeçalho na
   primeira linha: a coluna do tratamento (ou dos dois fatores), a do bloco
   (se houver) e a da resposta. CSV, TSV, TXT ou XLSX. Se a planilha estiver
   "deitada" (um bloco por coluna), reorganize para uma linha por parcela e
   mostre ao usuário como ficou antes de analisar.
2. **Como o ensaio foi instalado**: inteiramente casualizado, em blocos,
   fatorial, parcela subdividida. O arquivo nem sempre diz (veja o passo 2).
3. Depois do diagnóstico: **o teste e a significância**.

## Fluxo de trabalho (siga nesta ordem)

1. **Diagnóstico** (não compara médias):
   ```
   python scripts/analise.py --dados <planilha> --diagnostico --saida saida
   ```
   Se o palpite das colunas estiver errado ou houver mais de uma resposta,
   repita com `--resposta`, `--fatores` e `--bloco`.
2. **Mostre o que o diagnóstico disse e confirme com o usuário**:
   - **os papéis das colunas**: qual é a resposta, qual é o fator, qual é o
     bloco. O palpite sai do nome e do jeito dos valores e pode errar.
   - **o delineamento.** Duas coisas o arquivo não mostra, e o script avisa:
     uma coluna "Rep" pode ser **bloco** (DBC) ou só o **número da
     repetição** (DIC); e um fatorial em blocos pode ter sido instalado em
     **parcelas subdivididas**. Pergunte. Não presuma.
   - **parcelas sem valor** e linhas que o script apontou.
   - **os pressupostos**: os valores de p de Shapiro-Wilk, Bartlett e Levene
     e os resíduos discrepantes. Mostre `residuos.png`.
   - **o painel de transformações**, quando algum pressuposto ficou abaixo de
     0,05: o que cada transformação faria. Transformar ou não é decisão dele.
   - se o fator é **quantitativo** (doses): a tabela dos graus da regressão.
3. **Pergunte o teste e a significância.** Liste os testes que o ensaio
   aceita (o diagnóstico diz quais) com a linha de cada um da tabela abaixo.
   Se ele pedir "escolhe você", explique em uma frase o que muda de um para o
   outro e devolva a pergunta. **Sem a resposta dele, não rode.**
4. **Rode a análise** com o que ele escolheu:
   ```
   python scripts/analise.py --dados <planilha> --resposta <coluna> --fatores <fator[,fator]> \
       [--bloco <coluna>] [--subdividida] --teste <teste> --alfa <significância> \
       [--transformacao <qual>] [--testemunha "<nível>"] --nome "<ensaio>" --unidade <unidade> --saida saida
   ```
   Fator quantitativo, se ele quiser regressão: troque `--teste` por
   `--regressao --grau <1, 2 ou 3>` (o grau também é escolha dele).
5. **Relate o resultado inteiro**: o quadro da análise de variância; o CV; o
   F e o p de cada fonte, na significância escolhida; os pressupostos; a
   tabela de médias com as letras e a frase que explica as letras; a
   diferença mínima significativa, quando houver; e **todos os avisos, com as
   palavras do script**. Mostre `grafico.png`.
6. **Entregue os arquivos** e diga para que serve cada um. Se ele quiser
   outro teste, outra significância ou outra resposta, rode de novo e diga o
   que mudou. Cada resposta (produtividade, altura, massa) é uma análise.

Para ver a skill funcionando sem arquivo: `python scripts/analise.py --demo`
(dados inventados; também `--demo fatorial`, `--demo subdividida`,
`--demo doses`). O script diz que é exemplo e que o teste foi fixado só ali.

## Os testes, em uma linha cada

Para o usuário escolher. Não indique um.

| `--teste` | O que faz |
|---|---|
| `tukey` | Compara todos os pares mantendo o erro do conjunto de comparações no nível escolhido. Com repetições desiguais, usa Tukey-Kramer. |
| `t` | Teste t par a par (LSD), sem ajuste para o número de comparações: o erro vale para cada par, não para o conjunto. |
| `snk` | Student-Newman-Keuls: amplitudes que dependem de quantas médias há entre as duas comparadas. |
| `duncan` | Amplitudes múltiplas de Duncan: mais permissivo que o SNK; o erro do conjunto passa do nível escolhido. |
| `scott-knott` | Separa as médias em grupos sem sobreposição: cada média fica com uma letra só. |
| `dunnett` | Compara cada tratamento só com a testemunha (peça qual é: `--testemunha`). |

SNK, Duncan e Scott-Knott exigem o mesmo número de repetições em todos os
tratamentos. Dunnett vale para ensaio de um fator.

## Parâmetros

| Parâmetro | O que faz | Padrão |
|---|---|---|
| `--resposta` | coluna da variável analisada | obrigatório na análise |
| `--fatores a[,b]` | o fator, ou os dois do fatorial | obrigatório na análise |
| `--bloco` | coluna do bloco | sem ela, é DIC |
| `--subdividida` | o primeiro fator está na parcela e o segundo na subparcela | fatorial comum |
| `--teste` | teste de médias | **sem padrão: o usuário escolhe** |
| `--alfa` | significância: `5`, `1`, `0,05` | **sem padrão: o usuário escolhe** |
| `--transformacao` | `log`, `log1`, `raiz`, `raiz05`, `arcsen` | nenhuma |
| `--testemunha` | o nível de referência do Dunnett | — |
| `--desdobrar` | fatorial: `auto` desdobra só se a interação for significativa; `sim`; `nao` | `auto` |
| `--regressao --grau N` | regressão polinomial de grau N para fator quantitativo | — |
| `--planilha` | nome da planilha do XLSX | a primeira |
| `--nome`, `--unidade`, `--casas` | título, unidade e casas decimais do relatório | — |

O que cada conta faz, as fórmulas e os limites: `references/metodo.md`.

## Regras de honestidade

- **Diagnóstico antes, sempre.** Não rode a análise sem o usuário confirmar o
  delineamento.
- **Teste e significância vêm do usuário.** Se ele não disse, pergunte. Não
  use "o mais comum" por conta própria.
- **Transformação só a pedido.** O painel mostra o efeito; você não aplica
  nem sugere a "melhor". Com transformação, as letras valem para a escala
  transformada: diga isso.
- **Fale o que o teste disse, no nível escolhido**: "pelo teste de Tukey a
  5%, A e B não diferiram". Não diga "A é melhor", "recomenda-se A" nem "a
  dose ideal é". "Não diferiu" não é "é igual".
- **O ponto de máximo de uma parábola é propriedade da curva ajustada**, não
  a dose a recomendar. Diga assim.
- **Não esconda aviso**: pressuposto abaixo de 0,05, resíduo discrepante, F
  não significativo, interação significativa com desdobramento desligado.
- **Não retire dado.** O script aponta o resíduo discrepante e a linha do
  arquivo; conferir e decidir é do usuário. Se ele corrigir a planilha, rode
  de novo.
- **Recusa é recusa.** Se o script diz que não cobre (parcela perdida em
  blocos, três fatores), não improvise outra conta: diga o que falta.
- A skill foi conferida contra outras bibliotecas e por simulação, com dados
  **inventados**. Não foi usada num ensaio de verdade publicado.

## Saídas (na pasta `--saida`)

- `relatorio.pdf` — o quadro da análise de variância e os pressupostos; as
  médias com letras e o gráfico (ou a tabela de dupla entrada e o
  desdobramento, ou a regressão); os resíduos. `relatorio.png` é a primeira
  página.
- `anova.csv`, `medias.csv`, `pares.csv` — o quadro; as médias com letras; e
  cada par de médias, com a diferença, se difere e, em Tukey e t, o valor de
  p. Ponto e vírgula e vírgula decimal.
- `grafico.png` — barras com letras, linhas da interação ou a curva.
- `residuos.png` — quantis normais, resíduo × ajustado e resíduo por
  tratamento.
- `analise.json` — todos os números e as escolhas.
- No diagnóstico: `diagnostico.json` e `residuos.png`.

## Dependências

Python com `numpy`, `scipy` (1.7 ou mais novo para Tukey, SNK e Duncan) e
`matplotlib`. Sem internet.
