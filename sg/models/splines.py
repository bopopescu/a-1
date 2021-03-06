import collections

import matplotlib.pyplot as plt
import scipy
import numpy as np
from scipy import interpolate
import pandas as pd

def binomialcoefficient(n, k):
    """Binomial coefficient from Wikipedia. Probably slow, but will do when n
    is small."""
    from math import factorial
    return factorial(n) // (factorial(k) * factorial(n - k))

def bernsteinbasis(i, n):
    """Returns a closure with the Bernstein polynomial i of degree n."""
    bc = binomialcoefficient(n, i)
    n_less_i = n - i
    def bernie(t):
        return bc * t**i * (1 - t)**n_less_i
    return bernie

def bezierfunc(points):
    """Given the control points 'points', returns a closure that will calculate
    the bezier curve for these points when fed an argument t in [0, 1]."""
    n = len(points) - 1
    def c(t):
        x_t = 0
        y_t = 0
        for i in range(n+1):
            basis = bernsteinbasis(i, n)(t)
            x_t += points[i][0] * basis
            y_t += points[i][1] * basis
        return x_t, y_t
    return c

def _lte_cmp(ki, t, ki1, last):
    """Checks whether t is in the closed interval [ki, ki1] (where ki and ki1
    represent knots i and i+1). This is the formula used in 'Bezier and Splines
    in Image Processing and Machine Vision' by Sambhunath Biswas and Brian
    C. Lovell. However, it will create discontinuities in the basis functions,
    since two functions will be counted in internal knots. Not a good idea."""
    return ki <= t and t <= ki1
def _lt_cmp(ki, t, ki1, last):
    """Checks whether t is in the half-open interval [ki, ki1) (where ki and
    ki1 represent knots i and i+1). This is the 'normal' formula, as used on
    Wikipedia, Wolfram Mathworld, and Dr. C.-K. Shene's notes to the course
    'CS3621 Introduction to Computing with Geometry Notes', to name a
    few. However, when using the cox-deboor recursion to create B-splines, the
    curve will always end at 0 when t=1, since N_i0 returns 0 when t==t_n. Knot
    multiplicity will not make the curve end at the last control
    point. However, it can be achieved by creating multiplicity at the second
    to last knot (e.g. setting knots[-1] += 1)."""
    return ki <= t and t < ki1
def _fix_cmp(ki, t, ki1, last):
    """A pragmatic combination of _lte_cmp and _lt_cmp, where the very last
    interval is closed, but the other intervals are half-open."""
    return ki <= t and (t < ki1 or t == ki1 == last)
_coxdeboor_cmp = _fix_cmp

def _coxdeboor_recursion(knots, i, p):
    """Returns a B-spline basis function closure for control knot i and degree
    p given the list of knots. The closure calculates the basis functions using
    the Cox-de Boor recursion algorithm."""
    if i < 0:
        raise ValueError("Negative knot index: %f, must be >= 0." % i)
    if not i + p + 1 < len(knots):
        raise ValueError("Knot index (i=%d)/degree (p=%d) too large! "
                         "i + p + 1 < len(knots) = %d is not satisfied." % \
                         (i, p, len(knots)))
    def N_i0(t):
        if _coxdeboor_cmp(knots[i], t, knots[i+1], knots[-1]):
            return 1
        else:
            return 0
    def N_ip(t):
        thisrange = (knots[i+p] - knots[i])
        nextrange = (knots[i+p+1] - knots[i+1])
        term1 = 0
        if thisrange > 0:
            term1 = (t - knots[i]) / thisrange * \
                _coxdeboor_recursion(knots, i, p-1)(t)
        term2 = 0
        if nextrange > 0:
            term2 = (knots[i+p+1] - t) / nextrange * \
            _coxdeboor_recursion(knots, i+1, p-1)(t)
        return term1 + term2
    if p == 0:
        return N_i0
    else:
        return N_ip

def bsplinebasis(knots, i, p):
    """Returns a B-spline basis function closure for knot i and degree p given
    the list of knots."""
    return _coxdeboor_recursion(knots, i, p)

