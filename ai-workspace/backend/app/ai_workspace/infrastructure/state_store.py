from typing import Protocol


class StateStore(Protocol):
    def set(self, namespace: str, key: str, payload: dict | list) -> None:
        ...

    def get(self, namespace: str, key: str) -> dict | list | None:
        ...

    def list(self, namespace: str) -> list[tuple[str, dict | list]]:
        ...

    def delete(self, namespace: str, key: str) -> None:
        ...
