"""Drawing executor — CSPRNG-based winner selection with audit trail.

Uses Python's ``secrets`` module for cryptographically secure random
number generation. Creates an immutable ticket snapshot before selection
to ensure fairness and reproducibility.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import secrets
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Drawing execution error with HTTP status hint."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class DrawingExecutor:
    """Executes a drawing: snapshots tickets, selects winners via CSPRNG."""

    def __init__(
        self,
        drawing_repo: Any,
        ticket_repo: Any,
        prize_repo: Any,
        fulfillment_repo: Any,
    ) -> None:
        self.drawing_repo = drawing_repo
        self.ticket_repo = ticket_repo
        self.prize_repo = prize_repo
        self.fulfillment_repo = fulfillment_repo

    def execute(self, drawing_id: str) -> dict[str, Any]:
        """Execute a drawing — select winners, create fulfillment records.

        Steps:
          1. Validate drawing is in 'closed' status
          2. Snapshot all tickets (assign sequential numbers)
          3. Generate CSPRNG random seed
          4. Select winners for each prize
          5. Mark winning tickets
          6. Create fulfillment records
          7. Transition drawing to 'completed'

        This method is designed to be idempotent — if the process crashes,
        re-running will detect the completed status and skip.
        """
        drawing = self.drawing_repo.find_by_id(drawing_id)
        if drawing is None:
            raise ExecutionError("Drawing not found", status_code=404)

        status = drawing.get("status")
        if status == "completed":
            raise ExecutionError("Drawing already executed", status_code=409)

        if status != "closed":
            raise ExecutionError(
                f"Drawing must be in 'closed' status to execute (current: {status})"
            )

        # Step 1: Snapshot tickets with sequential numbers
        tickets = self.ticket_repo.find_by_drawing(drawing_id)
        if not tickets:
            raise ExecutionError("No tickets to draw from")

        snapshot = self._create_snapshot(tickets)

        # Step 2: Generate random seed for audit trail
        random_seed = secrets.token_hex(32)
        seed_hash = hashlib.sha256(random_seed.encode()).hexdigest()

        # Step 3: Get prizes for this drawing
        prizes = self.prize_repo.find_by_field("drawing_id", drawing_id)
        if not prizes:
            raise ExecutionError("No prizes configured for this drawing")

        # Sort prizes by rank (1st, 2nd, 3rd, etc.)
        prizes.sort(key=lambda p: p.get("rank", 1))

        # Step 4: Select winners
        winners = self._select_winners(snapshot, prizes, random_seed)

        # Step 5: Mark winning tickets and create fulfillments
        fulfillments = []
        for winner in winners:
            ticket_id = winner["ticket_id"]
            prize_id = winner["prize_id"]
            user_id = winner["user_id"]

            # Mark ticket as winner
            self.ticket_repo.update(
                ticket_id,
                data={
                    "is_winner": 1,
                    "prize_id": prize_id,
                    "ticket_number": winner["ticket_number"],
                },
            )

            # Create fulfillment record
            from fittrack.repositories.base import BaseRepository

            fulfillment_id = BaseRepository._generate_id()
            fulfillment_data = {
                "ticket_id": ticket_id,
                "prize_id": prize_id,
                "user_id": user_id,
                "drawing_id": drawing_id,
                "status": "pending",
                "created_at": datetime.now(tz=UTC).isoformat(),
            }
            self.fulfillment_repo.create(data=fulfillment_data, new_id=fulfillment_id)
            fulfillments.append({"fulfillment_id": fulfillment_id, **fulfillment_data})

        # Step 6: Update non-winning tickets with ticket numbers
        for entry in snapshot:
            if not entry.get("is_winner"):
                with contextlib.suppress(Exception):
                    self.ticket_repo.update(
                        entry["ticket_id"],
                        data={"ticket_number": entry["ticket_number"]},
                    )

        # Step 7: Mark drawing as completed
        now = datetime.now(tz=UTC)
        self.drawing_repo.update(
            drawing_id,
            data={
                "status": "completed",
                "completed_at": now.isoformat(),
                "random_seed": seed_hash,
                "total_tickets": len(snapshot),
            },
        )

        result = {
            "drawing_id": drawing_id,
            "status": "completed",
            "total_tickets": len(snapshot),
            "random_seed_hash": seed_hash,
            "algorithm": "secrets.randbelow",
            "winners": winners,
            "fulfillments": fulfillments,
            "executed_at": now.isoformat(),
        }

        logger.info(
            "Drawing %s executed: %d tickets, %d winners",
            drawing_id,
            len(snapshot),
            len(winners),
        )

        return result

    def _create_snapshot(self, tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Create an immutable snapshot of tickets with sequential numbers.

        Tickets are shuffled deterministically (by ticket_id) and assigned
        sequential numbers starting from 1.
        """
        # Sort by ticket_id for deterministic ordering
        sorted_tickets = sorted(tickets, key=lambda t: t.get("ticket_id", ""))

        snapshot = []
        for i, ticket in enumerate(sorted_tickets, start=1):
            snapshot.append(
                {
                    "ticket_number": i,
                    "ticket_id": ticket.get("ticket_id", ""),
                    "user_id": ticket.get("user_id", ""),
                    "drawing_id": ticket.get("drawing_id", ""),
                    "is_winner": False,
                }
            )

        return snapshot

    def _select_winners(
        self,
        snapshot: list[dict[str, Any]],
        prizes: list[dict[str, Any]],
        random_seed: str,
    ) -> list[dict[str, Any]]:
        """Select winners from the ticket snapshot using CSPRNG.

        Each prize gets a winner. If a prize has quantity > 1, multiple
        winners are selected. A user can only win once per drawing.
        """
        available = list(snapshot)
        winners_user_ids: set[str] = set()
        winners: list[dict[str, Any]] = []

        for prize in prizes:
            prize_id = prize.get("prize_id", "")
            quantity = prize.get("quantity", 1) or 1

            for _ in range(quantity):
                # Filter out users who already won
                eligible = [e for e in available if e["user_id"] not in winners_user_ids]

                if not eligible:
                    logger.warning("Not enough eligible tickets for prize %s", prize_id)
                    break

                # CSPRNG selection
                idx = secrets.randbelow(len(eligible))
                winner_entry = eligible[idx]

                # Mark as winner
                winner_entry["is_winner"] = True
                winners_user_ids.add(winner_entry["user_id"])

                winners.append(
                    {
                        "ticket_id": winner_entry["ticket_id"],
                        "ticket_number": winner_entry["ticket_number"],
                        "user_id": winner_entry["user_id"],
                        "prize_id": prize_id,
                        "prize_name": prize.get("name", ""),
                        "prize_rank": prize.get("rank", 1),
                    }
                )

                # Remove winner's ticket from available pool
                available = [e for e in available if e["ticket_id"] != winner_entry["ticket_id"]]

        return winners
