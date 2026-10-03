---
name: plan-custom
description: Use quando criar, atualizar, concluir ou arquivar planos de implementacao em .github/memories/exec-plans. Define padrao de nome, checklist de tarefas, arquivo de progresso e manutencao do PLAN-INDEX.
agent: agent
argument-hint: Describe what you want to plan or research
---

# Gestao de planos de implementacao

Estas regras valem para arquivos em `.github/memories/exec-plans/`.

## Estrutura de diretorios
- `active/`: planos em andamento ou prontos para iniciar.
- `completed/`: planos finalizados.
- `progress/`: diarios de progresso e aprendizados durante a execucao.
- `archived/`: planos descontinuados, pausados por tempo indeterminado ou mantidos apenas para historico.

## Padrao de criacao
1. Crie o plano em `active/` com o nome `YYYY-MM-DD-nome-do-plano.md`.
2. Inicie com um objetivo curto e claro.
3. Liste tarefas em checklist:
   - `[ ]` tarefa pendente
   - `[x]` tarefa concluida
4. Sempre divida a implementação em fases e etapas claras, com dependências explícitas.

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
1. Quando todas as tarefas estiverem concluídas (`[x]`):
   * Mova o plano de `active/` para `completed/`
   * Atualize o arquivo de progresso com as implementações feitas, aprendizados e o que mais achar relevante
   * Atualize as documentações `ARCHITECTURE.md` e `README.md` para incluir as mudanças relevantes
2. Quando o plano for interrompido ou cancelado, mova para `archived/` e registre o motivo no arquivo de progresso

Exemplos:

```bash
mv .github/memories/exec-plans/active/2026-04-15-plano-inicial.md \
   .github/memories/exec-plans/completed/

mv .github/memories/exec-plans/active/2026-04-15-plano-inicial.md \
   .github/memories/exec-plans/archived/
```

## Atualizacao obrigatoria do indice
- Sempre atualize `PLAN-INDEX.md` quando criar, mover, concluir ou arquivar um plano.
- Inclua uma descricao curta do objetivo do plano.

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

