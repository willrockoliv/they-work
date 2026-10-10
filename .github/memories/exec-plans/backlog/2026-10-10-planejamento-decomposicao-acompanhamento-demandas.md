# Plano de Implementação: Planejamento, Decomposição e Acompanhamento de Demandas

**Objetivo:** Fazer cada demanda passar por planejamento aprovado antes da execução, dividir o trabalho em tarefas pequenas com dependências explícitas e permitir acompanhar o estado real de cada tarefa até a conclusão.

**Status:** Planejado no backlog; a Etapa 0 precisa decidir os gates de aprovação e o significado dos estados antes da promoção para `active/`.

## Diagnóstico da iteração no banco

Consulta feita diretamente no PostgreSQL em 2026-10-10. Pedido analisado: `6587c1b5-d07a-4cc3-bfc9-5e45f200dacd`, “Software house para contabilidade”.

- O conselho registrou CTO `APPROVE`, CMO `REJECT` por falta de público/dor e CFO `REJECT` por falta de monetização. O CEO gravou o pedido como `REJECTED`.
- Mesmo assim, poucos milissegundos depois foram criadas três delegações simultâneas para tecnologia, mercado e finanças. Cada uma agrupava vários entregáveis numa única tarefa; não houve etapa de plano ou aprovação do plano.
- As três primeiras entregas foram: tecnologia `REJECT` (73/100; cobertura 40%), mercado `REJECT` (50/100; cobertura 15%) e finanças `MODIFY` (faltavam premissas numéricas).
- As três tarefas seguintes foram reexecuções/ajuste da mesma frente, não decomposição em trabalho menor. A tarefa financeira original aparece `COMPLETED` apesar do veredito `MODIFY`, enquanto a tarefa de ajuste permanece `AWAITING_REVIEW`.
- A primeira sessão de mercado terminou com uma resposta desviada para memória corporativa, após 14 passos. Na tentativa financeira, o agente repetiu chamadas com nomes de ferramenta inválidos e terminou truncado no limite de 8 iterações (25 registros de passo).
- O pedido está `AWAITING_FEEDBACK` com `outcome=REJECTED`; `current_state.milestones` registra deliberação, delegações e reports, mas nenhum plano aprovado, dependências, progresso por critério ou bloqueio.

**Conclusão:** a iteração não se perdeu apenas por qualidade de modelo. O fluxo autorizou execução após rejeição, delegou frentes grandes sem especificação operacional e não tem um objeto de plano nem estados que expressem aprovação, bloqueio e conclusão aceita. A revisão por evidências detecta lacunas depois do gasto de inferência, mas não substitui planejamento nem coordenação.

## Escopo

- Qualificar a demanda e resolver ambiguidades antes de contratar ou executar agentes.
- Produzir e aprovar um plano versionado antes de criar delegações.
- Decompor entregáveis em tarefas pequenas, verificáveis e ligadas por dependências.
- Acompanhar responsável, estado, evidências, tentativas e bloqueios por tarefa, em API e interface.
- Retomar o plano após falha ou reinício sem repetir etapas concluídas nem declarar sucesso sem aceite.

Fora do escopo: implementar um executor de código ou sandbox. A integração futura com o [ambiente de desenvolvimento isolado](2026-10-10-ambiente-desenvolvimento-isolado-agentes.md) deve usar contratos compatíveis, mas não é pré-requisito para entregar planejamento e acompanhamento.

## Decisões pendentes

- Gate de deliberação: rejeição encerra e não aloca agentes; aprovação condicional gera bloqueios explícitos; aprovação permite planejar. Definir também se o observador pode pedir revisão/override.
- Responsabilidade pelo plano: Chiefs elaboram as partes de domínio e o CEO consolida/aprova; decidir quando uma demanda simples pode usar plano curto sem reunião extra.
- Critério de tarefa pequena: definir tamanho máximo, número de entregáveis por tarefa e regras para tarefas indivisíveis ou que exigem esclarecimento humano.
- Estados canônicos para pedido, plano, tarefa, review e bloqueio; `COMPLETED` deve significar entrega aceita, não apenas execução encerrada.
- Representação persistente de versões, dependências, histórico de transições e snapshots de progresso, com migração compatível com pedidos existentes.
- Limites de concorrência, tentativas, tempo por tarefa e tratamento de ferramenta/modelo inválido sem consumir todo o orçamento em repetições.

## Etapa 0 — Política de planejamento e estados _(sem dependências)_

