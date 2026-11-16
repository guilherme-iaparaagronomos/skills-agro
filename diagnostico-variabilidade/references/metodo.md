# Como a conta é feita, e até onde ela vai

## 1. A grade comum

Todas as camadas vão para a mesma malha de células quadradas, em UTM, cortada
pelo perímetro. A célula automática é a menor da lista (10, 15, 20, 25, 30,
40, 50 m...) que deixa a área com até 20 mil células; o usuário pode informar
outra.

- **Raster**: o valor no centro da célula, por interpolação bilinear. Quando o
  pixel é menor que a célula, a célula recebe a média de 4 a 36 pontos
  espalhados dentro dela (a mesma conta da reamostragem "média").
- **Pontos**: a média dos pontos que caem na célula. Célula sem ponto fica
  vazia; não há interpolação aqui.
- **Polígonos com classe**: a classe do polígono onde cai o centro da célula.

A análise usa só as células que têm valor na variável a explicar e em todas
as camadas escolhidas. O relato diz quantas são e, quando sobra menos de 80%
da área, qual camada mais limita.

## 2. Correlações

Pearson (linha reta) e Spearman (ordem) entre a variável a explicar e cada
camada, e entre as camadas. Os coeficientes usam todas as células completas:
como descrição, estão certos. O que muda com a dependência espacial é quanta
confiança eles merecem.

## 3. Por que não há valor de p, e o que há no lugar

Num mapa, a célula ao lado quase repete a vizinha. O teste comum de
correlação supõe observações independentes; com milhares de células de dois
mapas suaves, ele chama de "significativa" quase qualquer coisa. Na simulação
desta skill, com dois mapas **sem relação nenhuma**, o teste comum acusou
relação em 59% a 93% das vezes.

O que a skill faz:

1. Calcula o **correlograma** de cada camada: a correlação entre células
   separadas por cada distância, contando só os pares em que as duas têm
   valor (as somas são feitas por transformada de Fourier, o que dá conta de
   contorno irregular e de falhas).
2. Calcula o **número de observações independentes** de cada par pela
   correção de Clifford, Richardson e Hémon (1989), a mesma ideia do teste t
   modificado de Dutilleul (1993):

   `var(r) = Σ N(h) · ρx(h) · ρy(h) / n²` e `n_ef = 1 + 1 / var(r)`

   onde `h` percorre as defasagens, `N(h)` é o número de pares de células em
   cada defasagem e `ρx`, `ρy` são os correlogramas das duas camadas. A soma
   vai até a distância em que o produto dos dois correlogramas deixa de ser
   positivo; esse corte é escolha desta skill, não dos artigos.
3. Dá o **intervalo de 95%** de r pela transformação z de Fisher, com `n_ef`
   no lugar do número de células.

Leitura: se o intervalo inclui o zero, a relação não se distingue do acaso.

**Como isso foi conferido.** Com campos aleatórios de suavidade conhecida,
num talhão de contorno irregular com 5 mil células, 300 repetições por caso:

| Suavidade dos dois mapas (em células) | Relação acusada sem existir, com `n_ef` | Com o número de células |
|---|---|---|
| nenhuma (ruído) | 4,0% | 4,0% |
| 3 e 3 | 5,0% | 59% |
| 6 e 6 | 4,7% | 80% |
| 3 e 12 | 6,7% | 77% |
| 12 e 12 | 6,3% | 88% |
| 20 e 20 | 8,3% | 93% |

O certo é 5%. Com mapas muito suaves (as duas últimas linhas, com menos de 35
observações independentes) o intervalo fica um pouco estreito demais. Com
relação plantada de r = 0,5, o intervalo cobriu o valor verdadeiro em 96% a
98% das vezes.

**O preço**: com poucas observações independentes, relação fraca de verdade
também não se distingue do acaso. No exemplo inventado, repetido em 24
talhões, a relação mais forte (argila) foi reconhecida nos 24; a mais fraca
(altitude, r perto de −0,4) em 12; e a camada sem relação foi dada como
relação em 2.

A **distância de correlação** do diagnóstico é onde o correlograma da camada
cai abaixo de 1/e (0,37). As "observações independentes" do diagnóstico são o
`n_ef` da camada com ela mesma.

## 4. A parte de cada camada

Tudo por regressão linear de mínimos quadrados, com as camadas padronizadas.
Camada de classes entra como um bloco de colunas 0/1, uma por classe menos a
primeira; o R² desse bloco sozinho é a fração da variância entre as classes.

