
"""@brief Tests of the LookupTable class.

Compares interpolated values a LookupTable that were created using a previous version of
the code (commit: e267f058351899f1f820adf4d6ab409d5b2605d5), using the
script devutils/external/make_table_testarrays.py
"""
import os
import numpy as np

path, filename = os.path.split(__file__) # Get the path to this file for use below...
try:
    import galsim
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(path, "..")))
    import galsim

def funcname():
    import inspect
    return inspect.stack()[1][3]


TESTDIR=os.path.join(path, "table_comparison_files")

DECIMAL = 14 # Make sure output agrees at 14 decimal places or better

# Some arbitrary args to use for the test:
args1 = range(7)  # Evenly spaced
vals1 = [ x**2 for x in args1 ]
testargs1 = [ 0.1, 0.8, 2.3, 3, 5.6, 5.9 ] # < 0 or > 7 is invalid

args2 = [ 0.7, 3.3, 14.1, 15.6, 29, 34.1, 42.5 ]  # Not evenly spaced
vals2 = [ np.sin(x*np.pi/180) for x in args2 ]
testargs2 = [ 1.1, 10.8, 12.3, 15.6, 25.6, 41.9 ] # < 0.7 or > 42.5 is invalid

interps = [ 'linear', 'spline', 'floor', 'ceil' ]

def test_table():
    """Test the spline tabulation of the k space Cubic interpolant.
    """
    import time
    t1 = time.time()

    for interp in interps:
        table1 = galsim.LookupTable(args1,vals1,interp)
        testvals1 = [ table1(x) for x in testargs1 ]

        # The 4th item is in the args list, so it should be exactly the same as the 
        # corresponding item in the vals list.
        np.testing.assert_almost_equal(testvals1[3], vals1[3], DECIMAL,
                err_msg="Interpolated value for exact arg entry does not match val entry")

        # Do a full regression test based on a version of the code thought to be working.
        ref1 = np.loadtxt(os.path.join(TESTDIR, 'table_test1_%s.txt'%interp))
        np.testing.assert_array_almost_equal(ref1, testvals1, DECIMAL,
                err_msg="Interpolated values from LookupTable do not match saved "+
                "data for evenly-spaced args, with interpolant %s."%interp)

        # Same thing, but now for args that are not evenly spaced.
        # (The Table class uses a different algorithm when the arguments are evenly spaced
        #  than when they are not.)
        table2 = galsim.LookupTable(args2,vals2,interp)
        testvals2 = [ table2(x) for x in testargs2 ]

        np.testing.assert_almost_equal(testvals2[3], vals2[3], DECIMAL,
                err_msg="Interpolated value for exact arg entry does not match val entry")
        ref2 = np.loadtxt(os.path.join(TESTDIR, 'table_test2_%s.txt'%interp))
        np.testing.assert_array_almost_equal(ref2, testvals2, DECIMAL,
                err_msg="Interpolated values from LookupTable do not match saved "+
                "data for non-evenly-spaced args, with interpolant %s."%interp)

    t2 = time.time()
    print 'time for %s = %.2f'%(funcname(),t2-t1)

if __name__ == "__main__":
    test_table()

