# Método, conferência e limites

Esta página diz o que cada conta faz, contra o que ela foi conferida e até
onde a skill vai. Vale para quem for explicar um resultado ao usuário.

## 1. Da planilha ao ensaio

- **Leitura**: uma linha por parcela, cabeçalho na primeira linha. O
  separador (ponto e vírgula, tabulação, vírgula, barra) e a vírgula decimal
  são detectados. Em XLSX é lida a primeira planilha, ou a de `--planilha`;
  fórmula entra pelo valor guardado; data vira número e não serve de fator.
- **Papel das colunas**: é palpite, pelo nome e pelo jeito dos valores. Texto
  que se repete vira fator; número que se repete em quantidades iguais, fator
  (dose); número medido, resposta; sequência sem repetição, identificador.
  "Bloco" é bloco; "Rep" fica em aberto, porque pode ser bloco ou só o número
  da repetição. Quem confirma é o usuário.
- **Estrutura**: antes de analisar, o script confere se o arquivo tem a
  estrutura do delineamento informado e recusa o que não cobre.

| Delineamento | Exigência |
|---|---|
| DIC, um fator | pelo menos um grau de liberdade no resíduo; aceita repetições desiguais |
| DBC, um fator | uma parcela de cada tratamento em cada bloco |
| Fatorial em DIC | as combinações com o mesmo número de repetições, duas ou mais |
| Fatorial em blocos | uma parcela de cada combinação em cada bloco |
| Parcela subdividida | em blocos; o primeiro fator na parcela, o segundo na subparcela |

Linha sem valor na resposta é contada como parcela perdida. No DIC a análise
segue com repetições desiguais. Em blocos e em fatorial ela é recusada: a
skill não estima parcela perdida.

## 2. Análise de variância

Cada fonte de variação entra no modelo linear na ordem do quadro, e a soma de
quadrados dela é o quanto a soma de quadrados do resíduo cai quando ela entra
(mínimos quadrados). Em dado balanceado isso dá o mesmo que as fórmulas de
totais dos livros, e o teste embutido confere as duas contas.

- **DIC**: tratamentos e resíduo.
- **DBC**: blocos, tratamentos e resíduo.
- **Fatorial**: (blocos), A, B, A × B e resíduo.
- **Parcela subdividida**: blocos, A e erro (a) (blocos × A); B, A × B e erro
  (b). Blocos e A são testados contra o erro (a); B e A × B, contra o erro
  (b). Saem dois coeficientes de variação.
- **CV** = 100 × raiz(QM do resíduo) ÷ média geral.

## 3. Pressupostos

Calculados sobre os resíduos do modelo:

- **Shapiro-Wilk** para a normalidade.
- **Bartlett** e **Levene** (centrado na mediana, a versão de Brown e
  Forsythe) para a homogeneidade de variâncias entre os tratamentos (no
  fatorial, entre as combinações). Em blocos e em fatorial os resíduos de um
  mesmo tratamento não são independentes, e o resultado é aproximado.
- **Resíduos discrepantes**: resíduo padronizado (dividido pelo seu
  desvio-padrão, que leva em conta a alavanca da parcela) acima de 3 em
  módulo. O script aponta a linha do arquivo e não retira nada.

A marca "abaixo de 0,05" nesses testes é referência usual, para chamar a
atenção. Ela não é a significância da análise, que o usuário escolhe.

**Transformações** (`log`, `log1`, `raiz`, `raiz05`, `arcsen`): o diagnóstico
refaz o modelo em cada escala que o dado aceita e mostra o CV e os valores de
p dos pressupostos. Nada é aplicado sem pedido. O CV de escalas diferentes não
se compara. Com transformação, o teste roda na escala transformada, as letras
valem para ela, e a tabela traz também a média aritmética na escala original.

## 4. Testes de médias

Todos usam o quadrado médio e os graus de liberdade do erro que testa aquele
fator (o resíduo; na parcela subdividida, o erro (a) para o fator da parcela
e o erro (b) para o da subparcela).

- **Tukey**: amplitude estudentizada com o número total de médias. Com
  repetições desiguais, Tukey-Kramer.
- **t (LSD)**: t de Student par a par, sem ajuste.
- **SNK** e **Duncan**: amplitudes críticas que dependem de quantas médias
  há na faixa. No Duncan, o nível de cada faixa de p médias é
  1 − (1 − α)^(p − 1). Vale a regra de proteção: duas médias dentro de uma
  faixa não significativa não são declaradas diferentes.
- **Scott-Knott**: as médias ordenadas são partidas no ponto que dá a maior
  soma de quadrados entre os dois grupos (B0); testa-se
  λ = π ÷ (2(π − 2)) × B0 ÷ σ0², com
  σ0² = [Σ(média − média geral)² + GL × QM ÷ r] ÷ (k + GL), contra o
  qui-quadrado com k ÷ (π − 2) graus de liberdade. Se a partição é
  significativa, repete-se em cada grupo.
- **Dunnett**: cada tratamento contra a testemunha, bilateral. A
  probabilidade conjunta é integrada numericamente e aceita repetições
  desiguais.
