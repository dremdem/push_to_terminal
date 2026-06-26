import pytest


@pytest.fixture(autouse=True, scope="session")
def _preload_torch():
    # Import torch once at session start so its C extension is initialised.
    # Without this, tests that use mocker.patch.dict({"torch": None}) would
    # remove torch from sys.modules on teardown (because it wasn't present when
    # the patch was applied), causing a subsequent `import torch` to re-run
    # torch/__init__.py against an already-initialised C extension and raise
    # "function '_has_torch_function' already has a docstring".
    try:
        import torch  # noqa: F401
    except ImportError:
        pass
