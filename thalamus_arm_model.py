
import osim
from osim.env import OsimEnv
import nengo
import numpy as np
import time
import nengo_spa as spa


newCue = True
D = 64
s = spa.sym

# define trial structure =====
trial_duration = 5 #in_sec
cue_length     = 0.1
target_length  = 0.1
tar_ON         = 0.8 # delay period is 600 ms

class Timing(object):

    def __init__(self, trial_duration, cue_length, target_length, tar_ON):
        self.trial = 0 # trial counter
        self.cue_ind  = 0
        self.tar_ind = 0
        self.trial_duration = trial_duration
        self.cue_length  = cue_length
        self.target_length = target_length
        self.tar_ON   = tar_ON
        self.cues =  ['Cue_A','Cue_B','CUE_C','CUE_D']
        self.targets = ['VIS*RIGHT + AUD*LEFT','VIS*LEFT + AUD*RIGHT']

    def presentCues(self, t):
        if self.trial <= 100:
            # context 1
            cues = ['Cue_A','Cue_B']
        elif self.trial <= 200:
            # context 2
            cues = ['Cue_C','Cue_D']
        else:
            # randomized
            cues = ['Cue_A','Cue_B','CUE_C','CUE_D']

        if  (int(t) % self.trial_duration==0) and ((t-int(t)) == 0):
            self.trial = self.trial + 1
            self.cue_ind = np.random.randint(0,len(cues))

        if  (int(t)%self.trial_duration==0) and (0<= t-int(t) <= self.cue_length):
            index = self.cue_ind
            return cues[index]
        else:
            return '0'

    def presentTargets(self, t):
        targets = self.targets
        if  (int(t) % self.trial_duration==0) and ((t-int(t)) == 0):
            self.tar_ind = np.random.randint(0,len(targets))
            print("Trial = {0}, Cue = {1}, Target = {2}".format(self.trial, self.cues[self.cue_ind], self.targets[self.tar_ind]))
        if  (int(t)%self.trial_duration==0) and ( self.tar_ON <= t-int(t) <= (self.tar_ON + self.target_length)):
            index = self.tar_ind
            return targets[index]
        else:
            return '0'
# vocabulary
vocab = spa.Vocabulary(D)
vocab.populate('CUE_A; CUE_B; CUE_C; CUE_D; RIGHT; LEFT; VIS; AUD; NOTHING')
moves       = ['RIGHT','LEFT']
movesMap    = {k : k for k in moves}
assoRule    = { 'CUE_A': 'VIS',
                'CUE_C': 'VIS',
                'CUE_B': 'AUD',
                'CUE_D': 'AUD'}

# define vocabulary known in PFC
vocabPFC = spa.Vocabulary(D)
vocabPFC.populate('CUE_A; CUE_B; CUE_C; CUE_D; NOTHING')
vocabPFC.add('AUDITORY', vocabPFC.parse('CUE_A+CUE_C')) # go to visial
vocabPFC.add('VISUAL', vocabPFC.parse('CUE_B+CUE_D')) # go to sound
# define vocabulary known in MOTOR
vocabMOTOR = spa.Vocabulary(D)
vocabMOTOR.populate('RIGHT; LEFT; NOTHING')

# with spa.Network(seed = 900) as model:

#######
class MuscleEnv(OsimEnv):

    model_path = 'arm26.osim'
    shoulder = 0
    elbow = 0

    def reward(self):
       return 0

    def output_fcn(self, t, x):
        if int(t*1000)%40 == 0:
            #time.sleep(.01)
            activ = [0.05] * 6
            activ[0] = x[1] if x[1] > 0.05 else 0.05
            activ[1] = activ[0]
            activ[3:6] = [x[0] if x[0] > 0.05 else 0.05]*3
            #print(">> activ: {0}".format(activ))
            obs = env.step(activ)
            self.shoulder = obs[0]['joint_pos']['r_shoulder'][0]
            self.elbow = obs[0]['joint_pos']['r_elbow'][0]
            #print(">> shoulder: {0:.5f}, elbow: {1:.5f} ".format(self.shoulder, self.elbow))
        return 0

    def state_fcn(self, t):
        return self.elbow
