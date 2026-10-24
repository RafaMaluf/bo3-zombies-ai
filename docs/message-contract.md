# Contrato de mensagens e geração estruturada

## Interpretação antes da geração

`app/answer_policy.py` resolve separadamente o assunto, o escopo e o nível de
detalhe. Expressões de apresentação são removidas da consulta de busca, mas
continuam nas instruções do modelo. Assim, `com todos os detalhes` não ativa
o antigo sinal de comparação `todos` nem mistura guias sem relação.

| Pedido | Detalhe | Escopo |
| --- | --- | --- |
| Como monto o escudo? | Detalhado | Procedimento do escudo |
| Passo a passo do escudo | Resumido | Todas as etapas do escudo |
| Me passa o EE de Origins | Resumido | Roteiro de todas as fases |
| EE explicadinho / sem resumir | Detalhado | Todas as fases fornecidas |
| Passo a passo do Maxis Drone sem resumir | Detalhado | Guia do Maxis Drone |
| Onde está a terceira peça? | Direto | Trechos relevantes à pergunta |
| Explique esta fase sem resumir | Detalhado | Fase atual |

As expressões reconhecidas incluem variações em português, inglês e francês.
A regra não usa uma chamada adicional ao modelo. O texto original é
preservado no prompt. Perguntas sem mapa ou assunto suficiente continuam
podendo pedir esclarecimento.

Um pedido amplo usa a recuperação como ponto de partida para o planejamento
de seções entre guias do mesmo mapa. O plano distingue objetivo, pré-requisito
e recomendação, valida evidências das relações e preserva a ordem das fases.
Veja [source-planning.md](source-planning.md). A expansão antiga de um único
arquivo permanece como seleção inicial, não como decisão final de escopo.

## Formato e validação

Nos modelos GPT-OSS 20B e 120B, o cliente envia `json_schema` com `strict: true`,
todos os campos obrigatórios e `additionalProperties: false`. Os identificadores
de fontes aceitos no campo `source_ids` são restritos aos fornecidos àquela
resposta. Outros modelos mantêm JSON object mode com as mesmas validações
locais. A referência do provedor é
[Structured Outputs](https://console.groq.com/docs/structured-outputs).

O contrato local verifica:

- tipos e limites do objeto;
- presença de blocos de instruções, em vez de apenas uma introdução;
- fontes oferecidas e cobertura de todas as seções obrigatórias;
- ordem das seções nos procedimentos;
- conteúdo mínimo por seção; a quantidade de bullets não é exigida, pois juntar
  ações em uma frase não implica omissão;
- concisão do resumo: no fluxo sem plano, até 45 palavras por seção, ou 60
  quando há apenas uma; em planos multi-guias, alvo de 15–30 palavras com teto
  de 120 por seção e 180 para procedimentos obrigatórios agrupados, preservando
  condições importantes sem rejeitar uma explicação correta por margem estreita;
- interrupção por limite de saída, sem aceitar uma resposta truncada como completa.

Essas verificações detectam defeitos estruturais e omissões mensuráveis. Elas
não provam equivalência semântica entre o texto em inglês e sua explicação em
português. A base e a revisão de respostas reais continuam importantes. O
prompt proíbe inventar condições, generalizar locais alternativos de todas as
peças e adicionar instruções de uso não documentadas.

## Uma correção automática

JSON inválido, rejeição `json_validate_failed`, schema inválido, fonte
desconhecida, seção ausente e resposta insuficiente podem disparar **uma única
regeneração por chamada** com os erros encontrados. Esse orçamento cobre
formato e conteúdo daquela chamada. O planejamento tem sua própria chamada;
guias extensos podem exigir vários lotes de geração, limitados a 16.

Se a segunda resposta também falhar, a API devolve um erro e não substitui
silenciosamente o detalhado por um resumo. Falhas de autenticação, conexão,
cota ou configuração não são tratadas como defeitos de conteúdo. As tentativas
de transporte já configuradas no SDK continuam independentes dessa correção.

## Navegação de guias

Na geração ordenada, o schema interno exige uma chave por seção (`OrderedAnswer`).
O servidor monta os blocos públicos e atribui fontes/ordem. Isso não muda o contrato
de resposta consumido pelo frontend. Além da correção de formato, cada lote real
pode passar por comparação com as fontes no modo experimental
`ENABLE_ANSWER_AUDIT=true`. Essa chamada adicional está desativada por padrão;
as validações estruturais por código continuam ativas.
Lotes que continuam incompletos podem ser divididos em seções menores, com o mesmo
detalhamento e limite global de 16 lotes tentados. Um erro final não entrega resposta
parcial. Veja [source-planning.md](source-planning.md) para o fluxo completo.

`start`, `jump` e `complete` são ações processadas pelo servidor. O modelo
recebe uma solicitação para explicar a fase atual resultante, não simplesmente
o texto do botão. Ao concluir uma fase intermediária, deve explicar a próxima.
Somente a conclusão da última fase permite uma confirmação breve.

Armazenamento de estado e frontend não foram ampliados nesta etapa.
O acompanhamento anterior continua funcionando; estado completo da partida e
continuidade persistente permanecem planejados para depois de múltiplos guias.
O planejador recebe um recorte do histórico recente; a geração por lotes usa
duas mensagens recentes, limitadas a 1.600 caracteres cada, além da pergunta
resolvida e do estado guiado. Isso não representa estado persistente da partida.

## Verificação

Os testes de `test_answer_policy.py`, `test_llm_contract.py` e
`test_chat_blocks.py` cobrem classificação, escopo, cobertura, resumo,
regeneração, erros não recuperáveis e navegação. Os testes usam modelos
simulados; respostas reais devem ser verificadas separadamente, sem commitar
chaves ou arquivos `.env`.
