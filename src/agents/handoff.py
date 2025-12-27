import inspect
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class HandoffTool:
    """A tool for handing off control between agents."""

    def __init__(
        self,
        target_agent: Any,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """
        Initialize the handoff tool.

        Args:
            target_agent: Target agent to hand off to
            name: Tool name (defaults to "transfer_to_{agent_name}")
            description: Tool description (defaults to an auto-generated description)
        """
        self.target_agent = target_agent
        # Agent name can be an attribute or a class name
        agent_name = getattr(target_agent, "name", target_agent.__class__.__name__)
        self.name = name or f"transfer_to_{agent_name}"
        self.description = description or (
            f"Hand off the conversation to agent {agent_name}. Use this tool when the user's request "
            f"falls into {agent_name}'s area of expertise."
        )

    def __call__(self) -> Any:
        """
        Calling the tool returns the target agent.

        Returns:
            Target agent
        """
        logger.info(f"Handoff called to {self.target_agent.name}")
        return self.target_agent

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the tool schema for the OpenAI API.

        Returns:
            Tool schema
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }


def function_to_schema(func: Callable) -> Dict[str, Any]:
    """
    Convert a Python function into an OpenAI tool schema.

    Args:
        func: Function to convert

    Returns:
        Tool schema
    """
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }

    try:
        signature = inspect.signature(func)
    except ValueError as e:
        logger.error(f"Failed to get signature for function {func.__name__}: {str(e)}")
        raise

    parameters = {}
    for param in signature.parameters.values():
        try:
            param_type = type_map.get(param.annotation, "string")
        except KeyError as e:
            logger.error(
                f"Unknown type annotation {param.annotation} for parameter {param.name}: {str(e)}"
            )
            raise
        parameters[param.name] = {"type": param_type}

    required = [
        param.name
        for param in signature.parameters.values()
        if param.default == inspect._empty
    ]

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": (func.__doc__ or "").strip(),
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required,
            },
        },
    }


def handoff(
    agent: Any, name: Optional[str] = None, description: Optional[str] = None
) -> HandoffTool:
    """
    Create a handoff tool to transfer control to a target agent.

    Args:
        agent: Target agent
        name: Tool name (defaults to "transfer_to_{agent_name}")
        description: Tool description

    Returns:
        Handoff tool
    """
    return HandoffTool(agent, name, description)
