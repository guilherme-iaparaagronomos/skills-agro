# Fontes e limites

O quadro não cria dado: põe lado a lado o que cada ferramenta entrega para a
área. Esta página diz o que é cada parte e até onde ela vai.

## Dossiê do imóvel (`dossie_pdf`)

- **O que traz**: o que o CAR declara (consulta pública do SICAR), o uso do
  solo de 1985 ao último mapa e a situação frente a 2008, 2019 e 2020
  (MapBiomas), a cobertura dos últimos 12 meses (Dynamic World), PRODES e
  DETER (INPE), o declarado ao lado do observado, o relevo, a imagem em cor
  real (Sentinel-2) e a de 2 m (CBERS-4A, INPE), as unidades de conservação
  (CNUC, MMA), terras indígenas (FUNAI) e termos de embargo (IBAMA e ICMBio),
  e a estimativa de textura e carbono do solo (SoilGrids 2.0, ISRIC).
- **Limites**:
  - constar no CAR não é ser aprovado: o cadastro é autodeclaratório e a
    análise é do órgão ambiental;
  - mapa de uso do solo é classificação de imagem, com erro, e cada mapa é do
    ano inteiro, não do dia de uma data-marco;
  - as bases de restrição têm data: o que entrou depois não aparece. Não é
    certidão;
  - os termos de embargo vêm sem nome e sem documento de pessoa; o número do
    termo serve para conferir no órgão;
  - o solo é estimativa de modelo, com pixel de 250 m. Não substitui análise.
- A skill `dossie-uso-ocupacao-solo` detalha cada fonte do dossiê.

## Índice de vegetação por safra (`curva_com_chuva`)

- **O que é**: a média do índice na área consultada em cada imagem do
  Sentinel-2 que passou no filtro de nuvem, ao longo da janela pedida. O
  padrão é o NDVI, que mede o vigor da vegetação.
- **Limites**:
  - **não é produtividade**. Duas safras com o mesmo pico podem ter colhido
    quantidades diferentes; doença, praga, acamamento, falha de colheita e
    preço não aparecem no índice;
  - é a média da área inteira consultada. Se o perímetro mistura lavoura,
    pasto e mata, o número mistura os três. Por isso a skill pede o perímetro
    da lavoura;
  - o satélite passa a cada poucos dias e a nuvem tira imagens. Em meses
    chuvosos e em safras antigas pode haver semanas sem imagem, e o pico
    registrado pode ser menor que o pico de verdade. A coluna "maior
    intervalo sem imagem" existe para o leitor ver isso;
  - a curva não diz qual cultura estava plantada nem se houve uma ou duas
    safras na janela;
  - cada chamada cobre até 400 dias.

## Chuva da safra e veranicos (`curva_com_chuva`)

- **O que é**: a chuva dia a dia da mesma área no mesmo período, o total, os
  dias de chuva e os veranicos. Por padrão, veranico é 7 ou mais dias
  seguidos com menos de 2 mm por dia; a ferramenta escreve a definição usada.
- **Limites**:
  - é chuva estimada para a área a partir de pluviômetros e satélites, não a
    leitura de um pluviômetro dentro da fazenda. A ferramenta informa a
    confiança;
  - os dias mais recentes ainda podem ser revisados;
  - veranico coincidir com queda do índice não prova a causa;
  - com a janela do ano agrícola, a estiagem normal do inverno entra na
    contagem de veranicos.

## Chuva dos últimos anos (`clima_historico`)

- **O que é**: a chuva de cada ano na área, ao lado da média histórica de
  1991 a 2020 do mesmo período, com a diferença em %.
- **Limites**: ano incompleto não se compara com ano inteiro; a média de 30
  anos é a referência de normal, não uma previsão.

## O ano em curso (`contexto_chuva`)

- **O que é**: a chuva desde 1º de julho comparada com a dos outros anos na
  mesma data, e o que costuma vir até 31 de dezembro.
- **Limites**: é descrição do registro. As frases vão para o quadro como a
  ferramenta escreveu; não viram "vai chover tanto" nem "o ano será igual a".

## O que fica de fora

O quadro não consulta o Zoneamento Agrícola de Risco Climático (ZARC), o
Manual de Crédito Rural, a política de cada instituição, matrícula, CCIR,
ITR, certidões nem cadastros de pessoas. Também não visita a área. O que cada
registro significa para o crédito é decisão do analista, com as regras da
instituição; o que significa para a lavoura, do responsável técnico.

## Como citar

- Dossiê: as fontes como estão na última página do PDF.
- Índice e chuva das safras: as linhas do bloco "FONTES DOS DADOS" com que a
  `curva_com_chuva` fecha a resposta, inteiras e como vieram.
- Chuva dos últimos anos: as linhas "Chuva" e "Média histórica" do bloco
  "FONTES DOS DADOS" da `clima_historico`.
- Não troque por nome genérico, não acrescente fonte que a ferramenta não
  informou e não descreva como os dados são combinados nem processados.
