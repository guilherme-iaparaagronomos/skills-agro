# O que o script lê e o que ele confere

`scripts/leitura.py` tira os números do texto das ferramentas por expressão
regular. Por isso o texto precisa chegar ao arquivo **como a ferramenta
devolveu**. Esta página lista as linhas que ele procura e as conferências.

## uso_do_solo → `--uso`

| Linha procurada | O que vira |
|---|---|
| `Área completa — 1.669,5 ha.` | área do perímetro |
| `MapBiomas Coleção 11, de 1985 a 2025` | coleção e anos |
| `HOJE (mapa de 2025): Classe 662,1 ha (40 %) · … . Vegetação nativa: 676,9 ha (41 %).` | classes do último mapa e a vegetação nativa |
| `- 2008 (Código Florestal, …): vegetação nativa 685,1 ha (41 %) · Classe … ha (… %) · …` | uma linha por data-marco, com as cinco maiores classes |
| `SITUAÇÃO HOJE (…): Vegetação nativa … ha · Uso que já existia em 2008 … ha · Aberto … ha` | faixas de situação |
| `ABERTO DEPOIS DE 2008: … ha · depois de 2019: … ha · depois de 2020: … ha.` | os três totais |
| `ANO DA ABERTURA (…): 1986 14,3 ha · 1987 0,6 ha · …` | série por ano |
| `Cite a fonte: MapBiomas Coleção 11.` | texto da fonte |

Conferências:
- a soma das classes de hoje bate com a área (tolerância de 2%);
- a soma das faixas de situação bate com a área (2%);
- "aberto depois de" não cresce de 2008 para 2019 para 2020;
- a soma das faixas "Aberto…" bate com o total depois de 2008 (0,35 ha).

## cobertura_do_solo → `--cobertura`

| Linha procurada | O que vira |
|---|---|
| `período de 13/11/2025 a 12/11/2026 (…): 88 dias com imagem, a última em 09/11/2026.` | período, dias com imagem e data da última |
| `- Árvores 801 ha (48 %) — probabilidade média 68 %; 2ª mais provável ali: Gramíneas (pasto e campo) (5 %)` | uma linha por classe |
| `PROBABILIDADE DA CLASSE ESCOLHIDA, POR FAIXA (média de 55 %): 50 % ou mais em 972,7 ha (58 %) · …` | faixas de probabilidade |
| `Cite a fonte como está: Dynamic World V1 (…), de imagens Sentinel-2.` | texto da fonte |

Conferência: a soma das classes bate com a área (2%).

## prodes_fazenda → `--prodes`

| Linha procurada | O que vira |
|---|---|
| `DEPOIS DE 31/07/2019 (PRODES 2020 em diante): …` | faixa: `nenhum polígono` ou `N polígono(s), X ha na área — A ha em n polígono(s) ACIMA … e B ha em m ABAIXO dele` |
| `PRODES 2019 — À PARTE, … : …` | idem, para 2019 |
| `PRODES de 2008 a 2018: …` | idem |
| `- PRODES 2023 (imagem de 14/08/2023): 12 ha na área (polígono de 31,5 ha) — acima do mínimo de 5 ha` | um polígono (até 20) |
| `ALERTAS DO DETER … desde 01/11/2024: …` | alertas: nenhum, ou contagem, área e a lista |
| `ATÉ ONDE VAI O DADO: …` | cobertura temporal, copiada como veio |
| `Cite a fonte como está: …, licença ….` | fonte e licença |

Conferência: o número de polígonos das três faixas bate com a lista (mais o
"e mais N polígonos", quando há).

## relevo_fazenda → `--relevo`

| Linha procurada | O que vira |
|---|---|
| `ALTITUDE: de 450 a 563 m (média 509 m; desnível 113 m).` | altitude |
| `DECLIVE: médio 7,1 % · 90 % da área abaixo de 12,6 % · máximo 31,4 %.` | declive |
| `CLASSES DE RELEVO (Embrapa): Plano (0–3%) 15,4 % = 256,5 ha · …` | classes |
| `MECANIZAÇÃO (…): sem restrição (até 12%) 88,3 % · …` | faixas |
| `ENCOSTA ACIMA DE 45° (…): …` | copiada como veio |

Conferência: as classes somam 100% (tolerância de 1,5).

## imagem_satelite → `--imagem`

`Cena Sentinel-2 de 2026-10-27, com 99.7% da área livre de nuvem (fonte: …).`
→ data da cena, percentual e fonte.

## restricoes_fazenda → `--restricoes`

Três blocos, cada um com cabeçalho próprio, e a mesma forma por dentro:

