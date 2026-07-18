from backend.agents.base_agent import AgentRequest, AgentResponse, BaseAgent


class AgentRegistry:
    def __init__(self): self._agents: dict[str, BaseAgent] = {}
    def register(self, agent: BaseAgent):
        if agent.name in self._agents: raise ValueError(f"Agent '{agent.name}' ist bereits registriert.")
        self._agents[agent.name] = agent
        return agent
    def get(self, name: str) -> BaseAgent:
        if name not in self._agents: raise KeyError(name)
        return self._agents[name]
    def has_agent(self, name: str) -> bool: return name in self._agents
    def list_agents(self): return [agent.health_check() for agent in self._agents.values()]
    def execute(self, name: str, request: AgentRequest, **kwargs) -> AgentResponse: return self.get(name).execute(request, **kwargs)
    def health_check(self):
        agents = {name: agent.health_check() for name, agent in self._agents.items()}
        return {"status": "ok" if all(item["available"] for item in agents.values()) else "degraded", "registry_status": "available", "agents": agents}


agent_registry = AgentRegistry()
