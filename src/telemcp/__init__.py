from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("telemcp")
except PackageNotFoundError:
    __version__ = "unknown"
