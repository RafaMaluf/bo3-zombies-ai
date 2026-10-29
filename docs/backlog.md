# Backlog do Krono

Atualizado em 29/10/2026.

## Incidente mobile e continuidade

Correções locais do teclado Safari/PWA e da continuação “onde pego a flecha?”
após o arco do lobo. Há regressões automatizadas e teste real OpenRouter;
validação do teclado em iPhone físico ainda pendente. Detalhes e limites em
[mobile-continuity-fixes.md](mobile-continuity-fixes.md). Sem publicação.

## Redesign Caderno de campo implementado localmente

Direção B aprovada, com gaveta recolhida no desktop e no mobile. Mapa discreto,
sem seletor permanente; histórico na gaveta e PDF no menu da conversa. Modos
compactos, fotos sem nomes técnicos visíveis e navegação na ampliação. Chat e
acompanhamento compartilham o visual. Validação: 21 testes frontend e inspeção
no navegador. Detalhes em [frontend-redesign.md](frontend-redesign.md).

Próximo: usuário experimentar a interface; depois PWA e desktop. Sem publicação.

## Histórico local e acompanhamento por conversa implementados

Conversas são salvas em IndexedDB, com reabertura, renomeação e exclusão manual.
Cada uma preserva seu acompanhamento; o término volta ao chat com transcrição e
resumo. Não há exclusão automática nem importação. A exportação abre uma prévia
com imagens e usa “Salvar como PDF” na impressão do navegador.

Validação: 406 testes Python, 17 testes de frontend e testes de navegador,
com leitura paginada de 30 mensagens. Arquitetura, medição e limites em
[local-history.md](local-history.md). Próximos pontos: usuário experimentar;
PWA e desktop continuam pendentes; redesign implementado conforme seção acima. Sem push ou publicação.

## Modos do chat livre implementados localmente

Seletor Rápido/Completo no compositor, padrão Rápido e preferência persistida.
Abrangência das fontes e detalhamento do pedido são independentes. Os dois mantêm
imagens e validação; a oferta de ampliar só repete o pedido após o clique.
O acompanhante mantém suas dependências por etapa. Contratos e validação em
[response-modes.md](response-modes.md). Suíte completa: 406 testes passando;
Ruff e sintaxe JavaScript sem erros. Sem push ou publicação.

## Acompanhante e estado da partida implementados localmente

O novo modo separado inclui convite no chat, preparação, overview curto das fases,
localização do progresso por texto livre, etapa com imagens, aprofundamento,
conclusão e avanço automático. Aceita várias conclusões fora de ordem, consultas
sem concluir, ajuda lateral e correções com confirmação quando afetam dependentes.
Uma partida é salva no navegador; falha/cancelamento de geração preserva o progresso.
O chat comum recebe o estado e permite consultar o que falta.

Validação: 397 testes passando, Ruff e sintaxe JavaScript sem erros; testes no
navegador com OpenRouter e falhas controladas. Plano e registro em
[companion-plan.md](companion-plan.md); contratos e limites em
[companion-architecture.md](companion-architecture.md).

Próximo passo: validação de uso pelo usuário. Sem push ou publicação.

## Estado atual: paralela, entrega integral e andamento real

As duas comparações, a ampliação de relações e a revisão das lacunas foram
concluídas localmente. A arquitetura escolhida gera até quatro lotes em paralelo
e entrega a resposta inteira ao final, preservando a ordem e as imagens por etapa.
Detalhes em [chat-transport.md](chat-transport.md).

A interface mostra fases reais e oferece cancelamento dedicado no compositor.
Após o teste com Der Eisendrache, o usuário preferiu abandonar a entrega
progressiva. Cancelamento ou falha não exibem fragmentos do guia. O texto e as imagens só são exibidos após a conclusão da geração; no novo
acompanhante, o progresso da partida é salvo antes de gerar a próxima explicação. Desenvolvimento usa OpenRouter,
com auditoria semântica desligada e sem push ou publicação.

Próximos pontos: usuário validar a experiência e os modos Rápido/Completo;
resolver os achados semânticos da comparação antes de
declarar completude factual. Cache de respostas não é prioridade. O estado da partida está implementado na versão local. Redesign geral,
PWA e desktop continuam pendentes.

Ainda precisam de atenção os trials sorteados descritos como lista obrigatória,
referências internas ocasionais no texto, repetição entre procedimentos e
traduções imprecisas. Os casos e trade-offs estão em
[generation-comparison-after-relations.md](generation-comparison-after-relations.md).

## Etapa atual: multi-guias implementado e testado localmente

A etapa de mensagens, JSON e imagens por etapa está implementada localmente.
Na validação anterior, foram 332 testes passando, com cobertura de 91,97%.
A comparação pós-revisão e as decisões de entrega posteriores estão registradas
nos relatórios e no transporte do chat. Isso não elimina a possibilidade de erro
factual do modelo. O usuário aprovou a melhoria das imagens do escudo e a
interação inicial do Easter Egg, mas fará mais testes antes da próxima etapa.

Sem push ou publicação. Depois dos testes iniciais, o usuário autorizou unir
a correção de mensagens à implementação de multi-guias, substituindo a ordem
anterior. A implementação local está descrita em [source-planning.md](source-planning.md).
Os testes de desenvolvimento usaram GPT-OSS 120B pelo OpenRouter, além de uma
verificação HTTP do servidor com sua configuração normal. Resultados,
repetições malsucedidas e limites estão no [relatório](multi-guide-validation.md).
O feedback abaixo fica registrado para o futuro redesign do frontend;
não representa mudanças de interface a executar agora.

