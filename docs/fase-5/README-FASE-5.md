# Resumo: Fase 5 — Rede Corporativa e Grafo de Comunicações

**Data:** 2026-10-05  
**Status:** Planejado (Backlog → pronto para promover para Active)  
**Documentação:** Completa com 3 diagramas + exemplos + ferramentas

---

## 🎯 O que você pediu?

> "Quero um campo no frontend para fazer pedidos aos chiefs. Quando mandar uma requisição, quero que os chefes conversem com as outras personas e produzam propostas de como prosseguir. Eles devem perguntar uns aos outros e delegar tarefas para funcionários."

> **Detalhe importante:** "Devem funcionar em loop — funcionários reportam tarefas completas, chiefs analisam, decidem se refazem, corrigem ou aprovam, e decidem o que fazer depois. É um grafo, não um loop linear."

> **Hierarquia Especializada:** "Um dev não reporta para o CEO, reporta para o CTO. Um analista de marketing reporta para o CMO. O CEO não toma decisões sozinho, ele toma em conjunto com os outros chiefs, com desempate dele."

> **Papel do RA:** "O RA não delega nem recebe report. RA é especialista em criar prompts de agentes. Quando um chief precisa de um agente, ele solicita ao RA, que o cria. O agente passa a reportar para o chief que pediu. Apenas chiefs podem solicitar criação de agentes."

---

## ✅ O que foi criado?

### **Plano Estruturado (Fase 5)**
- **7 fases de implementação** (backend → frontend → testes)
- **Schema de banco:** `communication_graph`, `initial_requests`, `agent_tasks`
- **Serviços novos:** `communication_service`, `agent_decision_engine`
- **Endpoints REST:** 8 novos endpoints
- **WebSocket:** Canal de comunicações em tempo real
- **Estimativa:** 52–64 horas (6–8 dias concentrados)

---

## 📊 Documentação Complementar

Todos os arquivos em `docs/fase-5/`:

1. **[ARQUITETURA-FASE-5.md](ARQUITETURA-FASE-5.md)** — Diagramas Mermaid de arquitetura (frontend → backend → db)
2. **[GRAFO-EXEMPLO.md](GRAFO-EXEMPLO.md)** — Exemplo prático passo a passo: "Fundar startup" (14 estados)
3. **[FLUXO-DECISAO-CHIEF.md](FLUXO-DECISAO-CHIEF.md)** — Ciclo de análise de reports (REJECT/MODIFY/CONSULT/APPROVE)
4. **[FERRAMENTAS-CHIEF-ANALYSIS.md](FERRAMENTAS-CHIEF-ANALYSIS.md)** — 7 ferramentas para análise
5. **[2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa.md](../../.github/memories/exec-plans/backlog/2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa.md)** — Plano completo em backlog

---

## 🔄 Como Funciona o Grafo?

### **Estrutura (DAG — Directed Acyclic Graph)**

