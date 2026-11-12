# Os filtros, um por um

A limpeza só **remove** pontos. A ordem importa: cada filtro trabalha sobre o
que sobrou dos anteriores, e o ponto fica com o motivo do primeiro filtro que
o tirou.

## Antes dos filtros: as passadas

Depois de tirar posição inválida e ponto fora do perímetro, o script divide os
pontos em **passadas** (os tiros da máquina), na ordem do arquivo. Uma passada
nova começa quando:

- a coluna de passada do arquivo muda (se houver);
- o relógio para por mais que 4 vezes o intervalo típico (piso de 5 s) ou anda
  para trás;
- a máquina salta mais que 4 vezes o passo típico (piso de 20 m);
- o rumo vira mais de 60° (manobra gravada).

Sem hora e sem coluna de passada, valem só a distância e o rumo, e o relatório
avisa.

## 1. Posição inválida ou repetida
Ponto sem coordenada, ou com a mesma coordenada (até o centímetro) de um ponto
anterior. Fica o primeiro. Sempre roda.

## 2. Fora do perímetro
Ponto fora de todos os polígonos enviados. É o filtro que pega salto de GPS e
deslocamento com a máquina gravando. Só roda com perímetro.

## 3. Valor ausente ou impossível
Ponto sem valor. No perfil `colheita`, também zero e negativo. `--minimo` e
`--maximo` põem os limites físicos que o usuário conhece (por exemplo, teto de
produtividade da cultura). Com `--minimo` dado pelo usuário, fica quem é igual
ou maior que ele.

## 4. Bordadura
Ponto a menos de `--borda` metros da divisa mais próxima (inclusive a divisa
entre dois talhões do mesmo arquivo). Desligado por padrão: cabeceira costuma
ter dado ruim, mas quem decide a largura é o usuário.

## 5. Velocidade fora da faixa
Máquina quase parada ou rápida demais dá valor errado, porque a produtividade
é fluxo dividido por velocidade e largura. O padrão do perfil `colheita` tira
quem está fora de **50% a 150% da mediana de velocidade do próprio arquivo**,
então não depende da unidade. `--vel-min` e `--vel-max` valem na unidade da
coluna. O diagnóstico diz em que unidade a coluna parece estar, comparando com
a velocidade calculada pela posição e pelo relógio.

## 6. Variação brusca de velocidade
Ponto em que a velocidade mudou mais que a fração `--vel-variacao` em relação
ao ponto anterior da mesma passada. Desligado por padrão; o diagnóstico mostra
quantos pontos passam de 25%.

## 7. Largura de trabalho parcial
Ponto com largura abaixo da fração `--largura-min` da largura cheia (a mais
comum do arquivo). Desligado por padrão, porque máquina com controle de seção
grava largura parcial com o valor já certo. O diagnóstico compara a mediana do
valor nos pontos de largura parcial com a dos de largura cheia: se a parcial
for muito diferente, o valor ali está errado e vale ligar o filtro.

## 8. Umidade fora da faixa
`--umid-min` e `--umid-max`. Desligado por padrão.

## 9. Começo e fim de passada
No começo de cada passada a máquina ainda está enchendo e o valor vem baixo;
no fim, esvaziando. O filtro corta `--inicio` pontos no começo e `--fim` no
fim de cada passada. **É em pontos, não em segundos** (o relatório mostra os
segundos quando há hora).

Com `auto` (padrão do perfil `colheita`), o corte é medido no arquivo: em cada
passada longa, divide-se o valor de cada um dos 15 primeiros pontos pela
mediana do trecho vizinho (os 15 seguintes), e tira-se a mediana entre as
passadas. O corte vai até o valor se firmar em 90% do trecho vizinho, com teto
de 12 pontos. O mesmo no fim, de trás para frente. O gráfico "Entrada e saída
das passadas" mostra a curva. Sem pelo menos 5 passadas de 60 pontos, não há
medida: nada é cortado e o relatório avisa.

Este filtro **não** corrige o atraso do grão dentro da máquina (o deslocamento
entre onde a planta foi cortada e onde o sensor leu). Isso é correção de
posição, que a skill não faz.

