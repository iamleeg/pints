#
# Scoring functions
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


class ErrorMeasure(object):
    """
    Abstract base class for objects that calculate some scalar measure of
    goodness-of-fit (for a model and a data set), such that a smaller value
    means a better fit.

    ErrorMeasures are callable objects: If ``e`` is an instance of an
    ``ErrorMeasure`` class you can calculate the error by calling ``e(p)``
    where ``p`` is a point in parameter space.
    """
    def __call__(self, x):
        raise NotImplementedError

    def evaluateS1(self, x):
        """
        Evaluates this error measure, and returns the result plus the partial
        derivatives of the result with respect to the parameters.

        The returned data has the shape ``(e, e')`` where ``e`` is a scalar
        value and ``e'`` is a sequence of length ``n_parameters``.

        *This is an optional method that is not always implemented.*
        """
        raise NotImplementedError

    def n_parameters(self):
        """
        Returns the dimension of the parameter space this measure is defined
        over.
        """
        raise NotImplementedError


class ProblemErrorMeasure(ErrorMeasure):
    """
    Abstract base class for ErrorMeasures defined for
    :class:`single<pints.SingleOutputProblem>` or
    :class:`multi-output<pints.MultiOutputProblem>` problems.
    """
    def __init__(self, problem=None):
        super(ProblemErrorMeasure, self).__init__()
        self._problem = problem
        self._times = problem.times()
        self._values = problem.values()
        self._n_outputs = problem.n_outputs()
        self._n_parameters = problem.n_parameters()
        self._n_times = len(self._times)

    def n_parameters(self):
        """ See :meth:`ErrorMeasure.n_parameters()`. """
        return self._n_parameters


class ProbabilityBasedError(ErrorMeasure):
    """
    Changes the sign of a :class:`LogPDF` to use it as an error. Minimising
    this error will maximise the probability.

    Arguments:

    ``log_pdf``
        A :class:`LogPDF` object.

    *Extends:* :class:`ErrorMeasure`
    """
    def __init__(self, log_pdf):
        super(ProbabilityBasedError, self).__init__()
        if not isinstance(log_pdf, pints.LogPDF):
            raise ValueError(
                'Given log_pdf must be an instance of pints.LogPDF.')
        self._log_pdf = log_pdf

    def __call__(self, x):
        return -self._log_pdf(x)

    def evaluateS1(self, x):
        """
        See :meth:`ErrorMeasure.evaluateS1()`.

        *This method only works if the underlying :class:`LogPDF`
        implements the optional method :meth:`LogPDF.evaluateS1()`!*
        """
        y, dy = self._log_pdf.evaluateS1(x)
        return -y, -np.asarray(dy)

    def n_parameters(self):
        """ See :meth:`ErrorMeasure.n_parameters()`. """
        return self._log_pdf.n_parameters()


class SumOfErrors(ErrorMeasure):
    """
    Calculates a sum of :class:`ErrorMeasure` objects, all defined on the same
    parameter space.

    Arguments:

    ``error_measures``
        A sequence of error measures.
    ``weights``
        An optional sequence of (float) weights, exactly one per error measure.
        If no weights are specified all sums will be weighted equally.

    Examples::

        errors = [
            pints.MeanSquaredError(problem1),
            pints.MeanSquaredError(problem2),
        ]

        # Equally weighted
        e1 = pints.SumOfErrors(errors)

        # Differrent weights:
        weights = [
            1.0,
            2.7,
        ]
        e2 = pints.SumOfErrors(errors, weights)

    *Extends:* :class:`ErrorMeasure`
    """
    def __init__(self, error_measures, weights=None):
        super(SumOfErrors, self).__init__()

        # Check input arguments
        if len(error_measures) < 1:
            raise ValueError(
                'SumOfErrors requires at least 1 error measure.')
        if weights is None:
            weights = [1] * len(error_measures)
        elif len(error_measures) != len(weights):
            raise ValueError(
                'Number of weights must match number of errors passed to'
                ' SumOfErrors.')

        # Check error measures
        for i, e in enumerate(error_measures):
            if not isinstance(e, pints.ErrorMeasure):
                raise ValueError(
                    'All error_measures passed to SumOfErrors must be'
                    ' instances of pints.ErrorMeasure (failed on argument '
                    + str(i) + ').')
        self._errors = list(error_measures)

        # Get and check dimension
        i = iter(self._errors)
        self._n_parameters = next(i).n_parameters()
        for e in i:
            if e.n_parameters() != self._n_parameters:
                raise ValueError(
                    'All errors passed to SumOfErrors must have same'
                    ' dimension.')

        # Check weights
        self._weights = [float(w) for w in weights]

    def __call__(self, x):
        i = iter(self._weights)
        total = 0
        for e in self._errors:
            total += e(x) * next(i)
        return total

    def evaluateS1(self, x):
        """
        See :meth:`ErrorMeasure.evaluateS1()`.

        *This method only works if all the underlying :class:`ErrorMeasure`
        objects implement the optional method
        :meth:`ErrorMeasure.evaluateS1()`!*
        """
        i = iter(self._weights)
        total = 0
        dtotal = np.zeros(self._n_parameters)
        for e in self._errors:
            w = next(i)
            a, b = e.evaluateS1(x)
            total += w * a
            dtotal += w * np.asarray(b)
        return total, dtotal

    def n_parameters(self):
        """ See :meth:`ErrorMeasure.n_parameters()`. """
        return self._n_parameters