```
REQUEST (input do usuário)
  ├─ CEO Delibera (raciocínio + conselho)
  │  ├─ CTO Opinion
  │  ├─ CMO Opinion
  │  └─ CFO Opinion
  │
  ├─ CEO Coordena com Chiefs
  │  └─ Aloca áreas de responsabilidade
  │
  ├─ CHIEFS SOLICITAM AGENTES AO RA
  │  ├─ CTO → "RA, cria Dev FastAPI"
  │  ├─ CMO → "RA, cria Analyst Marketing"
  │  └─ CFO → "RA, cria Analyst Financeiro"
  │
  ├─ RA CRIA AGENTES (especialista em prompts)
  │  ├─ Dev criado → reporting_chief_id = CTO
  │  ├─ Analyst MKT criado → reporting_chief_id = CMO
  │  └─ Analyst FIN criado → reporting_chief_id = CFO
  │
  ├─ CHIEFS DELEGAM AO SEU TIME
  │  ├─ CTO Delega Task → Dev
  │  ├─ CMO Delega Task → Analyst MKT
  │  └─ CFO Delega Task → Analyst FIN
  │
  ├─ Agents Executam (reasoning paralelo)
  │
  ├─ Reports Chegam aos CHIEFS SUPERVISORES
  │  ├─ Dev REPORT → CTO (seu supervisor)
  │  ├─ Analyst MKT REPORT → CMO (seu supervisor)
  │  └─ Analyst FIN REPORT → CFO (seu supervisor)
  │
  ├─ CHIEFS ANALISAM (com 7 ferramentas)
  │  ├─ CTO analisa seu Dev
  │  ├─ CMO analisa seu Analyst
  │  └─ CFO analisa seu Analyst
  │
  └─ CHIEFS DECIDEM (em paralelo)
     ├─ CTO: ✅ Aprovar | ❌ Rejeitar | ✏️ Modificar | 📞 Consultar
     ├─ CMO: ✅ Aprovar | ❌ Rejeitar | ✏️ Modificar | 📞 Consultar
     └─ CFO: ✅ Aprovar | ❌ Rejeitar | ✏️ Modificar | 📞 Consultar
        └─ Se divergem → CEO faz desempate
```

### **Fluxo de Feedback (loop contínuo com supervisão especializada)**

```
1. Chief precisa de agente → solicita ao RA
   └─ "CTO pede: Cria Dev em FastAPI"
   └─ "CMO pede: Cria Analyst de Marketing"
2. RA cria agente → especialista em prompts
   └─ Agent automaticamente: reporting_chief_id = solicitante
3. Chief delega → DELEGATION node
4. Agent executa → IN_PROGRESS (reasoning)
5. Agent REPORTA AO SEU CHIEF → REPORT node
   └─ Dev reporta para CTO (não para CEO)
   └─ Analyst reporta para CMO/CFO
6. Chief analisa → reasoning automático
   → Usa 7 ferramentas para avaliar
7. Chief decide → uma de 5 opções:
   ├─ ❌ REJECT: reconvocar agente
   ├─ ✏️ MODIFY: criar subtask
   ├─ ✅ APPROVE: completa
   ├─ 📞 CONSULT: conversar com outro chief
   └─ 👥 ESCALATE: vai para CEO se divergir

8. → Loop continua ou REQUEST completa
```

---

## 🖥️ Interface Frontend (Nova)

### **Aba 1: "Rede Corporativa"**
- Visualização do grafo (D3.js ou Cytoscape)
- Nodes = agentes (círculos com cores)
- Arestas = comunicações (setas direcionadas)
- Clique em nó/aresta → expande detalhes + reasoning
- Zoom/pan interativo

### **Aba 2: "Pedidos"** (nova aba no painel)
- Formulário para submeter pedido (tópico + descrição)
- Lista de pedidos com status (⏳ pendente, 🔄 em andamento, ✅ concluído)
- Clique expande: propostas de cada chief, decisão do CEO, delegações
- Timeline de eventos

### **Integração com Aba "Info"**
- Nova seção: "Tarefas Pendentes/Em Progresso/Concluídas"
- Reports com análise do chief
- Botão "Simular Execução" para forçar agent a trabalhar

---

## 📡 Arquitetura Backend (Resumida)

### **Tabelas Novas**
```sql
communication_graph (DAG)
  ├─ sender_agent_id FK
  ├─ recipient_agent_id FK
  ├─ type ENUM (DELEGATION, REPORT, CONSULTATION, DECISION)
  ├─ reasoning_session_id FK
  └─ status ENUM (PENDING, ACKNOWLEDGED, PROCESSED)

initial_requests
  ├─ topic, description
  ├─ status ENUM (PROPOSED, DELIBERATING, IN_EXECUTION, ...)
  └─ current_state JSONB (snapshots)

agent_tasks
  ├─ assigned_by_agent_id, assigned_to_agent_id
  ├─ task_description, context
  ├─ status ENUM (PENDING, ACKNOWLEDGED, IN_PROGRESS, COMPLETED, REJECTED)
  ├─ report_reasoning_session_id FK
  └─ review_reasoning_session_id FK
```

