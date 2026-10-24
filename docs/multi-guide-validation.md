# Multi-guias: validação local

Registro de 21/10/2026. Sem push ou deploy. Frontend e persistência do estado
da partida continuam fora desta etapa.

Atualização de latência: a auditoria por modelo foi desativada por padrão após
o experimento solicitado pelo usuário. Foram oito execuções A/B reais, mantendo
multi-guias e imagens, mais 292 testes automatizados (91,94% de cobertura).
Resultados, variação entre rodadas e ressalvas de conteúdo em
[audit-latency-comparison.md](audit-latency-comparison.md). Os registros anteriores
abaixo descrevem as etapas realizadas com auditoria ativa.

## Resultado técnico

- Suíte após a correção do transporte do navegador: **289 testes aprovados**,
  cobertura **91,77%**, acima do mínimo de 90% (rodadas anteriores: 281 / 91,82%
  e 284 / 91,73%). As instruções finais de concisão também passaram nos testes
  específicos de prompt e política de resposta.
- Catálogo de execução: 605 seções. Índice revisado: 110 seções, 30 relações,
  37 escopos de entrada, em 26 documentos. Não são 26 documentos integralmente
  certificados nem todos os objetivos dos 14 mapas revisados manualmente.
- Guias, imagens canônicas e índice de embeddings não foram reescritos.
- Servidor local verificado pelo endpoint real: saúde OK; pedido de escudo de
  Gorod retornou quatro blocos e dez imagens em aproximadamente 4,5 segundos.

Comandos de verificação, usando clientes simulados nos testes automatizados:

```powershell
$env:EMBEDDING_PROVIDER='none'
$env:GROQ_API_KEY='offline-test-placeholder'
python -m pytest -o addopts='' --cov=app --cov-report=term-missing --cov-fail-under=90 -q
python -m ruff check app scripts tests
python -m scripts.validate_dependencies
```

Os testes desativam o acesso pago antes da coleta. Sondagens reais foram
executadas separadamente com a credencial local de desenvolvimento.

## Comportamento implementado

O plano reúne objetivos explicitamente pedidos e seus requisitos transitivos.
Relações revisadas são resolvidas deterministicamente. As demais passam por
leitura integral das seções selecionadas, descoberta recursiva e validação de
evidências. Uma referência a equipamento resolve sua receita canônica, evitando
tratar a localização de uma peça como instrução completa de construção.

Resumo e resposta detalhada usam o mesmo conjunto necessário de fontes.
O resumo agrupa procedimentos adjacentes e explica condições essenciais; a
resposta detalhada desenvolve as seções e preserva os grupos completos de imagens.
Melhorias opcionais não se tornam requisitos somente por aparecerem no catálogo.

O JSON interno exige uma chave por seção ordenada; IDs e ordem são atribuídos
pelo servidor. Cada lote é conferido semanticamente contra suas próprias
fontes. O auditor não recebe o pedido global para cobrar objetivos de outro
lote, nem deve inventar dependências entre dois objetivos independentes.
Uma correção limitada e, quando cabível, subdivisão do lote recuperam falhas de
conteúdo. Falhas de conexão, autenticação e cota não são tratadas como JSON
inválido. A resposta só é entregue quando todos os lotes necessários terminam.

Foram acrescentadas notas revisadas para condições que os testes mostraram ser
fáceis de interpretar mal: os três desafios sorteados de cada jogador em
Zetsubou, a finalização compartilhada dos cajados de Origins e o título narrativo
“Secure the keys”, que não representa um conjunto adicional de chaves físicas.
As notas também acompanham fontes agrupadas no resumo.

## Sondagens reais durante o desenvolvimento

Modelo: `openai/gpt-oss-120b`, raciocínio baixo, pelo OpenRouter. Os testes diretos
usaram BM25; a verificação HTTP usou a configuração normal do servidor. As linhas
abaixo registram execuções aprovadas em momentos diferentes desta etapa, após
correções progressivas; não constituem benchmark de uma única revisão ou SLA.
Quantidades de blocos podem variar entre respostas válidas.