def bsplinebasis_deriv(knots, i, p, n):
    """Calculate the nth derivative function for the i'th B-spline basis
    function of degree p. Returns a function closure for calculating the value
    of the derivative at time t."""
    def deriv(t):
        if n == 1:
            basis1 = bsplinebasis(knots, i, p-1)
            basis2 = bsplinebasis(knots, i+1, p-1)
        else:
            basis1 = bsplinebasis_deriv(knots, i, p-1, n-1)
            basis2 = bsplinebasis_deriv(knots, i+1, p-1, n-1)
        thisrange = (knots[i+p] - knots[i])
        nextrange = (knots[i+p+1] - knots[i+1])
        term1 = 0
        if thisrange > 0:
            term1 = p / thisrange * basis1(t)
        term2 = 0
        if nextrange > 0:
            term2 = p / nextrange * basis2(t)
        return term1 - term2
    return deriv
    
def get_lengths_and_degree(knots, points):
    """Given knots and control points, returns m, n and degree."""
    m = len(knots) - 1
    n = len(points) - 1
    degree = m - n - 1
    try:
        dim = len(points[0])
    except TypeError:
        dim = 1
    return (m, n, degree, dim)

def get_uniform_knots(num_knots, degree, knotrange=(0, 1)):
    """Given the desired number of knots and the degree, return a list of
    uniformly spaced knots in knotrange (inclusive) with multiplicity at the
    end such that the curve will start and end at the first and last control
    point, respectively."""
    multiplicity = degree + 1
    internal = num_knots - 2 * multiplicity
    if internal < 0:
        raise RuntimeError("Cannot create %d knots with degree %d and "
                           "multiplicity, need at least %d knots." %
                           (num_knots, degree, 2 * multiplicity))
    knots = np.linspace(knotrange[0], knotrange[1], internal + 2)
    knots = np.insert(knots, np.zeros(degree),
                      np.ones(degree) * knotrange[0])
    knots = np.append(knots, np.ones(degree) * knotrange[1])
    return knots
    
def get_uniform_knots_from_points(points, degree,
                                  knotrange=(0, 1)):
    """Given a list of control points and the desired degree, return a list of
    uniformly spaced knots with multiplicity at the end such that the curve
    will start and end at the first and last control point, respectively."""
    num_knots = len(points) + degree + 1
    return get_uniform_knots(num_knots, degree, knotrange)

def bsplinefunc(knots, points):
    """Given knots and control points, returns a closure that will calculate
    the B-spline curve or surface using Cox-de Boor recursion when fed an
    argument t in [0, 1]."""
    m, n, degree, dim = get_lengths_and_degree(knots, points)
    try:
        dummy = points[0][0]
        pts = points
    except IndexError:
        pts = [[i] for i in points]
    def c(t):
        pt = np.zeros(dim)
        for i in range(n+1):
            basis = bsplinebasis(knots, i, degree)(t)
            pt += map(lambda x: x * basis, pts[i])
        return pt
    return c

