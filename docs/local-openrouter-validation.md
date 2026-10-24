# OpenRouter local — 21/10/2026

Integração validada com uma chamada real ao `openai/gpt-oss-120b`.
Nenhuma chave foi incluída em arquivos versionados. Nenhum push ou deploy.

Este registro descreve a integração inicial. A validação posterior de
completude está em [multi-guide-validation.md](multi-guide-validation.md).

## Comportamento

- Produção é o padrão: mesmo com chave paga e preferência por OpenRouter,
  somente `APP_ENV=development` junto do opt-in explícito permite o cliente pago.
- Local: Groq principal, OpenRouter somente após HTTP 429; testes reais podem
  selecionar diretamente OpenRouter via `LOCAL_LLM_PROVIDER=openrouter`.
- O mesmo schema JSON e validações de conteúdo são aplicados aos dois provedores.
- Roteamento exige parâmetros suportados, teto por milhão de US$0,06 de entrada
  e US$0,25 de saída; não troca automaticamente de modelo.
- Consumo efetivo fica em `.cache/llm-usage.jsonl`, sem conteúdo das conversas.
- Docker/Compose desativam acesso pago explicitamente. Compose também limpa a chave.
- Testes automatizados desativam a configuração paga durante a coleta.

## Verificação

- Suíte completa: 253 testes aprovados, cobertura de 90,37%.
- Após melhorar a mensagem de correção de citações curtas do planejador:
  49 testes específicos de planejamento, contrato e integração local aprovados.
- Ruff e `git diff --check` aprovados.
- Chamada mínima real: conexão e schema aceitos pelo OpenRouter.
- Pack-a-Punch de Der Eisendrache: 3 blocos, 6 imagens, sem escolha de arquivo.
- O teste de EE completo de Origins continua revelando dependências omitidas
  e planos inválidos. Um plano aceito pelo schema não garante a completude do EE.
  Não considerar a etapa de multi-guias concluída por causa desta integração.
- Uma sondagem experimental com instruções adicionais concluiu Origins em
  110,53 segundos, com 17 blocos, 90 imagens e 9 documentos. Ainda faltavam
  preparação e etapas de upgrade dos cajados. Essas instruções consumiam o
  orçamento de trechos relevantes de Zetsubou e foram retiradas; permanece
  somente o diagnóstico mais específico para corrigir citações curtas.

Nos primeiros 13 registros reais desta etapa, o custo informado somou
US$0,00299256. O total continua sendo atualizado no registro local; esse valor
não é uma consulta de saldo da conta nem um limite de gastos.
