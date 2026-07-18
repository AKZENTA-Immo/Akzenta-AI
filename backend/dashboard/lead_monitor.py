from .models import LeadOverview
class LeadMonitor:
    def __init__(self, conversations): self.conversations=conversations
    def list(self, **filters):
        lead_type=filters.pop('lead_type',None)
        result=[]
        for c in self.conversations.list(**filters):
            item=LeadOverview(lead_id=f"lead_{c.session_id}",name=c.name,phone=c.phone,lead_type=None,lead_score=c.lead_score,status='new',next_action=c.next_action,last_contact=c.ended_at or c.started_at,session_id=c.session_id,workflow_id=c.workflow_id)
            if not lead_type or item.lead_type==lead_type: result.append(item)
        return result
