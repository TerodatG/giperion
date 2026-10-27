# Giperion/app/core/neural_loader.py                               v001
# Загрузка чекпоинтов нейросетевого движка и ответов намерений.
# Последнее изменение: выделено из neural_engine.

import json
import logging

import torch

from giperion_model.config import DATA_DIR, DEVICE, MODELS_DIR
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

    if DEVICE == "cpu":
        return torch.device("cpu")

    if DEVICE == "cuda":
        return torch.device("cuda")

    return torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )


def load_responses() -> dict[str, list[str]]:
    """Собирает ответы намерений: тег → список ответов."""

    with INTENTS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        document = json.load(file)

    intents = document.get("intents", [])

    return {
        intent["tag"]: intent.get("responses", [])
        for intent in intents
        if isinstance(intent.get("tag"), str)
    }


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

        # --- Генератор ответов ---
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

        LAST_ERROR = ""

        return {
            "classifier": classifier,
            "generator": generator,
            "word_tokenizer": word_tokenizer,
            "char_tokenizer": char_tokenizer,
            "labels": classifier_checkpoint["labels"],
            "responses_by_tag": load_responses(),
            "device": device,
            "max_word_len": classifier_checkpoint["max_len"],
            "max_src_len": generator_checkpoint["max_src_len"],
            "max_tgt_len": generator_checkpoint["max_tgt_len"],
        }
    except Exception as error:
        # Нейросеть — усиление, а не обязательное условие:
        # без моделей бот продолжает работать на правилах.
        LAST_ERROR = str(error)
        LOGGER.warning("Нейросеть отключена: %s", error)

        return None
