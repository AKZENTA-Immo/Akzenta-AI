from backend.adapters.providers import (
    CalendarAdapter, GmailAdapter, MockCalendarAdapter, MockGmailAdapter,
    MockOnOfficeAdapter, MockPhoneAdapter, MockWhatsAppAdapter, OnOfficeAdapter,
    PhoneAdapter, ProviderStatus, WhatsAppAdapter,
)

__all__ = [name for name in globals() if name.endswith("Adapter") or name == "ProviderStatus"]
