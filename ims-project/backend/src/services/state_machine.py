"""
Work Item State Machine - State Design Pattern

Manages the lifecycle: OPEN → INVESTIGATING → RESOLVED → CLOSED
Each state encapsulates its own valid transitions and guards.
"""
from abc import ABC, abstractmethod
from loguru import logger


class WorkItemState(ABC):
    """Abstract base state."""

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def allowed_transitions(self) -> list[str]:
        pass

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.allowed_transitions()

    def transition(self, new_status: str, rca=None) -> "WorkItemState":
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Invalid transition: {self.get_name()} → {new_status}. "
                f"Allowed: {self.allowed_transitions()}"
            )
        # Guard: RESOLVED → CLOSED requires a complete RCA
        if new_status == "CLOSED":
            if not rca:
                raise ValueError(
                    "Cannot close a Work Item without a complete RCA. "
                    "Please submit the Root Cause Analysis first."
                )
        logger.info(f"Work item state: {self.get_name()} → {new_status}")
        return STATE_MAP[new_status]()


class OpenState(WorkItemState):
    def get_name(self) -> str:
        return "OPEN"

    def allowed_transitions(self) -> list[str]:
        return ["INVESTIGATING"]


class InvestigatingState(WorkItemState):
    def get_name(self) -> str:
        return "INVESTIGATING"

    def allowed_transitions(self) -> list[str]:
        return ["RESOLVED", "OPEN"]  # Can reopen if needed


class ResolvedState(WorkItemState):
    def get_name(self) -> str:
        return "RESOLVED"

    def allowed_transitions(self) -> list[str]:
        return ["CLOSED", "INVESTIGATING"]  # Can reopen if fix didn't hold


class ClosedState(WorkItemState):
    def get_name(self) -> str:
        return "CLOSED"

    def allowed_transitions(self) -> list[str]:
        return []  # Terminal state


STATE_MAP: dict[str, type[WorkItemState]] = {
    "OPEN": OpenState,
    "INVESTIGATING": InvestigatingState,
    "RESOLVED": ResolvedState,
    "CLOSED": ClosedState,
}


def get_state(status: str) -> WorkItemState:
    """Get state object from status string."""
    cls = STATE_MAP.get(status)
    if not cls:
        raise ValueError(f"Unknown status: {status}")
    return cls()


def validate_transition(current_status: str, new_status: str, rca=None) -> None:
    """
    Validate a state transition. Raises ValueError if invalid.
    Used by the service layer before committing to DB.
    """
    state = get_state(current_status)
    state.transition(new_status, rca=rca)  # Will raise if invalid
