from advisor.selector import select_agents


def test_frontend_only_never_activates_cloud():
    plan = select_agents(["frontend"], cloud_relevant=False)
    assert "cloud" not in plan.agents
    assert set(plan.agents) == {"frontend", "uiux", "security", "performance"}


def test_fullstack_without_cloud():
    plan = select_agents(["fullstack"], cloud_relevant=False)
    assert {"frontend", "backend", "database"} <= set(plan.agents)
    assert "cloud" not in plan.agents


def test_cloud_flag_adds_cloud_agent():
    plan = select_agents(["fullstack", "cloud"], cloud_relevant=True)
    assert "cloud" in plan.agents
    assert "hosting/infrastructure is in scope" in plan.reasons["cloud"]


def test_rag_activates_ai_agent():
    plan = select_agents(["aiml", "backend"], cloud_relevant=False)
    assert {"aiml", "database", "backend", "security"} <= set(plan.agents)


def test_low_confidence_escalates():
    plan = select_agents(["frontend"], cloud_relevant=False, confidence=0.5)
    assert plan.escalate


def test_other_domain_escalates():
    assert select_agents(["other"], cloud_relevant=False).escalate
