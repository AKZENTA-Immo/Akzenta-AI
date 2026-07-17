from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    connected: bool = False
    mock: bool = True


class ProviderNotConnected(RuntimeError):
    pass


class BaseAdapter(ABC):
    @abstractmethod
    def status(self) -> ProviderStatus: ...

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise ProviderNotConnected("Anbieterzugang ist nicht bestätigt; externe Aktion wurde blockiert.")


class OnOfficeAdapter(BaseAdapter): pass
class GmailAdapter(BaseAdapter): pass
class CalendarAdapter(BaseAdapter): pass
class WhatsAppAdapter(BaseAdapter): pass
class PhoneAdapter(BaseAdapter): pass


class _MockAdapter(BaseAdapter):
    provider_name = "mock"

    def status(self) -> ProviderStatus:
        return ProviderStatus(name=self.provider_name)


class MockOnOfficeAdapter(_MockAdapter, OnOfficeAdapter): provider_name = "onOffice"
class MockGmailAdapter(_MockAdapter, GmailAdapter): provider_name = "Gmail"
class MockCalendarAdapter(_MockAdapter, CalendarAdapter): provider_name = "Google Calendar"
class MockWhatsAppAdapter(_MockAdapter, WhatsAppAdapter): provider_name = "WhatsApp Business"
class MockPhoneAdapter(_MockAdapter, PhoneAdapter): provider_name = "Telefonanbieter"
