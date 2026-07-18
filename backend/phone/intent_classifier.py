from enum import Enum


class PhoneIntent(str, Enum):
    GREETING = "begruessung"
    CALLBACK = "rueckruf"
    SELLER = "verkaeufer"
    INVESTMENT = "kapitalanlage"
    VIEWING = "besichtigung"
    APPOINTMENT = "termin"
    DOCUMENTS = "dokumente"
    PRICE = "preis"
    PROPERTY_QUESTION = "objektfrage"
    FINANCING = "finanzierung"
    REJECTION = "ablehnung"
    GOODBYE = "verabschiedung"
    UNKNOWN = "unbekannt"


class IntentClassifier:
    _RULES = (
        (PhoneIntent.GOODBYE, ("tschüss", "auf wiederhören", "wiederhören")),
        (PhoneIntent.REJECTION, ("kein interesse", "nicht interessiert", "nein danke")),
        (PhoneIntent.CALLBACK, ("rückruf", "zurückrufen", "rufen sie mich")),
        (PhoneIntent.SELLER, ("verkaufen", "verkäufer", "verkauf meiner")),
        (PhoneIntent.INVESTMENT, ("kapitalanlage", "rendite", "investment")),
        (PhoneIntent.VIEWING, ("besichtigung", "besichtigen")),
        (PhoneIntent.APPOINTMENT, ("termin", "uhr", "montag", "dienstag", "mittwoch", "donnerstag", "freitag")),
        (PhoneIntent.DOCUMENTS, ("unterlagen", "dokument", "exposé", "expose")),
        (PhoneIntent.PRICE, ("preis", "kosten", "kaufpreis")),
        (PhoneIntent.FINANCING, ("finanzierung", "kredit", "darlehen")),
        (PhoneIntent.PROPERTY_QUESTION, ("objekt", "wohnung", "haus", "immobilie")),
        (PhoneIntent.GREETING, ("hallo", "guten tag", "guten morgen", "guten abend")),
    )

    def classify(self, text: str) -> PhoneIntent:
        normalized = text.casefold().strip()
        for intent, terms in self._RULES:
            if any(term in normalized for term in terms):
                return intent
        return PhoneIntent.UNKNOWN