- **Sozinha**: R² só com a camada.
- **Por cima das outras**: R² do conjunto menos o R² do conjunto sem ela.
- **Repartida**: a média do que a camada acrescenta ao R² em todas as ordens
  de entrada possíveis. É o método de Lindeman, Merenda e Gold (1980),
  descrito em Grömping (2006), igual ao valor de Shapley. As partes somam o
  R² do conjunto. Exige o R² de todos os subconjuntos (2 elevado ao número de
  camadas): com mais de 12 camadas a coluna não é calculada.

Os três números contam histórias diferentes e é por isso que vão juntos:

| Sozinha | Por cima das outras | O que está acontecendo |
|---|---|---|
| alta | alta | a camada acompanha a variável de um jeito que as outras não repetem |
| alta | perto de zero | outra camada diz quase a mesma coisa (redundância) |
| baixa | maior que sozinha | as outras escondiam a relação |
| baixa | perto de zero | não acompanha |

**Piso de ruído**: o R² que `p` colunas sem relação nenhuma alcançam em 95%
das vezes com `n_ef` observações independentes: o quantil 95% da distribuição
Beta(p/2, (n_ef − p − 1)/2). Usa o menor `n_ef` entre a variável a explicar e
as camadas, o que é uma aproximação conservadora. Quando há mais colunas que
observações independentes, o relato diz que o R² do conjunto não se separa do
acaso.

O **fator de inflação** (no CSV) é 1/(1 − R²) da camada contra as outras: de 5
para cima, a nota diz que ela é muito parecida com o conjunto das outras.

A nota **"relação em curva"** aparece quando uma curva de segundo grau na
camada, sozinha, acompanha pelo menos 5 pontos percentuais a mais que a reta.

## 5. As manchas

A variável a explicar é repartida em faixas: por padrão três, por quantis,
com a mesma área; ou pelos cortes que o usuário informar. Uma passada de
filtro de maioria 3 × 3 troca a célula solta pela faixa das vizinhas (dá para
desligar). "Mancha" é um pedaço contíguo de uma faixa com pelo menos 0,5% da
área (ou o mínimo informado).

O perfil é a média e o desvio de cada camada em cada faixa. "Alto − baixo, em
desvios" é a diferença das médias entre a faixa mais alta e a mais baixa,
dividida pelo desvio da camada em toda a área. Serve para comparar camadas de
unidades diferentes. É descrição do que há em cada mancha.

## 6. O que a análise não diz

- **Causa.** Camadas que se acompanham podem depender de uma terceira que não
  foi enviada (profundidade do solo, histórico de uso, compactação, data de
  plantio). O resultado depende de quais camadas entraram.
- **Qual de duas camadas parecidas pesa.** A repartição divide o que elas têm
  em comum; isso é uma convenção, não uma descoberta.
- **Relação que não é reta.** Ótimo no meio aparece só na nota de curva e no
  perfil das manchas. Efeito que depende de outra camada (interação) não
  aparece.
- **Outro talhão, outra safra.** Vale para os dados que entraram.
- **Mapa interpolado não é medição em cada célula.** Um mapa de solo de uma
  amostra por hectare tem a suavidade que a interpolação deu a ele. Ele
  acompanha outros mapas suaves com facilidade, e é por isso que o número de
  observações independentes dele é pequeno.
- **Índice de vegetação da mesma safra** da produtividade é outro retrato da
  mesma lavoura: entra como resposta, não como camada.
- **Erro de posição.** Mapa de colheita com atraso de fluxo não corrigido, ou
  camadas com deslocamento de alguns metros, enfraquecem a correlação.
  Aumentar a célula reduz esse efeito.

## Referências

- Clifford, P.; Richardson, S.; Hémon, D. (1989). Assessing the significance
  of the correlation between two spatial processes. *Biometrics*, 45(1),
  123–134.
- Dutilleul, P. (1993). Modifying the t test for assessing the correlation
  between two spatial processes. *Biometrics*, 49(1), 305–314.
- Lindeman, R. H.; Merenda, P. F.; Gold, R. Z. (1980). *Introduction to
  Bivariate and Multivariate Analysis*. Scott, Foresman.
- Grömping, U. (2006). Relative importance for linear regression in R: the
  package relaimpo. *Journal of Statistical Software*, 17(1).
