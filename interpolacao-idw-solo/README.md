# Interpolação IDW de Solo

Skill que transforma **laudo de análise de solo + malha de amostragem** em
**mapas de fertilidade por IDW, em classes**, com a área de cada classe em
hectares e em %, e monta a **apostila em PDF** (capa, resumo e um mapa por
página).

**O que ela faz:**

- **Casa os IDs** do shape de amostras com os do laudo mesmo com divergências
  reais de campo ("T01-03" ≈ "t1-3", "Ponto 12" ≈ "12"); casos duvidosos vão
  para o usuário confirmar, e laudos com mais de uma profundidade são
  detectados e perguntados.
- **Interpola por IDW** (potência 2 por padrão), mede o erro por **validação
  cruzada leave-one-out** e informa quanto o mapa prevê melhor que a média do
  talhão — quando não prevê, o mapa diz isso.
- **Classifica** cada elemento pela **5ª Aproximação (MG)**, pelo **Boletim
  100 (SP)**, por limites do usuário ou em classes livres. Só aplica classe
  oficial quando a unidade e o método do laudo batem com a tabela; unidades
  equivalentes são convertidas. O P de MG é classificado pixel a pixel, com o
  limite da argila (ou do P-rem) daquele pixel.
- **Entrega** por elemento o GeoTIFF (SIRGAS 2000/UTM), o PDF e o PNG da
  página, e no fim a apostila, o CSV das áreas por classe e o relatório.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue (conferir o casamento e
  as classes com o usuário → interpolar → entregar).
- `scripts/` — `interpolar.py` (pipeline CLI) · `idw.py` (IDW, validação
  cruzada, teste contra a média) · `classes.py` (tabelas de MG e SP, unidades,
  classes livres) · `mapa.py` (página do mapa, capa e resumo) · `casamento.py`
  (IDs fuzzy) · `geometria.py` (GeoJSON/KML/WKT/CSV + UTM + grade) ·
  `shapefile_min.py` (leitor de .shp/.dbf sem GDAL) · `raster.py` (GeoTIFF em
  Python puro). Todos com testes embutidos (`python scripts/<nome>.py`);
  `python scripts/interpolar.py --demo` roda um exemplo sintético completo.
  Dependências: numpy, scipy e matplotlib.
- `references/idw.md` — fórmulas, escolha da potência e limitações.
- `references/classes.md` — as tabelas de classes, com a fonte de cada quadro,
  e as regras de unidade e de método.

## Instalar

Baixe [`interpolacao-idw-solo.zip`](../../../releases/latest/download/interpolacao-idw-solo.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Avisos

IDW não conserta malha ruim: com menos de 5 pontos o script recusa, e abaixo
de 15 avisa que o mapa é um esboço. As classes seguem os boletins oficiais,
que têm a palavra final. As saídas são apoio técnico — a interpretação e a
recomendação são do engenheiro agrônomo responsável (ART). Divergências ou
melhorias? Abra uma [issue](../../../issues/new/choose).

Quer geoestatística (semivariograma, dependência espacial)? Use a skill
[`krigagem-solo`](../krigagem-solo/).