- [ ] 0.1 Definir o que acontece após `REJECTED`, `APPROVED_WITH_CONDITIONS` e `APPROVED`; garantir que pedido rejeitado não contrate agentes nem crie tarefas executáveis.
- [ ] 0.2 Definir quando pedir esclarecimento ao observador e como registrar premissas, riscos e decisões ainda não resolvidas.
- [ ] 0.3 Aprovar responsável, fluxo de revisão e versão do plano; indicar quais Chiefs contribuem para cada tipo de demanda.
- [ ] 0.4 Definir estados e transições de pedido, plano e tarefa, incluindo `BLOCKED`, `AWAITING_REVIEW`, reabertura e cancelamento.
- [ ] 0.5 Definir tarefa atômica e critérios de aceite: um resultado principal, escopo limitado, saída verificável, dependências e responsável.
- [ ] 0.6 Definir limites de WIP, tamanho máximo do plano, timeout e política de retentativa/replanejamento.

## Etapa 1 — Modelo do plano e projeção de progresso _(depende de 0)_

- [ ] 1.1 Modelar plano ligado a `InitialRequest`, com versão, objetivo, escopo, premissas, critérios globais, status, aprovador e datas.
- [ ] 1.2 Modelar tarefas planejadas com descrição curta, entregável único, critérios verificáveis, responsável/papel, estimativa, status e ordem.
- [ ] 1.3 Persistir dependências como relações explícitas sem ciclos; só tornar uma tarefa elegível quando suas predecessoras estiverem aceitas.
- [ ] 1.4 Definir como planos geram/reusam `AgentTask`, `parent_task_id` e `communication_graph` sem duplicar o registro operacional nem perder versões anteriores.
- [ ] 1.5 Registrar transições de estado e motivo como eventos auditáveis; derivar percentual de progresso de tarefas aceitas, nunca de estimativa textual do modelo.
- [ ] 1.6 Criar migração e backfill conservador: pedidos antigos sem plano seguem consultáveis e não recebem plano fictício.

## Etapa 2 — Fluxo de entrada, planejamento e aprovação _(depende de 1)_

- [ ] 2.1 Adicionar uma fase de qualificação que valide objetivo, público/beneficiário, restrições e informações mínimas antes da deliberação.
- [ ] 2.2 Interromper o fluxo após rejeição; persistir motivos e solicitar reformulação/decisão explícita do observador antes de qualquer contratação.
- [ ] 2.3 Após deliberação aprovada, gerar proposta de plano com tarefas pequenas, critérios de aceite, dependências, riscos, responsáveis e sequência sugerida.
- [ ] 2.4 Verificar automaticamente completude estrutural do plano: tarefa acionável, critério verificável, dependências válidas, escopo coberto e ausência de itens duplicados.
- [ ] 2.5 Permitir revisão dos Chiefs e aceite explícito do CEO/observador conforme a política da Etapa 0; manter versões e justificativas.
- [ ] 2.6 Não contratar subagentes pelo RA nem iniciar execução enquanto o plano não estiver aprovado e a tarefa elegível.

## Etapa 3 — Orquestração de tarefas e feedback _(depende de 2)_

- [ ] 3.1 Substituir frentes fixas que agrupam vários entregáveis por tarefas vindas do plano aprovado; permitir execução paralela apenas quando o DAG autorizar.
- [ ] 3.2 Solicitar ao RA agentes somente para tarefas elegíveis sem responsável disponível; manter o Chief solicitante como supervisor e revisor.
- [ ] 3.3 Propagar ao agente uma instrução focada: objetivo da tarefa, contexto necessário, critério de aceite, dependências concluídas e formato de report.
- [ ] 3.4 Validar nomes/argumentos de ferramentas e contar erros contra o limite de iterações; ao exceder, registrar `BLOCKED` ou falha recuperável com causa, não um report de sucesso truncado.
- [ ] 3.5 Traduzir a revisão em feedback por critério, com citação ou explicação verificável; `MODIFY`/`REJECT` reabre só o escopo necessário e preserva tentativas anteriores.
- [ ] 3.6 Marcar tarefa como `COMPLETED` apenas após aceite; propagar bloqueios para dependentes e recalcular progresso do plano.
- [ ] 3.7 Tornar início, retomada e transições idempotentes; após reinício, continuar do primeiro estado pendente sem duplicar agentes, reports ou eventos.

## Etapa 4 — API, eventos e interface de acompanhamento _(depende de 3)_

