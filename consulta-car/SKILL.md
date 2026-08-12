---
name: consulta-car
description: >-
  Consulta pública do CAR (Cadastro Ambiental Rural / SICAR): a partir do
  número de registro, traz município, estado, latitude, longitude, área do
  imóvel, módulos fiscais e data de cadastro — direto da base oficial
  (consulta.car.gov.br). Funciona com UM número no chat ou com uma PLANILHA
  (CSV/XLSX) de vários CARs, preenchendo as colunas faltantes e devolvendo a
  planilha completa. Acione com "consultar CAR", "dados do CAR", "SICAR",
  "preencher planilha de CAR" ou quando o usuário colar um número no formato
  UF-1234567-XXXX.XXXX...
---

# Consulta CAR — dados do imóvel rural pelo número de registro

Recebe um número de CAR (ou uma planilha cheia deles) e devolve os dados
públicos do imóvel na base oficial do SICAR: **município, estado, latitude,
longitude, área (ha), módulos fiscais e data de cadastro**.

## Como funciona por baixo

O portal https://consulta.car.gov.br/ expõe a consulta numa API pública
simples — a MESMA chamada que o site faz ao clicar em "Buscar":

```
GET https://consulta.car.gov.br/api/totalizer/getDeatilsByIdentifier/<NUMERO>
```

- Atenção ao endpoint: é `getDeatilsByIdentifier` mesmo (typo oficial).
- Aceita o número **com ou sem pontos** (`PI-2200053-1BAB.C06A...` ou
  `PI-2200053-1BABC06A...`). Sem captcha, sem token.
- Resposta: JSON com `nameCity`, `nameState`, `idState`, `latitude` e
  `longitude` (em graus/min/seg, ex.: `8°22'26.947"S`), `haRegisteredArea`,
  `fiscalModules`, `createdAt` e `bounderBox` (retângulo WKT do imóvel).
- **CAR inexistente responde 200 com corpo VAZIO** — trate como "não
  encontrado", não como erro.
- Formato válido do número: `UF-CCCCCCC-HHHHHHHH...` (UF, 7 dígitos do
  código IBGE do município, 32 caracteres hexadecimais).

## Caminho 1 — script (Claude Code, Cowork e qualquer ambiente com Python)

Use `scripts/consultar_car.py` (só biblioteca padrão, Python 3.9+, precisa
de internet):

```bash
# um CAR: imprime o JSON com todos os campos E JÁ SALVA o perímetro em
# <CAR>.geojson (não precisa pedir o shape num 2º passo)
python scripts/consultar_car.py "PI-2200053-1BAB.C06A.E224.43BC.A804.FFEC.51C2.5EB9"

# planilha: detecta a coluna do CAR pelo cabeçalho, PREENCHE só as células
# vazias e salva <nome>-preenchida.csv/.xlsx (colunas que faltarem são criadas)
python scripts/consultar_car.py fazendas.xlsx
python scripts/consultar_car.py lista.csv -o resultado.csv

# opções: --decimal (lat/long decimais) · --sobrescrever (reconsulta tudo)
#         --sem-feicao (não baixar o perímetro na consulta de 1 CAR)
```

**ENTREGUE O SHAPE JUNTO, não ofereça.** Ao consultar **um** CAR, o script
já salva o perímetro (`feicao_geojson` no JSON) — apresente os dados E
entregue o arquivo GeoJSON ao usuário na mesma resposta. Não pergunte "quer
o shape?": traga. (Só pule com `--sem-feicao`, ou quando o usuário disser
que não quer.) Para **planilha** de vários CARs, o script NÃO baixa um shape
por linha (seria pesado) — aí sim confirme com o usuário quais imóveis
devem ter o perímetro baixado (via `baixar_feicao.py`).

O leitor/escritor de XLSX é embutido (sem openpyxl): lê a primeira aba e
escreve um arquivo válido para Excel/Sheets. CSV aceita `;` ou `,`.
O script pausa 0,5 s entre consultas (gentileza com o servidor público) e
reporta linha a linha o que não encontrou ou está inválido.

## Caminho 2 — ambiente sem internet (sandbox do chat)

A sandbox de código do **chat (claude.ai)** só alcança uma lista fechada de
hosts (pypi, github…); `consulta.car.gov.br` NÃO está nela, então o script
recebe **`403 host_not_allowed`** e o fetch de URL também falha. Isso é
limite do ambiente, não da skill — e ela trata assim:

1. **Preenchimento OFFLINE (sempre roda)**: o código IBGE do município está
   embutido no número do CAR (os 7 dígitos após a UF). Com
   `references/municipios_ibge.tsv` (5.571 municípios), o script preenche
   **município, estado e UF sem tocar a rede** — e marca a linha como
   PARCIAL. Só latitude, longitude, área e módulos fiscais exigem a API.
