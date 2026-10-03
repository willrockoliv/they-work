---
name: architecture-documentation
description: Instruções para manutenção, atualização e validação do arquivo .github/ARCHITECTURE.md como referência rápida de contexto para agentes
agent: agent

---

# Manutenção e Atualização da ARCHITECTURE.md

## Visão Geral

[ARCHITECTURE.md](../../docs/ARCHITECTURE.md) serve como **referência rápida e compartilhada** do projeto para que agentes e desenvolvedores se contextualizem rapidamente antes de iniciarem implementações. Não é um documento de design detalhado, mas sim um **mapa mental vivo** da estrutura, fluxos críticos e convenções.

**Objetivo:**
- Prover contexto arquitetural e estrutural em um único arquivo
- Evitar desorientação de agentes ao iniciar tarefas
- Documentar fluxos críticos, modelos de dados e padrões visuais (diagramas)
- Manter alinhamento entre referência arquitetural e implementação real

**Quando atualizar:**
- Mudanças estruturais (novas pastas, serviços ou routers)
- Alterações em modelos ORM ou schemas críticos
- Mudanças em fluxos de negócio ou integrações
- Atualizações em padrões reconhecidos ou convenções
- Adição de novos providers ou tecnologias
- Alterações em Docker Compose ou infraestrutura

---

## Estrutura Esperada da ARCHITECTURE.md

O arquivo segue a estrutura abaixo. Mantenha as seções na ordem e o nível de detalhe conforme descrito:

| Seção | Tipo | Propósito | Nível de Detalhe |
|-------|------|----------|------------------|
| **1. Visão Geral** | Texto + Bulleted | Introdução, stack, propósito | Alto nível (2–3 linhas por item) |
| **2. Estrutura de Pastas** | Code block + Texto | Mapa de pastas | Até 2 níveis de profundidade |
| **3. Backend** | Subsecções | Modelos, rotas, serviços, concorrência | Texto + bullets; evitar código completo |
| **4. Frontend** | Subsecções | Páginas, componentes, API client, temas | Texto + bullets; evitar detalhes de código |
| **5. Convenções para IA** | Bullets + Links | Referências para agentes | Pontos-chave rápidos |
| **6. Fluxos Críticos** | Texto + Sequence/Flowchart Mermaid | Onboarding, ingestão, análise, auth | 1–2 fluxos por seção |
| **7. Diagramas** | Mermaid (flowchart, sequence, ER, etc.) | Visão da arquitetura em vários ângulos | Máximo 1 diagrama por padrão arquitetural |
| **8. RFCs** | Bulleted links | Referência a RFCs vigentes | Apenas títulos + links |
| **9. Referências Rápidas** | Bullets de paths | Caminhos importantes e exemplos | Paths + breve descrição |
| **10. Atualização Obrigatória** | Texto | Lembrete de quando/como atualizar | Manter padrão |

---

## Trigger para Atualização

### Cenários Que Exigem Atualização

✅ **FAÇA UPDATE:**
1. Novo router, serviço ou modelo adicionado
2. Fluxo de negócio alterado (ex: novo passo no onboarding)
3. Novo provider integrado (ex: novo adapter WhatsApp)
4. Estrutura de pasta reorganizada
5. Mudança em infraestrutura Docker Compose (novo serviço, volumes, variáveis)
6. Novo padrão de concorrência ou tratamento de erro adotado
7. RFC nova or existente alterada

❌ **NÃO FAÇA UPDATE:**
- Correção de bugs sem mudança estrutural
- Refatoração interna sem mudança de responsabilidade
- Ajustes de CSS ou UI minor
- Mudanças em comentários ou docstrings dentro de funções
- Revisão de um arquivo isolado sem impacto em fluxos

### Checklist de Validação Pós-Atualização

Após atualizar ARCHITECTURE.md, valide:

