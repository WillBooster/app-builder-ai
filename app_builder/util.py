import os
import sys

from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage

SCRIPT_DIR = os.path.dirname(os.path.abspath(str(sys.modules["__main__"].__file__)))
WORKSPACE_DIR = os.path.join(SCRIPT_DIR, "workspace")
SRC_DIR = os.path.join(WORKSPACE_DIR, "src")
DOC_DIR = os.path.join(WORKSPACE_DIR, "docs")
PROMPT_DIR = os.path.join(SCRIPT_DIR, "prompts")
PUBLIC_INTERFACE_DOCUMENT_NAME = "public_interface_document.json"
ACCEPTANCE_TEST_SCENARIOS_FILE_NAME = "acceptance_test_scenarios.json"
TEST_LOG_FILE_NAME = "test_results.log"
UNIT_TEST_PREFIX = "__unit_test_"
ACCEPTANCE_TEST_PREFIX = "__acceptance_test_"
RAW_ALL_TEST_ID = "__raw_all__"


def get_src_file_path(file_name: str) -> str:
    return os.path.join(SRC_DIR, file_name)


def get_doc_file_path(file_name: str) -> str:
    return os.path.join(DOC_DIR, file_name)


def get_prompt_file_path(file_name: str) -> str:
    return os.path.join(PROMPT_DIR, file_name)


def execute_model(model: ChatOpenAI, prompt: str) -> str:
    return model([HumanMessage(content=prompt)]).content


def get_unit_test_file_name(source_file_name: str) -> str:
    return f"{UNIT_TEST_PREFIX}{source_file_name}"


def get_acceptance_test_file_name(id: str, source_file_name: str) -> str:
    return f"{ACCEPTANCE_TEST_PREFIX}{id}_{source_file_name}"
