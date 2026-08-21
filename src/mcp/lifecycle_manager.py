from typing import TypeVar, Dict, Callable, List, Generic


T = TypeVar("T")


class LifecycleManager(Generic[T]):
    def __init__(
            self,
            on_change: Callable[[], None],
            id_getter: Callable[[T], str]
    ):
        self._items: Dict[str, T] = {}
        self.on_change = on_change
        self._get_id = id_getter

    def list(self) -> List[T]:
        return list(self._items.values())

    def get(self, identifier: str) -> T | None:
        return self._items.get(identifier)

    def add(self, items: List[T], notify: bool = True) -> None:
        if not items:
            return

        ids_to_add = set()
        for item in items:
            item_id = self._get_id(item)
            if item_id in self._items:
                raise ValueError(f"Transaction failed: Item '{item_id}' already exists.")
            if item_id in ids_to_add:
                raise ValueError(f"Transaction failed: Duplicate item '{item_id}' in input list.")
            ids_to_add.add(item_id)

        for item in items:
            self._items[self._get_id(item)] = item

        if notify:
            self.on_change()

    def update(self, items: List[T], notify: bool = True) -> None:
        if not items:
            return

        ids_to_update = set()
        for item in items:
            item_id = self._get_id(item)
            if item_id not in self._items:
                raise ValueError(f"Transaction failed: Cannot update '{item_id}' (not found).")
            if item_id in ids_to_update:
                raise ValueError(f"Transaction failed: Duplicate item '{item_id}' in input list.")
            ids_to_update.add(item_id)

        for item in items:
            self._items[self._get_id(item)] = item

        if notify:
            self.on_change()

    def upsert(self, items: List[T], notify: bool = True) -> None:
        if not items:
            return

        for item in items:
            self._items[self._get_id(item)] = item

        if notify:
            self.on_change()

    def remove(self, identifiers: List[str], notify: bool = True) -> None:
        if not identifiers:
            return

        modified = False
        for identifier in identifiers:
            if identifier in self._items:
                del self._items[identifier]
                modified = True

        if notify and modified:
            self.on_change()

    def override(self, items: List[T], notify: bool = True) -> None:
        new_registry = {}
        for item in items:
            item_id = self._get_id(item)
            if item_id in new_registry:
                raise ValueError(f"Transaction failed: Duplicate identifier '{item_id}' in input.")
            new_registry[item_id] = item

        self._items = new_registry

        if notify:
            self.on_change()
