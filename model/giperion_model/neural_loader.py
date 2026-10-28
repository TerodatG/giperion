# GiperionModel/giperion_model/neural_loader.py                       v003
# Загрузка чекпоинтов нейросетевого движка и ответов намерений.
# Последнее изменение: компоненты загружаются независимо.

import json
import logging

import torch

from giperion_model.config import (
    DATA_DIR,
    MODELS_DIR,
    resolve_device,
)
from giperion_model.language.linear_intent import LinearIntentRouter
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


def load_classifier(
    device: torch.device,
) -> tuple[
    HybridTextClassifier,
    WordTokenizer,
    CharTokenizer,
    dict,
]:
    """Загружает CNN и оба токенизатора."""

    word_tokenizer = WordTokenizer.load(TOKENIZER_FILE)
    char_tokenizer = CharTokenizer.load(CHAR_TOKENIZER_FILE)
    checkpoint = torch.load(
        CLASSIFIER_FILE,
        map_location=device,
        weights_only=True,
    )
    classifier = HybridTextClassifier(
        vocab_size=word_tokenizer.vocab_size,
        char_vocab_size=char_tokenizer.vocab_size,
        num_classes=len(checkpoint["labels"]),
        pad_id=word_tokenizer.pad_id,
    ).to(device)

    classifier.load_state_dict(checkpoint["model_state"])
    classifier.eval()

    return classifier, word_tokenizer, char_tokenizer, checkpoint


def load_generator(
    device: torch.device,
    word_tokenizer: WordTokenizer | None,
) -> tuple[Seq2Seq | None, dict]:
    """Загружает seq2seq, если есть токенизатор и чекпоинт."""

    if word_tokenizer is None:
        return None, {}

    try:
        checkpoint = torch.load(
            SEQ2SEQ_FILE,
            map_location=device,
            weights_only=True,
        )
        generator = Seq2Seq(
            vocab_size=word_tokenizer.vocab_size,
            pad_id=word_tokenizer.pad_id,
            sos_id=word_tokenizer.sos_id,
            eos_id=word_tokenizer.eos_id,
            embed_dim=checkpoint["embed_dim"],
            hidden_size=checkpoint["hidden_size"],
        ).to(device)

        generator.load_state_dict(checkpoint["model_state"])
        generator.eval()

        return generator, checkpoint
    except Exception as error:  # noqa: BLE001 — без seq2seq
        LOGGER.warning(
            "Генератор ответов не загружен: %s",
            error,
        )

        return None, {}


def load_components() -> dict | None:
    """Собирает доступные компоненты движка.

    Роутер и CNN независимы: если CNN или seq2seq отсутствуют,
    движок продолжает отвечать намерениями по роутеру.
    """

    global LAST_ERROR

    device = _device()
    router = LinearIntentRouter.load()

    try:
        responses_by_tag = load_responses()
    except Exception as error:  # noqa: BLE001 — без ответов
        responses_by_tag = {}
        LOGGER.warning(
            "Ответы намерений не загружены: %s",
            error,
        )

    classifier = None
    word_tokenizer = None
    char_tokenizer = None
    labels: list[str] = []
    max_word_len = 0

    try:
        (
            classifier,
            word_tokenizer,
            char_tokenizer,
            checkpoint,
        ) = load_classifier(device)
        labels = checkpoint["labels"]
        max_word_len = checkpoint["max_len"]
    except Exception as error:  # noqa: BLE001 — без CNN
        LOGGER.warning(
            "CNN не загружена: %s",
            error,
        )

    generator, generator_checkpoint = load_generator(
        device,
        word_tokenizer,
    )

    if (
        classifier is None
        and router is None
        and generator is None
    ):
        LAST_ERROR = "нет ни роутера, ни CNN, ни генератора"
        LOGGER.warning("Нейросеть отключена: %s", LAST_ERROR)

        return None

    LAST_ERROR = ""

    return {
        "classifier": classifier,
        "router": router,
        "generator": generator,
        "word_tokenizer": word_tokenizer,
        "char_tokenizer": char_tokenizer,
        "labels": labels,
        "responses_by_tag": responses_by_tag,
        "device": device,
        "max_word_len": max_word_len,
        "max_src_len": generator_checkpoint.get(
            "max_src_len",
            0,
        ),
        "max_tgt_len": generator_checkpoint.get(
            "max_tgt_len",
            0,
        ),
    }
