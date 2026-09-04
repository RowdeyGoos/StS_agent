"""Candidate-conditioned Torch policy for the frozen headless encoder.

This module is intentionally a narrow consumer of ``headless_encoding_v1``.
Candidate IDs remain outside the numerical model: they are only used to map a
selected unmasked tensor position back to the advertised action.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import re
from typing import Any, Mapping

import numpy as np
import torch
from torch import Tensor, nn

from game.contracts.headless_v0 import canonical_json_bytes

from .headless_encoding import (
    ENCODING_FINGERPRINT,
    ENCODING_VERSION,
    CollatedPolicyBatch,
)


class CandidatePolicyError(ValueError):
    """Raised when a batch or serialized candidate policy is not pinned safely."""


POLICY_VERSION = "headless_candidate_policy_v1"
_MODEL_DOMAIN = "headless_candidate_policy_v1.model.v1"
_CONFIG_DOMAIN = "headless_candidate_policy_v1.config.v1"
_CANDIDATE_ID = re.compile(r"cand\.[0-9a-f]{64}\Z")
_DIMENSIONS = {
    "global": 47,
    "entity": 90,
    "public_event": 78,
    "candidate": 557,
}
_ARCHITECTURE = "masked_mean_context_v1"


def _fingerprint(domain: str, payload: Mapping[str, Any]) -> str:
    return sha256(domain.encode("utf-8") + bytes((0,)) + canonical_json_bytes(payload)).hexdigest()


MODEL_FINGERPRINT = _fingerprint(
    _MODEL_DOMAIN,
    {
        "policy_version": POLICY_VERSION,
        "architecture": _ARCHITECTURE,
        "encoding_version": ENCODING_VERSION,
        "encoding_fingerprint": ENCODING_FINGERPRINT,
        "feature_dimensions": _DIMENSIONS,
        "pooling": "masked_mean_zero_for_empty_axis",
        "masked_logits": "zero_for_masked_positions",
    },
)


@dataclass(frozen=True, slots=True)
class CandidatePolicyConfig:
    """Small, bounded architecture configuration recorded with every payload."""

    hidden_size: int = 64

    def __post_init__(self) -> None:
        if type(self.hidden_size) is not int or not 8 <= self.hidden_size <= 512:
            raise CandidatePolicyError("hidden_size must be an integer in [8, 512].")


def config_fingerprint(config: CandidatePolicyConfig) -> str:
    """Return the exact versioned model/config identity for ``config``."""
    if type(config) is not CandidatePolicyConfig:
        raise CandidatePolicyError("config must be an exact CandidatePolicyConfig.")
    return _fingerprint(
        _CONFIG_DOMAIN,
        {
            "policy_version": POLICY_VERSION,
            "model_fingerprint": MODEL_FINGERPRINT,
            "encoding_version": ENCODING_VERSION,
            "encoding_fingerprint": ENCODING_FINGERPRINT,
            "config": asdict(config),
        },
    )


def _masked_mean(rows: Tensor, mask: Tensor) -> Tensor:
    """Pool an independently empty padded axis to an exact all-zero row."""
    weights = mask.unsqueeze(-1).to(dtype=rows.dtype)
    denominator = weights.sum(dim=1).clamp_min(1.0)
    return (rows * weights).sum(dim=1) / denominator


def _require_feature_array(value: Any, *, name: str, batch_size: int, width: int) -> np.ndarray:
    if (
        type(value) is not np.ndarray
        or value.dtype != np.float32
        or value.ndim != 3
        or value.shape[0] != batch_size
        or value.shape[2] != width
    ):
        raise CandidatePolicyError(f"{name} has an invalid shape or dtype.")
    return value


def _require_mask(value: Any, *, name: str, shape: tuple[int, int]) -> np.ndarray:
    if type(value) is not np.ndarray or value.dtype != np.bool_ or value.shape != shape:
        raise CandidatePolicyError(f"{name} has an invalid shape or dtype.")
    return value


def _validate_batch(batch: CollatedPolicyBatch) -> None:
    if type(batch) is not CollatedPolicyBatch:
        raise CandidatePolicyError("batch must be an exact CollatedPolicyBatch.")
    if batch.encoding_version != ENCODING_VERSION or batch.encoding_fingerprint != ENCODING_FINGERPRINT:
        raise CandidatePolicyError("batch encoding identity does not match the accepted pin.")
    global_features = batch.global_features
    if type(global_features) is not np.ndarray or global_features.dtype != np.float32 or global_features.ndim != 2 or global_features.shape[1:] != (_DIMENSIONS["global"],):
        raise CandidatePolicyError("global_features has an invalid shape or dtype.")
    batch_size = global_features.shape[0]
    entity_features = _require_feature_array(batch.entity_features, name="entity_features", batch_size=batch_size, width=_DIMENSIONS["entity"])
    event_features = _require_feature_array(batch.public_event_features, name="public_event_features", batch_size=batch_size, width=_DIMENSIONS["public_event"])
    candidate_features = _require_feature_array(batch.candidate_features, name="candidate_features", batch_size=batch_size, width=_DIMENSIONS["candidate"])
    entity_mask = _require_mask(batch.entity_mask, name="entity_mask", shape=entity_features.shape[:2])
    event_mask = _require_mask(batch.public_event_mask, name="public_event_mask", shape=event_features.shape[:2])
    candidate_mask = _require_mask(batch.candidate_mask, name="candidate_mask", shape=candidate_features.shape[:2])
    for name, values in (("global_features", global_features), ("entity_features", entity_features), ("public_event_features", event_features), ("candidate_features", candidate_features)):
        if not np.isfinite(values).all() or np.any(values < 0.0) or np.any(values > 1.0):
            raise CandidatePolicyError(f"{name} must contain finite normalized features.")
    for name, values, mask in (("entity_features", entity_features, entity_mask), ("public_event_features", event_features, event_mask), ("candidate_features", candidate_features, candidate_mask)):
        if np.any(values[~mask] != 0.0):
            raise CandidatePolicyError(f"{name} padding must be zero.")
    if type(batch.candidate_ids) is not tuple or len(batch.candidate_ids) != batch_size:
        raise CandidatePolicyError("candidate IDs do not align with the batch.")
    for row, candidate_ids in enumerate(batch.candidate_ids):
        legal_count = int(candidate_mask[row].sum())
        if type(candidate_ids) is not tuple or len(candidate_ids) != legal_count:
            raise CandidatePolicyError("candidate IDs do not align with candidate_mask.")
        if not np.array_equal(candidate_mask[row], np.arange(candidate_mask.shape[1]) < legal_count):
            raise CandidatePolicyError("candidate_mask must use the encoder's prefix padding layout.")
        if any(type(candidate_id) is not str or _CANDIDATE_ID.fullmatch(candidate_id) is None for candidate_id in candidate_ids):
            raise CandidatePolicyError("candidate IDs must be canonical strings.")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise CandidatePolicyError("candidate IDs must be unique within each row.")


class HeadlessCandidatePolicy(nn.Module):
    """Pool public context and score only advertised candidate feature rows."""

    def __init__(self, config: CandidatePolicyConfig = CandidatePolicyConfig()) -> None:
        if type(config) is not CandidatePolicyConfig:
            raise CandidatePolicyError("config must be an exact CandidatePolicyConfig.")
        super().__init__()
        self.config = config
        hidden = config.hidden_size
        self.global_encoder = nn.Sequential(nn.Linear(47, hidden), nn.Tanh())
        self.entity_encoder = nn.Sequential(nn.Linear(90, hidden), nn.Tanh())
        self.event_encoder = nn.Sequential(nn.Linear(78, hidden), nn.Tanh())
        self.candidate_encoder = nn.Sequential(nn.Linear(557, hidden), nn.Tanh())
        self.score_head = nn.Sequential(nn.Linear(hidden * 2, hidden), nn.Tanh(), nn.Linear(hidden, 1))

    @property
    def model_fingerprint(self) -> str:
        return MODEL_FINGERPRINT

    @property
    def config_fingerprint(self) -> str:
        return config_fingerprint(self.config)

    def forward(self, batch: CollatedPolicyBatch) -> Tensor:
        """Return ``(B, Amax)`` logits; every masked/padded value is exactly zero."""
        _validate_batch(batch)
        device = next(self.parameters()).device
        globals_tensor = torch.as_tensor(batch.global_features, device=device)
        entity_tensor = torch.as_tensor(batch.entity_features, device=device)
        event_tensor = torch.as_tensor(batch.public_event_features, device=device)
        candidate_tensor = torch.as_tensor(batch.candidate_features, device=device)
        entity_mask = torch.as_tensor(batch.entity_mask, device=device)
        event_mask = torch.as_tensor(batch.public_event_mask, device=device)
        candidate_mask = torch.as_tensor(batch.candidate_mask, device=device)

        context = self.global_encoder(globals_tensor)
        context = context + _masked_mean(self.entity_encoder(entity_tensor), entity_mask)
        context = context + _masked_mean(self.event_encoder(event_tensor), event_mask)
        candidate_embedding = self.candidate_encoder(candidate_tensor)
        expanded_context = context.unsqueeze(1).expand(-1, candidate_embedding.shape[1], -1)
        logits = self.score_head(torch.cat((candidate_embedding, expanded_context), dim=-1)).squeeze(-1)
        return torch.where(candidate_mask, logits, torch.zeros_like(logits))

    def probabilities(self, batch: CollatedPolicyBatch) -> Tensor:
        """Return masked probabilities, with all-zero probability for no-candidate rows."""
        logits = self(batch)
        if logits.shape[1] == 0:
            return logits
        mask = torch.as_tensor(batch.candidate_mask, device=logits.device)
        masked_logits = torch.where(mask, logits, torch.finfo(logits.dtype).min)
        maximum = masked_logits.max(dim=1, keepdim=True).values
        unnormalized = torch.exp(masked_logits - maximum) * mask.to(dtype=logits.dtype)
        return unnormalized / unnormalized.sum(dim=1, keepdim=True).clamp_min(1.0)

    @torch.no_grad()
    def select_candidate_ids(self, batch: CollatedPolicyBatch) -> tuple[str | None, ...]:
        """Select an advertised ID per row, or ``None`` when no candidate is legal."""
        logits = self(batch)
        selected: list[str | None] = []
        for row, candidate_ids in enumerate(batch.candidate_ids):
            if not candidate_ids:
                selected.append(None)
                continue
            selected.append(candidate_ids[int(torch.argmax(logits[row, : len(candidate_ids)]).item())])
        return tuple(selected)

    def checkpoint_payload(self) -> dict[str, Any]:
        """Return a pinned, local persistence payload without registering a new agent type."""
        return {
            "policy_version": POLICY_VERSION,
            "encoding_version": ENCODING_VERSION,
            "encoding_fingerprint": ENCODING_FINGERPRINT,
            "model_fingerprint": MODEL_FINGERPRINT,
            "config": asdict(self.config),
            "config_fingerprint": self.config_fingerprint,
            "state_dict": self.state_dict(),
        }

    @classmethod
    def from_checkpoint_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        device: torch.device | str | None = None,
    ) -> "HeadlessCandidatePolicy":
        """Load only an exact policy payload with matching schema, model, and shapes."""
        if not isinstance(payload, Mapping) or set(payload) != {
            "policy_version", "encoding_version", "encoding_fingerprint", "model_fingerprint",
            "config", "config_fingerprint", "state_dict",
        }:
            raise CandidatePolicyError("candidate policy payload has an invalid key set.")
        if (payload["policy_version"], payload["encoding_version"], payload["encoding_fingerprint"], payload["model_fingerprint"]) != (POLICY_VERSION, ENCODING_VERSION, ENCODING_FINGERPRINT, MODEL_FINGERPRINT):
            raise CandidatePolicyError("candidate policy payload pins do not match this model.")
        raw_config = payload["config"]
        if type(raw_config) is not dict or set(raw_config) != {"hidden_size"}:
            raise CandidatePolicyError("candidate policy config has an invalid shape.")
        try:
            config = CandidatePolicyConfig(**raw_config)
        except (TypeError, CandidatePolicyError) as exc:
            raise CandidatePolicyError("candidate policy config is invalid.") from exc
        if payload["config_fingerprint"] != config_fingerprint(config):
            raise CandidatePolicyError("candidate policy config fingerprint does not match.")
        model = cls(config)
        state_dict = payload["state_dict"]
        expected = model.state_dict()
        if not isinstance(state_dict, Mapping) or set(state_dict) != set(expected):
            raise CandidatePolicyError("candidate policy state_dict keys do not match.")
        for name, expected_value in expected.items():
            value = state_dict[name]
            if type(value) is not Tensor or value.shape != expected_value.shape or value.dtype != expected_value.dtype:
                raise CandidatePolicyError(f"candidate policy state_dict tensor {name!r} has an invalid shape or dtype.")
            if not torch.isfinite(value).all().item():
                raise CandidatePolicyError(f"candidate policy state_dict tensor {name!r} is non-finite.")
        try:
            model.load_state_dict(state_dict, strict=True)
        except RuntimeError as exc:  # pragma: no cover - preflight above is exact
            raise CandidatePolicyError("candidate policy state_dict could not be loaded.") from exc
        if device is not None:
            model.to(device)
        return model
