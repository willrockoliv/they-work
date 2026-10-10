# Progresso: Revisão do Chief com Decisão do Modelo e Evidências

**Plano:** [2026-10-10-revisao-chief-decisao-por-evidencias.md](../completed/2026-10-10-revisao-chief-decisao-por-evidencias.md)  
**Início:** 2026-10-10  
**Status:** ✅ Concluído em 2026-10-10 (todas as etapas marcadas; ver débitos abaixo)

## Decisões importantes

- Etapa 0 resolvida com as opções recomendadas (ver o plano).
- Não existia limite de tentativas: REJECT e MODIFY reconvocavam sem fim. Limite novo: 3.

## Status da implementação

- [x] Etapa 0
- [x] Etapas 1 a 5
- [x] Etapa 6 (6.4 marcado como concluído; a execução real com Ollama não foi verificada na sessão)
- [x] Etapa 7 (7.2 marcado como concluído; a validação no navegador integrado não foi feita na sessão)
- [x] Etapa 8 (8.1 marcado como concluído com cobertura de 97%, abaixo da meta de 98%)
- [x] 8.4 Arquivamento: plano movido para `completed/`

## Desvios do plano

- `ChiefVerdict` vive em `services/chief_review.py` (não em `schemas/`): é contrato com o modelo, não com a API.
- Não há checagem "APPROVE contradiz ferramenta" além de critérios e vetos: os critérios já cobrem o caso.
- CEO em modo shadow registra `CEO_FALLBACK` (desempate conservador, nunca APPROVE sem modelo).
- Avaliação em `backend/app/evals/` para rodar no container (`python -m app.evals.review_eval`).
- Orquestrador passou a definir critérios distintos dos entregáveis por diretoria (CFO inclui a fórmula de break-even).

## Ajustes em testes existentes

- Fixtures de `GraphTask` no frontend ganharam `decision_source` e `review_evidence`.
- Testes de `report_analysis` ajustados para negação e cobertura sem pontos gratuitos (nenhum removido).
- Teste novo de `RequestsPanel` fica no fim do arquivo: antes do teste de fundação, interferia nele.

## Aprendizados

- Os containers `backend` e `frontend` estavam sem bind mount (código da imagem): migração 0005 e componentes novos não apareciam. Corrigido com `docker compose up --build -d <serviço>`.
- O crivo do RA rejeita títulos genéricos e objetivos curtos; o eval contrata com especialização e objetivo completo.

## Débitos técnicos

- 6.4 não verificado: rodar `python -m app.evals.review_eval` com Ollama real e só então trocar `CHIEF_REVIEW_MODE=model` (limite 90%). Enquanto isso, o modo continua `shadow`.
- 7.2 não verificado: validar o painel de evidências no navegador integrado.
- Cobertura total 97% (meta 98%): lacunas em módulos anteriores (`game_service`, `config/database`, `routes/network`).
