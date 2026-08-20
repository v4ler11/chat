import re

from typing import Type, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


def get_schema(model_class: type[BaseModel]) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": model_class.__name__,
            "schema": model_class.model_json_schema(),
            "strict": True
        }
    }


def parse_model_output_json(output: str, parse_into: Type[T]) -> T:
    if "```" in output:
        output = re.sub(r"```(?:\w+)?", "", output).replace("```", "")

    start = output.find("{")
    end = output.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found in output.")

    json_str = output[start: end + 1]

    try:
        return parse_into.model_validate_json(json_str)
    except Exception as e:
        raise ValueError(f"Parse failed on: {json_str[:50]}... Error: {e}")
