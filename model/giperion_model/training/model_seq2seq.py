# GiperionModel/giperion_model/training/model_seq2seq.py              v001
# Генеративная модель ответов Giperion: энкодер, внимание, декодер.
# Последнее изменение: первый вариант — своё внимание Бахданау на GRU.

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils.rnn import (
    pack_padded_sequence,
    pad_packed_sequence,
)


class BahdanauAttention(nn.Module):
    """Внимание: декодер решает, на какие слова вопроса смотреть.

    Оценка слова = v · tanh(W_enc · слово + W_dec · состояние).
    Чем больше оценка, тем сильнее декодер «смотрит» на это слово,
    формируя следующий кусок ответа.
    """

    def __init__(
        self,
        hidden_size: int,
        attention_size: int = 128,
    ) -> None:
        super().__init__()

        self.encoder_projection = nn.Linear(
            hidden_size,
            attention_size,
            bias=False,
        )

        self.decoder_projection = nn.Linear(
            hidden_size,
            attention_size,
            bias=False,
        )

        self.score_projection = nn.Linear(
            attention_size,
            1,
            bias=False,
        )

    def forward(
        self,
        decoder_hidden: torch.Tensor,
        encoder_outputs: torch.Tensor,
        source_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Возвращает контекст (batch, hidden) и веса (batch, src_len)."""

        energy = torch.tanh(
            self.encoder_projection(encoder_outputs)
            + self.decoder_projection(
                decoder_hidden
            ).unsqueeze(1)
        )

        scores = self.score_projection(energy).squeeze(2)

        # Паддинг не должен привлекать внимания.
        scores = scores.masked_fill(
            source_mask,
            float("-inf"),
        )

        weights = F.softmax(scores, dim=1)

        context = torch.bmm(
            weights.unsqueeze(1),
            encoder_outputs,
        ).squeeze(1)

        return context, weights


class Seq2Seq(nn.Module):
    """Энкодер читает вопрос, декодер пишет ответ слово за словом."""

    def __init__(
        self,
        vocab_size: int,
        pad_id: int = 0,
        sos_id: int = 2,
        eos_id: int = 3,
        embed_dim: int = 128,
        hidden_size: int = 192,
        attention_size: int = 128,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()

        self.pad_id = pad_id
        self.sos_id = sos_id
        self.eos_id = eos_id

        # Энкодер: вопрос → последовательность векторов.
        self.encoder_embedding = nn.Embedding(
            vocab_size,
            embed_dim,
            padding_idx=pad_id,
        )

        self.encoder_gru = nn.GRU(
            embed_dim,
            hidden_size,
            batch_first=True,
        )

        # Декодер: текущее слово + контекст → следующее слово.
        self.decoder_embedding = nn.Embedding(
            vocab_size,
            embed_dim,
            padding_idx=pad_id,
        )

        self.decoder_gru = nn.GRU(
            embed_dim + hidden_size,
            hidden_size,
            batch_first=True,
        )

        self.attention = BahdanauAttention(
            hidden_size,
            attention_size,
        )

        self.output = nn.Linear(
            hidden_size * 2,
            vocab_size,
        )

        self.dropout = nn.Dropout(dropout)

    def encode(
        self,
        source: torch.Tensor,
        source_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Читает вопрос. Возвращает векторы слов и состояние итога."""

        embedded = self.dropout(
            self.encoder_embedding(source)
        )

        # GRU должен заканчиваться на настоящем конце фразы,
        # а не на паддинге — поэтому упаковываем по длине.
        lengths = (~source_mask).sum(dim=1).cpu()

        packed = pack_padded_sequence(
            embedded,
            lengths,
            batch_first=True,
            enforce_sorted=False,
        )

        outputs, hidden = self.encoder_gru(packed)

        outputs, _ = pad_packed_sequence(
            outputs,
            batch_first=True,
            total_length=source.size(1),
        )

        return outputs, hidden

    def step(
        self,
        token: torch.Tensor,
        hidden: torch.Tensor,
        encoder_outputs: torch.Tensor,
        source_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Один шаг декодера: слово → логиты следующего слова."""

        embedded = self.decoder_embedding(token).unsqueeze(1)

        context, weights = self.attention(
            hidden.squeeze(0),
            encoder_outputs,
            source_mask,
        )

        gru_input = torch.cat(
            [embedded, context.unsqueeze(1)],
            dim=2,
        )

        output, hidden = self.decoder_gru(
            gru_input,
            hidden,
        )

        logits = self.output(
            torch.cat(
                [output.squeeze(1), context],
                dim=1,
            )
        )

        return logits, hidden, weights

    def forward(
        self,
        source: torch.Tensor,
        source_mask: torch.Tensor,
        target: torch.Tensor,
        teacher_forcing_ratio: float = 0.5,
    ) -> torch.Tensor:
        """Возвращает логиты для каждой позиции ответа.

        target: (batch, tgt_len), где 0-й токен — <sos>.
        На каждом шаге декодер либо слушает учителя (эталон),
        либо верит себе — так модель учится не копить ошибки.
        """

        batch_size, target_length = target.shape

        if target_length < 2:
            raise ValueError(
                "target должен содержать <sos> и хотя бы один токен."
            )

        encoder_outputs, hidden = self.encode(
            source,
            source_mask,
        )

        token = target[:, 0]
        logits_collection = []

        for position in range(1, target_length):
            logits, hidden, _ = self.step(
                token,
                hidden,
                encoder_outputs,
                source_mask,
            )

            logits_collection.append(logits)

            predicted = logits.argmax(dim=1)

            if teacher_forcing_ratio > 0:
                use_teacher = (
                    torch.rand(
                        batch_size,
                        device=source.device,
                    )
                    < teacher_forcing_ratio
                )
                token = torch.where(
                    use_teacher,
                    target[:, position],
                    predicted,
                )
            else:
                token = predicted

        return torch.stack(logits_collection, dim=1)

    @torch.no_grad()
    def generate(
        self,
        source: torch.Tensor,
        source_mask: torch.Tensor,
        max_len: int = 40,
    ) -> torch.Tensor:
        """Придумывает ответы без учителя. Возвращает id токенов."""

        batch_size = source.size(0)

        encoder_outputs, hidden = self.encode(
            source,
            source_mask,
        )

        token = torch.full(
            (batch_size,),
            self.sos_id,
            dtype=torch.long,
            device=source.device,
        )

        finished = torch.zeros(
            batch_size,
            dtype=torch.bool,
            device=source.device,
        )

        generated = []

        for _ in range(max_len):
            logits, hidden, _ = self.step(
                token,
                hidden,
                encoder_outputs,
                source_mask,
            )

            predicted = logits.argmax(dim=1)
            generated.append(predicted)

            finished = finished | (
                predicted == self.eos_id
            )

            if bool(finished.all()):
                break

            # Закончившие продолжают «писать» паддингом —
            # их мусор отсечёт первый </eos> при разборе.
            token = torch.where(
                finished,
                torch.full_like(
                    predicted,
                    self.pad_id,
                ),
                predicted,
            )

        return torch.stack(generated, dim=1)
