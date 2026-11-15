# Formatos, sistemas de coordenadas e limites

## O que cada formato guarda

| Formato | Geometrias | Atributos | Sistema | Na leitura | Na gravação |
|---|---|---|---|---|---|
| Shapefile | ponto, multiponto, linha, polígono | sim | o do `.prj` | zip ou `.shp` com os irmãos; `.dbf` em UTF-8, cp1252, latin-1 ou cp850; Z e M descartados | zip com `.shp`, `.shx`, `.dbf`, `.prj` e `.cpg` (UTF-8) |
| KML | ponto, linha, polígono, multi | sim | sempre graus | pastas em qualquer nível, MultiGeometry, furos, dados estendidos, trilha `gx:Track` | um marcador por feição, com o nome e todos os atributos |
| KMZ | os do KML | sim | sempre graus | todos os `.kml` do pacote | `doc.kml` compactado |
| GeoJSON | todas | sim, com o tipo (número, texto) | graus; metros se o arquivo declarar | coleção, feição ou geometria solta; GeometryCollection desmontada | padrão RFC 7946 |
| GPX | ponto, linha | nome e descrição | sempre graus | `wpt`, `rte` e `trk` | pontos em `wpt`; linhas em `trk` (ou `rte`) |
| CSV | ponto por colunas; qualquer uma em WKT | sim, como texto | o que as coordenadas forem | vírgula, ponto e vírgula ou tabulação; ponto ou vírgula decimal; graus-minutos-segundos | pontos com duas colunas; o resto com a coluna `wkt` |
| WKT | todas | não | o que as coordenadas forem | uma ou várias geometrias; Z e M descartados; prefixo `SRID=` | uma geometria por linha, ou um MULTIPOLYGON só |

## Sistemas de coordenadas

**Aceitos**
- Graus em SIRGAS 2000 (EPSG:4674) e em WGS 84 (EPSG:4326).
- UTM em SIRGAS 2000 e em WGS 84, qualquer fuso, norte ou sul. No Brasil: do
  fuso 18 ao 25 no sul (EPSG:31978 a 31985) e do 19 ao 22 no norte.

**Recusados, com a explicação**
- SAD 69, Córrego Alegre e SIRGAS 1995, em graus ou em UTM.
- Policônica do Brasil, Albers, Lambert, Mercator do Brasil, Web Mercator
  (EPSG:3857) e qualquer Mercator transversa cujos parâmetros não sejam os do
  UTM.

A recusa é de propósito: mudar de datum exige os parâmetros oficiais de
transformação e desloca as coordenadas em dezenas de metros. Isso se faz no
QGIS (Exportar > Salvar feições como, SRC EPSG:4674).

**De onde o script tira o sistema**, nesta ordem: o que o usuário informou
(`--src-entrada`); o `.prj` do shapefile; o membro `crs` do GeoJSON ou o
`SRID=` do WKT; a grandeza das coordenadas. Pela grandeza ele só reconhece
graus. Coordenada em metros sem fuso declarado **para a conversão**: o fuso
não se deduz.

**SIRGAS 2000 e WGS 84** são tratados como equivalentes. A diferença entre
os dois é de centímetros, abaixo do que um GPS de campo mede.

**A conta do UTM** usa as séries de Krüger. Comparada com a biblioteca PROJ
em 84 mil pontos, até 4,5 graus do meridiano central: diferença de até
0,00006 mm.

**Sinais que o script dá**
- centro do arquivo fora do Brasil, e dentro quando x e y são trocados:
  latitude e longitude invertidas;
- fuso informado que leva o arquivo para fora do Brasil: fuso ou hemisfério
  errados. Um fuso vizinho errado dentro do Brasil **não** é detectado: o
  arquivo cai 6 graus ao lado, ainda no país. Por isso o fuso se pergunta.

## Área

- **Plana em UTM** (a principal): os polígonos são projetados no UTM do fuso
  em que está o centro do arquivo e a área sai pela fórmula do polígono, com
  os furos descontados. É o método das outras skills da casa.
- **Sobre o elipsoide** (mostrada no `--listar`): a área que o QGIS mostra em
  `$area` e a que o CAR declara. Comparada com a área geodésica do PROJ,
  diferiu 0,005 ha num imóvel de 1.669,5 ha.
- A plana fica de **−0,08%** (no meio do fuso) a **+0,2%** (na borda do fuso,
  perto do Equador) da elipsoidal. Num imóvel de 1.669,5 ha a 1,4 grau do
  meio do fuso, a diferença foi de 0,5 ha.
- Arquivo que atravessa dois fusos é medido inteiro no fuso do centro.

