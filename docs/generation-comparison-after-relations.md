# Geração após revisão de fontes e relacionamentos

Medição local em 22/10/2026, sobre a revisão **5c62386**. O paralelo voltou a ser
o mais rápido nos pedidos com vários lotes. As conexões e correções melhoraram
alguns procedimentos antes omitidos, mas não eliminaram falhas semânticas da
geração. Este experimento não muda o padrão sequencial da aplicação.

## Método e reprodução

Mesmo harness da [medição anterior](generation-comparison.md): GPT OSS 120B via
OpenRouter, reasoning low, temperatura 0,1, teto de 12.000 tokens de saída,
auditoria desligada, mesmos contratos e validações estruturais. Todas as 69
chamadas concluídas foram atendidas pela DeepInfra; nenhuma usou a Groq.

Por caso, fontes completas, notas, plano e imagens são congelados e reutilizados
nos três modos. Os fingerprints foram idênticos entre modos e nas repetições.
Busca BM25 e planejamento local iguais em todos; sem consulta Voyage, transporte
do navegador ou streaming. Os tempos abaixo vão até a resposta completa, incluindo
eventuais correções. Não são tempos até o primeiro token.

- Sequencial: lotes de até oito seções ou cerca de 10.000 caracteres, um por vez.
- Única: todas as fontes em um lote, com o escopo explícito da versão 2 do
  experimento; pode haver uma segunda chamada de correção.
- Paralela: os mesmos lotes do sequencial, até quatro simultâneos, reunidos pelo
  código na ordem original. Sem chamada adicional para revisar/reunir a resposta.

Rodada 1: cinco casos anteriores, três modos, ordem rotacionada. Rodada 2:
repetição de Origins completo e Zetsubou resumido com outra ordem, mais o caso
adicional Zetsubou completo. São **24 respostas e 69 chamadas**, sem subdivisão
adaptativa, falhas finais de transporte ou auditoria semântica.

```powershell
python -m scripts.compare_generation --live --output-dir .cache/generation-after-relations-2026-10-22
python -m scripts.compare_generation --live --cases origins-full zetsubou-summary zetsubou-full --modes parallel single sequential --output-dir .cache/generation-after-relations-repeat-2026-10-22
```

Os diretórios acima são ignorados pelo Git e contêm metadados, fontes, tentativas,
uso, respostas JSON e suas versões Markdown para leitura. A execução exige o
opt-in pago local existente. Não houve mudança de aplicação durante as medições.

## Tempos observados

Segundos até a resposta pronta; barras separam as duas execuções, não percentis.
Escudo, os dois PAPs e Zetsubou completo tiveram uma execução por modo.

| Pedido | Sequencial | Única | Paralela | Blocos / imagens |
| --- | ---: | ---: | ---: | --- |
| Escudo de Gorod | 7,969 | 6,781 | 6,734 | 4 / 10 |
| PAP de Shadows | 15,953 | 16,281 | 17,500 | 6 / 17 |
| PAP de Zetsubou | 24,141 | 48,031 | 15,843 | 11 / 14 |
| Origins completo | 71,187 / 83,000 | 66,297 / 108,563 | 26,468 / 40,812 | 23 / 133 |
| Zetsubou resumido | 65,328 / 71,828 | 26,531 / 45,985 | 15,312 / 23,438 | 25 / 0 |
| Zetsubou completo | 169,859 | 237,047 | 65,578 | 51 / 79 |

Nos casos repetidos:

| Pedido | Média sequencial | Média única | Média paralela | Redução paralelo vs. sequencial |
| --- | ---: | ---: | ---: | ---: |
| Origins completo | 77,094 s | 87,430 s | 33,640 s | 56,4% |
| Zetsubou resumido | 68,578 s | 36,258 s | 19,375 s | 71,7% |

Zetsubou completo teve redução de 61,4% com paralelo, em uma única observação.
Não se estima estabilidade ou significância estatística com essa amostra pequena.

