---
name: diagnostico-variabilidade
description: >-
  Mostra o que varia junto com a variabilidade de um talhão: põe o mapa de
  produtividade (ou outra variável) e as camadas disponíveis numa grade comum
  e descreve quem acompanha quem. Entram o perímetro e as camadas em GeoTIFF,
  pontos densos ou polígonos com classe: solo, relevo, índices de vegetação de
  outras safras, condutividade elétrica, drone, zonas. Sai o diagnóstico das
  camadas e, com as escolhas do usuário, as correlações com intervalo que
  respeita a semelhança entre células vizinhas, a parte de cada camada, as
  manchas de valor baixo, médio e alto com o perfil de cada camada, tabelas e
  PDF. Só descreve: variar junto não é causa, e a skill não
  recomenda correção nem manejo. A variável a explicar e as camadas são
  escolha do usuário. Acione com "o que explica a variabilidade do talhão",
  "por que essa mancha produz menos", "cruza a produtividade com o solo",
  "diagnóstico da variabilidade", "correlação entre os mapas" ou quando o
  usuário trouxer um mapa de produtividade e outras camadas do mesmo talhão.
---

# Diagnóstico da variabilidade do talhão

O usuário tem um mapa que varia dentro do talhão (em geral a produtividade) e
outras camadas do mesmo lugar. A skill responde a uma pergunta só: **o que
varia junto com ele?** Entrega:

1. o **diagnóstico das camadas**: o que cada arquivo cobre, com que
   resolução, e quais camadas se repetem;
2. as **correlações** com a variável a explicar, cada uma com o intervalo de
   95% calculado com o número de observações independentes do mapa;
3. a **parte de cada camada**: sozinha, por cima das outras e repartida;
4. as **manchas**: o talhão em faixas de valor baixo, médio e alto, e a média
   de cada camada em cada faixa;
5. os arquivos: `relato.md`, quatro CSV, o mapa das manchas em GeoTIFF, as
   figuras e `relatorio.pdf`.

Quem faz a conta é o script `scripts/variabilidade.py`.

## A regra que vale para tudo: descreve, não explica

- Diga **"acompanha"**, **"varia junto"**, "sobe junto", "desce quando ela
  sobe". NUNCA diga "causa", "explica", "é por causa de", "o problema é", "o
  fator limitante é". Variar junto não é causa: uma terceira coisa pode mexer
  nas duas, ou pode ser acaso. Diga isso junto do resultado, sempre.
- NUNCA recomende calagem, adubação, gessagem, subsolagem, troca de variedade,
  taxa variável nem outro manejo, e não diga o que "corrigir". O que fazer com
  o resultado é decisão do responsável técnico, que conhece a área.
- **A variável a explicar e as camadas que entram são do usuário.** Mostre o
  diagnóstico, pergunte, e só então rode. Não escolha por ele nem use "todas"
  sem ele dizer.
- **Células de um mapa não são amostras independentes.** Dez mil células de um
  mapa suave valem algumas dezenas de observações. Por isso a skill não dá
  valor de p: dá o intervalo com o número de observações independentes. Não
  conserte isso por fora nem diga "altamente significativo" porque há muitas
  células.
- Intervalo que inclui o zero: diga "não se distingue do acaso", e não
  "tendência" nem "relação fraca".
- **Camadas parecidas repartem a importância.** Quando duas dizem quase a
  mesma coisa, o resultado não diz qual das duas pesa. Repita o aviso.
- **Índice de vegetação da mesma safra é quase a própria resposta.** Se a
  variável a explicar é a produtividade de 2024, o NDVI de 2024 não entra como
  camada: ele é outro retrato da mesma lavoura. Índices de outras safras
  entram.
- Não use palavra que qualifica: bom, ruim, problema, crítico, limitante,
  deficiente.
- Se o usuário pedir a conclusão ("o que eu corrijo?", "é a argila?"), diga
  que a análise não conclui, mostre o que acompanha o quê e devolva a decisão
  a ele e ao responsável técnico.

## O que precisa estar disponível

- **Um ambiente que rode Python** com `numpy`, `scipy` e `matplotlib`. Sem
  ele, não faça correlação de cabeça nem "de olho" nos mapas: diga que a skill
  precisa de um ambiente com código.
- **O perímetro** do talhão: GeoJSON, KML, shapefile ou WKT.
- **As camadas**, em arquivo, pelo menos duas (a variável a explicar e mais
  uma):

