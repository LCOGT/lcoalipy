"""
    FITS Align - Align and reproject FITS files from Las Cumbres Observatory
    Copyright (C) 2018 Edward Gomez

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from __future__ import absolute_import
from . import star
from . import quad
import os
import numpy as np
from astropy.io import fits

import logging

logger = logging.getLogger(__name__)

class ImgCat:
    """
    Represent an individual image and its associated catalog, starlist, quads etc.
    """

    def __init__(self, filepath, hdu=0, cat=None):
        """

        :param filepath: Path to the FITS file, or alternatively just a string to identify the image.
        :type filepath: string

        :param cat: Catalog generated by SExtractor (if available -- if not, we'll make our own)
        :type cat: asciidata catalog

        :param hdu: The hdu containing the science data from which I should build the catalog. 0 is primary. If multihdu, 1 is usually science.

        """
        self.filepath = filepath

        (imgdir, filename) = os.path.split(filepath)
        (common, ext) = os.path.splitext(filename)
        self.name = common

        self.hdu = hdu
        self.cat = cat
        self.starlist = []
        self.mindist = 0.0
        self.xlim = (0.0, 0.0) # Will be set using the catalog -- no need for the FITS image.
        self.ylim = (0.0, 0.0)

        self.quadlist = []
        self.quadlevel = 0 # encodes what kind of quads have already been computed


    def __str__(self):
        return "%20s: approx %4i x %4i, %4i stars, %4i quads, quadlevel %i" % (os.path.basename(self.filepath),
            self.xlim[1] - self.xlim[0], self.ylim[1] - self.ylim[0],
            len(self.starlist), len(self.quadlist), self.quadlevel)

    def makecat(self, rerun=True, keepcat=False, verbose=True):
        hdu = fits.open(self.filepath)
        self.cat = hdu[2].data


    def makestarlist(self, skipsaturated=False, n=200, verbose=True):
        # if self.cat:
        if skipsaturated:
            maxflag = 3
        else:
            maxflag = 7
        self.starlist = star.sortstarlistbyflux(star.readsexcat(mycat=self.cat))[:n]
        (xmin, xmax, ymin, ymax) = star.area(self.starlist, border=0.01)
        self.xlim = (xmin, xmax)
        self.ylim = (ymin, ymax)

        # Given this starlists, what is a good minimal distance for stars in quads ?
        self.mindist = min(min(xmax - xmin, ymax - ymin) / 10.0, 30.0)
        #
        # else:
        #     raise RuntimeError("No cat : call makecat first !")


    def makemorequads(self, verbose=True):
        """
        We add more quads, following the quadlevel.
        """
        #if not add:
        #    self.quadlist = []
        logger.debug("Making more quads, from quadlevel %i ..." % self.quadlevel)
        if self.quadlevel == 0:
            self.quadlist.extend(quad.makequads1(self.starlist, n=7, d=self.mindist, verbose=verbose))
        elif self.quadlevel == 1:
            self.quadlist.extend(quad.makequads2(self.starlist, f=3, n=5, d=self.mindist, verbose=verbose))
        elif self.quadlevel == 2:
            self.quadlist.extend(quad.makequads2(self.starlist, f=6, n=5, d=self.mindist, verbose=verbose))
        elif self.quadlevel == 3:
            self.quadlist.extend(quad.makequads2(self.starlist, f=12, n=5, d=self.mindist, verbose=verbose))
        elif self.quadlevel == 4:
            self.quadlist.extend(quad.makequads2(self.starlist, f=10, n=6, s=3, d=self.mindist, verbose=verbose))

        else:
            return False

        self.quadlist = quad.removeduplicates(self.quadlist, verbose=verbose)
        self.quadlevel += 1
        return True


    def showstars(self, verbose=True):
        """
        Uses f2n to write a png image with circled stars.
        """
        try:
            import f2n
        except ImportError:
            logger.error("Couldn't import f2n -- install it !")
            return

        logger.debug("Writing png ...")
        myimage = f2n.fromfits(self.filepath, verbose=False)
        #myimage.rebin(int(myimage.xb/1000.0))
        myimage.setzscale("auto", "auto")
        myimage.makepilimage("log", negative = False)
        #myimage.upsample()
        myimage.drawstarlist(self.starlist, r=8, autocolour="flux")
        myimage.writetitle(os.path.basename(self.filepath))
        #myimage.writeinfo(["This is a demo", "of some possibilities", "of f2n.py"], colour=(255,100,0))
        if not os.path.isdir("alipy_visu"):
                os.makedirs("alipy_visu")
        myimage.tonet(os.path.join("alipy_visu", self.name + "_stars.png"))



    def showquads(self, show=False, flux=True, verbose=True):
        """
        Uses matplotlib to write/show the quads.
        """
        logger.debug("Plotting quads ...")

        import matplotlib.pyplot as plt
        #import matplotlib.patches
        #import matplotlib.collections

        plt.figure(figsize=(10, 10))

        if len(self.starlist) >= 2:
            a = star.listtoarray(self.starlist, full=True)
            if flux:
                f = np.log10(a[:,2])
                fmax = np.max(f)
                fmin = np.min(f)
                f = 1.0 + 8.0 * (f-fmin)/(fmax-fmin)
                plt.scatter(a[:,0], a[:,1], s=f, color="black")
            else:
                plt.plot(a[:,0], a[:,1], marker=",", ls="none", color="black")

        if len(self.quadlist) != 0:
            for quad in self.quadlist:
                polycorners = star.listtoarray(quad.stars)
                polycorners = ccworder(polycorners)
                plt.fill(polycorners[:,0], polycorners[:,1], alpha=0.03, ec="none")

        plt.xlim(self.xlim)
        plt.ylim(self.ylim)
        plt.title(str(self))
        plt.xlabel("x")
        plt.ylabel("y")
        ax = plt.gca()
        ax.set_aspect('equal', 'datalim')

        if show:
            plt.show()
        else:
            if not os.path.isdir("alipy_visu"):
                os.makedirs("alipy_visu")
            plt.savefig(os.path.join("alipy_visu", self.name + "_quads.png"))





def ccworder(a):
    """
    Sorting a coordinate array CCW to plot polygons ...
    """
    ac = a - np.mean(a, 0)
    indices = np.argsort(np.arctan2(ac[:, 1], ac[:, 0]))
    return a[indices]
