<p align="center">
    <img
        src="https://github.com/ReMi-HSBI/fastcc/blob/main/docs/src/static/images/fastcc_logo.svg?raw=true"
        alt="FastCC Logo"
        width="33%"
    />
</p>

# FastCC

<a href="https://docs.astral.sh/ruff">
    <img
        src="https://img.shields.io/badge/ruff-⚡-261230.svg?style=flat-square"
        alt="Ruff"
    />
</a>
<a href="https://mypy-lang.org">
    <img
        src="https://img.shields.io/badge/mypy-📝-2a6db2.svg?style=flat-square"
        alt="Mypy"
    />
</a>
<a href="https://gitmoji.dev">
    <img
        src="https://img.shields.io/badge/gitmoji-😜%20😍-FFDD67.svg?style=flat-square"
        alt="Gitmoji"
    />
</a>

FastCC is a [Python](https://www.python.org) package that simplifies
[MQTT](https://mqtt.org) communication using decorators. With its
intuitive `@route` system, developers can quickly define MQTT message
handlers without boilerplate code. FastCC natively supports
[Protocol Buffers](https://protobuf.dev) :boom:, automatically handling
serialization to byte format for efficient and structured data exchange.

- Lightweight :zap:
- Efficient :rocket:
- Developer-friendly :technologist:

This project is built on top of [aiomqtt](https://github.com/empicano/aiomqtt)
which itself is built on top of [paho-mqtt](https://eclipse.dev/paho).

# Usage

Please have a look on the `examples` directory.
