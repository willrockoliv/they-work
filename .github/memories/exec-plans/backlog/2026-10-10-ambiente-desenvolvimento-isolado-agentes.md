# Plano de Implementacao: Ambiente de Desenvolvimento Isolado para Agentes

**Objetivo:** Permitir que agentes criem e validem ferramentas e aplicacoes Python/web em workspaces controlados, com recursos computacionais limitados e sem acesso direto ao host ou aos servicos internos.

**Status:** Planejado no backlog; depende das decisoes de seguranca e operacao da Etapa 0 antes de ir para `active/`.

## Contexto e estado atual

- O ciclo ReAct executa `ToolSpec.run` no processo do backend; as ferramentas registradas sao calculos, consultas e analises, sem escrita de arquivos ou execucao arbitraria de codigo.
- O Compose tem backend, banco, Redis, Ollama e frontend, mas nao tem um runner de desenvolvimento nem cotas de CPU, RAM, processos, disco ou tempo por execucao.
- A Natureza monitora recursos do host e limita contratacoes/modelos; ela ainda nao aloca ou contabiliza orcamentos de workloads de codigo.
- O plano [Navegador Isolado para os Agentes](2026-10-09-navegador-isolado-agentes.md) trata de navegacao web. Ele nao fornece um ambiente para criar, instalar, executar ou hospedar codigo dos agentes.
- O ambiente de desenvolvimento nao deve alterar o papel do RA: Chiefs pedem subagentes ao RA, e cada Chief continua responsavel pela tarefa e revisao.

## Escopo proposto

- Workspaces por projeto/tarefa, com ciclo de vida e isolamento entre agentes.
- Ferramentas controladas para criar/ler/listar arquivos, executar comandos permitidos, rodar testes e consultar logs/artefatos.
- Imagens de runtime fixadas para Python e aplicacoes web; dependencias precisam seguir uma politica explicita de cache/instalacao.
- Limites verificaveis de CPU, memoria, processos, armazenamento, concorrencia, duracao, rede e tamanho de saida.
- Artefatos e preview temporarios acessiveis ao observador, sem publicar servicos no host por padrao.
- Codigo e artefatos permanecem dados nao confiaveis: nao sao importados pelo backend nem promovidos para a aplicacao principal automaticamente.

Fora do escopo inicial: acesso irrestrito a internet, credenciais/secrets nos workspaces, deploy automatico, acesso ao socket Docker pelo backend ou pelos agentes, e execucao de workloads GPU.

## Decisoes de arquitetura propostas

| ADR | Decisao a avaliar | Direcao inicial |
|-----|-------------------|-----------------|
| ADR-027 | Fronteira de isolamento e modelo de ameacas | Executor separado do backend; escolher entre containers efemeros com endurecimento adicional ou uma fronteira mais forte (por exemplo, VM leve) antes de executar codigo nao confiavel. |
| ADR-028 | Orquestracao de execucoes | API tipada para criar, consultar, cancelar e limpar execucoes; nenhum socket Docker montado no backend ou no workload. O componente que orquestra workloads deve expor apenas operacoes permitidas e imagens aprovadas. |
| ADR-029 | Templates e dependencias | Imagens/versionamento fixos para Python e web; decidir se instalacoes usam somente caches/artefatos pre-aprovados ou um proxy de saida com allowlist. Rede desligada por padrao. |
| ADR-030 | Persistencia e isolamento de arquivos | Workspace por projeto, permissao minima, quota de disco e retencao configuravel; sem bind mount arbitrario do host. |
| ADR-031 | Orcamento da Natureza | Reservar recursos para SO, IDE e servicos existentes; limitar concorrencia e aplicar cotas por execucao com base em disponibilidade, sem confundir a leitura do host com a quota do container. |
| ADR-032 | Preview e observabilidade | Preview temporario somente por caminho controlado, sem porta publicada diretamente; status, consumo, logs truncados e artefatos vinculados a tarefa/agente. |
| ADR-033 | Promocao de artefatos | Artefatos sao revisados pelo Chief e exportados explicitamente; nunca executar ou incorporar automaticamente no backend. |

Os numeros ADR-027 a ADR-033 sao provisoes para discussao e devem ser conferidos com `docs/ARCHITECTURE.md` ao promover o plano.

