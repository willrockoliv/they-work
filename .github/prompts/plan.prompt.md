---
name: plan-custom
description: Use quando criar, atualizar, concluir ou arquivar planos de implementacao em .github/memories/exec-plans. Define padrao de nome, checklist de tarefas, arquivo de progresso e manutencao do PLAN-INDEX.
agent: agent
argument-hint: Describe what you want to plan or research
---

# Gestao de planos de implementacao

Estas regras valem para arquivos em `.github/memories/exec-plans/`.

## Estrutura de diretorios
- `backlog/`: planos futuros, ideias e requisitos não planejados ainda.
- `active/`: planos em andamento ou prontos para iniciar.
- `completed/`: planos finalizados.
- `progress/`: diarios de progresso e aprendizados durante a execucao.
- `archived/`: planos descontinuados, pausados por tempo indeterminado ou mantidos apenas para historico.

## Padrao de criacao
1. **Para planos planejados:** Crie em `backlog/` com o nome `YYYY-MM-DD-nome-do-plano.md` (ideias, pesquisa, requisitos não detalhados).
2. **Para planos prontos para execução:** Mova para `active/` quando as tarefas estiverem bem definidas e dependências claras.
3. Inicie com um objetivo curto e claro.
4. Liste tarefas em checklist:
   - `[ ]` tarefa pendente
   - `[x]` tarefa concluida
5. Sempre divida a implementação em fases e etapas claras, com dependências explícitas.

## Regras de execucao
1. Execute uma tarefa por vez, na ordem do plano, salvo justificativa explicita no proprio plano.
2. Marque cada item como `[x]` assim que concluir.
3. Mantenha um arquivo de progresso em `progress/` com o mesmo nome-base do plano e sufixo `-progress.md`.
4. Registre no progresso:
   - status da implementacao
   - aprendizados
   - debitos tecnicos
   - decisoes importantes

## Conclusao e arquivamento
1. **Quando plano está pronto para execução:** Mova de `backlog/` para `active/`
2. **Quando todas as tarefas estiverem concluídas (`[x]`):**
   * Mova o plano de `active/` para `completed/`
   * Atualize o arquivo de progresso com as implementações feitas, aprendizados e o que mais achar relevante
   * Atualize as documentações `ARCHITECTURE.md` e `README.md` para incluir as mudanças relevantes
3. **Quando o plano for interrompido ou cancelado:** Mova para `archived/` e registre o motivo no arquivo de progresso

Exemplos:

```bash
# Promover plano do backlog para ativo
mv .github/memories/exec-plans/backlog/2026-04-15-plano-inicial.md \
   .github/memories/exec-plans/active/

# Concluir um plano
mv .github/memories/exec-plans/active/2026-04-15-plano-inicial.md \
   .github/memories/exec-plans/completed/

# Arquivar um plano
mv .github/memories/exec-plans/active/2026-04-15-plano-inicial.md \
   .github/memories/exec-plans/archived/
```

## Atualizacao obrigatoria do indice
- Sempre atualize `PLAN-INDEX.md` quando criar, mover, concluir, arquivar ou atualizar um plano.
- Inclua uma descricao curta do objetivo do plano.
- Mantenha os planos agrupados por diretório (backlog, active, completed, archived).

## Boas praticas
- Revise planos em `completed/` e `archived/` antes de criar um novo para evitar retrabalho.
- Mantenha o idioma em portugues.
- Use textos curtos, objetivos e verificaveis.
- para diagramas, utilize a skill `.github/skills/mermaid-diagrams/SKILL.md`

## Exemplo minimo

```markdown
# Plano de Implementacao: Nova Feature X

Objetivo: Implementar a feature X conforme PRD.

- [ ] Criar modelagem inicial
- [ ] Implementar endpoint
- [ ] Escrever testes unitarios
- [x] Configurar CI
```

