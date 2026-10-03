# Plano de Implementação: Fase 2 - Estruturação Societária e Recursos Agênticos

**Objetivo:** Implementar as personas C-Level (CEO, CTO, CMO, CFO) e o framework de Recursos Agênticos (RA) com lógica de contratação, Banco de Talentos e seleção dinâmica de modelos.

**Status:** Planejado

**Bloqueante:** Fase 1 (Motor Base) deve estar 100% concluída

**Prazo Estimado:** ~3 semanas

---

## 1. Framework de Personas C-Level

- [ ] Criar base de dados de Chief Personas:
  - [ ] Tabela `chief_profiles` (armazenar perfis, raciocínio, objetivos)
  - [ ] Tabela `chief_communications` (logs de decisões e comunicações)
- [ ] Implementar classe base `ChiefAgent`:
  - [ ] Estrutura de raciocínio por Chief
  - [ ] Sistema de prioridades e objetivos
  - [ ] Memória de contexto corporativo
- [ ] Implementar cada Chief com sua especialidade:
  - [ ] **CEO:** Visão macro, aprovação de orçamentos, mediação de conflitos
  - [ ] **CTO:** Viabilidade técnica, arquitetura, segurança, testes
  - [ ] **CMO:** Análise de mercado, concorrentes, persona do cliente, posicionamento
  - [ ] **CFO:** Fluxo de caixa, precificação, monetização

## 2. Recursos Agênticos (RA) - Core Business Logic

- [ ] Criar tabela `subagent_requests` (requisições de contratação do RA)
- [ ] Implementar lógica de questionamento do RA:
  - [ ] Validar requisições vagas
  - [ ] Questionar Chief antes de prosseguir
  - [ ] Estruturar requisitos detalhados
- [ ] Criar sistema de "Prompt Engineering" para metaprompts:
  - [ ] Função e escopo do subagente
  - [ ] Ferramentas disponíveis
  - [ ] Limitações e restrições
  - [ ] Formato de output esperado

## 3. Banco de Talentos (Talent Bank)

- [ ] Expandir tabela `talent_bank`:
  - [ ] Armazenar prompts de subagentes criados
  - [ ] Características e desempenho de cada perfil
  - [ ] Histórico de tarefas executadas
- [ ] Implementar busca em Banco de Talentos:
  - [ ] Quando Chief solicita tarefa recorrente, resgatar perfil existente
  - [ ] Reutilizar prompt em vez de gerar novo (economia de tokens)
- [ ] Criar versionamento de perfis de subagentes
- [ ] Implementar sistema de avaliação de subagentes (rating de desempenho)

## 4. Seleção Dinâmica de Modelos Ollama

- [ ] Criar classificador de complexidade de tarefas:
  - [ ] Entrada: descrição da tarefa
  - [ ] Saída: nível de complexidade (simples, médio, complexo, crítico)
- [ ] Mapear complexidade → modelo:
  - [ ] **Simples:** Llama 3.2 3B (~2GB)
  - [ ] **Médio:** Phi-4 Mini 3.8B (~2.3GB) ou Gemma 4 E4B (~3GB)
  - [ ] **Complexo:** Qwen3 8B (~4.6GB)
  - [ ] **Crítico:** DeepSeek R1 8B (~5GB)
- [ ] Implementar lógica de fallback:
  - [ ] Se modelo escolhido não tiver recursos, usar próximo menor
  - [ ] Consultar "A Natureza" antes de alocar
- [ ] Testes de seleção com diferentes cenários

## 5. Fluxo de Contratação de Subagentes

- [ ] Criar pipeline completo:
  - [ ] Chief solicita subagente → RA recebe requisição
  - [ ] RA questiona se requisição for vaga
  - [ ] RA consulta "A Natureza" (recursos disponíveis)
  - [ ] "A Natureza" aprova/nega ou força downgrade de modelo
  - [ ] RA busca em Banco de Talentos ou gera novo metaprompt
  - [ ] Subagente é instanciado com modelo selecionado
  - [ ] Subagente passa a reportar para Chief solicitante
- [ ] Implementar reporte estruturado de subagentes para Chiefs
- [ ] Criar sistema de "demissão" de subagentes (limpeza de memória)

## 6. Integração com "A Natureza"

- [ ] Criar endpoint `POST /nature/audit-request`:
  - [ ] RA envia requisição de contratação para auditoria
  - [ ] "A Natureza" retorna aprovação/negação com justificativa narrativa
- [ ] Implementar forçamento de downgrade de modelo:
  - [ ] "A Natureza" pode forçar Llama 3.2 3B em caso crítico
  - [ ] Registrar decisão em auditoria
- [ ] Criar sistema de alertas estruturados:
  - [ ] "Infraestrutura da empresa atingiu capacidade máxima"
  - [ ] "Contratação bloqueada até conclusão de projeto atual"

## 7. Testes e Validação

- [ ] Testes unitários para cada Chief:
  - [ ] Validar raciocínio e tomada de decisão
  - [ ] Validar comunicação entre Chiefs
- [ ] Testes de fluxo de contratação:
  - [ ] Requisição vaga → questionar RA
  - [ ] Recursos insuficientes → bloquear ou downgrade
  - [ ] Reutilização de Banco de Talentos
- [ ] Testes de integração:
  - [ ] Chief → RA → Natureza → Subagente
  - [ ] Validar toda a cadeia de decisões
- [ ] Teste de carga:
  - [ ] Múltiplos Chiefs solicitando simultaneamente
  - [ ] Comportamento do RA e Natureza sob pressão

## 8. Documentação e Preparação

- [ ] Documentar personas e sua lógica de decisão em `docs/CHIEF-LOGIC.md`
- [ ] Documentar Banco de Talentos e seleção de modelos em `docs/TALENT-BANK.md`
- [ ] Documentar fluxo de contratação em `docs/HIRING-FLOW.md`
- [ ] Atualizar `ARCHITECTURE.md` com diagrama de interações
- [ ] Preparar contexto para Fase 3

---

## Dependências

```
← Fase 1 (Motor Base) [BLOQUEANTE]
Fase 2 (Sociedade)
└→ Fase 3 (Observabilidade)
   └→ Fase 4 (Interface)
```
