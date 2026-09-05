from typing import Optional

from rich.table import Column
from rich.text import Text
from rich.progress import (
    Task,
    BarColumn,
    Progress,
    TextColumn,
    ProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


class FileCountColumn(ProgressColumn):
    def __init__(self, table_column: Optional[Column] = None) -> None:
        super().__init__(table_column=table_column)

    def render(self, task: "Task") -> Text:
        completed = int(task.completed)
        total_str = f"{int(task.total):,}" if task.total is not None else "?"
        return Text(f"{completed:,}/{total_str} files", style="progress.download")


files_progress = Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    FileCountColumn(),
    TimeRemainingColumn(),
    TimeElapsedColumn(),
)

class SharedProgressContext:
    def __init__(self, progress_instance):
        self.progress = progress_instance
        self.active_tasks = 0

    def __enter__(self):
        self.active_tasks += 1
        if self.active_tasks == 1:
            self.progress.start()
        return self.progress

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.active_tasks -= 1
        if self.active_tasks == 0:
            self.progress.stop()

shared_progress = SharedProgressContext(files_progress)
