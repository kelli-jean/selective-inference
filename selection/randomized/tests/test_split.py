from __future__ import print_function
import numpy as np

import regreg.api as rr

from selection.api import randomization, split_glm_group_lasso, pairs_bootstrap_glm, multiple_views, discrete_family, projected_langevin, glm_group_lasso_parametric
from selection.tests.instance import logistic_instance
from selection.tests.decorators import wait_for_return_value, set_seed_for_test, set_sampling_params_iftrue
from selection.randomized.glm import glm_parametric_covariance, glm_nonparametric_bootstrap, restricted_Mest, set_alpha_matrix

from selection.randomized.multiple_views import naive_confidence_intervals


class randomized_loss(rr.smooth_atom):
        def __init__(self,
                    X, y,
                    subsample_size,
                    quadratic=None,
                    initial=None,
                    offset=None):
            rr.smooth_atom.__init__(self,
                                    X.shape[1],
                                    coef=1.,
                                    offset=offset,
                                    quadratic=quadratic,
                                    initial=initial)
            self.X, self.y = X, y
            self.n, self.p = X.shape
            self.subsample = np.random.choice(self.n, size=(subsample_size,), replace=False)
            self.X1, self.y1 = X[self.subsample,:], y[self.subsample]
            self.sub_loss = rr.glm.logistic(self.X1, self.y1)
            self.full_loss = rr.glm.logistic(self.X, self.y)
            self.m = subsample_size
            self.fraction = self.m/float(self.n)

        def smooth_objective(self, beta, mode='both', check_feasibility=False):
            linear = -np.dot(self.X.T, self.y)*self.fraction +np.dot(self.X1.T,self.y1)
            if mode=='grad':
                return self.sub_loss.smooth_objective(beta, 'grad') + linear
            if mode=='func':
                return self.sub_loss.smooth_objective(beta, 'func')+np.inner(linear, beta)
            if mode=='both':
                return self.sub_loss.smooth_objective(beta, 'func')+np.inner(linear, beta), self.sub_loss.smooth_objective(beta, 'grad') + linear



def test_splits(ndraw=10000, burnin=2000, nsim=None, solve_args={'min_its':50, 'tol':1.e-10}): # nsim needed for decorator
    s, n, p = 3, 300, 10

    #randomizer = randomization.laplace((p,), scale=1.)
    X, y, beta, _ = logistic_instance(n=n, p=p, s=s, rho=0, snr=5)

    m = int(n/2)

    nonzero = np.where(beta)[0]
    lam_frac = 1.

    loss = randomized_loss(X, y, m)

    #randomizer = split(loss)
    randomizer = None
    epsilon = 1.

    lam = lam_frac * np.mean(np.fabs(np.dot(X.T, np.random.binomial(1, 1. / 2, (n, 10000)))).max(0))
    W = np.ones(p)*lam
    W[0] = 0 # use at least some unpenalized
    penalty = rr.group_lasso(np.arange(p),
                             weights=dict(zip(np.arange(p), W)), lagrange=1.)

    # first randomization
    M_est1 = split_glm_group_lasso(loss, epsilon, penalty, randomizer)
    # second randomization
    # M_est2 = glm_group_lasso(loss, epsilon, penalty, randomizer)

    # mv = multiple_views([M_est1, M_est2])
    mv = multiple_views([M_est1])
    mv.solve()

    active_union = M_est1.overall #+ M_est2.overall
    nactive = np.sum(active_union)
    print("nactive", nactive)
    if nactive==0:
        return None

    if set(nonzero).issubset(np.nonzero(active_union)[0]):

        active_set = np.nonzero(active_union)[0]

        form_covariances = glm_nonparametric_bootstrap(n, n)
        mv.setup_sampler(form_covariances)

        boot_target, target_observed = pairs_bootstrap_glm(loss.full_loss, active_union)

        # testing the global null
        # constructing the intervals based on the samples of \bar{\beta}_E at the unpenalized MLE as a reference
        all_selected = np.arange(active_set.shape[0])
        target_gn = lambda indices: boot_target(indices)[:nactive]
        target_observed_gn = target_observed[:nactive]

        unpenalized_mle = restricted_Mest(loss.full_loss, M_est1.overall, solve_args=solve_args)

        #alpha_mat = set_alpha_matrix(loss, active_union)
        #target_alpha_gn = alpha_mat

        ## bootstrap
        #target_sampler_gn = mv.setup_bootstrapped_target(target_gn,
        #                                                 target_observed_gn,
        #                                                 n, target_alpha_gn,
        #                                                 reference = unpenalized_mle)

        ## CLT plugin
        target_sampler_gn = mv.setup_target(target_gn,
                                            target_observed_gn, #reference=beta[active_union])
                                            reference = unpenalized_mle)

        target_sample = target_sampler_gn.sample(ndraw=ndraw,
                                                 burnin=burnin)


        LU = target_sampler_gn.confidence_intervals(unpenalized_mle,
                                                    sample=target_sample)

        LU_naive = naive_confidence_intervals(target_sampler_gn, unpenalized_mle)

        pvalues_mle = target_sampler_gn.coefficient_pvalues(unpenalized_mle,
                                                            parameter=target_sampler_gn.reference,
                                                            sample=target_sample)

        pvalues_truth = target_sampler_gn.coefficient_pvalues(unpenalized_mle,
                                                              parameter=beta[active_union],
                                                              sample=target_sample)

        L, U = LU
        true_vec = beta[active_union]

        ncovered = 0
        naive_ncovered = 0

        for j in range(nactive):
            if (L[j] <= true_vec[j]) and (U[j] >= true_vec[j]):
                ncovered += 1
            if (LU_naive[0,j] <= true_vec[j]) and (LU_naive[1,j] >= true_vec[j]):
                naive_ncovered += 1

        return pvalues_mle, pvalues_truth, ncovered, naive_ncovered, nactive