- **Letras**: duas médias têm letra em comum se, e só se, o teste não as
  separou. A letra "a" fica com a maior média.

**Fatorial**: se a interação é significativa no nível escolhido (ou se o
usuário pedir), as médias de um fator são comparadas dentro de cada nível do
outro. A tabela de dupla entrada usa minúsculas para comparar na coluna e
maiúsculas na linha, e o relatório traz o teste F de cada fatia. Sem
interação, as médias são comparadas por fator.

**Parcela subdividida, com desdobramento**: B dentro de A usa o erro (b). A
dentro de B usa a variância combinada [(b − 1) × QM(b) + QM(a)] ÷ b, com os
graus de liberdade de Satterthwaite.

## 5. Regressão polinomial

Para um fator quantitativo com três níveis ou mais (um fator, em DIC ou DBC).
Os graus de liberdade de tratamentos são desdobrados em linear, quadrático e
cúbico (até onde os níveis permitem) e desvios da regressão, cada um testado
contra o resíduo do delineamento. As equações são ajustadas às médias. R² é a
parte da soma de quadrados de tratamentos que a equação descreve. O grau é
escolha do usuário; o script mostra todos. O vértice da parábola só aparece
quando cai dentro do intervalo testado, como propriedade da curva.

## 6. Como foi conferida

Com dados inventados, em novembro de 2026:

| O quê | Contra o quê | Resultado |
|---|---|---|
| Quadro do DIC | `scipy.stats.f_oneway` | igual |
| Quadro do DBC, do fatorial (DIC e blocos) e da parcela subdividida | modelo de mínimos quadrados do `statsmodels` | somas de quadrados, F e p iguais |
| Erro (a) da parcela subdividida | análise em blocos das médias de parcela e componentes de variância de um modelo misto | F e p de A iguais; variâncias iguais |
| Erros da parcela subdividida no desdobramento (A dentro de B e B dentro de A) | erro-padrão da diferença num modelo misto (`statsmodels`) | iguais |
| Resíduos padronizados | `statsmodels` (resíduo estudentizado interno) | iguais |
| Desdobramento da interação | F conjunto no modelo de médias de caselas (`statsmodels`) | igual |
| Regressão | somas de quadrados sequenciais e coeficientes do `statsmodels` | iguais |
| Tukey e Tukey-Kramer | `scipy.stats.tukey_hsd` e `statsmodels` | valores de p iguais |
| t (LSD) em blocos | contraste entre dois tratamentos no modelo linear | igual |
| Dunnett | `scipy.stats.dunnett` e, com um tratamento só, o teste t | iguais, dentro do erro numérico do scipy |
| Tukey, SNK, Duncan, t e Dunnett | simulação de 40 mil ensaios sem diferença verdadeira | a frequência de falso positivo bate com a teoria de cada teste |
| Scott-Knott | a mesma simulação; soma de quadrados entre grupos refeita pela definição | ver abaixo |
| Letras | 23 mil pares sorteados, com repetições desiguais | letra em comum se, e só se, o par não diferiu |
| Leitura de XLSX | arquivo gravado por outra biblioteca | a mesma análise do CSV |

**Scott-Knott**: não havia na máquina outra implementação para comparar
número a número. A conferência foi a simulação: sem diferença verdadeira, o
teste formou mais de um grupo em 5,6% dos ensaios com 5 tratamentos, 4,0% com
10 e 4,4% com 20 (nível de 5%), e em 0,6% com 8 tratamentos no nível de 1%.
É o comportamento esperado de um teste aproximado no nível nominal. Com dois
grupos verdadeiros afastados quatro desvios, recuperou os dois em 89% dos
ensaios.

A skill não foi usada num ensaio de verdade publicado, nem comparada com os
programas de estatística mais usados na agronomia.

## 7. Limites

- Um ou dois fatores. Sem quadrado latino, faixas, blocos incompletos,
  tratamento adicional, medidas repetidas, análise conjunta.
- Blocos e fatorial só com dado completo e balanceado.
- SNK, Duncan e Scott-Knott só com repetições iguais.
- Dunnett só com um fator. Regressão só com um fator.
- Todos os testes supõem resíduos normais e variâncias homogêneas. A skill
  mostra os testes dos pressupostos e não decide por eles.
- Em fatorial com dose, as doses são comparadas como níveis separados.
- Contagem, proporção e nota têm modelos próprios, que a skill não ajusta. A
  transformação é o que ela oferece, a pedido.

## 8. Referências

- Tukey (1949), Comparing individual means in the analysis of variance.
  Kramer (1956), extensão para repetições desiguais.
- Newman (1939) e Keuls (1952), o teste de amplitudes em etapas.
- Duncan (1955), Multiple range and multiple F tests.
- Dunnett (1955), A multiple comparison procedure for comparing several
  treatments with a control.
- Scott e Knott (1974), A cluster analysis method for grouping means in the
  analysis of variance.
- Shapiro e Wilk (1965); Bartlett (1937); Levene (1960); Brown e Forsythe
  (1974).
- Satterthwaite (1946), An approximate distribution of estimates of variance
  components.
- Piepho (2004), An algorithm for a letter-based representation of
  all-pairwise comparisons.