| Pedido | Resultado observado |
| --- | --- |
| Pack-a-Punch de Der Eisendrache | 3 blocos, 6 imagens |
| Pack-a-Punch de Shadows | 6 blocos, 17 imagens |
| Pack-a-Punch de Zetsubou | 11 blocos, 14 imagens |
| Escudo base de Gorod | 4 blocos, 10 imagens |
| Escudo + Pack-a-Punch de Shadows | 10 blocos, 26 imagens; ambos os objetivos cobertos |
| Origins completo | 23 blocos, 127 imagens |
| Origins resumido | 19 blocos, sem galeria |
| Origins com os quatro cajados declarados melhorados | 13 blocos, 44 imagens; sem repetir sua construção |
| Revelations completo | 23 blocos, 78 imagens; receita do Keeper e requisitos da arma incluídos |
| Revelations resumido | 15 blocos, sem galeria |
| Zetsubou completo, revisão final | 47 blocos, 76 imagens; 362 segundos, 14 chamadas, US$0,004035 |
| Zetsubou resumido, com notas sobre desafios | 19 blocos, sem galeria |

Uma repetição de Zetsubou completo após os últimos ajustes falhou por conexão
ao provedor, depois de correções de conteúdo. Esse resultado não foi contado
como aprovação. A nova execução da revisão final terminou com sucesso, incluindo
as fontes e seções obrigatórias, sem as atividades opcionais excluídas pela
matriz. O sucesso posterior não elimina a falha de disponibilidade observada.
Na inspeção da resposta final, os desafios foram descritos como três sorteados
por jogador e a eletrificação exigiu as recompensas e a conclusão de todos no
cooperativo. Ainda apareceram referências técnicas no corpo de alguns blocos;
a limpeza da apresentação continua no backlog do frontend.

Os testes revelaram problemas reais corrigidos: receitas parciais, fontes
obrigatórias omitidas ou fundidas, campos JSON inventados, requisitos cobrados
no lote errado e alternativas de desafios confundidas com obrigações cumulativas.

## Custos, disponibilidade e limites

As chamadas aprovadas registradas custaram aproximadamente US$0,0003 a US$0,0046
por pedido. EEs extensos levaram vários minutos em algumas execuções, incluindo
conferências e correções. Não extrapolar a latência do escudo para um EE completo.
Chamadas malsucedidas também podem consumir crédito. O log local de uso fica
em `.cache/llm-usage.jsonl`, ignorado pelo Git, sem chaves ou texto das conversas.
Na consulta durante o fechamento, o total utilizado na conta era aproximadamente
US$0,08 dos US$5, com cerca de US$4,92 restantes. A consulta pode preceder a
contabilização de chamadas ainda em andamento.

OpenRouter pago permanece exclusivo do desenvolvimento com opt-in explícito.
Produção mantém a Groq gratuita e a mensagem de esgotamento diário acordada.
Os tetos de preço unitário não representam um limite de gasto total da conta.

Nem a estrutura JSON nem a auditoria por modelo provam completude factual
absoluta. A qualidade da base, a interpretação de referências, a disponibilidade
do provedor e a variabilidade do modelo continuam sendo limites práticos.
Não houve deploy, teste de infraestrutura de produção ou revisão factual manual
integral de todos os guias.

## Correção após o relato de requisições pendentes no navegador

O feedback posterior mostrou uma lacuna na validação inicial: o HTTP real havia
sido testado com um escudo, enquanto os EEs longos eram sondados diretamente pelo
OpenRouter. O servidor normal usa Groq primeiro; o SDK repetia erros de limite
antes do fallback e cada lote voltava a experimentar a rota gratuita.

Correções locais:

- SDK sem retentativas automáticas antes de tratar HTTP 429.
- Fallback pago local imediato, com intervalo mínimo de 60 segundos antes de
  voltar a tentar Groq; `Retry-After` numérico é respeitado até uma hora.
- Prazo absoluto de 600 segundos por requisição HTTP, cancelando a geração e
  retornando HTTP 504 em português quando excedido. Não se entrega um guia parcial.
- Logs de início/término, duração e status, sem texto da pergunta ou credenciais.
- Produção continua sem fallback pago e com a mensagem de cota gratuita.

A suíte seguinte passou com 284 testes / 91,73%. Os testes novos verificam a
troca de provedor, o retorno à rota gratuita depois do intervalo e o cancelamento
efetivo de uma geração parada pelo prazo HTTP.

