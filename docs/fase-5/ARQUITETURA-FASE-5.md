# Arquitetura Fase 5 — Rede Corporativa (Diagrama Visual)

## Arquitetura Geral

```mermaid
graph TB
    subgraph "FRONTEND"
        UI_REQUEST["📋 RequestForm<br/>(novo)"]
        UI_NETWORK["🌐 Rede Corporativa<br/>(novo)"]
        UI_TASKS["📌 Tasks Panel<br/>(estendido)"]
    end
    
    subgraph "WEBSOCKET"
        WS["🔄 /ws/game-state<br/>(estendido com<br/>communication_graph)"]
    end
    
    subgraph "BACKEND — ENDPOINTS CHIEFS"
        EP1["POST /council/request-action"]
        EP2["GET  /council/requests"]
        EP3["GET  /council/requests/{id}/graph"]
        EP4["GET  /chiefs/{chief_id}/pending-reviews"]
        EP5["POST /chiefs/{chief_id}/task/{id}/review-and-decide"]
        EP6["POST /chiefs/{chief_id}/consult-peers"]
        EP7["POST /ceo/final-decision/{id}"]
    end
    
    subgraph "BACKEND — ENDPOINTS RA"
        RA1["POST /ra/create-agent"]
        RA2["GET  /ra/created-agents"]
    end
    
    subgraph "BACKEND — SERVIÇOS NOVOS"
        SVC_COMM["communication_service<br/>├─ create_request()<br/>├─ delegate_task()<br/>├─ report_task_completion()"]
        
        SVC_DECIDE["agent_decision_engine<br/>├─ analyze_report()<br/>└─ decide_next_step()"]
        
        SVC_RA["ra_agent_creation_service<br/>├─ create_agent()<br/>└─ set_reporting_chief()"]
        
        TOOLS["7 Ferramentas ReAct<br/>├─ evaluate_report_quality<br/>├─ compare_vs_objective<br/>├─ check_risks<br/>├─ consult_corporate_memory<br/>├─ estimate_cost_benefit<br/>├─ identify_next_steps<br/>└─ get_agent_capability"]
    end
    
    subgraph "BACKEND — DB (NOVO SCHEMA)"
        DB_GRAPH["communication_graph<br/>(DAG)<br/>├─ sender/recipient<br/>├─ type ENUM<br/>├─ reasoning_session_id FK"]
        
        DB_REQ["initial_requests<br/>├─ topic, description<br/>├─ status ENUM"]
        
        DB_TASKS["agent_tasks<br/>├─ assigned_by_chief_id<br/>├─ assigned_to_agent_id<br/>└─ status ENUM"]
        
        DB_AGENTS["agents (estendido)<br/>└─ reporting_chief_id FK"]
    end
    
    subgraph "BACKEND — EXISTENTE"
        CORE["ReAct Engine<br/>reasoning_sessions<br/>councils"]
    end
    
    UI_REQUEST -->|POST| EP1
    EP1 -->|cria| SVC_COMM
    
    UI_NETWORK -->|GET| EP2
    EP2 -->|consulta| DB_REQ
    
    EP3 -->|consulta| DB_GRAPH
    
    EP4 -->|consulta| DB_TASKS
    
    EP5 -->|dispara| SVC_DECIDE
    
    RA1 -->|POST| SVC_RA
    SVC_RA -->|cria + set reporting| DB_AGENTS
    
    SVC_DECIDE -->|reasoning com tools| TOOLS
    SVC_DECIDE -->|atualiza| DB_GRAPH
    
    CORE -->|reasoning| TOOLS
    
    DB_GRAPH -->|broadcast| WS
    DB_TASKS -->|broadcast| WS
    
    WS -->|real-time| UI_NETWORK
    
    style SVC_RA fill:#ffd700,stroke:#b8860b,color:#000
    style RA1 fill:#ffd700,stroke:#b8860b,color:#000
    style RA2 fill:#ffd700,stroke:#b8860b,color:#000
```

---

## Camadas de Implementação

