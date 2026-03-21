"""LLM-as-judge for evaluating AI outputs.

Uses OpenAI structured output to determine if an AI response is correct.
Supports three query types: recipe_parse, chat_answer, chat_tool_use.
"""

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from src.config import get_config


@dataclass
class JudgeResponse:
    """Structured response from the LLM judge."""

    reasoning: str
    is_correct: bool


JUDGE_PROMPTS = {
    "recipe_parse": """You are an expert evaluator for recipe parsing systems.
Given a parsed recipe output and the expected recipe fields, determine if the parser
correctly extracted the recipe information.

Evaluate the following aspects:
- Recipe name: Is it correct or a reasonable variant?
- Prep time: Is it within 5 minutes of expected?
- Cook time: Is it within 5 minutes of expected?
- Servings: Is it correct or within 1 of expected?
- Ingredient count: Is the count within 2 of expected?
- Step count: Is the count within 2 of expected?

If the majority of fields are correct (4 out of 6 or better), judge it as correct.

PARSED OUTPUT:
{actual}

EXPECTED:
{expected}

Respond with your reasoning and whether the parse is correct.""",

    "chat_answer": """You are an expert evaluator for AI cooking assistant responses.
Given a user question, the recipe context, the AI's answer, and the expected answer,
determine if the AI's response is semantically correct.

The AI answer does NOT need to match word-for-word. It should:
- Contain the key information from the expected answer
- Be factually correct given the recipe context
- Be helpful and relevant to the question

USER QUESTION:
{query}

RECIPE CONTEXT:
{recipe_context}

AI ANSWER:
{actual}

EXPECTED ANSWER:
{expected}

Respond with your reasoning and whether the AI answer is correct.""",

    "chat_tool_use": """You are an expert evaluator for AI tool usage in a cooking assistant.
Given a user query and the AI's response (including any tool calls made),
determine if the AI used the correct tool(s).

The available tools are:
- search_recipes: Search for recipes using natural language
- add_note_to_recipe: Add a note/tip to a recipe
- suggest_recipe: Generate a new recipe suggestion

USER QUERY:
{query}

AI RESPONSE AND TOOL CALLS:
{actual}

EXPECTED BEHAVIOR:
{expected}

Respond with your reasoning and whether the AI used the correct tool(s).""",
}


def judge(
    query_type: str,
    actual: Any,
    expected: Any,
    query: str | None = None,
    recipe_context: str | None = None,
    model: str | None = None,
) -> JudgeResponse:
    """Use an LLM to judge if the actual output matches expectations.

    Args:
        query_type: One of "recipe_parse", "chat_answer", "chat_tool_use".
        actual: The actual output from the system under test.
        expected: The expected output or behavior.
        query: The user query (for chat evaluations).
        recipe_context: Recipe context (for chat evaluations).
        model: Override the judge LLM model.

    Returns:
        JudgeResponse with reasoning and correctness determination.
    """
    config = get_config()
    client = OpenAI(api_key=config.openai_api_key)

    prompt_template = JUDGE_PROMPTS.get(query_type)
    if not prompt_template:
        raise ValueError(f"Unknown query type: {query_type}. Must be one of: {list(JUDGE_PROMPTS.keys())}")

    # Format prompt with available fields
    actual_str = json.dumps(actual, indent=2, default=str) if isinstance(actual, dict | list) else str(actual)
    expected_str = json.dumps(expected, indent=2, default=str) if isinstance(expected, dict | list) else str(expected)

    format_kwargs = {
        "actual": actual_str,
        "expected": expected_str,
        "query": query or "",
        "recipe_context": recipe_context or "",
    }
    prompt = prompt_template.format(**format_kwargs)

    judge_model = model or config.judge_model

    response = client.chat.completions.create(
        model=judge_model,
        messages=[
            {
                "role": "system",
                "content": "You are an evaluation judge. Analyze the output and provide your reasoning, then determine if the output is correct.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "judge_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "reasoning": {
                            "type": "string",
                            "description": "Step-by-step reasoning for the judgment",
                        },
                        "is_correct": {
                            "type": "boolean",
                            "description": "Whether the output is correct",
                        },
                    },
                    "required": ["reasoning", "is_correct"],
                    "additionalProperties": False,
                },
            },
        },
        temperature=0.0,
    )

    content = response.choices[0].message.content or "{}"
    parsed = json.loads(content)

    return JudgeResponse(
        reasoning=parsed.get("reasoning", ""),
        is_correct=parsed.get("is_correct", False),
    )
