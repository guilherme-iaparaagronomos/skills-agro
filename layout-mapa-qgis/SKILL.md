---
name: layout-mapa-qgis
description: >-
  Monta no QGIS do usuário, pela ClaudIA QGIS, o layout final de um mapa num
  modelo profissional fixo, com a área de cada classe em hectares e em % na
  legenda, e exporta em PDF e PNG. O modelo tem moldura, faixa com a logo do
  cliente e os campos Fazenda e Proprietário, título, dados do mapa, escala,
  norte, data e mínimo, máximo e média; sai em A4 ou A3 e faz uma página por
  talhão com o atlas.
  Serve para mapa de fertilidade, produtividade, índice de vegetação, zonas de
  manejo ou qualquer camada em classes. Acione com "layout do mapa", "montar o
  mapa para impressão", "mapa para o cliente", "exportar o mapa em PDF",
  "legenda com hectares" ou quando houver uma camada no QGIS e o usuário pedir
  o mapa final.
---

# Layout de mapa no QGIS

Transforma uma camada do projeto aberto no QGIS em **mapa pronto para o
cliente**, sempre no mesmo modelo. O trabalho é feito no QGIS do usuário, pelo
conector **ClaudIA QGIS**; nada roda no chat.

## Para que serve
- Montar o layout de impressão sem o usuário arrastar caixa por caixa.
- Calcular a **área de cada classe em ha e em %** e escrever na legenda.
- Padronizar: todo mapa do escritório sai com a mesma cara.
- Exportar PDF e PNG, e uma página por talhão quando ele pedir.

## Para que NÃO serve
- Não cria o dado: a camada (raster interpolado, zonas, índice) já tem de
  estar no projeto. Para gerar o raster, use `interpolacao-idw` ou
  `interpolacao-krigagem`.
- Não escolhe os limites das classes. Se a camada não estiver classificada,
  PERGUNTE os limites ao usuário.
- Não inventa logo. A logo é a **do cliente**: peça o arquivo; se ele não
  tiver, o mapa sai sem logo. Nunca use logo de outra empresa.

## O que precisa estar pronto
- Conector **ClaudIA QGIS** ligado na IA e o QGIS do usuário aberto com o
  plugin conectado. Comece por `ping`. Sem resposta, avise e pare.
- O projeto com a camada do mapa e, de preferência, a camada dos talhões.

## Fluxo de trabalho (siga nesta ordem)

1. **Veja o projeto**: `ping`, `get_project_info` e `get_layers`. Diga ao
   usuário quais camadas você achou e confirme qual é a do mapa e qual é a dos
   talhões (o perímetro). Guarde os `id` das duas.
2. **Defina a pasta de trabalho.** Se o projeto tem arquivo salvo, é a pasta
   dele. Se não tem (`get_project_info` sem nome de arquivo), PERGUNTE ao
   usuário em que pasta gravar; não escolha por ele. É nessa pasta que ficam o
   módulo (subpasta `layout_agro/`) e os arquivos exportados.
3. **Pergunte o que vai escrito no mapa** (o que ele não disser, fica vazio):
   título; fazenda; proprietário; safra; atributo; profundidade ou outra
   informação; unidade das classes; A4 ou A3; e a logo (caminho do arquivo na
   máquina dele, PNG, JPG ou SVG). O **nome do layout** você mesmo monta com o
   atributo e a profundidade (ex.: `Argila 0-20`) e diz a ele qual é.
4. **Avise e instale o módulo.** Diga ao usuário, numa frase, o que vai
   fazer: gravar o arquivo `layout_agro.py` na pasta de trabalho e carregá-lo
   no QGIS, sem alterar nenhuma camada. Com o ok dele, mande o **Bloco A** por
   `execute_code`. Uma vez por conversa basta.
5. **Confira a camada** com o **Bloco C**. Ele diz se a camada já está em
   classes e lista os campos da camada dos talhões. Raster em cor contínua ou
   vetor de símbolo único não tem legenda de classes: pergunte os limites e
   use o **Bloco D**. Avise antes: isso troca o estilo da camada dele.
6. **Monte o layout** com o **Bloco E**. O resultado traz as classes com ha e
   %, a área total, o mínimo, o máximo, a média e a escala. **Mostre esses
   números ao usuário** e pergunte se batem com o que ele espera.