"""
learn_file_path = 'Models/Arm26/OutputReference/ComputedMuscleControl/Results100s/arm26_states.sto'
learn_file = open(learn_file_path, 'r')
activation_vals = []
joint_angles = []
for linenum, line in enumerate(learn_file):
    # skip header
    if linenum < 9:
        continue
    if linenum > 10007:
        break
    data = line.split()
    data = [float(d) for d in data]
    joint_angles.append([data[1], data[3]])
    activation_vals.append(data[5::2])
activation_vals = np.array(activation_vals)
joint_angles = np.array(joint_angles)
"""

env = MuscleEnv()
env.osim_model.stepsize = 0.02
env.osim_model.model.getVisualizer().getSimbodyVisualizer().setGroundHeight(-1.0)

state = env.reset()
env.step([0.05, 0.05, 0.05, 0.05, 0.05, 0.05])
        #print(state)

model = nengo.Network(seed=42)

def transform_input(x):
    if np.dot(vocabMOTOR.parse('LEFT').v, x) >= 0.5:
        return [0.2]
    elif np.dot(vocabMOTOR.parse('RIGHT').v,x) >= 0.5:
        return [0.6]
    else:
        return[0.9]

def input_fcn(t):
    return [0.2]


with spa.Network(seed = 900) as model:
    kp_b = 0.2
    kp_t = 0.2
    kd_b = 0.1
    kd_t = 0.1
    ki_b = 0.05
    ki_t = 0.05

    # error
    stim = nengo.Node(None, size_in=1)
    state = nengo.Node(env.state_fcn)
    err = nengo.Ensemble(n_neurons=500, dimensions=1)

    nengo.Connection(stim, err)
    nengo.Connection(state, err, transform=-1)

    # derivative
    derr = nengo.Ensemble(n_neurons=500, dimensions=1)
    nengo.Connection(err, derr, synapse=None, transform=1000)
    nengo.Connection(err, derr, synapse=0, transform=-1000)

    # integral
    ierr = nengo.Ensemble(n_neurons=500, dimensions=1)
    nengo.Connection(ierr, ierr, synapse=0.1)
    nengo.Connection(err, ierr, synapse=0.1, transform=0.1)

    bic = nengo.Ensemble(n_neurons=500, dimensions=1,
                         intercepts=nengo.dists.Uniform(0,1),
                         encoders=nengo.dists.Choice([[1]]))
    tri = nengo.Ensemble(n_neurons=500, dimensions=1,
                         intercepts=nengo.dists.Uniform(0,1),
                         encoders=nengo.dists.Choice([[1]]))
    output = nengo.Node(size_in=2, size_out=2,output=env.output_fcn)

    #nengo.Connection(bic, bic, synapse=0.1)
    nengo.Connection(err, bic, transform=kp_b, synapse=None)
    nengo.Connection(derr, bic, transform=kd_b, synapse=None)
    nengo.Connection(ierr, bic, transform=ki_b, synapse=None)

    #nengo.Connection(tri, tri, synapse=0.1)
    nengo.Connection(err, tri, transform=-kp_t, synapse=None)
    nengo.Connection(derr, tri, transform=-kd_t, synapse=None)
    nengo.Connection(ierr, tri, transform=-ki_t, synapse=None)

    nengo.Connection(bic, output[0], synapse=0.1)
    nengo.Connection(tri, output[1], synapse=0.1)

    # thalamus model
    exp = Timing( trial_duration, cue_length,target_length,tar_ON )

        # define population
    pfcCUE      = spa.State(vocab, feedback=0.9, label='pfcCUE')
    pfcRULEmemo = spa.State(vocab, feedback=0.3, label='pfcRULEmemo',feedback_synapse=0.25)
    mdCUE       = spa.State(vocab, label='mdCUE')
    mdRULE      = spa.State(vocab, label='mdRULE')
    ppc         = spa.State(vocab, feedback = 0.9, label = 'ppc',feedback_synapse=0.25)
    errorPPC    = spa.State(vocab, feedback = 0.05, label = 'errPPC')

        # define inputs
    stim_cue    = spa.Transcode( function = exp.presentCues, output_vocab = vocab, label='stim Cue')
    stim_target = spa.Transcode( function = exp.presentTargets, output_vocab = vocab, label='stim Target')

        # associative memory CUE -> RULE
    pfcRULEasso = spa.ThresholdingAssocMem(0.3, input_vocab=vocab,
                                            mapping=assoRule,
                                            function=lambda x: x > 0,
                                            label='pfcRULEasso')
    stim_cue >> pfcRULEasso
    pfcRULEasso >> pfcRULEmemo

        #####   toDo: TRANSFORM THE pfcRULE into a Winner-take-all network #####

        #cleanup = spa.WTAAssocMem(0.3, vocab, function=lambda x: x > 0)

        #####           ####

        # connections
    stim_cue >> ppc
    stim_cue >> pfcCUE

    motorClean  = spa.WTAAssocMem(threshold=0.1, input_vocab=vocab,
                                            mapping = movesMap,
                                            function=lambda x: x > 0,
                                            label = 'motorClean')

    nengo.Connection(mdRULE.output, pfcRULEmemo.input, transform=5,synapse=0.05)

    with spa.ActionSelection():
        spa.ifmax(0.3*spa.dot(s.NOTHING, pfcCUE),s.NOTHING >> pfcRULEmemo)

        # spa.ifmax(spa.dot(s.CUE_A + s.CUE_C, pfcCUE),
        #                    s.VIS >> pfcRULE)
        # spa.ifmax(spa.dot(s.CUE_B + s.CUE_D, pfcCUE),
        #                    s.AUD >> pfcRULE)
        spa.ifmax(spa.dot(pfcRULEasso, s.AUD), s.AUD >> mdRULE)
        spa.ifmax(spa.dot(pfcRULEasso, s.VIS), s.VIS >> mdRULE)
        spa.ifmax(spa.dot(stim_target, s.AUD*s.RIGHT+s.VIS*s.LEFT),
                              stim_target*~pfcRULEmemo >> motorClean)
        spa.ifmax(spa.dot(stim_target, s.VIS*s.RIGHT+s.AUD*s.LEFT),
                              stim_target*~pfcRULEmemo >> motorClean)

        # learning
    mdCUE_ens       = list(mdCUE.all_ensembles)
    mdRULE_ens      = list(mdRULE.all_ensembles)
    ppc_ens         = list(ppc.all_ensembles)
    errorPPC_ens    = list(errorPPC.all_ensembles)

    -ppc    >> errorPPC
    mdCUE   >> errorPPC
    for i, ppc_e in enumerate(ppc_ens):
        c2 = nengo.Connection(ppc_e, mdCUE_ens[i],
                #function = lambda x: [0]*md_e.dimensions,
                transform = 0,
                learning_rule_type = nengo.PES(learning_rate = 1e-4) )
        nengo.Connection(errorPPC_ens[i], c2.learning_rule)

        # damage md
    damage = nengo.Node(0, label='damage')
    for i, mdE_e in enumerate(mdRULE_ens):
        nengo.Connection(damage, mdE_e.neurons,
                            transform=10*np.ones((mdE_e.n_neurons,1)),
                            synapse=None)

    for i, mdC_e in enumerate(mdCUE_ens):
        nengo.Connection(damage, mdC_e.neurons,
                            transform=10*np.ones((mdC_e.n_neurons,1)),
                            synapse=None)

    motorOutput = spa.State(vocabMOTOR, subdimensions = 64, represent_identity = False,label = 'MotorOutput')
    motorClean >> motorOutput

    nengo.Connection(motorOutput.all_ensembles[0], stim, function = transform_input, synapse = None)