### Retorno dos testes de Pack-a-Punch em 21/10

O usuário relatou falhas em Shadows e Zetsubou. Os registros locais confirmam
rejeições em Shadows e Der Eisendrache pelo contrato de quantidade de itens:
ele exige a mesma quantidade de marcadores de lista da fonte. Isso não prova
cobertura factual e pode rejeitar uma explicação que combine ações. A expansão
de Der Eisendrache também incluiu a seção de Wunderspheres, além do objetivo
de liberar Pack-a-Punch. A causa em Zetsubou ainda precisa ser reproduzida.

Os três mapas tiveram respostas reais de Pack-a-Punch no fluxo novo. A validação
de completude passou a comparar o conteúdo das fontes, em vez de exigir a mesma
quantidade de marcadores. Ver a
[proposta de arquitetura alinhada](multi-guide-design.md) e a documentação
da implementação. Não encerrar a validação operacional só com testes simulados.
O usuário esclareceu que as ações dentro do chat podem ficar como estão por
enquanto; o redesign continua adiado.

Após o relato de EEs pendentes, a correção funcional passou o navegador para
jobs com consultas curtas. O fluxo real de escolha de Origins → roteiro → guia
completo foi testado na interface; o guia completo terminou com 23 blocos e 127
imagens. A geração ainda leva minutos. Ver [transporte do chat](chat-transport.md).

## Frontend: imagens e apresentação

- Remover nomes de arquivos e identificadores internos das legendas visíveis.
  O jogador precisa reconhecer o local ou a peça pela imagem e pelo passo.
- Manter texto alternativo acessível e descritivo. Exibir uma legenda humana
  apenas quando trouxer contexto útil, sem repetir o nome técnico do arquivo.
- Preservar as imagens junto da explicação correspondente e os grupos completos
  de locais alternativos de cada peça.

Critério de aceite: uma resposta sobre o escudo mostra as peças e suas imagens
na ordem da execução, sem expor nomes de arquivos na interface.

## Frontend: acompanhamento opcional dentro do aplicativo

- Andamento real, entrega integral e cancelamento dedicado implementados.
  O redesign futuro pode refinar a apresentação desses recursos, preservando
  os blocos em ordem, as fases reais e as imagens junto das etapas.
- Revisar a organização e os rótulos das ações de roteiro, resumo e guia
  completo. Todas as opções devem apresentar o conteúdo dentro do aplicativo.
- Hoje as ações “Ver roteiro” e “Ver guia completo” já solicitam uma resposta
  no próprio chat. O redesign deve tornar esse comportamento evidente, sem
  sugerir que o usuário será levado a uma página externa de guia.
- Oferecer um modo acompanhado opcional: o usuário aceita começar, recebe a
  etapa atual e pode clicar em “Terminei” para receber a próxima.
- Permitir recusar ou encerrar esse modo e continuar conversando livremente.
  O acompanhamento não pode ser obrigatório nem impedir perguntas no chat.
- Definir a preservação do contexto ao entrar e sair do acompanhamento em
  conjunto com a futura arquitetura de estado da partida.
- Dar destaque à ação útil naquele momento e reduzir a quantidade de controles
  simultâneos, sem esconder o acesso ao resumo ou à explicação completa.

Critério de aceite: o jogador consegue fazer o EE pelo acompanhamento ou
somente pelo chat, consultar explicações e avançar sem sair do aplicativo.

## Frontend: desktop e mobile

- Projetar a navegação, o chat, os controles e as imagens para uso frequente
  tanto no computador quanto no celular.
- Validar leitura, toque, rolagem e imagens em telas estreitas e largas, inclusive
  em respostas longas e grupos de várias fotos.
- Refinar a aparência com o usuário na etapa dedicada ao frontend.

## Ordem acordada das próximas etapas

1. Usuário testar localmente o fluxo unificado de mensagens e multi-guias;
   implementação, testes automatizados e sondagens reais estão registrados.
   A existência de validação não garante disponibilidade do provedor nem acerto
   factual de toda resposta.
2. Estado da partida e continuidade: jogadores, objetivos concluídos, itens e
   fase atual, para contextualizar perguntas e acompanhamento.
3. Redesign do frontend com os requisitos registrados acima.
4. Avaliar PWA.
5. Planejar aplicativo desktop leve, com atalho e acesso durante o jogo.
   Avaliar Rust/Tauri e alternativas com medições de consumo e compatibilidade.

Antes de cada implementação, alinhar o comportamento e a arquitetura. A mudança
dos timeouts e das tentativas da Voyage continua adiada por escolha do usuário.


## Correções editoriais antes da segunda medição

Revisão externa das lacunas autorizada e executada em 22/10. MDs, vínculos de
imagens, notas de interpretação, relações e índice Voyage atualizados. Ver
[source-corrections.md](source-corrections.md) para fontes, decisões e limites.
A comparação pós-revisão foi concluída a pedido do usuário; tempos, custo e falhas
semânticas em [generation-comparison-after-relations.md](generation-comparison-after-relations.md).
A escolha posterior foi a geração paralela. A entrega progressiva foi testada
e substituída por entrega integral a pedido do usuário. Roteiros agora preservam
as imagens; metas de palavras orientam o resumo sem rejeitar respostas válidas.
Andamento real e cancelamento dedicado foram implementados nesta entrega.
Os modos Leve/Completo seguem para discussão futura.
