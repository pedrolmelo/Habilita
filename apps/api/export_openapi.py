"""Script para exportar a especificação OpenAPI da API do Habilita."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Adiciona apps/api/src ao sys.path
SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

import yaml  # noqa: E402

from habilita.main import app  # noqa: E402


def main() -> None:
    schema = app.openapi()
    api_dir = Path(__file__).resolve().parent

    json_path = api_dir / "openapi.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        f.write("\n")

    yaml_path = api_dir / "openapi.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(schema, f, allow_unicode=True, sort_keys=False)

    print(f"Sucesso! OpenAPI exportado para {json_path} e {yaml_path}")
    print(f"Versão: {schema.get('info', {}).get('version')}")
    print(f"Total de rotas: {len(schema.get('paths', {}))}")


if __name__ == "__main__":
    main()
