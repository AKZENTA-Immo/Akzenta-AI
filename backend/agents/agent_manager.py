import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from backend.agents.base_agent import AgentRequest
from backend.agents.registry import AgentRegistry, agent_registry
from backend.agents.suite import register_default_agents

AgentTarget = Literal["crm", "email", "kalender", "whatsapp", "telefon", "marketing", "dokumente", "immobilien", "allgemein"]

class AgentManagerRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    simulation: bool = True
    context: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = None
    conversation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    @field_validator("message")
    @classmethod
    def validate_message(cls,value):
        value=value.strip()
        if not value: raise ValueError("Die Nachricht darf nicht leer sein.")
        return value

class AgentManagerResult(BaseModel):
    agent: AgentTarget
    display_name: str
    action: str
    confidence: float = Field(ge=0,le=1)
    reason: str
    original_message: str
    simulation: bool
    uncertain: bool=False
    secondary_agents: list[str]=Field(default_factory=list)
    result: dict[str,Any]

class AgentExecutionResponse(BaseModel):
    agent: AgentTarget
    display_name: str
    action: str
    intent: str
    confidence: float=Field(ge=0,le=1)
    reason: str
    reasoning: str
    simulation: bool=True
    approval_required: bool=True
    requires_confirmation: bool=True
    status: Literal["simulated","blocked","error","confirmation_required","not_supported","validation_error","rejected"]
    result: dict[str,Any]
    missing_information: list[str]=Field(default_factory=list)
    proposed_actions: list[str]=Field(default_factory=list)
    warnings: list[str]=Field(default_factory=list)
    uncertain: bool=False
    secondary_agents: list[str]=Field(default_factory=list)
    error: str|None=None
    metadata: dict[str,Any]=Field(default_factory=dict)

@dataclass(frozen=True)
class RoutingDecision:
    agent: AgentTarget
    confidence: float
    reason: str
    uncertain: bool=False
    secondary_agents: tuple[str,...]=()

class MessageClassifier(Protocol):
    def classify(self,message:str)->RoutingDecision: ...

class DeterministicMessageClassifier:
    rules=(
        (110,"whatsapp",("whatsapp","wa-nachricht","chatnachricht","kurze nachricht"),"WhatsApp-Schlüsselwörter erkannt"),
        (105,"telefon",("anrufen","telefon","telefonat","rückruf","gesprächsleitfaden","einwandbehandlung"),"Telefon-Schlüsselwörter erkannt"),
        (100,"email",("e-mail","email","mail","betreff","empfänger","nachfassmail","schreibe herr","schreibe frau"),"E-Mail-Schlüsselwörter erkannt"),
        (95,"kalender",("termin","kalender","besichtigung planen"," uhr","montag","freitag","video-call","verschieben"),"Kalender-Schlüsselwörter erkannt"),
        (90,"dokumente",("dokument","pdf","energieausweis","grundriss","kaufvertrag","teilungserklärung","wirtschaftsplan","grundbuchauszug","wissensbasis"),"Dokumenten-Schlüsselwörter erkannt"),
        (85,"crm",("crm","onoffice","lead","kunde","interessent","eigentümer","wiedervorlage","notiz"),"CRM-Schlüsselwörter erkannt"),
        (80,"marketing",("marketing","kampagne","newsletter","instagram","facebook","social media","video-script","hook","landingpage","google ads"),"Marketing-Schlüsselwörter erkannt"),
        (70,"immobilien",("immobilientext","objektbeschreibung","lagebeschreibung","exposétext","anzeigentext","wohnfläche"),"Immobilien-Schlüsselwörter erkannt"),
    )
    def classify(self,message):
        normalized=re.sub(r"\s+"," ",message.casefold()); matches=[]
        for priority,agent,keywords,reason in self.rules:
            hits=sum(keyword in normalized for keyword in keywords)
            if hits: matches.append((priority,hits,agent,reason))
        if not matches:return RoutingDecision("allgemein",.4,"Keine eindeutigen Agenten-Schlüsselwörter erkannt",True)
        matches.sort(key=lambda x:(x[0],x[1]),reverse=True); priority,hits,agent,reason=matches[0]
        secondary=tuple(item[2] for item in matches[1:] if item[2]!=agent); uncertain=bool(secondary)
        confidence=.68 if uncertain else min(.99,.86+hits*.04)
        if uncertain:reason += "; mehrere Fähigkeiten erkannt, Prioritätsregel angewendet"
        return RoutingDecision(agent,confidence,reason,uncertain,secondary)

class CentralAgentManager:
    def __init__(self,classifier:MessageClassifier|None=None,agents:dict|None=None,registry:AgentRegistry|None=None):
        self.classifier=classifier or DeterministicMessageClassifier(); self.registry=registry or register_default_agents(); self.legacy_agents=agents
    def _request(self,r):return AgentRequest(message=r.message,simulation=r.simulation,context=r.context,user_id=r.user_id,conversation_id=r.conversation_id,metadata=r.metadata)
    def _execute(self,r,decision):
        if self.legacy_agents is not None:
            legacy=self.legacy_agents.get(decision.agent)
            if legacy is None and decision.agent=="allgemein": legacy=self.legacy_agents.get("allgemein")
            if legacy is None: raise KeyError(decision.agent)
            return legacy.execute(r.message,decision)
        return self.registry.execute(decision.agent,self._request(r),confidence=decision.confidence,reason=decision.reason)
    def route(self,r):
        decision=self.classifier.classify(r.message)
        response=self._execute(r,decision)
        status="blocked" if not r.simulation else response.status
        return AgentManagerResult(agent=decision.agent,display_name=getattr(response,"display_name",decision.agent),action=getattr(response,"action","unknown"),confidence=decision.confidence,reason=decision.reason,original_message=r.message,simulation=r.simulation,uncertain=decision.uncertain,secondary_agents=list(decision.secondary_agents),result={"status":status,"external_action_executed":False})
    def execute(self,r):
        decision=self.classifier.classify(r.message)
        if self.legacy_agents is not None:
            try:return self._execute(r,decision)
            except Exception:return AgentExecutionResponse(agent=decision.agent,display_name="Allgemeiner Assistent",action="agent_error",intent="agent_error",confidence=decision.confidence,reason=decision.reason,reasoning=decision.reason,status="error",result={"external_action_executed":False},warnings=["Der simulierte Agent konnte die Anfrage nicht sicher verarbeiten."],uncertain=decision.uncertain)
        response=self._execute(r,decision); status="blocked" if response.status=="rejected" else response.status
        return AgentExecutionResponse(agent=decision.agent,display_name=response.display_name,action=response.action,intent=response.action,confidence=decision.confidence,reason=decision.reason,reasoning=decision.reason,simulation=response.simulation,approval_required=response.requires_confirmation,requires_confirmation=response.requires_confirmation,status=status,result=response.result,missing_information=response.missing_information,proposed_actions=[f"{response.action} als Vorschau prüfen"],warnings=response.warnings,uncertain=decision.uncertain,secondary_agents=list(decision.secondary_agents),error=response.error,metadata=response.metadata)

central_agent_manager=CentralAgentManager()
