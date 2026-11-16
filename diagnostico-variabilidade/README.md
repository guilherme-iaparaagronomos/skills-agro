# Diagnóstico da variabilidade do talhão

Skill da comunidade agrônomo10X para descobrir, com a sua IA, **o que varia
junto** com a produtividade (ou com outra variável) dentro de um talhão. Você
envia o perímetro e as camadas que tem: mapa de colheita, mapas de solo,
relevo, índices de vegetação de outras safras, condutividade elétrica, drone,
zonas, variedades. Ela põe tudo numa grade comum e mostra quem acompanha quem.

Só descreve. Variar junto não é causa, e a skill não recomenda correção nem
manejo: a decisão é do responsável técnico.

## O que entrega

- O diagnóstico das camadas, antes de qualquer conta: cobertura, resolução e
  camadas que se repetem.
- A correlação de cada camada com a variável a explicar, com um intervalo que
  respeita a semelhança entre células vizinhas (dez mil células de um mapa
  suave valem algumas dezenas de observações).
- A parte de cada camada: sozinha, por cima das outras e repartida.
- As manchas de valor baixo, médio e alto, com a média de cada camada em cada
  uma.
- `relato.md`, quatro CSV, o mapa das manchas em GeoTIFF, figuras e PDF.

Você escolhe a variável a explicar e as camadas que entram. A skill pergunta
depois do diagnóstico.

## O que precisa

- Um ambiente que rode Python 3 com `numpy`, `scipy` e `matplotlib`.
- O perímetro do talhão e pelo menos duas camadas em arquivo: GeoTIFF (SIRGAS
  2000 / UTM, WGS 84 / UTM ou graus), pontos densos (CSV, TXT, shapefile, zip
  ou GeoJSON) ou polígonos com classe.
- Laudo de solo em pontos esparsos entra já interpolado (skills
  `interpolacao-krigagem` e `interpolacao-idw`). O mapa de colheita entra
  limpo (skill `limpeza-monitor-produtividade`).

Não usa conector nem internet.

## Estrutura

```
diagnostico-variabilidade/
  SKILL.md                o roteiro que a IA segue
  README.md
  references/metodo.md    as contas, a conferência e os limites
  scripts/
    variabilidade.py      entrada: --diagnostico, a análise e --demo
    camadas.py            lê o perímetro e as camadas e monta o diagnóstico
    malha.py              a grade comum: raster, pontos e classes em células
    espacial.py           correlograma e número de observações independentes
    relacoes.py           correlações e a parte de cada camada
    manchas.py            faixas, manchas e perfil
    analise.py            junta tudo e monta os avisos
    relato.py             o texto
    saidas.py             CSV, GeoTIFF, figuras e PDF
    sintetico.py          talhão inventado, com relações plantadas
    geotiff.py, geometria.py, areas.py, leitura.py, shapefile_min.py
                          leitura de arquivos, as mesmas das outras skills da casa
```

Para ver funcionando sem dado nenhum:

```
python scripts/variabilidade.py --demo --saida saida-demo
```

Cada módulo roda sozinho como teste: `python scripts/espacial.py`.

## Instalar

Baixe o zip pelo botão da página da skill, ou a pasta deste repositório, e
adicione como skill na sua IA (em Claude: Configurações › Capacidades ›
Skills; em outras IAs compatíveis, a pasta de skills do projeto).

## Como foi testada

- **Talhão inventado com relações plantadas** (o do `--demo`): a
  produtividade depende da argila e da altitude; o pH não tem relação; uma
  segunda camada de argila é quase cópia da primeira. A skill reconheceu a
  argila e a altitude, deu o pH como "não se distingue do acaso" e avisou da
  redundância. Repetido em 24 talhões inventados: argila reconhecida nos 24;
  altitude (relação mais fraca) em 12; pH dado como relação em 2; aviso de
  redundância nos 24.
- **O intervalo das correlações**, por simulação com mapas sem relação
  nenhuma: acusou relação em 4% a 8% das vezes (o certo é 5%), onde a conta
  comum, com o número de células, acusava em 59% a 93%. Os números estão em
  `references/metodo.md`.
- **Contas refeitas por outro caminho**, sem usar os módulos da skill:
  correlações direto na biblioteca, R² de 32 subconjuntos por mínimos
  quadrados nos dados, a parte repartida em todas as 120 ordens de entrada, e
  o número de observações independentes contando os pares em 6.509
  defasagens, uma a uma. 115 conferências, sem diferença.
- **Leitura dos arquivos contra o GDAL e o PROJ** (os do QGIS): raster em
  graus, raster inteiro de 16 bits com NoData, raster de 64 bits em outro
  datum UTM, média de pixel fino dentro da célula, e a recusa do que não é
  coberto (SAD 69, Web Mercator, TIFF sem georreferência). 26 conferências,
  sem diferença.
- **Linha de comando**: 16 pedidos que têm de dar certo e 30 que têm de parar
  com o motivo; 111 conferências.
- **Dois mapas de solo de verdade**, de uma fazenda de 5 mil hectares,
  interpolados pela skill de krigagem da casa: a leitura e as páginas do PDF
  funcionaram com 14 mil células e vários polígonos.
- **O PDF foi olhado**, página a página, no exemplo e nos mapas reais.

O que **não** foi feito:

- usar com um mapa de produtividade de máquina de verdade. A produtividade de
  todos os testes é inventada;
- testar com condutividade elétrica, drone ou índice de vegetação reais;
- comparar o número de observações independentes com outro programa (a
  conferência foi por simulação e por uma segunda implementação);
- rodar a skill inteira dentro de uma conversa em duas IAs diferentes.

## Avisos

- Variar junto não é causa. O resultado depende de quais camadas você enviou:
  a que realmente pesa pode não estar entre elas.
- Com poucas observações independentes (mapas muito suaves), relação fraca de
  verdade também não se distingue do acaso.
- Camadas parecidas repartem a importância; isso não diz qual delas pesa.
- Índice de vegetação da mesma safra da produtividade fica de fora.
- A conta é de reta. Ótimo no meio aparece só na nota de curva e nas manchas.
- A decisão de manejo é do responsável técnico.

Autoria: Equipe agrônomo10X (OagronomIA).