## União de talhões

Cada polígono é uma volta de segmentos com o lado de dentro à esquerda. Onde
dois talhões dividem a divisa, o segmento aparece nos dois sentidos e se
anula. O que sobra é costurado de novo em anéis.

- **Exato** quando as divisas coincidem: os mesmos vértices, ou o vértice de
  um talhão em cima do lado do outro (divisa em T). A área da união é a soma
  das áreas.
- **Tolerância** (`--tolerancia`, padrão 0,05 m): pontos a menos disso um do
  outro contam como o mesmo. O script diz quantos vértices ajustou e em
  quanto.
- **Sobreposição não é resolvida.** Lados que se cruzam, um polígono dentro
  de outro ou dois iguais: o grupo sai junto, sem dissolver, com o nome das
  feições que se sobrepõem. A área somada conta o trecho duas vezes.
- **Fresta**: furo com menos de 1 m de largura média que sobrou entre divisas
  que não coincidem. É relatado, com a área. Fechar exige tolerância maior, e
  tolerância grande deforma detalhes pequenos.
- Só une polígonos. Os atributos do resultado são o campo da união (quando
  houver), o número de feições e a área em hectares.

## Conserto de geometria

| Defeito | O que o script faz |
|---|---|
| Coordenada vazia ou infinita | tira o vértice |
| Vértice repetido em seguida | tira |
| Anel aberto | fecha (sempre, mesmo sem `--consertar`) |
| Ida e volta (o contorno vai a um ponto e volta pelo mesmo caminho) | tira |
| Anel que se toca num vértice (o "8") | divide em anéis simples |
| Anel, polígono ou linha sem área ou sem comprimento | descarta |
| Sentido dos anéis | acerta para o que cada formato pede |
| Contorno que se cruza | **só relata**, com a coordenada |
| Furo traçado fora do polígono | **só relata** |

Os seis consertos seguros dão a mesma área que a correção do GEOS (a do
QGIS). O que não é consertado fica como está no arquivo de saída.

## Limites

- Shapefile: nome de campo com até 10 caracteres, sem acento (o script corta
  e numera os repetidos); texto com até 254 bytes; data sai como texto.
  MultiPatch não é lido.
- KML: estilos, ícones, imagens e links de rede não são levados. O nome do
  marcador vem do `--campo-nome`, ou do primeiro campo com cara de nome. Um
  campo chamado `id` também vai como identificador do marcador, que é de onde
  o QGIS lê o campo `id` de um KML.
- GPX: não tem polígono (vira trilha fechada, um trecho por anel) nem tabela
  de atributos (o nome vai em `name`, o resto em `desc`). Hora e altitude dos
  pontos de trilha não são guardadas.
- CSV: os atributos são lidos como texto. Linha sem coordenada legível fica
  de fora, e o script diz quais.
- WKT: sem atributos. Curvas (CIRCULARSTRING e afins) não são lidas.
- Zip e KMZ são lidos na memória, sem extrair para o disco; caminho com `..`
  é ignorado; arquivo de mais de 300 MB descompactado é recusado. XML com
  declaração de entidade não é aberto.
- Anel com mais de 200 mil vértices: o cruzamento do contorno não é
  conferido, e o relatório diz isso.
- Coordenadas saem com 8 casas em graus (cerca de 1 mm) e 3 em metros. Depois
  de várias conversões seguidas a posição pode variar meio milímetro.

## Como foi conferida

Contra o GDAL/OGR e o PROJ (as bibliotecas do QGIS), como leitores e
gravadores independentes:

- o UTM em 84 mil pontos, nos dois datums e nos dois hemisférios;
- o `.prj` de 42 sistemas, escrito pela skill e lido pelo GDAL, e o inverso em
  três dialetos; 15 sistemas que a skill não converte, recusados nos três;
- arquivos gravados pela skill e lidos pelo OGR nos sete formatos (feições,
  área, validade, atributos e sistema);
- arquivos gravados pelo OGR e lidos pela skill: shapefile em três
  codificações, sem `.cpg`, com Z, de pontos, de multiponto e de linhas;
  GeoJSON; KML e KMZ; GPX; CSV;
- a união contra a do GEOS em 40 conjuntos de talhões com divisas em T e 10
  com divisas a até 3 cm, e a sobreposição em 5 casos;
- o conserto contra a correção do GEOS, e 500 polígonos ao acaso para falso
  alarme e defeito não acusado.

Foram 2.240 conferências, sem diferença. Pela linha de comando: os 49 pares
de formatos, cadeias de até 7 conversões e 49 casos ruins.
