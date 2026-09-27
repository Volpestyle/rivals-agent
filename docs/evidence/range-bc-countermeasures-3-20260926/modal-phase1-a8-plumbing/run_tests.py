import pathlib,sys,unittest
B=pathlib.Path(__file__).resolve().parent
sys.path[:0]=[str(B),str(B/"dependencies")]
suite=unittest.defaultTestLoader.discover(str(B),pattern="test_*.py")
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
