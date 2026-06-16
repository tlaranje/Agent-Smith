import json
from pydantic import BaseModel, Field
from typing import List


class MBPPTaskInput(BaseModel):
    """Input for MBPP task evaluation."""
    task_id: int = 0
    task_definition: str = ""
    function_definition: str = ""
    test_imports: List[str] = Field(default_factory=list)
    test_list: List[str] = Field(default_factory=list)

    @classmethod
    def from_file(cls, path: str) -> "MBPPTaskInput":
        with open(path, "r") as fd:
            return cls(**json.load(fd))
