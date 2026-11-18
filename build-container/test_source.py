#!/usr/bin/env python3
"""Canonical-source tests; generated catalog/archive tests run after build."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests import test_manual_standard, test_math_notation
if __name__=='__main__':
    loader=unittest.TestLoader()
    suite=unittest.TestSuite(loader.loadTestsFromModule(module)
                            for module in (test_manual_standard,test_math_notation))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
