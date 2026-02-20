import os


def pytest_runtest_logreport(report):
    if os.getenv("STUDY_AGENT_PYTEST_PROGRESS") != "1":
        return
    if report.when != "call":
        return
    status = "PASS" if report.passed else "FAIL" if report.failed else "SKIP"
    print(f"{status}: {report.nodeid}")
