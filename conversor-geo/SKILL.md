---
name: conversor-geo
description: >-
  Converte arquivos geográficos entre Shapefile, KML, KMZ, GeoJSON, GPX, CSV e
  WKT, reprojeta entre graus e UTM, mede a área em hectares, une talhões e
  conserta o que é seguro na geometria. Primeiro mostra o que o arquivo tem
  (tipo de geometria, campos, sistema de coordenadas, área e defeitos); só
  converte depois de resolver o que for ambíguo com o usuário. Preserva os
  atributos e confere o arquivo gravado relendo-o. Prepara o perímetro para a
  ClaudIA Sat. Recusa SAD 69, Córrego Alegre e outras projeções em vez de
  converter errado. Acione com "converter shapefile para KML", "KML para
  shapefile", "passar o KMZ para GeoJSON", "CSV de pontos para shapefile",
  "GPX para KML", "reprojetar para UTM", "qual a área deste arquivo", "unir os
  talhões num perímetro só", "consertar a geometria", "preparar o arquivo para
  a ClaudIA Sat" ou quando o usuário enviar um arquivo geográfico pedindo outro
  formato.
---

# Conversor de arquivos geográficos

Passa perímetros, talhões, pontos e linhas de um formato para outro sem perder
os atributos, e diz o que mudou no caminho. Roda no ambiente de código da IA,
com Python e numpy. Não usa internet nem conector.

## Para que serve
- Converter entre **Shapefile, KML, KMZ, GeoJSON, GPX, CSV e WKT**.
- **Reprojetar**: graus (SIRGAS 2000 ou WGS 84) para UTM e de volta, e de um
  fuso UTM para outro.
- Dizer a **área em hectares** de cada polígono e o total.
- **Unir talhões** num perímetro só (todos, ou por um campo), sumindo com a
  divisa interna.
- **Consertar** o que é seguro na geometria e relatar o resto.
- Deixar o perímetro **pronto para a ClaudIA Sat** (GeoJSON em graus, com os
  atributos).

## Para que NÃO serve
- **Não muda de datum.** SAD 69, Córrego Alegre e outras projeções
  (Policônica, Albers, Web Mercator) são recusados com a explicação. Converter
  sem os parâmetros oficiais desloca dezenas de metros.
- **Não recorta sobreposição.** Se dois polígonos se sobrepõem, a união avisa
  quais são e não dissolve.
- **Não decide a divisa.** Contorno que se cruza é relatado, não consertado.
- Não lê DWG, DXF, GeoPackage, File Geodatabase nem raster. Peça ao usuário
  para exportar do programa de origem em um dos sete formatos.
- Não é levantamento nem certidão: a área é a do desenho que o arquivo traz.

## O que pedir ao usuário
1. **O arquivo.** Shapefile vem em zip, com `.shp`, `.shx`, `.dbf` e `.prj`
   juntos. Só o `.shp` não basta: faltam os atributos e o sistema.
2. **Para que formato** ele quer, e para onde vai (QGIS, Google Earth, GPS,
   máquina, ClaudIA Sat). O destino muda a escolha.

O resto se pergunta depois de olhar o arquivo.

## Fluxo de trabalho (siga nesta ordem)

1. **Inspecione antes de tudo** (não converte nada):
   ```
   python scripts/converter.py <arquivo> --listar
   ```
2. **Mostre ao usuário o que saiu**: quantas feições e de que tipo, os campos
   com exemplos, o sistema de coordenadas e **de onde ele veio**, a área total
   e os defeitos de geometria. Não resuma demais: é aqui que ele vê se o
   arquivo é o que pensava.
3. **Resolva o que for ambíguo com ele.** Não escolha por conta própria:
   - `SRC: NÃO IDENTIFICADO`: as coordenadas estão em metros e o arquivo não
     diz o fuso. Pergunte o fuso e o hemisfério (o `.prj` que faltou, o
     projeto do QGIS ou quem gerou o arquivo sabem). **Nunca deduza o fuso
     pela cidade ou pelo estado.** Repita com `--src-entrada utm22s`.
   - `SRC … deduzido das coordenadas`: parecem graus, mas o arquivo não
     confirma. Diga isso e pergunte se o arquivo pode ser de um datum antigo
     (SAD 69).
   - `SRC: RECUSADO`: explique o motivo e peça o arquivo reprojetado no QGIS
     para SIRGAS 2000 (EPSG:4674).
   - `ATENÇÃO … INVERTIDAS`: confirme e use `--trocar-xy`.
   - `ATENÇÃO … fora do Brasil` com fuso informado: o fuso ou o hemisfério
     estão errados. Volte a perguntar.
   - CSV em que o script não achou as colunas: mostre as colunas e pergunte
     quais são a do x (ou longitude) e a do y (ou latitude). Use `--x` e
     `--y`, ou `--wkt` quando a geometria está numa coluna de texto.
   - Zip com mais de uma camada: pergunte qual (`--camada`), ou converta
     todas.
   - Defeito de geometria: diga quais feições e pergunte se aplica os
     consertos seguros (`--consertar`).