## Etapa 0 — Decisoes de seguranca e produto _(sem dependencias)_

- [ ] 0.1 Definir ameacas cobertas e decidir se Docker endurecido e suficiente para codigo gerado por modelo ou se a v1 exige isolamento por VM/sandbox de kernel.
- [ ] 0.2 Escolher o componente de orquestracao e provar que o backend nao precisa de acesso ao socket Docker nem de privilegios de host.
- [ ] 0.3 Fixar cotas iniciais por workspace/execucao: CPU, memoria, PIDs, disco, duracao, concorrencia e limite de logs/artefatos; manter reserva explicita para o host e Ollama.
- [ ] 0.4 Definir runtimes e versoes suportadas para Python e web (incluindo como projetos frontend serao construidos/executados).
- [ ] 0.5 Definir politica de dependencias: offline com cache, catalogo aprovado ou saida mediada; nao permitir egress livre por padrao.
- [ ] 0.6 Definir quais arquivos podem persistir, por quanto tempo, quem pode ler/exportar, e como limpar workspaces cancelados ou abandonados.
- [ ] 0.7 Definir como o observador acessa previews sem expor portas dos workloads ao host/LAN e se isso depende do plano do navegador isolado.

## Etapa 1 — Prova de isolamento e cotas _(depende de 0)_

- [ ] 1.1 Construir uma prova tecnica minima com um workload Python e um workload web, usando imagens fixadas e usuario nao-root.
- [ ] 1.2 Aplicar limites de CPU/RAM/PIDs/tempo/armazenamento; testar encerramento por excesso, cancelamento e limpeza apos falha.
- [ ] 1.3 Verificar que workloads nao acessam host, socket Docker, `core`, Postgres, Redis, Ollama ou outros workspaces.
- [ ] 1.4 Verificar o comportamento de rede e instalacao de dependencias definido na Etapa 0, incluindo bloqueio de destinos privados se houver proxy de saida.
- [ ] 1.5 Registrar resultados e decidir se a fronteira e suficiente para prosseguir; nao promover para `active/` sem esse aceite.

## Etapa 2 — Servico de execucao _(depende de 1)_

- [ ] 2.1 Implementar API interna tipada para iniciar, consultar, cancelar e remover um workspace/execucao, validando proprietario e estado.
- [ ] 2.2 Implementar criacao de workspace isolado, selecao de template aprovado e execucao de comandos permitidos sem shell privilegiado.
- [ ] 2.3 Implementar quotas rigidas e timeouts, limites de concorrencia, saida truncada e coleta controlada de logs/artefatos.
- [ ] 2.4 Implementar preview web temporario atraves de proxy controlado, sem publicacao direta de portas nem rota para servicos internos.
- [ ] 2.5 Garantir limpeza idempotente de processos, containers, volumes temporarios e recursos associados.

## Etapa 3 — Integracao com backend, Natureza e agentes _(depende de 2)_

- [ ] 3.1 Adicionar settings versionados para habilitacao, limites e endpoint interno do executor; manter a feature desligada por padrao durante rollout.
- [ ] 3.2 Criar cliente injetavel para o executor e contratos de dominio/API; testes usam doubles locais, sem Docker ou rede real.
- [ ] 3.3 Expor ferramentas ReAct de escopo minimo para iniciar/retomar trabalho, manipular arquivos, rodar testes e ler resultado; validar caminho, tamanho e comando no limite do servico executor.
- [ ] 3.4 Associar workspace, execucoes e artefatos a tarefa e agente responsavel, preservando a hierarquia de supervisao da Fase 5.
- [ ] 3.5 Integrar a Natureza com disponibilidade e cotas de workload; bloquear, enfileirar ou reduzir execucoes quando a reserva ou os limites de concorrencia forem atingidos.
- [ ] 3.6 Registrar auditoria de criacao, comandos, encerramento, falha, limite excedido, preview e exportacao, sem armazenar secrets.
- [ ] 3.7 Emitir eventos de estado pelo barramento existente para o observador, com replay/retencao limitados e sem transmitir dados ilimitados.

## Etapa 4 — Interface do observador e fluxo de revisao _(depende de 3)_

