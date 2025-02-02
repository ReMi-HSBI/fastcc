"""Module containing the `Router` class."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from fastcc.utilities.type_aliases import Routable

from fastcc.utilities.mqtt import QoS
from fastcc.utilities.validation import validate_route


class Router:
    """Router for communication endpoints."""

    def __init__(self) -> None:
        self._routes: dict[str, dict[QoS, list[Routable]]] = {}

    @property
    def routes(self) -> dict[str, dict[QoS, list[Routable]]]:
        """Return all registered routes.

        Returns
        -------
        dict[str, dict[QoS, list[Routable]]]
            All registered routes.
        """
        return self._routes

    def route(
        self,
        topic: str,
        *,
        qos: QoS = QoS.AT_MOST_ONCE,
    ) -> Callable[[Routable], Routable]:
        """Register a (MQTT-) route.

        Parameters
        ----------
        topic
            MQTT topic to subscribe and assign the function to.
        qos
            Quality of Service level for the subscription.

        Returns
        -------
        Callable[[Routable], Routable]
            Decorated callable.
        """

        def decorator(routable: Routable) -> Routable:
            validate_route(routable)

            if topic not in self._routes:
                self._routes[topic] = {}

            if qos not in self._routes[topic]:
                self._routes[topic][qos] = []

            self._routes[topic][qos].append(routable)

            return routable

        return decorator

    def add_router(self, router: Router) -> None:
        """Add another router to this router.

        Parameters
        ----------
        router
            Router to add.
        """
        self._routes.update(router.routes)
