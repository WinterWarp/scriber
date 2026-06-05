class InjectionError(Exception):
    """Raised when text could not be delivered to the target."""


class Injector:
    name = "base"

    def available(self) -> tuple[bool, str]:
        return True, ""

    def send(self, text: str) -> None:
        raise NotImplementedError
