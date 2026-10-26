# Giperion/training/model_charcnn.py                                v001
# Гибридный классификатор: словесная и символьная ветки.
# Последнее изменение: первый вариант — word-CNN + char-CNN вместе.

import torch
import torch.nn as nn
import torch.nn.functional as F

from giperion_model.training.model_classifier import (
    CONV_WIDTHS,
    masked_max_pool,
)

# Символьные окна разной ширины захватывают морфемы:
# 3 символа — «обуч», 4 — «обуч-ен», 6 — «-тель-н» и т.д.
CHAR_CONV_WIDTHS = (3, 4, 5, 6)


class HybridTextClassifier(nn.Module):
    """Две ветки признаков: слова фразы и символы строки.

    Словесная ветка видит «привет, как дела» как токены,
    символьная — как строку символов. Вместе они ловят
    и известные словоформы, и опечатки, и новые слова
    со знакомыми корнями/суффиксами.
    """

    def __init__(
        self,
        vocab_size: int,
        char_vocab_size: int,
        num_classes: int,
        pad_id: int = 0,
        word_embed: int = 128,
        char_embed: int = 32,
        word_channels: int = 64,
        char_channels: int = 96,
        hidden: int = 256,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()

        self.pad_id = pad_id

        # --- Словесная ветка ---
        self.word_embedding = nn.Embedding(
            vocab_size,
            word_embed,
            padding_idx=pad_id,
        )

        self.word_convs = nn.ModuleList(
            nn.Conv1d(
                in_channels=word_embed,
                out_channels=word_channels,
                kernel_size=width,
            )
            for width in CONV_WIDTHS
        )

        # --- Символьная ветка ---
        self.char_embedding = nn.Embedding(
            char_vocab_size,
            char_embed,
            padding_idx=pad_id,
        )

        self.char_convs = nn.ModuleList(
            nn.Conv1d(
                in_channels=char_embed,
                out_channels=char_channels,
                kernel_size=width,
            )
            for width in CHAR_CONV_WIDTHS
        )

        self.dropout = nn.Dropout(dropout)

        feature_dim = (
            word_channels * len(CONV_WIDTHS)
            + char_channels * len(CHAR_CONV_WIDTHS)
        )

        self.fc1 = nn.Linear(feature_dim, hidden)

        self.fc2 = nn.Linear(hidden, num_classes)

    def forward(
        self,
        tokens: torch.Tensor,
        chars: torch.Tensor,
    ) -> torch.Tensor:
        """Логиты по двум источникам: словам и символам."""

        word_features = self.pool_branch(
            self.word_embedding(tokens),
            (tokens != self.pad_id).sum(dim=1),
            self.word_convs,
            CONV_WIDTHS,
        )

        char_features = self.pool_branch(
            self.char_embedding(chars),
            (chars != self.pad_id).sum(dim=1),
            self.char_convs,
            CHAR_CONV_WIDTHS,
        )

        features = torch.cat(
            [word_features, char_features],
            dim=1,
        )

        hidden = F.relu(
            self.fc1(self.dropout(features))
        )

        return self.fc2(self.dropout(hidden))

    @staticmethod
    def pool_branch(
        embedded: torch.Tensor,
        lengths: torch.Tensor,
        convs: nn.ModuleList,
        widths: tuple[int, ...],
    ) -> torch.Tensor:
        """Общий цикл ветки: свёртка → relu → masked max-pool."""

        # (batch, seq, embed) → (batch, embed, seq)
        embedded = embedded.transpose(1, 2)

        pooled = []

        for width, conv in zip(widths, convs, strict=False):
            feature = F.relu(conv(embedded))

            pooled.append(
                masked_max_pool(
                    feature,
                    lengths,
                    width,
                )
            )

        return torch.cat(pooled, dim=1)