7. **Exporte para ele ver**: tool `export_layout` com `layout_name`, `path`
   (um arquivo dentro da pasta de trabalho), `format` (`png` ou `pdf`) e
   `dpi: 150`. Diga o caminho. Você não enxerga o arquivo: peça que ele abra e
   diga se algo ficou cortado, sobreposto ou escondido.
8. **Ajuste o que ele pedir** e rode o Bloco E de novo, com TODOS os
   argumentos (o layout de mesmo nome é refeito do zero). Para um retoque
   fora do modelo, use `add_layout_label` e `add_layout_picture` sobre o
   layout já montado.
9. **Uma página por talhão** (se ele pedir): confirme com ele qual campo da
   camada dos talhões tem o nome (o Bloco C listou os campos com exemplos).
   Rode o Bloco E com o acréscimo do atlas e com **outro nome de layout**
   (o mesmo nome + ` por talhão`), para o layout do mapa inteiro continuar
   existindo. Depois, a tool `export_atlas` (`layout_name`, `output_path`,
   `format: "pdf"`, `dpi: 150`). Cada página traz o nome e a área do talhão,
   que aparece com o contorno grosso; os vizinhos ficam em cinza. Avise que a
   legenda continua com as áreas do mapa inteiro. Não exporte o layout do
   atlas pelo `export_layout`: fora do atlas, o nome e a área do talhão saem
   em branco.
10. **Vários atributos**: repita os passos 5 a 7 para cada camada, um layout
    por atributo, mudando o nome do layout, `Atributo` e a unidade.

## Os blocos de código

Mande cada bloco como está, começando na primeira coluna. Troque só o que
está entre `<< >>`. Em `<<pasta que o usuário indicou>>` vai a pasta do
passo 2; com o projeto salvo essa pasta não é usada, e o marcador pode ficar
como está.

### Bloco A — instalar o módulo (uma vez por conversa)

O conteúdo de `scripts/layout_agro.py` vai INTEIRO dentro de `CODIGO`, sem
alteração. O bloco confere se o arquivo chegou completo e fiel.

```python
import hashlib, os, sys
from qgis.core import QgsProject
BASE = QgsProject.instance().homePath() or r'<<pasta que o usuário indicou>>'
CODIGO = r'''
<<conteúdo de scripts/layout_agro.py>>
'''
compile(CODIGO, 'layout_agro.py', 'exec')
pasta = os.path.join(BASE, 'layout_agro')
os.makedirs(pasta, exist_ok=True)
with open(os.path.join(pasta, 'layout_agro.py'), 'w', encoding='utf-8') as f:
    f.write(CODIGO.lstrip())
if pasta not in sys.path:
    sys.path.insert(0, pasta)
sys.modules.pop('layout_agro', None)
import layout_agro as la
assert getattr(la, 'FIM_DO_ARQUIVO', False), 'o arquivo chegou cortado: mande o bloco de novo'
fiel = hashlib.md5(''.join(CODIGO.split()).encode('utf-8')).hexdigest()[:12] == 'ffdbcb413df1'
print('layout_agro pronto em', pasta, '|', 'cópia fiel' if fiel else 'CÓPIA DIFERENTE do original')
```

- Se o `assert` ou o `compile` falhar, o código foi cortado: mande o bloco de
  novo, com o arquivo inteiro, sem resumir nem pular função.
- Se imprimir `CÓPIA DIFERENTE`, algum trecho foi alterado na cópia: mande o
  bloco de novo, com o arquivo exatamente como está. Se repetir, siga em
  frente e avise o usuário de que o módulo pode ter diferença do original.

### Bloco B — cabeçalho de toda chamada seguinte

Cada `execute_code` é uma execução nova: comece os blocos C, D e E com isto.

```python
import os, sys
from qgis.core import QgsProject
BASE = QgsProject.instance().homePath() or r'<<pasta que o usuário indicou>>'
pasta = os.path.join(BASE, 'layout_agro')
if pasta not in sys.path:
    sys.path.insert(0, pasta)
import layout_agro as la
p = QgsProject.instance()
```

### Bloco C — conferir as classes e os campos dos talhões (depois do Bloco B)

```python
camada = p.mapLayer('<<id da camada do mapa>>')
try:
    print('EM CLASSES:', [c['rotulo'] for c in la.areas_por_classe(camada)[0]])
except ValueError as erro:
    print('SEM CLASSES:', erro)
talhoes = p.mapLayer('<<id dos talhões>>')
amostra = [f for _, f in zip(range(3), talhoes.getFeatures())]
print('CAMPOS DOS TALHÕES:', {c.name(): [str(f[c.name()]) for f in amostra] for c in talhoes.fields()})
```

