#!/usr/bin/env python3

import unittest
import os


test_root_directory = os.path.join(os.path.dirname(__file__), 'tests')


def suite():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    module_tests = loader.discover(test_root_directory)

    suite.addTest(module_tests)

    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite())