## 10. Passada curta
Passada com menos de `--passada-min` pontos (padrão 5 no perfil `colheita`):
arremate, manobra, ponto solto depois de um salto.

## 11. Fora dos limites do conjunto
Valor longe do resto do talhão. Métodos (`--global`), com o fator `--global-k`:

| Método | Limites | Fator padrão |
|---|---|---|
| `mad` | mediana ± k × desvio robusto (1,4826 × desvio absoluto mediano) | 3 |
| `dp` | média ± k × desvio-padrão | 3 |
| `iqr` | 1º quartil − k × distância interquartil; 3º quartil + k × distância | 1,5 |
| `pct` | mediana ± k % | 50 |

O padrão é `mad`, porque a média e o desvio-padrão são puxados pelos próprios
erros que se quer tirar. **Cuidado**: limite do conjunto não distingue erro de
mancha real. O script confere se os pontos que saíram estão agrupados (a
maioria dos 8 vizinhos também saiu) e avisa quando mais de 40% deles estão.

## 12. Diferente dos vizinhos
Cada ponto contra a **mediana dos vizinhos** dentro do raio (até 40 vizinhos):

- `pct`: sai o ponto que difere mais que `--local-limite` % da mediana local
  (padrão 30% no perfil `colheita`);
- `mad`: sai o ponto a mais de `--local-limite` desvios robustos locais
  (padrão 4 no perfil `sensor`, em que porcentagem não faz sentido para valor
  perto de zero ou com cota alta).

O raio automático é a distância mediana ao 12º vizinho, com folga, em número
redondo. Ponto com menos de `--local-viz` vizinhos (padrão 4) não é julgado, e
o relatório avisa se isso passar de 5% dos pontos. É este filtro que pega o
erro que fica dentro dos limites do talhão, e é ele que preserva a mancha
real: numa reboleira, os vizinhos também são baixos.

## Os dois perfis

- **`colheita`**: monitor de colheita. Tem passada, velocidade e enchimento.
- **`sensor`**: condutividade elétrica, sensor de dossel, altimetria. Sem
  enchimento de máquina, sem filtro de velocidade, valor pode ser negativo ou
  ter cota alta; vizinhança por desvio robusto.

Não há perfil separado por cultura: a diferença entre grãos e cana está nos
números (velocidade, quantos pontos de enchimento), e esses o diagnóstico mede
no próprio arquivo.

## Como a skill foi medida

Em colheita **simulada**: 16 mil pontos, 46 passadas, com erros plantados em
pontos sabidos (enchimento e esvaziamento, máquina quase parada, picos, zeros,
erro local, passada com meia plataforma, salto de GPS, posição repetida) e uma
mancha real de baixa produtividade. Com os padrões do perfil `colheita`, saem
100% dos erros plantados e 0,05% dos pontos bons, e a mancha fica no mapa
limpo. Dado de máquina de verdade é mais sujo e mais variado do que isso; por
isso o diagnóstico vem antes e o mapa do que saiu vai no relatório.

## Fontes

Os filtros seguem ideias publicadas; a skill não é reimplementação de nenhum
programa.

- Blackmore, B. S.; Moore, M. (1999). Remedial correction of yield map data.
  *Precision Agriculture*, 1, 53–66.
- Menegatti, L. A. A.; Molin, J. P. (2004). Remoção de erros em mapas de
  produtividade via filtragem de dados brutos. *Revista Brasileira de
  Engenharia Agrícola e Ambiental*, 8(1), 126–134.
- Sudduth, K. A.; Drummond, S. T. (2007). Yield Editor: software for removing
  errors from crop yield maps. *Agronomy Journal*, 99(6), 1471–1482.
- Spekken, M.; Anselmi, A. A.; Molin, J. P. (2013). A simple method for
  filtering spatial data. In: *Precision Agriculture '13*. Wageningen Academic
  Publishers.
- Vega, A.; Córdoba, M.; Castro-Franco, M.; Balzarini, M. (2019). Protocol for
  automating error removal from yield maps. *Precision Agriculture*, 20,
  1030–1044.
- Maldaner, L. F.; Molin, J. P.; Spekken, M. (2022). Methodology to filter out
  outliers in high spatial density data to improve maps reliability. *Scientia
  Agricola*, 79(1).
