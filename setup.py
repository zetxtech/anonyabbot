from setuptools import find_packages, setup

with open("README.md") as readme_file:
    readme = readme_file.read()

with open("requirements.txt") as requirements_file:
    requirements = requirements_file.read().splitlines()

setup(
    author="anonyabbot",
    author_email="jackzzs@outlook.com",
    python_requires=">=3.10,<3.11",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3.10",
    ],
    description="Bot server for @anonyabbot in telegram.",
    install_requires=requirements,
    long_description=readme,
    long_description_content_type="text/markdown",
    include_package_data=True,
    keywords=["telegram", "bot", "server"],
    name="anonyabbot",
    packages=find_packages(include=["anonyabbot", "anonyabbot.*"]),
    url="https://github.com/anonyabbot/anonyabbot",
    version="1.0.0",
    zip_safe=False,
)
