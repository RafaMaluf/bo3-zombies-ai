# Comparação das estratégias de geração

**Atualização:** a comparação após ampliar relações e corrigir as fontes está em
[generation-comparison-after-relations.md](generation-comparison-after-relations.md).
Os números abaixo preservam a primeira bateria, anterior a essas mudanças.

Experimento local de 22/10/2026. Esta é a primeira medição, antes da ampliação
dos relacionamentos mapa a mapa. A arquitetura definitiva será escolhida somente
após repetir as medições com os relacionamentos ampliados.

## Método

Três estratégias usam o mesmo modelo GPT OSS 120B via OpenRouter, reasoning low,
temperatura 0,1, teto de 12.000 tokens de saída por chamada, timeout de 90 segundos
por chamada e até 600 segundos por pergunta. Roteamento, preço máximo e contrato
JSON são os mesmos do fluxo local existente. Auditoria semântica desligada.
As validações estruturais e a associação de imagens continuam ativas.

- Sequencial: lotes existentes de até oito seções ou aproximadamente 10.000
  caracteres com margem por seção, executados um após outro.
- Única: todas as seções planejadas em um lote. Uma correção estrutural é
  permitida, como nas outras estratégias. Se houver falha persistente de conteúdo,
  o mecanismo existente pode subdividir o lote; isso deve ser contado e não
  apresentado como uma única chamada bem-sucedida.
- Paralela: os mesmos lotes do sequencial, no máximo quatro chamadas simultâneas,
  com reunião na ordem do plano. Sem chamada adicional de revisão final.
  Uma falha cancela as demais tarefas e não publica resposta parcial.

A primeira execução de cada caso congela os argumentos de geração: plano,
fontes completas, agrupamentos, notas, idioma, detalhe e contexto. As outras
estratégias reutilizam esses argumentos. O script rejeita mudanças no plano ou
na ordem de fontes entre os braços e registra um SHA-256 do plano/conteúdo/imagens.
O planejamento e a apresentação continuam no fluxo de `answer_chat`, com medição
separada do intervalo de geração. BM25 é usado em todos os braços, sem variância
adicional de chamadas Voyage. Não é um teste do transporte pelo navegador.

Nestes cinco pedidos o planejamento já foi resolvido pelas dependências locais:
as chamadas registradas são `OrderedAnswer`, sem chamada ao modelo para descobrir
fontes. O intervalo de geração ficou muito próximo do tempo total. Ampliar as
relações deve beneficiar outros pedidos/mapas e a cobertura, mas não há evidência
para prometer grande redução adicional nestes mesmos casos já preparados.

A ordem dos modos é rotacionada entre os casos. Perguntas pequenas que já cabem
em um lote são controles: diferenças entre seus modos refletem principalmente
variação da API/saída, não um benefício de paralelismo.

O script exige `--live` e o opt-in pago local existente. Não é executado pela suíte
de testes. As estratégias alternativas só são selecionadas explicitamente pelo
script; a aplicação continua usando o modo sequencial por padrão.

## Reprodução

```powershell
python -m scripts.compare_generation --live --output-dir .cache/generation-2026-10-22
```

Artefatos locais ignorados pelo Git: fontes, respostas completas, tentativas,
tempos e custo em `.cache/generation-2026-10-22/`. O aceite `structural_ok` verifica
caminhos/seções presentes, exclusões e ausência de clarificação. Não certifica
fidelidade factual: isso exige leitura dos textos e comparação com as fontes.

## Validação técnica

294 testes passando, cobertura 91,97%, lint e `git diff --check` aprovados.
Os novos testes verificam preservação da ordem/imagens nas três estratégias,
concorrência efetiva, limite de quatro chamadas e cancelamento das tarefas
restantes quando uma geração paralela falha.

A disponibilidade da Groq foi verificada com uma chamada curta de 77 tokens de
entrada e 17 de saída. Não foi usada para a bateria de comparação e esse teste
não permite comparar velocidade de provedores em respostas longas.

## Primeira rodada: protótipo com instruções comuns

Todos os quinze resultados passaram os aceites estruturais. Todas as chamadas
usaram DeepInfra via OpenRouter. O custo informado nessa rodada foi US$0,010355684.