Escudo e PAP de Shadows já cabem em uma chamada. Selecionar “paralelo” não cria
um ganho arquitetural nesses controles. O PAP de Zetsubou usa dois lotes; Origins
usa quatro; o roteiro de Zetsubou usa cinco; Zetsubou completo usa sete. Com mais
de quatro lotes há espera por uma vaga: o tempo não equivale ao de uma chamada.

### Correções contabilizadas

O modo único precisou de uma segunda geração em três situações:

- PAP de Zetsubou: primeira versão da etapa subaquática curta demais; total 48 s.
- Origins na repetição: pouca explicação da aquisição de Ice e de uma fase do EE;
  total 109 s.
- Zetsubou completo: pouca explicação dos hard trials; total 237 s.

Não se descartaram essas execuções. Em Zetsubou completo, as duas tentativas
consumiram 132,578 s e 104,422 s. Apesar do timeout de 90 s configurado no SDK,
ele não funcionou como um teto de duração total dessas chamadas. A medição usa
o tempo efetivamente transcorrido; não se diagnosticou aqui a razão de ultrapassar
o valor configurado. O limite externo do experimento permanece 600 s por pergunta.

## Estrutura, imagens e conteúdo

As 24 respostas finais passaram o aceite estrutural. Comparação independente dos
artefatos confirmou igualdade das listas de fontes por bloco e dos IDs de imagem
na mesma ordem entre modos. Isso não certifica que todas as ações dessas fontes
foram explicadas corretamente.

A revisão textual foi direcionada às falhas anteriores e aos procedimentos
recentemente corrigidos; não foi uma auditoria factual integral das 24 respostas.

| Verificação | Observação |
| --- | --- |
| G-Strike: voltar ao Gerador 2, evitar lama, recolocar e realizar a segunda carga | Presente nas seis respostas de Origins, nos três modos e duas rodadas. A correção da fonte ajudou neste ponto antes omitido. |
| Planta arco-íris no roteiro de Zetsubou | Sequencial/paralelo descreveram revelar o local, plantar, regar por três rodadas e recolher. Única omitiu o plantio na primeira rodada, explicando só coletar água; na repetição incluiu a receita. |
| Fabricação final da Masamune no roteiro | Sequencial/paralelo mandaram voltar à mesa e fabricar nas duas rodadas. Única omitiu essa ação nas duas, embora a fonte estivesse no grupo obrigatório. |
| Alternativas de trials no roteiro | Sequencial e paralelo introduziram as cinco opções fáceis como obrigatórias, ou mandaram executar cada uma, apesar de dizerem que cada jogador recebe três trials sorteados. Contradição persistente. |
| Zetsubou completo | Os três modos incluíram o plantio arco-íris e uma seção própria de fabricação da Masamune. A visão geral dos trials distingue os três atribuídos das 16 possibilidades. O modo único completou após a correção estrutural. |
| Construção repetida de KT-4 | Um roteiro paralelo repetido voltou a instruir construir o KT-4 “já existente”. Nos guias completos, o texto esclarece que outro KT-4 não precisa ser construído, mas algumas listas ainda repetem a ação. |
| IDs internos | Vazaram referências como s0, s2, s5 e s11 em quatro respostas: Origins único/paralelo da rodada 1 e Zetsubou completo sequencial/paralelo. Reunião correta dos blocos não impede esse vazamento no corpo. |
| Terminologia e português | Persistem “bassin”, termos ingleses, tradução de cocoon como “côco” e headshots como “cabeçadas”. Um G-Strike sequencial repetido contradisse a si mesmo sobre trocar por Monkey Bombs. |

O problema da Masamune foi observado sobretudo no resumo com receitas agrupadas.
Na versão completa, a fabricação tem seu próprio item de saída e apareceu nos
três modos. Isso sugere investigar um contrato que diferencie ações obrigatórias
de listas de alternativas e preserve conclusões de receitas agrupadas. É uma
hipótese para a próxima alteração, não uma correção já validada por este teste.

