---
name: dossie-uso-ocupacao-solo
description: >-
  Monta o dossiê de uso e ocupação do solo de um imóvel rural em PDF, só com
  fatos e a fonte de cada um. Reúne o uso do solo de 1985 a hoje e a situação
  frente às datas-marco de 2008, 2019 e 2020 (MapBiomas), a cobertura do solo
  dos últimos 12 meses (Dynamic World), a supressão mapeada pelo INPE (PRODES
  e DETER), o relevo, as unidades de conservação, terras indígenas e termos de
  embargo que o perímetro sobrepõe, a textura e o carbono do solo estimados
  (SoilGrids) e, quando há o número do CAR, o que o cadastro declara
  (situação, reserva legal, vegetação nativa, área consolidada, APP) ao lado
  do que os mapas mostram. Parte do número do CAR
  (busca o perímetro no SICAR), de um arquivo de perímetro ou de uma fazenda
  salva. Usa o conector ClaudIA Sat. Não avalia nem recomenda. Acione com
  "dossiê do imóvel", "uso e ocupação do solo", "histórico de uso da fazenda",
  "o que tinha aqui em 2008", "levantamento do CAR" ou quando o usuário trouxer
  um CAR ou um perímetro pedindo o histórico da área.
---

# Dossiê de uso e ocupação do solo

Junta num PDF o que bases públicas e mapeamentos por satélite registram sobre
um imóvel: uso do solo ano a ano, datas-marco, PRODES e DETER, relevo,
unidades de conservação, terras indígenas, termos de embargo, a estimativa de
textura e carbono do solo e as declarações do CAR. Cada número sai com a fonte
e a data.

## A regra que vale para tudo: só fatos

O dossiê **mostra o dado e para aí**. Você também:

- NUNCA diga que o imóvel está regular, irregular, apto, inapto, embargado,
  conforme, nem que passa ou não no crédito.
- NUNCA recomende conduta (regularizar, recompor, averbar, contratar).
- Ao comentar um número, cite a fonte junto: "pelo mapeamento do MapBiomas",
  "pelos dados públicos do INPE", "declarado no CAR".
- Diferença entre o declarado e o observado é uma subtração, não um achado.
- Se o usuário pedir a conclusão, entregue os dados e devolva a decisão ao
  responsável técnico, que conhece a área.
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

## O que precisa estar disponível

- **Conector ClaudIA Sat** (comunidade agrônomo10X) ligado na IA: é ele que
  devolve uso do solo, PRODES, relevo, restrições, solo e imagem. Sem ele não há dossiê: avise o
  usuário e pare.
- **Perímetro**, por um destes três caminhos:
  1. **Número do CAR** → `scripts/car.py` busca o polígono e as declarações no
     SICAR. Precisa de internet. Na sandbox de código do chat o site do CAR é
     bloqueado: o script avisa; aí peça o arquivo do perímetro ao usuário (ele
     baixa no site do CAR ou com a skill `consulta-car` onde há internet).
  2. **Arquivo** do usuário: `.kml`, `.geojson`, `.shp` (com `.dbf`/`.prj`) ou WKT.
  3. **Fazenda salva** na conta dele (`listar_fazendas`): as ferramentas
     aceitam o nome; para o desenho do contorno o script ainda precisa do
     arquivo — peça-o, ou monte o dossiê sem o bloco do CAR.

## Fluxo de trabalho (siga nesta ordem)

1. **Pergunte o que falta**: nome do imóvel para a capa; CAR, arquivo ou
   fazenda salva; solicitante e responsável técnico, se quiser que constem.
2. **Perímetro e CAR** (quando houver o número):
   `python scripts/car.py <CAR> --saida ./dossie`
   Grava `car.json`, `perimetro.geojson` e `car-temas.geojson`. CAR não
   encontrado ou serviço fora do ar: diga ao usuário e siga com o arquivo dele.
3. **Chame as ferramentas da ClaudIA Sat** com o MESMO perímetro (envie o
   GeoJSON na primeira e reutilize o `geometria_id` nas seguintes):
   - `uso_do_solo` — obrigatória;
   - `cobertura_do_solo` — o retrato dos últimos 12 meses, com pixel de 10 m
     (demora cerca de um minuto);
   - `prodes_fazenda`;
   - `relevo_fazenda`;
   - `restricoes_fazenda` — unidades de conservação, terras indígenas e
     termos de embargo que o perímetro sobrepõe ou que ficam perto;
   - `solo_textura_carbono` — textura e carbono estimados pelo SoilGrids;
   - `imagem_satelite` (produto `rgb`) — só para registrar a data da cena mais
     recente sem nuvem.
   As seis primeiras consomem hectares da franquia do usuário: avise antes.
   Se alguma não existir no conector do usuário, monte sem ela e diga qual
   seção ficou de fora.
