# Plano de Implementação: Fase 2 - Estruturação Societária e Recursos Agênticos

**Objetivo:** Implementar as personas C-Level (CEO, CTO, CMO, CFO) e o framework de Recursos Agênticos (RA) com lógica de contratação, Banco de Talentos e seleção dinâmica de modelos.

**Status:** ✅ Concluído em 2026-10-03

**Bloqueante:** ~~Fase 1 (Motor Base)~~ — concluída

**Progresso:** [2026-10-03-fase-2-estruturacao-societaria-progress.md](../progress/2026-10-03-fase-2-estruturacao-societaria-progress.md)

---

## 1. Framework de Personas C-Level

- [x] Criar base de dados de Chief Personas:
  - [x] Tabela `chief_profiles` (armazenar perfis, raciocínio, objetivos)
  - [x] Tabela `chief_communications` (logs de decisões e comunicações)
- [x] Implementar classe base `ChiefAgent`:
  - [x] Estrutura de raciocínio por Chief
  - [x] Sistema de prioridades e objetivos
  - [x] Memória de contexto corporativo
- [x] Implementar cada Chief com sua especialidade:
  - [x] **CEO:** Visão macro, aprovação de orçamentos, mediação de conflitos
  - [x] **CTO:** Viabilidade técnica, arquitetura, segurança, testes
  - [x] **CMO:** Análise de mercado, concorrentes, persona do cliente, posicionamento
  - [x] **CFO:** Fluxo de caixa, precificação, monetização

## 2. Recursos Agênticos (RA) - Core Business Logic

- [x] Criar tabela `subagent_requests` (requisições de contratação do RA)
- [x] Implementar lógica de questionamento do RA:
  - [x] Validar requisições vagas
  - [x] Questionar Chief antes de prosseguir
  - [x] Estruturar requisitos detalhados
- [x] Criar sistema de "Prompt Engineering" para metaprompts:
  - [x] Função e escopo do subagente
  - [x] Ferramentas disponíveis
  - [x] Limitações e restrições
  - [x] Formato de output esperado

## 3. Banco de Talentos (Talent Bank)

- [x] Expandir tabela `talent_bank`:
  - [x] Armazenar prompts de subagentes criados
  - [x] Características e desempenho de cada perfil
  - [x] Histórico de tarefas executadas
- [x] Implementar busca em Banco de Talentos:
  - [x] Quando Chief solicita tarefa recorrente, resgatar perfil existente
  - [x] Reutilizar prompt em vez de gerar novo (economia de tokens)
- [x] Criar versionamento de perfis de subagentes
- [x] Implementar sistema de avaliação de subagentes (rating de desempenho)

## 4. Seleção Dinâmica de Modelos Ollama

- [x] Criar classificador de complexidade de tarefas:
  - [x] Entrada: descrição da tarefa
  - [x] Saída: nível de complexidade (simples, médio, complexo, crítico)
- [x] Mapear complexidade → modelo:
  - [x] **Simples:** Llama 3.2 3B (~2GB)
  - [x] **Médio:** Phi-4 Mini 3.8B (~2.3GB) ou Gemma 4 E4B (~3GB)
  - [x] **Complexo:** Qwen3 8B (~4.6GB)
  - [x] **Crítico:** DeepSeek R1 8B (~5GB)
- [x] Implementar lógica de fallback:
  - [x] Se modelo escolhido não tiver recursos, usar próximo menor
  - [x] Consultar "A Natureza" antes de alocar
- [x] Testes de seleção com diferentes cenários

## 5. Fluxo de Contratação de Subagentes

- [x] Criar pipeline completo:
  - [x] Chief solicita subagente → RA recebe requisição
  - [x] RA questiona se requisição for vaga
  - [x] RA consulta "A Natureza" (recursos disponíveis)
  - [x] "A Natureza" aprova/nega ou força downgrade de modelo
  - [x] RA busca em Banco de Talentos ou gera novo metaprompt
  - [x] Subagente é instanciado com modelo selecionado
  - [x] Subagente passa a reportar para Chief solicitante
- [x] Implementar reporte estruturado de subagentes para Chiefs
- [x] Criar sistema de "demissão" de subagentes (limpeza de memória)

## 6. Integração com "A Natureza"

- [x] Criar endpoint `POST /nature/audit-request`:
  - [x] RA envia requisição de contratação para auditoria
  - [x] "A Natureza" retorna aprovação/negação com justificativa narrativa
- [x] Implementar forçamento de downgrade de modelo:
  - [x] "A Natureza" pode forçar Llama 3.2 3B em caso crítico
  - [x] Registrar decisão em auditoria
- [x] Criar sistema de alertas estruturados:
  - [x] "Infraestrutura da empresa atingiu capacidade máxima"
  - [x] "Contratação bloqueada até conclusão de projeto atual"

## 7. Testes e Validação

- [x] Testes unitários para cada Chief:
  - [x] Validar raciocínio e tomada de decisão
  - [x] Validar comunicação entre Chiefs
- [x] Testes de fluxo de contratação:
  - [x] Requisição vaga → questionar RA
  - [x] Recursos insuficientes → bloquear ou downgrade
  - [x] Reutilização de Banco de Talentos
- [x] Testes de integração:
  - [x] Chief → RA → Natureza → Subagente
  - [x] Validar toda a cadeia de decisões
- [x] Teste de carga:
  - [x] Múltiplos Chiefs solicitando simultaneamente
  - [x] Comportamento do RA e Natureza sob pressão

## 8. Documentação e Preparação

- [x] Documentar personas e sua lógica de decisão em `docs/CHIEF-LOGIC.md`
- [x] Documentar Banco de Talentos e seleção de modelos em `docs/TALENT-BANK.md`
- [x] Documentar fluxo de contratação em `docs/HIRING-FLOW.md`
- [x] Atualizar `ARCHITECTURE.md` com diagrama de interações
- [x] Preparar contexto para Fase 3

---

## Dependências

```
← Fase 1 (Motor Base) [CONCLUÍDA]
Fase 2 (Sociedade) [CONCLUÍDA]
└→ Fase 3 (Observabilidade)
   └→ Fase 4 (Interface)
```
