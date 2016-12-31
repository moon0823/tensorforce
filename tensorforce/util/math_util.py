# Copyright 2016 reinforce.io. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""
Contains various mathematical utility functions used for policy gradient methods.
"""

import numpy as np
import tensorflow as tf
import scipy.signal


def zero_mean_unit_variance(data):
    """
    Transform array to zero mean unit variance.
    :param data:
    :return:
    """
    data -= data.mean()
    data /= (data.std() + 1e-8)

    return data

def discount(rewards, gamma):
    return scipy.signal.lfilter([1], [1, -gamma], rewards[::-1], axis=0)[::-1]


def get_log_prob_gaussian(action_dist_mean, log_std, actions):
    """

    :param action_dist_mean: Mean of action distribution
    :param log_std: Log standard deviations
    :param actions: Actions for which to compute log probabilities.
    :return:
    """
    probability = -tf.square(actions - action_dist_mean) / (2 * tf.exp(2 * log_std)) \
                  - 0.5 * tf.log(tf.constant(2 * np.pi)) - log_std

    # Sum logs
    return tf.reduce_sum(probability, 1)


def get_kl_divergence_gaussian(mean_a, log_std_a, mean_b, log_std_b):
    """
    Kullback-Leibler divergence between Gaussians a and b.

    :param mean_a: Mean of first Gaussian
    :param log_std_a: Log std of first Gaussian
    :param mean_b: Mean of second Gaussian
    :param log_std_b: Log std of second Gaussian
    :return: KL-Divergence between a and b
    """
    exp_std_a = tf.exp(2 * log_std_a)
    exp_std_b = tf.exp(2 * log_std_b)

    return tf.reduce_sum(log_std_b - log_std_a
                         + (exp_std_a + tf.square(mean_a - mean_b)) / (2 * exp_std_b) - 0.5)


def get_fixed_kl_divergence_gaussian(mean, log_std):
    """
    KL divergence with first param fixed. Used in TRPO update.

    :param mean:
    :param log_std:
    :return:
    """
    mean_a, log_std_a = map(tf.stop_gradient, [mean, log_std])
    mean_b, log_std_b = mean, log_std

    return get_kl_divergence_gaussian(mean_a, log_std_a, mean_b, log_std_b)


def get_entropy_gaussian(log_std):
    """
    Gaussian entropy; n.b. does not depend on mean but covariance only.

    :param log_std:
    :return: Gaussian entropy for a given covariance
    """
    return tf.reduce_sum(log_std + tf.constant(0.5 * np.log(2 * np.pi * np.e), tf.float32))


def get_shape(variable):
    shape = [k.value for k in variable.get_shape()]
    return shape


def get_number_of_elements(x):
    return np.prod(get_shape(x))


def get_flattened_gradient(loss, variables):
    """
    Flat representation of gradients.

    :param loss: Loss expression
    :param variables: Variables to compute gradients on
    :return: Flattened gradient expressions
    """
    gradients = tf.gradients(loss, variables)

    return tf.concat(0, [tf.reshape(grad, [get_number_of_elements(v)])
                         for (v, grad) in zip(variables, gradients)])


class FlatVarHelper(object):
    def __init__(self, session, variables):
        self.session = session
        shapes = map(get_shape, variables)
        total_size = sum(np.prod(shape) for shape in shapes)
        self.theta = tf.placeholder(tf.float32, [total_size])
        start = 0
        assigns = []

        for (shape, variable) in zip(shapes, variables):
            size = np.prod(shape)
            assigns.append(tf.assign(variable, tf.reshape(self.theta[start:start + size], shape)))
            start += size

        self.set_op = tf.group(*assigns)
        self.get_op = tf.concat(0, [tf.reshape(variable, [get_number_of_elements(variable)]) for variable in variables])

    def set(self, theta):
        """
        Assign flat variable representation.

        :param theta: values
        """
        self.session.run(self.set_op, feed_dict={self.theta: theta})

    def get(self):
        """
        Get flat representation.

        :return: Concatenation of variables
        """

        return self.session.run(self.get_op)


def line_search(f, initial_x, full_step, expected_improve_rate, max_backtracks=10, accept_ratio=0.1):
    """
    Line search for TRPO where a full step is taken first and then backtracked to
    find optimal step size.

    :param f:
    :param initial_x:
    :param full_step:
    :param expected_improve_rate:
    :param max_backtracks:
    :param accept_ratio:
    :return:
    """

    function_value = f(initial_x)

    for _, step_fraction in enumerate(0.5 ** np.arange(max_backtracks)):
        updated_x = initial_x + step_fraction * full_step
        new_function_value = f(updated_x)

        actual_improve = function_value - new_function_value
        expected_improve = expected_improve_rate * step_fraction

        improve_ratio = actual_improve / expected_improve

        if improve_ratio > accept_ratio and actual_improve > 0:
            return updated_x

    return initial_x
