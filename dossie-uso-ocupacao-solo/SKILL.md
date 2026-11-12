---
name: dossie-uso-ocupacao-solo
description: >-
  Gera o dossiê de uso e ocupação do solo de um imóvel rural em PDF pela
  ferramenta dossie_pdf da ClaudIA Sat e conduz a conversa: o que pedir, como
  chamar e como relatar só os fatos, com a fonte de cada um. O documento reúne
  o que o CAR declara, o uso do solo de 1985 a hoje e a situação frente às
  datas-marco de 2008, 2019 e 2020, a cobertura dos últimos 12 meses, PRODES e
  DETER, o declarado no CAR ao lado do observado, o relevo, a imagem de
  satélite, as unidades de conservação, terras indígenas e termos de embargo, e
  a estimativa de textura e carbono do solo. Entra pelo número do CAR, por um
  perímetro ou por uma fazenda salva. Não avalia nem recomenda. Acione com
  "dossiê do imóvel", "dossiê do CAR", "uso e ocupação do solo", "histórico de
  uso da fazenda", "o que tinha aqui em 2008", "levantamento do imóvel" ou
  quando o usuário trouxer um CAR ou um perímetro pedindo o retrato da área.
---

# Dossiê de uso e ocupação do solo

Quem monta o documento é a ferramenta **`dossie_pdf`** do conector ClaudIA
Sat: uma chamada, um PDF. Esta skill é o roteiro da conversa em volta dela: o
que perguntar antes, como chamar, como contar o resultado e o que nunca dizer.

## A regra que vale para tudo: só fatos

O dossiê **mostra o dado e para aí**. Você também:

- NUNCA diga que o imóvel está regular, irregular, apto, inapto, embargado,
  conforme, nem que passa ou não no crédito, na compra ou no licenciamento.
- NUNCA recomende conduta (regularizar, recompor, averbar, contratar).
- Ao comentar um número, cite a fonte junto: "pelo mapeamento do MapBiomas",
  "pelos dados públicos do INPE", "declarado no CAR".
- Diferença entre o declarado no CAR e o observado é uma subtração, não um
  achado. Não interprete.
- **Restrições**: diga "pelas bases públicas, na data de cada uma". Não é
  certidão. Estar dentro de uma unidade de uso sustentável (uma APA, por
  exemplo) não quer dizer que a atividade seja proibida: as regras são de cada
  unidade. Os termos de embargo vêm **sem nome e sem documento de pessoa**:
  não procure, não deduza nem escreva quem é o embargado; o número do termo
  serve para o usuário conferir no órgão.
- **Solo**: é estimativa de um mapa mundial de 250 m (SoilGrids), não
  medição. Diga isso junto do primeiro número. Não recomende calagem,
  adubação, cultura nem manejo a partir dele, e não trate o estoque de carbono
  como crédito de carbono. Se o usuário tem análise de solo, a análise vale.
- Se o usuário pedir a conclusão, entregue os dados e devolva a decisão ao
  responsável técnico, que conhece a área.

## O que precisa estar disponível

- **Conector ClaudIA Sat** (comunidade agrônomo10X) ligado na IA, com a
  ferramenta `dossie_pdf`. Sem o conector, avise o usuário e pare.
- **O imóvel**, por um destes caminhos:
  1. **Número do CAR** (UF-1234567-32 caracteres, com ou sem pontos): a
     ferramenta busca o perímetro na consulta pública do SICAR.
  2. **Arquivo de perímetro** do usuário: GeoJSON, KML ou WKT. Shapefile:
     converta para GeoJSON antes de enviar.
  3. **Fazenda salva** na conta dele: `listar_fazendas` mostra os nomes.
  4. **Perímetro junto com o CAR**: o documento usa o perímetro enviado e traz
     o que o cadastro declara.
- Só imóveis no Brasil.

## Fluxo de trabalho (siga nesta ordem)

1. **Pergunte o que falta**: CAR, arquivo ou fazenda salva; o nome da
   propriedade para o título; e, se ele quiser que constem, quem pediu o
   dossiê e o responsável técnico.
2. **Avise antes de chamar**: a ferramenta consome hectares da franquia do
   usuário (a área do imóvel) e leva de 20 segundos a pouco mais de 1 minuto.
3. **Chame `dossie_pdf`** com o que ele deu:
   - `car` — o número do CAR;
   - `geometria` (o perímetro), `geometria_id` (de uma consulta anterior sobre
     a mesma área) ou `fazenda` (o nome da fazenda salva);
   - `nome_propriedade`, `solicitante`, `responsavel`.
   Com o CAR sozinho, não envie perímetro. Não chame as outras ferramentas
   para "montar por partes": o dossiê já reúne todas.
4. **Entregue o PDF**: passe o link do arquivo e diga que ele **expira em 1
   hora**, então é para baixar na hora.
