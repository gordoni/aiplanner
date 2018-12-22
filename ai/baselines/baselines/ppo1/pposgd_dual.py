# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

# Code based on baselines/ppo1/pposgd_simple.py

from baselines.common import Dataset, explained_variance, fmt_row, zipsame
from baselines import logger
import baselines.common.tf_util as U
import tensorflow as tf, numpy as np
import time
from baselines.common.mpi_adam import MpiAdam
from baselines.common.mpi_moments import mpi_moments
from mpi4py import MPI
from collections import deque

def traj_segment_generator(pi, env, horizon, stochastic):
    t = 0
    ac = env.action_space.sample() # not used, just so we have the datatype
    new = True # marks if we're on first timestep of an episode
    ob = env.reset()

    cur_ep_ret = 0 # return in current episode
    cur_ep_len = 0 # len of current episode
    ep_rets = [] # returns of completed episodes in this segment
    ep_lens = [] # lengths of ...

    # Initialize history arrays
    obs = np.array([ob for _ in range(horizon)])
    rews = np.zeros(horizon, 'float32')
    vpreds = np.zeros(horizon, 'float32')
    news = np.zeros(horizon, 'int32')
    acs = np.array([ac for _ in range(horizon)])
    prevacs = acs.copy()

    while True:
        prevac = ac
        ac, vpred = pi.act(stochastic, ob)
        # Slight weirdness here because we need value function at time T
        # before returning segment [0, T-1] so we get the correct
        # terminal value
        if t > 0 and t % horizon == 0:
            yield {"ob" : obs, "rew" : rews, "vpred" : vpreds, "new" : news,
                    "ac" : acs, "prevac" : prevacs, "nextvpred": vpred * (1 - new),
                    "ep_rets" : ep_rets, "ep_lens" : ep_lens}
            # Be careful!!! if you change the downstream algorithm to aggregate
            # several of these batches, then be sure to do a deepcopy
            ep_rets = []
            ep_lens = []
        i = t % horizon
        obs[i] = ob
        vpreds[i] = vpred
        news[i] = new
        acs[i] = ac
        prevacs[i] = prevac

        ob, rew, new, _ = env.step(ac)
        rews[i] = rew

        cur_ep_ret += rew
        cur_ep_len += 1
        if new:
            ep_rets.append(cur_ep_ret)
            ep_lens.append(cur_ep_len)
            cur_ep_ret = 0
            cur_ep_len = 0
            ob = env.reset()
        t += 1

def add_vtarg_and_adv(seg, gamma, lam):
    """
    Compute target value using TD(lambda) estimator, and advantage with GAE(lambda)
    """
    new = np.append(seg["new"], 0) # last element is only used for last vtarg, but we already zeroed it if last new = 1
    vpred = np.append(seg["vpred"], seg["nextvpred"])
    T = len(seg["rew"])
    seg["adv"] = gaelam = np.empty(T, 'float32')
    rew = seg["rew"]
    lastgaelam = 0
    for t in reversed(range(T)):
        nonterminal = 1-new[t+1]
        delta = rew[t] + gamma * vpred[t+1] * nonterminal - vpred[t]
        gaelam[t] = lastgaelam = delta + gamma * lam * nonterminal * lastgaelam
    seg["tdlamret"] = seg["adv"] + seg["vpred"]

