# Fontes, datas-marco e limites

O dossiê não cria dado: reúne o que cada fonte entrega para o perímetro. Esta
página diz o que é cada fonte e até onde ela vai.

## Cadastro Ambiental Rural (SICAR)

- **O que é**: registro público eletrônico, autodeclaratório, dos imóveis
  rurais. O proprietário ou possuidor desenha o imóvel e as áreas (reserva
  legal, APP, remanescente de vegetação nativa, área consolidada).
- **De onde vem**: consulta pública do SICAR (`consulta.car.gov.br`), a mesma
  que a skill `consulta-car` usa: a API de detalhes do imóvel e o serviço WFS
  das camadas, filtrado pelo código do imóvel. Sem captcha, sem login.
- **O que o dossiê mostra**: situação do cadastro (ativo, pendente, suspenso
  ou cancelado), condição da análise, datas de inscrição e de retificação,
  módulos fiscais, sobreposições informadas e a área de cada tema declarado.
- **Limites**:
  - constar no CAR não é ser aprovado: a análise é do órgão ambiental;
  - o cadastro muda a cada retificação, e o dossiê é a foto do dia da consulta;
  - os temas se sobrepõem entre si; as linhas da tabela não se somam;
  - as sobreposições (terra indígena, unidade de conservação, quilombo, área
    embargada, terras da União) saem como o serviço devolve, um número por
    imóvel, sem a unidade documentada.

## Uso e cobertura do solo (MapBiomas)

- **O que é**: mapas anuais de uso e cobertura do solo do Brasil, com pixel de
  30 m, de 1985 ao último ano publicado.
- **O que o dossiê mostra**: as classes do último mapa; as classes nos anos
  das datas-marco; a situação de cada pixel (vegetação nativa, uso que já
  existia em 2008, aberto em cada período); e o ano em que cada área em uso
  deixou de ser vegetação nativa.
- **Limites**:
  - é classificação de imagem, com erro: mancha de poucos pixels pode não
    existir no terreno, e a borda do imóvel mistura o que está fora;
  - cada mapa é do ano inteiro, não do dia do marco;
  - não é a base oficial do crédito rural (essa é o PRODES) nem substitui o CAR.

## Supressão de vegetação nativa (PRODES e DETER, INPE)

- **PRODES**: mapeamento anual, consolidado, da supressão de vegetação nativa,
  por bioma, de 2008 em diante. O ano é o da temporada de imagens. Na Mata
  Atlântica, na Caatinga e no Pampa as imagens se espalham pelo ano civil.
- **DETER**: alertas rápidos, não consolidados, na Amazônia, no Cerrado e no
  Pantanal. Um alerta anterior à última imagem do PRODES pode já estar nele.
- **Mínimo da nota do MMA**: o tamanho de polígono, medido inteiro, a partir
  do qual a nota técnica usada no crédito rural considera a supressão: mais de
  6,25 ha na Amazônia; mais de 5 ha no Cerrado e no Pantanal; mais de 2 ha na
  Mata Atlântica, na Caatinga e no Pampa. O dossiê mostra todos os polígonos e
  de que lado do mínimo cada um fica; não tira conclusão disso.
- **Licença**: CC BY-SA 4.0. Cite como a ferramenta manda.

## Relevo (modelo digital de terreno de 30 m)

- **O que é**: modelo do terreno, sem a vegetação, com pixel de 30 m.
- **O que o dossiê mostra**: altitude, desnível, declive, as classes de relevo
  da Embrapa e as faixas de declive usuais para mecanização.
- **Limites**: não vê terraço, curva de nível nem obra recente; não substitui
  levantamento topográfico. As faixas de mecanização são referência técnica
  usual, não regra.

## Imagem de satélite (Sentinel-2)

O dossiê registra a data da cena mais recente sem nuvem e o percentual do
perímetro livre de nuvem. A imagem em si vai ao usuário como GeoTIFF, para o
QGIS.

## As datas-marco

| Marco | De onde vem | Como aparece |
|---|---|---|
| 22/07/2008 | Código Florestal (Lei 12.651/2012): data de referência da área rural consolidada | mapa de 2008 |
| 31/07/2019 | corte usado nas regras do crédito rural para supressão de vegetação nativa | mapa de 2019; PRODES 2020 em diante |
| 31/12/2020 | regulamento europeu de produtos livres de desmatamento (EUDR) | mapa de 2020 |

O dossiê informa a área em cada lado de cada data. O que isso significa para
o imóvel depende de análise que não é feita aqui.

## Como citar

Use o texto de fonte que cada ferramenta devolve, sem trocar palavra. Sobre o
processamento, a única frase é: "processado pelas ferramentas da comunidade
agrônomo10X (OagronomIA)".
