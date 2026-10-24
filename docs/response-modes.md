# Modos do chat livre

Implementação local em 23/10/2026. A escolha controla a abrangência das fontes;
o texto do pedido continua controlando o detalhamento da resposta.

| Modo | Compromisso | Limite |
| --- | --- | --- |
| Rápido | Um guia principal, preservando as etapas, locais alternativos e imagens disponíveis nele. Prioriza velocidade. | Pode citar pré-requisitos sem desenvolver procedimentos de outros guias. |
| Completo | Consulta os guias relevantes e suas dependências, na ordem de execução. | Pode gerar mais texto e demorar mais; não significa incluir todos os arquivos do mapa. |

Rápido é o padrão. A última escolha fica em `localStorage`, chave
`krono.responseMode.v1`, no mesmo navegador/origem. Limpar conversa não a altera.
Se o armazenamento estiver indisponível, a escolha funciona durante a sessão.
A interface oferece português e inglês, enquanto a geração mantém o suporte
multilíngue existente. Não há troca automática de modo por causa do texto do pedido.

Resumo e detalhamento são independentes do seletor:

- “Resuma o EE” em Completo integra os pré-requisitos em um roteiro curto.
- “Escudo sem resumir” em Rápido desenvolve todas as peças e locais do guia escolhido.
- “EE sem resumir” em Rápido desenvolve as fases do guia principal, sem expandir
  as receitas externas de equipamentos. A oferta permite solicitar a abrangência maior.
- Perguntas pontuais continuam recebendo uma resposta direta.

## Seleção e entrega

`ChatRequest.response_mode` aceita `quick` ou `complete`, com padrão `quick` também
para clientes da API. Clientes antigos que precisam da abrangência anterior devem
enviar `complete`. Os scripts de comparação de gerações/auditoria fazem isso
explicitamente para manter o escopo dos experimentos anteriores.

No Rápido, `single_guide` restringe a recuperação ao guia relevante. A expansão
dentro do arquivo mantém o procedimento completo quando solicitado. Para fontes
com relações revisadas, `quick_procedure` usa o grafo local para ordenar o objetivo,
preservar condições, excluir tópicos estranhos e reunir fotografias de apoio do
mesmo arquivo. Dependências externas e suas imagens ficam fora do contexto de
geração; essa rota não faz chamada ao modelo para planejar múltiplos guias.
Guias sem relações revisadas usam a expansão dentro do arquivo já existente.

No Completo, a orquestração de múltiplos guias permanece como antes. Os dois modos
reutilizam contratos de detalhamento, validação/correção, vinculação local de imagens,
geração em lotes quando necessário, entrega integral, andamento e cancelamento.
Um guia extenso ainda pode demandar mais de uma chamada. Não há promessa de segundos
fixos ou de que toda consulta Rápida será mais veloz que qualquer consulta Completa.

Quando o grafo identifica fontes relacionadas externas ou o pedido combina vários
objetivos, `ChatResponse.offer_complete` permite mostrar a oferta discreta após a
resposta Rápida. “Usar Completo” seleciona e salva o modo e repete o mesmo pedido,
preservando o contexto. A oferta não dispara outra geração sem o clique.

O acompanhante mantém sua própria seleção por etapa e dependências. O seletor fica
no compositor do chat comum; não altera a partida salva nem seus objetivos. As ações
legadas de acompanhamento também preservam sua abrangência anterior.

## Validação

Suíte completa: **406 testes passando** (109,92 s). Ruff e sintaxe JavaScript
sem erros. Testes automatizados sem chamadas pagas; testes reais somente locais.

Testes cobrem escopo por arquivo versus múltiplos guias, nove fases do EE em resumo
e detalhado, escudo com nove fotos e locais alternativos em português/inglês,
Pack-a-Punch sem tópicos estranhos, vários objetivos, padrão/valores inválidos e
compatibilidade do acompanhamento. Os testes anteriores de múltiplos guias agora
selecionam `complete` explicitamente; suas exigências de ordem/imagens permanecem.

No navegador, com OpenRouter real, o Pack-a-Punch de Zetsubou em Rápido usou um guia
com suas imagens. O clique em Completo incluiu um segundo guia de baldes e água,
com as imagens correspondentes. As duas escolhas persistiram após recarregar.
O seletor foi conferido em desktop e em 390 × 844, sem rolagem horizontal.
Nenhum teste de modelo desta etapa utilizou a cota gratuita da Groq.

Essa validação não é uma nova comparação estatística de latência nem comprova
completude factual de toda resposta. Os limites de interpretação e conteúdo
registrados nos relatórios anteriores continuam aplicáveis.
