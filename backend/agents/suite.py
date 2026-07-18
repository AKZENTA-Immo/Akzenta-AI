from backend.agents.calendar_agent import CalendarAgent
from backend.agents.crm_agent import CrmAgent
from backend.agents.document_agent import DocumentAgent
from backend.agents.email_agent import EmailAgent
from backend.agents.general_agent import GeneralAgent
from backend.agents.marketing_agent import MarketingAgent
from backend.agents.phone_agent import PhoneAgent
from backend.agents.real_estate_agent import RealEstateAgent
from backend.agents.registry import agent_registry
from backend.agents.whatsapp_agent import WhatsAppAgent

def register_default_agents():
    for agent in (CrmAgent(), EmailAgent(), CalendarAgent(), DocumentAgent(), RealEstateAgent(), MarketingAgent(), PhoneAgent(), WhatsAppAgent(), GeneralAgent()):
        if not agent_registry.has_agent(agent.name): agent_registry.register(agent)
    return agent_registry

register_default_agents()
