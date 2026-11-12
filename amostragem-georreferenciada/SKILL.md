---
name: amostragem-georreferenciada
description: >-
  Plano de amostragem georreferenciada a partir do perímetro dos talhões:
  pontos de coleta numerados em grade regular, em células com amostra composta
  ou por zona de manejo. Entrega a rota de caminhamento, a planilha de campo,
  o mapa e os arquivos para o GPS (KML, GPX, shapefile, GeoJSON e CSV). Serve
  para solo, nematoides, pragas, plantas daninhas ou qualquer coleta feita em
  pontos. Os IDs já saem no formato que as skills interpolacao-idw e
  interpolacao-krigagem casam com o laudo. Acione com "grade amostral",
  "pontos de amostragem", "plano de amostragem", "amostragem de solo",
  "amostragem por zona", "onde coletar" ou quando o usuário trouxer o
  perímetro pedindo os pontos de coleta.
---

# Amostragem Georreferenciada — do perímetro aos pontos de coleta

Recebe o perímetro dos talhões e devolve o **plano de coleta**: onde ficam os
pontos, como se chamam, em que ordem caminhar, a planilha para levar a campo
e os arquivos que o GPS ou o aplicativo abre.

## Para que serve
- Desenhar a coleta em três jeitos: **grade** (um ponto por malha),
  **célula** (uma amostra composta por célula) e **zona** (amostras compostas
  por zona de manejo ou por talhão).
- Numerar cada amostra com o nome do talhão (`T01-03`), para o laudo voltar do
  laboratório e casar sozinho com os pontos na interpolação.
- Ordenar a caminhada, estimar a distância e contar as amostras de laboratório.

## Para que NÃO serve
- **Não decide a densidade nem o modo.** Quantos hectares por ponto, quantas
  subamostras e quais camadas são decisão do responsável técnico. PERGUNTE;
  nunca escolha por ele. Referências de uso comum estão em
  `references/amostragem.md`, para quando ele pedir um ponto de partida.
- Não faz amostragem dirigida por mapa de índice ou de produtividade (v1).
  Com as zonas já desenhadas em polígonos, use o modo `zona`.
- Não navega até o ponto: entrega o arquivo para o GPS ou aplicativo dele.

## Entradas

1. **Perímetro dos talhões**: `.kml`, `.geojson`, `.shp` (com `.dbf` e `.prj`)
   ou WKT. Cada polígono é uma área; o nome dela vira o começo do ID.
2. **Zonas** (só no modo `zona`, opcional): polígonos das zonas de manejo. Sem
   o arquivo, cada talhão é tratado como uma zona.

`.zip`/`.kmz`: descompacte antes. Coordenadas em metros sem `.prj` exigem a
zona UTM: `--zona 22S`.

## Fluxo de trabalho (siga nesta ordem)

1. **Confira os nomes dos talhões** antes de tudo:
   `python scripts/amostragem.py --perimetro talhoes.shp --listar-campos`
   Mostre ao usuário os nomes que seriam usados. Se vierem `A01`, `A02`…, o
   script não achou o campo do nome: mostre os campos e os exemplos e pergunte
   qual é (`--campo-area plot_name`). O nome vira o ID da amostra, e ID errado
   é laudo que não casa.
2. **Pergunte o que define o plano**, uma pergunta por vez se preciso:
   - o que vai ser coletado (solo, nematoide, praga…): vai para o subtítulo;
   - o modo (tabela abaixo);
   - a densidade: hectares por ponto, por célula ou por amostra;
   - nas compostas, quantas subamostras por amostra;
   - as camadas, se for solo (ex.: `0-20,20-40`);
   - a distância mínima da divisa (padrão 15 m);
   - se quiser a conta do laboratório, o preço por amostra.