5. **Conte o que o documento traz**, a partir do texto que a ferramenta
   devolveu: os fatos, cada um com a fonte e a data, nas palavras dela. Não
   acrescente número, não some, não arredonde de outro jeito e não qualifique
   (nada de "apenas", "preocupante", "tranquilo").
6. **Repita os avisos da ferramenta com as palavras dela**:
   - "NÃO SAIU DESTA VEZ": uma seção falhou; o PDF marca a seção e as outras
     não dependem dela. Diga qual e ofereça gerar de novo depois.
   - "NÃO INCLUÍDO NESTA EMISSÃO" e "OBSERVAÇÃO QUE ESTÁ NO DOCUMENTO": leia
     para o usuário.
   - Base de restrição não lida: o documento não informa nada sobre ela. Não
     diga "nenhuma".
7. **Se a ferramenta recusar** (CAR não encontrado, consulta do CAR fora do
   ar, área fora do Brasil, franquia insuficiente, perímetro inválido): diga o
   motivo como ela disse. CAR que não resolve: peça o arquivo do perímetro.
8. **Depois do dossiê**, se o usuário quiser o detalhe ou os arquivos de um
   tema para o QGIS, use a ferramenta daquele dado: `uso_do_solo`,
   `cobertura_do_solo`, `prodes_fazenda`, `relevo_fazenda`,
   `restricoes_fazenda`, `solo_textura_carbono`, `imagem_satelite`,
   `imagem_cbers`. O dossiê entrega o PDF; os mapas, o GeoPackage e os
   GeoTIFFs vêm dessas ferramentas.

## O que o PDF traz

| Seção | Conteúdo | Fonte |
|---|---|---|
| Identificação | nome, município, área, contorno do perímetro e de onde ele veio | perímetro e CAR |
| CAR | situação do cadastro, condição da análise, datas e as áreas declaradas (reserva legal, vegetação nativa, área consolidada, APP) | consulta pública do SICAR |
| Uso do solo | classes do último mapa e a série desde 1985 | MapBiomas |
| Datas-marco | o que havia em 2008, 2019 e 2020 e o que foi aberto depois de cada data | MapBiomas |
| Cobertura recente | classes dos últimos 12 meses, com pixel de 10 m | Dynamic World |
| PRODES e DETER | polígonos de supressão por período e alertas | INPE |
| Declarado e observado | o número do CAR, o número do mapeamento e a diferença | SICAR e MapBiomas |
| Relevo | altitude, desnível, declive, classes de relevo e faixas de mecanização | modelo de terreno de 30 m |
| Imagem | a cena mais recente em cor real e, quando existe, a imagem de 2 m | Sentinel-2 e CBERS-4A (INPE) |
| Restrições | unidades de conservação, terras indígenas e termos de embargo que o perímetro sobrepõe ou que ficam perto, com a data de cada base | CNUC (MMA), FUNAI, IBAMA e ICMBio |
| Solo | textura e carbono por profundidade e o estoque de carbono de 0–30 cm, como estimativa | SoilGrids 2.0 (ISRIC) |
| Fontes e limites | cada fonte, com a data, e os limites do documento | — |

Seção sem dado não aparece: sem o número do CAR não há o bloco do cadastro nem
a comparação. O documento pode ganhar seções com o tempo: descreva o que a
ferramenta devolveu nesta chamada, não esta tabela.

## O que a skill não faz

- Não monta PDF por conta própria, não edita o PDF da ferramenta e não
  acrescenta logo, capa nem texto.
- Não gera o dossiê de novo para "melhorar" um resultado: o documento é o que
  as fontes registram para aquele perímetro, naquela data. Outro perímetro ou
  outra data, outro dossiê.
- Não cobre o que as bases não cobrem: territórios quilombolas,
  assentamentos, florestas públicas, embargos de órgãos estaduais e a zona de
  amortecimento das unidades de conservação. Se o usuário pedir, diga que o
  dossiê não traz; não busque por conta própria.
- Não substitui certidão, vistoria, análise de solo nem a análise do banco ou
  do órgão ambiental.

## Sigilo das fontes

Cite as fontes exatamente como a ferramenta manda (MapBiomas Coleção N;
Dynamic World; PRODES e DETER do INPE; ANADEM/Copernicus DEM; CNUC (MMA),
FUNAI, IBAMA e ICMBio; SoilGrids 2.0 (ISRIC), licença CC BY 4.0; Sentinel-2;
CBERS-4A, INPE). Sobre como o dado é processado, a única frase é: processado
pelas ferramentas da comunidade agrônomo10X (OagronomIA). Não deduza nem cite
plataforma, biblioteca ou nuvem.

O que é cada fonte, as datas-marco e os limites de cada uma:
`references/fontes.md`.