4. **Grave o texto de cada ferramenta num arquivo, COMO VEIO**: `uso.txt`,
   `cobertura.txt`, `prodes.txt`, `relevo.txt`, `restricoes.txt`, `solo.txt`,
   `imagem.txt`. Copie o texto inteiro, sem
   resumir, reordenar, traduzir nem arredondar, **com a lista de arquivos e os
   links**. O script lê os números desse texto e confere as somas (um número
   trocado na cópia aparece como aviso) e usa os links para buscar os mapas.
   Os links valem 1 hora: monte o dossiê logo depois das consultas.
5. **Monte**:
   `python scripts/montar_dossie.py --perimetro ./dossie/perimetro.geojson
   --nome "Fazenda Exemplo" --uso uso.txt --cobertura cobertura.txt --prodes
   prodes.txt --relevo relevo.txt --restricoes restricoes.txt --solo solo.txt
   --imagem imagem.txt --car ./dossie/car.json --car-temas
   ./dossie/car-temas.geojson --saida ./dossie --png`
   Sem CAR, tire `--car` e `--car-temas` e informe `--municipio "Cidade/UF"`.
6. **Leia a saída do script.** "conferências de soma: tudo fechou" = pode
   entregar. Qualquer aviso de soma ou de "não li": compare o arquivo com o
   texto da ferramenta, corrija a cópia e rode de novo. Não entregue dossiê
   com aviso de conferência sem dizer ao usuário qual é. A linha "figuras:"
   diz se os mapas entraram (passo 8).
7. **Entregue** o `dossie.pdf` (mostre no chat as páginas em PNG), o
   `dossie_tabelas.csv` e lembre que os arquivos das ferramentas (mapas,
   GeoPackage, GeoTIFF, curvas de nível) têm link de 1 hora: o usuário precisa
   baixar na hora.
8. **Figuras**: o script baixa sozinho, pelos links dos textos, os mapas das
   ferramentas e a imagem de satélite (que vem em GeoTIFF e ele converte em
   figura), e põe cada um numa página. Não peça nada ao usuário antes de
   tentar.
   - Saiu "figuras: N arquivo(s) baixado(s)": está pronto.
   - Saiu "não consegui baixar": o ambiente de código não tem internet (é o
     padrão na sandbox do chat) ou os links venceram. Entregue o dossiê como
     saiu e ofereça o complemento: o usuário baixa os arquivos pelos links,
     envia no chat, você os põe numa pasta e roda de novo com
     `--figuras ./figuras`. O script reconhece pelo nome: `rgb_AAAA-MM-DD.tif`,
     `uso_solo_situacao`, `uso_solo_mapas`, `uso_solo_historico`,
     `cobertura_classes`, `cobertura_confianca`, `prodes_deter`,
     `relevo_altitude`, `relevo_declividade`, `restricoes`,
     `solo_textura_carbono`.
   - Outra imagem entra com `--figura "Legenda=arquivo.png"`. É assim que
     entra a imagem de 2 m da `imagem_cbers`, se o usuário quiser:
     `--figura "Imagem de 2 m (CBERS-4A, INPE), cena de DD/MM/AAAA=arquivo.png"`.

## O dossiê pronto pelo conector (`dossie_pdf`)

A ClaudIA Sat também tem a ferramenta `dossie_pdf`, que monta no servidor um
dossiê com estas mesmas seções a partir do número do CAR, de um perímetro ou
de uma fazenda salva, em menos de um minuto, já com os mapas. Se ela aparecer
no conector do usuário, **conte que existem os dois caminhos e deixe ele
escolher**:

- `dossie_pdf`: mais rápido, uma chamada só, não depende de internet no
  ambiente de código.
- esta skill: entrega também as tabelas em CSV e os números em JSON, aceita
  figuras do usuário, tem o tema escuro e funciona quando só algumas
  ferramentas estão disponíveis.

As regras de "só fatos" valem igual para os dois. Não cole página de um no
outro.

