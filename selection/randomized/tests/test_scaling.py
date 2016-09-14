import numpy as np
from scipy.stats import norm as ndist
import statsmodels.api as sm

import regreg.api as rr

from selection.randomized.api import randomization, multiple_views, pairs_bootstrap_glm, bootstrap_cov, glm_group_lasso
from selection.randomized.multiple_views import conditional_targeted_sampler
from selection.distributions.discrete_family import discrete_family
from selection.sampling.langevin import projected_langevin

from selection.randomized.tests import wait_for_return_value, logistic_instance

instance_opts = {'snr':15,
                 's':5,
                 'p':20,
                 'n':200,
                 'rho':0.1}

#@wait_for_return_value

def generate_data(s=5, 
                  n=200, 
                  p=20, 
                  rho=0.1, 
                  snr=15):

    return logistic_instance(n=n, p=p, s=s, rho=rho, snr=snr, scale=False, center=False)

def test_logistic_many_targets(snr=15, 
                               s=5, 
                               n=200, 
                               p=20, 
                               rho=0.1, 
                               burnin=20000, 
                               ndraw=30000, 
                               scale=0.9,
                               frac=0.5): # 0.9 has roughly same screening probability as 50% data splitting, i.e. around 10%

    DEBUG = False
    randomizer = randomization.laplace((p,), scale=scale)
    X, y, beta, _ = generate_data(n=n, p=p, s=s, rho=rho, snr=snr)

    nonzero = np.where(beta)[0]
    lam_frac = 1.

    loss = rr.glm.logistic(X, y)
    epsilon = 1. / np.sqrt(n)

    lam = lam_frac * np.mean(np.fabs(np.dot(X.T, np.random.binomial(1, 1. / 2, (n, 10000)))).max(0))
    W = np.ones(p)*lam
    penalty = rr.group_lasso(np.arange(p),
                             weights=dict(zip(np.arange(p), W)), lagrange=1.)

    M_est = glm_group_lasso(loss, epsilon, penalty, randomizer)

    mv = multiple_views([M_est])
    mv.solve()

    active = M_est.overall
    nactive = active.sum()

    sampler = lambda : np.random.choice(n, size=(n,), replace=True)

    if set(nonzero).issubset(np.nonzero(active)[0]):

        if DEBUG:
            print M_est.initial_soln[:3] * scaling, scaling, 'first nonzero scaled'

        pvalues = []
        active_set = np.nonzero(active)[0]
        inactive_selected = I = [i for i in np.arange(active_set.shape[0]) if active_set[i] not in nonzero]
        active_selected = A = [i for i in np.arange(active_set.shape[0]) if active_set[i] in nonzero]

        if not I:
            return None
        idx = I[0]
        boot_target, target_observed = pairs_bootstrap_glm(loss, active, inactive=M_est.inactive)

        if DEBUG:
            print(boot_target(sampler())[-3:], 'boot target')

        mv.setup_sampler(sampler)

        # null saturated

        def null_target(indices):
            result = boot_target(indices)
            return result[idx]

        null_observed = np.zeros(1)
        null_observed[0] = target_observed[idx]

        target_sampler = mv.setup_target(null_target, null_observed)

        #target_scaling = 5 * np.linalg.svd(target_sampler.target_transform[0][0])[1].max()**2# should have something do with noise scale too

        print target_sampler.crude_lipschitz(), 'crude'

        test_stat = lambda x: x[0]
        pval = target_sampler.hypothesis_test(test_stat, null_observed, burnin=burnin, ndraw=ndraw, stepsize=.5/target_sampler.crude_lipschitz()) # twosided by default
        pvalues.append(pval)

        # true saturated

        idx = A[0]

        def active_target(indices):
            result = boot_target(indices)
            return result[idx]

        active_observed = np.zeros(1)
        active_observed[0] = target_observed[idx]

        sampler = lambda : np.random.choice(n, size=(n,), replace=True)

        target_sampler = mv.setup_target(active_target, active_observed)
        target_scaling = 5 * np.linalg.svd(target_sampler.target_transform[0][0])[1].max()**2# should have something do with noise scale too

        test_stat = lambda x: x[0]
        pval = target_sampler.hypothesis_test(test_stat, active_observed, burnin=burnin, ndraw=ndraw, stepsize=.5/target_sampler.crude_lipschitz()) # twosided by default
        pvalues.append(pval)

        # null selected

        idx = I[0]

        def null_target(indices):
            result = boot_target(indices)
            return np.hstack([result[idx], result[nactive:]])

        null_observed = np.zeros_like(null_target(range(n)))
        null_observed[0] = target_observed[idx]
        null_observed[1:] = target_observed[nactive:] 

        target_sampler = mv.setup_target(null_target, null_observed)#, target_set=[0])
        target_scaling = 5 * np.linalg.svd(target_sampler.target_transform[0][0])[1].max()**2# should have something do with noise scale too

        print target_sampler.crude_lipschitz(), 'crude'

        test_stat = lambda x: x[0]
        pval = target_sampler.hypothesis_test(test_stat, null_observed, burnin=burnin, ndraw=ndraw, stepsize=.5/target_sampler.crude_lipschitz()) # twosided by default
        pvalues.append(pval)

        # true selected

        idx = A[0]

        def active_target(indices):
            result = boot_target(indices)
            return np.hstack([result[idx], result[nactive:]])

        active_observed = np.zeros_like(active_target(range(n)))
        active_observed[0] = target_observed[idx] 
        active_observed[1:] = target_observed[nactive:]

        target_sampler = mv.setup_target(active_target, active_observed)#, target_set=[0])

        test_stat = lambda x: x[0]
        pval = target_sampler.hypothesis_test(test_stat, active_observed, burnin=burnin, ndraw=ndraw, stepsize=.5/target_sampler.crude_lipschitz()) # twosided by default
        pvalues.append(pval)

        # condition on opt variables

        # null saturated

        idx = I[0]

        def null_target(indices):
            result = boot_target(indices)
            return result[idx]

        null_observed = np.zeros(1)
        null_observed[0] = target_observed[idx]

        target_sampler = mv.setup_target(null_target, null_observed, constructor=conditional_targeted_sampler)

        print target_sampler.crude_lipschitz(), 'crude'

        test_stat = lambda x: x[0]
        pval = target_sampler.hypothesis_test(test_stat, null_observed, burnin=burnin, ndraw=ndraw, stepsize=.5/target_sampler.crude_lipschitz()) # twosided by default
        pvalues.append(pval)

        # true saturated

        idx = A[0]

        def active_target(indices):
            result = boot_target(indices)
            return result[idx]

        active_observed = np.zeros(1)
        active_observed[0] = target_observed[idx]

        sampler = lambda : np.random.choice(n, size=(n,), replace=True)

        target_sampler = mv.setup_target(active_target, active_observed, constructor=conditional_targeted_sampler)

        test_stat = lambda x: x[0]
        pval = target_sampler.hypothesis_test(test_stat, active_observed, burnin=burnin, ndraw=ndraw, stepsize=.5/target_sampler.crude_lipschitz()) # twosided by default
        pvalues.append(pval)

        # true selected

        # oracle p-value -- draws a new data set

        X, y, beta, _ = generate_data(n=n, p=p, s=s, rho=rho, snr=snr)
        X_E = X[:,active_set]

        try:
            model = sm.GLM(y, X_E, family=sm.families.Binomial())
            model_results = model.fit()
            pvalues.extend([model_results.pvalues[I[0]], model_results.pvalues[A[0]]])

        except sm.tools.sm_exceptions.PerfectSeparationError:
            pvalues.extend([np.nan, np.nan])

        # data splitting-ish p-value -- draws a new data set of smaller size
        # frac is presumed to be how much data was used in stage 1, we get (1-frac)*n for stage 2
        # frac defaults to 0.5

        Xs, ys, beta, _ = generate_data(n=n, p=p, s=s, rho=rho, snr=snr)
        Xs = Xs[:int((1-frac)*n)]
        ys = ys[:int((1-frac)*n)]
        X_Es = Xs[:,active_set]

        try:
            model = sm.GLM(ys, X_Es, family=sm.families.Binomial())
            model_results = model.fit()
            pvalues.extend([model_results.pvalues[I[0]], model_results.pvalues[A[0]]])

        except sm.tools.sm_exceptions.PerfectSeparationError:
            pvalues.extend([np.nan, np.nan])

        return pvalues