Palavras nos corpos, para contextualizar diferenças de trabalho:

| Pedido | Sequencial | Única | Paralela |
| --- | ---: | ---: | ---: |
| Origins, rodada 1 / 2 | 2.868 / 2.826 | 1.985 / 1.932 | 2.993 / 2.975 |
| Zetsubou resumido, rodada 1 / 2 | 1.588 / 1.545 | 931 / 993 | 1.476 / 1.569 |
| Zetsubou completo | 4.333 | 3.250 | 4.245 |

Menos palavras não prova pior qualidade. Aqui, as omissões identificadas no
roteiro são evidências específicas; o tamanho é apenas informação complementar.

## Antes e depois das conexões

Este não é um A/B que isola somente o efeito do grafo: entre as baterias também
foram corrigidos MDs, notas e vínculos de imagens. Nestes pedidos, o planejamento
já era local antes; nas 69 chamadas novas o estágio foi OrderedAnswer, sem seleção
de fontes por modelo. Não há evidência de que o grafo tenha removido chamadas
auxiliares nesses mesmos casos. Ele amplia a cobertura de outros objetivos, que
esta bateria não mede.

| Caso | Seções antes → agora | Caracteres de fontes antes → agora | Imagens antes → agora |
| --- | --- | --- | --- |
| Escudo de Gorod | 4 → 4 | 1.302 → 1.302 | 10 → 10 |
| PAP de Shadows | 6 → 6 | 4.700 → 4.700 | 17 → 17 |
| PAP de Zetsubou | 11 → 11 | 4.505 → 5.526 | 14 → 14 |
| Origins completo | 23 → 23 | 19.115 → 21.472 | 127 → 133 |
| Zetsubou resumido | 19 → 25 | 26.006 → 30.838 | 0 → 0 |

Os dois controles mantiveram fingerprints idênticos à bateria antiga. Os três
outros mudaram; os seis registros extras no roteiro refletem a forma atual do
plano/compactação, não seis chamadas adicionais. As seis imagens de Origins são
as fotos da referência da pá comum, não das melhorias douradas.

Médias antigas sequencial/paralelo eram 99,570/39,141 s em Origins e
66,836/17,422 s no roteiro de Zetsubou. Agora são 77,094/33,640 s e
68,578/19,375 s, respectivamente. Houve melhoria de algumas instruções, mas não
uma aceleração uniforme depois das conexões. Variação da API e conteúdo diferente
impedem atribuir essas diferenças de tempo exclusivamente à revisão.

## Custo e decisão sugerida

Custo informado pela API: **US$0,029405963**, aproximadamente três centavos de
dólar, somando as 24 respostas e as correções. Uso reportado: 348.299 tokens de
entrada e 97.170 de saída. Rodada 1: US$0,011577230; rodada 2 com caso completo:
US$0,017828733. Contagem reportada não é uma projeção de consumo futuro.

O candidato mais forte é manter uma geração para pedidos que cabem em um lote
e executar lotes em paralelo quando há vários. O paralelo preservou mais do
conteúdo revisado que o modo único nos roteiros e reduziu o tempo total dos
pedidos grandes. Ainda exige resolver contradições de alternativas/execução,
ações finais em resumos e referências internas. Não há justificativa nesta
bateria para declarar qualquer modo semanticamente impecável.

O caso completo de Zetsubou continua levando mais de um minuto em paralelo.
A decisão de streaming ou entrega de blocos continua relevante para o tempo até
começar a usar a resposta; não deve ser confundida com redução do tempo total.
Também falta verificar a política de concorrência adequada aos limites gratuitos
da Groq: estes resultados pagos da OpenRouter não demonstram essa viabilidade.

Aplicação permanece na geração sequencial; nenhum frontend, modo de entrega,
modelo, credencial ou configuração de produção foi alterado. Apenas os resultados
e a recomendação desta comparação foram registrados localmente.