def make_a_plot():
    import matplotlib.pyplot as plt
    from scipy.stats import probplot, uniform
    import statsmodels.api as sm

    np.random.seed(2)

    _pvalues_mle = []
    _pvalues_truth = []
    _nparam = 0
    _ncovered = 0
    _naive_ncovered = 0
    for i in range(200):
        print("iteration", i)
        test = test_splits()
        if test is not None:
            pvalues_mle, pvalues_truth, ncovered, naive_ncovered, nparam = test
            _pvalues_mle.extend(pvalues_mle)
            _pvalues_truth.extend(pvalues_truth)
            _nparam += nparam
            _ncovered += ncovered
            _naive_ncovered += naive_ncovered
            print(np.mean(_pvalues_truth), np.std(_pvalues_truth), np.mean(np.array(_pvalues_truth) < 0.05))

        if _nparam > 0:
            print("coverage", _ncovered/float(_nparam))
            print("naive coverage", _naive_ncovered/float(_nparam))

    print("number of parameters", _nparam,"coverage", _ncovered/float(_nparam))

    fig = plt.figure()
    fig.suptitle('Pivots at the reference (MLE) and the truth')
    plot_pvalues_mle = fig.add_subplot(121)
    plot_pvalues_truth = fig.add_subplot(122)

    ecdf_mle = sm.distributions.ECDF(_pvalues_mle)
    x = np.linspace(min(_pvalues_mle), max(_pvalues_mle))
    y = ecdf_mle(x)
    plot_pvalues_mle.plot(x, y, '-o', lw=2)
    plot_pvalues_mle.plot([0, 1], [0, 1], 'k-', lw=2)
    plot_pvalues_mle.set_title("Pivots at the unpenalized MLE")
    plot_pvalues_mle.set_xlim([0, 1])
    plot_pvalues_mle.set_ylim([0, 1])

    ecdf_truth = sm.distributions.ECDF(_pvalues_truth)
    x = np.linspace(min(_pvalues_truth), max(_pvalues_truth))
    y = ecdf_truth(x)
    plot_pvalues_truth.plot(x, y, '-o', lw=2)
    plot_pvalues_truth.plot([0, 1], [0, 1], 'k-', lw=2)
    plot_pvalues_truth.set_title("Pivots at the truth (by tilting)")
    plot_pvalues_truth.set_xlim([0, 1])
    plot_pvalues_truth.set_ylim([0, 1])

    #while True:
    #    plt.pause(0.05)
    plt.show()


def make_a_plot_individual_coeff():

    np.random.seed(3)
    fig = plt.figure()
    fig.suptitle('Pivots for glm wild bootstrap')

    pvalues = []
    for i in range(100):
        print("iteration", i)
        pvals = test_multiple_views_individual_coeff()
        if pvals is not None:
            pvalues.extend(pvals)
            print("pvalues", pvals)
            print(np.mean(pvalues), np.std(pvalues), np.mean(np.array(pvalues) < 0.05))

    ecdf = sm.distributions.ECDF(pvalues)
    x = np.linspace(min(pvalues), max(pvalues))
    y = ecdf(x)

    plt.title("Logistic")
    fig, ax = plt.subplots()
    ax.plot(x, y, label="Individual coefficients", marker='o', lw=2, markersize=8)
    plt.xlim([0,1])
    plt.ylim([0,1])
    plt.plot([0, 1], [0, 1], 'k-', lw=1)


    legend = ax.legend(loc='upper center', shadow=True)
    frame = legend.get_frame()
    frame.set_facecolor('0.90')
    for label in legend.get_texts():
        label.set_fontsize('large')

    for label in legend.get_lines():
        label.set_linewidth(1.5)  # the legend line width

    plt.savefig("Bootstrap after GLM two views")
    #while True:
    #    plt.pause(0.05)
    plt.show()



if __name__ == "__main__":
    make_a_plot()
    #make_a_plot_individual_coeff()