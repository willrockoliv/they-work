# Ferramentas para Análise de Reports — Chief Decision Engine

Quando um chief analisa um report de um agente, ele precisa de **ferramentas específicas** para:
1. Avaliar qualidade do trabalho
2. Comparar resultado vs. objetivo
3. Identificar gaps e riscos
4. Consultar banco de conhecimento corporativo
5. Tomar decisão informada

## Ferramentas Implementadas para Chiefs

### 1. `evaluate_report_quality`
Escore automático de qualidade do report (0-100).
- Valida estrutura de report via regex
- Verifica presença de acceptance_criteria
- Scoring baseado em completude + clareza
- Identifica palavras de risco automaticamente

### 2. `compare_vs_objective`
Compara resultado vs. objetivo original; calcula delta/gap.
- Achievement ratio (0.0–1.0)
- Lista de gaps vs. objetivo
- Bonus items extras feitos pelo agente
- Recomendação: REJECT/MODIFY/APPROVE

### 3. `check_risks`
Identifica riscos técnicos, comerciais, financeiros no report.
- Categoriza por tipo (PERFORMANCE, SCALABILITY, SECURITY, FINANCE)
- Severidade (HIGH, MEDIUM, LOW)
- Impacto estimado
- Recomendação de ação

### 4. `consult_corporate_memory`
Busca no histórico corporativo (decisions passadas, lições aprendidas).
- Retorna precedents com outcomes
- Extrai padrões de decisão anteriores
- Ajuda chief a não repetir erros
- Contextualiza decisão atual

### 5. `estimate_cost_benefit`
Estima custo vs. benefício de aprovação, rejeição ou modificação.
- Calcula custo para cada opção
- Timeline e risco
- ROI e benefício
- Recomendação de ação ótima

### 6. `identify_next_steps`
Baseado no report, sugerir próximas tarefas logicamente.
- Próximo passo no roadmap original
- Tarefas sugeridas com contexto
- Dependências entre tarefas
- Quem deve fazer (role do agente)

### 7. `get_agent_capability`
Consulta perfil e histórico de um agente antes de reconvocar ou redelegar.
- Histórico recente de tarefas
- Average quality score
- Rejection rate
- Recomendação: "viável reconvocar", "supervise de perto", etc.

---

## Integração com ReAct

Quando chief executa `agent_decision_engine.analyze_report()`, o motor ReAct tem acesso a todas essas 7 ferramentas.

### Exemplo de Reasoning de Chief

```
Pensamento: Recebi o report da Analyst sobre market validation.
            Preciso verificar: qualidade, gaps, riscos.

Ação: evaluate_report_quality
Entrada: {report_text, task_description, acceptance_criteria}
Observação: quality_score=85, completeness=90, risks=["amostra pequena"]

Pensamento: Score é bom. Vou comparar com objetivo original.

Ação: compare_vs_objective
Entrada: {task_id, report_conclusion, original_objective}
Observação: achievement_ratio=0.85, gap=["2 entrevistas faltam"]

Pensamento: Faltam 2 entrevistas. Consultei histórico corporativo?

Ação: consult_corporate_memory
Entrada: {query: "Market validation com <10 entrevistas é confiável?"}
Observação: precedents mostram que <10 entrevistas = alto risco falso positivo

Pensamento: Deveria reconvocar. Mas vou estimar custo-benefício.

Ação: estimate_cost_benefit
Entrada: {decision_options: {APPROVE, MODIFY}}
Observação: MODIFY tem melhor ROI (3 dias delay < 100% confiança)

Conclusão: Work is 85% complete. Recomendo MODIFICAR para 2 entrevistas
           extras. Risco baixo, confiança sobe de 72% para 90%.
```

---

## Implementação Técnica

### 1. Estender `reasoning_tools.py`
Adicionar 7 ferramentas novas ao dicionário de tools disponíveis.

### 2. Handlers (Offline, Determinístico)
Cada ferramenta tem um handler Python que:
- Não requer API externa
- Funciona offline (determinístico)
- Retorna JSON estruturado

### 3. Integração no Chief Decision Engine
```python
def analyze_report(task_id: UUID, report_session: ReasoningSession):
    chief = get_chief(task)
    
    # Preparar contexto com 7 ferramentas
    tools_available = [
        TOOLS["avaliar_qualidade_report"],
        TOOLS["comparar_vs_objetivo"],
        TOOLS["check_risks"],
        TOOLS["consult_corporate_memory"],
        TOOLS["estimate_cost_benefit"],
        TOOLS["identify_next_steps"],
        TOOLS["get_agent_capability"]
    ]
    
    # Chief raciocina com essas ferramentas
    reasoning = react_engine.run_task(
        session,
        agent=chief,
        request=TaskRequest(
            task=f"Analisar report de {task.assigned_to.name}",
            context={"tools": tools_available},
            max_steps=6  # Chief precisa de mais steps
        )
    )
    
    # Parser extrai decisão final
    decision = parse_decision(reasoning.conclusion)
    return decision
```

---

## Observações Importantes

### 1. **Determinismo**
Todas as ferramentas são determinísticas (sem API externa):
- Scoring usa regex/heurísticas
- Corporate memory é local
- Cost/benefit usa fórmulas simples

### 2. **Customização por Chief**
Cada chief pode ter pesos diferentes:
- CEO: valor 0.8 em risk management
- CTO: valor 0.9 em technical quality
- CFO: valor 0.95 em cost control

### 3. **Fallback Offline**
Se chief reasoning falhar (Ollama offline):
- Sistema cai em modo determinístico puro
- Usa regras simples: se score>80, APPROVE; se <60, REJECT

### 4. **Auditoria**
Cada uso de ferramenta é auditado com entrada, saída e timestamp.

---

## Estimativa de Esforço

- **Implementação das 7 ferramentas:** 8–10 horas
- **Integração com ReAct:** 4–6 horas
- **Testes (unit + integration):** 6–8 horas
- **Total ferramentas:** 18–24 horas

Parte da **Fase II (Backend)** e **VI (Testes)** do plano geral.