- [ ] 4.1 Expor plano, versão, grafo de dependências, tarefas e histórico de estados por pedido, com paginação/limites para relatórios e eventos.
- [ ] 4.2 Publicar eventos de plano/tarefa no WebSocket existente: plano proposto/aprovado, tarefa iniciada, bloqueada, reportada, aceita, reaberta e concluída.
- [ ] 4.3 Criar visualização de plano com status global, tarefas agrupadas por estado, dependências, responsável, progresso derivado, tentativas e blockers.
- [ ] 4.4 Permitir ações explícitas do observador previstas na política: aprovar/rejeitar plano, responder esclarecimentos, cancelar ou solicitar replanejamento.
- [ ] 4.5 Manter a aba da rede corporativa coerente com o plano, distinguindo deliberação, planejamento, execução e revisão.
- [ ] 4.6 Testar loading, vazio, erro, reconexão/replay e seleção de pedido; validar todas as telas alteradas no Integrated Browser.

## Etapa 5 — Testes de regressão e qualidade _(depende de 3 e 4)_

- [ ] 5.1 Criar cenário de regressão baseado no pedido do banco: duas diretorias rejeitam, CEO rejeita, e o resultado esperado é zero contratações/delegações.
- [ ] 5.2 Testar ciclo aprovado: plano proposto, revisão, aceite, tarefas atômicas, dependências, execução, report e aceite final.
- [ ] 5.3 Testar tarefa bloqueada, review rejeitada, retentativa limitada, replanejamento versionado, cancelamento e retomada idempotente.
- [ ] 5.4 Testar que erro repetido de ferramenta ou limite do ReAct não se torna report concluído nem mantém tarefa indefinidamente `IN_PROGRESS`.
- [ ] 5.5 Testar consistência entre `InitialRequest.status/outcome`, plano, `AgentTask.status/decision`, eventos e percentuais da UI.
- [ ] 5.6 Executar testes offline com banco isolado e doubles de modelo; não depender de Ollama, rede real ou workloads externos.
- [ ] 5.7 Reexecutar o mesmo pedido de regressão em modo controlado e comparar delegações, tarefas aceitas, tentativas, duração e causas de bloqueio com a execução registrada.

## Etapa 6 — Documentação e rollout _(depende de 5)_

- [ ] 6.1 Atualizar `docs/COMMUNICATION-GRAPH.md` e `docs/ARCHITECTURE.md` com o novo ciclo e a semântica dos estados.
- [ ] 6.2 Atualizar `docs/PRD.md` e `README.md` com planejamento obrigatório, aprovação e acompanhamento por tarefa.
- [ ] 6.3 Documentar configuração, migração, pedidos legados, limites, operação manual e recuperação após reinício.
- [ ] 6.4 Habilitar por etapas; comparar resultados com o fluxo anterior e manter mecanismo de desligamento/retorno.
- [ ] 6.5 Criar arquivo de progresso e atualizar `PLAN-INDEX.md` ao promover/concluir o plano.

## Critérios para promover a `active/`

- Estados e gates aprovados, incluindo o tratamento inequívoco de pedidos rejeitados e aprovações condicionais.
- Critérios objetivos para decomposição em tarefas pequenas e para aceite final definidos.
- Contrato de persistência decidido sem duplicar indevidamente `AgentTask` e `communication_graph`.
- Telas/API e estratégia de migração/compatibilidade dimensionadas; cenário de regressão do banco preparado sem depender dos dados vivos.

## Critérios de aceite da implementação

- Nenhuma delegação ou contratação ocorre antes do aceite do plano; pedido rejeitado não dispara execução.
- Cada tarefa possui um resultado verificável, dono, critério de aceite e dependências explícitas quando aplicável.
- O estado mostrado corresponde ao banco e ao histórico de transições; progresso só avança com tarefa aceita.
- Falhas de ferramenta/modelo viram erro ou bloqueio observável, com retentativa limitada e retomada segura.
- Chief e observador conseguem identificar o que está pronto, em andamento, bloqueado e aguardando revisão, além do motivo.
- O cenário baseado na demanda “Software house para contabilidade” não cria as três delegações observadas após decisão `REJECTED`.

## Relação com outros planos

- [Ambiente de desenvolvimento isolado para agentes](2026-10-10-ambiente-desenvolvimento-isolado-agentes.md): complementar; o presente plano controla o que fazer e o estado do trabalho, enquanto o outro fornece ambiente de execução para código.
- [Navegador isolado para os agentes](2026-10-09-navegador-isolado-agentes.md): independente; acesso à web não substitui planejamento, decomposição ou acompanhamento.