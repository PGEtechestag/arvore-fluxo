from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from datajud_pipeline.config import load_settings
from datajud_pipeline.logging_config import configure_logging
from datajud_pipeline.pipeline import Pipeline, format_report


def resolve_path(path: Path | str, base_dir: Path | None = None) -> Path:
    """Resolve caminhos relativos primeiro no diretório atual e, em seguida, no projeto."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()

    current_dir_candidate = (Path.cwd() / candidate).resolve()
    if current_dir_candidate.exists():
        return current_dir_candidate

    base = (base_dir or ROOT).resolve()
    project_candidate = (base / candidate).resolve()
    if project_candidate.exists() or candidate.name == candidate.as_posix() or candidate.parts:
        return project_candidate
    return current_dir_candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Coleta processos da API Pública do DataJud em JSON.")
    parser.add_argument("--anos", type=int, nargs="+", help="Anos a coletar; substitui config.yaml.")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--entrada", type=Path, help="Pasta com JSONs de uma Vara ou subpastas de Varas.")
    parser.add_argument("--saida", type=Path, help="Pasta onde os JSONs DataJud serão gravados.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = configure_logging(ROOT / "pipeline.log")
    try:
        config_path = resolve_path(args.config, ROOT)
        settings = load_settings(config_path, args.anos)
        if args.entrada:
            settings = replace(settings, entrada=resolve_path(args.entrada, ROOT))
        if args.saida:
            settings = replace(settings, saida=resolve_path(args.saida, ROOT))
        result = Pipeline(settings).run()
        print(format_report(result))
        return 0
    except Exception as error:
        logger.exception("Pipeline encerrado com erro: %s", error)
        print(f"Erro: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())