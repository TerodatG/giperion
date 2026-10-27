# GiperionModel/giperion_model/neural_engine.py                       v005
# Нейросетевой движок: намерение классификатора и сгенерированный ответ.
# Последнее изменение: защита от повторов и ответов не по теме.

import random
import threading
from collections import Counter

import torch

from giperion_model.language.linear_intent import LinearIntentRouter
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

# Слишком длинный или зацикленный вывод тоже отбрасываем.
MAX_GENERATED_LEN = 240

# Если обратная проверка уверена в другом намерении — ответ не принимаем.
INTENT_CHECK_THRESHOLD = 0.6


def has_repetition(text: str) -> bool:
    """Ищет зацикленные трёхсловные повторы в сгенерированном тексте."""

    words = str(text or "").lower().split()

    if len(words) < 6:
        return False

    trigrams = [
        tuple(words[index : index + 3])
        for index in range(len(words) - 2)
    ]
    counts = Counter(trigrams)

    return max(counts.values(), default=0) > 1


class NeuralEngine:
    """Держит модели в памяти и отвечает на два вопроса:

    «какое это намерение?» (классификатор) и
    «что на это ответить?» (генератор или готовый ответ).
    """

    def __init__(
        self,
        classifier: HybridTextClassifier,
        generator: Seq2Seq | None,
        word_tokenizer: WordTokenizer,
        char_tokenizer: CharTokenizer,
        labels: list[str],
        responses_by_tag: dict[str, list[str]],
        device: torch.device,
        max_word_len: int,
        max_src_len: int,
        max_tgt_len: int,
        router: LinearIntentRouter | None = None,
    ) -> None:
        self.classifier = classifier
        self.router = router
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

        if self.router is not None:
            result = self.router.predict(text)

            if result is not None:
                return result

        return self._classify_cnn(text)

    def _gated_classification(
        self,
        message: str,
    ) -> tuple[str, float] | None:
        """Отсекает ответы ниже порога выбранной модели."""

        if self.router is not None:
            result = self.router.predict(message)

            if result is not None:
                label, confidence = result

                if confidence < self.router.threshold:
                    return None

                return label, confidence

        label, confidence = self._classify_cnn(message)

        if confidence < CONFIDENCE_THRESHOLD:
            return None

        return label, confidence

    def _classify_cnn(self, text: str) -> tuple[str, float]:
        """Классифицирует текст гибридной CNN."""

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

        if self.generator is None or not str(text or "").strip():
            return None

        if self.max_src_len <= 0 or self.max_tgt_len <= 0:
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

        if len(answer) > MAX_GENERATED_LEN:
            return None

        if has_repetition(answer):
            return None

        return answer

    def _matches_intent(self, answer: str, label: str) -> bool:
        """Проверяет, что сгенерированный ответ про то же намерение."""

        predicted, confidence = self.classify(answer)

        return (
            predicted == label
            or confidence < INTENT_CHECK_THRESHOLD
        )

    def reply_with_confidence(
        self,
        message: str,
    ) -> tuple[str, float] | None:
        """Ответ нейросети вместе с уверенностью или None."""

        if not str(message or "").strip():
            return None

        gated = self._gated_classification(message)

        if gated is None:
            return None

        label, confidence = gated
        responses = self.responses_by_tag.get(label)

        if not responses:
            return None

        if self.generator is not None and confidence >= GENERATION_THRESHOLD:
            generated = self.generate(message)

            if generated and self._matches_intent(
                generated,
                label,
            ):
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
_engine_lock = threading.Lock()


def reload_engine() -> None:
    """Сбрасывает кэш моделей, чтобы следующее обращение загрузило их заново."""

    global _engine, _engine_checked

    with _engine_lock:
        _engine = None
        _engine_checked = False


def get_neural_reply(
    message: str,
) -> tuple[str, float] | None:
    """Возвращает ответ нейросети и уверенность или None."""

    global _engine, _engine_checked

    if not _engine_checked:
        with _engine_lock:
            if not _engine_checked:
                _engine = _build_engine()
                _engine_checked = True

    if _engine is None:
        return None

    return _engine.reply_with_confidence(message)
