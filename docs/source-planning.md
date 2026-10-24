# Planejamento de fontes por objetivo

Implementação local com validação automatizada e sondagens reais. Nenhum push
ou deploy nesta etapa. Resultados e limites em [multi-guide-validation.md](multi-guide-validation.md).
O navegador consulta o processamento por chamadas curtas, conforme
[chat-transport.md](chat-transport.md); o endpoint síncrono original continua disponível.

## Resolução de completude

O contrato atualizado está em [dependency-contract.md](dependency-contract.md).
`assets/guide-dependencies.json` registra o catálogo derivado, fingerprints,
escopos de entrada e relações com evidência. A ampliação de 22/10/2026 leu os
166 Markdown dos 14 mapas e registra 196 relações, 192 escopos e cobertura de
relações em 601 de 609 fontes (incluindo dois recortes verificáveis). A cobertura
é por seção; a leitura não certifica completude factual de todos os guias.
Decisões, limites e lacunas estão em [relationship-review.md](relationship-review.md).

Escopos revisados usam resolução transitiva determinística antes da geração.
Perguntas sobre energia, teleporte e Pack-a-Punch podem usar escopos diferentes
mesmo quando o Markdown é compartilhado. Resumos agrupam apenas requisitos
adjacentes do mesmo documento e com a mesma condição, preservando fontes e ordem.
Uma cadeia de preparação agrupada mantém sua âncora externa, em vez de apontar
para uma seção que foi incorporada ao próprio bloco.

Condições acompanham os requisitos transitivos; rotas alternativas são `OR`.
Uma exigência incondicional prevalece sobre caminhos condicionais do mesmo item.
Enciclopédias de objetivos independentes mantêm seleção semântica; escolher um
arquivo não autoriza expandir todas as plantas, máscaras ou upgrades que ele contém.
Nomes de estados conhecidos e redirecionamentos usam escopos/destinos versionados.
Recortes literais podem fornecer locais/imagens sem importar uma missão inteira;
o fingerprint do pai e os limites de texto/imagens precisam permanecer válidos.

Nos demais escopos o plano inicial passa por inspeção integral das seções
selecionadas. Novos requisitos são lidos recursivamente em lotes (até quatro
seções/10.000 caracteres alvo, uma seção indivisível até 32.000 caracteres com
catálogo; até 48 rodadas/96 fontes). Evidências, referências e ciclos são
validados. Uma lacuna explicitamente encontrada não vira sucesso parcial.
Essas descobertas não recebem o status de relações revisadas do índice.

A descoberta cita intervalos de linhas: o servidor extrai a evidência literal.
Referências a fases principais futuras, recapitulações do mesmo documento,
recomendações e melhorias não exigidas não criam arestas obrigatórias. Um item
comum sem guia de obtenção continua sendo um requisito declarado; isso não
autoriza inventar sua obtenção nem substituir pelo guia de uma melhoria.
Uma lacuna só bloqueia quando há delegação explícita a um procedimento ausente.

Após identificar uma dependência de equipamento, o servidor resolve a receita
canônica inteira, incluindo peças, construção e estado de melhoria solicitado.
Uma referência geral a Pack-a-Punch usa o documento específico quando ele existe.
Isso evita aceitar um único trecho de localização como receita completa.
Objetivos explicitamente combinados e opções resolvidas de uma continuação
precisam aparecer todos no plano, sem perguntar qual arquivo usar.

`grouped_source_ids` representa procedimentos obrigatórios agrupados no resumo;
`supporting_ids` representa locais/imagens complementares. São papéis distintos.
As imagens e a proveniência dos dois conjuntos são preservadas. Estados concluídos
dispensam seus requisitos transitivos conhecidos, sem avançar fases principais.

Declarações explícitas de progresso do usuário podem dispensar procedimentos
concluídos. A extração exige citação literal do usuário; mensagens do assistente
não comprovam progresso. Isso não acrescenta persistência ao estado da partida.

A conferência semântica adicional por modelo está **desativada por padrão**,
conforme solicitado após a revisão de latência. `ENABLE_ANSWER_AUDIT=true` é
mantido para experimentos A/B explícitos. Esse modo compara cada lote às fontes,
pode regenerá-lo e conferi-lo novamente, aumentando chamadas e tempo de espera.
Quando habilitado, recebe somente as fontes, o contrato e os blocos do lote atual.

Sem essa auditoria, continuam ativos o JSON estrito, a validação de fontes,
cobertura estrutural de seções, ordem, limites e imagens por etapa. Essas
verificações não demonstram que cada detalhe factual foi explicado corretamente.
O planejamento multi-guias e a descoberta de dependências também permanecem.

