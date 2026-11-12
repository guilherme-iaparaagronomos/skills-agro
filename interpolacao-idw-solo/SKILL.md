---
name: interpolacao-idw-solo
description: >-
  Mapas de fertilidade do solo por IDW, em classes, com a área de cada classe
  em hectares e em % e uma apostila em PDF. Entradas: perímetro do talhão ou
  da fazenda, pontos de amostragem (shapefile/GeoJSON/KML/CSV) e o laudo do
  laboratório. Casa os IDs do shape com os do laudo mesmo com divergências
  (T01-03 ≈ t1-3), escolhe a potência do IDW por validação cruzada, classifica
  cada elemento pela tabela oficial (5ª Aproximação de MG ou Boletim 100 de
  SP) ou por limites do usuário e entrega GeoTIFF, PDF e PNG por elemento mais
  a apostila com capa e resumo. Acione com "mapa de fertilidade", "IDW",
  "interpolar análise de solo", "apostila de mapas de solo", "mapa de argila,
  P, K ou V%" ou quando o usuário trouxer laudo + pontos de amostragem.
---

# Interpolação IDW de Solo — do laudo à apostila de mapas

Transforma laudo de análise de solo + malha de amostragem em **mapas de
fertilidade interpolados por IDW e classificados**, um por elemento: a página
traz o mapa em classes, a legenda com **hectares e % de cada classe**, as
estatísticas e a fonte da tabela. No fim, uma **apostila em PDF** com capa,
resumo e um mapa por página.

## Para que serve
- Casar os IDs do **shape de amostras** com os do **laudo** mesmo quando
  divergem ("T01-03" vs "t1-3", "Ponto 12" vs "12") e apontar o que não casou.
- Interpolar por **IDW** (inverso da distância) com a **potência escolhida por
  validação cruzada** — e dizer quanto o mapa prevê melhor que a média do talhão.
- **Classificar** cada elemento pela **5ª Aproximação (MG)**, pelo **Boletim
  100 (SP)**, por limites do usuário ou, sem tabela, em classes livres.
- Entregar o mapa pronto para o cliente: PDF e PNG por elemento, GeoTIFF para
  o QGIS e a apostila.

## Para que NÃO serve
- Não é geoestatística. Se o usuário pedir **krigagem**, semivariograma ou
  análise de dependência espacial, use a skill `krigagem-solo`.
- Não conserta malha rala: com menos de 5 pontos o script se recusa; abaixo
  de 15 avisa que o mapa é só um esboço.
- Não recomenda adubo nem corretivo. Para recomendar, use `5a-aproximacao-mg`
  ou `boletim-100-sp` sobre os mapas. A decisão é do responsável técnico.
- Não separa a tabela de áreas por talhão (v1 trata o perímetro como um todo;
  os limites internos aparecem desenhados no mapa).

## Entradas

1. **Perímetro**: `.kml`, `.geojson`, `.shp` (polígono) ou WKT. Vários
   talhões no mesmo arquivo viram um mapa só.
2. **Pontos de amostragem**: `.shp` (leitor embutido, sem GDAL), `.geojson`,
   `.kml` ou `.csv` com lon/lat. `.zip`/`.kmz`: descompacte antes.
3. **Laudo**: qualquer formato (PDF, foto, planilha). VOCÊ extrai a tabela
   para um CSV com **uma linha por amostra**: primeira coluna = ID da amostra
   como está no laudo; demais colunas = elementos, **com a unidade no
   cabeçalho, entre parênteses, exatamente como o laudo traz** — `K (mg/dm3)`,
   `Ca (cmolc/dm3)`, `Argila (g/kg)`, `V (%)`. Diga também o método quando o
   laudo disser: `pH CaCl2`, `pH H2O`, `P resina (mg/dm3)`, `P Mehlich (mg/dm3)`.

**A unidade é o que protege o mapa.** K em mg/dm³ classificado com limites de
mmolc/dm³ dá um mapa bonito e errado. Sem unidade no cabeçalho, o script não
aplica classe oficial. Nunca escreva uma unidade que o laudo não traz: se
faltar, PERGUNTE ao usuário. Não invente valores; decimais com vírgula e
"<0,1" podem ficar como estão (o script trata; "<LD" entra como metade).

Coordenadas em metros (UTM) sem `.prj` exigem a zona: `--zona 22S`.

## Fluxo de trabalho (siga nesta ordem)

1. **Extraia o laudo** para `laudo.csv` (regra acima) e liste as colunas
   numéricas encontradas.
2. **Pergunte ao usuário** — nunca decida por ele:
   - quais elementos quer mapear;
   - qual tabela de classes: **MG** (5ª Aproximação), **SP** (Boletim 100),
     limites dele ou nenhuma. A tabela é a do manual que ele usa para
     recomendar, que nem sempre é o do estado onde fica a fazenda;
   - para o P pelo Boletim 100: o grupo de culturas (`florestais`, `perenes`,
     `anuais` ou `hortalicas`);
   - o que vai na capa: fazenda, cliente, responsável técnico, camada
     (ex.: "0–20 cm") e, se quiser, a logo (PNG ou JPG).
3. **Etapa 1 — conferência** (sempre primeiro):
   `python scripts/interpolar.py --perimetro talhao.kml --pontos amostras.shp
   --laudo laudo.csv --tabela mg --so-casamento --saida ./saida`
   O JSON traz o casamento dos IDs e, em `classes_propostas`, como cada coluna
   será classificada (quadro, limites na unidade do laudo, avisos).
