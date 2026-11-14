# Zonas de manejo

Skill que divide o talhão em **zonas de manejo** a partir das camadas que o
usuário tiver: argila, matéria orgânica, produtividade de várias safras,
altitude, índice de vegetação, condutividade elétrica. Entram pontos com as
camadas em colunas, rasters GeoTIFF, ou os dois juntos.

**O que ela faz:**

- **Diagnóstico** antes de gerar qualquer zona: as camadas disponíveis, as que
  se repetem e, para cada número de zonas, a silhueta, quantas sobram depois
  do refino e quanto explicam.
- **Agrupamento** por componentes principais e K-Means, com o número de zonas
  que o usuário confirmar.
- **Refino**: classe pequena absorvida pelas vizinhas, pedaço solto
  reatribuído e parte abaixo da área mínima fundida à vizinha de maior divisa.
- **Polígonos** com as divisas suavizadas (a mesma linha para as duas zonas
  vizinhas) e a borda de fora no perímetro do talhão.
- **Tabela por zona** com a média de cada camada, e quanto as zonas explicam
  de cada uma.

Ela não recomenda manejo e não dá nota às zonas: mostra o agrupamento.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue.
- `scripts/zonas.py` — a linha de comando (diagnóstico, zonas e exemplo).
- `scripts/zoneamento.py` — a sequência do método e os avisos.
- `scripts/agrupamento.py` — padronização, componentes principais, K-Means,
  silhueta e o refino nos pontos.
- `scripts/grade.py` — a grade fina e a fusão das partes pequenas.
- `scripts/vetor.py` — da grade aos polígonos, com divisas compartilhadas e a
  borda no perímetro.
- `scripts/geotiff.py` — leitura e escrita de GeoTIFF em Python puro.
- `scripts/saidas.py` — GeoJSON, KML, shapefile, tabelas e o relatório em PDF.
- `scripts/sintetico.py` — o talhão inventado com zonas plantadas, usado no
  exemplo e nos testes.
- `scripts/leitura.py`, `areas.py`, `geometria.py`, `shapefile_min.py` —
  leitura de pontos e do perímetro, iguais aos das outras skills da casa.
- `references/metodo.md` — cada etapa, os padrões, os limites e as fontes.

Cada script tem um teste embutido: `python scripts/<nome>.py`. O exemplo
completo: `python scripts/zonas.py --demo`.

## Instalar

Baixe [`zonas-de-manejo.zip`](../../../releases/latest/download/zonas-de-manejo.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Avisos

A skill foi medida num talhão inventado, com zonas plantadas, e rodada numa
fazenda real. As zonas são um agrupamento estatístico das camadas informadas;
o que fazer em cada uma é decisão do responsável técnico. Achou um arquivo que
ela lê mal? Abra uma [issue](../../../issues/new/choose).
