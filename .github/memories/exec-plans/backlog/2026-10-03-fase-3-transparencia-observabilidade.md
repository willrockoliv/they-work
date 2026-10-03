# Plano de Implementação: Fase 3 - Transparência e Observabilidade (Backend)

**Objetivo:** Interceptar e visualizar o fluxo cognitivo (ReAct/Chain-of-Thought) de cada agente em tempo real, transformando pensamentos brutos em estrutura de fluxogramas para o frontend.

**Status:** Planejado

**Bloqueante:** Fase 2 (Estruturação Societária) deve estar 100% concluída

**Prazo Estimado:** ~2 semanas

---

## 1. Implementação do Padrão ReAct (Reasoning and Acting)

- [ ] Criar estrutura de dados para capturar fluxo ReAct:
  - [ ] Tabela `reasoning_logs` (armazenar pensamentos)
  - [ ] Tabela `action_logs` (armazenar ações/tools)
  - [ ] Tabela `observation_logs` (armazenar observações)
  - [ ] Tabela `conclusion_logs` (armazenar conclusões)
- [ ] Implementar callbacks de interceptação:
  - [ ] Callback para capturar "Pensamento" (tokens brutos)
  - [ ] Callback para capturar "Uso de Ferramenta" (tool calls)
  - [ ] Callback para capturar "Observação" (tool results)
  - [ ] Callback para capturar "Conclusão" (final reasoning)
- [ ] Estruturar dados em formato JSON normalizado:
  - [ ] Timestamp, agent_id, thought, action, observation, conclusion
  - [ ] Vincular a cada step o modelo LLM utilizado
  - [ ] Rastrear tokens consumidos por step

## 2. Integração com LangGraph / CrewAI

- [ ] Avaliar melhor framework para interceptação:
  - [ ] LangGraph para agentic workflows mais transparentes
  - [ ] CrewAI para multiplos agentes com papéis
  - [ ] Ou wrapper customizado sobre Ollama
- [ ] Implementar callbacks customizados:
  - [ ] Hook em cada passo do fluxo de pensamento
  - [ ] Capturar prompts enviados
  - [ ] Capturar respostas completas (não só tokens)
- [ ] Testar com cada Chief e subagente

## 3. Visualização em Fluxograma

- [ ] Criar estrutura de dados para fluxograma:
  - [ ] Nodes: [Pensamento], [Ferramenta], [Observação], [Conclusão]
  - [ ] Edges: conexões entre nodes
  - [ ] Metadata: timestamp, duração, tokens
- [ ] Implementar serialização JSON:
  - [ ] Formato compatível com D3.js ou similar para frontend
  - [ ] Incluir posicionamento e layout hints
- [ ] Criar endpoint `GET /agents/{agent_id}/reasoning-flow`:
  - [ ] Retorna fluxograma atual em tempo real
  - [ ] Histórico de steps executados
  - [ ] Status de execução (em progresso, concluído, erro)

## 4. Captura de Contexto de Ferramentas

- [ ] Armazenar termos de pesquisa:
  - [ ] Quando agente faz busca, salvar query
  - [ ] Salvar resultados retornados
- [ ] Armazenar web scraping:
  - [ ] URLs acessadas
  - [ ] Conteúdo extraído (resumido)
  - [ ] Timestamp de acesso
- [ ] Armazenar lógica de código:
  - [ ] Código gerado ou analisado
  - [ ] Raciocínio por trás de cada linha
  - [ ] Erros encontrados e resoluções

## 5. Painel de Auditoria em Tempo Real

- [ ] Criar endpoint `GET /agents/{agent_id}/live-status`:
  - [ ] Retorna status atual do agente
  - [ ] Barra de progresso de processamento
  - [ ] Última ação executada
  - [ ] Tempo decorrido
- [ ] Implementar WebSocket para atualizações push:
  - [ ] Frontend se conecta a `/ws/agents/{agent_id}/reasoning`
  - [ ] Backend envia novos steps conforme são executados
  - [ ] Real-time updates sem polling
- [ ] Armazenar histórico completo:
  - [ ] Permitir replay de raciocínio histórico
  - [ ] Timestamps precisos de cada passo

## 6. Análise e Métricas de Agentes

- [ ] Criar dashboard de métricas:
  - [ ] Tokens consumidos por agente
  - [ ] Tempo médio de decisão
  - [ ] Taxa de sucesso/erro
  - [ ] Modelos mais utilizados
- [ ] Implementar rastreamento de custo:
  - [ ] Equivalência em custo computacional (tokens)
  - [ ] Consumo de RAM/VRAM por sessão
  - [ ] ROI de cada subagente
- [ ] Testes de performance:
  - [ ] Overhead de captura de reasoning
  - [ ] Latência de transmissão WebSocket
  - [ ] Tamanho de payloads JSON

## 7. Persistência e Auditoria Corporativa

- [ ] Armazenar todos os fluxos em banco de dados:
  - [ ] Auditoria completa de decisões dos Chiefs
  - [ ] Histórico de subagentes e seus outputs
  - [ ] Rastreabilidade de origem de cada conclusão
- [ ] Criar relatórios estruturados:
  - [ ] Decisões tomadas por Chief
  - [ ] Subagentes contratados e seus resultados
  - [ ] Investimento de recursos por projeto
- [ ] Implementar retenção de dados:
  - [ ] Política de arquivamento de raciocínios antigos
  - [ ] Opção de export para análise

## 8. Testes e Validação

- [ ] Testes unitários:
  - [ ] Captura correta de cada step ReAct
  - [ ] Serialização JSON
  - [ ] Timestamps precisos
- [ ] Testes de integração:
  - [ ] Chief executando tarefa com captura completa
  - [ ] Subagente com captura de reasoning
  - [ ] Múltiplos agentes simultâneos
- [ ] Testes de performance:
  - [ ] Overhead aceitável (<10% latência)
  - [ ] Banco de dados com milhares de raciocínios
  - [ ] WebSocket com múltiplos clientes

## 9. Documentação

- [ ] Documentar formato de ReAct em `docs/REASONING-FORMAT.md`
- [ ] Documentar endpoints de reasoning em `docs/API-REASONING.md`
- [ ] Documentar padrão de fluxograma em `docs/FLOWCHART-SCHEMA.md`
- [ ] Atualizar `ARCHITECTURE.md` com componente de observabilidade

---

## Dependências

```
← Fase 2 (Sociedade) [BLOQUEANTE]
Fase 3 (Observabilidade)
└→ Fase 4 (Interface)
```
