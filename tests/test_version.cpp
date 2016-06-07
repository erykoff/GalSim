/* -*- c++ -*-
 * Copyright (c) 2012-2015 by the GalSim developers team on GitHub
 * https://github.com/GalSim-developers
 *
 * This file is part of GalSim: The modular galaxy image simulation toolkit.
 * https://github.com/GalSim-developers/GalSim
 *
 * GalSim is free software: redistribution and use in source and binary forms,
 * with or without modification, are permitted provided that the following
 * conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this
 *    list of conditions, and the disclaimer given in the accompanying LICENSE
 *    file.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions, and the disclaimer given in the documentation
 *    and/or other materials provided with the distribution.
 */

#include <cstdio>
#include "GalSim.h"

#define BOOST_TEST_DYN_LINK

// icpc pretends to be GNUC, since it thinks it's compliant, but it's not.
// It doesn't understand #pragma GCC
// Rather, it uses #pragma warning(disable:nn)
#ifdef __INTEL_COMPILER

// Disable "overloaded virtual function ... is only partially overridden"
#pragma warning(disable:654)

#else

// The boost unit tests have some unused variables, so suppress the warnings about that.
// I think pragma GCC was introduced in gcc 4.2, so guard for >= that version 
#if defined(__GNUC__) && __GNUC__ >= 4 && (__GNUC__ >= 5 || __GNUC_MINOR__ >= 2)
#pragma GCC diagnostic ignored "-Wunused-variable"
#endif

// Not sure when this was added.  Currently check for it for versions >= 4.3
#if defined(__GNUC__) && __GNUC__ >= 4 && (__GNUC__ >= 5 || __GNUC_MINOR__ >= 3)
#pragma GCC diagnostic ignored "-Warray-bounds"
#endif

#if defined(__GNUC__) && __GNUC__ >= 4 && (__GNUC__ >= 5 || __GNUC_MINOR__ >= 8)
#pragma GCC diagnostic ignored "-Wunused-local-typedefs"
#endif

// Only clang seems to have this
#ifdef __clang__
#if __has_warning("-Wlogical-op-parentheses")
#pragma GCC diagnostic ignored "-Wlogical-op-parentheses"
#endif
#endif

#endif

#define BOOST_NO_CXX11_SMART_PTR
#include <boost/test/unit_test.hpp>
#include <boost/test/test_case_template.hpp>
#include <boost/test/floating_point_comparison.hpp>
#include <boost/mpl/list.hpp>

BOOST_AUTO_TEST_SUITE(version_tests);

BOOST_AUTO_TEST_CASE( TestVersion )
{
    // Here we mostly just check that the different ways to get the version are all consistent.

    // First, these are #define values we get from GalSim.h.
    int major = GALSIM_MAJOR;
    int minor = GALSIM_MINOR;
    int rev = GALSIM_REVISION;

    // Next, there are function versions of these that should return the same things.
    BOOST_CHECK(galsim::major_version() == major);
    BOOST_CHECK(galsim::minor_version() == minor);
    BOOST_CHECK(galsim::revision() == rev);

    // Finally, there is a function that returns the version as a string.
    char str[80];
    std::sprintf(str, "%d.%d.%d", major, minor, rev);
    BOOST_CHECK(galsim::version() == str);

    // And run the inline check as well.
    BOOST_CHECK(galsim::check_version());
}

BOOST_AUTO_TEST_SUITE_END();

