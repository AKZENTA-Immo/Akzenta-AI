from backend.adapters import MockCalendarAdapter, MockGmailAdapter, MockOnOfficeAdapter, MockPhoneAdapter, MockWhatsAppAdapter
from backend.agents.services import ApprovalService, CalendarAgentService, CrmAgentService, EmailAgentService, WorkflowCoreService
from backend.agents.workflow_repository import WorkflowRepository
from backend.agents.workflow_engine import WorkflowOrchestrator


class AgentManager:
    def __init__(self, repository=None):
        self.crm = CrmAgentService(MockOnOfficeAdapter())
        self.email = EmailAgentService(MockGmailAdapter())
        self.calendar = CalendarAgentService(MockCalendarAdapter())
        self.repository = repository or WorkflowRepository()
        self.approvals = ApprovalService(self.repository)
        self.workflow_core = WorkflowCoreService(self.crm, self.email, self.calendar, self.approvals)
        self.workflow_engine = WorkflowOrchestrator(self.repository, self.approvals)
        self.future_adapters = {"whatsapp": MockWhatsAppAdapter(), "phone": MockPhoneAdapter()}

    def statuses(self):
        return [self.crm.status(), self.email.status(), self.calendar.status(), self.workflow_core.status()]

    def safety_status(self):
        return {
            "safe": True, "external_actions": False, "approval_required": True,
            "execution_mode": "simulation", "persistence": "sqlite", "persistent": True,
            "restart_safe": True, "audit_log": True,
            "workflow_engine": True, "multi_step_workflows": True, "resume_enabled": True,
            "retry_enabled": True, "conditions_enabled": True, "dynamic_code_execution": False,
        }


agent_manager = AgentManager()
