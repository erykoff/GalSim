# Copyright 2012, 2013 The GalSim developers:
# https://github.com/GalSim-developers
#
# This file is part of GalSim: The modular galaxy image simulation toolkit.
#
# GalSim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GalSim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GalSim.  If not, see <http://www.gnu.org/licenses/>
#
"""@file chromatic.py
Definitions for GalSim classes implementing wavelength-dependence.

This file extends the base GalSim classes by allowing them to be wavelength dependent.  This allows
one to implement wavelength-dependent PSFs or galaxies with color gradients.
"""

import galsim

class ChromaticObject(object):
    """Base class for defining wavelength dependent objects.
    """
    def draw(self, throughput_fn, bluelim, redlim, N=100, image=None, add_to_image=False,
             *args, **kwargs):
        """Draws an Image of a chromatic object as observed through a bandpass filter.

        Draws the image wavelength by wavelength, i.e., using a Riemann sum.  This is often slow,
        especially if each wavelength involves multiple convolutions, for example.  Hence, subclasses
        should try to override this method if they can think of clever ways to reduce the number of
        convolutions needed (see ChromaticConvolution below, for instance)

        @param throughput_fn  A function to take wavelength in nanometers and return the total system
                              dimensionless throughput.
        @bluelim              Lower (blue) limit for wavelength integration.
        @redlim               Upper (red) limit for wavelength integration.
        @N                    Number of points to use for Riemann sum evaluation.  Default 100.

        @returns           The drawn image.
        """

        h = (redlim * 1.0 - bluelim) / N
        ws = [bluelim + h * (i+0.5) for i in range(N)]

        prof = self.evaluateAtWavelength(ws[0]) * throughput_fn(ws[0]) * h
        image = prof.draw(image=image, add_to_image=add_to_image, *args, **kwargs)

        for w in ws[1:]:
            prof = self.evaluateAtWavelength(w) * throughput_fn(w) * h
            image = prof.draw(image=image, add_to_image=True, *args, **kwargs)
        return image

    def __add__(self, other):
        return galsim.ChromaticSum([self, other])

    def __iadd__(self, other):
        self = galsim.ChromaticSum([self, other])
        return self

class Chromatic(ChromaticObject):
    """Construct chromatic versions of the galsim GSObjects.

    This class extends the base GSObjects in basy.py by adding SEDs.  Useful to consistently generate
    the same galaxy observed through different filters, or, with the ChromaticSum class, to construct
    multi-component galaxies, each with a different SED. For example, a bulge+disk galaxy could be
    constructed:

    >>> bulge_SED = user_function_to_get_bulge_spectrum()
    >>> disk_SED = user_function_to_get_disk_spectrum()
    >>> bulge_mono = galsim.DeVaucouleurs(half_light_radius=1.0)
    >>> bulge = galsim.Chromatic(mono, bulge_SED)
    >>> disk_mono = galsim.Exponential(half_light_radius=2.0)
    >>> disk = galsim.Chromatic(disk_mono, disk_SED)
    >>> gal = galsim.ChromaticSum([bulge, disk])

    The SED is specified as a galsim.SED object.  The normalization is set via the SED.  I.e., the
    SED implicitly has units of counts per nanometer.  The drawn flux will be an intregral over this
    distribution.
    """
    def __init__(self, gsobj, SED):
        """Initialize Chromatic.

        @param gsobj    An GSObject instance to be chromaticized.
        @param SED      A SED object.
        """
        self.SED = SED
        self.gsobj = gsobj
        # Chromaticized GSObjects are separable into spatial (x,y) and spectral (lambda) factors.
        self.separable = True

    # Make op* and op*= work to adjust the flux of an object
    def __imul__(self, other):
        self.gsobj.scaleFlux(other)
        return self

    def __mul__(self, other):
        ret = self.copy()
        ret *= other
        return ret

    def __rmul__(self, other):
        ret = self.copy()
        ret *= other
        return ret

    # Make a copy of an object
    # Not sure if `SED` and `gsobj` copy cleanly here or not...
    def copy(self):
        cls = self.__class__
        ret = cls.__new__(cls)
        ret.__dict__.update(self.__dict__)
        return ret

    def applyShear(self, *args, **kwargs):
        self.gsobj.applyShear(*args, **kwargs)

    def applyDilation(self, *args, **kwargs):
        self.gsobj.applyDilation(*args, **kwargs)

    def applyShift(self, *args, **kwargs):
        self.gsobj.applyShift(*args, **kwargs)

    def applyExpansion(self, *args, **kwargs):
        self.gsobj.applyExpansion(*args, **kwargs)

    def applyMagnification(self, *args, **kwargs):
        self.gsobj.applyMagnification(*args, **kwargs)

    def applyLensing(self, *args, **kwargs):
        self.gsobj.applyLensing(*args, **kwargs)

    def applyRotation(self, *args, **kwargs):
        self.gsobj.applyRotation(*args, **kwargs)

    def evaluateAtWavelength(self, wave):
        """
        @param wave  Wavelength in nanometers.
        @returns     GSObject for profile at specified wavelength
        """
        return self.SED(wave) * self.gsobj

