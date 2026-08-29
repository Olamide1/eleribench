"""One module per payment protocol (PRD §3.5). Each exposes PROTOCOL and
make_reference()/default_extras() so render.py can stay protocol-agnostic and
new rails are additive here, never a schema change (PRD Appendix C.5)."""

from . import acp, ap2, stripe, x402

REGISTRY = {
    x402.PROTOCOL: x402,
    ap2.PROTOCOL: ap2,
    acp.PROTOCOL: acp,
    stripe.PROTOCOL: stripe,
}

__all__ = ["REGISTRY", "x402", "ap2", "acp", "stripe"]
