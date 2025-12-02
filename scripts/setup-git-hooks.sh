#!/usr/bin/env bash
set -euo pipefail

# Configura git para usar los hooks versionados en .githooks
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Asegurar permisos de ejecución en el hook commit-msg
chmod +x .githooks/commit-msg

# Apuntar git a la carpeta .githooks a nivel de repo
git config core.hooksPath .githooks

echo "Git hooks configurados: core.hooksPath -> .githooks"
echo "Prueba: realiza un commit con un mensaje que cumpla Conventional Commits."