Sem camada de talhões, apague as três últimas linhas.

### Bloco D — pôr o raster em classes (depois do Bloco B)

```python
camada = p.mapLayer('<<id da camada do mapa>>')
print(la.classificar_raster(camada, [<<limites, ex.: 150, 250, 350, 450>>]))
```

`invertida=True` para variável em que mais é pior (alumínio, saturação por
Al). Em vetor, o usuário categoriza ou gradua no QGIS, ou você usa
`set_layer_style`.

### Bloco E — montar o layout (depois do Bloco B)

```python
resumo = la.montar_layout(
    '<<nome do layout, ex.: Argila 0-20>>', p.mapLayer('<<id da camada do mapa>>'),
    titulo='<<título>>', fazenda='<<fazenda>>', proprietario='<<proprietário>>',
    campos=[('Safra', '<<safra>>'), ('Atributo', '<<atributo>>'), ('Profundidade', '<<profundidade>>')],
    perimetro=p.mapLayer('<<id dos talhões>>'), unidade='<<unidade>>', logo=None, pagina='A4')
print(resumo)
```

Para o atlas, troque o nome do layout (ex.: `Argila 0-20 por talhão`) e
acrescente antes do parêntese final:
`atlas_camada=p.mapLayer('<<id dos talhões>>'), atlas_campo='<<campo com o nome do talhão>>'`.
O `resumo` passa a trazer `atlas_paginas`.

## Opções do `montar_layout`

| Parâmetro | O que faz | Padrão |
|---|---|---|
| `titulo` | texto do quadro de cima, à direita | `'Mapa'` |
| `fazenda`, `proprietario` | faixa de cima | vazio |
| `campos` | lista de pares (rótulo, valor) na coluna da direita | nenhum |
| `perimetro` | camada dos talhões: enquadra o mapa e é desenhada por cima, só o contorno | a própria camada |
| `contorno_perimetro` | `False` desenha os talhões com o estilo que a camada já tem | `True` |
| `logo` | caminho da imagem da logo do cliente | sem logo |
| `unidade` | aparece ao lado de "CLASSE" | vazio |
| `pagina` | `'A4'` ou `'A3'` (deitada) | `'A4'` |
| `grade` | coordenadas na borda do mapa | `False` |
| `casas` | casas decimais das áreas e das estatísticas | `2` |
| `ocultar_vazias` | tira da legenda a classe com 0 ha | `False` |
| `camadas_extra` | outras camadas a desenhar (pontos de amostra, por exemplo) | nenhuma |
| `atlas_camada`, `atlas_campo` | uma página por feição, com o nome lido do campo | sem atlas |
| `atlas_rotulo` | como chamar a feição na página | `'Talhão'` |

## Detalhes fixos

- **O módulo não altera as camadas do usuário.** Os talhões saem só com o
  contorno no mapa do layout, mesmo que na tela estejam preenchidos, e o
  estilo deles no projeto fica como estava. A única troca de estilo é a do
  `classificar_raster`, que você avisa antes.
- **O layout guarda o estilo do momento em que foi montado.** Se o usuário
  reclassificar a camada depois, monte de novo: a legenda é texto fixo.
- **Áreas**: no raster, número de pixels de cada classe × área do pixel. No
  vetor, a área elipsoidal dos polígonos de cada classe. A área total é a
  soma das classes; diga isso se ela diferir da área que o usuário conhece
  (pixel de borda e áreas sem dado explicam a diferença).
- **Projeção do mapa**: se a camada estiver em graus, o mapa do layout é posto
  na zona UTM SIRGAS 2000 do local, para a escala sair em metros.
- **Escala**: o passo é sempre um número redondo que cabe na coluna; no atlas
  ele é recalculado em cada página.
- **Mínimo, máximo e média** são do raster inteiro (ou do campo do vetor
  graduado), não das amostras.
- Raster acima de 30 milhões de pixels é lido reduzido para a contagem; a
  diferença nas áreas fica abaixo de 1 %.
- Cada `execute_code` precisa terminar em menos de 55 s. Exporte pelas tools
  `export_layout` e `export_atlas`, que não têm esse limite.
- No fim, diga ao usuário que a subpasta `layout_agro/` pode ser apagada: ela
  só guarda o módulo.
- O modelo, medida por medida, e as regras de um mapa bem apresentado:
  `references/modelo.md`.