class ActorCritic:

    def __init__(self, unit, policy_fn, ob_space, ac_space, clip_param, entcoeff, optim_epochs, optim_stepsize, optim_batchsize, gamma, lam, adam_epsilon):

        self.unit = unit
        self.optim_epochs = optim_epochs
        self.optim_stepsize = optim_stepsize
        self.optim_batchsize = optim_batchsize
        self.gamma = gamma
        self.lam = lam

        with tf.variable_scope(unit):

            self.pi = policy_fn("pi", ob_space, ac_space) # Construct network for new policy
            tf.identity(self.pi.ac, name='action')
            oldpi = policy_fn("oldpi", ob_space, ac_space) # Network for old policy
            atarg = tf.placeholder(dtype=tf.float32, shape=[None]) # Target advantage function (if applicable)
            ret = tf.placeholder(dtype=tf.float32, shape=[None]) # Empirical return

            lrmult = tf.placeholder(name='lrmult', dtype=tf.float32, shape=[]) # learning rate multiplier, updated with schedule
            clip_param = clip_param * lrmult # Annealed cliping parameter epislon

            ob = U.get_placeholder_cached(phc_scope=unit, name='ob')
            ac = self.pi.pdtype.sample_placeholder([None])

            kloldnew = oldpi.pd.kl(self.pi.pd)
            ent = self.pi.pd.entropy()
            meankl = tf.reduce_mean(kloldnew)
            meanent = tf.reduce_mean(ent)
            pol_entpen = (-entcoeff) * meanent

            ratio = tf.exp(self.pi.pd.logp(ac) - oldpi.pd.logp(ac)) # pnew / pold
            surr1 = ratio * atarg # surrogate from conservative policy iteration
            surr2 = tf.clip_by_value(ratio, 1.0 - clip_param, 1.0 + clip_param) * atarg #
            pol_surr = - tf.reduce_mean(tf.minimum(surr1, surr2)) # PPO's pessimistic surrogate (L^CLIP)
            vf_loss = tf.reduce_mean(tf.square(self.pi.vpred - ret))
            total_loss = pol_surr + pol_entpen + vf_loss
            losses = [pol_surr, pol_entpen, vf_loss, meankl, meanent]
            self.loss_names = ["pol_surr", "pol_entpen", "vf_loss", "kl", "ent"]

            var_list = self.pi.get_trainable_variables()
            self.lossandgrad = U.function([ob, ac, atarg, ret, lrmult], losses + [U.flatgrad(total_loss, var_list)])
            self.adam = MpiAdam(var_list, epsilon=adam_epsilon)

            self.assign_old_eq_new = U.function([],[], updates=[tf.assign(oldv, newv)
                for (oldv, newv) in zipsame(oldpi.get_variables(), self.pi.get_variables())])
            self.compute_losses = U.function([ob, ac, atarg, ret, lrmult], losses)

    def optimize(self, seg, cur_lrmult):

        add_vtarg_and_adv(seg, self.gamma, self.lam)

        # ob, ac, atarg, ret, td1ret = map(np.concatenate, (obs, acs, atargs, rets, td1rets))
        ob, ac, atarg, tdlamret = seg["ob"], seg["ac"], seg["adv"], seg["tdlamret"]
        vpredbefore = seg["vpred"] # predicted value function before udpate
        atarg = (atarg - atarg.mean()) / atarg.std() # standardized advantage function estimate
        d = Dataset(dict(ob=ob, ac=ac, atarg=atarg, vtarg=tdlamret), shuffle=not self.pi.recurrent)
        optim_batchsize = self.optim_batchsize or ob.shape[0]

        if hasattr(self.pi, "ob_rms"): self.pi.ob_rms.update(ob) # update running mean/std for policy

        self.assign_old_eq_new() # set old parameter values to new parameter values
        optim_batchsize = min(self.optim_batchsize, d.n)
        if optim_batchsize == 0:
            return
        logger.log("Optimizing...")
        logger.log(fmt_row(13, self.loss_names))
        # Here we do a bunch of optimization epochs over the data
        for _ in range(self.optim_epochs):
            losses = [] # list of tuples, each of which gives the loss for a minibatch
            for batch in d.iterate_once(optim_batchsize):
                *newlosses, g = self.lossandgrad(batch["ob"], batch["ac"], batch["atarg"], batch["vtarg"], cur_lrmult)
                self.adam.update(g, self.optim_stepsize * cur_lrmult)
                losses.append(newlosses)
            logger.log(fmt_row(13, np.mean(losses, axis=0)))

        logger.log("Evaluating losses...")
        losses = []
        for batch in d.iterate_once(optim_batchsize):
            newlosses = self.compute_losses(batch["ob"], batch["ac"], batch["atarg"], batch["vtarg"], cur_lrmult)
            losses.append(newlosses)
        meanlosses,_,_ = mpi_moments(losses, axis=0)
        logger.log(fmt_row(13, meanlosses))
        for (lossval, name) in zipsame(meanlosses, self.loss_names):
            logger.record_tabular(self.unit+"_loss_"+name, lossval)
        logger.record_tabular(self.unit+"_ev_tdlam_before", explained_variance(vpredbefore, tdlamret))

def is_couple(ob):
    return ob[:,0] == 1

class DualPolicyFn:

    def __init__(self, single_ac, couple_ac):
        self.single_ac = single_ac
        self.couple_ac = couple_ac

    def act(self, stochastic, ob):
        return self.couple_ac.act(stochastic, ob) if is_couple(np.array([ob])) else self.single_ac.act(stochastic, ob)

