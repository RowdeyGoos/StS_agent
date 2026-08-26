"""Torch-optional shared neural encoder for exact card-zone records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ..simulation.card_records import (
    CARD_ID_CAPACITY,
    CARD_SEMANTIC_FEATURE_NAMES,
    MAX_DISTINCT_RECORDS_PER_PILE,
    MAX_HAND_RECORDS,
    PILE_RECORD_ORDER,
    CardZoneRecords,
    card_semantic_feature_table,
    validate_card_zone_records,
)

CARD_ID_EMBEDDING_DIM = 16
CARD_EMBEDDING_DIM = 32

try:
    import torch
    from torch import Tensor, nn
except ModuleNotFoundError:  # pragma: no cover - depends on optional dependency
    torch = None
    Tensor = Any
    nn = None


@dataclass(frozen=True, slots=True)
class CardRecordTensors:
    """Padded integer IDs/counts and exact boolean masks for one batch."""

    hand_ids: Tensor
    hand_mask: Tensor
    pile_ids: Tensor
    pile_counts: Tensor
    pile_mask: Tensor

    @property
    def batch_size(self) -> int:
        """Return the number of observations in this tensor batch."""
        return int(self.hand_ids.shape[0])


@dataclass(frozen=True, slots=True)
class EncodedCardRecords:
    """Fixed-width learned outputs from all visible card zones."""

    hand_embeddings: Tensor
    pooled_hand_embedding: Tensor
    pile_embeddings: Tensor
    pile_total_counts: Tensor


def tensorize_card_zone_records(
    records: Sequence[CardZoneRecords],
    *,
    device: str | Any | None = None,
) -> CardRecordTensors:
    """Pad exact records into integer tensors without lossy ID/count casts."""
    _require_torch()
    record_batch = tuple(records)
    if not record_batch:
        raise ValueError("At least one CardZoneRecords value is required.")
    for record in record_batch:
        validate_card_zone_records(record)

    batch_size = len(record_batch)
    hand_ids = torch.zeros(
        (batch_size, MAX_HAND_RECORDS),
        dtype=torch.long,
        device=device,
    )
    hand_mask = torch.zeros(
        (batch_size, MAX_HAND_RECORDS),
        dtype=torch.bool,
        device=device,
    )
    pile_ids = torch.zeros(
        (
            batch_size,
            len(PILE_RECORD_ORDER),
            MAX_DISTINCT_RECORDS_PER_PILE,
        ),
        dtype=torch.long,
        device=device,
    )
    pile_counts = torch.zeros_like(pile_ids)
    pile_mask = torch.zeros_like(pile_ids, dtype=torch.bool)

    for batch_index, record in enumerate(record_batch):
        hand_length = len(record.hand_card_ids)
        if hand_length:
            hand_ids[batch_index, :hand_length] = torch.as_tensor(
                record.hand_card_ids,
                dtype=torch.long,
                device=device,
            )
            hand_mask[batch_index, :hand_length] = True

        for pile_index, pile_name in enumerate(PILE_RECORD_ORDER):
            pile = record.pile(pile_name)
            pile_length = len(pile)
            if not pile_length:
                continue
            pile_ids[batch_index, pile_index, :pile_length] = torch.as_tensor(
                [entry.card_id for entry in pile],
                dtype=torch.long,
                device=device,
            )
            pile_counts[batch_index, pile_index, :pile_length] = torch.as_tensor(
                [entry.count for entry in pile],
                dtype=torch.long,
                device=device,
            )
            pile_mask[batch_index, pile_index, :pile_length] = True

    return CardRecordTensors(
        hand_ids=hand_ids,
        hand_mask=hand_mask,
        pile_ids=pile_ids,
        pile_counts=pile_counts,
        pile_mask=pile_mask,
    )


if torch is not None and nn is not None:

    class SharedCardEncoder(nn.Module):
        """Share card semantics and ID embeddings across hand, piles, and actions."""

        def __init__(
            self,
            semantic_feature_table: Sequence[Sequence[float]] | Tensor | None = None,
        ) -> None:
            super().__init__()
            self.card_id_embedding = nn.Embedding(
                CARD_ID_CAPACITY,
                CARD_ID_EMBEDDING_DIM,
                padding_idx=0,
            )
            semantic_table = _coerce_semantic_feature_table(semantic_feature_table)
            self.register_buffer(
                "card_semantic_features",
                semantic_table,
                persistent=False,
            )
            semantic_width = len(CARD_SEMANTIC_FEATURE_NAMES)
            self.card_mlp = nn.Sequential(
                nn.Linear(CARD_ID_EMBEDDING_DIM + semantic_width, CARD_EMBEDDING_DIM),
                nn.ReLU(),
                nn.Linear(CARD_EMBEDDING_DIM, CARD_EMBEDDING_DIM),
                nn.ReLU(),
            )

        def encode_card_ids(self, card_ids: Tensor) -> Tensor:
            """Encode arbitrary hand, pile, or action card-ID tensors."""
            _validate_id_tensor(card_ids)
            card_ids = card_ids.to(dtype=torch.long)
            id_embeddings = self.card_id_embedding(card_ids)
            semantic_features = self.card_semantic_features[card_ids]
            embeddings = self.card_mlp(
                torch.cat([id_embeddings, semantic_features], dim=-1)
            )
            return embeddings * card_ids.ne(0).unsqueeze(-1).to(embeddings.dtype)

        def forward(self, records: CardRecordTensors) -> EncodedCardRecords:
            """Encode ordered hand slots and invariant exact-composition piles."""
            _validate_record_tensors(records)
            hand_embeddings = self.encode_card_ids(records.hand_ids)
            hand_weights = records.hand_mask.unsqueeze(-1).to(hand_embeddings.dtype)
            hand_total = hand_weights.sum(dim=1).clamp_min(1.0)
            pooled_hand = (hand_embeddings * hand_weights).sum(dim=1) / hand_total

            record_embeddings = self.encode_card_ids(records.pile_ids)
            count_weights = (
                records.pile_counts.to(record_embeddings.dtype)
                * records.pile_mask.to(record_embeddings.dtype)
            )
            pile_total_counts = records.pile_counts.sum(dim=-1)
            pooled_piles = (
                record_embeddings * count_weights.unsqueeze(-1)
            ).sum(dim=2) / count_weights.sum(dim=2, keepdim=True).clamp_min(1.0)

            return EncodedCardRecords(
                hand_embeddings=hand_embeddings,
                pooled_hand_embedding=pooled_hand,
                pile_embeddings=pooled_piles,
                pile_total_counts=pile_total_counts,
            )


    def _coerce_semantic_feature_table(
        source: Sequence[Sequence[float]] | Tensor | None,
    ) -> Tensor:
        values = card_semantic_feature_table() if source is None else source
        table = torch.as_tensor(values, dtype=torch.float32)
        expected_shape = (CARD_ID_CAPACITY, len(CARD_SEMANTIC_FEATURE_NAMES))
        if tuple(table.shape) != expected_shape:
            raise ValueError(
                f"Semantic feature table shape must be {expected_shape}, got "
                f"{tuple(table.shape)}."
            )
        if not torch.isfinite(table).all():
            raise ValueError("Semantic feature table must contain only finite values.")
        if not torch.equal(table[0], torch.zeros_like(table[0])):
            raise ValueError("Padding card ID 0 must have an all-zero semantic row.")
        return table.clone().detach()


    def _validate_id_tensor(card_ids: Tensor) -> None:
        if card_ids.dtype not in {
            torch.uint8,
            torch.int8,
            torch.int16,
            torch.int32,
            torch.int64,
        }:
            raise ValueError("Card IDs must use an integer tensor dtype.")
        if card_ids.numel() and (
            bool((card_ids < 0).any()) or bool((card_ids >= CARD_ID_CAPACITY).any())
        ):
            raise ValueError(f"Card IDs must be in [0, {CARD_ID_CAPACITY}).")


    def _validate_record_tensors(records: CardRecordTensors) -> None:
        batch_size = records.batch_size
        expected_hand_shape = (batch_size, MAX_HAND_RECORDS)
        expected_pile_shape = (
            batch_size,
            len(PILE_RECORD_ORDER),
            MAX_DISTINCT_RECORDS_PER_PILE,
        )
        if tuple(records.hand_ids.shape) != expected_hand_shape:
            raise ValueError(
                f"hand_ids shape must be {expected_hand_shape}, got "
                f"{tuple(records.hand_ids.shape)}."
            )
        if tuple(records.hand_mask.shape) != expected_hand_shape:
            raise ValueError("hand_mask shape must match hand_ids.")
        for name, tensor in (
            ("pile_ids", records.pile_ids),
            ("pile_counts", records.pile_counts),
            ("pile_mask", records.pile_mask),
        ):
            if tuple(tensor.shape) != expected_pile_shape:
                raise ValueError(
                    f"{name} shape must be {expected_pile_shape}, got "
                    f"{tuple(tensor.shape)}."
                )
        if (
            records.hand_mask.dtype != torch.bool
            or records.pile_mask.dtype != torch.bool
        ):
            raise ValueError("Card-record masks must use boolean tensor dtype.")
        _validate_id_tensor(records.hand_ids)
        _validate_id_tensor(records.pile_ids)
        if records.pile_counts.dtype not in {
            torch.uint8,
            torch.int8,
            torch.int16,
            torch.int32,
            torch.int64,
        }:
            raise ValueError("Pile counts must use an integer tensor dtype.")
        if records.pile_counts.numel() and bool((records.pile_counts < 0).any()):
            raise ValueError("Pile counts cannot be negative.")
        if not torch.equal(records.hand_mask, records.hand_ids.ne(0)):
            raise ValueError("hand_mask must exactly identify non-padding hand IDs.")
        if not torch.equal(records.pile_mask, records.pile_ids.ne(0)):
            raise ValueError("pile_mask must exactly identify non-padding pile IDs.")
        if bool((records.pile_counts[records.pile_mask] <= 0).any()):
            raise ValueError("Active pile records must have positive counts.")
        if bool((records.pile_counts[~records.pile_mask] != 0).any()):
            raise ValueError("Padded pile records must have zero counts.")


else:

    class SharedCardEncoder:  # pragma: no cover - optional dependency fallback
        """Dependency-error placeholder when Torch is unavailable."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            _require_torch()


def _require_torch() -> None:
    if torch is None:
        raise ModuleNotFoundError(
            "Card-record tensorization and neural encoding require the optional "
            "dependency 'torch'."
        )