Condições e alternativas continuam explícitas. Por exemplo, os desafios de
Zetsubou são os três sorteados para cada jogador; listar métodos possíveis
não significa exigir todos os desafios do catálogo. Notas editoriais revisadas
do índice esclarecem esse tipo de interpretação sem alterar o Markdown canônico.

Lotes ordenados usam internamente `OrderedAnswer`: cada seção tem uma chave
obrigatória própria. O servidor atribui os IDs e a ordem dos blocos. O JSON público
continua igual. O schema também é mostrado explicitamente ao modelo, além de ser
enviado ao provedor, para evitar respostas com nomes de campos inventados.
Após falha de conteúdo/cobertura, um lote com várias seções pode ser subdividido,
preservando nível de detalhe e roteiro global. O orçamento total é de 16 lotes
tentados, incluindo subdivisões. Falhas de autenticação, rede, cota ou configuração
não acionam essa recuperação. Nenhuma parte é enviada se a resposta inteira falhar.

Validação local do artefato: `python -m scripts.validate_dependencies`. Alterar
fontes/imagens exige revisar relações afetadas e seus fingerprints, sem atualizar
hashes cegamente. A matriz de aceite está em `tests/fixtures/guide_completeness.json`.

## Política de credenciais e cota

O acesso pago pelo OpenRouter é exclusivo do desenvolvimento local. Exige
simultaneamente `APP_ENV=development`, `LOCAL_OPENROUTER_ENABLED=true` e
`OPENROUTER_API_KEY`. A chave fica somente no `.env`, ignorado pelo Git e pelo
contexto de build Docker. O padrão é produção, que ignora a chave paga.
Docker e Compose também desativam explicitamente o acesso pago; Compose limpa
a chave mesmo se o `.env` local for reutilizado. Não copiar essa chave para produção.

Com `LOCAL_LLM_PROVIDER=groq`, a Groq continua principal e somente HTTP 429
aciona o fallback local, imediatamente, sem retentativas de transporte do SDK.
Após o limite, o cliente local evita novas chamadas à Groq por pelo menos 60
segundos (respeita `Retry-After` numérico até uma hora) e depois volta a tentá-la.
Esse intervalo só se aplica quando o fallback pago local está habilitado;
produção retorna o erro gratuito sem criar acesso pago.
Com `openrouter`, os testes locais usam diretamente
o mesmo `openai/gpt-oss-120b`. Nunca há fallback pago em produção. O OpenRouter
exige suporte aos parâmetros de JSON estrito e limita o preço por milhão de
tokens a US$0,06 de entrada e US$0,25 de saída; sem rota elegível, retorna erro.
O teto é de preço unitário, não de gasto total da conta. Cada chamada paga
limita a saída a 12.000 tokens, sem retentativas automáticas de transporte.
As rotas locais habilitadas são `deepinfra/bf16` e `crusoe/bf16`, nessa ordem,
com raciocínio baixo. O log registra também o provedor efetivo e os tokens de
raciocínio quando informados. Essa seleção não garante disponibilidade.

Tokens e custo efetivo informado pelo provedor são registrados em
`.cache/llm-usage.jsonl` no desenvolvimento. O registro não contém chaves,
perguntas ou respostas. Testes automatizados desativam o opt-in pago antes
da coleta e usam clientes simulados; somente as sondagens reais usam crédito.

Em produção, o esgotamento da cota diária gratuita deve informar:
“Infelizmente, usamos APIs gratuitas e o limite diário de uso foi atingido.
Tente novamente amanhã.” Limites temporários por minuto pedem uma espera
curta, sem afirmar que a cota diária acabou. As mensagens usam o fluxo de erro
já exibido no chat; esta alteração não publica nada em produção.

## Fluxo

1. Resolver mapa e contexto de conversa. Um objetivo explícito novo não depende
   do guia consultado anteriormente. Perguntas de mapa desconhecido continuam
   sendo tratadas antes do planejamento.
2. Recuperar fontes iniciais. Em procedimentos, criar um catálogo de **todas**
   as seções do mapa, com resumo do documento e indicação de imagens. Perguntas
   pontuais sem procedimento mantêm o caminho de recuperação existente.
3. Consultar referências locais por até dois saltos, usando nomes de documentos
   e termos distintivos de seções. Esses sinais só descobrem trechos para
   inspeção: uma menção lexical não torna um equipamento obrigatório. Os trechos
   de apoio são distribuídos entre documentos para evitar que um guia extenso
   esgote o orçamento antes dos demais.
4. Escopos revisados resolvem o `SourcePlan` localmente. Quando o objetivo precisa
   de seleção semântica, o modelo escolhe as seções e as relações revisadas são
   aplicadas depois, sem redescobrir as dependências já cobertas.
   O schema só permite etapas: o planejador não tem um campo para pedir ao
   jogador que escolha arquivos ou autorize fontes.