class SplineEnvelope(object):
    def __init__(self, series, period):
        """Set up the envelope around 'series', using a spline that interpolates
        the max and min values with each 'period'. 'period' can be any
        code accepted as a frequency by Pandas.Grouper, such as 'D',
        'W', 'Q', 'A': daily, weekly, quarterly, yearly
        ("Annual"). 'series' is assumed to be a Pandas timeseries
        (i.e. a Series with datetime index).

        """
        self._series = series
        grouped = series.groupby(pd.Grouper(freq=period)) # Grouper requires Pandas >= 0.14.0
        self._xall = self._to_xcoords(self._series)
        self._lower_interp, self._lower_points = self._find_envelope(grouped, 'lower')
        self._upper_interp, self._upper_points = self._find_envelope(grouped, 'upper')

    def _adjust_envelope(self, points, cmp_op):
        """Create interpolating envelope based on boundary points 'points'."""
        # """Based on the initial boundary points 'points', adjust the envelope
        # such that it is below (above) every point in self._series,
        # according to comparison operation 'cmp_op', and by more than a
        # numerical tolerance.

        # """
        points_ext = self._extend(points)
        x = self._to_xcoords(points_ext)
        interpolator = interpolate.InterpolatedUnivariateSpline(x, points_ext.values)
        envelope = interpolator(self._xall)
        outside = cmp_op(envelope, self._series)
        untolerated = np.logical_not(np.isclose(envelope, self._series))
        misses = np.where(np.logical_and(outside, untolerated))[0]
        # This part, which makes sure every data point is inside the
        # envelope, didn't work too well. It tends to include two or
        # more adjacent points, which in turn makes for a large
        # derivative and a nasty-looking envelope.
        # if len(misses) > 0:
        #     print "Including these misses in interpolation points:", misses
        #     points = points.combine_first(self._series[misses])
        #     return self._adjust_envelope(points, cmp_op)
        return interpolator, points_ext
        
    def _find_envelope(self, grouped, which):
        """Find the upper or lower envelope of the series after grouping."""
        if which == 'lower':
            trans = lambda x : x == x.min()
            cmp_op = np.greater
        else:
            trans = lambda x : x == x.max()
            cmp_op = np.less
        points = self._series[np.where(grouped.transform(trans))[0]]
        return self._adjust_envelope(points, cmp_op)

    def _extend(self, points):
        """Return a new series where the endpoints have been extended to include
        the start and end times of the original timeseries. 

        """
        # Make sure not to include an endpoint if it is already in the
        # series: duplicates will break the spline interpolation
        # routine.
        subseries = []
        if points.index[0] != self._series.first_valid_index():
            subseries.append(pd.Series(points.iloc[0], index=[self._series.first_valid_index()]))
        subseries.append(points)
        if points.index[-1] != self._series.last_valid_index():
            subseries.append(pd.Series(points.iloc[-1], index=[self._series.last_valid_index()]))
        return pd.concat(subseries)
    
    def _to_xcoords(self, points):
        """Return array containing x coordinates for 'points',
        relative to the start of 'self._series'.

        Assumes temporal resolution of series is << seconds.

        """
        x0 = self._series.first_valid_index()
        return points.index.map(lambda x : (x - x0).total_seconds())

    def lower_envelope(self, points):
        """Evaluate the lower envelope spline for the series 'points'."""
        return pd.Series(self._lower_interp(self._to_xcoords(points)),
                         index=points.index)

    def upper_envelope(self, points):
        """Evaluate the upper envelope spline for the series 'points'."""
        return pd.Series(self._upper_interp(self._to_xcoords(points)),
                         index=points.index)

    def get_interpolation_points(self):
        """Return the points used in interpolation"""
        return self._lower_points, self._upper_points

    def flip(self, series=None):
        """Return 'series', or self._series if 'series' is None, flipped
        relative to the envelope.

        """
        if series is None:
            series = self._series
        lower = self.lower_envelope(series)
        upper = self.upper_envelope(series)
        return upper - (series - lower)

def create_and_plot_envelope(series, period):
    import matplotlib.pyplot as plt
    splenv = SplineEnvelope(series, period)
    if period == 'A':
        upsampled = series
    else:
        upsampled = series.resample('Min')
    lower = splenv.lower_envelope(upsampled)
    upper = splenv.upper_envelope(upsampled)
    flipped = splenv.flip(series)
    points = splenv.get_interpolation_points()
    axis_sub = series.plot(style='b')
    axis_sub.lines[-1].set_label('Original data')
    axis_sub = lower.plot(style='c')
    axis_sub.lines[-1].set_label('Envelope')
    axis_sub = upper.plot(style='c')
    axis_sub.lines[-1].set_label('_nolegend_')
    axis_sub = points[0].plot(style='kx')
    axis_sub.lines[-1].set_label('Interpolation points')
    axis_sub = points[1].plot(style='kx')
    axis_sub.lines[-1].set_label('_nolegend_')
    axis_sub = flipped.plot(style='r--')
    axis_sub.lines[-1].set_label('Inverted timeseries')
    plt.legend()
    return splenv
    
def bsplinederivfunc(knots, points, nderiv):
    """Given knots and control points, returns a closure that will calculate
    the nderiv'th derivative of the B-spline curve or surface using Cox-de Boor
    recursion when fed an argument t in [0, 1]."""
    m, n, degree, dim = get_lengths_and_degree(knots, points)
    def c(t):
        pt = np.zeros(dim)
        for i in range(n+1):
            basis = bsplinebasis_deriv(knots, i, degree, nderiv)(t)
            pt += map(lambda x: x * basis, points[i])
        return pt
    return c

