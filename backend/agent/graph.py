from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from agent.llm import get_llm
from agent.nodes import Deps, Nodes
from agent.state import MemeState
from app.core.config import get_settings
from app.core.storage import get_storage
from rag.search import get_index


def build_graph(deps: Deps):
    n = Nodes(deps)
    g = StateGraph(MemeState)
    g.add_node("understand", n.understand)
    g.add_node("refuse", n.refuse)
    g.add_node("describe_image", n.describe_image)
    g.add_node("pick_templates", n.pick_templates)
    g.add_node("write_captions", n.write_captions)
    g.add_node("render", n.render)
    g.add_node("critique", n.critique)
    g.add_node("select", n.select)

    def after_understand(state: MemeState) -> str:
        if not state["intent"].safe:
            return "refuse"
        return "describe_image" if state.get("upload_key") else "pick_templates"

    g.add_edge(START, "understand")
    g.add_conditional_edges("understand", after_understand, ["refuse", "describe_image", "pick_templates"])
    g.add_conditional_edges(
        "describe_image", lambda s: "refuse" if s.get("refusal") else "write_captions", ["refuse", "write_captions"]
    )
    g.add_edge("pick_templates", "write_captions")
    g.add_edge("write_captions", "render")
    g.add_edge("render", "critique")
    g.add_edge("critique", "select")
    g.add_conditional_edges(
        "select", lambda s: "write_captions" if s.get("decision") == "rewrite" else END, ["write_captions", END]
    )
    g.add_edge("refuse", END)
    return g.compile()


def default_deps() -> Deps:
    return Deps(llm=get_llm(), index=get_index(), storage=get_storage(), settings=get_settings())


@lru_cache
def get_graph():
    return build_graph(default_deps())


def initial_state(job_id: str, topic: str | None, style: str | None, upload_key: str | None, template_id: str | None):
    return {
        "job_id": job_id,
        "topic": topic or "",
        "style": style,
        "upload_key": upload_key,
        "forced_template": template_id,
        "candidates": [],
        "round": 0,
        "winners": [],
        "refusal": None,
        "llm_calls": 0,
    }