2. Se você (IA) TIVER uma ferramenta de fetch que alcance o site (algumas
   alcançam mesmo com a sandbox bloqueada), monte a URL da API com o número
   normalizado e leia o JSON — assim completa os campos que faltam. Para
   poucos CARs (até ~15).
3. Se nada alcançar o site, **diga ao usuário com todas as letras**: os
   dados geográficos só vêm da base oficial e este ambiente bloqueia o
   acesso — rode a skill no **Claude Code** ou no **Cowork** (internet
   real), onde ela funciona ponta a ponta. Não invente lat/long/área.

O script já faz tudo isso: em bloqueio ele preenche o que dá offline, avisa
o motivo e sai com código 3 (único) ou reporta "N PARCIAL(is)" (planilha).

## Caminho 3 — último recurso (navegador)

Com browser automation disponível e a API fora do ar: abra
https://consulta.car.gov.br/, preencha o campo **"Número de registro no
CAR"** (canto direito do bloco "Confira as áreas cadastradas"), clique em
**Buscar** e leia o bloco **"Dados do imóvel rural"** no fim da página
(município, UF, lat/long, área, módulos fiscais).

## Baixar a FEIÇÃO do imóvel (polígono) — SEM captcha, via WFS oficial

O botão "Baixar feições" do site empacota um shapefile atrás de um
reCAPTCHA, mas o MESMO dado geográfico está no **GeoServer público do
SICAR** — filtrável pelo código do imóvel numa requisição pública
legítima. É o **caminho preferido** (roda em qualquer ambiente com Python
e rede, sem clique nenhum):

```bash
# perímetro do imóvel em GeoJSON (SIRGAS 2000)
python scripts/baixar_feicao.py "PI-2200053-1BAB.C06A.E224.43BC.A804.FFEC.51C2.5EB9"

# com camadas temáticas do cadastro (reserva legal, vegetação nativa...)
python scripts/baixar_feicao.py <CAR> --temas arl_averbada,vegetacao_nativa
python scripts/baixar_feicao.py <CAR> --temas todos   # varre as comuns
```

Por baixo: `GET .../geoserver/consulta_publica/ows` (WFS 2.0, GetFeature,
`cql_filter=cod_imovel='<CAR>'`, `outputFormat=application/json`). A camada
`iru` é o perímetro; as demais (`arl_*`, `vegetacao_nativa`,
`area_consolidada`, `app_*` etc.) filtram pelo mesmo campo. O GeoJSON abre
direto no QGIS e serve de **perímetro para a skill `krigagem-solo`**.
Detalhes das camadas em `references/api-sicar.md`.

## Fallback — baixar o SHAPEFILE oficial pelo site (com captcha)

Só quando o usuário precisar do **pacote shapefile idêntico ao do site**
(ou o WFS estiver fora). Aí o download tem reCAPTCHA, que é **para HUMANO
resolver** — a skill NUNCA burla, resolve ou terceiriza captcha:

1. Requer navegador (Claude Code/Cowork). Abra o site, preencha o CAR,
   **Buscar**, e no painel "Detalhes" clique **"Baixar feições"**.
2. **PARE e peça ao usuário**: "clique no 'Não sou um robô' — eu sigo daqui".
3. Com o zip baixado, `scripts/feicoes.py <arquivo>.zip` extrai e resume os
   temas (geometria, registros, bbox) e aponta o perímetro AREA_IMOVEL.

## Regras de resposta

1. **Normalize antes de consultar**: maiúsculas, sem espaços; valide o
   formato (UF + 7 dígitos + 32 hex). Número mal formado → diga o que está
   errado em vez de consultar à toa.
2. **Planilha**: NUNCA sobrescreva célula já preenchida (padrão do script);
   preserve as colunas e a ordem do arquivo do usuário; colunas que não
   existirem (ex.: Módulos Fiscais) são acrescentadas ao final.
3. **Não encontrado ≠ erro**: informe quais números não existem na base e
   siga com os demais.
4. Ao apresentar resultado único, entregue os campos em lista limpa (como o
   site mostra) e ofereça o bounding box WKT se o usuário for plotar em GIS.
5. **Cite a fonte e a data**: "Consulta Pública do CAR (consulta.car.gov.br),
   consultado em <data>". Os dados são autodeclarados pelo proprietário no
   SICAR — situação cadastral e sobreposições NÃO vêm nesta consulta.
6. São dados PÚBLICOS do governo federal; ainda assim, não especule sobre o
   proprietário — a consulta não traz (nem deve trazer) dados pessoais.

## Limites conhecidos

- A API pública traz o RESUMO do imóvel — não traz situação do cadastro
  (ativo/pendente/cancelado), reserva legal, APP nem sobreposição; para
  isso o caminho é o demonstrativo completo no site com o proprietário.
- Latitude/longitude são o centroide declarado, em DMS; use `--decimal`
  para converter (S/W negativos).
- Base atualizada periodicamente pelo SICAR (a data aparece no rodapé do
  site) — pequenas divergências com o painel estadual são esperadas.