| Linha do texto | O que vira |
|---|---|
| `UNIDADES DE CONSERVAÇÃO (CNUC, MMA, versão de DD/MM/AAAA):` | data da base |
| `N unidade(s) sobrepõe(m) a área: X ha, Y% dela` ou `Nenhuma unidade de conservação sobrepõe a área.` | total do bloco |
| `- Nome — categoria, grupo, esfera E, criada em AAAA; plano de manejo: …; X ha na área (Y%); a unidade inteira tem Z ha` | uma unidade |
| `PERTO (até 10 km da divisa): N unidade(s).` e as linhas `- Nome (categoria, grupo, esfera E) a X km` | o que fica perto |
| `TERRAS INDÍGENAS (FUNAI, base atualizada até DD/MM/AAAA):` | mesmo desenho; cada terra traz etnia e fase do processo |
| `EMBARGOS (IBAMA, base atualizada até …; ICMBio, até …):` | datas das duas bases |
| `N termo(s) de embargo toca(m) a área: A com contorno (X ha dentro da área, Y% dela) e B marcado(s) por ponto.` | total do bloco |
| `- ÓRGÃO, termo NÚMERO, de DD/MM/AAAA — tipo; contorno com X ha dentro da área (Y%)` ou `marcado por PONTO dentro da área`; `área embargada declarada no termo: Z ha (Município/UF)` | um termo, sem nome nem documento de pessoa |
| `A base não pôde ser lida nesta consulta` | o bloco sai como "base não lida" |
| `O QUE ESTA LEITURA NÃO COBRE: …` | copiada na nota da página |

Conferências: a quantidade de itens lidos bate com o total do bloco (o texto
traz no máximo 12 unidades, 12 terras e 15 termos); termos com contorno e por
ponto somam o total.

## solo_textura_carbono → `--solo`

| Linha do texto | O que vira |
|---|---|
| `… (N pixel(s) tocam a área)` | pixels de 250 m |
| `CAMADA DE 0–30 cm (média pesada pela espessura): argila A%, areia B%, silte C% — textura T; carbono orgânico X g/kg (cerca de Y% de matéria orgânica).` | camada de cima |
| `CAMADA DE 30–100 cm: …` | camada de baixo |
| `ESTOQUE DE CARBONO ORGÂNICO DE 0–30 cm: X t de carbono por hectare — cerca de Y t de carbono nos Z ha com dado.` | estoque |
| `DENTRO DA ÁREA: a argila de 0–30 cm vai de …` | variação entre os pixels |
| `FAIXA DE 90% DO PRÓPRIO MODELO, em cada pixel: …` | a incerteza que o mapa informa |
| as linhas depois de `POR CAMADA:` | tabela por profundidade |
| `ÁREA PEQUENA PARA ESTE MAPA` | nota de menos de 4 pixels |

Conferência: argila + areia + silte somam 100% em cada camada (tolerância de 1,5).

## Arquivos das ferramentas (figuras)

No fim de cada texto vem a lista `- nome.ext (NN KB): https://…`. O script
baixa só estes: `uso_solo_situacao.png`, `uso_solo_mapas.png`,
`uso_solo_historico.png`, `cobertura_classes.png`, `cobertura_confianca.png`,
`prodes_deter.png`, `relevo_altitude.png`,
`relevo_declividade.png`, `restricoes.png`, `solo_textura_carbono.png` e
`rgb_AAAA-MM-DD.tif`. Regras: só `https`, até 12 MB
por arquivo, e o conteúdo precisa ser mesmo PNG ou TIFF. GeoPackage, curvas de
nível e os GeoTIFFs de relevo não são baixados: são para o QGIS. Falha de rede
não derruba o dossiê; a saída diz o que faltou.

## Entre as ferramentas

- as áreas informadas por uso do solo, cobertura, PRODES, relevo, restrições e solo diferem menos de 1%
  (senão os textos não são do mesmo perímetro);
- a área declarada no CAR e a do perímetro analisado diferem menos de 3%
  (senão o perímetro pode não ser o do CAR informado).

## Quando aparece um aviso

1. "não li a linha …": a linha não está no arquivo ou foi alterada na cópia.
   Abra o texto da ferramenta e copie de novo.
2. Aviso de soma: um número foi trocado na cópia. Compare o arquivo com o
   texto da ferramenta.
3. O aviso continua com a cópia certa: o formato da ferramenta mudou. Diga
   isso ao usuário; o dossiê sai com a seção incompleta e o aviso fica
   registrado na última página. Não preencha número à mão.

## `car.json` (saída de `car.py`)

Campos usados: `car`, `municipio`, `uf`, `area_declarada_ha`,
`modulos_fiscais`, `data_cadastro`, `ultima_retificacao`,
`numero_retificacao`, `latitude`, `longitude`, `tipo_imovel`, `status`
(`codigo`, `texto`), `situacao_analise`, `sobreposicoes`, `consultado_em`,
`app_consultada` e `temas` (`camada`, `rotulo`, `grupo`, `feicoes`,
`area_ha`, `area_origem`). Os grupos são `reserva_legal`, `vegetacao_nativa`,
`area_consolidada`, `app`, `uso_restrito` e `outros`.