- [ ] Todos os paths relativos existem (use `ls` para confirmar)
- [ ] Nenhuma linha de código copy-pasta; apenas referências conceituais
- [ ] Diagramas Mermaid renderizam sem erro (valide sintaxe em editor Markdown)
- [ ] Links internos (ex: `rfcs/002-...`) apontam para arquivos que existem
- [ ] Nenhuma informação contradiz implementação atual (leia o código se duvidar)
- [ ] Seções 1–5 cobertas e alinhadas
- [ ] Fluxos críticos (seção 6) correspondem a rotas/serviços reais
- [ ] RFCs listadas são vigentes (remova as obsoletas)

---

## Skills para Manutenção e Atualização

Use as skills a seguir conforme necessário. **Não invoque skills automaticamente**, apenas quando o tipo de mudança indicar.

### 1. **architecture-blueprint-generator** (`.github/skills/architecture-blueprint-generator/SKILL.md`)

**Quando usar:**
- Você está fazendo mudança estrutural significativa e quer re-analisar toda a arquitetura
- Novo provider ou serviço adicionado, e você quer garantir que a visão geral está correta
- Adoção de novo padrão arquitetural (ex: mudança de monolito para microserviços)

**O que faz:**
- Analisa codebase e auto-detecta stacks, padrões, camadas e dependências
- Gera visão consolidada de responsabilidades, camadas, fluxos e patterns
- Documenta implementações concretas, decision records e extensibility points

**Saída esperada:**
- Atualização de seções 1–5 da ARCHITECTURE.md (visão geral, estrutura, backend, frontend)
- Confirmação de que modelos, rotas e serviços estão devidamente mapeados

**Como usar:**
```
Carregue o skill e peça: 
"Analise a arquitetura atual do projeto e revise as seções 1–5 de ARCHITECTURE.md, 
confirmando que modelos, rotas, serviços e fluxos estão alinhados com a implementação."
```

---

### 2. **mermaid-diagrams** (`.github/skills/mermaid-diagrams/SKILL.md`)

**Quando usar:**
- Fluxo crítico mudou (ex: novo passo no onboarding)
- Novo diagrama necessário para explicar padrão (ex: novo adapter WhatsApp)
- Diagrama existente ficou desatualizado e precisa ser redesenhado

**O que faz:**
- Cria ou atualiza diagramas Mermaid (flowchart, sequence, ER, class diagrams)
- Valida sintaxe e renderização
- Documentação de padrões visuais e fluxos

**Saída esperada:**
- Blocos de código Mermaid válidos inseridos na seção 7 (Diagramas)
- Diagramas com legenda clara e referência cruzada para texto

**Como usar:**
```
Carregue o skill e peça: 
"Crie um diagrama Mermaid sequence para o fluxo de análise de lead 
e insira na seção 7 de ARCHITECTURE.md."
```

---

### 3. **code-tour** (`.github/skills/code-tour/SKILL.md`)

**Quando usar:**
- Você quer criar um tour interativo de arquitetura para new joiners
- Você quer documentar um fluxo crítico com referências ao código real
- Você quer criar tours para agentes se contextualizarem antes de trabalhar

**O que faz:**
- Gera arquivos `.tour` JSON (CodeTour) que linkam diretamente a arquivos/linhas
- Persona-targeted walkthroughs (ex: "new-joiner", "architect")
- Narrativa guiada com passos executáveis

**Saída esperada:**
- Arquivo `.tours/architecture-overview.tour` (ou similar)
- Referência cruzada em ARCHITECTURE.md: "Veja o tour `architecture-overview` para walkthrough interativo"

**Como usar:**
```
Carregue o skill e peça: 
"Crie um CodeTour 'architecture-overview' para a persona 'new-joiner' 
que explique a estrutura, backend, frontend e fluxo crítico de onboarding."
```

---

## Processo de Atualização

### Passo 1: Identificar o Escopo de Mudança

Classifique a mudança em uma categoria:
- **Estrutural:** nova pasta, router, serviço ou modelo
- **Fluxo:** mudança em sequência de operações (ex: novo passo em onboarding)
- **Integração:** novo provider ou dependência externa
- **Infraestrutura:** Docker Compose, variáveis de ambiente, banco de dados

