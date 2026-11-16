# Os controladores e de onde vem cada informação

A pasta do pen drive de cada controlador vem do material de campo do fundador
da comunidade agrônomo10X (12/11/2026). O que está na coluna "Do fabricante"
foi lido num manual ou numa página de ajuda do próprio fabricante, em
16/11/2026. O que não foi achado em documento de fabricante está dito como
não confirmado: a skill não inventa limite, unidade nem caminho de menu.

| Controlador | Pasta no pen drive | Do fabricante |
|---|---|---|
| Trimble CFX 750 | `AgGPS/Prescriptions/` | nada confirmado |
| Trimble GFX 750 | `AgDATA/Prescriptions/` | nada confirmado |
| Stara | `Dados/Mapas/` | a dose varia de acordo com arquivos shapefile importados por pen drive ou pela telemetria da marca (1) |
| Raven | `ePro/WorkOrders/rxMaps/` | shapefile de polígonos no datum WGS 84; `.shp`, `.shx` e `.dbf`; o menor número de zonas possível; menor zona não mais estreita que a barra (2) |
| John Deere | `Rx/` | os shapefiles têm de estar numa pasta chamada `Rx` na raiz do pen drive; dose zero desliga as seções quando o controle de seções está ligado (3) |
| New Holland (IntelliView IV e Pro 700) | `Shapefile/` | nada confirmado |
| Hexagon | raiz, sem pasta | importação por Arquivos › Importar do USB › Mapa de recomendação; no display escolhe-se o mapa e o atributo da dose (4) |
| Arvus | raiz, sem pasta | nada confirmado |
| Agres | raiz, sem pasta | nada confirmado |
| Jacto | raiz, sem pasta | nada confirmado |
| Verion | pasta com o nome do talhão ou do produto | formato próprio (`product1.bmp`, `product1.dat`, `product1.map`); sem documentação pública: a skill não gera |

## Fontes do fabricante

1. Stara, prospecto do Topper 5500: "A dosagem dos insumos pode ser variada
   conforme as zonas de manejo, de acordo com arquivos Shapefile importados
   via pen drive ou Telemetria Stara."
2. Raven, manual do console Viper Pro, seção "Prescription (Rx) Maps" (lida na
   reprodução do manual que acompanha semeadoras com esse console): os mapas
   têm de ser shapefile de polígonos, no datum WGS 84; devem ter o menor número
   de zonas possível; a menor zona não deve ser mais estreita que a largura da
   barra; os arquivos `.shp`, `.shx` e `.dbf` vão para a pasta `RxMaps` do pen
   drive. O manual é do Viper Pro e fala em `RxMaps`; a pasta
   `ePro/WorkOrders/rxMaps` é a do material de campo. Se o console não achar o
   mapa, confira o caminho no manual dele.
3. John Deere, ajuda na tela dos monitores G5 e Geração 4 (4640), telas
   "Gerenciador de Arquivos › Importar dados" e "Mapas de prescrição": "To
   import prescriptions, the shapefiles must be located in a folder named Rx
   on the root of the USB drive"; "Zero rates in the prescription command
   sections OFF in Section Control".
4. Hexagon Agriculture, Manual do usuário dos displays HxGN AgrOn Ti5 e Ti7,
   versão V3R009 (2020): importação de dados (seção 19.2) e taxa variável no
   controle de fertilização (seção 14.2.1.3), no atuador linear (capítulo 15)
   e no controle de pulverização (seção 16.2.1.3). No controle de fertilização
   há uma dose de fora do mapa, em kg/ha, a configurar no display; no atuador
   linear, "fora dos limites do mapa, nada é aplicado".

## O que foi procurado e não foi achado em documento de fabricante

- **Limite de polígonos, de vértices ou de tamanho do arquivo**, para qualquer
  uma das marcas. O material de campo diz que o shapefile não pode ser grande;
  nenhum número foi confirmado.
- **Unidade que cada controlador espera** e nome obrigatório da coluna de
  dose. Nos manuais lidos (Hexagon, John Deere), a coluna ou o atributo é
  escolhido no monitor.
- **Trimble CFX 750 e GFX 750, New Holland, Arvus, Agres e Jacto**: nenhum
  manual do fabricante com os requisitos do mapa foi achado na pesquisa. Há
  guias de terceiros e relatos em fórum na internet; não foram usados para
  afirmar nada aqui.
- **Verion**: nenhuma documentação do formato `product1.bmp`, `product1.dat`
  e `product1.map`.

Para tudo o que está como não confirmado, vale o manual do monitor e a
assistência da marca.
