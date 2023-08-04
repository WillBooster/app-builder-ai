import argparse
import io
import json
import re
import sys
import traceback
import unittest

from util import (
    ACCEPTANCE_TEST_PREFIX,
    RAW_ALL_TEST_ID,
    SRC_DIR,
    TEST_LOG_FILE_NAME,
    UNIT_TEST_PREFIX,
    get_doc_file_path,
)


def save_test_results(text: str):
    with open(get_doc_file_path(TEST_LOG_FILE_NAME), "a") as f:
        f.write(text)


parser = argparse.ArgumentParser()
parser.add_argument("pattern", type=str)
args = parser.parse_args()

sys.dont_write_bytecode = True

buffer = io.StringIO()
sys.stdout = buffer

loader = unittest.TestLoader()
suite = loader.discover(start_dir=SRC_DIR, pattern=args.pattern)
runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2, failfast=True)

test_failures = {}
try:
    # TODO: consider failfast=False
    result = runner.run(suite)
    for test, error in result.failures + result.errors:
        test_id = test.id()
        test_failures[test_id] = error
    test_failures[RAW_ALL_TEST_ID] = buffer.getvalue()

    save_test_results(buffer.getvalue())
except BaseException:
    test_id_regex = re.compile(
        f"\\(({UNIT_TEST_PREFIX}\\w*(\\.\\w+)+|"
        f"{ACCEPTANCE_TEST_PREFIX}\\w*(\\.\\w+)+)\\)"
    )
    buffer.seek(0)
    stacktrace = traceback.format_exc()
    for line in buffer:
        match = re.search(test_id_regex, line)
        if match:
            test_id = match.group(1)
            test_failures[test_id] = stacktrace
            break
    test_failures[RAW_ALL_TEST_ID] = f"{buffer.getvalue()}\n\n{stacktrace}"

    save_test_results(stacktrace)
finally:
    sys.stdout = sys.__stdout__
    print(json.dumps(test_failures))
