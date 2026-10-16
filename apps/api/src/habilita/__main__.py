"""Ponto de entrada de produção: `python -m habilita`.

Lê a porta de PORT (padrão 8000) e escuta em 0.0.0.0, como o Cloud Run exige.
Não precisa de shell para expandir variáveis (sem `sh -c` no contêiner).
"""

import uvicorn

from habilita.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "habilita.main:app",
        # 0.0.0.0 é necessário dentro do contêiner; quem limita o acesso é o Docker/Cloud Run.
        host="0.0.0.0",  # noqa: S104
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