| O que é | Como chega | De onde costuma vir |
|---|---|---|
| mapa de produtividade | pontos limpos (CSV) ou GeoTIFF | skill `limpeza-monitor-produtividade`; exportação do monitor |
| atributos de solo | um GeoTIFF por atributo | skills `interpolacao-krigagem` e `interpolacao-idw` |
| relevo (altitude, declive) | GeoTIFF | ferramenta `relevo_fazenda` da ClaudIA Sat; QGIS |
| índice de vegetação de outra safra | GeoTIFF | ferramentas `composto_indice` e `imagem_satelite` da ClaudIA Sat |
| condutividade elétrica, sensor, drone | pontos densos ou GeoTIFF | o equipamento; QGIS |
| zonas, variedades, talhões | polígonos com a classe | skill `zonas-de-manejo`; o cadastro da fazenda |

GeoTIFF em SIRGAS 2000 / UTM, WGS 84 / UTM ou em graus. Outro sistema (SAD
69, por exemplo) é recusado: peça para reexportar. As ferramentas da ClaudIA
Sat consomem a franquia de hectares do usuário: só chame se ele pedir, e diga
antes quanto vai consumir.

**Laudo de solo em pontos esparsos não entra direto.** Com uma amostra por
hectare, quase todas as células ficariam vazias. Interpole antes, com uma das
skills de interpolação, e traga o GeoTIFF.

## Antes de rodar: as perguntas (numa mensagem só)

1. **O perímetro e os arquivos** de cada camada, com o nome que cada uma vai
   ter.
2. **De que safra é cada índice de vegetação**, e de que safra é a
   produtividade.
3. **De quantas amostras saiu cada mapa de solo** (para dizer, no relato, que
   mapa de poucas amostras é suave).
4. Para os polígonos: **qual campo** traz a classe.

A variável a explicar, as camadas que entram, a célula e as faixas ficam para
depois do diagnóstico. O que ele já disse, não pergunte de novo.

## Fluxo de trabalho (siga nesta ordem)

1. **Rode o diagnóstico** (não analisa nada):
   ```
   python scripts/variabilidade.py --perimetro talhao.geojson \
       --raster argila=argila.tif --raster altitude=altitude.tif \
       --pontos colheita_limpa.csv --classes variedade=variedades.geojson:variedade \
       --diagnostico --saida saida
   ```
   - `--raster nome=arquivo.tif`, um por camada (`arquivo.tif:2` para a banda 2);
   - `--pontos arquivo.csv`: cada coluna numérica vira uma camada com o nome
     da coluna (`--pontos prefixo=arquivo.csv` põe o prefixo no nome);
   - `--classes nome=arquivo.geojson:campo` para polígonos com classe.
2. **Mostre o diagnóstico ao usuário**, inteiro: a tabela das camadas, as
   notas, os pares parecidos. Preste atenção em:
   - camada com cobertura baixa (a análise só usa as células que têm valor em
     todas);
   - "varia devagar no talhão": poucas observações independentes;
   - pares "quase iguais";
   - pontos esparsos para a célula.
3. **Pergunte o que é dele**: a variável a explicar; quais camadas entram;
   qual fica de fora por ser da mesma safra ou repetida; se a célula
   automática serve (`--celula`); e como repartir as manchas (três faixas de
   mesma área é o padrão; `--faixas 2` a `5`, ou `--cortes` com os valores
   que ele usa). Se ele disser "escolhe você", explique em uma frase o que
   muda e devolva a pergunta. **Sem a resposta, não rode.**
4. **Rode a análise** com as escolhas:
   ```
   python scripts/variabilidade.py --perimetro talhao.geojson \
       --raster argila=argila.tif --raster altitude=altitude.tif --pontos colheita_limpa.csv \
       --classes variedade=variedades.geojson:variedade \
       --alvo prod_t_ha --camadas argila,altitude --com-classes variedade \
       --nome "Talhão 12" --saida saida
   ```
5. **Relate**: escreva na conversa o conteúdo de `relato.md` (a leitura, a
   tabela camada por camada, as manchas, os avisos e o "como ler") e mostre
   `manchas.png` e `importancia.png`. Abra o PDF e olhe antes de entregar.
6. **Repita todos os avisos com as palavras do script.** Eles são parte do
   resultado.
