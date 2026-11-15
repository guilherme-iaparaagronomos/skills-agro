# As colunas da planilha

A `triagem.csv` tem um imóvel por linha. As duas primeiras linhas são
cabeçalho: o nome curto da coluna (o que se usa em `--criterio`) e o nome por
extenso. Separador ponto e vírgula, decimal com vírgula.

Cada coluna vem de uma linha do resumo que a ferramenta `dossie_pdf` devolve.
Se a linha não veio, as colunas dela ficam **vazias**. Vazio não é zero.

| Coluna | O que é | Linha do resumo |
|---|---|---|
| `imovel` | o CAR ou o nome, como na lista | linha `IMOVEL:` do arquivo |
| `ficha` | o nome do PDF salvo | linha `FICHA:` do arquivo |
| `titulo`, `municipio`, `area_ha`, `perimetro`, `paginas` | identificação do dossiê | primeira linha |
| `car_situacao`, `car_condicao`, `car_area_declarada_ha`, `car_consultado_em` | o que o CAR declara, pela consulta pública do SICAR | O QUE O CAR DECLARA |
| `nativa_ha`, `nativa_pct` | vegetação nativa no último mapa anual | USO DO SOLO |
| `uso_fonte`, `uso_ano` | a fonte e o ano desse mapa | USO DO SOLO |
| `aberta_depois_2008_ha`, `aberta_depois_2019_ha`, `aberta_depois_2020_ha` | vegetação nativa que deixou de ser nativa depois de cada data | USO DO SOLO |
| `prodes_2020_poligonos`, `prodes_2020_ha` | PRODES de 2020 em diante (supressão depois de 31/07/2019) | PRODES E DETER |
| `prodes_2019_poligonos`, `prodes_2019_ha` | PRODES 2019 | PRODES E DETER |
| `prodes_2008_2018_poligonos`, `prodes_2008_2018_ha` | PRODES de 2008 a 2018 | PRODES E DETER |
| `deter_alertas`, `deter_ha` | alertas DETER no período que a linha informa | PRODES E DETER |
| `deter_depois_prodes_alertas`, `deter_depois_prodes_ha` | alertas depois da última imagem do PRODES | PRODES E DETER |
| `uc_n`, `uc_ha` | unidades de conservação que sobrepõem o perímetro | RESTRIÇÕES |
| `ti_n`, `ti_ha` | terras indígenas que sobrepõem o perímetro | RESTRIÇÕES |
| `embargos_n`, `embargos_ha`, `embargos_por_ponto` | termos de embargo que tocam o perímetro; a área só dos que têm contorno | RESTRIÇÕES |
| `itens_perto` | itens das mesmas bases perto do perímetro, sem sobrepor | RESTRIÇÕES |
| `bases_nao_lidas` | quantas bases de restrição não foram lidas naquela emissão | RESTRIÇÕES |
| `declive_medio_pct`, `declive_max_pct` | declive do terreno | RELEVO |
| `argila_pct`, `textura` | estimativa de um mapa mundial de 250 m | SOLO |
| `imagem_data` | data da imagem em cor real da ficha | IMAGEM EM COR REAL |
| `nao_saiu` | seções que a ferramenta não conseguiu gerar, com o motivo | NÃO SAIU DESTA VEZ |
| `observacoes` | observações e itens não incluídos | OBSERVAÇÃO / NÃO INCLUÍDO |
| `criterio_do_usuario: ...` | uma coluna por regra informada: sim, não ou sem dado | calculada |
| `arquivo_lido` | o arquivo de texto de onde a linha saiu | |

## Como ler algumas colunas

- **`aberta_depois_...`** e **PRODES** medem coisas parecidas por caminhos
  diferentes: a primeira compara mapas anuais de uso do solo; o PRODES é o
  mapeamento de supressão do INPE. Os dois números podem não bater. A planilha
  mostra os dois.
- **`embargos_ha`** soma só os termos que têm contorno. Termo marcado por
  ponto entra em `embargos_por_ponto` e não tem área.
- **`bases_nao_lidas` maior que zero**: as colunas de restrição valem só para
  as bases que foram lidas. Diga isso ao lado do número.
- **`car_...` vazias** quando o imóvel entrou por fazenda salva ou por arquivo,
  sem o número do CAR.
- **`itens_perto`** não é sobreposição.

## O quadro da conversa

O `triagem.md` leva as colunas: imóvel, município, área, vegetação nativa
(%), nativa aberta depois de 2008 e de 2019, PRODES de 2020 em diante,
alertas DETER, sobreposição com UC e com TI, embargos e seções que não
saíram, mais as colunas de critério. O resto está no CSV e na ficha.
