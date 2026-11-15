# Conversor de arquivos geográficos

Skill que passa **perímetros, talhões, pontos e linhas** de um formato para
outro, sem perder os atributos, e conta o que mudou no caminho.

**O que ela faz:**

- **Sete formatos**, de qualquer um para qualquer outro: Shapefile, KML, KMZ,
  GeoJSON, GPX, CSV e WKT.
- **Inspeção antes de converter**: tipo de geometria, campos com exemplos,
  sistema de coordenadas e de onde ele veio, área em hectares e defeitos.
- **Reprojeção** entre graus (SIRGAS 2000 e WGS 84) e UTM. SAD 69, Córrego
  Alegre e outras projeções são recusados com a explicação, em vez de sair
  convertidos errado.
- **União de talhões** num perímetro só, ou por um campo, sumindo com a
  divisa interna. Sobreposição é detectada e avisada.
- **Conserto de geometria**: aplica só o que é seguro e relata o resto.
- **Conferência**: relê o arquivo gravado e compara feições e área.
- **Pronto para a ClaudIA Sat**: GeoJSON em graus, com os atributos.

O fuso UTM, as colunas de um CSV e a troca de latitude por longitude não são
decididos pela skill: quando o arquivo não diz, ela para e pergunta.

## O que precisa

Python com numpy, no ambiente de código da sua IA. Não usa internet nem
conector.

## Estrutura

- [`SKILL.md`](SKILL.md) — o roteiro que a IA segue (inspecionar → perguntar
  o que for ambíguo → converter → conferir → entregar).
- `scripts/` — `converter.py` (linha de comando) · `projecao.py` (UTM e
  sistemas de coordenadas) · `geom.py` (área, anéis, medidas) ·
  `shapefile.py` · `kml_gpx.py` · `texto.py` (GeoJSON, CSV e WKT) ·
  `uniao.py` · `conserto.py` · `sintetico.py` (fazenda inventada). Todos com
  testes embutidos (`python scripts/<nome>.py`); `python scripts/converter.py
  --demo --saida demo` roda dez passos numa fazenda de exemplo.
- `references/formatos.md` — o que cada formato guarda, os sistemas aceitos e
  recusados, como a área, a união e o conserto são feitos, e os limites.

## Instalar

Baixe [`conversor-geo.zip`](../../../releases/latest/download/conversor-geo.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Como foi testada

Contra o GDAL/OGR e o PROJ, as bibliotecas do QGIS, usados como leitores e
gravadores independentes: 2.240 conferências, sem diferença. O UTM bate com o
PROJ em 0,00006 mm; os arquivos gravados pela skill abrem no OGR com as mesmas
feições, áreas e atributos, e os gravados pelo OGR são lidos igual; a união e
o conserto dão o mesmo resultado que o GEOS. Pela linha de comando, os 49
pares de formatos e 49 casos ruins (shapefile sem `.prj`, CSV com vírgula
decimal, coordenadas trocadas, fuso errado, anel aberto, arquivo vazio).
Com arquivos reais: o perímetro e os temas de um imóvel do CAR e as zonas de
uma fazenda de 5 mil hectares. A skill ainda não foi rodada dentro de uma
conversa com a IA.

## Avisos

A área é a do desenho que o arquivo traz: não é levantamento nem certidão. A
área plana em UTM difere da medida sobre o elipsoide (a do QGIS e do CAR) em
até 0,2%; a skill mostra as duas. As saídas são apoio técnico, e a conferência
final é do responsável técnico. Divergências ou melhorias? Abra uma
[issue](../../../issues/new/choose).