def data_splitting_screening(frac=0.5, snr=10, s=5, n=200, p=20, rho=0.1):

    count = 0
    
    while True:
        count += 1
        X, y, beta, _ = logistic_instance(n=n, p=p, s=s, rho=rho, snr=snr, scale=False, center=False)

        n2 = int(frac * n)
        X = X[:n2]
        y = y[:n2]

        nonzero = np.where(beta)[0]
        lam_frac = 1.

        loss = rr.glm.logistic(X, y)
        epsilon = 1. / np.sqrt(n2)

        lam = lam_frac * np.mean(np.fabs(np.dot(X.T, np.random.binomial(1, 1. / 2, (n2, 10000)))).max(0))
        W = np.ones(p)*lam
        penalty = rr.group_lasso(np.arange(p),
                                 weights=dict(zip(np.arange(p), W)), lagrange=1.)

        problem = rr.simple_problem(loss, penalty)
        quadratic = rr.identity_quadratic(epsilon, 0, 0, 0)

        soln = problem.solve(quadratic)
        active_set = np.nonzero(soln != 0)[0]
        if set(nonzero).issubset(active_set):
            return count

def randomization_screening(scale=1., snr=15, s=5, n=200, p=20, rho=0.1):

    count = 0

    randomizer = randomization.laplace((p,), scale=scale)

    while True:
        count += 1
        X, y, beta, _ = logistic_instance(n=n, p=p, s=s, rho=rho, snr=snr, scale=False, center=False)

        nonzero = np.where(beta)[0]
        lam_frac = 1.

        loss = rr.glm.logistic(X, y)
        epsilon = 1. / np.sqrt(n)

        lam = lam_frac * np.mean(np.fabs(np.dot(X.T, np.random.binomial(1, 1. / 2, (n, 10000)))).max(0))
        W = np.ones(p)*lam
        penalty = rr.group_lasso(np.arange(p),
                                 weights=dict(zip(np.arange(p), W)), lagrange=1.)

        M_est = glm_group_lasso(loss, epsilon, penalty, randomizer)
        M_est.solve()

        active_set = np.nonzero(M_est.initial_soln != 0)[0]
        if set(nonzero).issubset(active_set):
            return count

def main(nsample=2000):
    P = []
    while len(P) < nsample:
        p = test_logistic_many_targets(**instance_opts)
        if p is not None: P.append(p)
        print np.nanmean(P, 0), 'mean', len(P)
        print np.nanstd(P, 0), 'std'
        print np.nanmean(np.array(P) < 0.05, 0), 'rejection'
        