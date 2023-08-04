import difflib
import json
import logging
import os
import signal
import subprocess
import time

from langchain.chat_models import ChatOpenAI
from langchain.prompts import load_prompt
from parsers.code_output_parser import CodeOutputParser
from parsers.strict_pydantic_output_parser import StrictPydanticOutputParser
from schema import PublicInterfaceDocument, TestScenarioSet
from util import (
    ACCEPTANCE_TEST_SCENARIOS_FILE_NAME,
    SCRIPT_DIR,
    execute_model,
    get_acceptance_test_file_name,
    get_doc_file_path,
    get_prompt_file_path,
    get_src_file_path,
    get_unit_test_file_name,
)


def generate_unit_tests(
    model: ChatOpenAI,
    specifications_text: str,
    public_interface_document: PublicInterfaceDocument,
) -> None:
    tested_files = [
        file
        for file in public_interface_document.files
        if file.name.endswith(".py")
        and file.name != public_interface_document.entry_point_file_name
    ]
    for file in tested_files:
        test_file_name = get_unit_test_file_name(file.name)
        if os.path.exists(get_src_file_path(test_file_name)):
            logging.info(f"Reusing {test_file_name}.")
            continue

        logging.info(f"Generating {test_file_name}.")

        output_parser = CodeOutputParser()
        prompt = load_prompt(get_prompt_file_path("gen_unit_test.yaml")).format(
            specifications=specifications_text,
            public_interface_document=public_interface_document.json(),
            file=file.name,
            format_instructions=output_parser.get_format_instructions(),
        )
        output = execute_model(model, prompt)
        test_code = output_parser.parse(output)

        with open(get_src_file_path(test_file_name), "w") as f:
            f.write(test_code)


def generate_acceptance_test_scenarios(
    model: ChatOpenAI,
    specifications_text: str,
) -> TestScenarioSet:
    test_scenarios_file_path = get_doc_file_path(ACCEPTANCE_TEST_SCENARIOS_FILE_NAME)
    if os.path.exists(test_scenarios_file_path):
        logging.info(f"Reusing {test_scenarios_file_path}.")
        return TestScenarioSet.parse_file(test_scenarios_file_path)

    logging.info("Generating acceptance test scenarios.")

    output_parser = StrictPydanticOutputParser(pydantic_object=TestScenarioSet)
    prompt = load_prompt(
        get_prompt_file_path("gen_acceptance_test_scenarios.yaml")
    ).format(
        specifications=specifications_text,
        format_instructions=output_parser.get_format_instructions(),
    )
    output = execute_model(model, prompt)
    test_scenario_collection = output_parser.parse(output)

    with open(test_scenarios_file_path, "w") as f:
        f.write(test_scenario_collection.json())

    return test_scenario_collection


def generate_acceptance_tests(
    model: ChatOpenAI,
    specifications_text: str,
    test_scenario_collection: TestScenarioSet,
    public_interface_document: PublicInterfaceDocument,
) -> None:
    logging.info("Generating acceptance tests.")

    entry_point_file = [
        file
        for file in public_interface_document.files
        if file.name == public_interface_document.entry_point_file_name
    ][0]
    with open(get_src_file_path(entry_point_file.name)) as f:
        entry_point_source_code = f.read()

    for test_index, test_scenario in enumerate(test_scenario_collection.scenarios):
        test_file_name = get_acceptance_test_file_name(
            test_index, entry_point_file.name
        )
        if os.path.exists(get_src_file_path(test_file_name)):
            logging.info(f"Reusing {test_file_name}.")
            return

        logging.info(f"Generating {test_file_name}.")

        output_parser = CodeOutputParser()
        prompt = load_prompt(get_prompt_file_path("gen_acceptance_test.yaml")).format(
            specifications=specifications_text,
            test_scenario=test_scenario.json(),
            public_interface_document=public_interface_document.json(),
            entry_point_source_code=entry_point_source_code,
            format_instructions=output_parser.get_format_instructions(),
        )
        output = execute_model(model, prompt)
        test_code = output_parser.parse(output)

        with open(get_src_file_path(test_file_name), "w") as f:
            f.write(test_code)


def execute_all_tests(file_pattern: str) -> dict[str, str]:
    logging.info(f"Executing all tests ({file_pattern}).")

    test_script = os.path.join(SCRIPT_DIR, "test.py")
    try:
        test_proc = subprocess.Popen(
            ["python", test_script, file_pattern], text=True, stdout=subprocess.PIPE
        )
        test_proc.wait(timeout=10)
        test_failures = json.loads(test_proc.stdout.read())
    except subprocess.TimeoutExpired:
        test_proc.send_signal(signal.SIGINT)
        time.sleep(1)
        test_failures = json.loads(test_proc.stdout.read())
        test_proc.kill()
        test_proc.wait()

    return test_failures


def modify_unit_test(
    model: ChatOpenAI,
    specifications_text: str,
    change_request: str,
    source_file_name: str,
    public_interface_document: PublicInterfaceDocument,
) -> bool:
    test_file_name = get_unit_test_file_name(source_file_name)
    logging.info(f"Modifying {test_file_name}.")

    with open(get_src_file_path(source_file_name)) as source_file:
        source_code = source_file.read()
    with open(get_src_file_path(test_file_name)) as test_file:
        test_code = test_file.read()

    output_parser = CodeOutputParser()
    prompt = load_prompt(get_prompt_file_path("modify_unit_test.yaml")).format(
        specifications=specifications_text,
        change_request=change_request,
        public_interface_document=public_interface_document.json(),
        source_file=source_file_name,
        test_file=test_file_name,
        source_code=source_code,
        test_code=test_code,
        format_instructions=output_parser.get_format_instructions(),
    )
    output = execute_model(model, prompt)
    fixed_test_code = output_parser.parse(output)

    if fixed_test_code.strip() == "":
        logging.info(f"No changes to {test_file_name}.")
        return False
    else:
        with open(get_src_file_path(test_file_name), "w") as f:
            f.write(fixed_test_code)
        logging.info(f"Modified {test_file_name}.")

        diff = difflib.unified_diff(
            test_code.splitlines(), fixed_test_code.splitlines(), lineterm=""
        )
        print("\n".join(diff))

        return True
