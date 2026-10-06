"""Process entry point: connect to ibus-daemon and serve engines."""

from __future__ import annotations

import argparse
import logging
import os
import sys

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

from . import __version__  # noqa: E402
from .engine import LatexEngine, Resources  # noqa: E402

BUS_NAME = "org.freedesktop.IBus.Latex"
ENGINE_PATH = "/org/freedesktop/IBus/Engine/Latex/%d"
DEV_ENGINE = "latex-dev"

log = logging.getLogger("ibus_latex")


class Factory(IBus.Factory):
    __gtype_name__ = "IBusLatexFactory"

    def __init__(self, bus):
        super().__init__(object_path=IBus.PATH_FACTORY,
                         connection=bus.get_connection())
        self._bus = bus
        self._resources = None
        self._count = 0
        self._engines = []

    def do_create_engine(self, engine_name):
        if self._resources is None:
            self._resources = Resources()
        self._count += 1
        engine = LatexEngine(self._resources,
                             engine_name=engine_name,
                             object_path=ENGINE_PATH % self._count,
                             connection=self._bus.get_connection())
        # Keep the Python object alive for as long as IBus uses the engine.
        self._engines.append(engine)
        engine.connect("destroy", self._engines.remove)
        log.debug("created engine %s", engine_name)
        return engine


def dev_component():
    """Component for running from a source tree without installing."""
    component = IBus.Component(
        name=BUS_NAME + ".Dev",
        description="LaTeX symbols (development)",
        version=__version__, license="MIT", author="", homepage="",
        command_line="", textdomain="")
    component.add_engine(IBus.EngineDesc(
        name=DEV_ENGINE, longname="LaTeX symbols (dev)",
        description="LaTeX symbols, running from a source tree",
        language="en", license="MIT", author="", icon="",
        layout="default", rank=0))
    return component


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ibus-engine-latex",
        description="IBus engine for typing Unicode symbols by LaTeX name. "
                    "Without --ibus it registers a '%s' engine with the running "
                    "ibus-daemon for testing; select it with "
                    "'ibus engine %s'." % (DEV_ENGINE, DEV_ENGINE))
    parser.add_argument("--ibus", action="store_true",
                        help="started by ibus-daemon from the installed component")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if os.environ.get("IBUS_LATEX_DEBUG") else logging.WARNING,
        format="ibus-latex: %(levelname)s: %(message)s")

    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        print("ibus-engine-latex: cannot connect to ibus-daemon", file=sys.stderr)
        return 1

    loop = GLib.MainLoop()
    bus.connect("disconnected", lambda _bus: loop.quit())
    factory = Factory(bus)  # noqa: F841 (exported on the bus)
    if args.ibus:
        bus.request_name(BUS_NAME, 0)
    else:
        bus.register_component(dev_component())
        print("registered engine '%s'; switch to it with: ibus engine %s"
              % (DEV_ENGINE, DEV_ENGINE), flush=True)
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    return 0
