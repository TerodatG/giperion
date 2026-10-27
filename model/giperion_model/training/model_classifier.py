# GiperionModel/giperion_model/training/model_classifier.py           v002
# Своя модель-классификатор намерений Giperion.
# Последнее изменение: max-pooling теперь не слышит паддинг (masked pooling).

import torch
import torch.nn as nn
import torch.nn.functional as F

# Ширины свёрточных окон: биграммы, триграммы и т.д.
CONV_WIDTHS = (2, 3, 4, 5)


def parameter_count(model: nn.Module) -> int:
    """Считает все обучаемые параметры модели."""

    return sum(
        parameter.numel()
        for parameter in model.parameters()
        if parameter.requires_grad
    )


def masked_max_pool(
    feature: torch.Tensor,
    lengths: torch.Tensor,
    width: int,
) -> torch.Tensor:
    """Max-pooling только по окнам внутри настоящей фразы.

    Окно [j, j + width) целиком в фразе ⇔ j < L - width + 1.
    Для коротких фраз остаётся первое окно — хотя бы одно
    признак всегда есть, иначе max был бы −бесконечностью.
    """

    total = feature.size(2)
    starts = torch.arange(
        total,
        device=feature.device,
    )

    valid = starts.unsqueeze(0) < (
        lengths - width + 1
    ).clamp(min=1).unsqueeze(1)

    feature = feature.masked_fill(
        ~valid.unsqueeze(1),
        float("-inf"),
    )

    return feature.max(dim=2).values


class TextClassifier(nn.Module):
    """Классификатор: Embedding → свёртки → max-pool → MLP.

    Идея: каждое сверточное окно «сканирует» фразу на предмет
    признака (например, «приветствие»), max-pool запоминает
    самое сильное срабатывание, MLP собирает диагноз.
    """

    def __init__(
        self,
        vocab_size: int,
        num_classes: int,
        pad_id: int = 0,
        embed_dim: int = 128,
        channels: int = 64,
        hidden: int = 256,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()

        self.pad_id = pad_id

        # Таблица векторов: токен → вектор из embed_dim чисел.
        self.embedding = nn.Embedding(
            vocab_size,
            embed_dim,
            padding_idx=pad_id,
        )

        # Окна разной ширины ловят разные по длине паттерны.
        self.convs = nn.ModuleList(
            nn.Conv1d(
                in_channels=embed_dim,
                out_channels=channels,
                kernel_size=width,
            )
            for width in CONV_WIDTHS
        )

        self.dropout = nn.Dropout(dropout)

        self.fc1 = nn.Linear(
            channels * len(CONV_WIDTHS),
            hidden,
        )

        self.fc2 = nn.Linear(
            hidden,
            num_classes,
        )

    def forward(
        self,
        tokens: torch.Tensor,
    ) -> torch.Tensor:
        """Возвращает логиты для каждого примера батча."""

        # Сколько в каждой фразе настоящих слов (не паддинга).
        lengths = (tokens != self.pad_id).sum(dim=1)

        # (batch, seq) → (batch, seq, embed)
        embedded = self.embedding(tokens)

        # Свёртка ждёт каналы первыми: (batch, embed, seq)
        embedded = embedded.transpose(1, 2)

        pooled = []

        for width, conv in zip(CONV_WIDTHS, self.convs, strict=False):
            # (batch, channels, seq') → (batch, channels)
            feature = F.relu(conv(embedded))

            pooled.append(
                masked_max_pool(
                    feature,
                    lengths,
                    width,
                )
            )

        # Собираем все признаки в один вектор.
        features = torch.cat(pooled, dim=1)

        hidden = F.relu(
            self.fc1(self.dropout(features))
        )

        return self.fc2(self.dropout(hidden))
