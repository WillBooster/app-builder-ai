from pydantic import BaseModel, Field


class File(BaseModel):
    name: str
    class_diagram: str = Field(
        description="PlantUML code for the class diagram with methods and attributes. "
        "It should only contain classes in this file. "
        "If there are no classes in this file, leave this empty."
    )


class PublicInterfaceDocument(BaseModel):
    entry_point_file_name: str = Field(
        description="This should handle user input and output"
    )
    files: list[File] = Field(description="All files required for the system")
    sequence_diagram: str = Field(
        description="PlantUML code for the sequence diagram of the whole system"
    )


class SourceCodeFix(BaseModel):
    description: str
    file_name: str
    code: str = Field(
        description="This will be parsed by json parser and then directly written "
        "to a file, so write string representation of entire source code of "
        "the fixed file without markdown code block syntax. "
        "Always use tabs for indentation."
    )


class SourceCodeFixOption(BaseModel):
    file_name: str = Field(description="Which file to fix")
    observation: str = Field(description="What is the problem?")
    how_to_fix: str


class SourceCodeFixOptionSet(BaseModel):
    options: list[SourceCodeFixOption]


class TestScenario(BaseModel):
    name: str
    scenario: str


class TestScenarioSet(BaseModel):
    scenarios: list[TestScenario]
