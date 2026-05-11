from __future__ import annotations

import warnings


def quiet_dependency_warnings() -> None:
    warnings.filterwarnings(
        "ignore",
        message=r"You are using a Python version 3\.9.*",
        category=FutureWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r"You are using a non-supported Python version.*",
        category=FutureWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r"urllib3 v2 only supports OpenSSL.*",
    )
