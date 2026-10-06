# Exemplo Prático: Grafo de Comunicações — Fundar Startup

Demonstração de como o grafo evolui com o tempo quando o usuário submete o pedido:
**"Fundem uma startup de tecnologia para escritórios de contabilidade"**

Veja [../../.github/memories/exec-plans/backlog/GRAFO-EXEMPLO.md](../../.github/memories/exec-plans/backlog/GRAFO-EXEMPLO.md) para o exemplo completo com 14 estados detalhados.

## Resumo dos Estados

- **Estado 1 (T=0ms):** Pedido submetido (1 nó USER → CEO)
- **Estado 2 (T=2s):** CEO delibera (consulta CTO, CMO, CFO)
- **Estado 3 (T=5s):** Chiefs opinam (3 reasoning_sessions)
- **Estado 4 (T=8s):** CEO consolida e delega (3 tasks criadas)
- **Estado 5 (T=10s):** Agents reconhecem tarefas
- **Estado 6 (T=15s–60s):** Agents executam (reasoning paralelo)
- **Estado 7 (T=75s):** RA reporta (3 candidatos encontrados)
- **Estado 8 (T=80s):** CEO revisa report do RA
- **Estado 9 (T=90s):** CEO aprova e delega contratação
- **Estado 10 (T=120s):** Analyst reporta (validação concluída)
- **Estado 11 (T=130s):** CEO revisa Analyst e consulta CTO
- **Estado 12 (T=145s):** CTO propõe roadmap
- **Estado 13 (T=160s):** CEO abre nova demanda com RA
- **Estado 14 (T=200s):** Grafo complexo e interconectado

---

## Fluxo Agregado: Do Pedido Inicial até Conclusão

```mermaid
graph TD
    REQUEST["🎯 USER REQUEST<br/>'Fundar startup'"] -->|POST /council/request-action| DELIBERATE["🧠 CEO DELIBERA<br/>(consulta chiefs)"]
    
    DELIBERATE --> DECISIONPLAN["📋 CHIEFS PLANEJAM<br/>- CTO: arquitetura<br/>- CMO: go-to-market<br/>- CFO: viabilidade"]
    
    DECISIONPLAN -->|CTO pede| RA1["📋 RA cria<br/>Dev FastAPI"]
    DECISIONPLAN -->|CMO pede| RA2["📋 RA cria<br/>Analyst MKT"]
    DECISIONPLAN -->|CFO pede| RA3["📋 RA cria<br/>Analyst FIN"]
    
    RA1 -->|Agent criado| CTO_D1["CTO → Dev#1<br/>(auto reporting)"]
    RA2 -->|Agent criado| CMO_A2["CMO → Analyst#2<br/>(auto reporting)"]
    RA3 -->|Agent criado| CFO_A3["CFO → Analyst#3<br/>(auto reporting)"]
    
    CTO_D1 -->|Delega TASK| DEV_EXEC["💻 DEV<br/>Implement MVP"]
    CMO_A2 -->|Delega TASK| MKT_EXEC["📊 Analyst MKT<br/>Market validation"]
    CFO_A3 -->|Delega TASK| FIN_EXEC["💰 Analyst FIN<br/>Financial plan"]
    
    DEV_EXEC -->|Executa| DEV_R["Dev reasoning<br/>(8h)"]
    MKT_EXEC -->|Executa| MKT_R["Analyst reasoning<br/>(6h)"]
    FIN_EXEC -->|Executa| FIN_R["Analyst reasoning<br/>(4h)"]
    
    DEV_R -->|REPORT| CTO_REVIEW["👔 CTO<br/>Revisa seu Dev"]
    MKT_R -->|REPORT| CMO_REVIEW["👔 CMO<br/>Revisa seu Analyst"]
    FIN_R -->|REPORT| CFO_REVIEW["💰 CFO<br/>Revisa seu Analyst"]
    
    CTO_REVIEW -->|Decide| CTO_OK["✅ CTO Aprova"]
    CMO_REVIEW -->|Decide| CMO_OK["✅ CMO Aprova"]
    CFO_REVIEW -->|Decide| CFO_OK["✅ CFO Aprova"]
    
    CTO_OK -->|Converge| CHIEFS["👔 Chiefs coordenam"]
    CMO_OK -->|Converge| CHIEFS
    CFO_OK -->|Converge| CHIEFS
    
    CHIEFS -->|Decisão Final| CEO_FINAL["👤 CEO<br/>(se needed)"]
    
    CEO_FINAL -->|Próxima Fase| NEXT["🚀 Implementação"]
    
    style CEO_FINAL fill:#4a90d9,stroke:#2c5282,color:#fff
    style CTO_REVIEW fill:#68d391,stroke:#276749,color:#fff
    style CMO_REVIEW fill:#f6ad55,stroke:#c05621,color:#fff
    style CFO_REVIEW fill:#fc8181,stroke:#c53030,color:#fff
    style RA1 fill:#ffd700,stroke:#b8860b,color:#000
    style RA2 fill:#ffd700,stroke:#b8860b,color:#000
    style RA3 fill:#ffd700,stroke:#b8860b,color:#000
```

**Diferenças-Chave vs. Linear:**
- ✅ RA cria agentes sob demanda (especialista em prompts)
- ✅ Agentes criados reportam automaticamente para o chief que pediu
- ✅ Cada chief supervisiona apenas seus agentes
- ✅ Reports chegam direto ao chief, não escalão para CEO
- ✅ Chiefs revisam em paralelo
- ✅ CEO apenas decide se há disagreement

---

## Paralelismo Real

Diferente do loop sequencial tradicional:

```
❌ Sequencial (ruins):
Task 1 → Report 1 → Review 1 (bloqueado esperando) → Task 2 → Report 2 → ...

✅ Paralelo (Fase 5):
Task 1 ─┐
Task 2 ─┼─→ Reports 1,2,3 chegando em paralelo
Task 3 ─┤     (CEO recebe conforme pronto, analisa cada um)
        └─→ Chief 1 reconvoca Task 1 (REJECT)
        └─→ Chief 2 aprova Task 2
        └─→ Chief 3 consulta colegas Task 3
        
        Resultado: DAG complexo, não pipeline linear
```