class ChromaticSum(ChromaticObject):
    """Sum ChromaticObjects and/or GSObjects together.  GSObjects are treated as having flat spectra.
    """
    def __init__(self, objlist):
        self.objlist = objlist

    def evaluateAtWavelength(self, wave):
        """
        @param wave  Wavelength in nanometers.
        @returns     GSObject for profile at specified wavelength
        """
        return galsim.Sum([obj.evaluateAtWavelength(wave) for obj in self.objlist])

    def draw(self, throughput_fn, bluelim, redlim, N=100, image=None, add_to_image=False,
             *args, **kwargs):
        # is the most efficient method to just add up one component at a time...?
        image = self.objlist[0].draw(wave, throughput_fn, bluelim, redlim, N=N,
                                     image=image, add_to_image=add_to_image,
                                     *args, **kwargs)
        for obj in self.objlist[1:]:
            image = obj.draw(wave, throughput_fn, bluelim, redlim, N=N,
                             image=image, add_to_image=True,
                             *args, **kwargs)

    def applyShear(self, *args, **kwargs):
        for obj in self.objlist:
            obj.applyShear(*args, **kwargs)

    def applyDilation(self, *args, **kwargs):
        for obj in self.objlist:
            obj.applyDilation(*args, **kwargs)

    def applyShift(self, *args, **kwargs):
        for obj in self.objlist:
            obj.applyShift(*args, **kwargs)

    def applyExpansion(self, *args, **kwargs):
        for obj in self.objlist:
            obj.applyExpansion(*args, **kwargs)

    def applyMagnification(self, *args, **kwargs):
        for obj in self.objlist:
            obj.applyMagnification(*args, **kwargs)

    def applyLensing(self, *args, **kwargs):
        for obj in self.objlist:
            obj.applyLensing(*args, **kwargs)

    # Does this work?  About which point is the rotation applied?
    def applyRotation(self, *args, **kwargs):
        for obj in self.objlist:
            obj.applyRotation(*args, **kwargs)

