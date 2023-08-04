import argparse
import logging
import shutil
from pathlib import Path

from builders.fix import fix_test_errors
from builders.interface import (
    generate_public_interface_document,
    update_public_interface_document,
)
from builders.source_code import (
    create_source_code_vector_db,
    generate_source_code,
    modify_source_code,
)
from builders.test import (
    execute_all_tests,
    generate_acceptance_test_scenarios,
    generate_acceptance_tests,
    generate_unit_tests,
    modify_unit_test,
)
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from schema import PublicInterfaceDocument
from util import (
    ACCEPTANCE_TEST_PREFIX,
    DOC_DIR,
    PUBLIC_INTERFACE_DOCUMENT_NAME,
    RAW_ALL_TEST_ID,
    SRC_DIR,
    TEST_LOG_FILE_NAME,
    UNIT_TEST_PREFIX,
    get_doc_file_path,
)


def main():
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S",
    )

    arg_parser = argparse.ArgumentParser(description="Build an app from user's prompt.")
    arg_parser.add_argument(
        "--spec",
        type=str,
        required=True,
        help="Path to a file containing the specifications of the app to build.",
    )
    arg_parser.add_argument(
        "--reuse",
        action="store_true",
        help="Reuse existing files.",
    )
    arg_parser.add_argument(
        "--change-request",
        type=str,
        default=None,
        help="Path to a file containing the change request.",
    )
    args = arg_parser.parse_args()

    if args.change_request:
        modify_app(args.spec, args.change_request)
    else:
        prepare_workspace(args.reuse)
        build_app(args.spec)


def prepare_workspace(reuse: bool) -> None:
    directories = [SRC_DIR, DOC_DIR]
    for directory in directories:
        if not reuse and Path(directory).exists():
            shutil.rmtree(directory)
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
    with open(get_doc_file_path(TEST_LOG_FILE_NAME), "w") as f:
        f.write("")


def build_app(spec_file_path: str) -> None:
    gpt4_low_t = ChatOpenAI(model_name="gpt-4", temperature=0.2)
    gpt4_high_t = ChatOpenAI(model_name="gpt-4", temperature=0.7)

    specifications_text = open(spec_file_path).read()

    public_interface_document = generate_public_interface_document(
        gpt4_high_t, specifications_text
    )

    generate_unit_tests(gpt4_high_t, specifications_text, public_interface_document)

    generate_source_code(
        gpt4_high_t,
        specifications_text,
        public_interface_document,
    )
    public_interface_document = update_public_interface_document(
        gpt4_low_t,
        public_interface_document,
    )

    test_scenario_collection = generate_acceptance_test_scenarios(
        gpt4_high_t,
        specifications_text,
    )
    generate_acceptance_tests(
        gpt4_high_t,
        specifications_text,
        test_scenario_collection,
        public_interface_document,
    )

    while True:
        source_code_vector_db = create_source_code_vector_db()

        for test_pattern in [
            f"{UNIT_TEST_PREFIX}*.py",
            f"{ACCEPTANCE_TEST_PREFIX}*.py",
        ]:
            test_failures = execute_all_tests(test_pattern)

            if test_failures.keys() != {RAW_ALL_TEST_ID}:
                fixed_file_names = fix_test_errors(
                    gpt4_low_t,
                    specifications_text,
                    public_interface_document,
                    source_code_vector_db,
                    test_failures,
                )
                public_interface_document = update_public_interface_document(
                    gpt4_low_t,
                    public_interface_document,
                    file_names=fixed_file_names,
                    force=True,
                )
                break
        else:
            break

    logging.info("Done.")


def modify_app(spec_file_path: str, change_request_file_path: str) -> None:
    gpt4_low_t = ChatOpenAI(model_name="gpt-4", temperature=0.2)
    gpt4_high_t = ChatOpenAI(model_name="gpt-4", temperature=0.7)

    specifications_text = open(spec_file_path).read()
    change_request_text = open(change_request_file_path).read()
    public_interface_document = PublicInterfaceDocument.parse_file(
        get_doc_file_path(PUBLIC_INTERFACE_DOCUMENT_NAME)
    )

    for file in public_interface_document.files:
        modified = modify_source_code(
            gpt4_high_t,
            specifications_text,
            change_request_text,
            file.name,
            public_interface_document,
        )

        if modified:
            public_interface_document = update_public_interface_document(
                gpt4_low_t,
                public_interface_document,
                file_names=[file.name],
                force=True,
            )

    files_with_unit_tests = [
        file
        for file in public_interface_document.files
        if file.name != public_interface_document.entry_point_file_name
    ]
    for file in files_with_unit_tests:
        modify_unit_test(
            gpt4_high_t,
            specifications_text,
            change_request_text,
            file.name,
            public_interface_document,
        )

    logging.info("Done.")


if __name__ == "__main__":
    main()
