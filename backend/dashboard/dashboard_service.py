from datetime import datetime,timezone
from .models import DashboardOverview
class DashboardService:
    def __init__(self,conversations,workflows,leads,agents,events): self.conversations=conversations; self.workflows=workflows; self.leads=leads; self.agents=agents; self.events=events
    def overview(self):
        today=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
        calls=self.conversations.list(date_from=today,limit=10000,offset=0); all_active=self.conversations.list(status='active',limit=10000,offset=0); workflows=self.workflows.list(limit=10000,offset=0); leads=self.leads.list(date_from=today,limit=10000,offset=0)
        return DashboardOverview(active_conversations=len(all_active),conversations_today=len(calls),open_escalations=sum(bool(c.escalation_status) for c in all_active),open_appointments=sum(bool(c.appointment_status) for c in calls),prepared_followups=sum(bool(c.followup_status) for c in calls),active_workflows=sum(w.status in ('created','running','waiting_for_approval','paused') for w in workflows),failed_workflows=sum(w.status=='failed' for w in workflows),new_leads=len(leads),average_lead_score=round(sum(l.lead_score for l in leads)/len(leads),2) if leads else 0,agent_statuses=self.agents.list(),recent_events=self.events.list_events(limit=10))