7. **Outra escolha é outra rodada**: tirar uma camada, mudar a célula ou os
   cortes muda os números. Rode de novo e diga o que mudou. Não rode várias
   combinações para ficar com a que dá o resultado mais forte.

Para ver funcionando sem dado nenhum: `python scripts/variabilidade.py --demo`
(talhão inventado, com relações plantadas; o script diz quais escolhas foram
fixadas só no exemplo).

## Como ler o que sai

| Coluna | O que é |
|---|---|
| r (Pearson) | correlação em linha reta com a variável a explicar, de −1 a +1 |
| Intervalo de 95% | a faixa do r, contando só as observações independentes. Se inclui o zero, não se distingue do acaso |
| Spearman | a correlação das posições (ordem). Longe do Pearson: relação que não é reta, ou valores extremos |
| Observações independentes | quanto o mapa vale em observações soltas, descontada a semelhança entre vizinhas |
| Sozinha | a parte da variação que a camada acompanha sem as outras (R²) |
| Por cima das outras | quanto o conjunto perde quando só ela sai |
| Repartida | a média do que ela acrescenta em todas as ordens de entrada; as partes somam o R² do conjunto |
| Piso de ruído | o R² que o mesmo número de camadas sem relação nenhuma alcança por acaso |
| Alto − baixo, em desvios | a diferença da camada entre a faixa mais alta e a mais baixa, em desvios dela |

- Duas camadas altas em "sozinha" e perto de zero em "por cima das outras":
  são redundantes.
- "Por cima das outras" maior que "sozinha": as outras camadas escondiam a
  relação. Vale para as classes também: a média crua de cada variedade
  mistura o efeito das outras camadas.
- R² do conjunto perto do piso de ruído: não há o que ler.
- Nota "relação em curva": há um valor do meio em que a variável a explicar é
  maior (ou menor). A conta de reta não vê; o perfil das manchas mostra.

## Parâmetros

| Parâmetro | O que faz | Padrão |
|---|---|---|
| `--alvo` | a variável a explicar | **sem padrão: o usuário escolhe** |
| `--camadas` | as camadas numéricas, separadas por vírgula (`todas` só se ele disser) | **sem padrão** |
| `--com-classes` | as camadas de classes que entram | nenhuma |
| `--celula` | lado da célula da grade, em metros | automática: a partir de 10 m, até 20 mil células |
| `--faixas` | número de faixas de mesma área nas manchas (2 a 5) | 3 |
| `--cortes "3,2;4,0"` | cortes das faixas, com os valores do usuário | os quantis |
| `--sem-filtro` | não tira células soltas das manchas | filtro de maioria ligado |
| `--mancha-minima` | área mínima, em ha, para contar como mancha | 0,5% da área |
| `--zona 22S` | zona UTM do perímetro em metros sem `.prj` | a do arquivo |
| `--x`, `--y` | colunas de coordenada dos pontos | reconhecidas pelo nome |
| `--sem-pdf` | não grava figuras nem PDF | grava |

A célula não deve ser menor que a resolução de verdade das camadas: célula de
10 m com mapa de solo de uma amostra por hectare só multiplica células
repetidas. O diagnóstico mostra o pixel de cada raster e o espaçamento dos
pontos. O método e os limites: `references/metodo.md`.

## O que a skill não faz

- Não diz a causa da variabilidade nem recomenda correção.
- Não interpola laudo de solo, não limpa mapa de colheita e não faz zonas de
  manejo: para isso existem as skills `interpolacao-krigagem`,
  `interpolacao-idw`, `limpeza-monitor-produtividade` e `zonas-de-manejo`.
- Não compara talhões nem safras: uma rodada, um talhão, uma variável.
- Não enxerga relação que depende de outra camada (interação) nem ótimo no
  meio, a não ser pela nota de curva e pelo perfil das manchas.
- Não substitui a ida ao talhão: mancha que nenhuma camada acompanha pode ter
  motivo que não está em mapa nenhum (praga, falha de plantio, compactação,
  histórico).

## Recusas

O script para e diz o motivo quando: falta o perímetro ou há só uma camada;
um raster não é GeoTIFF, está noutro sistema de coordenadas ou não cobre o
talhão; nenhum ponto cai dentro do perímetro; duas camadas têm o mesmo nome;
menos de 50 células têm valor em todas as camadas escolhidas; a variável a
explicar ou uma camada é constante; os cortes deixam uma faixa vazia. Repasse
o motivo como veio e não contorne.