| Pedido | Sequencial | Única | Paralela | Blocos / imagens |
| --- | ---: | ---: | ---: | --- |
| Escudo de Gorod | 10,187 s | 10,015 s | 8,313 s | 4 / 10 |
| Pack-a-Punch de Shadows | 23,063 s | 19,312 s | 18,609 s | 6 / 17 |
| Pack-a-Punch de Zetsubou | 28,203 s | 38,063 s | 15,063 s | 11 / 14 |
| EE completo de Origins | 101,671 s | 74,313 s | 28,265 s | 23 / 127 |
| Roteiro de EE de Zetsubou | 54,500 s | 35,047 s | 17,250 s | 19 / 0 |

Escudo e Shadows já usam uma chamada nos três modos. Zetsubou PAP usa dois
lotes; sua geração única exigiu duas chamadas porque o contrato rejeitou a
primeira versão da etapa subaquática por pouca substância. O tempo inclui essa
correção, sem remover a execução desfavorável da amostra.

Origins usou quatro chamadas sequenciais/paralelas e uma no modo único. Zetsubou
resumido usou cinco chamadas sequenciais/paralelas (até quatro concorrentes) e
uma no modo único. Não houve subdivisão adaptativa nessa rodada.

## Revisão de conteúdo: diferenças reais, além da estrutura

Não foram alterados fontes, prompts ou contratos entre os modos para corrigir
problemas encontrados nessa primeira comparação. A mesma versão foi mantida
na repetição dos EEs. Uma limitação encontrada no protótipo motivou um experimento
adicional, separado: a instrução herdada de lotes ainda dizia que outras gerações
cobririam outras etapas, mesmo no modo único. A versão 2 do modo único explicita
que é a resposta inteira e deve cobrir todas as fontes/procedimentos agrupados,
sem uma futura geração complementar. Essa sondagem adicional não modifica o
prompt padrão sequencial/paralelo nem corrige guias ou fatos específicos.

- No PAP de Zetsubou, a geração única preservou as ações principais, mas omitiu
  o aviso de zumbis infectados/monstro do pântano ao entrar no bunker. Os dois
  outros resultados incluíram o aviso. Uma versão sequencial abreviou a rota
  inicial da etapa subaquática mais do que as outras.
- Origins completo: 2.648 palavras no sequencial, 2.057 no único e 2.600 no
  paralelo. Menos palavras não prova pior qualidade, mas também não permite
  atribuir toda a diferença de tempo somente ao número de chamadas.
- Origins sequencial omitiu no corpo de "Chuva de Fogo" a instrução final de
  lançar o G-Strike na pedra fora do mapa, embora o título a sugira. Único e
  paralelo trouxeram a ação explícita.
- Origins único expôs referências como "seção s11", "s14" e "s19", que são chaves
  internas do contrato e não rótulos de navegação para o jogador. Também omitiu
  "colocar de volta" na preparação do G-Strike; o paralelo omitiu essa ação,
  enquanto o sequencial a menciona. O próprio MD é ambíguo sobre o retorno da
  pedra; a revisão dos guias precisa resolver a lacuna, sem inventar o destino.
- Zetsubou resumido único omitiu o retorno à mesa de upgrade e a fabricação final
  da Masamune, apesar de essa receita estar no conteúdo agrupado obrigatório da
  seção do frasco 115. Sequencial e paralelo explicaram a fabricação, mas
  repetiram "construir KT-4" depois de já tê-la explicado.
- Zetsubou sequencial ainda usou "Procedimentos obrigatórios" antes de uma lista
  de possíveis trials, contradizendo a indicação de três sorteados por jogador.
  O paralelo os apresentou como exemplos. O único foi mais conciso nesse ponto.
- Permanecem termos ingleses/português pouco natural em todos os modos. Não há
  evidência para certificar equivalência semântica total nem superioridade
  factual universal de uma estratégia.

As imagens mantiveram IDs, agrupamento e ordem dos passos entre estratégias;
isso é uma propriedade da montagem pelo código, não prova de completude do texto.
O roteiro resumido já oculta imagens por política; zero não é regressão.

## Repetição dos EEs, antes do ajuste de escopo do modo único

Segunda ordem: Origins paralela → única → sequencial; Zetsubou única → sequencial
→ paralela. Mesmos fingerprints de fontes/plano e mesmos parâmetros da primeira
rodada. Os seis resultados passaram os aceites estruturais, sem mudança na ordem
das fontes/imagens. Todos usaram DeepInfra. Somadas as duas rodadas, o custo foi
US$0,018012369.

| Pedido | Sequencial (rodada 1 / 2) | Única (rodada 1 / 2) | Paralela (rodada 1 / 2) |
| --- | --- | --- | --- |
| Origins completo | 101,671 / 97,469 s | 74,313 / 69,671 s | 28,265 / 50,016 s |
| Zetsubou roteiro | 54,500 / 79,172 s | 35,047 / 51,562 s | 17,250 / 17,594 s |

