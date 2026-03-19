from setuptools import find_namespace_packages, setup

setup(
    name="metaflow-sample-ext",
    version="1.0.0",
    description="Sample extension for testing the extension testing framework",
    author="Metaflow Test",
    license="Apache Software License 2.0",
    packages=find_namespace_packages(include=["metaflow_extensions.*"]),
    include_package_data=True,
    zip_safe=False,
)
