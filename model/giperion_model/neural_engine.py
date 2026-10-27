# Giperion/app/core/neural_engine.py                               v003
# Нейросетевой движок: намерение классификатора и сгенерированный ответ.
# Последнее изменение: загрузка чекпоинтов вынесена в neural_loader.

import random

import torch

from giperion_model.training.char_tokenizer import CharTokenizer
from giperion_model.training.model_charcnn import HybridTextClassifier
from giperion_model.training.model_seq2seq import Seq2Seq
from giperion_model.training.tokenizer import WordTokenizer

# Ниже порога диагнозу не верим — отвечать пусть правила.
CONFIDENCE_THRESHOLD = 0.45

# Выше порога отвечаем сгенерированным текстом,
# между порогами — готовым ответом намерения.
GENERATION_THRESHOLD = 0.6

# Слишком короткий вывод seq2seq не считаем ответом.
MIN_GENERATED_LEN = 6


class NeuralEngine:
    """Держит модели в памяти и отвечает на два вопроса:

    «какое это намерение?» (классификатор) и
    «что на это ответить?» (генератор или готовый ответ).
    """

    def __init__(
        self,
        classifier: HybridTextClassifier,
        generator: Seq2Seq,
        word_tokenizer: WordTokenizer,
        char_tokenizer: CharTokenizer,
        labels: list[str],
        responses_by_tag: dict[str, list[str]],
        device: torch.device,
        max_word_len: int,
        max_src_len: int,
        max_tgt_len: int,
    ) -> None:
        self.classifier = classifier
        self.generator = generator
        self.word_tokenizer = word_tokenizer
        self.char_tokenizer = char_tokenizer
        self.labels = labels
        self.responses_by_tag = responses_by_tag
        self.device = device
        self.max_word_len = max_word_len
        self.max_src_len = max_src_len
        self.max_tgt_len = max_tgt_len

    def classify(self, text: str) -> tuple[str, float]:
        """Возвращает тег намерения и уверенность (0..1)."""

        ids = self.word_tokenizer.encode(
            text,
        )[: self.max_word_len]

        ids = ids + [self.word_tokenizer.pad_id] * (
            self.max_word_len - len(ids)
        )

        chars = self.char_tokenizer.encode(text)

        tokens = torch.tensor(
            [ids],
            dtype=torch.long,
            device=self.device,
        )

        char_tensor = torch.tensor(
            [chars],
            dtype=torch.long,
            device=self.device,
        )

        with torch.no_grad():
            logits = self.classifier(
                tokens,
                char_tensor,
            )

            probabilities = torch.softmax(
                logits,
                dim=1,
            )

        index = int(
            probabilities.argmax(dim=1).item()
        )

        return (
            self.labels[index],
            float(probabilities[0, index].item()),
        )

    def generate(self, text: str) -> str | None:
        """Придумывает ответ seq2seq; None, если вывод не годится."""

        if not str(text or "").strip():
            return None

        ids = self.word_tokenizer.encode(
            text,
        )[: self.max_src_len]

        if not ids:
            return None

        ids = ids + [self.word_tokenizer.pad_id] * (
            self.max_src_len - len(ids)
        )

        source = torch.tensor(
            [ids],
            dtype=torch.long,
            device=self.device,
        )

        source_mask = (
            source == self.word_tokenizer.pad_id
        )

        with torch.no_grad():
            generated = self.generator.generate(
                source,
                source_mask,
                max_len=self.max_tgt_len,
            )

        # Собираем текст до первого </eos>.
        answer_ids: list[int] = []

        for index in generated[0].tolist():
            if index == self.word_tokenizer.eos_id:
                break

            answer_ids.append(index)

        answer = self.word_tokenizer.decode(
            answer_ids
        ).strip()

        if len(answer) < MIN_GENERATED_LEN:
            return None

        return answer

    def reply_with_confidence(
        self,
        message: str,
    ) -> tuple[str, float] | None:
        """Ответ нейросети вместе с уверенностью или None."""

        label, confidence = self.classify(message)

        if confidence < CONFIDENCE_THRESHOLD:
            return None

        responses = self.responses_by_tag.get(label)

        if not responses:
            return None

        if confidence >= GENERATION_THRESHOLD:
            generated = self.generate(message)

            if generated:
                return generated, confidence

        return random.choice(responses), confidence

    def reply(self, message: str) -> str | None:
        """Ответ нейросети или None — тогда работают правила."""

        result = self.reply_with_confidence(message)

        return result[0] if result else None


def _build_engine() -> NeuralEngine | None:
    """Собирает движок через загрузчик; при ошибке — None."""

    from giperion_model.neural_loader import load_components

    parts = load_components()

    if parts is None:
        return None

    return NeuralEngine(**parts)


_engine: NeuralEngine | None = None
_engine_checked = False


def reload_engine() -> None:
    """Сбрасывает кэш моделей, чтобы следующее обращение загрузило их заново."""

    global _engine, _engine_checked

    _engine = None
    _engine_checked = False


def get_neural_reply(
    message: str,
) -> tuple[str, float] | None:
    """Возвращает ответ нейросети и уверенность или None."""

    global _engine, _engine_checked

    if not _engine_checked:
        _engine = _build_engine()
        _engine_checked = True

    if _engine is None:
        return None

    return _engine.reply_with_confidence(message)

