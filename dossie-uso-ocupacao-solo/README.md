# Dossiê de uso e ocupação do solo

Skill que monta, em PDF, o **dossiê de um imóvel rural só com fatos**: o que
bases públicas e mapeamentos por satélite registram sobre a área, cada número
com a fonte e o ano. Não avalia, não conclui e não recomenda.

**O que ela reúne:**

- **CAR** (pelo número): situação do cadastro, condição da análise,
  sobreposições informadas e as áreas declaradas de reserva legal, vegetação
  nativa, área consolidada e APP, com o mapa delas.
- **Uso do solo de 1985 a hoje** e a situação frente às datas-marco de 2008,
  2019 e 2020: o que é vegetação nativa, o uso que já existia e o que foi
  aberto depois de cada data, com o ano da abertura.
- **Cobertura do solo recente** (Dynamic World): as classes dos últimos 12
  meses, com pixel de 10 m e a probabilidade de cada uma.
- **PRODES e DETER** (INPE): polígonos de supressão por período, frente ao
  mínimo da nota do MMA, e os alertas.
- **Declarado no CAR × observado no mapeamento**: os dois números e a diferença.
- **Relevo**: altitude, declive, classes da Embrapa e faixas de mecanização.

Parte do **número do CAR** (a skill busca o perímetro no SICAR), de um
**arquivo de perímetro** ou de uma **fazenda salva** na conta.

## O que precisa

- O conector **ClaudIA Sat** da comunidade agrônomo10X ligado na sua IA: é
  dele que vêm o uso do solo, o PRODES, o relevo e a imagem.
- Para buscar o CAR pelo número e para os mapas entrarem sozinhos no PDF, um
  ambiente de código com internet (Claude Code, Cowork). Na sandbox do chat a
  internet costuma ser bloqueada: envie o arquivo do perímetro e, se quiser os
  mapas no dossiê, baixe-os pelos links e envie no chat.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue.
- `scripts/` — `car.py` (perímetro e declarações do CAR, só biblioteca
  padrão) · `leitura.py` (lê os números do texto das ferramentas e confere as
  somas) · `paginas.py` (as páginas do PDF, no design system da casa) ·
  `imagem_rgb.py` (lê o GeoTIFF da imagem de satélite e faz a figura) ·
  `montar_dossie.py` (pipeline CLI; baixa os mapas pelos links quando o
  ambiente tem internet) · `geometria.py` e `shapefile_min.py` (perímetro em
  KML, GeoJSON, shapefile ou WKT). Todos com testes embutidos; `python
  scripts/montar_dossie.py --demo` monta um dossiê de exemplo com dados
  inventados. Dependências: numpy e matplotlib.
- `references/fontes.md` — o que é cada fonte, as datas-marco e os limites.
- `references/dados.md` — o que o script lê e o que ele confere.

## Instalar

Baixe [`dossie-uso-ocupacao-solo.zip`](../../../releases/latest/download/dossie-uso-ocupacao-solo.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Avisos

O dossiê não é laudo, parecer nem análise de conformidade ambiental,
fundiária ou de crédito. Mapeamento por satélite tem erro de classificação, o
CAR é autodeclaratório e fontes públicas mudam: uma nova consulta pode trazer
números diferentes. A interpretação é do responsável técnico. Divergências ou
melhorias? Abra uma [issue](../../../issues/new/choose).