4. **Revise o casamento — VOCÊ é a camada final.**
   - `duplicados_laudo` preenchido = mais de uma linha por ponto
     (profundidades). Pergunte qual usar e repita com `--filtro-laudo "0-20"`.
   - `aproximados_para_confirmar` = mostre a tabela ponto ↔ laudo e confirme.
   - `pontos_sem_par` = use `sugestoes_para_os_sem_par` e o seu entendimento
     para PROPOR o par ao usuário. Nunca decida sozinho um par ambíguo: um
     casamento errado põe o valor na coordenada errada.
   - Pares confirmados entram com `--par "PONTO=ID DO LAUDO"` (repetível).
   - Detecção de campo errada corrige-se com `--id-pontos`/`--id-laudo`.
5. **Revise as classes propostas com o usuário**, coluna por coluna:
   - mostre o quadro e os limites que serão usados;
   - coluna que caiu em "classes livres" tem o motivo em `avisos` (unidade
     ausente, extrator diferente, item sem classe na tabela). Resolva com ele:
     corrigir o cabeçalho, forçar o item (`--classe "pH=ph"`) ou dar limites;
   - **P pela 5ª Aproximação** depende da argila ou do P-rem. Com a coluna no
     laudo, o script interpola a argila (ou o P-rem) e classifica **cada pixel
     com o limite da sua faixa**. Sem a coluna, peça um valor único
     (`--argila-fixa 45`, em %; `--prem-fixo 20`, em mg/L);
   - micronutrientes pressupõem o extrator da tabela (Mehlich-1 em MG, DTPA em
     SP; B em água quente). Confirme com o usuário se o laudo usa o mesmo.
6. **Etapa 2 — interpolação**:
   `python scripts/interpolar.py ... --tabela mg --elementos "K (mg/dm3),V (%)"
   --fazenda "Fazenda Exemplo" --camada "0–20 cm" --saida ./saida`
   (nomes exatamente como no cabeçalho do CSV; `todos` = todas as numéricas).
7. **Entregue**: a `apostila.pdf` e, por elemento, o PNG (mostre no chat), o
   PDF e o GeoTIFF. Diga a potência usada, o RMSE da validação cruzada e o
   ganho sobre a média, e repasse TODOS os avisos do relatório.
8. **Honestidade**: se vier o aviso de que o IDW não previu melhor que a média
   do talhão, diga claramente que a malha não captou padrão espacial e que o
   mapa pouco difere da média. Não venda um mapa pobre como bom.

## Classes: as quatro formas

| Forma | Como pedir | O que acontece |
|---|---|---|
| 5ª Aproximação (MG) | `--tabela mg` | pH em água, MO, Ca, Mg, Al, SB, H+Al, t, T, m, V, K, P (por argila ou P-rem), S (por P-rem), Zn, Mn, Fe, Cu, B e textura |
| Boletim 100 (SP) | `--tabela sp` | pH em CaCl₂, V, K, P resina (por grupo de cultura), Ca, Mg, S, B, Cu, Fe, Mn, Zn |
| Limites do usuário | `--limites "CE (mS/m)=10,20,30"` e, se quiser, `--nomes "CE (mS/m)=Baixa\|Média\|Alta\|Muito alta"` | valem os limites dele, na unidade da coluna |
| Sem tabela | (padrão para o que não tem classe) | 5 intervalos iguais "redondos"; `--classes-livres quantis` troca por quantis |

- Unidade diferente da tabela mas conversível (cmolc ↔ mmolc; K em mg/dm³ ↔
  mmolc/dm³; % ↔ g/kg) é convertida, e o aviso diz o fator. O mapa continua na
  unidade do laudo.
- Cores: verde é bom. Para Al, m% e H+Al a escala inverte sozinha. Em coluna
  com limites do usuário, `--sentido "Coluna=alto_ruim"` inverte.
- Para forçar ou desligar a classe de uma coluna: `--classe "Coluna=k"` ou
  `--classe "Coluna=nenhuma"`.
- Tabelas, quadros e regras de conversão: `references/classes.md`.

## IDW ou krigagem?

- **IDW** (esta skill): simples de explicar, roda com poucas amostras, é o que
  a maioria dos softwares de agricultura de precisão usa. O valor da amostra é
  respeitado no ponto e o mapa nunca passa do mínimo e do máximo amostrados.
- **Krigagem** (`krigagem-solo`): modela a dependência espacial e costuma
  errar menos quando a malha tem 30 pontos ou mais e há estrutura espacial.
- Em dúvida, rode as duas e compare o RMSE da validação cruzada, que as duas
  skills informam.

## Detalhes fixos da implementação

- Pixel padrão **5 m** (`--pixel` muda). Em fazenda grande com malha larga,
  `--pixel 10` ou `20` gera arquivos bem menores sem perder conteúdo
  agronômico. A decisão é do usuário.
- **Potência** `auto`: testa 1 · 1,5 · 2 · 2,5 · 3 · 4 e fica com a de menor
  RMSE na validação cruzada leave-one-out. `--potencia 2` fixa. Se a potência
  vencedora for a mais alta, o script avisa que o mapa fica perto do "vizinho
  mais próximo": ofereça ao usuário a comparação com potência 2.
- **Vizinhos**: 12 amostras por célula (`--vizinhos`). `--raio 600` limita a
  busca em metros; célula sem amostra dentro do raio fica vazia.
- Projeção alvo: **UTM / SIRGAS 2000** (zona automática; EPSG no rodapé).
- Áreas: contadas na grade (célula entra se o centro cai no perímetro).
- Pontos em coordenada repetida viram um só (média).
- Arquivos: `<elemento>.tif` (valores), `.pdf`, `.png`, `apostila.pdf`,
  `resumo_classes.csv`, `casamento.csv`, `relatorio.json`. Com
  `--tif-classes`, também `<elemento>-classes.tif` (1 = primeira classe).
- Teoria e limitações: `references/idw.md`.
