# Skills Agro — agrônomo10X · OagronomIA

Catálogo aberto de **skills de agronomia no formato oficial de Skills do Claude**, mantido
pela equipe da comunidade [agrônomo10X](https://comunidade.agronomos.ia.br) (powered by
**OagronomIA**). Cada skill transforma uma fonte técnica oficial (boletim de recomendação,
manual de cultura, norma) em um pacote que a IA sabe **aplicar**: interpreta os dados,
roda os cálculos nos scripts e responde citando o quadro e a página da fonte.

**O catálogo cresce**: cada pasta na raiz é uma skill completa, com README próprio
contando o que ela faz, qual a fonte e como foi validada.

## Skills disponíveis

<!-- SKILLS:START -->
| Skill | O que faz | Baixar |
|---|---|---|
| [`5a-aproximacao-mg`](5a-aproximacao-mg/) | Recomendações para o uso de corretivos e fertilizantes em Minas Gerais (5ª Aproximação, CFSEMG, 1999). | [zip](../../releases/latest/download/5a-aproximacao-mg.zip) |
| [`boletim-100-sp`](boletim-100-sp/) | Recomendações de adubação e calagem para o Estado de São Paulo (Boletim 100, IAC). | [zip](../../releases/latest/download/boletim-100-sp.zip) |
| [`consulta-car`](consulta-car/) | Consulta pública do CAR (Cadastro Ambiental Rural / SICAR): a partir do número de registro, traz município, estado, latitude, longitude, área do imóvel, módulos fiscais e data de cadastro — direto da base oficial (consul | [zip](../../releases/latest/download/consulta-car.zip) |
| [`krigagem-solo`](krigagem-solo/) | Interpolação por krigagem ordinária de laudos de análise de solo georreferenciados. | [zip](../../releases/latest/download/krigagem-solo.zip) |
<!-- SKILLS:END -->

*Tabela e zips são gerados automaticamente a cada atualização — o link "zip" sempre
baixa a última versão da skill.*

## Como instalar no Claude

1. Baixe o `.zip` da skill (coluna "Baixar" acima, ou na página de
   [**Releases**](../../releases/latest)).
2. No **claude.ai**, abra **Configurações → Capacidades → Skills** e envie o `.zip`
   (*Upload skill*). Se usar Skills dentro de um **Projeto**, envie o `.zip` lá.
3. Ative a skill. Quando a conversa cair no assunto dela (ex.: um laudo de solo do
   estado que ela cobre), o Claude aciona a skill sozinho, roda os scripts e responde
   citando a fonte.

> Membros da comunidade agrônomo10X também baixam estas skills prontas no catálogo
> interno, em **Soluções → Skills**.

## Como cada skill é construída

Toda skill deste repositório segue a mesma anatomia:

1. **Fórmulas de recomendação → scripts** (a parte de maior risco). Transcritas das
   páginas de fórmulas da fonte e **validadas contra os exemplos resolvidos da própria
   publicação** — batem número a número. Rode qualquer script para ver os exemplos:
   `python scripts/<nome>.py`.
2. **Interpretação agronômica → referências.** As classes de interpretação da fonte
   viram arquivos em `references/`.
3. **Recomendações por cultura → referências.** As tabelas por cultura, incluindo os
   elementos além de NPK, parcelamento, época/modo e diagnose foliar.

O `SKILL.md` de cada pasta é o playbook que a IA lê: para que serve, para que **não**
serve, e o fluxo de trabalho na ordem certa. O `README.md` de cada pasta explica a
skill para humanos.

## Revisão e contribuições

**Ninguém altera o catálogo diretamente** — toda mudança passa pela revisão da equipe:

- Encontrou um número que diverge da fonte? Abra uma
  [issue de revisão técnica](../../issues/new/choose) citando o quadro/página — toda
  correção é validada contra a publicação original antes de entrar.
- Quer propor uma mudança pronta? Abra um Pull Request (veja
  [CONTRIBUTING.md](CONTRIBUTING.md)) — ele só entra após aprovação dos mantenedores.
- Ideia de skill nova (outro boletim estadual, manual de cultura)? Abra uma issue de
  sugestão dizendo qual fonte oficial ela operacionalizaria.

## Avisos importantes

- As saídas são **recomendações técnicas de referência**; a decisão final é sempre do
  **engenheiro agrônomo responsável (ART)**, considerando histórico da gleba, cultivar,
  clima e manejo.
- Cada skill declara **sua fonte e sua abrangência regional** no próprio README e no
  SKILL.md — fora desse contexto, use a referência adequada da sua região.
- Este repositório não reproduz as publicações originais — apenas operacionaliza suas
  recomendações, com citação da fonte. Os direitos das obras pertencem aos seus editores.

---

Feito pela equipe **agrônomo10X · OagronomIA** — IA aplicada à agronomia, do laudo à
recomendação. Conheça a comunidade: <https://comunidade.agronomos.ia.br>