class ChromaticConvolution(ChromaticObject):
    """Convolve ChromaticObjects and/or GSObjects together.  GSObjects are treated as having flat
    spectra.
    """
    def __init__(self, objlist):
        self.objlist = objlist

    def evaluateAtWavelength(self, wave):
        """
        @param wave  Wavelength in nanometers.
        @returns     GSObject for profile at specified wavelength
        """
        return galsim.Convolve([obj.evaluateAtWavelength(wave) for obj in self.objlist])

    def draw(self, throughput_fn, bluelim, redlim, N=100, image=None, add_to_image=False,
             *args, **kwargs):
        # Only make temporary changes to objlist...
        objlist = list(self.objlist)

        # expand any `ChromaticConvolution`s in the object list
        L = len(objlist)
        i = 0
        while i < L:
            if isinstance(objlist[i], ChromaticConvolution):
                # found a ChromaticConvolution object, so unpack its obj.objlist to end of objlist,
                # delete obj from objlist, and update list length `L` and list index `i`.
                L += len(objlist[i].objlist) - 1
                # appending to the end of the objlist means we don't have to recurse in order to
                # expand a hierarchy of `ChromaticSum`s; we just have to keep going until the end of
                # the ever-expanding list.
                # I.e., `*` marks progress through list...
                # {{{A, B}, C}, D}  i = 0, length = 2
                #  *
                # {D, {A, B}, C}    i = 1, length = 3
                #     *
                # {D, C, A, B}      i = 2, length = 4
                #        *
                # {D, C, A, B}      i = 3, length = 4
                #           *
                # Done!
                objlist.extend(objlist[i].objlist)
                del objlist[i]
                i -= 1
            i += 1

        # Now split up any `ChromaticSum`s:
        # This is the tricky part.  Some notation first:
        #     I(f(x,y,lambda)) denotes the integral over wavelength of a chromatic surface brightness
        #         profile f(x,y,lambda).
        #     C(f1, f2) denotes the convolution of surface brightness profiles f1 & f2.
        #     A(f1, f2) denotes the addition of surface brightness profiles f1 & f2.
        #
        # In general, chromatic s.b. profiles can be classified as either separable or inseparable.
        # Write separable profiles as g(x,y) * h(lambda), and leave inseparable profiles as
        # f(x,y,lambda).
        # We will suppress the arguments `x`, `y`, `lambda`, hereforward, but generally an `f` refers
        # to an inseparable profile, a `g` refers to the spatial part of a separable profile, and an
        # `h` refers to the spectral part of a separable profile.
        #
        # Now, analyze a typical scenario, a bulge+disk galaxy model (each of which is separable,
        # e.g., an SED times an exponential profile for the disk, and another SED times a DeV profile
        # for the bulge).  Suppose the PSF is inseparable.  (Chromatic PSF's will generally be
        # inseparable since we usually think of the PSF as being normalized to unit integral, no
        # matter the wavelength we evaluate it at.)  Say there's also an achromatic pixel to
        # convolve with.
        # The formula for this might look like:
        #
        # img = I(C(A(bulge, disk), PSF, pix))
        #     = I(C(A(g1*h1, g2*h2), f3, g4))                # note pix is lambda-independent
        #     = I(A(C(g1*h1, f3, g4)), C(A(g2*h2, f3, g4)))  # distribute the A over the C
        #     = A(I(C(g1*h1, f3, g4)), I(C(g2*h2, f3, g4)))  # distribute the A over the I
        #     = A(C(g1,I(h1*f3),g4), C(g2,I(h2*f3),g4))      # factor lambda-indep terms out of I
        #
        # The result is that the integral is now inside the convolution, meaning we only have to
        # compute two convolutions instead of a convolution for each wavelength at which we evaluate
        # the integrand.  This technique, making an `effective` PSF profile for each of the bulge and
        # disk, is a significant time savings most of the time.
        # In general, we make effective profiles by splitting up `ChromaticSum`s and collecting the
        # inseparable terms on which to do integration first, and then finish with convolution last.

        # Here is the logic to turn I(C(A(...))) into A(C(..., I(...)))
        returnme = False
        for i, obj in enumerate(objlist):
            if isinstance(obj, ChromaticSum):
                # say obj.objlist = [A,B,C], where obj is a ChromaticSum object
                returnme = True
                del objlist[i] # remove the add object from objlist
                tmplist = list(objlist) # collect remaining items to be convolved with each of A,B,C
                tmplist.append(obj.objlist[0]) # add A to this convolve list
                tmpobj = ChromaticConvolution(tmplist) # draw image
                image = tmpobj.draw(throughput_fn, bluelim, redlim, N=N,
                                    image=image, add_to_image=add_to_image,
                                    *args, **kwargs)
                for summand in obj.objlist[1:]: # now do the same for B and C
                    tmplist = list(objlist)
                    tmplist.append(summand)
                    tmpobj = ChromaticConvolution(tmplist)
                    image = tmpobj.draw(throughput_fn, bluelim, redlim, N=N, # add to previous image
                                        image=image, add_to_image=True,
                                        *args, **kwargs)
        if returnme:
            return image

        # If program gets this far, the objects in objlist should be atomic (non-ChromaticSum
        # and non-ChromaticConvolution).
        # Sort these atomic objects into separable and inseparable lists, and collect
        # the spectral parts of the separable profiles.
        sep_profs = []
        insep_profs = []
        sep_SED = []
        for obj in objlist:
            if obj.separable:
                if isinstance(obj, galsim.GSObject):
                    sep_profs.append(obj) # The g(x,y)'s (see above)
                else:
                    sep_profs.append(obj.gsobj) # more g(x,y)'s
                sep_SED.append(obj.SED) # The h(lambda)'s (see above)
            else:
                insep_profs.append(obj) # The f(x,y,lambda)'s (see above)

        # replace array-indexing Riemann sum with function-calling midpoint rule...
        h = (redlim * 1.0 - bluelim) / N
        ws = [bluelim + h * (i+0.5) for i in range(N)]
        # check if there are any inseparable profiles
        if insep_profs == []:
            multiplier = 0.0
            for w in ws:
                term = throughput_fn(w) * h
                for s in sep_SED:
                    term *= s(w)
                multiplier += term
        else:
            # make an effective profile from inseparables and the chromatic part of separables
            # start combining monochromatic profiles into an effective profile
            multiplier = 1.0
            # start with the first wavelength
            mono_prof = galsim.Convolve([insp.evaluateAtWavelength(ws[0]) for insp in insep_profs])
            mono_prof *= throughput_fn(ws[0]) * h
            # multiply it by the appropriate spectral factor
            for s in sep_SED:
                mono_prof *= s(ws[0])
            # start drawing effective profile
            effective_prof_image = mono_prof.draw(*args, **kwargs)
            # now loop over remaining wavelengths and keep adding to effective profile
            for w in ws[1:]:
                mono_prof = galsim.Convolve([insp.evaluateAtWavelength(w) for insp in insep_profs])
                mono_prof *= throughput_fn(w) * h
                for s in sep_SED:
                    mono_prof *= s(w)
                effective_prof_image = mono_prof.draw(image=effective_prof_image, add_to_image=True,
                                                      *args, **kwargs)
            # turn drawn effective profile into a GSObject
            effective_prof = galsim.InterpolatedImage(effective_prof_image)
            # append effective profile to separable profiles (which are all GSObjects)
            sep_profs.append(effective_prof)
        # finally, convolve and draw.
        final_prof = multiplier * galsim.Convolve(sep_profs)
        return final_prof.draw(image=image, add_to_image=add_to_image,
                               *args, **kwargs)