def calc_multiplicity(knots):
    """Given a list of knots, returns two lists: one giving the unique knots,
    and the other giving the multiplicity of each of these knots."""
    m = collections.defaultdict(int)
    for knot in knots:
        m[knot] += 1
    uniq, mult = zip(*sorted(m.items()))
    return list(uniq), list(mult)


class SplinesPlotter():
    def __init__(self):
        self.points = [(1, 2), (2, 4), (4, 1.5), (7, 2), (6, 3.5)]
        self.t = np.linspace(0, 1, 100)
        
    def plot_bernstein_bases(self):
        """Plots the Bernstein basis functions, for visual validation against
        Wolfram Mathworld."""
        for n in range(6):
            for i in range(n+1):
                bf = bernsteinbasis(i, n)
                y = bf(self.t)
                plt.plot(self.t, y, label="Poly %d, degree %d" % (i, n))

    def show_splines(self, x, y):
        p_x, p_y = zip(*self.points)
        plt.plot(p_x, p_y, 'x')
        plt.plot(x, y)
        
    def plot_bezier(self):
        c = bezierfunc(self.points)
        x, y = c(self.t)
        self.show_splines(x, y)

    def plot_bsplines(self):
        n = len(self.points) - 1
        degree = 3
        m = n + degree + 1
        knots = np.linspace(0, 1, m - (2*degree - 1))
        knots = np.insert(knots, np.zeros(degree), 0)
        knots = np.append(knots, np.ones(degree))
        knots[4] = knots[5] = knots[6]
        c = bsplinefunc(knots, self.points)
        xy = map(c, self.t)
        x, y = zip(*xy)
        self.show_splines(x, y)

def _plot_splines():
    sp = SplinesPlotter()
    plt.figure()
    plt.title("Bernstein polynomials")
    sp.plot_bernstein_bases()
    plt.figure()
    plt.title("Bezier curves")
    sp.plot_bezier()
    plt.figure()
    plt.title("B-spline curves")
    sp.plot_bsplines()
    plt.show()

def plot_bases(knot_idx, degree, plot_max=False):
    """For a list of knots and degrees, both with n elements, plot the basis
    function starting at knot[i] with degree[i]. The necessary number of
    uniformly spaced knots will be generated automatically. If plot_max is
    True, a horizontal line indicating the max value of each basis will also be
    plotted."""
    if len(knot_idx) != len(degree):
        raise ValueError("knot_idx and degree must be lists " \
                         "of the same length.")
    knots = np.linspace(0, 1, max(np.add(knot_idx, degree)) + 2)
    t = np.linspace(0, 1, 1000)
    for i in range(len(knot_idx)):
        p = degree[i]
        basis = bsplinebasis(knots, knot_idx[i], p)
        y = map(basis, t)
        plt.plot(t, y, label='degree %d' % p, hold=True)
        if plot_max:
            plt.plot(t, np.ones(len(t)) * max(y), hold=True)
    plt.yticks([0, 0.25, 0.5, 0.75, 1])
    plt.legend(loc=2)

def plot_basis_derivatives(knot_idx, degree, t):
    """For a list of knot indices and degrees, both with n elements, plot the
    derivative at time t of the basis function starting at knots[i] with
    degree[i]. knots will be automatically generated."""
    if len(knot_idx) != len(degree) or len(knot_idx) != len(t):
        raise ValueError("knot_idx, degree and t must be lists " \
                         "of the same length.")
    knots = np.linspace(0, 1, max(np.add(knot_idx, degree)) + 2)
    x = np.linspace(0, 1, 1000)
    for i in range(len(knot_idx)):
        n = knot_idx[i]
        p = degree[i]
        t_ = t[i]
        slope = bsplinebasis_deriv(knots, n, p, 1)(t_)
        offset = bsplinebasis(knots, n, p)(t_)
        y = map(lambda a: (a - t_) * slope + offset, x)
        plt.plot(x, y, label='deriv at t=%.2f' % t_, hold=True)
    plt.legend(loc=2)

if __name__ == "__main__":
    from unittest import main
    main(module="test_" + __file__[:-3])
    
