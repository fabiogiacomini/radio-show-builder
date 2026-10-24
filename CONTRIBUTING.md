# Contributing

Discuss substantial changes in an issue. Small fixes can go directly into a pull request.

1. Fork and clone the repository.
2. Install Python and FFmpeg, create a virtual environment and install with python -m pip install -e .
3. Run python -m unittest discover -s tests -v.
4. Keep documentation, comments and interface text in English.
5. Describe the change and its validation in your pull request.

Use generated signals or appropriately licensed examples for tests. Never commit credentials, private voice IDs, personal recordings, production scripts or exports.

Provider adapters need mock request/response tests. Audio changes need meaningful timing or sound integration checks.

Contributions are submitted under the project's MIT license.