## O que sai no PDF

| Página | Conteúdo | Fonte |
|---|---|---|
| Identificação | nome, município, CAR, área, contorno do perímetro, como ler | perímetro e CAR |
| CAR | situação do cadastro, condição da análise, datas, sobreposições informadas, áreas declaradas e o mapa delas | SICAR |
| Uso do solo | classes do último mapa e tabela das datas-marco | MapBiomas |
| Datas-marco | situação de cada área, área aberta depois de 2008, 2019 e 2020, ano da abertura | MapBiomas |
| Cobertura recente | classes dos últimos 12 meses (10 m), probabilidade de cada uma e a 2ª mais provável | Dynamic World |
| PRODES e DETER | polígonos por período, frente ao mínimo da nota do MMA, alertas | INPE |
| Declarado × observado | área, vegetação nativa e uso anterior a 2008: os dois números e a diferença | SICAR e MapBiomas |
| Relevo | altitude, declive, classes da Embrapa, faixas de mecanização | modelo de terreno de 30 m |
| Restrições | o que o perímetro sobrepõe e o que fica perto, com a data de cada base; termos de embargo pelo número | CNUC (MMA), FUNAI, IBAMA e ICMBio |
| Solo | argila, areia, silte, textura e carbono por profundidade, estoque de carbono de 0–30 cm e a faixa do próprio modelo | SoilGrids 2.0 (ISRIC) |
| Figuras | a imagem de satélite e os mapas das ferramentas, uma por página | a da figura |
| Fontes e limites | cada fonte, datas, limites e as observações da montagem | — |

Bloco sem dado não aparece: sem CAR não há as páginas do CAR nem a comparação;
sem o texto de uma ferramenta, a seção dela não sai. Base de restrição que a
ferramenta não conseguiu ler sai como "base não lida", nunca como "nenhuma".

## Sigilo das fontes

Cite as fontes exatamente como as ferramentas mandam (MapBiomas Coleção N;
Dynamic World; PRODES e DETER do INPE; ANADEM/Copernicus DEM; CNUC (MMA),
FUNAI, IBAMA e ICMBio; SoilGrids 2.0 (ISRIC), licença CC BY 4.0; Sentinel-2).
Sobre como o dado
é processado, a única frase é: processado pelas ferramentas da comunidade
agrônomo10X (OagronomIA). Não deduza nem cite plataforma, biblioteca ou nuvem.

## Detalhes fixos

- O script **não interpreta**: organiza, desenha e confere somas (classes ×
  área, faixas "aberto" × total, áreas iguais entre as ferramentas, CAR × perímetro).
- As áreas do CAR são as que o SICAR informa por polígono; sem o campo, a área
  é calculada do polígono e a página diz isso.
- Temas do CAR se sobrepõem (reserva legal sobre vegetação nativa, APP sobre
  as duas). A tabela avisa para não somar.
- A imagem de satélite vem em GeoTIFF de 16 bits; `imagem_rgb.py` a lê e
  estica para virar figura. O dossiê também registra a data da cena.
- **Aparência**: o PDF segue o design system da casa, no tema claro de
  impressão (`--tema escuro` troca para o tema escuro da marca). As fontes do
  design system (Chakra Petch, Manrope, JetBrains Mono) só entram se estiverem
  instaladas ou numa pasta passada em `--fontes`; sem elas, o script usa as
  fontes padrão. Não altere cores nem acrescente logo por conta própria.
- `python scripts/montar_dossie.py --demo` monta um dossiê de exemplo com
  dados inventados, sem rede. `python scripts/<nome>.py` roda os testes de
  cada módulo (`car.py --teste`).
- A `monitorar_cobertura` (mudança da cobertura no tempo) não entra no dossiê:
  é acompanhamento, não retrato. Ofereça à parte se o usuário pedir.
- As restrições não cobrem territórios quilombolas, assentamentos, florestas
  públicas, embargos de órgãos estaduais nem a zona de amortecimento das
  unidades; a página diz isso. Se o usuário pedir, diga que o dossiê não
  cobre; não busque por conta própria.
- A página de restrições lista até 12 unidades, 12 terras e 15 termos (é o
  que o texto da ferramenta traz); o GeoPackage da ferramenta tem todos.
- Formato dos textos lidos e o que cada conferência faz: `references/dados.md`.
- Fontes, datas-marco e limites: `references/fontes.md`.
