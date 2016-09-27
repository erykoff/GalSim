# Copyright (c) 2012-2016 by the GalSim developers team on GitHub
# https://github.com/GalSim-developers
#
# This file is part of GalSim: The modular galaxy image simulation toolkit.
# https://github.com/GalSim-developers/GalSim
#
# GalSim is free software: redistribution and use in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions, and the disclaimer given in the accompanying LICENSE
#    file.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions, and the disclaimer given in the documentation
#    and/or other materials provided with the distribution.
#
"""@file sed.py
Simple spectral energy distribution class.  Used by galsim/chromatic.py
"""

import numpy as np
from astropy import units as u

import galsim
from . import utilities

class SED(object):
    """Simple SED object to represent the spectral energy distributions of stars and galaxies.

    SEDs are callable, returning the flux density in photons/nm/cm^2/s as a function of wavelength.
    By default, the above wavelength used by __call__ is nanometers, but it's possible to use other
    units via the astropy.units module.  The return value *always* has units photons/nm/cm^2/s,
    however (just as a np.ndarray, though, never as an astropy.units.Quantity).

    SEDs are immutable; all transformative SED methods return *new* SEDs, and leave their
    originating SEDs unaltered.

    SEDs have `blue_limit` and `red_limit` attributes, which may be set to `None` in the case that
    the SED is defined by a python function or lambda `eval` string.  SEDs are considered undefined
    outside of this range, and __call__ will raise an exception if a flux density is requested
    outside of this range.  Note that `blue_limit` and `red_limit` are always in nanometers and in
    the observed frame when `redshift != 0`.

    SEDs may be multiplied by scalars or scalar functions of wavelength.  In particular, an SED
    multiplied by a `Bandpass` will yield the appropriately filtered SED.

    SEDs may be added together if they are at the same redshift.  The resulting SED will only be
    defined on the wavelength region where both of the operand SEDs are defined. `blue_limit` and
    `red_limit` will be reset accordingly.

    The input parameter, `spec`, may be one of several possible forms:
    1. a regular python function (or an object that acts like a function)
    2. a LookupTable
    3. a file from which a LookupTable can be read in
    4. a string which can be evaluated into a function of `wave`
       via eval('lambda wave : '+spec)
       e.g. spec = '0.8 + 0.2 * (wave-800)'

    The argument of `spec` should be the wavelength in units specified by `wave_type`, which should
    be an instance of `astropy.units.Unit` of equivalency class `spectral`.  Note that `spectral`
    includes not only units with dimensions of length, but also frequency, energy, or wavenumber.
    For backwards compatibility, `wave_type` can also be any of 'nm', 'nanometer', 'nanometers',
    'A', 'Ang', 'Angstrom', or 'Angstroms'.

    The return value of `spec` should be a spectral density with units specified by `flux_type`,
    which should be an instance of `astropy.units.Unit` of equivalency class `spectral_density`.
    The `spectral_density` class includes dimensions [energy/time/area/unit-wavelength],
    [energy/time/area/unit-frequency], [photons/time/area/unit-wavelength], and so on.  For
    backwards compatibility, `flux_type` can also be one of:
       1. 'flambda':  erg/wave_type/cm^2/s, where wave_type is as above.
       2. 'fnu':      erg/Hz/cm^2/s
       3. 'fphotons': photons/wave_type/cm^2/s, where wave_type is as above.

    Astropy.units.Quantity objects may also be used in calls to __call__ and withFluxDensity, though
    normal ndarrays or scalars are also allowed.

    Finally, the `fast` keyword option changes when unit conversions occur.  If `fast=True`, the
    default, then unit conversions occur at initialization, which can lead to faster subsequent
    operations.  The speed savings is probably only significant if `spec` is given as a LookupTable.
    The cost, however, is a loss of accuracy due to the fact that, for example, a piecewise linear
    function of wavelength will no longer be piecewise linear when converted to a function of
    frequency.

    @param spec          Function defining the z=0 spectrum at each wavelength.  See above for
                         valid options for this parameter.
    @param wave_type     String specifying units for wavelength input to `spec`.
    @param flux_type     String specifying what type of spectral density `spec` represents.  See
                         above for valid options for this parameter.
    @param redshift      Optionally shift the spectrum to the given redshift. [default: 0]
    @param fast          Convert units on initialization instead of on __call__. [default: True]
    """
    def __init__(self, spec, wave_type, flux_type, redshift=0., fast=True,
                 _blue_limit=None, _red_limit=None, _wave_list=None):

        self._orig_spec = spec  # Save these for pickling

        if isinstance(wave_type, str):
            if wave_type.lower() in ['nm', 'nanometer', 'nanometers']:
                wave_type = u.nm
            elif wave_type.lower() in ['a', 'ang', 'angstrom', 'angstroms']:
                wave_type = u.AA
            else:
                raise ValueError("Unknown wave_type '{0}'".format(wave_type))
        self.wave_type = wave_type

        if isinstance(flux_type, str):
            if flux_type.lower() == 'flambda':
                flux_type = u.erg / (u.s * self.wave_type * u.cm**2)
            elif flux_type.lower() == 'fphotons':
                flux_type = u.astrophys.photon / (u.s * self.wave_type * u.cm**2)
            elif flux_type.lower() == 'fnu':
                flux_type = u.erg / (u.s * u.Hz * u.cm**2)
            elif flux_type.lower() == '1':
                flux_type = u.dimensionless_unscaled
            else:
                raise ValueError("Unknown flux_type '{0}'".format(flux_type))
        self.flux_type = flux_type
        if not (self.dimensionless or self.spectral):
            raise TypeError("Flux_type must be equivalent to a spectral density or dimensionless.")

        self.redshift = redshift
        self.fast = fast
        # Convert string input into a real function (possibly a LookupTable)
        self.const = False
        self._initialize_spec()

        # Finish re-evaluating __init__() here.
        if _wave_list is not None:
            self.wave_list = _wave_list
            self.blue_limit = _blue_limit
            self.red_limit = _red_limit
            return

        if isinstance(self._spec, galsim.LookupTable):
            self.wave_list = (self._spec.getArgs() * self.wave_type).to(u.nm, u.spectral()).value
            self.wave_list *= (1.0 + self.redshift)
            self.blue_limit = np.min(self.wave_list)
            self.red_limit = np.max(self.wave_list)
        else:
            self.blue_limit = None
            self.red_limit = None
            self.wave_list = np.array([], dtype=float)

    def _initialize_spec(self):
        # Turn the input spec into a real function self._rest_photons
        # The function cannot be pickled, so will need to do this in getstate as well as init.

        if hasattr(self, '_spec'):
            return
        if isinstance(self._orig_spec, (int, float)):
            if not self.dimensionless:
                raise ValueError("Attempt to set dimensionful SED using float or integer.")
            self.const = True
            self._spec = lambda w: float(self._orig_spec)
        elif isinstance(self._orig_spec, str):
            import os
            if os.path.isfile(self._orig_spec):
                self._spec = galsim.LookupTable(file=self._orig_spec, interpolant='linear')
            else:
                # Don't catch ArithmeticErrors when testing to see if the the result of `eval()`
                # is valid since `spec = '1./(wave-700)'` will generate a ZeroDivisionError (which
                # is a subclass of ArithmeticError) despite being a valid spectrum specification,
                # while `spec = 'blah'` where `blah` is undefined generates a NameError and is not
                # a valid spectrum specification.
                # Are there any other types of errors we should trap here?
                try:
                    self._spec = galsim.utilities.math_eval('lambda wave : ' + self._orig_spec)
                    self._spec(700)
                except ArithmeticError:
                    pass
                except Exception as e:
                    raise ValueError(
                        "String spec must either be a valid filename or something that "+
                        "can eval to a function of wave.\n" +
                        "Input provided: {0}\n".format(self._orig_spec) +
                        "Caught error: {0}".format(e))

        else:
            self._spec = self._orig_spec

    @property
    def spectral(self):
        """Boolean indicating if SED has units compatible with a spectral density.
        """
        try:
            (1*self.flux_type).to(u.erg/u.s/u.cm**2/u.nm, u.spectral_density(1*u.nm))
        except u.UnitConversionError:
            return False
        return True

    @property
    def dimensionless(self):
        """Boolean indicating if SED is dimensionless.
        """
        try:
            (1*self.flux_type).to(u.dimensionless_unscaled)
        except u.UnitConversionError:
            return False
        return True

    def _wavelength_intersection(self, other):
        blue_limit = self.blue_limit
        if other.blue_limit is not None:
            if blue_limit is None:
                blue_limit = other.blue_limit
            else:
                blue_limit = max([blue_limit, other.blue_limit])

        red_limit = self.red_limit
        if other.red_limit is not None:
            if red_limit is None:
                red_limit = other.red_limit
            else:
                red_limit = min([red_limit, other.red_limit])

        return blue_limit, red_limit

    def _rest_nm_to_photons(self, wave):
        wave_native_quantity = (wave * u.nm).to(self.wave_type, u.spectral())
        wave_native_value = wave_native_quantity.value
        flux_native_quantity = self._spec(wave_native_value) * self.flux_type
        return (flux_native_quantity
                .to(u.astrophys.photon/(u.s*u.cm**2*u.nm),
                    u.spectral_density(wave_native_quantity))
                .value)

    def _obs_nm_to_photons(self, wave):
        return self._rest_nm_to_photons(wave / (1.0 + self.redshift))

    def _rest_nm_to_dimensionless(self, wave):
        wave_native_value = (wave * u.nm).to(self.wave_type, u.spectral()).value
        return self._spec(wave_native_value)

    # Does it every actually make sense for an SED with a redshift to be dimensionless?
    def _obs_nm_to_dimensionless(self, wave):
        return self._rest_nm_to_dimensionless(wave / (1.0 + self.redshift))

    def _check_bounds(self, wave):
        if hasattr(wave, '__iter__'):
            wmin = np.min(wave)
            wmax = np.max(wave)
        else:
            wmin = wmax = wave

        extrapolation_slop = 1.e-6 # allow a small amount of extrapolation
        if self.blue_limit is not None:
            if wmin < self.blue_limit - extrapolation_slop:
                raise ValueError("Requested wavelength ({0}) is bluer than blue_limit ({1})"
                                 .format(wmin, self.blue_limit))
        if self.red_limit is not None:
            if wmax > self.red_limit + extrapolation_slop:
                raise ValueError("Requested wavelength ({0}) is redder than red_limit ({1})"
                                 .format(wmax, self.red_limit))

    def _call_fast(self, wave):
        """ Return flux in photons / sec / cm^2 / nm.

        Assumes that self._spec has already been transformed to accept correct wavelength units and
        yield correct flux units.

        @param wave  Wavelength in nanometers.
        @returns     Flux.
        """
        self._check_bounds(wave)

        # Create a fast version of self._spec by constructing a LookupTable on self.wave_list
        if not hasattr(self, '_fast_spec'):
            if (self.wave_type == u.nm
                and self.flux_type == (u.astrophys.photon / (u.s * u.cm**2 * u.nm))):
                    self._fast_spec = self._spec
            else:
                if len(self.wave_list) == 0:
                    if self.spectral:
                        self._fast_spec = self._rest_nm_to_photons
                    else:
                        self._fast_spec = self._rest_nm_to_dimensionless
                else:
                    x = self.wave_list / (1.0 + self.redshift)
                    if self.spectral:
                        f = self._rest_nm_to_photons(x)
                    else:
                        f = self._rest_nm_to_dimensionless(x)
                    self._fast_spec = galsim.LookupTable(x, f, interpolant='linear')

        if isinstance(wave, tuple):
            return tuple(self._fast_spec(np.array(wave) / (1.0 + self.redshift)))
        elif isinstance(wave, list):
            return list(self._fast_spec(np.array(wave) / (1.0 + self.redshift)))
        else:  # ndarray or scalar
            return self._fast_spec(wave / (1.0 + self.redshift))

    def _call_slow(self, wave):
        """ Return flux in photons / sec / cm^2 / nm.

        Uses self._spec that has not been pre-transformed for desired units, instead does all unit
        conversions inside this method.

        @param wave  Wavelength.  If not a Quantity, then assumed units are nanometers.
        @returns     Flux.
        """
        wave_in = wave
        # Convert wave to nanometers if needed.
        if isinstance(wave, u.Quantity):
            wave = wave.to(u.nm, u.spectral()).value

        self._check_bounds(wave)

        # Figure out rest-frame wave_type wavelength array for query to self._spec.
        rest_wave = wave / (1.0 + self.redshift)
        rest_wave_quantity = rest_wave * u.nm
        rest_wave_native = rest_wave_quantity.to(self.wave_type, u.spectral()).value

        out = self._spec(rest_wave_native)

        # Manipulate output units
        if self.spectral:
            out = out * self.flux_type
            out = out.to(u.astrophys.photon/(u.s*u.cm**2*u.nm),
                         u.spectral_density(rest_wave_quantity)).value

        # Return same format as received (except Quantity -> ndarray)
        if isinstance(wave_in, tuple):
            return tuple(out)
        elif isinstance(wave_in, list):
            return list(out)
        else:
            return out # Works for np.ndarray, Quantity, or scalar.

    def __call__(self, wave):
        """ Return photon flux density at wavelength `wave`.

        Note that outside of the wavelength range defined by the `blue_limit` and `red_limit`
        attributes, the SED is considered undefined, and this method will raise an exception if a
        flux density at a wavelength outside the defined range is requested.

        @param wave     Wavelength in nanometers at which to evaluate the SED.

        @returns the photon flux density in units of photons/nm/cm^2/s.
        """
        if self.fast:
            return self._call_fast(wave)
        else:
            return self._call_slow(wave)

    def __mul__(self, other):
        # Watch out for 5 types of `other`:
        # 1.  SED: Check that not both spectral densities.
        # 2.  GSObject: return a ChromaticObject().
        # 3.  Bandpass: return an SED, but carefully propagate blue/red limit and wave_list.
        # 4.  Callable: return an SED
        # 5.  Scalar: return an SED
        #
        # Additionally, check for shortcuts when self.const

        # Product of two SEDs
        if isinstance(other, galsim.SED):
            if self.spectral and other.spectral:
                raise TypeError("Cannot multiply two spectral densities together.")

            if other.const:
                return self.__mul__(other._spec(1.0))
            elif self.const:
                return other.__mul__(self._spec(1.0))

            if self.spectral:
                redshift = self.redshift
            elif other.spectral:
                redshift = other.redshift
            else:
                redshift = 0.0

            fast = self.fast and other.fast

            wave_list, blue_limit, red_limit = galsim.utilities.combine_wave_list(self, other)
            spec = lambda w: self(w*(1.0+self.redshift)) * other(w * (1.0 + other.redshift))
            return SED(spec, 'nm', 'fphotons', redshift=redshift, fast=fast,
                       _blue_limit=blue_limit, _red_limit=red_limit, _wave_list=wave_list)

        # Product of SED and achromatic GSObject is a `ChromaticTransformation`.
        if isinstance(other, galsim.GSObject):
            return galsim.Transform(other, flux_ratio=self)

        # Product of SED and Bandpass is (filtered) SED.  The `redshift` attribute is retained.
        if isinstance(other, galsim.Bandpass):
            if self.const:
                # make a new scaled Bandpass, and use that to initialize a new SED.
                new_bp = other * self._spec(1.0)
                return SED(new_bp.func, 'nm', '1', redshift=self.redshift,
                           _blue_limit=new_bp.blue_limit, _red_limit=new_bp.red_limit,
                           _wave_list=new_bp._wave_list)
            else:
                wave_list, blue_limit, red_limit = galsim.utilities.combine_wave_list(self, other)
                spec = lambda w: self(w*(1.0+self.redshift)) * other(w * (1.0 + self.redshift))
                return SED(spec, 'nm', 'fphotons', redshift=self.redshift,
                           _blue_limit=blue_limit, _red_limit=red_limit, _wave_list=wave_list)

        # Product of SED with generic callable is also a (filtered) SED, with retained `redshift`.
        if hasattr(other, '__call__'):
            spec = lambda w: self(w * (1.0 + self.redshift)) * other(w * (1.0 + self.redshift))
            flux_type = 'fphotons' if self.spectral else '1'
            return SED(spec, 'nm', flux_type, redshift=self.redshift,
                       _blue_limit=self.blue_limit, _red_limit=self.red_limit,
                       _wave_list=self.wave_list)

        if isinstance(other, (int, float)):
            # If other is a scalar and self._spec a LookupTable, then remake that LookupTable.
            if isinstance(self._spec, galsim.LookupTable):
                wave_type = self.wave_type
                flux_type = self.flux_type
                x = self._spec.getArgs()
                f = [ val * other for val in self._spec.getVals() ]
                spec = galsim.LookupTable(x, f, x_log=self._spec.x_log, f_log=self._spec.f_log,
                                          interpolant=self._spec.interpolant)
            elif self.const:
                spec = self._spec(1.0) * other
                wave_type = 'nm'
                flux_type = '1'
            else:
                wave_type = 'nm'
                flux_type = 'fphotons' if self.spectral else '1'
                spec = lambda w: self(w * (1.0 + self.redshift)) * other
            return SED(spec, wave_type, flux_type, redshift=self.redshift,
                       _blue_limit=self.blue_limit, _red_limit=self.red_limit,
                       _wave_list=self.wave_list)

    def __rmul__(self, other):
        return self*other

    def __div__(self, other):
        # Prohibit division of two SEDs as dimensionally inconsistent.
        # I suppose we _could_ return a python function here, but certainly not another SED.
        if isinstance(other, galsim.SED):
            raise TypeError("Cannot divide two SEDs.")
        if hasattr(other, '__call__'):
            spec = lambda w: self(w * (1.0 + self.redshift)) / other(w * (1.0 + self.redshift))
        elif isinstance(self._spec, galsim.LookupTable):
            # If other is not a function, then there is no loss of accuracy by applying the
            # factor directly to the LookupTable, if that's what we are using.
            # Make sure to keep the same properties about the table, flux_type, wave_type.
            x = self._spec.getArgs()
            f = [ val / other for val in self._spec.getVals() ]
            spec = galsim.LookupTable(x, f, x_log=self._spec.x_log, f_log=self._spec.f_log,
                                      interpolant=self._spec.interpolant)
        else:
            spec = lambda w: self(w * (1.0 + self.redshift)) / other

        return SED(spec, flux_type=self.flux_type, wave_type=self.wave_type, redshift=self.redshift,
                   _wave_list=self.wave_list,
                   _blue_limit=self.blue_limit, _red_limit=self.red_limit)

    def __truediv__(self, other):
        return self.__div__(other)

    def __add__(self, other):
        # Add together two SEDs, with the following caveats:
        # 1) The SEDs must have the same redshift.
        # 2) The resulting SED will be defined on the wavelength range set by the overlap of the
        #    wavelength ranges of the two SED operands.
        # 3) The new `wave_list` will be the union of the operand `wave_list`s in the intersecting
        #    region, even if one or both of the `wave_list`s are empty.
        # These conditions ensure that SED addition is commutative.

        if self.redshift != other.redshift:
            raise ValueError("Can only add SEDs with same redshift.")

        if self.dimensionless and other.dimensionless:
            flux_type = '1'
        elif self.spectral and other.spectral:
            flux_type = 'fphotons'
        else:
            raise TypeError("Cannot add SEDs with different dimensions.")

        spec = lambda w: self(w*(1.0+self.redshift)) + other(w*(1.0 + self.redshift))
        wave_list, blue_limit, red_limit = galsim.utilities.combine_wave_list([self, other])

        return SED(spec, wave_type='nm', flux_type=flux_type,
                   redshift=self.redshift, _wave_list=wave_list,
                   _blue_limit=blue_limit, _red_limit=red_limit)

    def __sub__(self, other):
        # Subtract two SEDs, with the same caveats as adding two SEDs.
        return self.__add__(-1.0 * other)

    def withFluxDensity(self, target_flux_density, wavelength):
        """ Return a new SED with flux density set to `target_flux_density` at wavelength
        `wavelength`.  Note that this normalization is *relative* to the `flux` attribute of the
        chromaticized GSObject.

        @param target_flux_density  The target *relative* normalization in photons/nm/cm^2/s.
        @param wavelength           The wavelength, in nm, at which the flux density will be set.

        @returns the new normalized SED.
        """
        if self.dimensionless:
            raise TypeError("Cannot set flux density of dimensionless SED.")
        if isinstance(wavelength, u.Quantity):
            wavelength_nm = wavelength.to(u.nm, u.spectral())
        current_flux_density = self(wavelength)
        if isinstance(target_flux_density, u.Quantity):
            target_flux_density = target_flux_density.to(
                    u.astrophys.photons/(u.s * u.cm**2 * u.nm),
                    u.spectral_density(wavelength_nm * u.nm)).value
        factor = target_flux_density / current_flux_density
        return self * factor

    def withFlux(self, target_flux, bandpass):
        """ Return a new SED with flux through the Bandpass `bandpass` set to `target_flux`.  Note
        that this normalization is *relative* to the `flux` attribute of the chromaticized GSObject.

        @param target_flux  The desired *relative* flux normalization of the SED.
        @param bandpass     A Bandpass object defining a filter bandpass.

        @returns the new normalized SED.
        """
        current_flux = self.calculateFlux(bandpass)
        norm = target_flux/current_flux
        return self * norm

    def withMagnitude(self, target_magnitude, bandpass):
        """ Return a new SED with magnitude through `bandpass` set to `target_magnitude`.  Note
        that this requires `bandpass` to have been assigned a zeropoint using
        `Bandpass.withZeropoint()`.  When the returned SED is multiplied by a GSObject with
        flux=1, the resulting ChromaticObject will have magnitude `target_magnitude` when drawn
        through `bandpass`.  Note that the total normalization depends both on the SED and the
        GSObject.  See the galsim.Chromatic docstring for more details on normalization
        conventions.

        @param target_magnitude  The desired *relative* magnitude of the SED.
        @param bandpass          A Bandpass object defining a filter bandpass.

        @returns the new normalized SED.
        """
        if bandpass.zeropoint is None:
            raise RuntimeError("Cannot call SED.withMagnitude on this bandpass, because it does not"
                               " have a zeropoint.  See Bandpass.withZeropoint()")
        current_magnitude = self.calculateMagnitude(bandpass)
        norm = 10**(-0.4*(target_magnitude - current_magnitude))
        return self * norm

    def atRedshift(self, redshift):
        """ Return a new SED with redshifted wavelengths.

        @param redshift

        @returns the redshifted SED.
        """
        wave_factor = (1.0 + redshift) / (1.0 + self.redshift)
        wave_list = self.wave_list * wave_factor
        blue_limit = self.blue_limit
        red_limit = self.red_limit
        if blue_limit is not None:
            blue_limit *= wave_factor
        if red_limit is not None:
            red_limit *= wave_factor
        wave_type = self.wave_type
        flux_type = self.flux_type

        return SED(self._orig_spec, wave_type, flux_type, redshift,
                   _wave_list=wave_list, _blue_limit=blue_limit, _red_limit=red_limit)

    def calculateFlux(self, bandpass):
        """ Return the flux (photons/cm^2/s) of the SED through the bandpass.

        @param bandpass   A Bandpass object representing a filter, or None to compute the bolometric
                          flux.  For the bolometric flux the integration limits will be set to
                          (0, infinity) unless overridden by non-`None` SED attributes `blue_limit`
                          or `red_limit`.  Note that SEDs defined using `LookupTable`s automatically
                          have `blue_limit` and `red_limit` set.

        @returns the flux through the bandpass.
        """
        if self.dimensionless:
            raise TypeError("Cannot calculate flux of dimensionless SED.")
        if bandpass is None: # do bolometric flux
            if self.blue_limit is None:
                blue_limit = 0.0
            else:
                blue_limit = self.blue_limit
            if self.red_limit is None:
                red_limit = 1.e11 # = infinity in int1d
            else:
                red_limit = self.red_limit
            if len(self.wave_list) > 0:
                return(np.trapz(self(self.wave_list), self.wave_list))
            else:
                return galsim.integ.int1d(self, blue_limit, red_limit)
        else: # do flux through bandpass
            if len(bandpass.wave_list) > 0 or len(self.wave_list) > 0:
                x, _, _ = galsim.utilities.combine_wave_list([self, bandpass])
                return np.trapz(bandpass(x) * self(x), x)
            else:
                return galsim.integ.int1d(lambda w: bandpass(w)*self(w),
                                          bandpass.blue_limit, bandpass.red_limit)

    def calculateMagnitude(self, bandpass):
        """ Return the SED magnitude through a Bandpass `bandpass`.  Note that this requires
        `bandpass` to have been assigned a zeropoint using `Bandpass.withZeropoint()`.

        @param bandpass   A Bandpass object representing a filter, or None to compute the
                          bolometric magnitude.  For the bolometric magnitude the integration
                          limits will be set to (0, infinity) unless overridden by non-`None` SED
                          attributes `blue_limit` or `red_limit`.  Note that SEDs defined using
                          `LookupTable`s automatically have `blue_limit` and `red_limit` set.

        @returns the bandpass magnitude.
        """
        if self.dimensionless:
            raise TypeError("Cannot calculate magnitude of dimensionless SED.")
        if bandpass.zeropoint is None:
            raise RuntimeError("Cannot do this calculation for a bandpass without an assigned"
                               " zeropoint")
        flux = self.calculateFlux(bandpass)
        return -2.5 * np.log10(flux) + bandpass.zeropoint

    def thin(self, rel_err=1.e-4, trim_zeros=True, preserve_range=True, fast_search=True):
        """ If the SED was initialized with a LookupTable or from a file (which internally creates a
        LookupTable), then remove tabulated values while keeping the integral over the set of
        tabulated values still accurate to `rel_err`.

        @param rel_err            The relative error allowed in the integral over the SED
                                  [default: 1.e-4]
        @param trim_zeros         Remove redundant leading and trailing points where f=0?  (The last
                                  leading point with f=0 and the first trailing point with f=0 will
                                  be retained).  Note that if both trim_leading_zeros and
                                  preserve_range are True, then the only the range of `x` *after*
                                  zero trimming is preserved.  [default: True]
        @param preserve_range     Should the original range (`blue_limit` and `red_limit`) of the
                                  SED be preserved? (True) Or should the ends be trimmed to
                                  include only the region where the integral is significant? (False)
                                  [default: True]
        @param fast_search        If set to True, then the underlying algorithm will use a
                                  relatively fast O(N) algorithm to select points to include in the
                                  thinned approximation.  If set to False, then a slower O(N^2)
                                  algorithm will be used.  We have found that the slower algorithm
                                  tends to yield a thinned representation that retains fewer samples
                                  while still meeting the relative error requirement.
                                  [default: True]

        @returns the thinned SED.
        """
        if len(self.wave_list) > 0:
            rest_wave_nm = self.wave_list / (1.0 + self.redshift) * u.nm
            rest_wave_native_units = rest_wave_nm.to(self.wave_type, u.spectral()).value
            spec_native_units = self._spec(rest_wave_native_units)

            # Note that this is thinning in native units, not nm and photons/nm.
            newx, newf = utilities.thin_tabulated_values(
                    rest_wave_native_units, spec_native_units,
                    trim_zeros=trim_zeros, preserve_range=preserve_range, fast_search=fast_search)

            newspec = galsim.LookupTable(newx, newf, interpolant='linear')
            return SED(newspec, self.wave_type, self.flux_type, redshift=self.redshift)
        else:
            return self

    def calculateDCRMomentShifts(self, bandpass, **kwargs):
        """ Calculates shifts in first and second moments of PSF due to differential chromatic
        refraction (DCR).  I.e., equations (1) and (2) from Plazas and Bernstein (2012)
        (http://arxiv.org/abs/1204.1346).

        @param bandpass             Bandpass through which object is being imaged.
        @param zenith_angle         Angle from object to zenith, expressed as an Angle
        @param parallactic_angle    Parallactic angle, i.e. the position angle of the zenith,
                                    measured from North through East.  [default: 0]
        @param obj_coord            Celestial coordinates of the object being drawn as a
                                    CelestialCoord. [default: None]
        @param zenith_coord         Celestial coordinates of the zenith as a CelestialCoord.
                                    [default: None]
        @param HA                   Hour angle of the object as an Angle. [default: None]
        @param latitude             Latitude of the observer as an Angle. [default: None]
        @param pressure             Air pressure in kiloPascals.  [default: 69.328 kPa]
        @param temperature          Temperature in Kelvins.  [default: 293.15 K]
        @param H2O_pressure         Water vapor pressure in kiloPascals.  [default: 1.067 kPa]

        @returns a tuple.  The first element is the vector of DCR first moment shifts, and the
                 second element is the 2x2 matrix of DCR second (central) moment shifts.
        """
        if self.dimensionless:
            raise TypeError("Cannot calculate DCR shifts of dimensionless SED.")
        if 'zenith_angle' in kwargs:
            zenith_angle = kwargs.pop('zenith_angle')
            parallactic_angle = kwargs.pop('parallactic_angle', 0.0*galsim.degrees)
        elif 'obj_coord' in kwargs:
            obj_coord = kwargs.pop('obj_coord')
            if 'zenith_coord' in kwargs:
                zenith_coord = kwargs.pop('zenith_coord')
                zenith_angle, parallactic_angle = galsim.dcr.zenith_parallactic_angles(
                    obj_coord=obj_coord, zenith_coord=zenith_coord)
            else:
                if 'HA' not in kwargs or 'latitude' not in kwargs:
                    raise TypeError("calculateDCRMomentShifts requires either zenith_coord or "+
                                    "(HA, latitude) when obj_coord is specified!")
                HA = kwargs.pop('HA')
                latitude = kwargs.pop('latitude')
                zenith_angle, parallactic_angle = galsim.dcr.zenith_parallactic_angles(
                    obj_coord=obj_coord, HA=HA, latitude=latitude)
        else:
            raise TypeError(
                "Need to specify zenith_angle and parallactic_angle in calculateDCRMomentShifts!")
        # Any remaining kwargs will get forwarded to galsim.dcr.get_refraction
        # Check that they're valid
        for kw in kwargs:
            if kw not in ['temperature', 'pressure', 'H2O_pressure']:
                raise TypeError("Got unexpected keyword in calculateDCRMomentShifts: {0}".format(kw))
        # Now actually start calculating things.
        flux = self.calculateFlux(bandpass)
        if len(bandpass.wave_list) > 0:
            x, _, _ = galsim.utilities.combine_wave_list([self, bandpass])
            R = galsim.dcr.get_refraction(x, zenith_angle, **kwargs)
            photons = self(x)
            throughput = bandpass(x)
            Rbar = np.trapz(throughput * photons * R, x) / flux
            V = np.trapz(throughput * photons * (R-Rbar)**2, x) / flux
        else:
            weight = lambda w: bandpass(w) * self(w)
            Rbar_kernel = lambda w: galsim.dcr.get_refraction(w, zenith_angle, **kwargs)
            Rbar = galsim.integ.int1d(lambda w: weight(w) * Rbar_kernel(w),
                                      bandpass.blue_limit, bandpass.red_limit)
            V_kernel = lambda w: (galsim.dcr.get_refraction(w, zenith_angle, **kwargs) - Rbar)**2
            V = galsim.integ.int1d(lambda w: weight(w) * V_kernel(w),
                                   bandpass.blue_limit, bandpass.red_limit)
        # Rbar and V are computed above assuming that the parallactic angle is 0.  Hence we
        # need to rotate our frame by the parallactic angle to get the desired output.
        sinp, cosp = parallactic_angle.sincos()
        rot = np.array([[cosp, -sinp], [sinp, cosp]])
        Rbar = Rbar * rot.dot(np.array([0,1]))
        V = rot.dot(np.array([[0, 0], [0, V]])).dot(rot.T)
        return Rbar, V

    def calculateSeeingMomentRatio(self, bandpass, alpha=-0.2, base_wavelength=500):
        """ Calculates the relative size of a PSF compared to the monochromatic PSF size at
        wavelength `base_wavelength`.

        @param bandpass             Bandpass through which object is being imaged.
        @param alpha                Power law index for wavelength-dependent seeing.  [default:
                                    -0.2, the prediction for Kolmogorov turbulence]
        @param base_wavelength      Reference wavelength in nm from which to compute the relative
                                    PSF size.  [default: 500]
        @returns the ratio of the PSF second moments to the second moments of the reference PSF.
        """
        if self.dimensionless:
            raise TypeError("Cannot calculate seeing moment ratio of dimensionless SED.")
        flux = self.calculateFlux(bandpass)
        if len(bandpass.wave_list) > 0:
            x, _, _ = galsim.utilities.combine_wave_list([self, bandpass])
            photons = self(x)
            throughput = bandpass(x)
            return np.trapz(photons * throughput * (x/base_wavelength)**(2*alpha), x) / flux
        else:
            weight = lambda w: bandpass(w) * self(w)
            kernel = lambda w: (w/base_wavelength)**(2*alpha)
            return galsim.integ.int1d(lambda w: weight(w) * kernel(w),
                                      bandpass.blue_limit, bandpass.red_limit) / flux

    def __eq__(self, other):
        return (isinstance(other, SED) and
                self._orig_spec == other._orig_spec and
                self.fast == other.fast and
                self.wave_type == other.wave_type and
                self.flux_type == other.flux_type and
                self.redshift == other.redshift and
                self.red_limit == other.red_limit and
                self.blue_limit == other.blue_limit and
                np.array_equal(self.wave_list,other.wave_list))

    def __ne__(self, other): return not self.__eq__(other)

    def __hash__(self):
        # Cache this in case self._orig_spec or self.wave_list is long.
        if not hasattr(self, '_hash'):
            self._hash = hash(("galsim.SED", self._orig_spec, self.wave_type, self.flux_type,
                               self.redshift, self.fast, self.blue_limit, self.red_limit,
                               tuple(self.wave_list)))
        return self._hash

    def __repr__(self):
        outstr = ('galsim.SED(%r, redshift=%r, wave_type=%r, flux_type=%r' +
                  ' _wave_list=%r, _blue_limit=%r, _red_limit=%r)')%(
                      self._orig_spec, self.redshift, self.wave_type, self.flux_type,
                      self.wave_list, self.blue_limit, self.red_limit)
        return outstr

    def __str__(self):
        orig_spec = repr(self._orig_spec)
        if len(orig_spec) > 80:
            orig_spec = str(self._orig_spec)
        return 'galsim.SED(%s, redshift=%s)'%(orig_spec, self.redshift)

    def __getstate__(self):
        d = self.__dict__.copy()
        if not isinstance(d['_spec'], galsim.LookupTable):
            del d['_spec']
        if '_fast_spec' in d:
            del d['_fast_spec']
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        if '_spec' not in d:
            self._initialize_spec()
