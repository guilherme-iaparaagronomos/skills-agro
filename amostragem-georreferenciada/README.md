# Amostragem Georreferenciada

Skill que transforma o **perímetro dos talhões** num **plano de coleta**: os
pontos numerados, a ordem de caminhada, a planilha de campo, o mapa e os
arquivos para o GPS. Serve para solo, nematoides, pragas, plantas daninhas ou
qualquer coleta feita em pontos.

**O que ela faz:**

- **Três desenhos**: grade regular (quadrada ou triangular, com giro), células
  com amostra composta e amostras compostas por zona de manejo ou por talhão.
- **IDs com o nome do talhão** (`T01-03`), no formato que as skills
  [`interpolacao-idw`](../interpolacao-idw/) e
  [`interpolacao-krigagem`](../interpolacao-krigagem/) casam com o laudo.
- **Rota de coleta** em serpentina ou por caminho curto, com a distância.
- **Arquivos prontos**: KML, GPX (pontos e rota), shapefile de pontos, GeoJSON,
  CSV, planilha de campo por camada e o mapa em PDF e PNG.

A densidade, o modo, as subamostras e as camadas são decisão do responsável
técnico: a skill pergunta e desenha o que ele definir.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue (conferir os nomes dos
  talhões → perguntar os parâmetros → desenhar → entregar).
- `scripts/` — `amostragem.py` (pipeline CLI) · `desenho.py` (grade, células,
  compostas e rota) · `areas.py` (leitura dos talhões com nome, projeção e
  geometria) · `saidas.py` (arquivos e mapa) · `geometria.py` e
  `shapefile_min.py` (leitura de KML, GeoJSON, shapefile e WKT). Todos com
  testes embutidos (`python scripts/<nome>.py`); `python scripts/amostragem.py
  --demo` roda os três modos numa fazenda de exemplo. Dependências: numpy e
  matplotlib.
- `references/amostragem.md` — como cada desenho é calculado, as referências
  de densidade e os limites.

## Instalar

Baixe [`amostragem-georreferenciada.zip`](../../../releases/latest/download/amostragem-georreferenciada.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Avisos

O plano não considera carreadores, cercas nem cursos d'água, e a distância de
caminhada é em linha reta entre os pontos. As saídas são apoio técnico — a
decisão é do engenheiro agrônomo responsável (ART). Divergências ou melhorias?
Abra uma [issue](../../../issues/new/choose).