Médias de somente duas execuções por modo: Origins 99,570 → 71,992 → 39,141 s;
Zetsubou 66,836 → 43,305 → 17,422 s. O paralelo foi mais rápido nos dois casos
nas duas rodadas; as diferenças entre mínimos e máximos impedem prometer um
tempo fixo. A segunda execução sequencial de Zetsubou consumiu seis chamadas,
pois uma seção ultrapassou o teto de palavras e precisou de uma correção.

Origins único repetido não expôs IDs internos, demonstrando que a falha é variável.
Zetsubou único repetido novamente omitiu a fabricação final da Masamune.

Resultados OpenRouter não certificam a viabilidade do mesmo nível de concorrência
na cota gratuita da Groq em produção. Não se deve escolher o modo definitivo
somente pelo melhor tempo, nem trocar automaticamente o padrão da aplicação.

Reprodução da repetição (o código atual usa o ajuste de escopo do modo único;
os dados antigos ficam separados):

```powershell
python -m scripts.compare_generation --live --cases origins-full zetsubou-summary --modes parallel single sequential --output-dir .cache/generation-repeat-2026-10-22
```

## Sondagem adicional: geração única com escopo explícito

O processo anterior já havia carregado o código com o prompt original. Após seu
término, um processo separado usou a versão 2, deixando explícito que uma única
geração deve desenvolver a resposta inteira. Fontes/plano mantiveram exatamente
os fingerprints das rodadas anteriores. Demais parâmetros permaneceram iguais.

| Pedido | Tempo | Chamadas | Blocos / imagens | Palavras |
| --- | ---: | ---: | --- | ---: |
| Origins completo | 68,750 s | 1 | 23 / 127 | 2.027 |
| Zetsubou roteiro | 50,469 s | 1 | 19 / 0 | 865 |

Não houve correção, subdivisão ou timeout nesses dois resultados. Ambos passaram
os aceites estruturais; a disposição das fontes/imagens permaneceu igual. Origins
não expôs referências `sN` nessa sondagem e incluiu o lançamento do G-Strike, mas
a preparação do G-Strike continuou omitindo o retorno da pedra e a segunda etapa
de mortes. Zetsubou ainda omitiu a fabricação final da Masamune no procedimento
agrupado obrigatório. Portanto, corrigir a instrução herdada era necessário para
avaliar o protótipo, mas não eliminou as perdas observadas.

```powershell
python -m scripts.compare_generation --live --cases origins-full zetsubou-summary --modes single --output-dir .cache/generation-single-scope-v2-2026-10-22
```

## Conclusão provisória e próximos passos

Foram 23 execuções pagas, com custo total informado de **US$0,019863893**. Todas
as chamadas completadas usaram DeepInfra; não houve mistura com a cota Groq.
Todas passaram os aceites estruturais. A revisão manual identificou omissões e
ambiguidades, inclusive na referência sequencial: não existe equivalência factual
total demonstrada. As respostas completas e versões Markdown para leitura estão
nos três diretórios locais de artefatos citados acima, ignorados pelo Git.

O paralelo é o candidato com maior ganho observado nos pedidos grandes. Não se
justificou acrescentar automaticamente outra chamada de revisão final apenas
para reunir a resposta: ordem e imagens foram preservadas pelo código. Isso não
significa que os textos estejam livres de repetições ou de erros semânticos.

O modo único reduziu chamadas e custo, mas encurtou os textos e omitiu instruções
obrigatórias agrupadas em Zetsubou nas três tentativas (duas originais e uma com
escopo explícito). A simples presença de um bloco não comprova cobertura das
receitas dentro dele. Corrigir isso exige melhorar representação/contrato de
completude e rever conteúdo, sem supor que ampliar somente as relações resolva
omissões da geração.

Próxima etapa autorizada na sequência de trabalho: ampliar relações revisadas
mapa a mapa, preservando evidência e distinguindo obrigatório/condicional/opcional.
Depois, repetir medições e revisão de conteúdo antes de escolher arquitetura ou
entrega progressiva. Esta medição não seleciona o paralelo como padrão, não
implementa streaming, modos, novos estados de andamento ou botão cancelar.

O `.env` local ignorado foi configurado com `LOCAL_LLM_PROVIDER=openrouter`,
mantendo o opt-in pago restrito a desenvolvimento. Servidor local com saúde OK,
índice pronto e zero erros de validação; geração sequencial padrão preservada.
Sem push ou deploy.
