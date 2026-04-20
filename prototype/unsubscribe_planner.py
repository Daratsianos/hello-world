#!/usr/bin/env python3
"""Dry-run planner for Outlook trusted-sender unsubscribe automation.

This prototype does not connect to Microsoft Graph yet. It demonstrates the
core policy and approval flow using local JSON input.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


@dataclass
class SenderStats:
    sender: str
    domain: str
    messages_30d: int = 0
    opened_30d: int = 0
    replied_30d: int = 0
    clicked_30d: int = 0
    work_or_billing_keywords: bool = False
    list_unsubscribe_available: bool = False
    allowlisted: bool = False
    previously_unsubscribed: bool = False


@dataclass
class BatchItem:
    sender: str
    domain: str
    trust_score: int
    reason: str
    action: str


def load_messages(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of message objects")
    return data


def keyword_hit(subject: str) -> bool:
    subject_lower = subject.lower()
    keywords = ("invoice", "receipt", "billing", "security", "mfa", "verification")
    return any(k in subject_lower for k in keywords)


def aggregate(messages: List[dict], allow_domains: set[str], deny_domains: set[str]) -> Dict[str, SenderStats]:
    stats: Dict[str, SenderStats] = {}
    for msg in messages:
        sender = msg.get("sender", "").strip().lower()
        if "@" not in sender:
            continue
        domain = sender.split("@", 1)[1]

        s = stats.setdefault(sender, SenderStats(sender=sender, domain=domain))
        s.messages_30d += 1
        s.opened_30d += 1 if msg.get("opened") else 0
        s.replied_30d += 1 if msg.get("replied") else 0
        s.clicked_30d += 1 if msg.get("clicked") else 0
        s.list_unsubscribe_available = s.list_unsubscribe_available or bool(msg.get("list_unsubscribe"))
        s.work_or_billing_keywords = s.work_or_billing_keywords or keyword_hit(msg.get("subject", ""))
        s.allowlisted = domain in allow_domains
        s.previously_unsubscribed = domain in deny_domains
    return stats


def trust_score(s: SenderStats) -> int:
    score = 50
    if s.allowlisted:
        score += 25
    if s.replied_30d > 0:
        score += 20
    if s.work_or_billing_keywords:
        score += 10
    if s.opened_30d == 0:
        score -= 20
    if s.messages_30d > 10 and (s.opened_30d + s.clicked_30d + s.replied_30d) <= 2:
        score -= 15
    if s.clicked_30d == 0 and s.replied_30d == 0 and s.messages_30d >= 3:
        score -= 25
    if s.previously_unsubscribed:
        score -= 30
    return max(0, min(100, score))


def classify(score: int) -> str:
    if score >= 70:
        return "trusted"
    if score >= 40:
        return "review"
    return "candidate_unsubscribe"


def reason_for(s: SenderStats, score: int) -> str:
    reasons = []
    if s.opened_30d == 0:
        reasons.append("never opened")
    if s.clicked_30d == 0 and s.replied_30d == 0 and s.messages_30d >= 3:
        reasons.append("high volume with no engagement")
    if s.previously_unsubscribed:
        reasons.append("similar domain unsubscribed before")
    if score >= 70:
        reasons.append("active relationship")
    return ", ".join(reasons) if reasons else "mixed signals"


def action_for(s: SenderStats) -> str:
    return "unsubscribe_header" if s.list_unsubscribe_available else "move_to_junk"


def build_batch(stats: Dict[str, SenderStats]) -> List[BatchItem]:
    items: List[BatchItem] = []
    for sender, s in sorted(stats.items()):
        score = trust_score(s)
        status = classify(score)
        if status == "candidate_unsubscribe":
            items.append(
                BatchItem(
                    sender=sender,
                    domain=s.domain,
                    trust_score=score,
                    reason=reason_for(s, score),
                    action=action_for(s),
                )
            )
    return items


def print_report(stats: Dict[str, SenderStats], batch: List[BatchItem]) -> None:
    trusted = []
    review = []
    candidate = []
    for sender, s in sorted(stats.items()):
        score = trust_score(s)
        row = (sender, score)
        status = classify(score)
        if status == "trusted":
            trusted.append(row)
        elif status == "review":
            review.append(row)
        else:
            candidate.append(row)

    print("=== TRUSTED ===")
    for sender, score in trusted:
        print(f"- {sender} (score {score})")

    print("\n=== REVIEW ===")
    for sender, score in review:
        print(f"- {sender} (score {score})")

    print("\n=== CANDIDATE UNSUBSCRIBE BATCH ===")
    for item in batch:
        print(f"- {item.sender} (score {item.trust_score}) -> {item.action}; {item.reason}")


def execute_batch(batch: List[BatchItem], state_path: Path) -> None:
    state = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "items": [asdict(item) for item in batch],
    }
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Executed dry-run unsubscribe batch with {len(batch)} items.")
    print(f"Wrote execution log to: {state_path}")


def load_lines(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    return {line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run unsubscribe planner")
    parser.add_argument("--input", required=True, type=Path, help="Path to sample messages JSON")
    parser.add_argument("--allowlist", type=Path, help="Optional domain allowlist (one per line)")
    parser.add_argument("--denylist", type=Path, help="Optional domain denylist (one per line)")
    parser.add_argument("--approve-all", action="store_true", help="Execute candidate batch immediately")
    parser.add_argument("--state", type=Path, default=Path("prototype/executed_batch.json"))
    args = parser.parse_args()

    allow_domains = load_lines(args.allowlist)
    deny_domains = load_lines(args.denylist)
    messages = load_messages(args.input)
    stats = aggregate(messages, allow_domains=allow_domains, deny_domains=deny_domains)
    batch = build_batch(stats)

    print_report(stats, batch)

    if args.approve_all:
        execute_batch(batch, args.state)
    else:
        print("\nBatch is pending approval. Re-run with --approve-all to execute.")


if __name__ == "__main__":
    main()
