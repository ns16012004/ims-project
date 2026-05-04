"""
Alerting Strategy - Strategy Design Pattern

Different component failures require different alerting behaviors.
New strategies can be added without modifying existing code (Open/Closed Principle).
"""
from abc import ABC, abstractmethod
from loguru import logger
from ..models.schemas import Priority, ComponentType


class AlertStrategy(ABC):
    """Abstract base for all alerting strategies."""

    @abstractmethod
    def get_priority(self) -> Priority:
        pass

    @abstractmethod
    def format_alert(self, component_id: str, signal_type: str, message: str) -> dict:
        pass

    @abstractmethod
    def notify(self, alert: dict):
        pass


class P0CriticalAlert(AlertStrategy):
    """P0 - Critical: RDBMS / core infrastructure failures. Immediate page."""

    def get_priority(self) -> Priority:
        return Priority.P0

    def format_alert(self, component_id: str, signal_type: str, message: str) -> dict:
        return {
            "priority": "P0",
            "severity": "CRITICAL",
            "component_id": component_id,
            "signal_type": signal_type,
            "message": message,
            "channel": "pagerduty+slack+email",
            "escalation": "immediate",
            "title": f"🔴 P0 CRITICAL: {component_id} FAILURE",
        }

    def notify(self, alert: dict):
        logger.critical(
            f"🔴 [P0 ALERT] {alert['title']} | "
            f"Channel: {alert['channel']} | "
            f"Escalation: {alert['escalation']}"
        )


class P1HighAlert(AlertStrategy):
    """P1 - High: API / MCP Host / Queue failures."""

    def get_priority(self) -> Priority:
        return Priority.P1

    def format_alert(self, component_id: str, signal_type: str, message: str) -> dict:
        return {
            "priority": "P1",
            "severity": "HIGH",
            "component_id": component_id,
            "signal_type": signal_type,
            "message": message,
            "channel": "slack+email",
            "escalation": "15min",
            "title": f"🟠 P1 HIGH: {component_id} degraded",
        }

    def notify(self, alert: dict):
        logger.error(
            f"🟠 [P1 ALERT] {alert['title']} | "
            f"Channel: {alert['channel']}"
        )


class P2MediumAlert(AlertStrategy):
    """P2 - Medium: Cache / NoSQL failures."""

    def get_priority(self) -> Priority:
        return Priority.P2

    def format_alert(self, component_id: str, signal_type: str, message: str) -> dict:
        return {
            "priority": "P2",
            "severity": "MEDIUM",
            "component_id": component_id,
            "signal_type": signal_type,
            "message": message,
            "channel": "slack",
            "escalation": "1hr",
            "title": f"🟡 P2 MEDIUM: {component_id} issue",
        }

    def notify(self, alert: dict):
        logger.warning(
            f"🟡 [P2 ALERT] {alert['title']} | "
            f"Channel: {alert['channel']}"
        )


class AlertStrategyFactory:
    """
    Factory that returns the correct alerting strategy
    based on the component type. Fully extensible.
    """

    _strategies: dict[str, AlertStrategy] = {
        ComponentType.RDBMS: P0CriticalAlert(),
        ComponentType.API: P1HighAlert(),
        ComponentType.MCP_HOST: P1HighAlert(),
        ComponentType.ASYNC_QUEUE: P1HighAlert(),
        ComponentType.NOSQL: P2MediumAlert(),
        ComponentType.DISTRIBUTED_CACHE: P2MediumAlert(),
    }

    @classmethod
    def get_strategy(cls, component_type: str) -> AlertStrategy:
        strategy = cls._strategies.get(component_type)
        if not strategy:
            logger.warning(f"No strategy for component type '{component_type}', defaulting to P2")
            return P2MediumAlert()
        return strategy

    @classmethod
    def fire_alert(cls, component_id: str, component_type: str, signal_type: str, message: str) -> dict:
        strategy = cls.get_strategy(component_type)
        alert = strategy.format_alert(component_id, signal_type, message)
        strategy.notify(alert)
        return alert