### **Serviços Novos**
- `communication_service` — cria/roteia comunicações
- `agent_decision_engine` — chief analisa reports + decide
- Estendido: `council_service` — CEO vira orquestrador

### **Endpoints**
```
POST   /council/request-action           — submeter pedido
GET    /council/requests                 — listar pedidos
GET    /council/requests/{id}            — detalhes + grafo
GET    /council/requests/{id}/graph      — retorna DAG em JSON
GET    /agents/{id}/tasks                — tarefas pendentes
POST   /agents/{id}/task/{id}/report     — agente reporta
POST   /agents/{id}/review-and-decide    — chief decide
```

---

## ⚙️ Fluxo E2E (Resumido)

1. **Usuário submete:** "Fundem uma startup de IA"
2. **CEO delibera:** consulta CTO, CMO, CFO (raciocínio paralelo)
3. **CEO coordena:** aloca tarefas aos chiefs responsáveis
4. **Chiefs solicitam agentes:** cada chief pede ao RA para criar agentes especializados
   - CTO → "Cria Dev em FastAPI, DevOps"
   - CMO → "Cria Analyst de Go-to-Market"
   - CFO → "Cria Analyst Financeiro"
5. **RA cria agentes:** com prompts especializados, eles automaticamente passam a reportar para os chiefs que pediram
6. **Chiefs delegam:** cada chief delega tarefas para seus agentes
7. **Agents executam:** raciocínio próprio para cada tarefa
8. **Reports chegam ao chief:** cada agente reporta para seu supervisor (não para CEO)
9. **Chiefs analisam:** em paralelo, usando suas 7 ferramentas especializadas
10. **Chiefs decidem:** APPROVE/REJECT/MODIFY/CONSULT_PEERS/ESCALATE
11. **Decisões complexas:** chefes consultam uns aos outros
12. **CEO desempata:** apenas se houve disagreement entre chiefs

---

## 🎬 Próximos Passos

### Opção 1: **Começar Implementação Agora**
- Mover plano de `backlog/` para `active/`
- Começar pela **Fase I (Backend — Schema)**
- Timeline: ~6–8 dias

### Opção 2: **Refinar Planejamento Primeiro**
- Questões de UX (visualização do grafo)
- Parametrização de decisões dos chiefs
- Tratamento de edge cases (timeout, agent recusa, etc.)

### Opção 3: **Prototipar Partes Específicas**
- Começar pelo "pedido inicial" (frontend)
- Depois adicionar deliberação dos chiefs
- Depois adicionar feedback loop

---

## 📈 Complexidade

| Aspecto | Complexidade | Razão |
|---------|--------------|-------|
| **Schema** | 🟡 Média | 3 tabelas + relações com reasoning_sessions |
| **Serviços** | 🟠 Alta | Decision engine precisa orquestrar múltiplos agents |
| **Reasoning** | 🟡 Média | Uso de 7 ferramentas novas (mas determinísticas) |
| **Frontend** | 🟡 Média | Grafo visual + WebSocket, mas bem delimitado |
| **Testes** | 🟠 Alta | Fluxo completo requer múltiplos agents em paralelo |

---

## 🚀 TL;DR

Você queria:  
✅ Campo no frontend para pedidos aos chiefs  
✅ Chiefs conversam entre si  
✅ Delegação de tarefas  
✅ Feedback loop (agentes reportam, chiefs analisam, decidem próximos passos)  
✅ Grafo dinâmico (não linear)

Você tem:  
📋 Plano estruturado (7 fases, 52–64h)  
📚 5 documentos detalhados com exemplos  
📊 Diagramas Mermaid prontos  
🔧 7 ferramentas para analysis  
🎯 Pronto para começar implementação
