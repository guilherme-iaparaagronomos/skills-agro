# Layout de mapa no QGIS

Skill que monta, **no QGIS do usuário**, o layout final de um mapa num modelo
profissional fixo, pela **ClaudIA QGIS**: moldura, faixa com a logo do cliente
e os campos Fazenda e Proprietário, título, dados do mapa, **legenda com a
área de cada classe em hectares e em %**, escala, norte, data e mínimo, máximo
e média.

**O que ela faz:**

- Lê o projeto aberto, confirma com o usuário a camada do mapa e a dos talhões
  e pergunta o que vai escrito (título, fazenda, proprietário, safra…).
- Classifica o raster pelos limites que o usuário der, quando ele ainda está
  em cor contínua.
- Calcula as áreas por classe e monta o layout em A4 ou A3.
- Exporta em PDF e PNG e, com o atlas, uma página por talhão, com o nome, a
  área e o contorno do talhão em destaque.
- Não altera o estilo das camadas do usuário: os talhões saem só com o
  contorno no mapa do layout.

Serve para mapa de fertilidade, produtividade, índice de vegetação, zonas de
manejo ou qualquer camada em classes.

## O que precisa

O conector **ClaudIA QGIS** da comunidade agrônomo10X ligado na sua IA e o
QGIS aberto com o plugin conectado.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue.
- `scripts/layout_agro.py` — o módulo PyQGIS que a IA envia ao QGIS: classes,
  áreas, montagem do layout, exportação e atlas.
- `references/modelo.md` — o modelo com as medidas, as regras de um mapa bem
  apresentado e como as áreas são calculadas.

## Instalar

Baixe [`layout-mapa-qgis.zip`](../../../releases/latest/download/layout-mapa-qgis.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Avisos

A logo do mapa é a do cliente: a skill pede o arquivo e, sem ele, o mapa sai
sem logo. As saídas são apoio técnico — a conferência dos números é do
engenheiro agrônomo responsável. Divergências ou melhorias? Abra uma
[issue](../../../issues/new/choose).
