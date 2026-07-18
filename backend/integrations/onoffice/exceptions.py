class OnOfficeError(RuntimeError): pass
class OnOfficeDisabled(OnOfficeError): pass
class OnOfficeConfigurationError(OnOfficeError): pass
class OnOfficeTimeout(OnOfficeError): pass
class OnOfficeAuthenticationError(OnOfficeError): pass
class OnOfficeUnavailable(OnOfficeError): pass
class OnOfficeResponseError(OnOfficeError): pass
