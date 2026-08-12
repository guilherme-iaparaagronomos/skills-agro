# Consulta CAR

Skill que consulta a base pública oficial do **CAR (Cadastro Ambiental
Rural / SICAR)** a partir do número de registro e devolve os dados do
imóvel: **município, estado, latitude, longitude, área (ha), módulos
fiscais e data de cadastro** — um número de cada vez no chat, ou uma
**planilha inteira (CSV/XLSX)** com as colunas faltantes preenchidas.

**O que ela faz:**

- Usa a **API pública do consulta.car.gov.br** (a mesma chamada que o site
  faz no botão "Buscar") — GET simples, sem captcha, aceitando o número com
  ou sem pontos.
- **Modo planilha**: detecta a coluna do CAR pelo cabeçalho, preenche SÓ as
  células vazias (nunca sobrescreve o que o usuário já tem), cria as
  colunas que faltarem e devolve `<nome>-preenchida.xlsx/.csv` com um
  relatório do que foi preenchido, não encontrado ou está inválido.
- Leitor e escritor de **XLSX embutidos** — o script roda com a biblioteca
  padrão do Python (3.9+), sem nenhuma dependência.
- Degrada com elegância: sem ambiente de execução com rede, o playbook
  instrui a IA a fazer o fetch da API diretamente; sem rede nenhuma, traz o
  passo a passo do site para navegação assistida.
- **Feição do imóvel (polígono) SEM captcha, nos 3 formatos**:
  `scripts/baixar_feicao.py` puxa o perímetro do WFS público do SICAR
  (filtro por `cod_imovel`) e entrega **GeoJSON + Shapefile + KML** — roda
  sozinho, sem clique, e ainda traz status/situação do cadastro e camadas
  temáticas (reserva legal, APP, vegetação nativa). Consultar 1 CAR já vem
  com os três arquivos juntos.
  Fallback: baixar o shapefile oficial pelo site (aí com reCAPTCHA que o
  **usuário** resolve — a skill nunca burla) e resumir com
  `scripts/feicoes.py`. Ambos entregam perímetro pronto para o QGIS e para
  a skill `krigagem-solo`.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue (3 caminhos: script →
  fetch direto da API → navegador) + regras de resposta e limites.
- `scripts/consultar_car.py` — CLI: `python consultar_car.py <CAR>` ou
  `python consultar_car.py planilha.xlsx` (`--decimal` para lat/long em
  graus decimais, `--sobrescrever` para reconsultar tudo).
- `scripts/baixar_feicao.py` — baixa o polígono do imóvel via WFS oficial,
  sem captcha, em **GeoJSON + Shapefile + KML** (`--temas` para camadas).
- `scripts/converter.py` — converte um GeoJSON em Shapefile (.zip) e KML em
  Python puro, sem GDAL (SIRGAS 2000).
- `scripts/feicoes.py` — fallback: extrai e resume o zip de shapefile
  baixado do site (temas, geometria, bbox, perímetro AREA_IMOVEL).
- `references/api-sicar.md` — detalhes do endpoint (campos da resposta,
  formato do número, comportamento de erro).

## Instalação

Baixe o `.zip` desta skill na [release `latest`](../../releases/tag/latest)
e instale no Claude (Configurações → Capacidades → Skills), ou aponte o
Claude Code para a pasta da skill.

## Limites

- A consulta pública traz o **resumo** do imóvel — situação do cadastro,
  reserva legal, APP e sobreposições não vêm nesta API.
- Dados autodeclarados no SICAR; cite sempre a fonte e a data da consulta.
