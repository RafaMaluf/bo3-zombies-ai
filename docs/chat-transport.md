# Transporte e entrega das respostas

Atualizado em 22/10/2026. Geração paralela, entrega integral e andamento real.

## Decisão atual

A aplicação gera até quatro lotes simultaneamente, com roteiro e idioma comuns,
e fontes específicas para cada parte. Um pedido que cabe em um lote continua
fazendo uma geração. O servidor reúne os resultados na ordem do guia e só então
publica a resposta completa. O usuário preferiu essa entrega após testar blocos
progressivos. As imagens permanecem intercaladas no texto final.

Não há streaming de tokens, entrega parcial nem uma chamada adicional para unir
os resultados. Os limites de tamanho dos lotes e orçamento de chamadas continuam
ativos. Uma falha cancela as tarefas irmãs e impede a publicação de fragmentos.
Os contratos de JSON, fontes, ordem e substância mínima continuam ativos;
a auditoria semântica permanece desligada por padrão.

## Fluxo do navegador

1. `POST /chat/jobs` recebe `ChatRequest` e devolve HTTP 202 com ID aleatório,
   sem esperar pela geração.
2. `GET /chat/jobs/{id}` informa `pending`, `completed` ou `failed`, `phase` e
   `elapsed_seconds`. O navegador consulta a cada 1,5 segundo; cada chamada tem
   prazo de 20 segundos. Até três falhas transitórias consecutivas são toleradas.
3. Enquanto o job estiver pendente, `response` permanece nulo. O indicador mostra
   a operação real: entendimento, busca, planejamento, geração, conferência
   (somente se habilitada) ou finalização. Fases rápidas podem ocorrer entre
   consultas. Não há percentuais simulados ou frases alternadas por temporizador.
4. `completed` contém o `ChatResponse` inteiro. A interface apresenta uma mensagem
   com todos os blocos e suas imagens e atualiza o acompanhamento e o histórico.
5. `failed` preserva o status e a mensagem de erro, inclusive limite gratuito,
   JSON inválido ou prazo total excedido. Não contém um guia parcial.
6. “Cancelar resposta”, junto ao campo de mensagem, aborta a consulta e solicita
   `DELETE /chat/jobs/{id}`. O servidor cancela a tarefa e suas gerações ativas.
   Isso não garante estorno de tokens já processados pelo provedor.
7. “Limpar conversa” também cancela a requisição. Uma resposta antiga não pode
   reaparecer ou liberar os controles de uma requisição nova. Perguntas canceladas
   ou malsucedidas são removidas do histórico enviado ao modelo.

O tempo aparece após dez segundos. O navegador mantém prazo total de 660 segundos;
o servidor, 600 segundos. Suspender o computador pode atrasar temporizadores até
a retomada. `POST /chat` continua disponível com o contrato de resposta integral.

## Correções após o relato de Der Eisendrache

A requisição do usuário falhou com HTTP 502 após 20,4 segundos: o bloco agrupado
do arco Void excedeu a meta de 180 palavras mesmo depois de uma correção. A regra
de estilo estava sendo tratada como invalidade da resposta inteira. O resumo
agora recebe metas de palavras nas instruções, sem rejeição por ultrapassá-las.
Campos ausentes, referências desconhecidas, etapas ausentes, ordem incorreta e
conteúdo insuficiente continuam sendo motivos de rejeição. Isso não garante
que o modelo sempre produzirá um resumo tão curto quanto o desejado.

As imagens não haviam sido perdidas no navegador: o modo roteiro removia seus
vínculos antes da geração e novamente ao aplicar o plano multi-guias. Essa
supressão foi removida. Roteiros e guias completos agora preservam imagens dos
objetivos e pré-requisitos, incluindo grupos de locais alternativos. A montagem
das galerias é local; não depende de o modelo pedir IDs de imagens.

## Ciclo de vida

- Jobs vivem em memória, em um worker. Não são histórico persistente, estado da
  partida ou fila distribuída.
- Até quatro jobs ativos e 32 resultados retidos por processo; resultados
  terminados expiram após 15 minutos. Jobs ativos não são removidos para liberar
  espaço. Sem capacidade, o início retorna HTTP 429.
- IDs imprevisíveis; início e consulta usam `Cache-Control: no-store`.
- Reiniciar o app perde jobs. Uma consulta posterior recebe HTTP 404.
- Múltiplos workers/réplicas exigiriam armazenamento compartilhado ou afinidade.

## Verificação

Suíte offline: 355 testes passando; lint e sintaxe JavaScript sem erros.

Testes cobrem: lotes terminando fora de ordem sem exposição parcial; resultado
final com imagens e ordem preservadas; falha, cancelamento e timeout sem resposta
parcial; isolamento de fases entre requisições; capacidade e retenção; roteiro de
Der Eisendrache e Origins com imagens dos guias relacionados; resposta válida
acima da meta de palavras sem tentativa extra ou falha.

Na interface local, o pedido “Como faço o Easter Egg principal de Der Eisendrache?”
concluiu pelo OpenRouter em 30,4 segundos, com 26 blocos e 113 imagens, sem erro.
É uma verificação de integração, não uma garantia de tempo ou correção factual
para todo pedido. Os achados semânticos anteriores continuam registrados em
[generation-comparison-after-relations.md](generation-comparison-after-relations.md).

Sem push ou publicação. Desenvolvimento usa OpenRouter; a política de produção
para chaves gratuitas e esgotamento de cota permanece a mesma.
