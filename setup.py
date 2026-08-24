import re
from pathlib import Path

from setuptools import setup


def get_version():
    text = Path("cleepcli/version.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', text, re.M)
    if not match:
        raise RuntimeError("VERSION not found in cleepcli/version.py")
    return match.group(1)


def get_requirements():
    path = Path("requirements.txt")
    if not path.is_file():
        raise FileNotFoundError(
            "requirements.txt is required to build cleepcli (is it listed in MANIFEST.in?)"
        )
    reqs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        reqs.append(line)
    return reqs


setup(
    name="cleepcli",
    version=get_version(),
    description="Cleep-cli helps developers to build great Cleep applications from command line.",
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="Tanguy Bonneau",
    author_email="tanguy.bonneau@gmail.com",
    maintainer="Tanguy Bonneau",
    maintainer_email="tanguy.bonneau@gmail.com",
    url="https://github.com/CleepDevice/cleep-cli",
    packages=["cleepcli"],
    include_package_data=True,
    install_requires=get_requirements(),
    python_requires=">=3.7",
    scripts=["bin/cleep-cli", "bin/ccli"],
)
