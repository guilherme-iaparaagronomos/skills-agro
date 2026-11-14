# O método, etapa por etapa

A skill agrupa **pontos** que carregam as camadas e depois transforma o
resultado em polígonos. Quando as camadas vêm em raster, ela primeiro lê os
rasters numa grade de pontos.

## 0. Preparo

- **Perímetro e pontos** vão para UTM (SIRGAS 2000), na zona do talhão. Ponto
  fora do perímetro sai.
- **Rasters** são lidos em cada ponto por interpolação bilinear (o pixel mais
  próximo onde a interpolação esbarra em pixel sem dado). Sem arquivo de
  pontos, a skill cria uma grade regular com perto de 6 mil pontos no talhão
  (`--espacamento` muda isso).
- **Ponto sem valor** em alguma camada sai. Se passar de 5% dos pontos, há
  aviso: provavelmente um raster não cobre o talhão inteiro.
- **Dado denso** (mais de 20 mil pontos, como colheita): a skill tira a média
  por célula antes de agrupar (`--agregar`). Dado ponto a ponto de colheita é
  ruidoso, e a média por célula mostra o padrão.

## 1. Padronização e pesos

Cada camada é posta em média 0 e desvio 1, para argila em g/kg e altitude em
metros pesarem igual. Com `--pesos`, a camada padronizada é multiplicada pelo
peso: peso 2 conta em dobro; 0,5, pela metade.

## 2. Componentes principais

As camadas padronizadas viram componentes principais, e ficam as que somam
90% da variação (`--variancia-pca`). Isso tira repetição entre camadas
parecidas e ruído. Mesmo assim, duas camadas quase iguais (correlação acima
de 0,9) puxam a divisão para o lado delas: o diagnóstico e o relatório
avisam.

## 3. K-Means e o número de grupos

O K-Means separa os pontos em `k` grupos de valores parecidos (início
k-means++, cinco partidas, sempre a mesma semente: o resultado se repete).

Para escolher `k`, o diagnóstico roda de 2 a 8 grupos e mede a **silhueta**
de cada um: de −1 a 1, quanto mais alta, mais separados os grupos. Em conjunto
grande, a silhueta é medida numa amostra de 4 mil pontos.

| Silhueta | Como ler |
|---|---|
| acima de 0,5 | grupos bem separados |
| de 0,25 a 0,5 | grupos existem, com sobreposição |
| abaixo de 0,25 | as camadas não formam grupos nítidos |

A maior silhueta é a **sugestão**. Ela é estatística: não sabe quantas zonas
a máquina aplica, nem o tamanho que compensa manejar. Muitas vezes 2 grupos
têm a maior silhueta e o usuário precisa de 3 ou 4. Por isso o diagnóstico
mostra também quantas zonas sobram depois do refino e quanto explicam.

## 4. Classe pequena é absorvida

Grupo com menos de 10% dos pontos (`--area-minima`) não vira zona: os pontos
dele passam para o grupo mais comum entre os vizinhos. Por isso o número final
de zonas pode ser menor que o `k` pedido, e o relatório avisa quando é.

## 5. Fragmentos soltos

Depois do K-Means sobram pontos e pedaços de uma classe no meio de outra. A
skill liga cada ponto aos 8 mais próximos (`--vizinhos`) e acha os pedaços de
cada classe que não se ligam ao resto dela. O pedaço com **menos de 3% de
todos os pontos e menos de 20% dos pontos da própria classe**
(`--frag-total`, `--frag-classe`) passa para a classe mais comum ao redor.
Repete até dez vezes, enquanto houver o que mudar.

Um pedaço que passa de um dos dois limites fica: é uma parte de verdade da
zona, ainda que separada.

## 6. Da classe dos pontos à zona no chão

Cada célula de uma grade fina (um quarto do espaçamento dos pontos) recebe a
classe do **ponto mais próximo**. É o mesmo que desenhar a área de influência
de cada ponto e juntar as de mesma classe.

