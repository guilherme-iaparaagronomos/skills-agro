# Como o script acha os ciclos

## O dado

A `curva_com_chuva` devolve, para cada talhão, a média do índice de vegetação
em cada imagem limpa do período: uma lista de datas e valores. Entre duas
imagens não há dado. Em época de chuva é comum passar 20, 30 ou mais dias sem
imagem limpa.

O script trabalha em cima dessa lista. Ele não baixa imagem e não refaz a
conta do índice.

## Passo a passo

1. **Uma linha por data.** Duas imagens no mesmo dia viram uma, com a média.
2. **Série emendada.** As janelas consultadas (um ano agrícola depois do
   outro) são juntadas numa série só por talhão. Janelas separadas por mais de
   20 dias viram trechos independentes, e o quadro avisa.
3. **Queda isolada.** Sai da conta a imagem que fica `queda` (padrão 0,10) ou
   mais abaixo da anterior e também da seguinte, com as duas a até 20 dias
   dela. É o desenho de nuvem ou sombra que sobrou: o índice cai numa imagem e
   volta na outra. Queda que não volta fica na série, porque pode ser
   colheita, dessecação ou geada. O quadro diz quantas imagens saíram, e a
   figura marca cada uma com ×.
4. **Picos.** É candidato o ponto mais alto que os vizinhos (num patamar, a
   primeira data). O candidato vale como pico de um ciclo quando o índice sobe
   pelo menos `amplitude_min` (padrão 0,20) acima do menor valor de cada lado,
   olhando até encontrar um ponto mais alto que ele ou a ponta da série. Na
   ponta da série basta metade da amplitude, desde que o outro lado tenha a
   amplitude inteira: é o ciclo cortado pelo período consultado.
5. **Picos que são o mesmo ciclo.** Dois picos a menos de `distancia_min`
   dias (padrão 45), ou sem um vale de `amplitude_min` entre eles, contam como
   um ciclo; fica o mais alto e, no empate, o primeiro.
6. **Base.** De cada lado do pico, a base é o menor valor entre ele e o pico
   vizinho (ou a ponta da série).
7. **Início e fim.** O início é o dia em que a curva, subindo, passa do nível
   `base + fração × (pico − base)`; o fim, o dia em que, descendo, passa do
   mesmo nível calculado com a base do outro lado. A fração padrão é 0,30. A
   data sai por interpolação em linha reta entre as duas imagens vizinhas, e
   as duas vão escritas junto ("entre 29/10 e 08/11").
8. **Duração.** Dias entre o início e o fim.
9. **Safra do ciclo.** O ciclo é contado na safra em que caiu o pico.

## O que cada observação quer dizer

| Observação | Leitura |
|---|---|
| "início: N dias sem imagem entre A e B" | a subida passou do nível em algum dia desse intervalo; a data é a do meio da reta |
| "pico: N dias sem imagem entre A e B" | o valor mais alto de verdade pode ter caído no intervalo e não aparecer |
| "começou antes do período consultado" | a série já começa com o índice alto; não há como datar o início |
| "não terminou dentro do período consultado" | a série acaba antes de a curva descer |
| "a primeira imagem do período já marca X" | a subida pode ter começado antes da primeira janela |
| "a última imagem do período ainda marca X" | a descida pode continuar depois da última janela |
| "o período começa com a curva em queda" | fim de um ciclo anterior, que não entra na contagem |
| "o período termina com um ciclo em aberto" | subida sem descida suficiente até a última imagem |
| "nenhum ciclo com amplitude de X ou mais" | o índice oscilou menos que a amplitude mínima |

## Limites que valem sempre

- **A data é do verde, não da operação.** Entre o plantio e a subida do
  índice passam de alguns dias a algumas semanas, conforme a cultura, a
  palhada e a chuva. O fim pode ser maturação, dessecação, colheita, geada ou
  seca.
- **A média do talhão esconde a mancha.** Talhão com duas culturas, com
  reboleira ou com parte em pousio dá uma curva que não é de nenhuma das
  partes.
- **Pasto, cana, café, eucalipto e mata** não têm o desenho de sobe e desce de
  uma lavoura anual. Com a amplitude padrão o script pode não achar ciclo, ou
  achar um por ano que é a estação das chuvas. Nesses casos o que o quadro
  mostra é a estação, e isso deve ser dito.
- **Nuvem.** Com intervalos longos sem imagem, o pico e as datas ficam menos
  certos, e uma segunda safra curta pode passar sem ser vista.
- **Os números padrão são uma convenção.** Amplitude de 0,20 e fração de 0,30
  são escolhas razoáveis para NDVI de lavoura anual; não são norma. Mudando a
  fração, as datas de início e fim andam; o pico não muda.
- **Série curta.** Com menos de 5 imagens no trecho o script não procura
  ciclo.

## A chuva

O total, a média histórica (1991–2020) do mesmo período e a diferença em %
vêm da linha `RESUMO` da `clima_historico`, como a ferramenta devolveu. Os
dias de chuva e os veranicos vêm da `curva_com_chuva`, com a régua que ela
informa (por padrão, 7 ou mais dias seguidos com menos de 2 mm por dia). Com a
janela do ano agrícola, os veranicos do inverno seco entram na contagem.

O sinal ▼ marca a safra com chuva 20% ou mais abaixo da média histórica do
período (`--abaixo-pct` muda o corte). É uma marca sobre o número, não um
laudo de seca.