- [ ] 4.1 Exibir estado, consumo, logs recentes, testes e artefatos da execucao vinculados ao agente/tarefa.
- [ ] 4.2 Exibir e encerrar previews temporarios sem abrir acesso direto ao container.
- [ ] 4.3 Permitir exportacao explicita de artefatos para revisao; manter separacao entre artefato gerado e codigo executado pelo produto.
- [ ] 4.4 Integrar a conclusao tecnica ao report do subagente para revisao pelo Chief, sem envolver o RA apos a contratacao.
- [ ] 4.5 Validar no Integrated Browser todas as telas alteradas.

## Etapa 5 — Validacao de seguranca e comportamento _(depende de 3 e 4)_

- [ ] 5.1 Testar quotas, timeout, cancelamento, concorrencia, limpeza, caminhos invalidos e saidas grandes.
- [ ] 5.2 Testar isolamento negativo contra host, servicos Compose, outros workspaces, metadata endpoints e rede nao autorizada.
- [ ] 5.3 Testar que prompt injection e comandos fornecidos pelo agente nao conseguem contornar a politica do executor.
- [ ] 5.4 Validar contratos, auditoria, eventos, permissao de preview/exportacao e ausencia de secrets nos logs.
- [ ] 5.5 Rodar gates de backend/frontend e testes integrados sem executar workloads com rede real na suite automatizada.
- [ ] 5.6 Fazer verificacao manual controlada de workloads Python e web e registrar uso maximo observado na maquina-alvo.

## Etapa 6 — Documentacao e rollout _(depende de 5)_

- [ ] 6.1 Atualizar `docs/ARCHITECTURE.md` com topologia, isolamento, fluxo, limites e ADRs aprovados.
- [ ] 6.2 Atualizar `docs/PRD.md` e `docs/SETUP.md` com capacidades, limites, politica de rede, configuracao e riscos residuais.
- [ ] 6.3 Atualizar `README.md` e exemplos de ambiente sem incluir credenciais.
- [ ] 6.4 Definir habilitacao gradual, limites padrao conservadores, procedimento de desligamento e retencao/limpeza.
- [ ] 6.5 Criar arquivo de progresso e atualizar o indice ao promover/concluir o plano.

## Criterios para promover a `active/`

- Ameaca e fronteira de isolamento aprovadas para codigo nao confiavel.
- Prova tecnica demonstra cotas efetivas, cancelamento e bloqueio de acesso ao host/servicos internos.
- Runtimes, politica de rede/dependencias, persistencia e cotas iniciais definidos.
- Integracao com a Natureza e preview tem responsaveis e contratos claros.

## Criterios de aceite da implementacao

- Um agente autorizado consegue criar ou alterar um projeto Python/web, executar testes e entregar artefatos sem executar codigo no processo do backend.
- Cada execucao respeita cotas de CPU, RAM, PIDs, disco, duracao, concorrencia e saida, com cancelamento e limpeza verificaveis.
- Workloads nao acessam host, socket Docker, banco, Redis, Ollama, outros workspaces ou internet fora da politica aprovada.
- O observador acompanha execucao e preview pelo canal controlado, e nenhum servico de workload fica publicado diretamente no host.
- Artefatos exigem revisao/exportacao explicita e nao sao promovidos automaticamente ao produto.
- A suite automatizada permanece offline e cobre os contratos e limites sem depender de Docker-in-Docker.

## Riscos e debitos a validar

- Containers compartilham o kernel do host; cotas de recursos nao equivalem a isolamento forte contra escape. A decisao de ameaca da Etapa 0 e bloqueadora.
- O cliente do Docker e um plano de controle de alto privilegio; nao pode estar acessivel ao backend nem a workloads e requer uma API estreita e auditada se escolhido.
- Builds web e instaladores de pacotes tendem a tentar acesso a rede; templates, caches e egress precisam seguir a mesma politica de seguranca.
- Preview de aplicacao gerada pode conter XSS ou tentar acessar servicos internos; usar origem isolada, proxy com allowlist de destinos e headers restritivos.
- O monitor atual da Natureza mede recursos do host, mas nao fornece por si so cotas ou contabilidade por workload; essas responsabilidades devem ser separadas e testadas.
- A rede `core`/`edge` e a exposicao de portas atuais devem ser revisadas ao desenhar a topologia final; este plano nao assume que a configuracao existente ja satisfaz o isolamento exigido.