```
┌───────────────────────────────────────────┐
│           FRONTEND (React/TS)             │
│  ┌──────────────────────────────────────┐ │
│  │ RequestForm (novo)                   │ │
│  │ Rede Corporativa (novo, D3.js)      │ │
│  │ Tasks Panel (estendido)              │ │
│  └──────────────────────────────────────┘ │
├───────────────────────────────────────────┤
│      WEBSOCKET LAYER (Real-time)          │
│  /ws/game-state (estendido)              │
├───────────────────────────────────────────┤
│        REST API (FastAPI, novo)           │
│  ┌──────────────────────────────────────┐ │
│  │ /council/request-action              │ │
│  │ /council/requests/{id}/graph         │ │
│  │ /chiefs/{chief_id}/pending-reviews   │ │
│  │ /chiefs/{chief_id}/task/{id}/review  │ │
│  │ /chiefs/{chief_id}/consult-peers     │ │
│  │ /ra/create-agent (NOVO)              │ │
│  │ /ra/created-agents                   │ │
│  │ /ceo/final-decision/{id}             │ │
│  └──────────────────────────────────────┘ │
├───────────────────────────────────────────┤
│       BUSINESS LOGIC (Python Services)    │
│  ┌──────────────────────────────────────┐ │
│  │ communication_service                │ │
│  │ agent_decision_engine                │ │
│  │ ra_agent_creation_service (NOVO)     │ │
│  │ council_service (estendido)          │ │
│  └──────────────────────────────────────┘ │
├───────────────────────────────────────────┤
│   REASONING (ReAct + 7 Ferramentas)      │
│  ┌──────────────────────────────────────┐ │
│  │ react_engine (existente)             │ │
│  │ + evaluate_report_quality            │ │
│  │ + compare_vs_objective               │ │
│  │ + check_risks                        │ │
│  │ + [4 mais]                           │ │
│  └──────────────────────────────────────┘ │
├───────────────────────────────────────────┤
│    DATA LAYER (SQLAlchemy + Alembic)      │
│  ┌──────────────────────────────────────┐ │
│  │ communication_graph (novo)           │ │
│  │ initial_requests (novo)              │ │
│  │ agent_tasks (novo)                   │ │
│  │ agents.reporting_chief_id (novo)     │ │
│  │ [existentes: agents, sessions, ...]  │ │
│  └──────────────────────────────────────┘ │
└───────────────────────────────────────────┘
```

**Mudanças-chave:**
- RA é serviço de criação de agentes (não supervisor)
- Cada agente tem `reporting_chief_id` (seu supervisor)
- Reports vão direto para o chief, não para CEO
- RA cria agentes sob demanda dos chiefs

---

## Paralelismo (Parte Crítica)

```mermaid
gantt
    title Execução Paralela de Tarefas em Fase 5
    dateFormat YYYY-MM-DD HH:mm:ss
    
    section CEO Deliberate
    CEO Deliberate :crit, ceo1, 2026-10-05 10:00:00, 4s
    
    section Agent Tasks
    Analyst Market Validation :agent1, 2026-10-05 10:04:00, 60s
    RA Find Devs :agent2, 2026-10-05 10:04:00, 55s
    CTO Roadmap :agent3, 2026-10-05 10:04:00, 50s
    
    section CEO Reviews
    Review RA Report :crit, ceo2, 2026-10-05 10:05:00, 3s
    Review Analyst Report :crit, ceo3, 2026-10-05 10:06:00, 4s
    Review CTO Report :crit, ceo4, 2026-10-05 10:06:05, 5s
    
    section CEO Consolidates
    Consolidate & Decide :crit, ceo5, 2026-10-05 10:06:10, 5s
```

**Observação:** Tasks em paralelo → Reports em paralelo → Reviews em paralelo → Decisão consolidada

---

## Comparativo: Antes vs. Depois

| Aspecto | Fase 4 | Fase 5 |
|---------|--------|--------|
| **Workflow** | Linear | DAG dinâmico |
| **Feedback** | Nenhum | Loop contínuo |
| **Comunicação** | CEO solo | CEO + Chiefs + Agents |
| **Decisões** | Determinísticas | ReAct + 7 ferramentas |
| **Observabilidade** | Agente individual | Rede corporativa inteira |
| **Interface** | Agente selecionado | Grafo + pedidos + tarefas |
| **Paralelismo** | Não | Sim, múltiplos agents |
| **Escalabilidade** | ~10 agents | ~50+ agents (via grafo) |
