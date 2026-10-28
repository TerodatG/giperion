# Giperion/tools/retrain_router.py                                   v001
# Переобучение роутера с проверкой и продвижением артефакта.
# Последнее изменение: первый вариант — train → eval → promote.

import argparse
import json
import shutil
from pathlib import Path

from config import MODELS_DIR
from giperion_model.training import build_dataset
from tools.eval_intent_model import main as evaluate
from tools.sync_router_passport import (
    DEFAULT_PASSPORTS,
    sync,
)
from tools.train_linear_intent import main as train

DEFAULT_TARGET = MODELS_DIR / "linear_intent.json"
DEFAULT_CANDIDATE = MODELS_DIR / "linear_intent_candidate.json"


def load_meta(path: Path) -> dict:
    """Читает meta артефакта или возвращает пустой словарь."""

    if not path.is_file():
        return {}

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    return document.get("meta", {})


def is_better(candidate: dict, current: dict) -> bool:
    """Кандидат не хуже по обеим метрикам и лучше хотя бы по одной."""

    if not current:
        return True

    candidate_top1 = float(candidate.get("eval_top1", 0.0))
    candidate_macro = float(candidate.get("eval_macro_f1", 0.0))
    current_top1 = float(current.get("eval_top1", 0.0))
    current_macro = float(current.get("eval_macro_f1", 0.0))

    return (
        candidate_top1 >= current_top1
        and candidate_macro >= current_macro
        and (
            candidate_top1 > current_top1
            or candidate_macro > current_macro
        )
    )


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """Разбирает ключи запуска."""

    parser = argparse.ArgumentParser(
        description="Переобучение и продвижение роутера.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET,
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=DEFAULT_CANDIDATE,
    )
    parser.add_argument(
        "--skip-dataset",
        action="store_true",
        help="не пересобирать classification.json",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="продвинуть кандидата даже при ухудшении",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Обучает кандидата, сравнивает и при улучшении продвигает."""

    args = parse_args(argv)

    if not args.skip_dataset:
        build_dataset.main()

    if train(["--output", str(args.candidate)]) != 0:
        print("Кандидат не прошёл порог обучения.")
        args.candidate.unlink(missing_ok=True)

        return 1

    if evaluate(["--artifact", str(args.candidate), "--fail"]) != 0:
        print("Кандидат не прошёл eval-гейт.")
        args.candidate.unlink(missing_ok=True)

        return 1

    candidate_meta = load_meta(args.candidate)
    current_meta = load_meta(args.target)
    better = is_better(candidate_meta, current_meta)

    print(
        "Кандидат: "
        f"top-1 {candidate_meta.get('eval_top1')}, "
        f"macro {candidate_meta.get('eval_macro_f1')}"
    )
    print(
        "Текущий: "
        f"top-1 {current_meta.get('eval_top1')}, "
        f"macro {current_meta.get('eval_macro_f1')}"
    )

    if not better and not args.force:
        print("Кандидат не лучше — артефакт не заменён.")
        args.candidate.unlink(missing_ok=True)

        return 0

    shutil.copy2(args.candidate, args.target)
    args.candidate.unlink(missing_ok=True)
    sync(args.target, DEFAULT_PASSPORTS)
    print(f"Артефакт обновлён: {args.target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
