# Acompanhante de Easter Egg — escopo e retomada

Atualizado em 22/10/2026. Decisões de produto alinhadas com o usuário neste chat.
Este documento prepara a implementação; não significa que os recursos abaixo
estão implementados. Não iniciar uma implementação inteira só por ler este arquivo.

## Ponto de partida

- Último commit funcional: `20d694b`.
- Última suíte completa executada: 355 testes passando. Não representa uma nova
  execução de testes na preparação deste documento.
- Multi-guias, relações revisadas, JSON validado e imagens junto das etapas existem.
- Geração de até quatro lotes em paralelo; resposta inteira entregue ao final.
- Andamento real e cancelamento dedicado existem. Entrega progressiva foi retirada
  a pedido do usuário: não reintroduzir.
- O acompanhamento atual possui estado básico de jogadores, fase e conclusões.
  Ainda não é o estado completo de partida descrito abaixo.
- Redesign geral, modos de resposta, PWA e desktop ficam para etapas posteriores.

## Experiência acordada

1. Uma pergunta relacionada a EE recebe resposta normal e um convite discreto:
   experimentar o acompanhamento ou continuar no chat. Convite uma vez por
   conversa/mapa, respeitando a recusa.
2. Ao aceitar, a pessoa entra num modo próprio, informa jogadores (um significa
   solo) e recebe uma lista muito curta dos principais objetivos.
3. Ao final do overview, perguntar por texto se começarão do início ou já fizeram
   alguma parte. Aceitar descrições naturais, sem exigir números ou nomes exatos.
4. A tela do acompanhante destaca um objetivo, instruções executáveis e imagens
   junto do texto. Contém texto livre e duas ações principais: Explicar melhor
   e Terminei. Não recriar o painel cheio de controles acima do chat comum.
5. Explicar melhor aprofunda a própria seção, podendo terminar convidando a pessoa
   a apontar uma dúvida específica. A explicação inicial já deve ser executável.
6. Terminei registra a conclusão e apresenta o próximo objetivo executável.
7. A conversa contextual permite tirar dúvidas, atualizar progresso e resolver
   equipamentos faltantes, depois retornando ao objetivo principal.
8. Progresso e confirmação visual discretos. Não acrescentar pontos, medalhas ou
   mecânicas extras. Roteiro e saída ficam em acesso secundário.

## Estado e regras de progresso

- Uma partida ativa por conversa, salva automaticamente, sem exigir conta
  ou sincronização entre aparelhos nesta versão. Permitir retomar depois.
- Guardar mapa/EE, jogadores, objetivos e equipamentos concluídos, progresso
  parcial relevante, objetivo consultado e retorno após uma ajuda lateral.
- Objetivo consultado e objetivo concluído são conceitos diferentes.
- Usar objetivos identificáveis e estáveis, não o índice de um bloco gerado pelo
  modelo. A mesma tarefa não deve ganhar identidade nova por ser resumida.
- Conclusões podem ocorrer fora de ordem. Fez 2, 3, 5 e 6 não comprova 1 e 4.
- Distinguir concluído, pendente e informação ainda desconhecida. Procedimentos
  condicionais e caminhos alternativos dependem da situação da partida.
- Não inferir que todos os passos anteriores ocorreram por visitar uma fase
  avançada. Confirmar somente o que for necessário para seguir.
- Reconhecer conclusões necessariamente comprovadas por um relato, usando
  relações revisadas. Não confundir dependência lógica com mera ordem sugerida.
- Pergunta pontual não conclui tarefa. Relato explícito de conclusão pode atualizar
  uma ou várias tarefas. Ambiguidade relevante pede esclarecimento específico.
- Permitir corrigir conclusões e desfazer marcações. Se a correção afetar objetivos
  posteriores, confirmar o efeito específico sem apagar o restante silenciosamente.
- Registrar conclusão antes de gerar a próxima explicação. Se a API falhar, a
  conclusão permanece salva e a próxima explicação pode ser solicitada novamente.
- Gerar instruções a partir das fontes; estado da partida não autoriza inventar
  fatos ou considerar pré-requisitos desconhecidos como concluídos.

## Casos mínimos de aceite

| Entrada/ação | Resultado esperado |
| --- | --- |
| Do começo | Iniciar pelo primeiro objetivo aplicável |
| Já fizemos a 3, 4 e 5 | Registrar as três sem gerar explicações intermediárias |
| Fizemos 2, 3, 5 e 6; faltam 1 e 4 | Preservar as lacunas e selecionar o próximo objetivo viável |
| Quero ver a etapa 6 | Consultar sem concluir as anteriores |
| Pula essa | Esclarecer a intenção; não marcar como concluída automaticamente |
| Já melhoramos todos os cajados | Identificar os objetivos correspondentes e atualizar o estado |
| Não achei essa peça | Explicar dentro do contexto, mantendo o progresso |
| Estamos sem o escudo | Ajudar no equipamento e preservar o objetivo de retorno |
| Marquei errado; falta uma peça | Corrigir o estado e avaliar dependências afetadas |
| Terminei + falha da API na próxima explicação | Manter conclusão registrada e permitir nova tentativa |
| Fechar e reabrir | Oferecer retomada do estado salvo |

