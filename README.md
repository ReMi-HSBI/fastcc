[![ruff](https://img.shields.io/badge/ruff-⚡-261230.svg?style=flat-square)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/mypy-📝-2a6db2.svg?style=flat-square)](https://github.com/python/mypy)
[![gitmoji](https://img.shields.io/badge/gitmoji-😜%20😍-FFDD67.svg?style=flat-square)](https://github.com/carloscuesta/gitmoji)

<p align="center">
    <img
        src="https://github.com/ReMi-HSBI/fastcc/blob/main/docs/src/static/images/logos/fastcc.svg?raw=true"
        alt="FastCC Logo"
        width="33%"
    />
</p>

# FastCC

FastCC is a lightweight, efficient and developer-friendly framework for
[MQTT](https://mqtt.org) communication written in
[Python](https://www.python.org). It is built on top of the
[aiomqtt](https://github.com/empicano/aiomqtt) library and extends it
with the following functionalities:

| Feature                          | Status          |
| -------------------------------- | --------------- |
| Request/Response                 | ✅ Done         |
| Streaming                        | ✅ Done         |
| Routing                          | ✅ Done         |
| Custom encoding/decoding         | ✅ Done         |

## Miscellaneous

### API Documentation

To build the API Documentation, use the following command in the
root-directory of the project.

`sphinx-build -M html docs/src docs/build`

> Ensure that your virtual environment is activated and that the
> development extras are installed, as they include the docstring
> tooling required to build the API documentation.
