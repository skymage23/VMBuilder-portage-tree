# Copyright 2018 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

try:
	import asyncio
except ImportError:
	asyncio = None

from portage.tests import TestCase
from portage.util.futures.unix_events import DefaultEventLoopPolicy


class PolicyWrapperRecursionTestCase(TestCase):
	def testPolicyWrapperRecursion(self):
		if asyncio is None:
			self.skipTest('asyncio is not available')

		initial_policy = asyncio.get_event_loop_policy()
		if not isinstance(initial_policy, DefaultEventLoopPolicy):
			asyncio.set_event_loop_policy(DefaultEventLoopPolicy())

		try:
			with self.assertRaises(NotImplementedError):
				asyncio.get_event_loop()

			with self.assertRaises(NotImplementedError):
				asyncio.get_child_watcher()
		finally:
			asyncio.set_event_loop_policy(initial_policy)