Depois, cada **parte** contígua de zona com menos de 10% da área
(`--area-minima`, o mesmo número da etapa 4) é fundida à parte vizinha com
quem divide a **maior divisa**, e fica com a zona dela. Da menor para a maior,
até não sobrar parte pequena com vizinha.

- Parte pequena **isolada** (um bloco separado do resto do talhão, sem
  vizinha) fica como está, e há aviso.
- Em talhão grande, 10% pode ser muita área: o diagnóstico diz quantos
  hectares dá. Diminua `--area-minima` se fizer sentido para a operação.

## 7. Polígonos

- A **divisa entre duas zonas** é traçada uma vez, simplificada (tolerância
  `--suavizar`, por padrão o espaçamento dos pontos) e arredondada pelo corte
  de cantos de Chaikin (duas passadas). A mesma linha serve às duas zonas:
  não fica fresta nem sobreposição.
- A **borda de fora** é encaixada no perímetro verdadeiro do talhão, com os
  cantos dele. As zonas somam a área do perímetro.
- A **área de cada zona** é a do polígono entregue.
- Os **números** das zonas seguem a média da camada de ordenação
  (`--ordenar-por`): zona 1 = menor média.

## 8. O que as zonas explicam

Para cada camada, a **redução de variância**: 1 − (variação dentro das zonas
÷ variação total). Vai de 0 a 100%. Zonas que explicam 80% de uma camada
separam bem aquela camada; abaixo de 10%, quase não separam, e há aviso.

## Limites

- **O método agrupa o que recebe.** Não sabe se a camada é boa. Mapa
  interpolado com poucos pontos entra como se fosse medido em cada lugar.
- **Vários talhões de uma vez**: as zonas são feitas para o conjunto, a mesma
  zona pode aparecer em mais de um talhão, a área mínima vale para o total, e
  carreador estreito entre talhões fica dentro da zona. Para zonas dentro de
  cada talhão, rode um por vez.
- **Camadas de datas diferentes** (safras, épocas de imagem): a skill não
  sabe a data. Juntar ou não é escolha do usuário.
- **Raster**: até 80 milhões de pixels; tiras ou ladrilhos; sem compressão,
  Deflate ou LZW; UTM (SIRGAS 2000 ou WGS 84) ou graus. Outro SRC, BigTIFF ou
  raster rotacionado: reexporte no QGIS.
- A divisa suavizada pode ficar a até uma tolerância (`--suavizar`) do
  limite entre os pontos. Para divisa colada nos pontos, use `--suavizar 0`.

## Como a skill foi medida

- **Talhão inventado** de 53 ha, com três zonas plantadas e ruído por cima
  (pela argila sozinha, um em cada sete pontos cairia na zona errada): o
  método escolheu 3 grupos e pôs 99,9% dos pontos na zona plantada.
- **Fazenda real** de 5 mil hectares e 20 talhões, com dois rasters de 5 m:
  rodou em 7 segundos, e as zonas seguiram a borda dos talhões.
- O leitor de GeoTIFF foi conferido contra arquivos gravados pelo GDAL em 18
  combinações de compressão, preditor, ladrilho, tipo e SRC.
- Em talhão de verdade não há gabarito: a conferência é no campo.

## Fontes

As etapas usam técnicas publicadas; a skill não é reimplementação de nenhum
programa.

- Arthur, D.; Vassilvitskii, S. (2007). k-means++: the advantages of careful
  seeding. *Proceedings of the 18th ACM-SIAM Symposium on Discrete
  Algorithms*, 1027–1035.
- Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation
  and validation of cluster analysis. *Journal of Computational and Applied
  Mathematics*, 20, 53–65.
- Fridgen, J. J. et al. (2004). Management Zone Analyst (MZA): software for
  subfield management zone delineation. *Agronomy Journal*, 96, 100–108.
- Douglas, D. H.; Peucker, T. K. (1973). Algorithms for the reduction of the
  number of points required to represent a digitized line or its caricature.
  *The Canadian Cartographer*, 10(2), 112–122.
- Chaikin, G. M. (1974). An algorithm for high-speed curve generation.
  *Computer Graphics and Image Processing*, 3, 346–349.
