"""Bounded asynchronous adapter for Windows' synchronous inherited Chrome pipe.

A daemon thread (not asyncio's executor) prevents a stalled stdin from blocking
loop work or asyncio.run shutdown. Backpressure limits queued input to 8 KiB;
serve() still owns the 64 KiB frame and partial-frame timeout contracts.
"""
import asyncio
import concurrent.futures
import threading


class PipeReader:
    def __init__(self, source):
        self.loop = asyncio.get_running_loop()
        self.source = source
        self.queue = asyncio.Queue(maxsize=2)
        self.buffer = bytearray()
        self.eof = False
        self.stopped = threading.Event()
        self.pending = None
        self.thread = threading.Thread(target=self._pump, name='PearPlay-stdin', daemon=True)
        self.thread.start()

    def _pump(self):
        try:
            while not self.stopped.is_set():
                # read1 returns available pipe bytes; BufferedReader.read may wait
                # for all 4096 bytes even when a complete Chrome frame is ready.
                chunk = self.source.read1(4096) if hasattr(self.source, 'read1') else self.source.read(4096)
                if self.stopped.is_set():
                    return
                self.pending = self._enqueue(chunk)
                while not self.stopped.is_set():
                    try:
                        self.pending.result(timeout=.1)
                        break
                    except concurrent.futures.TimeoutError:
                        continue
                if not chunk:
                    return
        except (OSError, ValueError):
            if not self.stopped.is_set():
                self.pending = self._enqueue(None)
        except (RuntimeError, concurrent.futures.CancelledError):
            pass

    def _enqueue(self, chunk):
        coroutine = self.queue.put(chunk)
        try:
            return asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        except RuntimeError:
            coroutine.close()
            raise

    async def read(self, size):
        if not 0 < size <= 65540:
            raise ValueError('bounded_read_required')
        while not self.buffer and not self.eof:
            chunk = await self.queue.get()
            if chunk is None:
                raise OSError('input_failed')
            if not chunk:
                self.eof = True
            else:
                self.buffer.extend(chunk)
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        return result

    async def readexactly(self, size):
        if not 0 <= size <= 65536:
            raise ValueError('bounded_read_required')
        result = bytearray()
        while len(result) < size:
            chunk = await self.read(size - len(result))
            if not chunk:
                raise asyncio.IncompleteReadError(bytes(result), size)
            result.extend(chunk)
        return bytes(result)

    def close(self):
        self.stopped.set()
        if self.pending is not None:
            self.pending.cancel()
        # Do not close an actively read BufferedReader: its lock can block.
        # A blocked daemon is discarded on process exit; no executor join.


def binary_stdio():
    import msvcrt
    import os
    import sys
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)


async def serve_stdio(output, serve, factory=None):
    import sys
    reader = PipeReader(sys.stdin.buffer)
    try:
        await serve(reader, output, factory=factory)
    finally:
        reader.close()