def learn(env, policy_fn, couple_net, *,
        timesteps_per_actorbatch, # timesteps per actor per update
        clip_param, entcoeff, # clipping parameter epsilon, entropy coeff
        optim_epochs, optim_stepsize, optim_final_stepsize, optim_single_batchsize, optim_couple_batchsize, # optimization hypers
        gamma, lam, # advantage estimation
        max_timesteps=0, max_episodes=0, max_iters=0, max_seconds=0,  # time constraint
        callback=None, # you can do anything in the callback, since it takes locals(), globals()
        adam_epsilon=1e-5,
        schedule='constant' # annealing for stepsize parameters (epsilon and adam)
        ):
    # Setup losses and stuff
    # ----------------------------------------
    ob_space = env.observation_space
    ac_space = env.action_space
    single_ac = ActorCritic('single', policy_fn, ob_space, ac_space, clip_param, entcoeff,
        optim_epochs, optim_stepsize, optim_single_batchsize, gamma, lam, adam_epsilon)
    if couple_net:
        couple_ac = ActorCritic('couple', policy_fn, ob_space, ac_space, clip_param, entcoeff,
            optim_epochs, optim_stepsize, optim_couple_batchsize, gamma, lam, adam_epsilon)
        pi = DualPolicyFn(single_ac.pi, couple_ac.pi)
    else:
        pi = single_ac.pi

    U.initialize()
    single_ac.adam.sync()
    if couple_net:
        couple_ac.adam.sync()

    # Prepare for rollouts
    # ----------------------------------------
    seg_gen = traj_segment_generator(pi, env, timesteps_per_actorbatch, stochastic=True)

    episodes_so_far = 0
    timesteps_so_far = 0
    timesteps_single_so_far = 0
    timesteps_couple_so_far = 0
    iters_so_far = 0
    tstart = time.time()
    lenbuffer = deque(maxlen=100) # rolling buffer for episode lengths
    rewbuffer = deque(maxlen=100) # rolling buffer for episode rewards

    assert sum([max_iters>0, max_timesteps>0, max_episodes>0, max_seconds>0])==1, "Only one time constraint permitted"

    while True:
        if callback:
            if callback(locals(), globals()):
                break
        if max_timesteps and timesteps_so_far >= max_timesteps:
            break
        elif max_episodes and episodes_so_far >= max_episodes:
            break
        elif max_iters and iters_so_far >= max_iters:
            break
        elif max_seconds and time.time() - tstart >= max_seconds:
            break

        if schedule == 'constant':
            cur_lrmult = 1.0
        elif schedule == 'linear':
            cur_lrmult =  max(1.0 - float(timesteps_so_far) / max_timesteps, 0)
        elif schedule == 'exponential':
            cur_lrmult = (optim_final_stepsize / optim_stepsize) ** min(float(timesteps_so_far) / max_timesteps, 1)
        else:
            raise NotImplementedError

        logger.log("********** Iteration %i ************"%iters_so_far)

        seg = seg_gen.__next__()
        # Split seg into couple and single parts.
        single_seg = {}
        couple_seg = {}
        is_couple_seg = np.logical_and(is_couple(seg["ob"]), couple_net)
        couple_count = np.count_nonzero(is_couple_seg)
        timesteps_single_so_far += len(is_couple_seg) - couple_count
        timesteps_couple_so_far += couple_count
        for var in ("ob", "rew", "vpred", "new", "ac", "prevac"):
            single_seg[var] = seg[var][np.nonzero(np.logical_not(is_couple_seg))]
            couple_seg[var] = seg[var][np.nonzero(is_couple_seg)]
        # Mark new for single when couple becomes single.
        single_new = []
        new_couple = False
        for couple, new in zip(is_couple_seg, seg["new"]):
            if couple:
                new_couple = True
            else:
                single_new.append(new_couple or new)
                new_couple = False
        single_seg["new"] = np.array(single_new, 'int32')
        # Add up following rewards for couple when couple becomes single.
        couple_rew = 0
        i = -1
        for couple, rew in reversed(tuple(zip(is_couple_seg, seg["rew"]))):
            if couple:
                couple_seg["rew"][i] += couple_rew
                i -= 1
                couple_rew = 0
            else:
                couple_rew += rew
        single_seg["nextvpred"] = 0 if is_couple_seg[-1] else seg["nextvpred"]
        couple_seg["nextvpred"] = seg["nextvpred"]

        single_ac.optimize(single_seg, cur_lrmult)
        if couple_net:
            couple_ac.optimize(couple_seg, cur_lrmult)

        lrlocal = (seg["ep_lens"], seg["ep_rets"]) # local values
        listoflrpairs = MPI.COMM_WORLD.allgather(lrlocal) # list of tuples
        lens, rews = map(flatten_lists, zip(*listoflrpairs))
        lenbuffer.extend(lens)
        rewbuffer.extend(rews)
        logger.record_tabular("EpLenMean", np.mean(lenbuffer))
        logger.record_tabular("EpRewMean", np.mean(rewbuffer))
        logger.record_tabular("EpThisIter", len(lens))
        episodes_so_far += len(lens)
        timesteps_so_far += sum(lens)
        iters_so_far += 1
        logger.record_tabular("EpisodesSoFar", episodes_so_far)
        logger.record_tabular("TimestepsSoFar", timesteps_so_far)
        logger.record_tabular("TimestepsSingle", timesteps_single_so_far)
        logger.record_tabular("TimestepsCouple", timesteps_couple_so_far)
        logger.record_tabular("TimeElapsed", time.time() - tstart)
        if MPI.COMM_WORLD.Get_rank()==0:
            logger.dump_tabular()

def flatten_lists(listoflists):
    return [el for list_ in listoflists for el in list_]