3. **Rode** com os números dele:
   `python scripts/amostragem.py --perimetro talhoes.shp --modo grade
   --ha-por-ponto 2 --camadas "0-20,20-40" --fazenda "Fazenda Exemplo"
   --finalidade solo --saida ./plano`
4. **Mostre o mapa** (`mapa_amostragem.png`) e diga o resumo que o script
   imprime: amostras, pontos, hectares por amostra, quilômetros de caminhada
   e amostras para o laboratório. Repasse todo aviso (talhão em que nenhum
   ponto coube, por exemplo).
5. **Ajuste se ele pedir**: densidade, `--angulo` para alinhar a grade com as
   linhas de plantio, `--arranjo triangular`, `--borda`. Cada rodada refaz
   tudo; os mesmos parâmetros dão sempre os mesmos pontos.
6. **Entregue os arquivos** dizendo para que serve cada um (tabela abaixo).
7. **Feche o ciclo**: quando o laudo voltar, os IDs da planilha são os que as
   skills `interpolacao-idw` e `interpolacao-krigagem` procuram. Diga isso.

## Os três modos

| Modo | O que é uma amostra | Parâmetros | Quando se usa |
|---|---|---|---|
| `grade` | cada ponto | `--ha-por-ponto` ou `--espacamento`; `--arranjo`; `--angulo` | mapear a variação dentro do talhão e interpolar |
| `celula` | a célula inteira (composta) | `--ha-por-celula` ou `--lado`; `--subamostras` | reduzir o número de análises mantendo a malha |
| `zona` | a zona, ou parte dela (composta) | `--zonas`; `--ha-por-amostra`; `--subamostras` | já existem zonas de manejo, ou se quer uma amostra por talhão |

- Na **grade**, o ponto fica no centro de cada malha, nunca em cima da divisa.
- Na **célula**, só entra a célula com pelo menos 25 % da área dentro do
  perímetro. Célula de borda pode ficar com menos subamostras que o pedido.
- Na **zona**, sem `--ha-por-amostra` cada zona recebe uma amostra. Com ele,
  a zona é dividida em partes de tamanho parecido, uma amostra por parte.
- Nas compostas, o ponto de cada subamostra tem ID próprio (`T01-02.7`) e a
  amostra de laboratório é o `T01-02`.

## Os arquivos

| Arquivo | Para quê |
|---|---|
| `mapa_amostragem.pdf` / `.png` | mostrar e imprimir |
| `planilha_de_campo.csv` | uma linha por amostra e por camada, com data, coletor e observação em branco |
| `pontos.gpx` | GPS de mão e aplicativos de navegação (pontos e rota) |
| `pontos.kml` | Google Earth e aplicativos de campo |
| `pontos-shapefile.zip` | QGIS e sistemas de agricultura de precisão (pontos em graus, SIRGAS 2000) |
| `pontos.geojson`, `pontos.csv` | QGIS, planilha e as skills de interpolação |
| `celulas.geojson` | os quadros das células (modo `celula`) |
| `resumo.json` | os números do plano |

## Detalhes fixos

- IDs: `--numeracao por-area` (padrão) gera `<TALHÃO>-<nn>`, com o nome do
  talhão sem espaços nem acentos; `--numeracao corrida` gera `P001`, `P002`…
  Dois talhões com o mesmo nome recebem um número para não repetir ID.
- A ordem dos pontos é a da caminhada: serpentina na grade e nas células;
  caminho curto entre as subamostras nas compostas. A distância informada é em
  linha reta entre os pontos, dentro de cada talhão.
- Coordenadas de saída em graus, SIRGAS 2000 (EPSG:4674); o CSV traz também
  as UTM. Os cálculos são feitos em UTM.
- Nada é sorteado: o plano é reprodutível.
- `python scripts/amostragem.py --demo` roda os três modos numa fazenda de
  exemplo; `python scripts/<nome>.py` roda os testes de cada módulo.
- Como cada desenho é calculado e as referências de densidade:
  `references/amostragem.md`.
