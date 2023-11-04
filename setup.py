from setuptools import find_packages, setup

with open("README.md", "r") as f:
    long_description = f.read()

description = """A set of useful utils for dumping, restoring and wiping your
fansly.com account data.
"""

install_requires=[
    "jinja2",
    "requests>=2.26.0",
    "rich",
]

extra_require = {
    "dev": [
        "flake8-black",
        "flake8-bugbear",
        "flake8-isort",
        "flake8-logging",
    ]
}

setup(
    name="fansly_utils",
    version="0.0.1",
    author="Obsessed Cake",
    author_email="obsessed-cake@proton.me",
    description=description,
    long_description=long_description,
    url="https://github.com/obsessedcake",
    packages=find_packages(),
    entry_points = {
        "console_scripts": [
            "fansly-utils=fansly_utils.run:main"
        ]
    },
    license="GPL-3.0",
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Internet",
        "Topic :: Utilities",
    ],
    install_requires=install_requires,
    extra_require=extra_require,
    zip_safe=True
)
