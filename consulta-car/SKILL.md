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
# um CAR (imprime JSON com todos os campos)
python scripts/consultar_car.py "PI-2200053-1BAB.C06A.E224.43BC.A804.FFEC.51C2.5EB9"

# planilha: detecta a coluna do CAR pelo cabeçalho, PREENCHE só as células
# vazias e salva <nome>-preenchida.csv/.xlsx (colunas que faltarem são criadas)
python scripts/consultar_car.py fazendas.xlsx
python scripts/consultar_car.py lista.csv -o resultado.csv

# opções: --decimal (lat/long em graus decimais) · --sobrescrever (reconsulta tudo)
```

O leitor/escritor de XLSX é embutido (sem openpyxl): lê a primeira aba e
escreve um arquivo válido para Excel/Sheets. CSV aceita `;` ou `,`.
O script pausa 0,5 s entre consultas (gentileza com o servidor público) e
reporta linha a linha o que não encontrou ou está inválido.

## Caminho 2 — sem ambiente de execução com rede (chat)

Se você (IA) não puder rodar o script com acesso à internet, faça a
consulta VOCÊ MESMO com sua ferramenta de busca/fetch de URL: monte a URL
da API acima com o número normalizado (pode manter os pontos) e leia o
JSON. Para poucos CARs (até ~15), repita por número e monte a tabela na
resposta. Para planilhas grandes, oriente o usuário a rodar o script no
Claude Code/Cowork — iterar dezenas de fetches no chat é lento e sujeito a
limite.

## Caminho 3 — último recurso (navegador)

Com browser automation disponível e a API fora do ar: abra
https://consulta.car.gov.br/, preencha o campo **"Número de registro no
CAR"** (canto direito do bloco "Confira as áreas cadastradas"), clique em
**Buscar** e leia o bloco **"Dados do imóvel rural"** no fim da página
(município, UF, lat/long, área, módulos fiscais).

## Baixar o SHAPE do imóvel (feições) — fluxo assistido com captcha

O site também entrega um **zip com os shapefiles do cadastro** (perímetro
AREA_IMOVEL + demais feições declaradas), mas o download é protegido por
**reCAPTCHA — e captcha é para HUMANO resolver**. A skill automatiza tudo
ao redor e devolve o clique ao usuário:

1. Precisa de **browser automation** (Claude Code com Playwright/Chrome,
   Cowork com navegador). Sem navegador, oriente o usuário a baixar
   manualmente no site e siga do passo 5.
2. Abra https://consulta.car.gov.br/, preencha o **"Número de registro no
   CAR"**, clique **Buscar** e aguarde o painel "Detalhes da pesquisa".
3. Clique **"Baixar feições"** (há também "Baixar demonstrativo", o PDF).
   Um reCAPTCHA "Não sou um robô" aparece no próprio painel.
4. **PARE e peça ao usuário**: "clique no 'Não sou um robô' (e resolva as
   imagens, se pedir) — eu continuo daqui". NUNCA tente resolver, burlar ou
   automatizar o captcha — nem com serviços externos; é a proteção do site
   e a skill respeita.
5. Com o zip baixado, rode `scripts/feicoes.py <arquivo>.zip`: ele extrai,
   lista os temas (tipo de geometria, nº de registros, bbox) e aponta o
   perímetro (AREA_IMOVEL) — pronto para o QGIS e para a skill
   `krigagem-solo` (entrada de perímetro).
6. Em lote, o captcha limita o ritmo por natureza (1 clique por imóvel) —
   combine com o usuário quais imóveis valem o download em vez de
   atropelar.

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