Validação com o servidor reiniciado, configuração normal e dois pedidos reais
pelo `/chat` (executados com sobreposição):

| Pedido | Resultado HTTP | Tempo do cliente |
| --- | --- | --- |
| “me de o passo a passo do ee de origins bem explicado, sem resumir”, sem mapa ativo | 200, modo completo, 23 blocos, 127 imagens, sem esclarecimento | 273,8 s |
| “Como faço o Easter Egg principal?”, com Zetsubou ativo | 200, roteiro, 19 blocos, 47 fontes, sem esclarecimento | 231,3 s |

A resposta de Origins também foi comparada aos caminhos e seções exigidos
pela matriz de completude. Pela interface real, uma pergunta de escudo de Gorod
terminou em 40,2 segundos no servidor; os blocos e imagens apareceram, o indicador
sumiu e o campo de envio voltou a funcionar. A latência varia: essa medição não
repete os 4,5 segundos do primeiro smoke de escudo.

Essas medições confirmam conclusão dos pedidos testados; não demonstram uma
experiência rápida. Os EEs ainda geram e conferem vários lotes sequenciais.
Redução de latência, feedback de progresso e cancelamento visível continuam
como melhorias, sem confundir o prazo de erro com otimização da geração.

## Reprodução no navegador e transporte assíncrono

Após novo relato, foi reproduzido na interface o caminho exato: clicar em
“Easter Egg principal”, receber a pergunta de mapa e escolher Origins. Uma
tentativa exibiu `Failed to fetch` enquanto ainda havia processamento no
servidor. Portanto, os êxitos pelo cliente HTTP com espera longa não demonstravam
conclusão no navegador. Também houve um EE de Shadows com HTTP 502 por falha
de conferência semântica; esses são problemas distintos.

O frontend agora usa jobs e consultas curtas de status, com resultado completo,
erros explícitos, cancelamento ao limpar a conversa e tempo de espera visível.
O endpoint síncrono é preservado para outros clientes. Limites de memória,
expiração e exigência de um worker estão em [chat-transport.md](chat-transport.md).

No primeiro teste do novo transporte pelo navegador interno, o roteiro de Origins
terminou em **156,8 segundos** no servidor; apareceram os 19 blocos, os controles
de roteiro e o campo de mensagem habilitado. Houve uma correção de cobertura e
subdivisão antes da conclusão. Esse teste antecedeu o último ajuste que dá mais
espaço aos procedimentos agrupados no resumo.

Com as instruções finais e o servidor atualizado, foi clicado “Ver guia completo”
nesse mesmo roteiro, preservando o histórico e o estado de navegação enviados
pelo navegador. A tarefa terminou em **169,2 segundos**, HTTP 200: **23 blocos e
127 imagens**. A resposta apareceu na interface com o painel “Guia completo” e
o campo de mensagem habilitado. Os caminhos e seções obrigatórios também foram
comparados à matriz `origins-full`, com aprovação. Nessa execução não houve
registro de correção semântica ou de schema. Isso é uma execução aprovada, não
uma garantia de que nenhuma chamada futura falhará.

O diagnóstico também identificou campos do exemplo JSON genérico dentro de
`OrderedAnswer`. Os formatos agora têm instruções de saída separadas. A auditoria
continua ativa e registra motivos de rejeição; nenhum resultado foi liberado
somente para contornar uma reprovação de conteúdo.

O usuário ofereceu o Chrome com perfil Rafael, mas a ferramenta listou somente
o navegador interno e MCP Apps e retornou “Browser is not available: chrome”.
Não houve acesso ao Chrome nem ao Firefox; a validação visual registrada foi
feita no navegador interno.

Também foi testado “Limpar conversa” com uma tarefa pendente na interface: o
compositor foi liberado imediatamente e o servidor confirmou cancelamento
(status interno 499, 4,6 segundos). Não houve mensagem de erro antiga inserida
depois da limpeza. O servidor temporário de diagnóstico foi encerrado; somente
o servidor local normal foi mantido.

## Próxima etapa

O usuário pode testar localmente resumo, guia completo, dois objetivos no mesmo
pedido e progresso explicitamente declarado. Depois desse retorno, alinhar a
arquitetura de estado da partida e continuidade. O redesign do frontend, PWA e
aplicativo desktop seguem no [backlog](backlog.md).
