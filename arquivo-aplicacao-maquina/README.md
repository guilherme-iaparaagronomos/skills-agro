# Arquivo de aplicação para a máquina

Skill da comunidade agrônomo10X para levar, com a sua IA, o mapa de aplicação
em taxa variável até o monitor da máquina. Você entrega o mapa de polígonos
com a dose; ela confere o arquivo, corrige o que os monitores costumam
rejeitar e devolve um zip para extrair na raiz do pen drive, com o passo a
passo e o relatório do que mudou.

Atende Trimble CFX 750 e GFX 750, Stara, Raven, John Deere, New Holland
(IntelliView IV e Pro 700), Hexagon, Arvus, Agres e Jacto.

**A dose é sua.** A skill não calcula, não recomenda e não altera dose. Só
converte unidade, arredonda ao degrau da máquina ou aplica limite quando você
informa o valor, e mostra polígono a polígono o que mudou.

## O que ela confere e ajusta

- só `.shp`, `.shx` e `.dbf` no pen drive, com o mesmo nome curto, sem acento;
- coordenadas em graus, sem arquivo de projeção, sem Z nem M;
- dose em campo numérico;
- unidade coerente com o produto (sólido, líquido ou semente);
- pontos, linhas e polígonos sem área fora do arquivo;
- sobreposição entre polígonos e frestas;
- junção dos polígonos vizinhos de mesma dose, para deixar o arquivo leve,
  sem mudar a área nem o total de produto;
- a pasta que cada controlador espera.

## O que precisa

- Um ambiente que rode Python 3 com numpy.
- O mapa em shapefile (zip), GeoJSON, KML ou KMZ, com a dose num campo; ou as
  zonas (as da skill `zonas-de-manejo`, por exemplo) e a dose de cada zona.

## Estrutura

```
arquivo-aplicacao-maquina/
  SKILL.md                     o roteiro que a IA segue
  README.md
  references/
    regras.md                  as regras do arquivo e o que o script faz com cada uma
    controladores.md           a pasta de cada controlador e a fonte de cada informação
  scripts/
    aplicacao.py               entrada: --diagnostico, a geração e --demo
    regras.py                  dose, unidade, degrau, limites, nomes
    controladores.py           os dez controladores e o passo a passo
    pacote.py                  grava o shapefile e o zip e relê para conferir
    sintetico.py               talhão inventado para a demonstração
    shapefile.py, texto.py, kml_gpx.py, projecao.py, geom.py, uniao.py, conserto.py
                               leitura dos formatos, projeção, medida, união e conserto
                               (os mesmos módulos da skill conversor-geo)
```

Para ver funcionando com um talhão inventado:

```
python scripts/aplicacao.py --demo --saida saida-demo
```

Cada módulo roda sozinho como teste: `python scripts/regras.py`.

## Instalar

Baixe o zip pelo botão da página da skill, ou a pasta deste repositório, e
adicione como skill na sua IA (em Claude: Configurações › Capacidades ›
Skills; em outras IAs compatíveis, a pasta de skills do projeto).

## Como foi testada

- **Contra o GDAL/OGR, o GEOS e o PROJ do QGIS**: as entradas foram gravadas
  pelo OGR (shapefile em UTM com Z, em graus, sem `.prj`, com a dose em texto;
  GeoJSON; KML e KMZ) e cada arquivo gerado pela skill foi relido pelo OGR.
  Foram 96.548 conferências, sem falha: os três arquivos no caminho de cada um
  dos dez controladores, camada sem sistema de coordenadas, polígono sem Z nem
  M e válido para o GEOS, campos numéricos, dose de cada polígono, área e
  dose × área iguais às da entrada. A junção por dose foi comparada com a
  união do GEOS, dose a dose (mesmas partes e mesma forma, com furo).
- **Conversão, degrau e limites** refeitos à parte e comparados polígono a
  polígono; a diferença de total escrita no relatório bate com a conta à
  parte.
- **Casos ruins pela linha de comando**, cada um parando com o motivo: dose
  em texto que não é número, dose negativa, polígono sem dose, UTM sem fuso,
  campo que não existe, controlador ausente ou desconhecido, Verion, produto,
  unidade ou nome ausentes, unidade de outro produto, limite ultrapassado,
  polígonos sobrepostos com doses diferentes, arquivo só com pontos, zip com
  duas camadas, zona fora da tabela.
- **Arquivo grande**: 6.000 e 20.000 polígonos, com e sem junção (de 5 a 25
  segundos na máquina do teste). Acima de 2.500 polígonos a conferência de
  sobreposição não roda, e o relatório diz isso.
- **Com a saída de outra skill**: o `zonas.geojson` e o shapefile do exemplo
  da `zonas-de-manejo`, com a dose por zona.

**O que não foi feito**:

- **Nenhum arquivo foi carregado num monitor de verdade.** O formato foi
  conferido contra as regras e contra o GDAL; a leitura na máquina, não.
- O limite de polígonos de cada monitor não foi achado em manual de
  fabricante; a skill não afirma nenhum.
- A unidade esperada e o caminho do menu só foram confirmados em documento do
  fabricante para John Deere, Hexagon e, em parte, Raven e Stara. O resto está
  em `references/controladores.md` como não confirmado.
- Mapas de verdade de clientes: todos os testes usaram talhões inventados.
- A skill inteira dentro de uma conversa, em duas IAs diferentes.

## Avisos

- Confira no monitor a dose de dois ou três polígonos antes de aplicar.
- A unidade não está no arquivo: vale a que você informar, e é a que tem de
  estar configurada no monitor.
- Dose zero, em alguns monitores, desliga as seções.
- Verion usa formato próprio, sem documentação pública: a skill não gera.
- Polígonos sobrepostos e frestas são defeitos do mapa: quem corrige é quem
  fez a recomendação.

Autoria: Equipe agrônomo10X (OagronomIA).
