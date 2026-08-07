# Krigagem de Solo

Skill que transforma **laudo de análise de solo + malha de amostragem** em
**mapas de fertilidade interpolados por krigagem ordinária** — um GeoTIFF
georreferenciado (pixel 5 m, SIRGAS 2000/UTM) e um PNG com legenda em régua
por elemento escolhido pelo usuário.

**O que ela faz:**

- **Casa os IDs** do shape de amostras com os do laudo mesmo com divergências
  reais de campo ("T01-03" ≈ "t1-3", "Ponto 12" ≈ "12"), em camadas de
  confiança decrescente — casos duvidosos vão para o usuário confirmar, e
  laudos com duas profundidades (0-20/20-40) são detectados e perguntados.
- **Testa três modelos de semivariograma** (exponencial, esférico, gaussiano)
  ajustados por mínimos quadrados ponderados e **escolhe o melhor por
  validação cruzada leave-one-out** (menor RMSE) — por elemento.
- **Interpola dentro do perímetro** (furos respeitados) e entrega o raster +
  o mapa pronto com régua de valores, escala gráfica, norte e os metadados da
  interpolação (modelo vencedor, RMSE, n, CRS) no subtítulo.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue (fluxo em duas etapas:
  casar → confirmar com o usuário → interpolar).
- `scripts/` — `interpolar.py` (pipeline CLI) · `casamento.py` (IDs fuzzy) ·
  `krigagem.py` (variograma, 3 modelos, LOO, krigagem ordinária) ·
  `geometria.py` (GeoJSON/KML/WKT/CSV + UTM + grade 5 m) · `shapefile_min.py`
  (leitor de .shp/.dbf sem GDAL) · `raster.py` (GeoTIFF em Python puro) ·
  `mapa.py` (PNG com régua). Todos com testes embutidos
  (`python scripts/<nome>.py`); `python scripts/interpolar.py --demo` roda um
  exemplo sintético completo, com IDs propositalmente "sujos".
- `references/krigagem.md` — decisões técnicas, fórmulas e limitações da v1.

## Instalar

Baixe [`krigagem-solo.zip`](../../../releases/latest/download/krigagem-solo.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Avisos

Krigagem não conserta malha ruim: com menos de 8 pontos o script recusa, e
entre 8 e 25 avisa que o variograma é frágil. As saídas são apoio técnico —
a decisão final é do engenheiro agrônomo responsável (ART). Divergências ou
melhorias? Abra uma [issue](../../../issues/new/choose).