## Subetapas de implementação

As cinco subetapas foram implementadas e validadas localmente em 23/10/2026.

1. **Arquitetura e estado:** revisar estruturas existentes, definir identidades de
   objetivos, dependências, atualizações, persistência e compatibilidade com o chat.
   Documentar decisões técnicas; implementar o domínio com testes de transições.
2. **Interpretação:** converter relatos em propostas estruturadas de atualização.
   Validar essas propostas no domínio; cobrir ambiguidades, várias conclusões,
   consultas sem conclusão e correções. Preservar suporte multilíngue.
3. **Orquestração:** convite, preparação, overview, localização do progresso,
   próximo objetivo, ajuda lateral e retomada. Integrar com geração e cancelamento.
4. **Interface própria:** substituir o painel atual pela experiência simples
   acordada. Manter chat comum e acompanhamento como experiências distintas.
5. **Validação integrada:** testar mapas, dependências condicionais, falhas, estado
   fora de ordem, retomada e navegador. Atualizar documentação e backlog.

Não estimar a quantidade de trabalho restante a partir da porcentagem de cota.
Cada subetapa deve produzir uma unidade revisável, com testes relevantes e commit
local. Uma interrupção não significa que a unidade em andamento está concluída.

## Registro de execução

- Escopo e plano de retomada: documentados.
- Subetapa 1: domínio e catálogo implementados em 23/10; 16 testes específicos passando.
- Catálogo reúne seções de equipamentos e mantém fases do EE separadas. Progresso
  usa IDs das fontes; consultas não concluem objetivos. Correções propagadas exigem
  confirmação. O estado é serializável e não contém texto gerado.
- Subetapa 2: interpretação multilíngue implementada e validada; 26 testes de
  domínio/interpretação passando. Equipamentos opcionais podem ser consultados
  sem bloquear a conclusão do EE.
- Subetapa 3: endpoints de início/atualização e jobs de explicação implementados,
  com tradução de rótulos, validação da partida e estado compartilhado com o chat.
  Testes verificam que falha de geração não desfaz conclusão registrada.
- Subetapa 4: interface própria, convite, preparação, overview das fases principais,
  texto livre, ações simples e persistência local implementados.
- Testes no navegador controlado: início, imagens, avanço, várias conclusões,
  falha após conclusão e retomada após recarregar passaram.
- Subetapa 5: validação integrada concluída. Suíte completa: 397 testes passando;
  Ruff e sintaxe dos dois scripts JavaScript sem erros.
- OpenRouter real: convite, preparação com dois jogadores, relato de fases 2/3/5
  concluídas com 1/4 pendentes, início e aprofundamento com sete imagens.
- Navegador controlado: recuperação de falha, repetição sem concluir outra etapa,
  confirmação de correção e consulta ambígua sem avanço.
- Commits locais das subetapas: 7469c8b, 015efd2, ab0dcde e 450d825.
- Arquitetura, contratos e limites: [companion-architecture.md](companion-architecture.md).
- Próxima ação: usuário experimentar a nova versão local durante uma partida.
- Decisões de produto bloqueadoras conhecidas: nenhuma. Modos de resposta,
  redesign geral, PWA e desktop continuam fora desta implementação.

Atualizar este registro ao trabalhar: arquivos alterados, último commit, testes
executados, falhas abertas e próxima ação concreta. Registrar alterações ainda
sem teste como pendentes; não apresentar resultados de testes antigos como atuais.

## Procedimento de retomada

1. Ler este documento e as últimas mensagens do usuário, incorporando correções.
2. Inspecionar `git status`, commits recentes e diffs antes de repetir ações.
   Não resetar ou descartar alterações existentes para voltar a um checkpoint.
3. Conferir o registro acima com o código. Revalidar primeiro a unidade que tiver
   ficado incompleta ou sem teste e continuar apenas o trabalho pendente.
4. Atualizar o registro e criar commits locais nas unidades concluídas. Não fazer
   push, deploy ou publicar.

## Restrições preservadas

- Desenvolvimento com chamadas reais somente pelo OpenRouter autorizado; preservar
  cota gratuita da Groq em produção. Não registrar nem versionar chaves.
- Auditoria semântica desligada por padrão. Validação estrutural continua ativa;
  metas de palavras orientam estilo e não derrubam respostas válidas.
- Preservar imagens por etapa e grupos de locais alternativos.
- Não reformular todos os guias ou fazer redesign geral como trabalho incidental.
- Relações revisadas não eliminam os achados semânticos já registrados no backlog.
