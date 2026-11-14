---
name: zonas-de-manejo
description: >-
  Divide o talhão em zonas de manejo a partir das camadas que o usuário tiver
  (solo, produtividade, relevo, índice de vegetação), em pontos ou rasters, e
  entrega os polígonos, a tabela por zona e o relatório. Primeiro mostra o
  diagnóstico (camadas, repetição entre elas e o que cada número de zonas
  daria); depois agrupa por componentes principais e K-Means, limpa os
  fragmentos, funde as partes pequenas e desenha as divisas suavizadas, com a
  borda no perímetro do talhão. Saídas: GeoJSON, KML, shapefile, raster,
  tabelas e PDF. Acione com "zonas de manejo", "dividir o talhão em zonas",
  "unidades de gestão diferenciada", "ambientes de produção a partir dos
  mapas", "juntar os mapas em zonas" ou quando o usuário tiver várias camadas
  do mesmo talhão e quiser uma divisão para manejar.
---

# Zonas de manejo

Junta as camadas de um talhão (o que o usuário tiver: argila, matéria
orgânica, produtividade de várias safras, altitude, declive, índice de
vegetação, condutividade elétrica) e separa os lugares parecidos em **zonas**,
com polígonos prontos para o QGIS e para a máquina.

## Para que serve
- Transformar vários mapas do mesmo talhão numa divisão só.
- Mostrar o que cada zona tem de diferente: a média de cada camada por zona.
- Dizer **quanto** as zonas explicam de cada camada, para o usuário saber se a
  divisão é firme ou fraca.

## Para que NÃO serve
- **Não recomenda manejo.** Não diz dose, população, cultivar nem o que fazer
  em cada zona. Informa o agrupamento; a decisão é do responsável técnico.
- **Não cria dado.** As camadas já têm de existir. Para gerar mapas de solo,
  use `interpolacao-idw` ou `interpolacao-krigagem`; para limpar dado de
  colheita, `limpeza-monitor-produtividade`.
- **Não dá nota às zonas.** O número da zona é só a ordem da média de uma
  camada. "Zona 3" não quer dizer "melhor".
- Não substitui a conferência no campo: o método agrupa o que recebe.

## O que pedir ao usuário
1. O **perímetro** do talhão (GeoJSON, KML ou shapefile). Um talhão por vez
   dá o melhor resultado.
2. As **camadas**, de um destes jeitos (ou dos dois juntos):
   - um arquivo de **pontos** com as camadas em colunas (CSV/TXT com
     coordenadas, ou shapefile de pontos): grade amostral com o laudo, pontos
     de colheita já limpos, grade com valores amostrados de vários mapas;
   - **rasters GeoTIFF**, um por camada: mapas interpolados, índice de
     vegetação, altitude. Em UTM (SIRGAS 2000 ou WGS 84) ou em graus.
3. O que é cada camada, e se alguma deve **pesar mais**.

## Fluxo de trabalho (siga nesta ordem)

1. **Diagnóstico** (não gera zonas):
   ```
   python scripts/zonas.py --perimetro <perímetro> --pontos <pontos> --raster nome=<arquivo.tif> --diagnostico --saida saida
   ```
   Use só o que houver: `--pontos`, um ou mais `--raster nome=arquivo.tif`, ou
   os dois. O nome do raster é o nome da camada no relatório.
2. **Mostre ao usuário o que o diagnóstico disse** e **confirme com ele**:
   - **quais camadas entram.** O script lista as colunas numéricas e marca as
     que parecem identificador. Coluna de id, de data ou de número de amostra
     não é camada.
   - **camadas que andam juntas.** Se duas têm correlação acima de 0,9, a
     mesma informação entra duas vezes: pergunte se tira uma ou reduz o peso.
   - **o número de zonas.** Mostre a tabela inteira: para cada número, a
     silhueta, quantas zonas sobram depois do refino e quanto elas explicam.
     Diga a sugestão do script e que ela é um critério estatístico. Quem
     decide quantas zonas dá para manejar é ele.
   - **a área mínima.** O padrão é 10% da área: o diagnóstico diz quantos
     hectares isso dá. Zona ou parte menor que isso é absorvida pela vizinha.
   - **a camada que ordena os números** das zonas (padrão: a primeira).
3. **Gere as zonas** com o que ele confirmou:
   ```
   python scripts/zonas.py --perimetro <perímetro> --pontos <pontos> --colunas "a,b,c" \
       --raster nome=<arquivo.tif> --k <número> --nome "<talhão · safra>" --saida saida
   ```
   `--k auto` só se ele disser para ficar com o critério estatístico.