### Passo 2: Determinar Qual Seção Atualizar

Use a tabela abaixo para localizar seções:

| Mudança | Seção(ões) |
|---------|-----------|
| Nova pasta ou reorganização | Seção 2 (Estrutura) |
| Novo modelo ORM | Seção 3.1 (Modelos) |
| Novo router | Seção 3.2 (Rotas e Serviços) |
| Novo serviço | Seção 3.2 (Rotas e Serviços) |
| Novo padrão de concorrência | Seção 3.3 (Concorrência) |
| Nova página ou componente | Seção 4.1–4.2 (Frontend) |
| Novo provider | Seção 3.2 (Rotas e Serviços), Diagramas (Seção 7) |
| Fluxo novo/alterado | Seção 6 (Fluxos Críticos), Diagramas (Seção 7) |
| RFC novo/alterado | Seção 8 (RFCs) |

### Passo 3: Realizar a Atualização

**Abordagem rápida (< 5 linhas de mudança):**
1. Edite diretamente ARCHITECTURE.md
2. Valide paths e links
3. Testar renderização Mermaid (se houver)

**Abordagem com skill (mudança estrutural):**
1. Carregue `architecture-blueprint-generator`
2. Peça re-análise da arquitetura
3. Revise a saída sugerida
4. Integre à ARCHITECTURE.md

**Abordagem com diagrama (fluxo novo):**
1. Carregue `mermaid-diagrams`
2. Descreva o fluxo e peça diagrama Mermaid
3. Copie o diagrama para a seção apropriada (Seção 6 ou 7)

---

## Convenções de Escrita

Para manter consistência, siga estas convenções:

### Nível de Detalhe
- **Visão Geral (Seção 1):** 1–2 linhas por item
- **Estrutura (Seção 2):** Apenas pastas principais, até 2 níveis
- **Backend (Seção 3):** Função, responsabilidade, padrão; evitar código completo
- **Frontend (Seção 4):** Componentes chave, fluxo; evitar detalhe de CSS
- **Diagramas (Seção 7):** Máximo 1 diagrama por conceito arquitetural

### Exemplos de Referências Cruzadas
- Linke para RFCs: `[RFC 002](../rfcs/002-frontend-redesign.md)`
- Linke para arquivos: `[app/models/models.py](../../app/models/models.py)` (use markdown link)
- Não copie path/código — apenas referencie

### Diagramas
- Use **Mermaid** para todos os diagramas (flowchart, sequence, ER, class)
- Adicione **classDef** e cores para melhor legibilidade
- Inclua legenda ou texto explanatório abaixo do diagrama
- Valide sintaxe em VS Code (extensão Markdown Preview Enhanced ou similar)

---

## Checklist Final

Antes de considerar a atualização completa:

- [ ] Mudança identificada e classificada (estrutural, fluxo, integração, infraestrutura)
- [ ] Seção(ões) correspondente(s) localizada(s)
- [ ] Atualização realizada (manual ou via skill)
- [ ] Todos os paths verificados com `ls`
- [ ] Diagramas Mermaid validados (sem erros de sintaxe)
- [ ] Links internos testados
- [ ] Sem copypasta de código — apenas referências conceituais
- [ ] Alinhamento com RFCs vigentes confirmado

---

## Referências

- **Skills:**
  - [architecture-blueprint-generator](../skills/architecture-blueprint-generator/SKILL.md)
  - [mermaid-diagrams](../skills/mermaid-diagrams/SKILL.md)
  - [code-tour](../skills/code-tour/SKILL.md)

- **Memórias:**
  - [Planos de Execução](../memories/exec-plans/PLAN-INDEX.md)

- **Documentos Principais:**
  - [PRD.md](../../docs/PRD.md)
  - [ARCHITECTURE.md](../../docs/ARCHITECTURE.md)
  - [README.md](../../README.md)
