# FastCC

FastCC is a lightweight, efficient and developer-friendly framework for
[MQTT](https://mqtt.org) communication written in
[Python](https://www.python.org). It is built on top of the
[aiomqtt](https://github.com/empicano/aiomqtt) library and extends it
with the following functionalities:

| Feature                          | Status          |
| -------------------------------- | --------------- |
| Request/Response                 | 📋Planned       |
| Streaming                        | 📋Planned       |
| Custom payload encoding/decoding | 📋Planned       |
| Routing                          | 📋Planned       |

## Miscellaneous

### API Documentation

To build the API Documentation, use the following command in the
root-directory of the project.

`sphinx-build -M html docs/src docs/build`

> Ensure that your virtual environment is activated and that the
> development extras are installed, as they include the docstring
> tooling required to build the API documentation.
