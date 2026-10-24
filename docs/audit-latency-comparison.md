# Comparação da auditoria por modelo

Experimento local de 21/10/2026, solicitado pelo usuário antes de decidir
simplificações adicionais. A auditoria está desativada por padrão com
`ENABLE_ANSWER_AUDIT=false`. A opção `true` é mantida para comparações explícitas.
Não houve rollback do multi-guias nem mudanças na associação de imagens aos passos.

## Método

Pedidos idênticos, mesma base, mesmo modelo `openai/gpt-oss-120b`, mesmo roteamento
OpenRouter e parâmetros, execução sequencial. A ordem dos modos foi alternada
entre os casos. Foram usados BM25 e uma base previamente carregada nos dois
modos, sem acrescentar variabilidade da Voyage ou da cota gratuita da Groq.

O experimento mede o fluxo completo de `answer_chat`: planejamento, geração,
eventuais correções e apresentação. Cada chamada à API foi cronometrada e seu
provedor efetivo, tokens e custo registrados. O tempo de construção inicial da
base e do cliente fica fora da medição por pergunta. Não foi usado cache de respostas.

Uma execução de cada modo por caso é uma sondagem, não um benchmark estatístico.
Origins recebeu uma repetição adicional em ordem inversa, em diretório separado,
porque a variação no tempo de geração quase anulou o custo da auditoria no primeiro par.
O modelo é variável; textos, quantidade de tokens, necessidade de reparo e carga
do provedor podem diferir. Menos chamadas não implica redução proporcional do
tempo, porque uma conferência costuma produzir muito menos texto que um guia.

## Resultados

O provedor efetivo foi DeepInfra em todas as chamadas. O custo total informado
pelo OpenRouter nas oito execuções foi US$0,011449194. Todas passaram os aceites
estruturais de caminhos/seções exigidos e exclusões; ressalvas semânticas abaixo.

| Pedido | Com auditoria | Sem auditoria | Diferença observada |
| --- | ---: | ---: | ---: |
| Escudo base de Gorod | 22,906 s | 15,531 s | 7,375 s / 32,2% |
| Origins completo, média de duas rodadas | 150,407 s | 135,328 s | 15,079 s / 10,0% |
| EE de Zetsubou resumido | 129,000 s | 84,234 s | 44,766 s / 34,7% |

Origins, rodadas individuais: 158,047 → 152,265 segundos e, na ordem inversa,
142,766 → 118,391 segundos. A pequena amostra e a variação de geração não
permitem tratar esses percentuais como efeito causal exato ou SLA.

| Pedido/modo | Gerações | Conferências | Blocos/imagens | Palavras da resposta |
| --- | ---: | ---: | --- | ---: |
| Escudo, com | 1 | 1 | 4 / 10 | 196 |
| Escudo, sem | 1 | 0 | 4 / 10 | 193 |
| Origins rodada 1, com | 4 | 5 | 23 / 127 | 2.615 |
| Origins rodada 1, sem | 4 | 0 | 23 / 127 | 2.537 |
| Origins rodada 2, com | 4 | 4 | 23 / 127 | 2.692 |
| Origins rodada 2, sem | 4 | 0 | 23 / 127 | 2.704 |
| Zetsubou resumido, com | 6 | 6 | 19 / 0 | 1.155 |
| Zetsubou resumido, sem | 5 | 0 | 19 / 0 | 1.176 |

O roteiro resumido já não apresentava galeria; zero imagens nesse modo não é
uma regressão. As 127 imagens do guia completo e as dez do escudo foram mantidas.
Os números de chamadas incluem respostas HTTP concluídas que exigiram correção.
Em Origins, a própria conferência devolveu uma resposta vazia na primeira rodada
e precisou ser repetida. Em Zetsubou, houve uma regeneração semântica adicional.

