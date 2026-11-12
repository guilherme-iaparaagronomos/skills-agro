# Amostragem georreferenciada — como o plano é calculado

Notas para quem quiser auditar (ou melhorar) a implementação de `scripts/`.

## Quem decide o quê

O script desenha; o responsável técnico decide a densidade, o modo, o número
de subamostras e as camadas. Essas escolhas dependem do objetivo (diagnóstico,
taxa variável, monitoramento), da cultura, do histórico da área e do custo, e
nenhuma delas sai de uma fórmula.

Quando o usuário pede um ponto de partida, estas são referências de uso comum
no Brasil. Apresente-as como referência, não como recomendação:

- **Grade**: malhas comerciais costumam ficar entre 1 e 5 ha por ponto. Malha
  mais fina mostra mais detalhe e custa mais análises; malha larga pode não
  captar a variação e deixar a interpolação fraca (as skills de interpolação
  medem isso na validação cruzada).
- **Amostra composta**: os manuais estaduais de adubação pedem, em geral, de
  10 a 30 amostras simples por amostra composta. Vale o manual do estado.
- **Camadas**: 0–20 cm é a mais comum em culturas anuais; 20–40 cm entra para
  avaliar acidez e cálcio em profundidade. Quem define é o manual e o objetivo.

## Grade

- Densidade → espaçamento: na grade quadrada, `e = √(área por ponto)`; na
  triangular, `e = √(área por ponto ÷ 0,866)`, com as linhas afastadas de
  `0,866 × e` e deslocadas de meio passo, uma sim e outra não.
- A grade é centrada na caixa do talhão e deslocada de meio passo, para o
  ponto cair no **centro** de cada malha. Um ponto em cima da divisa não
  representa o talhão.
- `--angulo` gira a grade em torno do centro do talhão (por exemplo, para
  acompanhar as linhas de plantio ou os terraços).
- Ficam os pontos dentro do perímetro e a pelo menos `--borda` metros do
  contorno, incluídos os contornos internos (furos).
- A ordem é a serpentina: uma linha em um sentido, a seguinte no outro.

## Célula

- Células quadradas de lado `--lado` (ou `√(ha por célula)`), com as bordas
  passando pelo centro do talhão.
- Cada célula é testada em 11 × 11 pontos. Com menos de 25 % deles dentro do
  perímetro, a célula sai.
- As subamostras são escolhidas entre esses pontos de teste, as mais afastadas
  entre si (primeiro o ponto mais central, depois sempre o mais distante dos já
  escolhidos). Célula de borda tem menos lugares e pode ficar com menos
  subamostras que o pedido.

## Zona

- Sobre cada zona vai uma malha fina de pontos candidatos (uns 12 por
  subamostra pedida), respeitando a borda. Se a borda pedida não deixar
  candidatos suficientes numa zona estreita, ela é relaxada naquela zona.
- Com `--ha-por-amostra`, o número de amostras da zona é a área dividida por
  esse valor, arredondada (no mínimo 1). Os candidatos são separados em grupos
  compactos por k-médias, com início determinístico, e cada grupo vira uma
  amostra.
- Dentro de cada grupo as subamostras são as mais afastadas entre si, para
  cobrir a parte toda, que é o que o caminhamento em zigue-zague busca.

## Rota

- Grade e células: serpentina.
- Compostas: vizinho mais próximo a partir do ponto mais a oeste, melhorado
  por 2-opt (desfaz cruzamentos), até 400 pontos por amostra.
- A distância é a soma das retas entre pontos seguidos, por talhão. Não conta
  o deslocamento entre talhões, estradas nem obstáculos.

## IDs

- `nome do talhão` → só letras e números, em maiúsculas (`Talhão 01` vira
  `TALHAO01`; `MIN 01` vira `MIN01`), cortado em 12 caracteres.
- Amostra: `<talhão>-<nn>`. Subamostra: `<talhão>-<nn>.<k>`.
- As skills `interpolacao-idw` e `interpolacao-krigagem` casam `T01-03` com
  `t1-3`, `T1 - 3` e parecidos; ainda assim, peça ao laboratório para manter o
  ID da planilha.
- O nome do talhão é lido do atributo do arquivo. A ordem de procura: `talhao`,
  `plot_name`, `field_name` e parecidos; depois qualquer campo com "talh",
  "plot", "field", "gleba" ou "zona" no nome; depois `nome`, `name`, `id`. Sem
  nada disso, `A01`, `A02`… Use `--listar-campos` e `--campo-area` para acertar.

## Arquivos e coordenadas

- Cálculo em UTM / SIRGAS 2000 (zona pelo centro do perímetro ou pelo `.prj`).
- Saída em graus, SIRGAS 2000 (EPSG:4674), que na prática coincide com o
  WGS 84 do GPS.
- Shapefile de pontos escrito em Python puro, sem projeção e sem Z ou M, com
  os campos `ID`, `AREA`, `AMOSTRA` e `ORDEM`.
- GPX com os pontos (`wpt`) e a rota (`rte`) na ordem da caminhada.

## Limites da v1

- Não usa mapa de índice, de produtividade nem de relevo para dirigir os
  pontos. Para isso, desenhe as zonas antes e use o modo `zona`.
- A caminhada não considera carreadores, cercas nem cursos d'água.
- Talhão muito estreito pode ficar sem ponto na grade: o script avisa.
