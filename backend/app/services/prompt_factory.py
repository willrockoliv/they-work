"""Fábrica de metaprompts do RA.

Converte uma requisição estruturada de um Chief no prompt de sistema do
subagente, cobrindo função, escopo, ferramentas, restrições e formato de saída.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import AgentRole, TaskComplexity

#: Formato de resposta exigido por nível de complexidade.
_OUTPUT_FORMAT: dict[TaskComplexity, str] = {
    TaskComplexity.TRIVIAL: "Responda em até 5 linhas, sem preâmbulo.",
    TaskComplexity.SIMPLE: "Responda em tópicos curtos, com uma conclusão objetiva ao final.",
    TaskComplexity.MODERATE: (
        "Estruture a resposta em seções: Contexto, Análise, Recomendação e Riscos."
    ),
    TaskComplexity.COMPLEX: (
        "Estruture a resposta em seções: Premissas, Alternativas Avaliadas, Solução Proposta, "
        "Plano de Execução e Riscos. Inclua trechos de código quando aplicável."
    ),
    TaskComplexity.CRITICAL: (
        "Explicite seu raciocínio passo a passo antes da conclusão e finalize com um bloco "
        "'DECISÃO' contendo a recomendação única e a justificativa."
    ),
}

#: Restrições impostas a todo subagente, independentemente do cargo.
BASE_CONSTRAINTS: tuple[str, ...] = (
    "Você é um colaborador temporário: atue apenas no escopo desta vaga.",
    "Não instancie, contrate ou delegue trabalho para outros agentes — isso é atribuição do RA.",
    "Não acesse a internet nem recursos externos; trabalhe apenas com o contexto fornecido.",
    "Se faltar informação para concluir a tarefa, pergunte ao seu gestor em vez de supor.",
    "Ao concluir, entregue um relatório final — ele é o único artefato que sobrevive à sua "
    "demissão.",
)


@dataclass(frozen=True, slots=True)
class MetapromptSpec:
    """Insumos estruturados para gerar o prompt de sistema de um subagente."""

    job_title: str
    objective: str
    complexity: TaskComplexity
    reports_to: AgentRole
    deliverables: tuple[str, ...] = field(default_factory=tuple)
    tools: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    specialization: str = ""


def build_metaprompt(spec: MetapromptSpec) -> str:
    """Monta o prompt de sistema completo do subagente."""
    sections: list[str] = [
        f"# Cargo: {spec.job_title}",
        (
            f"Você é um subagente temporário da TheyWork, contratado pelo "
            f"{spec.reports_to.value} e reportando diretamente a ele."
        ),
        "",
        "## Objetivo",
        spec.objective.strip() or "Executar a tarefa designada pelo gestor solicitante.",
    ]

    if spec.specialization:
        sections += ["", "## Especialização", spec.specialization.strip()]

    sections += ["", "## Entregáveis", *_bullets(spec.deliverables, "Relatório final da tarefa.")]
    sections += [
        "",
        "## Ferramentas disponíveis",
        *_bullets(spec.tools, "Nenhuma ferramenta externa: use apenas raciocínio e o contexto."),
    ]
    sections += [
        "",
        "## Limitações e restrições",
        *_bullets(BASE_CONSTRAINTS + tuple(spec.constraints)),
    ]
    sections += ["", "## Formato de saída esperado", _OUTPUT_FORMAT[spec.complexity]]

    return "\n".join(sections).strip()


def _bullets(items: tuple[str, ...], fallback: str | None = None) -> list[str]:
    cleaned = [item.strip() for item in items if item.strip()]
    if not cleaned:
        return [f"- {fallback}"] if fallback else []
    return [f"- {item}" for item in cleaned]