Na primeira execução de Origins sem auditoria, 151,750 dos 152,265 segundos
foram gastos nas quatro chamadas de geração. A saída consumiu 5.088 tokens.
Na execução com auditoria, a geração levou 128,297 segundos e a conferência,
29,640 segundos. Portanto, a geração mais rápida daquela rodada mascarou boa
parte da sobrecarga ao comparar somente os totais.

Retirar a auditoria eliminou chamadas e reduziu tempo/custo, mas não transformou
EEs extensos em respostas de poucos segundos. O gargalo restante medido está
nas chamadas de geração desse caminho OpenRouter/DeepInfra, incluindo escrita,
espera e transmissão. Não foram separados tempo de fila, prefill e decodificação,
nem realizada uma comparação controlada com a Groq. Alterar a política de lotes
ou voltar à recuperação anterior exige outro experimento; isso não foi feito aqui.

Validação automatizada final: **292 testes**, cobertura **91,94%**. Lint passou.
O servidor local foi reiniciado com a auditoria desativada e saúde OK, índice
semântico pronto e zero erros de validação. Sem push ou deploy.

## Tamanho dos Markdown

Contagens de todos os documentos do mapa, removendo referências a arquivos de
imagem com o mesmo tratamento da ingestão. Palavras contadas por separação de
espaços; não são contagens de tokens do modelo.

| Mapa | Documentos | Caracteres de texto | Palavras |
| --- | ---: | ---: | ---: |
| Der Eisendrache | 21 | 56.984 | 10.475 |
| Zetsubou | 20 | 49.291 | 8.966 |
| Gorod Krovi | 17 | 48.216 | 8.811 |
| Origins | 22 | 25.296 | 4.627 |
| Revelations | 14 | 31.655 | 5.726 |
| Shadows | 21 | 20.608 | 3.802 |

Esses volumes não explicam sozinhos minutos de espera. É necessário distinguir
o texto lido, o texto reescrito na saída e o texto reenviado a outras chamadas.
O fluxo de geração ainda usa lotes sequenciais de até oito seções ou 10.000
caracteres de fontes por lote; essa regra não foi alterada neste experimento.

## Verificação e limites

São conferidos caminhos e seções exigidos pelas fixtures, exclusões de objetivos
opcionais, quantidade de blocos/imagens e trechos das respostas. As validações
estruturais por código permanecem ativas com e sem auditoria. Isso não certifica
equivalência factual de todas as frases nem a precisão absoluta da base.

Na revisão das duas respostas de Zetsubou, ambas disseram que cada jogador
recebe três desafios sorteados, mas rotularam a lista de desafios possíveis como
“Procedimentos obrigatórios”. A versão auditada também deixou essa ambiguidade
passar. Os dois modos ainda repetiram instruções de montar a KT-4 na conclusão
da melhoria, embora a arma já tivesse sido tratada antes. Esses achados foram
registrados, sem mudar os prompts entre os modos nem corrigir uma resposta
manualmente para melhorar o resultado do experimento.

No escudo sem auditoria foram mantidos os três locais de cada peça e a bancada
de montagem. Em Origins, os trechos revisados preservaram a preparação da melhoria
do cajado de fogo, a finalização compartilhada, o G-Strike e as peças do Drone.
Isso é revisão amostral das respostas contra a base, não uma certificação de todos
os fatos do jogo. O campo `ok` dos dados brutos refere-se aos aceites estruturais.

As respostas completas, dados de cada chamada e tamanhos de arquivos ficam em
`.cache/audit-ab-2026-10-21/`, ignorado pelo Git. Não há credenciais nos relatórios.
A repetição de Origins fica em `.cache/audit-ab-repeat-2026-10-21/`.

Para repetir, com opt-in pago de desenvolvimento já configurado:

```powershell
python -m scripts.compare_answer_audit --live --output-dir .cache/audit-comparison
python -m scripts.compare_answer_audit --live --cases origins-full --reverse-order --output-dir .cache/audit-repeat
```

O script exige `--live` e o opt-in local e usa crédito do OpenRouter; não faz
parte da suíte automatizada. Os testes automatizados usam modelos simulados.
