from haystack.tools import ComponentTool

COMPONENT_NAME = "graph_query_tool"
COMPONENT_DESCRIPTION = "Search in the central graph database containing information about an enterprise's relationships and connections."

graph_query_tool = ComponentTool(
    component=GraphQuery.graph_pipeline,
    name=COMPONENT_NAME,
    description=COMPONENT_DESCRIPTION,
    outputs_to_string={
        "source": "documents",
        "handler": lambda docs: ", ".join(
            set(getattr(doc, "source", "unknown") for doc in docs)
        ),
    },
)
