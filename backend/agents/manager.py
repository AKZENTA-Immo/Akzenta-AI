from backend.adapters import MockCalendarAdapter, MockGmailAdapter, MockOnOfficeAdapter, MockPhoneAdapter, MockWhatsAppAdapter
from backend.agents.services import CalendarAgentService, CrmAgentService, EmailAgentService, WorkflowCoreService


class AgentManager:
    def __init__(self):
        self.crm = CrmAgentService(MockOnOfficeAdapter())
        self.email = EmailAgentService(MockGmailAdapter())
        self.calendar = CalendarAgentService(MockCalendarAdapter())
        self.workflow_core = WorkflowCoreService(self.crm, self.email, self.calendar)
        self.future_adapters = {"whatsapp": MockWhatsAppAdapter(), "phone": MockPhoneAdapter()}

    def statuses(self):
        return [self.crm.status(), self.email.status(), self.calendar.status(), self.workflow_core.status()]


agent_manager = AgentManager()
