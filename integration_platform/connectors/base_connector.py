from abc import ABC, abstractmethod

class BaseConnector(ABC):
    """Abstract base class for all connectors."""

    @abstractmethod
    def connect(self):
        """Connects to the service."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self):
        """Disconnects from the service."""
        raise NotImplementedError

    @abstractmethod
    def execute_action(self, action_name: str, params: dict):
        """
        Executes a specific action on the service.

        Args:
            action_name: The name of the action to execute.
            params: A dictionary of parameters for the action.
        """
        raise NotImplementedError
