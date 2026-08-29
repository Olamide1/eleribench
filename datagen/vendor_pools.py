"""Curated vendor/purpose pools per spend category — the raw material the
deterministic renderer (render.py) samples from. Kept hand-authored and small
on purpose: realism grounding matters more than sheer count (PRD §3.5's
"structurally indistinguishable from real x402 settlements" check), and the
Claude enrichment pass (enrich.py) is what adds long-tail lexical variety on
top of this scaffold, not this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CategoryProfile:
    """purposes[i] and intents[i] must describe the same underlying activity —
    render.py samples them as an (purpose, intent) pair at a shared index, not
    independently. Independent sampling was the root cause of a purpose_mismatch
    training-signal bug (many "clean match" examples paired an unrelated purpose
    and intent from the same category, teaching the model that surface mismatch
    doesn't matter) — see train/README.md postmortem."""

    vendors: list[str]
    purposes: list[str]
    intents: list[str]


CATEGORY_PROFILES: dict[str, CategoryProfile] = {
    "compute_inference": CategoryProfile(
        vendors=["api.openai.com", "api.anthropic.com", "api.together.ai", "runpod.io", "api.replicate.com"],
        # purposes[i] and intents[i] are index-aligned (render.py samples them as
        # a pair) — keep them describing the same underlying activity.
        purposes=["LLM inference calls", "batch embedding generation", "GPU inference usage"],
        intents=[
            "Run inference calls to summarize the daily research digest",
            "Generate embeddings for the document index",
            "Call the model API to draft a report section",
        ],
    ),
    "data_api": CategoryProfile(
        vendors=["api.polygon.io", "api.bloomberg.com", "serpapi.com", "api.weatherstack.com", "newsapi.org"],
        purposes=["market data feed", "search API usage", "real-time data feed access"],
        intents=[
            "Pull live market data for the trading dashboard",
            "Query search results for competitive research",
            "Fetch the latest news feed for the briefing",
        ],
    ),
    "storage_bandwidth": CategoryProfile(
        vendors=["s3.amazonaws.com", "storage.googleapis.com", "r2.cloudflarestorage.com", "backblaze.com"],
        purposes=["object storage", "CDN bandwidth", "backup storage"],
        intents=[
            "Store processed dataset artifacts",
            "Serve static assets via CDN",
            "Back up the nightly database snapshot",
        ],
    ),
    "saas_subscription": CategoryProfile(
        vendors=["notion.so", "linear.app", "figma.com", "slack.com", "airtable.com"],
        purposes=["team workspace subscription", "monthly seat renewal", "project management subscription"],
        intents=[
            "Renew the monthly workspace subscription",
            "Pay for an additional team seat",
            "Auto-renew the project board subscription",
        ],
    ),
    "software_tools": CategoryProfile(
        vendors=["jetbrains.com", "sketch.com", "1password.com", "github.com", "sentry.io"],
        purposes=["IDE license", "one-off plugin license", "developer tool license"],
        intents=[
            "Purchase an annual IDE license",
            "Buy a one-off plugin license",
            "Upgrade the error-monitoring tool tier",
        ],
    ),
    "content_media": CategoryProfile(
        vendors=["shutterstock.com", "istockphoto.com", "elevenlabs.io", "artlist.io", "epidemicsound.com"],
        purposes=["stock image licensing", "voice generation credits", "stock music licensing"],
        intents=[
            "License stock images for the blog post",
            "Generate a voiceover for the product video",
            "License background music for the ad",
        ],
    ),
    "communications": CategoryProfile(
        vendors=["twilio.com", "sendgrid.com", "vonage.com", "postmark.com"],
        purposes=["SMS delivery", "transactional email delivery", "voice call delivery"],
        intents=[
            "Send SMS delivery notifications to users",
            "Send transactional emails for order confirmations",
            "Place an automated reminder call",
        ],
    ),
    "advertising_promotion": CategoryProfile(
        vendors=["ads.google.com", "ads.meta.com", "ads.tiktok.com", "ads.x.com"],
        purposes=["ad campaign", "boosted post promotion", "sponsored listing"],
        intents=[
            "Run a paid ad campaign for the product launch",
            "Boost a post to a target audience",
            "Pay for a sponsored search listing",
        ],
    ),
    "commerce_goods": CategoryProfile(
        vendors=["amazon.com", "shopify.com", "bestbuy.com", "staples.com"],
        purposes=["office supplies purchase", "hardware purchase", "equipment purchase"],
        intents=[
            "Purchase office supplies for the team",
            "Order a replacement laptop charger",
            "Buy a webcam for the meeting room",
        ],
    ),
    "commerce_services": CategoryProfile(
        vendors=["taskrabbit.com", "instacart.com", "doordash.com", "urbansitter.com"],
        purposes=["book a delivery task", "book a grocery delivery", "book a courier task"],
        intents=[
            "Book a same-day delivery task",
            "Order groceries for the office kitchen",
            "Arrange a courier pickup",
        ],
    ),
    "travel_logistics": CategoryProfile(
        vendors=["expedia.com", "booking.com", "uber.com", "delta.com"],
        purposes=["flight booking", "hotel booking", "ground transport booking"],
        intents=[
            "Book a flight for the conference trip",
            "Reserve a hotel room for the offsite",
            "Book ground transport to the airport",
        ],
    ),
    "financial_fees": CategoryProfile(
        vendors=["stripe.com", "wise.com", "plaid.com", "adyen.com"],
        purposes=["payment processing fee", "FX conversion fee", "facilitator fee"],
        intents=[
            "Pay the processing fee on a settled invoice",
            "Cover the FX conversion fee on a cross-border payment",
            "Pay the payment facilitator's service fee",
        ],
    ),
    "network_gas_fees": CategoryProfile(
        vendors=["base_network", "ethereum_network", "arbitrum_network"],
        purposes=["settlement gas fee", "on-chain transaction fee", "network relay fee"],
        intents=[
            "Pay gas fee to settle an x402 payment on Base",
            "Cover the on-chain transaction fee for settlement",
            "Pay the relay fee for a pending settlement",
        ],
    ),
    "human_services": CategoryProfile(
        vendors=["upwork.com", "fiverr.com", "toptal.com", "mturk.com"],
        purposes=["freelancer task", "human-in-the-loop review task", "contractor payment"],
        intents=[
            "Pay a freelancer for a human-in-the-loop review task",
            "Pay a contractor for a data-labeling task",
            "Pay a specialist for a one-off consulting task",
        ],
    ),
    "deposits_transfers": CategoryProfile(
        vendors=["wise.com", "circle.com", "coinbase.com", "revolut.com"],
        purposes=["internal wallet top-up", "treasury transfer", "operating balance top-up"],
        intents=[
            "Top up the agent's operating wallet",
            "Move funds between internal treasury accounts",
            "Replenish the operating balance for the month",
        ],
    ),
    "other_unclassified": CategoryProfile(
        vendors=["miscvendor.example", "generalservices.example"],
        purposes=["general operating expense", "miscellaneous charge"],
        intents=[
            "Pay a general operating expense that doesn't fit a specific category",
            "Cover a miscellaneous charge from a one-off vendor",
        ],
    ),
}


def vendor_pool_for_split(category: str, split: str) -> list[str]:
    """PRD §3.5: test/val must come from "a held-out generator config with
    disjoint vendors... no template overlap with train". Reserves the last
    ~25% (min 1) of each category's vendor list exclusively for val/test;
    train draws only from the rest. Keeps every pool non-empty even for the
    smallest category lists (down to 2 vendors)."""
    vendors = CATEGORY_PROFILES[category].vendors
    heldout_count = max(1, round(len(vendors) * 0.25))
    train_vendors = vendors[:-heldout_count]
    heldout_vendors = vendors[-heldout_count:]
    if not train_vendors:  # pool of 1 — fall back to sharing rather than an empty pool
        return vendors
    return heldout_vendors if split in ("val", "test") else train_vendors


def lookalike_domain(domain: str) -> str:
    """PRD §3.5 hard negative: api.openai.com vs api.openai.com.pay-verify.net."""
    return f"{domain}.pay-verify.net"


def poisoned_address(address: str) -> str:
    """Appendix C.2 hard negative: same prefix/suffix, differing middle segment."""
    if len(address) < 12:
        return address[:-1] + ("0" if address[-1] != "0" else "1")
    head, mid, tail = address[:6], address[6:-6], address[-6:]
    swapped = "".join(("1" if c == "0" else "0") if c.isalnum() else c for c in mid)
    return head + swapped + tail


SAMPLE_WALLET_ADDRESSES: list[str] = [
    "0x71C7656EC7ab88b098defB751B7401B5f6d8976",
    "0x8ba1f109551bD432803012645Ac136ddd64DBA7",
    "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9",
    "0x4E83362442B8d1beC281594ceA3050c8EB01311",
]
