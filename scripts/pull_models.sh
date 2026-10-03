#!/usr/bin/env bash
# Baixa os 5 modelos open source do catálogo TheyWork no container Ollama.
#
# Uso:
#   ./scripts/pull_models.sh            # baixa todos
#   ./scripts/pull_models.sh llama3.2:3b phi4-mini:3.8b
#
# Total aproximado em disco: ~17 GB.
set -euo pipefail

CATALOG=(
  "llama3.2:3b"      # Meta      ~2.0 GB  - conversação, sumarização
  "phi4-mini:3.8b"   # Microsoft ~2.3 GB  - raciocínio lógico e matemático
  "gemma3n:e4b"      # Google    ~3.0 GB  - multimodal, thinking mode
  "qwen3:8b"         # Alibaba   ~4.6 GB  - codificação pesada
  "deepseek-r1:8b"   # DeepSeek  ~5.0 GB  - chain-of-thought, decisões vitais
)

MODELS=("${@:-}")
if [[ ${#MODELS[@]} -eq 0 || -z ${MODELS[0]} ]]; then
  MODELS=("${CATALOG[@]}")
fi

if ! docker compose ps --status running --services | grep -qx ollama; then
  echo "[pull_models] serviço 'ollama' não está rodando. Execute: docker compose up -d ollama" >&2
  exit 1
fi

for model in "${MODELS[@]}"; do
  echo "[pull_models] baixando ${model}..."
  docker compose exec -T ollama ollama pull "${model}"
done

echo "[pull_models] modelos presentes no repositório local:"
docker compose exec -T ollama ollama list