class MeanSquaredError(ProblemErrorMeasure):
    """
    Calculates the mean square error: ``f = sum( (x[i] - y[i])**2 ) / n``,
    where ``n`` is the product of the number of times in the time series and
    the number of outputs of the problem.

    Arguments:

    ``problem``
        A :class:`pints.SingleOutputProblem` or
        :class:`pints.MultiOutputProblem`.
    ``weights``
        (Optional) A sequence of (float) weights, exactly one per problem
        output. If no weights are specified all sums will be weighted equally.

    *Extends:* :class:`ProblemErrorMeasure`
    """
    def __init__(self, problem, weights=None):
        super(MeanSquaredError, self).__init__(problem)
        self._ninv = 1.0 / np.product(self._values.shape)

        if weights is None:
            weights = [1] * self._n_outputs
        elif self._n_outputs != len(weights):
            raise ValueError(
                'Number of weights must match number of problem outputs.')
        # Check weights
        self._weights = np.asarray([float(w) for w in weights])

    def __call__(self, x):
        return np.sum(((np.sum((self._problem.evaluate(x) - self._values)**2,
                               axis=0) * self._weights) * self._ninv),
                      axis=0)

    def evaluateS1(self, x):
        """ See :meth:`ErrorMeasure.evaluateS1()`. """
        y, dy = self._problem.evaluateS1(x)
        dy = dy.reshape((self._n_times, self._n_outputs, self._n_parameters))
        r = y - self._values
        e = self._ninv * np.sum(np.sum(r**2, axis=0) * self._weights, axis=0)
        de = 2 * self._ninv * np.sum(np.sum((r.T * dy.T), axis=2) *
                                     self._weights, axis=1)
        return e, de


class RootMeanSquaredError(ProblemErrorMeasure):
    """
    Calculates a root mean squared error (RMSE):
    ``f = sqrt( sum( (x[i] - y[i])**2 / n) )``

    Arguments:

    ``problem``
        A :class:`pints.SingleOutputProblem`

    *Extends:* :class:`ProblemErrorMeasure`
    """
    def __init__(self, problem):
        super(RootMeanSquaredError, self).__init__(problem)

        if not isinstance(problem, pints.SingleOutputProblem):
            raise ValueError(
                'This measure is only defined for single output problems.')

        self._ninv = 1.0 / len(self._values)

    def __call__(self, x):
        return np.sqrt(self._ninv * np.sum(
            (self._problem.evaluate(x) - self._values)**2))


class SumOfSquaresError(ProblemErrorMeasure):
    """
    Calculates a sum-of-squares error: ``f = sum( (x[i] - y[i])**2 )``

    Arguments:

    ``problem``
        A :class:`pints.SingleOutputProblem` or
        :class:`pints.MultiOutputProblem`.

     *Extends:* :class:`ErrorMeasure`
    """
    def __init__(self, problem, weights=None):
        super(SumOfSquaresError, self).__init__(problem)

        if weights is None:
            weights = [1] * self._n_outputs
        elif self._n_outputs != len(weights):
            raise ValueError(
                'Number of weights must match number of problem outputs.')
        # Check weights
        self._weights = np.asarray([float(w) for w in weights])

    def __call__(self, x):
        return np.sum((np.sum(((self._problem.evaluate(x) - self._values)**2),
                              axis=0) * self._weights),
                      axis=0)

    def evaluateS1(self, x):
        """ See :meth:`ErrorMeasure.evaluateS1()`. """
        y, dy = self._problem.evaluateS1(x)
        dy = dy.reshape((self._n_times, self._n_outputs, self._n_parameters))
        r = y - self._values
        e = np.sum(np.sum(r**2, axis=0) * self._weights, axis=0)
        de = 2 * np.sum(np.sum((r.T * dy.T), axis=2) * self._weights, axis=1)
        return e, de