5. Validar referências do mapa, duplicatas, ordem das fases e evidências. Cada
   pré-requisito/recomendação tem uma citação literal de outra seção (`anchor_id`)
   e um passo de destino (`before_source_id`). Pré-requisitos aparecem antes do
   destino, o que também impede ciclos nas relações obrigatórias. A evidência
   pode estar num resumo de preparação sem obrigar a repeti-lo na resposta.
6. Restaurar o conteúdo **completo** das seções selecionadas. `supporting_ids`
   acrescentam descrições de locais e imagens à etapa correspondente, sem criar
   passos repetidos. Essas fontes também aparecem na proveniência da resposta.
7. Gerar lotes internos e reunir uma única resposta, com introdução única,
   blocos em ordem e grupos de imagens completos. Uma falha num lote posterior
   devolve erro, sem apresentar uma parte como se fosse o guia completo.

O mecanismo é compartilhado por todos os mapas; não há roteamento exclusivo
para os exemplos de Origins, Gorod ou Zetsubou. O resolvedor não altera guias nem imagens durante uma pergunta. A revisão editorial
separada pode atualizar MDs, vínculos e embeddings; veja [correções das fontes](source-corrections.md).

## Apresentação e acompanhamento

- Resumo: fases e pré-requisitos essenciais, com oferta de aprofundamento nos
  procedimentos longos. O roteiro guiado continua sem galeria.
- Detalhado: procedimentos obrigatórios e imagens das seções selecionadas.
- Recomendações: explicitamente opcionais, com descrição breve, inclusive em
  respostas detalhadas.
- Fase acompanhada: permite pré-requisitos externos da fase atual; não pode
  adicionar outra fase principal nem marcar progresso automaticamente.
- Pedido de Pack-a-Punch durante um EE sai do escopo daquela fase para responder
  ao novo objetivo. O estado guiado não é avançado por essa consulta.

## Limites e custo

- Catálogo e trechos de planejamento: `MAX_PLAN_CONTEXT_CHARS`, padrão 22.000.
  Os trechos podem ser abreviados **para seleção**, com marcação explícita;
  a geração usa o texto completo das fontes escolhidas.
- Até `MAX_PLAN_SOURCES` etapas (padrão 96).
- Geração: até oito seções ou cerca de 10.000 caracteres de fontes por lote,
  até 16 lotes. Uma seção indivisível pode exceder o tamanho alvo do lote.
- Cada chamada de planejamento/geração tem no máximo uma correção de conteúdo
  ou JSON. As tentativas de transporte do SDK continuam independentes.
- O planejamento recebe até 1.500 caracteres de contexto recente; a geração
  recebe as duas mensagens mais recentes, até 1.600 caracteres cada.
- O orçamento padrão de 36 imagens não corta planos: os grupos selecionados
  são preservados e imagens repetidas são removidas pelo servidor.
- Limites de capacidade retornam erro explícito. Limites do provedor podem
  impedir o atendimento; o fallback pago só existe no desenvolvimento opt-in,
  conforme a política de credenciais acima. Não há migração automática de modelo.
- A requisição HTTP inteira tem prazo `CHAT_TIMEOUT_SECONDS` (padrão 600 segundos),
  incluindo recuperação, planejamento, geração e conferência. Ao excedê-lo, a
  tarefa é cancelada e o endpoint retorna HTTP 504 com uma mensagem em português.
  Isso não abrevia nem entrega parcialmente um guia completo.
- Os logs do servidor registram início, término, status e duração de cada pedido
  com um identificador, sem texto das perguntas ou credenciais.

Uma pergunta simples de procedimento acrescenta uma chamada de planejamento.
Guias completos podem consumir vários lotes e mais cota. O limite antigo de
três arquivos deixa de bloquear a conversa; os limites agora são de capacidade.

## O que as validações não provam

Uma citação literal comprova que o trecho existe; não comprova sozinha que o
modelo classificou corretamente a relação nem que escolheu todos os requisitos.
Seleção, classificação e explicação ainda precisam de avaliações semânticas e
respostas reais. Não há promessa de que toda interação será factual e completa.

As sondagens reais incluíram Pack-a-Punch de Der Eisendrache, Shadows e
Zetsubou, escudo de Gorod, objetivos combinados e EEs completos de Origins,
Revelations e Zetsubou. Elas motivaram correções na seleção de receitas,
condições, JSON ordenado e escopo da auditoria. Uma repetição final de Zetsubou
teve erro de conexão; a repetição seguinte da revisão final passou com 47 blocos
e 76 imagens. O relatório de validação distingue essas execuções e seus limites.

Testes: `test_source_planning.py`, `test_planned_chat.py`, `test_llm_contract.py`,
`test_chat_blocks.py` e regressões de idioma, navegação e API.
