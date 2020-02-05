# Copyright 2018 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

import portage
portage.proxy.lazyimport.lazyimport(globals(),
	'portage.util.futures:asyncio',
)
from portage.util.futures._asyncio.streams import _reader, _writer
from portage.util.futures.compat_coroutine import coroutine, coroutine_return


class _Process(object):
	"""
	Emulate a subset of the asyncio.subprocess.Process interface,
	for python2.
	"""
	def __init__(self, proc, loop):
		"""
		@param proc: process instance
		@type proc: subprocess.Popen
		@param loop: asyncio.AbstractEventLoop (or compatible)
		@type loop: event loop
		"""
		self._proc = proc
		self._loop = loop
		self.terminate = proc.terminate
		self.kill = proc.kill
		self.send_signal = proc.send_signal
		self.pid = proc.pid
		self._waiters = []
		loop._asyncio_child_watcher.\
			add_child_handler(self.pid, self._proc_exit)

	@property
	def returncode(self):
		return self._proc.returncode

	@coroutine
	def communicate(self, input=None):
		"""
		Read data from stdout and stderr, until end-of-file is reached.
		Wait for process to terminate.

		@param input: stdin content to write
		@type input: bytes
		@return: tuple (stdout_data, stderr_data)
		@rtype: asyncio.Future (or compatible)
		"""
		futures = []
		for input_file in (self._proc.stdout, self._proc.stderr):
			if input_file is None:
				future = self._loop.create_future()
				future.set_result(None)
			else:
				future = _reader(input_file, loop=self._loop)
			futures.append(future)

		writer = None
		if input is not None:
			if self._proc.stdin is None:
				raise TypeError('communicate: expected file or int, got {}'.format(type(self._proc.stdin)))
			writer = asyncio.ensure_future(_writer(self._proc.stdin, input), loop=self._loop)

		try:
			yield asyncio.wait(futures + [self.wait()], loop=self._loop)
		finally:
			if writer is not None:
				if writer.done():
					# Consume expected exceptions.
					try:
						writer.result()
					except EnvironmentError:
						# This is normal if the other end of the pipe was closed.
						pass
				else:
					writer.cancel()

		coroutine_return(tuple(future.result() for future in futures))

	def wait(self):
		"""
		Wait for child process to terminate. Set and return returncode attribute.

		@return: returncode
		@rtype: asyncio.Future (or compatible)
		"""
		waiter = self._loop.create_future()
		if self.returncode is None:
			self._waiters.append(waiter)
			waiter.add_done_callback(self._waiter_cancel)
		else:
			waiter.set_result(self.returncode)
		return waiter

	def _waiter_cancel(self, waiter):
		if waiter.cancelled():
			try:
				self._waiters.remove(waiter)
			except ValueError:
				pass

	def _proc_exit(self, pid, returncode):
		self._proc.returncode = returncode
		waiters = self._waiters
		self._waiters = []
		for waiter in waiters:
			waiter.set_result(returncode)
