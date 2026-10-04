"""Edge-free entity processing over the common public feature tables."""
import torch
from torch import nn


class EntityAttention(nn.Module):
    """Four-head self-attention without dropout or train/eval fast-path changes."""
    def __init__(self, width):
        super().__init__()
        self.width = width
        self.qkv = nn.Linear(width, 3 * width)
        self.output = nn.Linear(width, width)
        self.norm_attention = nn.LayerNorm(width)
        self.feedforward = nn.Sequential(nn.Linear(width, 2 * width), nn.GELU(), nn.Linear(2 * width, width))
        self.norm_feedforward = nn.LayerNorm(width)

    def forward(self, tokens, valid):
        b, length, d = tokens.shape
        q, k, v = self.qkv(tokens).reshape(b, length, 3, 4, d // 4).permute(2, 0, 3, 1, 4).unbind(0)
        scores = (q @ k.transpose(-1, -2)) * ((d // 4) ** -.5)
        weights = scores.masked_fill(~valid[:, None, None, :], -torch.inf).softmax(-1)
        context = (weights @ v).transpose(1, 2).reshape(b, length, d)
        tokens = self.norm_attention(tokens + self.output(context))
        return self.norm_feedforward(tokens + self.feedforward(tokens))


def attend_entities(h, batch, layers):
    """Attend only to public actors/roots/action operands, never graph edges.

    All other rows still contribute to the model's pooled state. Selection
    candidates are included even if their nodes have no tactical role. Padding
    is isolated per state and cannot leak another example's entities.
    """
    active = batch['roles'] >= 0
    active = active.clone()
    active[batch['roots'].reshape(-1)] = True
    operands = batch['candidates'][:, :, 1:].reshape(-1)
    active[operands[operands >= 0]] = True
    indexes = torch.nonzero(active, as_tuple=True)[0]
    owners = batch['owners'][indexes]
    count = len(batch['roots'])
    sizes = torch.bincount(owners, minlength=count)
    offsets = sizes.cumsum(0) - sizes
    positions = torch.arange(len(indexes), device=h.device) - offsets[owners]
    width = int(sizes.max())
    tokens = h.new_zeros((count, width, h.shape[-1]))
    tokens[owners, positions] = h[indexes]
    valid = torch.arange(width, device=h.device)[None, :] < sizes[:, None]
    for layer in layers:
        tokens = layer(tokens, valid)
    return h.index_copy(0, indexes, tokens[owners, positions])
