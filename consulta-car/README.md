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
- **Download do shape (feições)**: fluxo assistido em que a IA navega até o
  botão "Baixar feições" e o **usuário resolve o reCAPTCHA** (a skill nunca
  burla captcha); `scripts/feicoes.py` extrai o zip, resume os temas e
  aponta o perímetro — pronto para o QGIS e para a skill `krigagem-solo`.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue (3 caminhos: script →
  fetch direto da API → navegador) + regras de resposta e limites.
- `scripts/consultar_car.py` — CLI: `python consultar_car.py <CAR>` ou
  `python consultar_car.py planilha.xlsx` (`--decimal` para lat/long em
  graus decimais, `--sobrescrever` para reconsultar tudo).
- `scripts/feicoes.py` — extrai e resume o zip de feições baixado do site
  (temas, geometria, bbox, perímetro AREA_IMOVEL).
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