class ChromaticShiftAndDilate(ChromaticObject):
    """Class representing chromatic profiles whose wavelength dependence consists of shifting and
    dilating a fiducial profile.

    By simply shifting and dilating a fiducial PSF, a variety of physical wavelength dependencies can
    be effected.  For instance, differential chromatic refraction is just shifting the PSF center as
    a function of wavelength.  The wavelength-dependence of seeing, and the wavelength-dependence of
    the diffraction limit are dilations.  This class can compactly represent all of these effects.
    See tests/test_chromatic.py for an example.
    """
    def __init__(self, gsobj,
                 shift_fn=None, dilate_fn=None):
        """
        @param gsobj      Fiducial profile (as a GSObject instance) to shift and dilate.
        @param shift_fn   Function that takes wavelength in nanometers and returns a
                          galsim.Position object, or parameters which can be transformed into a
                          galsim.Position object (dx, dy).
        @param dilate_fn  Function that takes wavelength in nanometers and returns a dilation
                          scale factor.
        """
        self.gsobj = gsobj
        if shift_fn is None:
            self.shift_fn = lambda x: (0,0)
        else:
            self.shift_fn = shift_fn
        if dilate_fn is None:
            self.dilate_fn = lambda x: 1.0
        else:
            self.dilate_fn = dilate_fn
        self.separable = False

    def applyShear(self, *args, **kwargs):
        self.gsobj.applyShear(*args, **kwargs)

    def evaluateAtWavelength(self, wave):
        """
        @param wave  Wavelength in nanometers.
        @returns     GSObject for profile at specified wavelength
        """
        PSF = self.gsobj.copy()
        PSF.applyDilation(self.dilate_fn(wave))
        PSF.applyShift(self.shift_fn(wave))
        return PSF

class SED(object):
    """Simple class to represent chromatic objects' spectral energy distributions."""
    def __init__(self, wave=None, photons=None, flambda=None, photon_fn=None,
                 redshift=None, base_wavelength=None, norm=None):
        if photon_fn is not None:
            self.photon_fn = photon_fn
        elif wave is not None and photons is not None:
            self.photon_fn = galsim.LookupTable(wave, photons)
        elif wave is not None and flambda is not None:
            self.photon_fn = galsim.LookupTable(wave,
                                                [wave[i] * flambda[i] for i in range(len(wave))])
        if redshift is None:
            self.redshift = 0.0
        else:
            self.redshift = redshift

        self.norm = 1.0
        if norm is not None and base_wavelength is not None:
            self.normalize(base_wavelength, norm)

    def setRedshift(self, redshift):
        self.redshift = redshift

    def normalize(self, base_wavelength, norm):
        f0 = self.photon_fn(base_wavelength / (1.0 + self.redshift))
        self.norm = norm/f0

    def __call__(self, wave):
        return self.norm * self.photon_fn(wave / (1.0 + self.redshift))
