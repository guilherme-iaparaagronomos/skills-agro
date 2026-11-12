---
name: dossie-uso-ocupacao-solo
description: >-
  Monta o dossiê de uso e ocupação do solo de um imóvel rural em PDF, só com
  fatos e a fonte de cada um. Reúne o uso do solo de 1985 a hoje e a situação
  frente às datas-marco de 2008, 2019 e 2020 (MapBiomas), a supressão mapeada
  pelo INPE (PRODES e DETER), o relevo e, quando há o número do CAR, o que o
  cadastro declara (situação, reserva legal, vegetação nativa, área
  consolidada, APP) ao lado do que os mapas mostram. Parte do número do CAR
  (busca o perímetro no SICAR), de um arquivo de perímetro ou de uma fazenda
  salva. Usa o conector ClaudIA Sat. Não avalia nem recomenda. Acione com
  "dossiê do imóvel", "uso e ocupação do solo", "histórico de uso da fazenda",
  "o que tinha aqui em 2008", "levantamento do CAR" ou quando o usuário trouxer
  um CAR ou um perímetro pedindo o histórico da área.
---

# Dossiê de uso e ocupação do solo

Junta num PDF o que bases públicas e mapeamentos por satélite registram sobre
um imóvel: uso do solo ano a ano, datas-marco, PRODES e DETER, relevo e as
declarações do CAR. Cada número sai com a fonte e o ano.

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

## O que precisa estar disponível

- **Conector ClaudIA Sat** (comunidade agrônomo10X) ligado na IA: é ele que
  devolve uso do solo, PRODES, relevo e imagem. Sem ele não há dossiê: avise o
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
   - `prodes_fazenda`;
   - `relevo_fazenda`;
   - `imagem_satelite` (produto `rgb`) — só para registrar a data da cena mais
     recente sem nuvem.
   As três primeiras consomem hectares da franquia do usuário: avise antes.
4. **Grave o texto de cada ferramenta num arquivo, COMO VEIO**: `uso.txt`,
   `prodes.txt`, `relevo.txt`, `imagem.txt`. Copie o texto inteiro, sem
   resumir, reordenar, traduzir nem arredondar. O script lê os números desse
   texto e confere as somas; um número trocado na cópia aparece como aviso.
   Os links podem ficar ou sair, tanto faz.
5. **Monte**:
   `python scripts/montar_dossie.py --perimetro ./dossie/perimetro.geojson
   --nome "Fazenda Exemplo" --uso uso.txt --prodes prodes.txt --relevo
   relevo.txt --imagem imagem.txt --car ./dossie/car.json --car-temas
   ./dossie/car-temas.geojson --saida ./dossie --png`
   Sem CAR, tire `--car` e `--car-temas` e informe `--municipio "Cidade/UF"`.
6. **Leia a saída do script.** "conferências de soma: tudo fechou" = pode
   entregar. Qualquer aviso de soma ou de "não li": compare o arquivo com o
   texto da ferramenta, corrija a cópia e rode de novo. Não entregue dossiê
   com aviso de conferência sem dizer ao usuário qual é.
7. **Entregue** o `dossie.pdf` (mostre no chat as páginas em PNG), o
   `dossie_tabelas.csv` e lembre que os arquivos das ferramentas (mapas,
   GeoPackage, GeoTIFF, curvas de nível) têm link de 1 hora: o usuário precisa
   baixar na hora.
8. **Figuras** (opcional): os mapas que as ferramentas geram entram no dossiê
   se o usuário baixar os PNG e enviar no chat. Ponha-os numa pasta e rode de
   novo com `--figuras ./figuras`. O script reconhece pelo nome:
   `uso_solo_situacao`, `uso_solo_mapas`, `uso_solo_historico`, `prodes_deter`,
   `relevo_altitude`, `relevo_declividade`. Outra imagem entra com
   `--figura "Legenda=arquivo.png"`.

## O que sai no PDF

| Página | Conteúdo | Fonte |
|---|---|---|
| Identificação | nome, município, CAR, área, contorno do perímetro, como ler | perímetro e CAR |
| CAR | situação do cadastro, condição da análise, datas, sobreposições informadas, áreas declaradas e o mapa delas | SICAR |
| Uso do solo | classes do último mapa e tabela das datas-marco | MapBiomas |
| Datas-marco | situação de cada área, área aberta depois de 2008, 2019 e 2020, ano da abertura | MapBiomas |
| PRODES e DETER | polígonos por período, frente ao mínimo da nota do MMA, alertas | INPE |
| Declarado × observado | área, vegetação nativa e uso anterior a 2008: os dois números e a diferença | SICAR e MapBiomas |
| Relevo | altitude, declive, classes da Embrapa, faixas de mecanização | modelo de terreno de 30 m |
| Figuras | os mapas enviados | a da figura |
| Fontes e limites | cada fonte, datas, limites e as observações da montagem | — |

Bloco sem dado não aparece: sem CAR não há as páginas do CAR nem a comparação.

## Sigilo das fontes

Cite as fontes exatamente como as ferramentas mandam (MapBiomas Coleção N;
PRODES e DETER do INPE; ANADEM/Copernicus DEM; Sentinel-2). Sobre como o dado
é processado, a única frase é: processado pelas ferramentas da comunidade
agrônomo10X (OagronomIA). Não deduza nem cite plataforma, biblioteca ou nuvem.

## Detalhes fixos

- O script **não interpreta**: organiza, desenha e confere somas (classes ×
  área, faixas "aberto" × total, áreas iguais entre as ferramentas, CAR × perímetro).
- As áreas do CAR são as que o SICAR informa por polígono; sem o campo, a área
  é calculada do polígono e a página diz isso.
- Temas do CAR se sobrepõem (reserva legal sobre vegetação nativa, APP sobre
  as duas). A tabela avisa para não somar.
- A imagem de satélite vem em GeoTIFF para o QGIS e não entra como figura; o
  dossiê registra a data da cena.
- `python scripts/montar_dossie.py --demo` monta um dossiê de exemplo com
  dados inventados, sem rede. `python scripts/<nome>.py` roda os testes de
  cada módulo (`car.py --teste`).
- Formato dos textos lidos e o que cada conferência faz: `references/dados.md`.
- Fontes, datas-marco e limites: `references/fontes.md`.
