import numpy as np

import tensorflow as tf
import tensorflow_probability as tfp

import gpflow
from gpflow.utilities import print_summary


def TrainGPPrior(X, y, maxiter=100, verbose=False):
    """"Pretrains a GP prior on the data for `maxiter` iterations.

    Returns the learned model.
    """
    kernel = gpflow.kernels.Matern52()
    gp_prior = gpflow.models.GPR(data=(X, y), kernel=kernel,
                                 mean_function=None)
    optimizer = gpflow.optimizers.Scipy()
    opt_logs = optimizer.minimize(gp_prior.training_loss,
                                  gp_prior.trainable_variables,
                                  options=dict(maxiter=maxiter))
    if verbose:
        print_summary(gp_prior)
    return gp_prior, opt_logs


def ComputeCrossEntropy(config):
    """
    Compute either analytical or a surrogate cross entropy.

    As part of the optimization process of f-ELBO, one has to compute the expected
    score of the prior. Since the expectation is taken w.r.t. the variational
    posterior, we're effectively computing a cross entropy term.

    Current support:
        - Exact \nabla log_prior estimation via analytical priors
        (Gaussian Processes in this case).
        - Approximation of \nabla log_prior via applying SSGE to a set of
        particles (i.e. samples) which represent the prior as an empirical
        measure.
    """
    method = config['method']
    cross_entropy = None

    if 'gp' in method:
        x, y = config['x'], config['y']
        kernel_function = config['kernel_function']
        kernel_matrix = kernel_function(tf.cast(x, tf.float64))
        
        # Perturb eigenvalues of the kernel matrix to ensure Cholesky
        # decomposition succeeds.
        kernel_matrix += 0.01 * tf.eye(tf.shape(x)[0], dtype=tf.float64)

        # Build the GP as a simple MVN with the given `kernel_matrix`.
        prior = tfp.distributions.MultivariateNormalFullCovariance(
          tf.zeros(x.shape[0], dtype=tf.float64), kernel_matrix)

        # Compute analytic crossentropy.
        cross_entropy = -tf.reduce_mean(
          prior.log_prob(tf.cast(y, tf.float64)))
          
    elif 'ssge' in method:
        y = config['y']
        n_particles = config['n_particles']
        prior_particles = config['prior_particles']
        estimator = config['estimator']

        # Use SSGE to evaluate the gradient of the log prior
        # on the predictions.
        cross_entropy_gradients = estimator.compute_gradients(
              np.tile(prior_particles, (n_particles, 1))[..., None],
              y)

        cross_entropy = -tf.reduce_mean(
              tf.reduce_sum(
                  tf.stop_gradient(cross_entropy_gradients)
                  * tf.cast(y, tf.float64), -1))

    return cross_entropy

