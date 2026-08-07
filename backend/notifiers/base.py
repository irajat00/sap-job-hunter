"""Base interface every alert-notification provider implements."""
from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> bool:
        """Sends a message. Returns True on success."""
        raise NotImplementedError
