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

## Entre as ferramentas

- as áreas informadas por uso do solo, PRODES e relevo diferem menos de 1%
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
