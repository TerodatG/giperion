# GiperionModel/giperion_model/neural_loader.py                       v001
# Загрузка чекпоинтов нейросетевого движка и ответов намерений.
# Последнее изменение: выделено из neural_engine.

import json
import logging

import torch

from giperion_model.config import (
    DATA_DIR,
    MODELS_DIR,
    resolve_device,
)
from giperion_model.training.char_tokenizer import (
    CHAR_TOKENIZER_FILE,
    CharTokenizer,
)
from giperion_model.training.model_charcnn import HybridTextClassifier
from giperion_model.training.model_seq2seq import Seq2Seq
from giperion_model.training.tokenizer import TOKENIZER_FILE, WordTokenizer

CLASSIFIER_FILE = MODELS_DIR / "hybrid.pt"
SEQ2SEQ_FILE = MODELS_DIR / "seq2seq.pt"
INTENTS_FILE = DATA_DIR / "intents.json"
LAST_ERROR = ""
LOGGER = logging.getLogger(__name__)


def _device() -> torch.device:
    """Устройство из GIPERION_DEVICE: auto, cpu или cuda."""

    return resolve_device()


def load_responses() -> dict[str, list[str]]:
    """Собирает ответы намерений: тег → список ответов.

    Поддерживает оба формата intents.json: объект с ключом intents
    и простой список намерений.
    """

    with INTENTS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        document = json.load(file)

    if isinstance(document, list):
        intents = document
    elif isinstance(document, dict):
        intents = document.get("intents", [])
    else:
        raise ValueError(
            "Неподдерживаемый формат intents.json."
        )

    if not isinstance(intents, list):
        raise ValueError(
            "В intents.json нет списка intents."
        )

    responses_by_tag: dict[str, list[str]] = {}

    for intent in intents:
        if not isinstance(intent, dict):
            continue

        tag = intent.get("tag")

        if not isinstance(tag, str) or not tag.strip():
            continue

        raw_responses = intent.get("responses")

        if not isinstance(raw_responses, list):
            continue

        responses = [
            response.strip()
            for response in raw_responses
            if isinstance(response, str) and response.strip()
        ]

        if responses:
            responses_by_tag[tag] = responses

    return responses_by_tag


def get_last_error() -> str:
    """Причина последней неудачной загрузки нейросети."""

    return LAST_ERROR


def load_components() -> dict | None:
    """Собирает компоненты движка; при ошибке — None."""

    global LAST_ERROR

    try:
        device = _device()

        word_tokenizer = WordTokenizer.load(
            TOKENIZER_FILE
        )

        char_tokenizer = CharTokenizer.load(
            CHAR_TOKENIZER_FILE
        )

        # --- Классификатор намерений ---
        classifier_checkpoint = torch.load(
            CLASSIFIER_FILE,
            map_location=device,
            weights_only=True,
        )

        classifier = HybridTextClassifier(
            vocab_size=word_tokenizer.vocab_size,
            char_vocab_size=char_tokenizer.vocab_size,
            num_classes=len(
                classifier_checkpoint["labels"]
            ),
            pad_id=word_tokenizer.pad_id,
        ).to(device)

        classifier.load_state_dict(
            classifier_checkpoint["model_state"]
        )

        classifier.eval()

        # --- Генератор ответов (необязателен) ---
        generator = None
        generator_checkpoint = {}

        try:
            generator_checkpoint = torch.load(
                SEQ2SEQ_FILE,
                map_location=device,
                weights_only=True,
            )

            generator = Seq2Seq(
                vocab_size=word_tokenizer.vocab_size,
                pad_id=word_tokenizer.pad_id,
                sos_id=word_tokenizer.sos_id,
                eos_id=word_tokenizer.eos_id,
                embed_dim=generator_checkpoint["embed_dim"],
                hidden_size=generator_checkpoint[
                    "hidden_size"
                ],
            ).to(device)

            generator.load_state_dict(
                generator_checkpoint["model_state"]
            )

            generator.eval()
        except Exception as error:  # noqa: BLE001 — без seq2seq
            generator = None
            generator_checkpoint = {}
            LOGGER.warning(
                "Генератор ответов не загружен: %s",
                error,
            )

        try:
            responses_by_tag = load_responses()
        except Exception as error:  # noqa: BLE001 — без ответов
            responses_by_tag = {}
            LOGGER.warning(
                "Ответы намерений не загружены: %s",
                error,
            )

        LAST_ERROR = ""

        return {
            "classifier": classifier,
            "generator": generator,
            "word_tokenizer": word_tokenizer,
            "char_tokenizer": char_tokenizer,
            "labels": classifier_checkpoint["labels"],
            "responses_by_tag": responses_by_tag,
            "device": device,
            "max_word_len": classifier_checkpoint["max_len"],
            "max_src_len": generator_checkpoint.get(
                "max_src_len",
                0,
            ),
            "max_tgt_len": generator_checkpoint.get(
                "max_tgt_len",
                0,
            ),
        }
    except Exception as error:
        # Нейросеть — усиление, а не обязательное условие:
        # без моделей бот продолжает работать на правилах.
        LAST_ERROR = str(error)
        LOGGER.warning("Нейросеть отключена: %s", error)

        return None
