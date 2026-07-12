#!/usr/bin/python3

"""
Shared async scaffolding for the URL and DOI checkers.
~~~~~~~~~~~~~~~~~~~~~
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026 Rüdiger Voigt and contributors
Released under the Apache License 2.0
"""

import asyncio

import aiohttp
from tqdm.asyncio import tqdm  # type: ignore


class AsyncCheckerBase:
    """Common queue/worker/session machinery for network checkers.

    Subclasses implement `_process_item` to check a single queue item and
    may override `_fill_queue` to filter or transform items before they
    are enqueued.
    """

    def __init__(self, quiet: bool = False) -> None:
        """Initialize the shared checker state.

        Args:
            quiet: If True, suppress progress messages.
        """
        self.quiet = quiet
        self.session: aiohttp.ClientSession | None = None
        self.pbar: tqdm | None = None

    async def _create_session(self) -> None:
        # Create a client session bound to the current running loop
        self.session = aiohttp.ClientSession()

    async def _close_session(self) -> None:
        """Close the session object once it is no longer needed."""
        if self.session:
            await self.session.close()

    async def _process_item(self, item: str) -> None:
        """Check a single item from the queue. Must not raise.

        Args:
            item: The queue item (URL or DOI) to check.
        """
        raise NotImplementedError

    def _fill_queue(self,
                    items: list,
                    queue: asyncio.Queue) -> None:
        """Put the items to check into the queue.

        Args:
            items: List of items to check.
            queue: Async queue the workers consume from.
        """
        for entry in items:
            queue.put_nowait(entry)

    async def _worker(self,
                      name: str,
                      queue: asyncio.Queue) -> None:
        """Worker coroutine to process checks from the queue.

        Args:
            name: Worker identifier for debugging purposes.
            queue: Async queue containing items to check.
        """
        # DO NOT REMOVE 'while True'. Without that the queue is stopped
        # after the first iteration.
        while True:
            item = await queue.get()
            try:
                await self._process_item(item)
            finally:
                if self.pbar is not None:
                    self.pbar.update(1)
                queue.task_done()

    async def _distribute_work(self,
                               items: list,
                               num_workers: int) -> None:
        """Start a queue and spawn workers to work in parallel.

        Args:
            items: List of items to check.
            num_workers: Number of worker coroutines to spawn.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._fill_queue(items, queue)

        await self._create_session()
        tasks = []
        try:
            for i in range(int(num_workers)):
                task = asyncio.create_task(self._worker(f'worker-{i}', queue))
                tasks.append(task)
            await queue.join()
        finally:
            for task in tasks:
                task.cancel()
            await self._close_session()
            await asyncio.gather(*tasks, return_exceptions=True)