4. **Relate o resultado inteiro**: quantas zonas ficaram; hectares, % e
   número de partes de cada uma; a média de cada camada por zona; quanto as
   zonas explicam de cada camada; o que aconteceu no refino (classes
   absorvidas, fragmentos reatribuídos, partes fundidas); e **todos os
   avisos**, com as palavras do script. Mostre `relatorio-zonas.png`.
5. **Pare e converse antes de entregar** se houver aviso de silhueta abaixo
   de 0,25, de camada que as zonas quase não separam, de camadas repetidas ou
   de zona única. Nesses casos o mapa é uma divisão possível, não um limite
   firme: diga isso.
6. **Entregue** os arquivos e diga para que serve cada um. Se ele pedir outro
   número de zonas, outra área mínima ou outro peso, rode de novo e diga o
   que mudou.

Para ver a skill funcionando sem arquivo: `python scripts/zonas.py --demo`
(talhão inventado, com zonas plantadas; o script diz que é exemplo).

## Parâmetros

| Parâmetro | O que faz | Padrão |
|---|---|---|
| `--colunas a,b,c` | colunas do arquivo de pontos que entram como camadas | obrigatório com `--pontos` |
| `--raster nome=arquivo.tif[:banda]` | camada em GeoTIFF (repetível) | — |
| `--pesos a=2,b=0.5` | peso de cada camada | 1 para todas |
| `--k N` ou `--k auto` | número de zonas | obrigatório |
| `--k-min`, `--k-max` | faixa testada no diagnóstico e no `auto` | 2 a 8 |
| `--area-minima P` | menor zona e menor parte, em % da área | 10 |
| `--vizinhos N` | vizinhos usados no refino | 8 |
| `--frag-total P`, `--frag-classe P` | pedaço solto menor que P% do total E P% da classe é reatribuído | 3 e 20 |
| `--variancia-pca P` | % da variação guardada nas componentes | 90 |
| `--suavizar M` | tolerância das divisas entre zonas, em metros (0 = sem suavizar) | o espaçamento dos pontos |
| `--ordenar-por camada` | camada que dá a ordem dos números | a primeira |
| `--espacamento M` | grade de pontos usada para ler os rasters | automático |
| `--agregar M` | média por célula, para dado denso (`nenhum` desliga) | automático acima de 20 mil pontos |
| `--separar-partes` | no shapefile, uma feição por parte de zona | uma por zona |
| `--zona 22S` | zona UTM, para coordenadas em metros sem `.prj` | — |

O que cada etapa faz, quando mexer no padrão e os limites:
`references/metodo.md`.

## Regras de honestidade

- **Diagnóstico antes, sempre.** Não gere zonas sem o usuário confirmar as
  camadas e o número de zonas.
- **Nenhum parâmetro escolhido em silêncio.** Diga quais vai usar, inclusive
  os padrões.
- **Fale das zonas pelo que elas têm**: "a zona 1 tem a menor média de
  argila, 190 g/kg". Não chame de "zona boa", "zona ruim", "alto potencial"
  ou "baixo potencial": isso é interpretação do responsável técnico.
- **Diga quanto a divisão explica.** Zonas que explicam 80% de uma camada
  separam bem aquela camada; 10%, quase nada.
- **O resultado depende das camadas.** Camada de um ano atípico, mapa
  interpolado com poucos pontos ou dado sujo entram do jeito que estão. Se o
  usuário não souber a origem de uma camada, diga que isso limita o resultado.
- **Não esconda aviso** e não troque as palavras dele por outras mais leves.
- A skill foi medida em **talhão inventado com zonas plantadas** e rodada
  numa fazenda real; em talhão de verdade não existe gabarito, e a
  conferência é no campo.

## Saídas (na pasta `--saida`)

- `zonas.geojson`, `zonas.kml`, `zonas-shapefile.zip` — os polígonos, com a
  área e a média de cada camada por zona. A borda de fora segue o perímetro do
  talhão; a divisa entre duas zonas é a mesma linha nas duas.
- `zonas.tif` — raster com o número da zona, em UTM.
- `zonas-resumo.csv` — por zona: área, %, partes e média, desvio, mínimo e
  máximo de cada camada.
- `pontos-com-zona.csv` — os pontos usados, com a zona de cada um.
- `relatorio-zonas.pdf` — o mapa e a tabela; como foi feito; as camadas com
  o contorno das zonas. `relatorio-zonas.png` é a primeira página.
- `zonas.json` — todos os números e os parâmetros usados.
- No diagnóstico: `diagnostico.json`.

## Para onde vão as zonas

- `amostragem-georreferenciada` desenha a coleta por zona com o
  `zonas.geojson`: `--perimetro <perímetro> --modo zona --zonas zonas.geojson`.
- `layout-mapa-qgis` monta o mapa final no QGIS a partir do shapefile.

## Dependências

Python com `numpy`, `scipy` e `matplotlib`. Sem internet.
