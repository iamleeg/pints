#
# Parameter-space boundaries object
#
# This file is part of PINTS.
#  Copyright (c) 2017-2018, University of Oxford.
#  For licensing information, see the LICENSE file distributed with the PINTS
#  software package.
#
from __future__ import absolute_import, division
from __future__ import print_function, unicode_literals
import pints
import numpy as np


class Boundaries(object):
    """
    Abstract class representing boundaries on a parameter space.
    """
    def check(self, parameters):
        """
        Returns ``True`` if and only if the given point in parameter space is
        within the boundaries.
        """
        raise NotImplementedError

    def n_parameters(self):
        """
        Returns the dimension of the parameter space these boundaries are
        defined on.
        """
        raise NotImplementedError

    def sample(self, n=1):
        """
        Returns ``n`` random samples from within the boundaries, for example to
        use as starting points for an optimisation.

        The returned value is a numpy array with shape ``(n, d)`` where ``n``
        is the requested number of samples, and ``d`` is the dimension of the
        parameter space these boundaries are defined on.

        *Note that implementing :meth:`sample()` is optional, so some boundary
        types may not support it.*
        """
        raise NotImplementedError


class RectangularBoundaries(Boundaries):
    """
    Represents a set of lower and upper boundaries for model parameters.

    A point ``x`` is considered within the boundaries if (and only if)
    ``lower <= x < upper``.

    Arguments:

    ``lower``
        A 1d array of lower boundaries.
    ``upper``
        The corresponding upper boundaries

    *Extends:* :class:`pints.Boundaries`.
    """
    def __init__(self, lower, upper):
        super(RectangularBoundaries, self).__init__()

        # Convert to shape (n,) vectors, copy to ensure they remain unchanged
        self._lower = pints.vector(lower)
        self._upper = pints.vector(upper)

        # Get and check dimension
        self._n_parameters = len(self._lower)
        if len(self._upper) != self._n_parameters:
            raise ValueError('Lower and upper bounds must have same length.')

        # Check dimension is at least 1
        if self._n_parameters < 1:
            raise ValueError('The parameter space must have a dimension > 0')

        # Check if upper > lower
        if not np.all(self._upper > self._lower):
            raise ValueError('Upper bounds must exceed lower bounds.')

    def check(self, parameters):
        """ See :meth:`pints.Boundaries.check()`. """
        if np.any(parameters < self._lower):
            return False
        if np.any(parameters >= self._upper):
            return False
        return True

    def n_parameters(self):
        """ See :meth:`pints.Boundaries.n_parameters()`. """
        return self._n_parameters

    def lower(self):
        """
        Returns the lower boundaries for all parameters (as a read-only NumPy
        array).
        """
        return self._lower

    def range(self):
        """
        Returns the size of the parameter space (i.e. ``upper - lower``).
        """
        return self._upper - self._lower

    def sample(self, n=1):
        """ See :meth:`pints.Boundaries.sample()`. """
        return np.random.uniform(
            self._lower, self._upper, size=(n, self._n_parameters))

    def upper(self):
        """
        Returns the upper boundary for all parameters (as a read-only NumPy
        array).
        """
        return self._upper


class LogPDFBoundaries(Boundaries):
    """
    Uses a :class:`pints.LogPDF` (e.g. a :class:`LogPrior`) as boundaries),
    accepting log-likelihoods above a given threshold as within bounds.

    Arguments:

    ``log_pdf``
        A :class:`pints.LogPdf` to use.
    ``threshold``
        A threshold to determine whether a given log-prior value counts as
        within bounds. Anything _above_ the threshold counts as within bounds.

    For a :class:`pints.LogPrior` based on :class:`pints.Boundaries`, see
    :class:`pints.UniformLogPrior`.

    *Extends:* :class:`pints.Boundaries`.
    """
    def __init__(self, log_pdf, threshold=-float('inf')):
        super(LogPDFBoundaries, self).__init__()

        # Check log pdf
        if not isinstance(log_pdf, pints.LogPDF):
            raise ValueError('First argument must be a pints.LogPDF.')
        self._log_pdf = log_pdf

        # Check threshold
        self._threshold = float(threshold)

        # Check if we can sample
        self._pdf_is_prior = isinstance(log_pdf, pints.LogPrior)

    def check(self, parameters):
        """ See :meth:`pints.Boundaries.check()`. """
        return self._log_pdf(parameters) > self._threshold

    def n_parameters(self):
        """ See :meth:`pints.Boundaries.n_parameters()`. """
        return self._log_pdf.n_parameters()

    def sample(self, n=1):
        """
        See :meth:`pints.Boundaries.sample()`.

        Note: This method is implemented only when the error measure is based
        on a :class:`pints.LogPrior` that supports sampling.
        """
        if not self._pdf_is_prior:
            raise NotImplementedError
        return self._log_pdf.sample(n)

