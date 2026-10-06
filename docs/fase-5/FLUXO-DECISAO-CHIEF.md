# Fluxo de Decisão do Chief — Análise de Reports

Diagrama do ciclo de feedback quando um chief recebe um report de um agente.

```mermaid
flowchart TD
    A["Agent Completa Task<br/>(reasoning_session_N)"] -->|Report Enviado| B["Chief Recebe Report<br/>(pending_review=true)"]
    
    B -->|Inicia Reasoning| C["Chief Analisa Report<br/>(agent_decision_engine)"]
    
    C -->|Reasoning Steps| C1["Pensamento: Analisar qualidade<br/>Ação: tool_evaluate_quality<br/>Observação: Score, gaps, concerns"]
    
    C1 -->|Reasoning Continua| C2["Pensamento: Comparar com objetivo<br/>Ação: tool_compare_vs_objective<br/>Observação: Delta, missing items"]
    
    C2 -->|Reasoning Finaliza| C3["Conclusão: Rejeitar/Aceitar/Modificar"]
    
    C3 --> D{Decision Type?}
    
    D -->|REJECT| E["❌ Reconvocar Agent<br/>(criar nova DELEGATION)"]
    E -->|Feedback| F["Agent Recebe Crítica<br/>Status: task=REJECTED"]
    F -->|Tenta Novamente| A
    
    D -->|MODIFY| G["✏️ Criar Subtask<br/>(parcial, corrigindo gaps)"]
    G -->|Nova Delegação| H["Agent Trabalha em Subtask<br/>Status: task=MODIFIED"]
    H -->|Report New Task| B
    
    D -->|CONSULT| I["📞 Consultar Outro Chief<br/>(CONSULTATION node)"]
    I -->|CTO/CMO/CFO Opinion| J["Altro Chief Faz Reasoning"]
    J -->|Opinion Volta| K["CEO Consolida Opiniões<br/>(reasoning novo)"]
    K -->|Final Decision| L{Outcome?}
    
    L -->|Approved + Next Steps| M["✅ Aprovar e Definir Próximos Passos"]
    M -->|Pode ser| N["Contratar novo agent via RA<br/>Delegar nova task<br/>Completar request"]
    
    L -->|Needs More Work| O["Reconvocar agent ou consultar novo chief"]
    O -->|Loop| B
    
    D -->|APPROVE| M
    
    M --> P["Update communication_graph<br/>Create new DECISION node<br/>Broadcast via WebSocket"]
    P --> Q["Request continua (ou finaliza)"]
```

---

## Parametrização de Decisões

Como o chief **supervisor especializado** decide qual ação tomar? Depende de:

| Fator | REJECT | MODIFY | CONSULT_PEERS | ESCALATE | APPROVE |
|-------|--------|--------|---------------|----------|---------|
| **Qualidade** | <70% | 70-85% | 85-95% | 85-95% | >90% |
| **Completude** | <50% | 50-80% | 80-95% | 75-95% | 100% |
| **Riscos** | Alto | Médio | Baixo | Médio | Nenhum |
| **Urgência** | Med/High | Medium | Low | Medium | Low |
| **Complexidade** | Qualquer | Alta | Alta | Muito Alta | Qualquer |
| **Afeta Múltiplas Áreas** | Não | Não | Sim | Sim | Não |

**Nota:** Quando afeta múltiplas áreas → CONSULT_PEERS. Quando há disagreement → ESCALATE para CEO.

---

## Modo AUTOMÁTICO vs MANUAL

**AUTOMÁTICO** (default):
- Chief recebe report → reasoning automático → decisão automática
- User vê tudo acontecendo em tempo real no frontend
- Mais realista, mais dinâmico

**MANUAL**:
- Chief recebe report → reasoning automático → **user valida decisão**
- User clica "Confirmar: REJECT, pedir refazer"
- Mais controle, mais lento, ideal para debug/teaching
