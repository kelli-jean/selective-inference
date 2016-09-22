import numpy as np
from initial_soln import instance, selection
from scipy.optimize import minimize

#####for debugging currently; need to change this part
n=100
p=20
s=5
snr=5
data_instance = instance(n, p, s, snr)
X, y, true_beta, nonzero, sigma = data_instance.generate_response()

random_Z = np.random.standard_normal(p)
lam, epsilon, active, betaE, cube, initial_soln = selection(X,y, random_Z)

#########################################################
#####defining a class for computing selection probability
class selection_probability(object):

    #defining class variables
    def __init__(self, V,B_E,gamma_E,sigma,tau,lam):

        (self.V, self.B_E,self.gamma_E,self.sigma,self.tau,self.lam) = (V,B_E,gamma_E,sigma,tau,lam)
        self.sigma_sq = self.sigma ** 2
        self.tau_sq = self.tau ** 2
        self.signs = np.sign(self.betaE)
        self.n, self.p = V.shape
        self.nactive = betaE.shape[0]
        self.ninactive=self.p-self.nactive
        #be careful here to permute the active columns
        self.V_E = self.V[:,:self.nactive]
        self.V_E_comp=self.V[:,self.nactive:]
        self.C_E=self.B_E[:self.nactive,:self.nactive]
        self.D_E=self.B_E.T[:self.nactive,self.nactive:]

    def optimization(self,param):

        # defining barrier function on betaE
        def barrier_sel(z):
            # A_1 beta_E\leq 0
            A_1 = np.zeros((self.nactive, self.nactive))
            A_1 = -np.diag(self.signs)
            if all(- np.dot(A_1, z) >= np.power(10, -9)):
                return np.sum(np.log(1 + np.true_divide(1, - np.dot(A_1, z))))
            return self.nactive * np.log(1 + 10 ** 9)

        # defining barrier function on u_{-E}
        def barrier_subgrad(z):

            # A_2 beta_E\leq b
            A_2 = np.zeros(((2 * self.ninactive), (self.ninactive)))
            A_2[:self.ninactive, :] = np.identity(self.ninactive)
            A_2[self.ninactive:, :] = -np.identity(self.ninactive)
            b = np.ones((2 * self.ninactive))
            if all(b - np.dot(A_2, z) >= np.power(10, -9)):
                return np.sum(np.log(1 + np.true_divide(1, b - np.dot(A_2, z))))
            return b.shape[0] * np.log(1 + 10 ** 9)

        Sigma=np.true_divide(np.identity((self.n,self.n)),self.sigma_sq)+np.true_divide(np.dot(self.V,self.V.T),
                                                                                        self.tau_sq)
        Sigma_inv=np.linalg.inv(Sigma)
        Sigma_inter=np.identity(self.p)-np.true_divide(np.dot(np.dot(self.V.T,Sigma_inv),self.V),self.tau_sq ** 2)
        def mean(param):
            return np.dot(-self.V[:,:self.nactive],param)

        mat_inter=np.dot(np.true_divide(np.dot(self.B_E.T, self.V.T), self.tau_sq), Sigma_inv)
        vec_inter=np.true_divide(np.dot(self.B_E.T,self.gamma_E),self.tau_sq)
        mu_tilde=-np.dot(mat_inter,np.true_divide(mean(param),self.sigma_sq)-np.true_divide(np.dot(self.V,self.gamma_E),
                                                                                    self.tau_sq))-vec_inter
        Sigma_tilde=np.dot(np.dot(self.B_E.T,Sigma_inter),self.B_E)

        def objective_noise(z):

            z_1=z[1:self.nactive]
            z_2=z[self.nactive:]
            return np.true_divide(np.dot(np.dot(z.T,Sigma_tilde),z),2)+ barrier_sel(z_1)\
                   +barrier_subgrad(z_2)-np.dot(z.T,mu_tilde)

        def objective_subgrad(z_3,z_1,z_2):

            mu_z3=np.true_divide(np.dot(self.V_E_comp.T,z_1)-np.dot(self.D_E.T,z_2),self.tau_sq)
            return -np.dot(z_3.T,mu_z3)+np.true_divide(np.inner(z_3.T,z_3),self.tau_sq)+barrier_subgrad(z_3)

        def value_subgrad(z_1,z_2):
            initial_subgrad=np.random.uniform(-1, 1, self.ninactive)
            res = minimize(objective_subgrad, x0=initial_subgrad,args=(z_1,z_2))
            return -res.fun

        def objective_data_noise(z):
            z_1=z[:self.n]
            z_2=z[self.n:]
            Sigma_z2=np.true_divide(np.dot(self.C_E,self.C_E)+np.dot(self.D_E,self.D_E.T),2*self.tau_sq)
            mu_z2=-self.lam*np.dot(self.C_E,self.signs)-np.dot((np.true_divide(np.dot(self.C_E,self.V_E.T),self.tau_sq)\
                  +np.true_divide(self.D_E,self.V_E.T)),z_1)
            mu_z1=np.true_divide(mean(param),self.sigma_sq) - np.true_divide(np.dot(self.V, self.gamma_E),self.tau_sq)
            return -np.dot(z_1.T,mu_z1)+np.true_divide(np.dot(np.dot(z_1.T,Sigma),z_1),2)-value_subgrad(z_1,z_2)-\
                   np.dot(z_2.T,mu_z2)+np.dot(np.dot(z_2.T,Sigma_z2),z_2)

        if self.p< self.n+self.nactive:
            initial_noise = np.zeros(self.p)
            initial_noise[:self.nactive] = self.betaE
            initial_noise[self.nactive:] = np.random.uniform(-1, 1, self.ninactive)
            res=minimize(objective_noise,x0=initial_noise)
            return -res.fun
        else:
            initial_data_noise=np.zeros(self.p+self.n)
            initial_data_noise[self.n:]=self.betaE
            res=minimize(objective_data_noise,x0=initial_data_noise)
            return -res.fun














































