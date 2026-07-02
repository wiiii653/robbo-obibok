"""Queue and subsong playback state — extracted from domain_state."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PlaybackQueueState:
    """Queue and subsong playback state."""

    queue: list[str] = field(default_factory=list)
    index: int = -1
    loop: bool = True
    subsong_current: int = -1
    subsong_total: int = 0
    subsong_path: str | None = None
    subsong_wavs: list[str] = field(default_factory=list)

    def set_queue_state(
        self, queue: list[str], index: int, *, loop: bool | None = None
    ) -> None:
        self.queue = list(queue)
        self.index = index
        if loop is not None:
            self.loop = loop

    def set_loop_enabled(self, enabled: bool) -> None:
        self.loop = enabled

    def advance_queue_index(self) -> int:
        self.index += 1
        return self.index

    def clear_queue_state(self) -> None:
        self.queue = []
        self.index = -1

    def queue_length(self) -> int:
        return len(self.queue)

    def current_queue_url(self) -> str | None:
        if 0 <= self.index < len(self.queue):
            return self.queue[self.index]
        return None

    def has_current_queue_item(self) -> bool:
        return self.current_queue_url() is not None

    def current_queue_position(self) -> tuple[int, int] | None:
        if not self.has_current_queue_item():
            return None
        return self.index + 1, self.queue_length()

    def remaining_queue_count(self) -> int:
        position = self.current_queue_position()
        if position is None:
            return self.queue_length()
        return position[1] - position[0]

    def contains_queue_index(self, index: int) -> bool:
        return 0 <= index < self.queue_length()

    def next_queue_url(self) -> str | None:
        next_index = self.index + 1
        if self.contains_queue_index(next_index):
            return self.queue[next_index]
        if self.loop and self.queue:
            return self.queue[0]
        return None

    def upcoming_queue(self, limit: int = 10) -> list[str]:
        if not self.has_current_queue_item():
            return []
        return self.queue[self.index + 1 : self.index + 1 + limit]

    def played_queue(self, limit: int = 10) -> list[str]:
        if self.index <= 0:
            return []
        start = max(0, self.index - limit)
        return self.queue[start:self.index]

    def set_subsong_state(
        self, *, path: str, total: int, current: int = 0
    ) -> None:
        self.subsong_path = path
        self.subsong_total = total
        self.subsong_current = current

    def set_current_subsong(self, subsong: int) -> None:
        self.subsong_current = subsong

    def ensure_subsong_slot(self, subsong: int) -> None:
        while len(self.subsong_wavs) <= subsong:
            self.subsong_wavs.append("")

    def set_subsong_wav(self, subsong: int, wav_path: str) -> None:
        self.ensure_subsong_slot(subsong)
        self.subsong_wavs[subsong] = wav_path

    def reset_subsong_state(self) -> None:
        self.subsong_wavs.clear()
        self.subsong_total = 0
        self.subsong_current = -1
        self.subsong_path = None
