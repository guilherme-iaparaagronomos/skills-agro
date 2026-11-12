# Fontes, datas-marco e limites

O dossiê não cria dado: reúne o que cada fonte entrega para o perímetro. Esta
página diz o que é cada fonte e até onde ela vai.

## Cadastro Ambiental Rural (SICAR)

- **O que é**: registro público eletrônico, autodeclaratório, dos imóveis
  rurais. O proprietário ou possuidor desenha o imóvel e as áreas (reserva
  legal, APP, remanescente de vegetação nativa, área consolidada).
- **De onde vem**: consulta pública do SICAR (`consulta.car.gov.br`), a mesma
  que a skill `consulta-car` usa. A ferramenta do dossiê faz a consulta pelo
  número do CAR.
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

## Cobertura do solo recente (Dynamic World)

- **O que é**: classificação automática de cada imagem Sentinel-2, com pixel
  de 10 m, em 9 classes genéricas, com a probabilidade de cada classe.
- **O que o dossiê mostra**: a classe mais provável de cada pixel na média das
  imagens dos últimos 12 meses, a área de cada classe, a probabilidade média
  e a segunda classe mais provável.
- **Limites**:
  - é a leitura de um modelo, não um fato do imóvel;
  - "Lavoura" não diz qual cultura e "Gramíneas" junta pasto e campo nativo;
  - não separa vegetação nativa de plantada e não mede desmatamento;
  - probabilidade baixa indica com o que a classe se confunde, não erro.
- **Para que serve ao lado do mapeamento anual**: o mapeamento anual dá a
  história e as datas-marco, com pixel de 30 m e um mapa por ano; a cobertura
  recente dá o retrato dos últimos meses, com pixel de 10 m.

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

## Unidades de conservação, terras indígenas e termos de embargo

- **O que é**: três bases públicas cruzadas com o perímetro. Unidades de
  conservação: Cadastro Nacional de Unidades de Conservação (CNUC), do
  Ministério do Meio Ambiente. Terras indígenas: FUNAI. Termos de embargo:
  IBAMA e ICMBio.
- **O que o dossiê mostra**: o que sobrepõe o perímetro (quantos, hectares e
  % da área) e o que fica perto (até 10 km para unidade de conservação e terra
  indígena; até 1 km para termo de embargo), com a data de cada base.
- **Termos de embargo**: aparecem pelo número, sem nome e sem documento de
  pessoa. Há termo com contorno e termo marcado só por um ponto (o órgão
  registrou a coordenada, não o contorno). A base do IBAMA tem termos sem
  localização, que não entram no cruzamento.
- **Limites**: é a leitura das bases na data de cada uma; não equivale a
  certidão e não substitui a consulta ao órgão. Ficam de fora territórios
  quilombolas, assentamentos, florestas públicas, embargos de órgãos estaduais
  e a zona de amortecimento de cada unidade. Estar dentro de unidade de uso
  sustentável não diz, por si, o que é permitido: as regras são de cada unidade.

## Solo: textura e carbono (SoilGrids)

- **O que é**: SoilGrids 2.0, mapa mundial de solos do ISRIC (World Soil
  Information), feito por modelo, com pixel de 250 m. Licença CC BY 4.0.
- **O que o dossiê mostra**: argila, areia, silte, classe textural (grupamento
  da Embrapa) e carbono orgânico por profundidade; o estoque de carbono de
  0–30 cm; a variação entre os pixels do perímetro e a faixa de 90% que o
  próprio modelo informa.
- **Limites**: são valores modelados, não medições. O ISRIC informa que o
  mapa não foi feito para a escala de fazenda, e os valores tendem ao meio da
  faixa (solo muito arenoso ou muito argiloso costuma sair como médio). Não
  substitui análise de solo. O estoque de carbono não equivale a crédito de
  carbono. A matéria orgânica é o carbono × 1,724 (conversão convencional).

## Imagem de satélite (Sentinel-2 e CBERS-4A)

- **Cor real, 10 m (Sentinel-2)**: o dossiê traz a cena mais recente sem
  nuvem, com a data e o percentual do perímetro livre de nuvem.
- **Alta resolução, 2 m (CBERS-4A, câmera WPM, INPE)**: a cena mais recente
  dos últimos 36 meses que cobre o perímetro inteiro com pouca nuvem. O
  satélite repete a área a cada 31 dias e muita passagem tem nuvem; quando
  nenhuma serve, o documento diz isso e lista as datas que existem.
- O GeoTIFF de cada imagem, para o QGIS, vem das ferramentas `imagem_satelite`
  e `imagem_cbers`, não do dossiê.

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
