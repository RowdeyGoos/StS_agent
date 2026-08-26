"""Tests for the Torch-optional shared card-record encoder."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from game.agents.card_encoder import (  # noqa: E402
    CARD_EMBEDDING_DIM,
    CARD_ID_EMBEDDING_DIM,
    CardRecordTensors,
    SharedCardEncoder,
    tensorize_card_zone_records,
)
from game.simulation.card_records import (  # noqa: E402
    CARD_ID_CAPACITY,
    CARD_SEMANTIC_FEATURE_NAMES,
    MAX_DISTINCT_RECORDS_PER_PILE,
    MAX_HAND_RECORDS,
    PILE_RECORD_ORDER,
    CardZoneRecords,
    PileCardRecord,
    card_semantic_feature_table,
    get_card_id,
)


def _records(
    *,
    draw_strikes: int = 2,
    draw_defends: int = 1,
) -> CardZoneRecords:
    return CardZoneRecords(
        hand_card_ids=(get_card_id("Strike"), get_card_id("Bash")),
        draw_pile=(
            PileCardRecord(get_card_id("Strike"), draw_strikes),
            PileCardRecord(get_card_id("Defend"), draw_defends),
        ),
        discard_pile=(PileCardRecord(get_card_id("Pommel Strike"), 1),),
        exhaust_pile=(),
    )


def test_tensorization_preserves_integer_ids_counts_masks_and_padding() -> None:
    large_exact_count = 16_777_217
    first = _records(draw_strikes=large_exact_count)
    empty = CardZoneRecords((), (), (), ())

    tensors = tensorize_card_zone_records((first, empty))

    assert tensors.batch_size == 2
    assert tensors.hand_ids.shape == (2, MAX_HAND_RECORDS)
    assert tensors.hand_ids.dtype == torch.long
    assert tensors.hand_mask.dtype == torch.bool
    assert tensors.pile_ids.shape == (
        2,
        len(PILE_RECORD_ORDER),
        MAX_DISTINCT_RECORDS_PER_PILE,
    )
    assert tensors.pile_ids.dtype == torch.long
    assert tensors.pile_counts.dtype == torch.long
    assert tensors.pile_mask.dtype == torch.bool
    assert tensors.hand_ids[0, :2].tolist() == [
        get_card_id("Strike"),
        get_card_id("Bash"),
    ]
    assert tensors.hand_mask[0, :3].tolist() == [True, True, False]
    assert int(tensors.pile_counts[0, 0, 0]) == large_exact_count
    assert not bool(tensors.hand_mask[1].any())
    assert not bool(tensors.pile_mask[1].any())


def test_tensorization_rejects_empty_batch_and_invalid_records() -> None:
    with pytest.raises(ValueError, match="At least one"):
        tensorize_card_zone_records(())

    strike_id = get_card_id("Strike")
    duplicate = CardZoneRecords(
        (),
        (PileCardRecord(strike_id, 1), PileCardRecord(strike_id, 1)),
        (),
        (),
    )
    with pytest.raises(ValueError, match="unique, strictly ascending"):
        tensorize_card_zone_records((duplicate,))


def test_encoder_has_fixed_dimensions_and_zeroes_padding() -> None:
    torch.manual_seed(0)
    encoder = SharedCardEncoder()
    tensors = tensorize_card_zone_records((_records(), CardZoneRecords((), (), (), ())))

    output = encoder(tensors)

    assert encoder.card_id_embedding.weight.shape == (
        CARD_ID_CAPACITY,
        CARD_ID_EMBEDDING_DIM,
    )
    assert output.hand_embeddings.shape == (2, MAX_HAND_RECORDS, CARD_EMBEDDING_DIM)
    assert output.pooled_hand_embedding.shape == (2, CARD_EMBEDDING_DIM)
    assert output.pile_embeddings.shape == (
        2,
        len(PILE_RECORD_ORDER),
        CARD_EMBEDDING_DIM,
    )
    assert output.pile_total_counts.shape == (2, len(PILE_RECORD_ORDER))
    assert output.pile_total_counts.dtype == torch.long
    assert torch.count_nonzero(output.hand_embeddings[0, 2:]) == 0
    assert torch.count_nonzero(output.hand_embeddings[1]) == 0
    assert torch.count_nonzero(output.pooled_hand_embedding[1]) == 0
    assert torch.count_nonzero(output.pile_embeddings[1]) == 0
    assert torch.count_nonzero(encoder.encode_card_ids(torch.tensor([0]))) == 0


def test_pile_pooling_is_record_order_invariant() -> None:
    torch.manual_seed(1)
    encoder = SharedCardEncoder()
    tensors = tensorize_card_zone_records((_records(),))
    original = encoder(tensors)

    reversed_tensors = CardRecordTensors(
        hand_ids=tensors.hand_ids,
        hand_mask=tensors.hand_mask,
        pile_ids=tensors.pile_ids.clone(),
        pile_counts=tensors.pile_counts.clone(),
        pile_mask=tensors.pile_mask.clone(),
    )
    reversed_tensors.pile_ids[:, 0, :2] = tensors.pile_ids[:, 0, :2].flip(1)
    reversed_tensors.pile_counts[:, 0, :2] = tensors.pile_counts[:, 0, :2].flip(1)
    reversed_tensors.pile_mask[:, 0, :2] = tensors.pile_mask[:, 0, :2].flip(1)
    reversed_output = encoder(reversed_tensors)

    assert torch.allclose(original.pile_embeddings, reversed_output.pile_embeddings)
    assert torch.equal(original.pile_total_counts, reversed_output.pile_total_counts)


def test_pile_pooling_uses_counts_and_exposes_exact_totals() -> None:
    torch.manual_seed(2)
    encoder = SharedCardEncoder()
    balanced = tensorize_card_zone_records((_records(draw_strikes=1, draw_defends=1),))
    strike_heavy = tensorize_card_zone_records((_records(draw_strikes=3, draw_defends=1),))

    balanced_output = encoder(balanced)
    strike_heavy_output = encoder(strike_heavy)

    assert balanced_output.pile_total_counts[0, 0].item() == 2
    assert strike_heavy_output.pile_total_counts[0, 0].item() == 4
    assert not torch.allclose(
        balanced_output.pile_embeddings[0, 0],
        strike_heavy_output.pile_embeddings[0, 0],
    )


def test_hand_slot_embeddings_are_permutation_equivariant() -> None:
    torch.manual_seed(3)
    encoder = SharedCardEncoder()
    records = _records()
    swapped = CardZoneRecords(
        hand_card_ids=tuple(reversed(records.hand_card_ids)),
        draw_pile=records.draw_pile,
        discard_pile=records.discard_pile,
        exhaust_pile=records.exhaust_pile,
    )

    original_output = encoder(tensorize_card_zone_records((records,)))
    swapped_output = encoder(tensorize_card_zone_records((swapped,)))

    assert torch.allclose(
        original_output.hand_embeddings[0, :2].flip(0),
        swapped_output.hand_embeddings[0, :2],
    )
    assert torch.allclose(
        original_output.pooled_hand_embedding,
        swapped_output.pooled_hand_embedding,
    )


def test_same_card_encoder_weights_are_shared_across_hand_pile_and_action_ids() -> None:
    torch.manual_seed(4)
    encoder = SharedCardEncoder()
    strike_id = get_card_id("Strike")
    single_strike = CardZoneRecords(
        hand_card_ids=(strike_id,),
        draw_pile=(PileCardRecord(strike_id, 5),),
        discard_pile=(),
        exhaust_pile=(),
    )

    output = encoder(tensorize_card_zone_records((single_strike,)))
    action_embedding = encoder.encode_card_ids(torch.tensor([[strike_id]]))[0, 0]

    assert torch.allclose(
        output.hand_embeddings[0, 0], action_embedding, rtol=1e-5, atol=1e-6
    )
    assert torch.allclose(
        output.pile_embeddings[0, 0], action_embedding, rtol=1e-5, atol=1e-6
    )


def test_gradients_reach_id_embedding_and_shared_semantic_mlp() -> None:
    torch.manual_seed(5)
    encoder = SharedCardEncoder()
    output = encoder(tensorize_card_zone_records((_records(),)))
    loss = (
        output.hand_embeddings.sum()
        + output.pooled_hand_embedding.sum()
        + output.pile_embeddings.sum()
    )

    loss.backward()

    embedding_grad = encoder.card_id_embedding.weight.grad
    first_linear = encoder.card_mlp[0]
    assert embedding_grad is not None
    assert torch.count_nonzero(embedding_grad[get_card_id("Strike")]) > 0
    assert torch.count_nonzero(embedding_grad[0]) == 0
    assert first_linear.weight.grad is not None
    assert torch.count_nonzero(first_linear.weight.grad) > 0


def test_append_only_semantics_keep_embedding_and_output_dimensions_stable() -> None:
    extended_table = torch.tensor(card_semantic_feature_table())
    synthetic_id = max(
        get_card_id("Body Slam") + 1,
        9,
    )
    extended_table[synthetic_id, 0] = 1.0
    extended_table[synthetic_id, 4] = 2.0

    encoder = SharedCardEncoder(semantic_feature_table=extended_table)
    encoded = encoder.encode_card_ids(torch.tensor([[synthetic_id]], dtype=torch.long))

    assert encoder.card_id_embedding.weight.shape == (CARD_ID_CAPACITY, 16)
    assert encoder.card_semantic_features.shape == (
        CARD_ID_CAPACITY,
        len(CARD_SEMANTIC_FEATURE_NAMES),
    )
    assert encoded.shape == (1, 1, CARD_EMBEDDING_DIM)


def test_encoder_rejects_lossy_or_inconsistent_tensor_inputs() -> None:
    encoder = SharedCardEncoder()
    tensors = tensorize_card_zone_records((_records(),))

    with pytest.raises(ValueError, match="integer tensor dtype"):
        encoder.encode_card_ids(tensors.hand_ids.float())

    bad_mask = CardRecordTensors(
        hand_ids=tensors.hand_ids,
        hand_mask=torch.zeros_like(tensors.hand_mask),
        pile_ids=tensors.pile_ids,
        pile_counts=tensors.pile_counts,
        pile_mask=tensors.pile_mask,
    )
    with pytest.raises(ValueError, match="hand_mask"):
        encoder(bad_mask)

    bad_counts = CardRecordTensors(
        hand_ids=tensors.hand_ids,
        hand_mask=tensors.hand_mask,
        pile_ids=tensors.pile_ids,
        pile_counts=tensors.pile_counts.clone(),
        pile_mask=tensors.pile_mask,
    )
    bad_counts.pile_counts[0, 0, 0] = 0
    with pytest.raises(ValueError, match="positive counts"):
        encoder(bad_counts)


def test_custom_semantic_table_requires_fixed_shape_finite_values_and_zero_padding() -> None:
    base_table = torch.tensor(card_semantic_feature_table())

    with pytest.raises(ValueError, match="shape"):
        SharedCardEncoder(semantic_feature_table=base_table[:-1])

    non_finite = base_table.clone()
    non_finite[1, 0] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        SharedCardEncoder(semantic_feature_table=non_finite)

    nonzero_padding = base_table.clone()
    nonzero_padding[0, 0] = 1.0
    with pytest.raises(ValueError, match="Padding"):
        SharedCardEncoder(semantic_feature_table=nonzero_padding)