4. **Converta:**
   ```
   python scripts/converter.py <arquivo> --para <formato> --saida saida
   ```
   Formatos: `geojson`, `kml`, `kmz`, `shp`, `gpx`, `csv`, `wkt`.
5. **Confira a saída do script.** A linha `CONFERÊNCIA` tem de terminar em
   `CONFERE`: o script relê o arquivo gravado e compara o número de feições e
   a área. Se disser `NÃO CONFERE`, não entregue: mostre a diferença.
6. **Entregue** o arquivo e conte, com os números do script: quantas feições
   entraram e saíram, o sistema de entrada e o de saída, a área total, e
   **todos os avisos** (campo que mudou de nome, texto cortado, altitude
   descartada, feição sem geometria, o que o formato de destino não guarda).
   Junto vai o `<nome>_relatorio.txt`.

## Receitas

| Pedido | Comando |
|---|---|
| Shapefile para Google Earth | `--para kmz` (ou `kml`). Use `--campo-nome TALHAO` para o rótulo |
| KML ou KMZ para shapefile em UTM | `--para shp --src-saida utm` (o fuso é o do centro do arquivo) |
| Shapefile de UTM para graus | `--para shp --src-saida 4674` |
| Planilha de pontos para shapefile | `--para shp` (com `--x`, `--y` se preciso; `--src-entrada 22S` se for UTM) |
| Pontos para o GPS | `--para gpx` |
| Qualquer formato para o Excel | `--para csv --csv-br` (ponto e vírgula e vírgula decimal) |
| Perímetro para a ClaudIA Sat | `--para-sat` (GeoJSON em graus, com os atributos) |
| Um texto WKT só | `--para wkt --wkt-unico` |
| Talhões num perímetro só | `--para <formato> --unir` |
| Um polígono por fazenda ou cultura | `--para <formato> --unir-por <CAMPO>` |
| Consertar a geometria | `--para <formato> --consertar` |
| Só os polígonos de um arquivo misto | `--so poligonos` |
| Arquivo pesado para enviar como texto | `--simplificar 2` (muda o contorno: leia o aviso) |

## Regras

- **Área.** A área principal é a plana em UTM, no fuso do centro do arquivo: é
  a medida das outras skills da casa. O `--listar` mostra ao lado a área sobre
  o elipsoide, que é como o QGIS e o CAR medem. As duas diferem de −0,08% a
  +0,2%, conforme a distância ao meio do fuso. Diga qual está citando; se o
  usuário comparar com a área do CAR, use a do elipsoide.
- **SIRGAS 2000 e WGS 84** são tratados como o mesmo: diferem em centímetros.
  Trocar de um para o outro muda só o rótulo, e o script avisa.
- **KML, KMZ e GPX são sempre em graus.** GeoJSON sai em graus por padrão.
  Shapefile, CSV e WKT saem no sistema da entrada, a não ser que se peça
  outro com `--src-saida`.
- **Shapefile**: nome de campo tem até 10 caracteres, sem acento; um tipo de
  geometria por arquivo. Arquivo misto vira um shapefile por tipo, no mesmo
  zip. O script avisa cada campo que mudou de nome: repasse.
- **União**: exata quando as divisas coincidem (os mesmos vértices, ou o
  vértice de um talhão em cima da linha do outro, até 5 cm). Sobreposição não
  é dissolvida: o script diz quais feições se sobrepõem. Furo com menos de
  1 m de largura é relatado como fresta: mostre ao usuário antes de aumentar a
  `--tolerancia`.
- **Conserto** (`--consertar`): fecha o anel, tira vértice repetido e de ida e
  volta, divide o anel que se toca num vértice e descarta o que ficou sem
  área. Contorno que se cruza e furo fora do polígono **não** são mexidos: o
  relatório diz onde estão, e a correção é do usuário, no QGIS.
- **Simplificação** muda o contorno e desfaz divisas coincidentes. Só para
  enviar o arquivo como texto; nunca para medir ou para a máquina.
- **O que se perde por causa do formato** (o script avisa): altitude e medida
  (Z e M), estilos e ícones do KML, o polígono no GPX (vira trilha fechada) e
  os atributos no WKT.
- Não invente campo, nome de talhão nem coordenada. Arquivo vazio, cortado ou
  ilegível: diga o que o script respondeu e peça outro.

## Depois da conversão
- **ClaudIA Sat**: o GeoJSON do `--para-sat` vai no campo de perímetro das
  ferramentas, ou em `salvar_fazenda` para guardar com um nome.
- **Coleta de solo**: `amostragem-georreferenciada` recebe o perímetro.
- **Mapas e zonas**: `interpolacao-idw`, `interpolacao-krigagem` e
  `zonas-de-manejo` recebem GeoJSON, KML ou shapefile.

## Escopo
A skill converte e descreve o arquivo. Não avalia o imóvel, não diz se a área
está certa e não substitui o levantamento de campo nem o responsável técnico.

Formatos em detalhe, sistemas aceitos e recusados, como cada conta é feita e
os limites: `references/formatos.md`.
