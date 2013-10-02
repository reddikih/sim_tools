#!/usr/bin/env python

import os
import sys
import re

import numpy as np
import matplotlib as mpl
if 'darwin' != sys.platform:
    mpl.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

'''
Parameter names of filter are follows
--------------------------------------
num_dd
num_cd
num_mem
mem_size
rep_level
storage_manager
mem_assignor
memory_manager
buffer_manager
wl_hour
wl_read_ratio
wl_lambda
wl_zipf_factor
wl_data_size
'''
path_filter = re.compile(r'^DD(?P<num_dd>\d+)CD(?P<num_cd>\d+)NM(?P<num_mem>\d+)MS(?P<mem_size>\d+)R(?P<rep_level>\d+)SM(?P<storage_manager>[a-zA-Z])CMA(?P<mem_assignor>[a-zA-Z]+)CMF(?P<memory_manager>[a-zA-Z]+)BS\d+BM(?P<buffer_manager>[a-zA-Z]+)_Wworkload\.(?P<wl_hour>\d+)h\.rr(?P<wl_read_ratio>\d)\.lam(?P<wl_lambda>\d+)\.the(?P<wl_zipf_factor>\d+)\.ds(?P<wl_data_size>\d+)[KMGT]B$')

_PLOT_TYPE = ('energy', 'response', 'overflow', 'spin', 'hit', 'statetime')

_CONDITION_TRANSLATE_TABLE = {
    'NM': 'num_mem',
    'R': 'rep_level',
    'SM': 'storage_manager',
    'CMA': 'mem_assignor',
    'CMF': 'memory_manager',
    'BM': 'buffer_manager',
    'WL': 'wl_',
    'h': 'hour',
    'rr': 'read_ratio',
}

_BUFFER_MANGER_TYPE = {
    'normal': 'Normal',
    'raposda': 'Chunk', 
    'flushtoallspinningdisk': 'WithAllSpins',
    'spinupenergyefficientdisks': 'SpinupEE',
}

_STORAGE_MANAGER_NAME_TABLE = {
    'normal': 'n',
    'maid': 'm',
    'raposda': 'r',
}

_to_plot_list = []
_input_dir = '.'
_output_dir = None
_conditions = {} # conditions of workload characteristics
_sim_results = {}
_file_formats = ['eps', 'png']

class SimResult:

    def __init__(self, path):
        self.path = path
        self.parse_file()

    def parse_file(self):
        """
        Parse a simulation result file and set each result value to
        this properties.
        """

        f = open(self.path, "r")
        line = f.readline()
        while line != '':
            line = line.lower().strip()
            if line.startswith("data disks  "):
                self.numdatadisk = line.split()[3];
            elif line.startswith("cache disks  "):
                self.numcachedisk = line.split()[3];
            elif line.startswith("replicas  "):
                self.replicalevel = line.split()[2];
            elif line.startswith("number of cache memories "):
                self.nummemories = line.split()[5];
            elif line.startswith("memory size"):
                self.memsize = line.split()[4][0:-4].replace(',','')
            elif line.startswith("block size  "):
                self.blocksize = line.split()[3][0:-4].replace(',','')
            elif line.startswith("cachememoryassignor"):
                self.memoryassignor = line.split()[2]
            elif line.startswith("cachememoryfactory"):
                line = line.split()[2].split('.')
                line = line[len(line)-1]
                self.memoryfactory = line[0:line.find('region')]
            elif line.startswith("storagemanagerfactory"):
                line = line.split()[2].split('.')
                line = line[len(line)-1]
                self.storagemanagerfactory = line[0:line.find('storage')]
            elif line.startswith("buffermanagerfactory"):
                line = line.split()[2].split('.')
                line = line[len(line)-1]
                self.buffermanagerfactory = line[0:line.find('buffer')]
            elif line.startswith("workload"):
                line = line.split()[2].split('/')
                line = line[len(line)-1]
                self.workload = WorkloadParam(line.split('.'))
            elif line.startswith("total energy"):
                self.energy = Energy(f)
            elif line.startswith("avg. response time"):
                self.averageresponsetime = line.split(':')[1].strip().replace(',','')
            elif line.startswith("total request count"):
                self.setrequestcount(f)
            elif line.startswith("cache memory read count"):
                self.set_memory_access_count('read', line.split(':')[1])
            elif line.startswith("cache memory write count"):
                self.set_memory_access_count('write', line.split(':')[1])
            elif line.startswith("avg. data disk response time"):
                self.averagedatadiskresponsetime = line.split(':')[1].strip().replace(',','')
            elif line.startswith("data disk access count"):
                self.datadiskaccesscount = line.split(':')[1].strip().replace(',','')
                self.datadiskreadcount = f.readline().split(':')[1].strip().replace(',','')
                self.datadiskwritecount = f.readline().split(':')[1].strip().replace(',','')
            elif line.startswith("avg. cache disk response time"):
                self.averagecachediskresponsetime = line.split(':')[1].strip().replace(',','')
            elif line.startswith("cache disk access count"):
                self.set_cache_disk_access_count(f)
            elif line.startswith("spindown count"):
                self.spindowncount = line.split(':')[1].strip().replace(',','')
            elif line.startswith("spinup   count"):
                self.spinupcount = line.split(':')[1].strip().replace(',','')
            elif line.startswith("buffer overflow count"):
                self.bufferoverflowcount = line.split(':')[1].strip().replace(',','')
            line = f.readline()

    def get_buffer_managerfactory_name(self):
        t = self.buffermanagerfactory.split('.')
        t = _BUFFER_MANGER_TYPE[t[len(t) - 1]]
        return t

    def get_x_tick_label(self):
        sm = _STORAGE_MANAGER_NAME_TABLE[self.storagemanagerfactory]
        bm = _BUFFER_MANGER_TYPE[self.buffermanagerfactory]
        return sm + '_' + bm

    def setrequestcount(self, f):
        ll = f.readline().lower().strip().split(':')[1]
        self.readrequestcount = ll[:ll.find(',')]
        ll = f.readline().lower().strip().split(':')[1]
        self.writerequestcount = ll[:ll.find(',')]

    def set_memory_access_count(self, attrname, l):
        l = l.strip().replace(',','').replace(')','')
        tmpl = l.split('(')
        setattr(self, "memory_" + attrname + "_count", tmpl[0])
        setattr(self, "memory_" + attrname + "_hit", tmpl[1])

    def set_cache_disk_access_count(self, f):
        l = f.readline().split(':')[1].strip().replace(',','').replace(')','')
        tmpl = l.split('(')
        self.cache_disk_read_count = tmpl[0]
        self.cache_disk_hit = tmpl[1]
        l = f.readline().split(':')[1].strip().replace(',','').replace(')','')
        self.cache_disk_write_count = l.split('(')[0]


                

class WorkloadParam:

    def __init__(self, args):
        self.hour = args[1][:-1]
        self.readratio = args[2][2:]
        self.arrivalrate = args[3][3:]
        self.zipffactor = args[4][3]
        self.datasize = args[5][2:]

class Energy:

    def __init__(self, f):
        self._attrnames = ['active', 'idle', 'standby', 'spindown', 'spinup']
        self._ENERGY_PREFIX = '_energy'
        self._TOTALTIME_PREFIX = '_totaltime'
        self._AVERAGETIME_PREFIX = '_averagetime'

        self.get_energy_value(self._attrnames[0], f.readline().lower().strip())
        self.get_energy_value(self._attrnames[1], f.readline().lower().strip())
        self.get_energy_value(self._attrnames[2], f.readline().lower().strip())
        self.get_energy_value(self._attrnames[3], f.readline().lower().strip())
        self.get_energy_value(self._attrnames[4], f.readline().lower().strip())


    def get_energy_value(self, attrname, line):
        tmpl = line.split(':')[1].strip().split('(')
        setattr(self, attrname + self._ENERGY_PREFIX, tmpl[0].replace(',',''))
        setattr(self, attrname + self._TOTALTIME_PREFIX, tmpl[1].replace(',',''))
        tmpl = line.split(':')[2].strip()[:-1]
        setattr(self, attrname + self._AVERAGETIME_PREFIX, tmpl.replace(',',''))

    def get_energy_value_list(self):
        l = []
        l.append(float(getattr(self, self._attrnames[0] + self._ENERGY_PREFIX, 0.0)))
        l.append(float(getattr(self, self._attrnames[1] + self._ENERGY_PREFIX, 0.0)))
        l.append(float(getattr(self, self._attrnames[2] + self._ENERGY_PREFIX, 0.0)))
        l.append(float(getattr(self, self._attrnames[3] + self._ENERGY_PREFIX, 0.0)))
        l.append(float(getattr(self, self._attrnames[4] + self._ENERGY_PREFIX, 0.0)))
        return l

    def get_total_energy_value(self):
        total_energy = float(getattr(self, self._attrnames[0] + self._ENERGY_PREFIX, 0.0))
        total_energy += float(getattr(self, self._attrnames[1] + self._ENERGY_PREFIX, 0.0))
        total_energy += float(getattr(self, self._attrnames[2] + self._ENERGY_PREFIX, 0.0))
        total_energy += float(getattr(self, self._attrnames[3] + self._ENERGY_PREFIX, 0.0))
        total_energy += float(getattr(self, self._attrnames[4] + self._ENERGY_PREFIX, 0.0))

        return total_energy
        

def plot_energy():
    '''
    x axis: buffer manager
    y axis: disk status
    '''

    active_l = []
    idle_l = []
    standby_l = []
    spinup_l = []
    spindown_l = []

    x_ticks = []

    for sr in sort_sim_results(_sim_results.values()):
        x_ticks.append(sr.get_x_tick_label())
        ene_val = sr.energy.get_energy_value_list()
        active_l.append(float(ene_val[0]))
        idle_l.append(float(ene_val[1]))
        standby_l.append(float(ene_val[2]))
        spinup_l.append(float(ene_val[3]))
        spindown_l.append(float(ene_val[4]))

    width = 0.50
    ind = np.arange(len(x_ticks))
    ind = ind + 0.5 - width / 2

    bottoms = np.array([0 for i in range(len(x_ticks))])

    # clear figure
    plt.clf()

    # setting layout
    gs = GridSpec(1,1)
    gs.update(left=0.15, right=0.80)
    ax = plt.subplot(gs[:])

    p_active = plt.bar(ind, active_l, width, color='r', label='active', axes=ax)
    bottoms = bottoms + active_l
    p_idle = plt.bar(ind, idle_l, width, color='g', bottom=bottoms, label='idle', axes=ax)
    bottoms = bottoms + idle_l
    p_standby = plt.bar(ind, standby_l, width, color='b', bottom=bottoms, label='standby', axes=ax)
    bottoms = bottoms + standby_l
    p_spindown = plt.bar(ind, spindown_l, width, color='c', bottom=bottoms, label='spindown', axes=ax)
    bottoms = bottoms + spindown_l
    p_spinup = plt.bar(ind, spinup_l, width, color='m', bottom=bottoms, label='spinup', axes=ax)

    # labels setting
    plt.ylabel('Energy Consumption [joule]', size=14)
    plt.xticks(ind + width / 2, x_ticks)

    # title setting
    plt.title('Replevel=%s, CMA=%s, CMF=%s'
              % (_sim_results.values()[0].replicalevel, 
                 _sim_results.values()[0].memoryassignor,
                 _sim_results.values()[0].memoryfactory),
              size=16
    )

    # legend setting 
    plt.legend(
        (p_spinup[0], p_spindown[0], p_standby[0], p_idle[0], p_active[0]),
        ('spinup', 'spindown', 'standby', 'idle', 'active'),
        bbox_to_anchor=(1, 1),
        borderaxespad=0.0,
        loc='upper left',
    )

        
    # set x ticks to the scientific notation
    plt.gca().ticklabel_format(style="sci", scilimits=(0,0), axis="y")
    
    # plt.show()
    save_figure(plt, 'energy', _output_dir)



def plot_response():
    '''
    x axis: buffer manager
    y axis: average response time
    '''

    x_ticks = []
    resp_time = []
    
    # for sr in _sim_results.iteritems():
    #     x_ticks.append(sr[1].get_x_tick_label())
    #     resp_time.append(float(sr[1].averageresponsetime))
    for sr in sort_sim_results(_sim_results.values()):
        x_ticks.append(sr.get_x_tick_label())
        resp_time.append(float(sr.averageresponsetime))
        

    width = 0.25
    ind = np.arange(len(x_ticks))
    ind = ind + 0.5 - width / 2

    # clear figure
    plt.clf()

    # plt.bar(ind, resp_time, width, color='b', axes=ax)
    plt.bar(ind, resp_time, width, color='b')

    # labels setting
    plt.ylabel('Avg. Response Time [s]', size=14)
    plt.xticks(ind + width / 2, x_ticks)

    # title setting
    plt.title('Replevel=%s, CMA=%s, CMF=%s'
              % (_sim_results.values()[0].replicalevel, 
                 _sim_results.values()[0].memoryassignor,
                 _sim_results.values()[0].memoryfactory),
              size=16
    )
    
    # plt.show()
    save_figure(plt, 'avg_response', _output_dir)


def plot_overflow():
    '''
    x axis: buffer manager
    y axis: buffer overflow count
    '''

    x_ticks = []
    overflow = []

    # for sr in _sim_results.iteritems():
    #     x_ticks.append(sr[1].get_x_tick_label())
    #     overflow.append(int(sr[1].bufferoverflowcount))
    for sr in sort_sim_results(_sim_results.values()):
        x_ticks.append(sr.get_x_tick_label())
        overflow.append(int(sr.bufferoverflowcount))


    width = 0.30
    ind = np.arange(len(x_ticks))
    ind = ind + 0.5 - width / 2

    # clear figure
    plt.clf()

    plt.bar(ind, overflow, width, color='b')

    # labels setting
    plt.ylabel('Overflow Count', size=14)
    plt.xticks(ind + width / 2, x_ticks)

    # title setting
    plt.title('Replevel=%s, CMA=%s, CMF=%s'
              % (_sim_results.values()[0].replicalevel, 
                 _sim_results.values()[0].memoryassignor,
                 _sim_results.values()[0].memoryfactory),
              size=16
    )
    
    # plt.show()
    save_figure(plt, 'overflow', _output_dir)


def plot_spin():
    '''
    x axis: buffer manager
    y axis: cache hit ration (memory and disk)
    '''
    x_ticks = []
    
    spindowns = []
    spinups = []

    # for sr in _sim_results.iteritems():
    #     x_ticks.append(sr[1].get_x_tick_label())
    #     spindowns.append(int(sr[1].spindowncount))
    #     spinups.append(int(sr[1].spinupcount))
    for sr in sort_sim_results(_sim_results.values()):
        x_ticks.append(sr.get_x_tick_label())
        spindowns.append(int(sr.spindowncount))
        spinups.append(int(sr.spinupcount))
    
    width = 0.30
    ind = np.arange(len(x_ticks))
    ind = ind + 0.5 - width

    # clear figure
    plt.clf()

    ax_down = plt.bar(ind, spindowns, width, color='b')
    ax_up = plt.bar(ind+width, spinups, width, color='r')
    
    # labels setting
    plt.ylabel('Spinup/down Count', size=14)
    plt.xticks(ind + 2 * width / 2, x_ticks)

    # title setting
    plt.title('Replevel=%s, CMA=%s, CMF=%s'
              % (_sim_results.values()[0].replicalevel, 
                 _sim_results.values()[0].memoryassignor,
                 _sim_results.values()[0].memoryfactory),
              size=16
    )

    # legend setting 
    plt.legend(
        (ax_down[0], ax_up[0]),
        ('spindown', 'spinup'),
        # bbox_to_anchor=(1, 1),
        loc='upper right',
    )
     
    # plt.show()
    save_figure(plt, 'spindownup', _output_dir)


def plot_hit():
    '''
    x axis: buffer manager
    y axis: cache hit ration (memory and disk)
    '''

    x_ticks = []
    mem_hit = []
    disk_hit = []

    for sr in sort_sim_results(_sim_results.values()):
        x_ticks.append(sr.get_x_tick_label())
        mem_hit.append(float(sr.memory_read_hit))
        disk_hit.append(float(sr.cache_disk_hit))

    width = 0.30
    ind = np.arange(len(x_ticks))
    ind = ind + 0.5 - width

    # clear figure
    plt.clf()

    ax_mem_hit = plt.bar(ind, mem_hit, width, color='b')
    ax_disk_hit = plt.bar(ind+width, disk_hit, width, color='r')

    # labels setting
    plt.ylabel('Cache Hit Ratio', size=14)
    plt.xticks(ind + 2 * width / 2, x_ticks, size=14)
    plt.yticks(np.arange(0, 1.01, 0.25), size=14)

    # title setting
    plt.title('Replevel=%s, CMA=%s, CMF=%s'
              % (_sim_results.values()[0].replicalevel, 
                 _sim_results.values()[0].memoryassignor,
                 _sim_results.values()[0].memoryfactory),
              size=16
    )

    # legend setting 
    plt.legend(
        (ax_mem_hit[0], ax_disk_hit[0]),
        ('mem hit', 'disk hit'),
        # bbox_to_anchor=(1, 1),
        loc='upper right',
    )
     
    # plt.show()
    save_figure(plt, 'cache_hit', _output_dir)


def plot_statetime():
    '''
    x axis: buffer manager
    y axis: cache hit ration (memory and disk)
    '''
    
    x_ticks = []
    active_t = []
    idle_t = []
    standby_t = []
    spindown_t = []
    spinup_t = []

    for sr in sort_sim_results(_sim_results.values()):
        x_ticks.append(sr.get_x_tick_label())
        active_t.append(float(sr.energy.active_totaltime))
        idle_t.append(float(sr.energy.idle_totaltime))
        standby_t.append(float(sr.energy.standby_totaltime))
        spindown_t.append(float(sr.energy.spindown_totaltime))
        spinup_t.append(float(sr.energy.spinup_totaltime))

    width = 1.0 / 6
    ind = np.arange(len(x_ticks))
    ind = ind + 0.5 - (5.0 * width / 2)

    # clear figure
    plt.clf()

    ax_active = plt.bar(ind, active_t, width, color='r')
    ax_idle = plt.bar(ind + width, idle_t, width, color='g')
    ax_standby = plt.bar(ind + 2 * width, standby_t, width, color='b')
    ax_spindown = plt.bar(ind + 3 * width, spindown_t, width, color='c')
    ax_spinup = plt.bar(ind + 4 * width, spinup_t, width, color='m')

    # labels setting
    plt.ylabel('Total Time of Each State  [s]', size=14)
    plt.xticks(ind + 5 * width / 2, x_ticks, size=14)
    plt.yticks(size=14)

    # title setting
    plt.title('Replevel=%s, CMA=%s, CMF=%s'
              % (_sim_results.values()[0].replicalevel, 
                 _sim_results.values()[0].memoryassignor,
                 _sim_results.values()[0].memoryfactory),
              size=16
    )

    # legend setting 
    plt.legend(
        (ax_active[0], ax_idle[0], ax_standby[0], ax_spindown[0], ax_spinup[0]),
        ('active', 'idle', 'standby', 'spindown', 'spinup'),
        bbox_to_anchor=(0.85, 1),
        loc='upper left',
    )

    # set x ticks to the scientific notation
    plt.gca().ticklabel_format(style="sci", scilimits=(0,0), axis="y")
     
    # plt.show()
    save_figure(plt, 'state_time', _output_dir)


def save_figure(plt, name, parent='.'):
    if not os.path.exists(parent):
        os.mkdir(parent)
    parent = get_output_dirname()
    if not os.path.exists(parent):
        os.mkdir(parent)
    path = os.path.join(parent, name)
    for sufix in _file_formats:
        plt.savefig(path + '.' + sufix)


def sort_sim_results(sim_results):
    zipped = sorted(zip([sr.get_x_tick_label() for sr in sim_results],sim_results))
    ks, vs = zip(*zipped)
    return vs

def generate_file_paths(root):
    '''
    This generator traverses from the root to the most deep offspring
    directories. it traverses the directories with depth-first search.
    '''
    for path in os.listdir(root):
        path = os.path.join(root, path)
        if os.path.isdir(path):
            for subpath in generate_file_paths(path):
                yield subpath
        elif os.path.isfile(path):
            yield path

        
def get_output_dirname():
    parent = ''
    for cond in _conditions.values():
        parent = parent + '_' + cond
    return os.path.join(_output_dir, parent)



def print_usage(command_name):
    print '''
Usage:

python %s -G[energy] [,response] [,overflow] [,spin] [,hit] [,statetime] \
-D<dir>  -O<dir> \
-CONDNM=n,R=n,SM=[r|n],CMA=[dga|cs],CMF=[fix|share|simple],BM=[raposda|withallspins|spinupee],\
WL=h:n_rr:n -NP
''' % command_name


def test_condition(path):
    regex_ret = None
    regex_ret = path_filter.match(os.path.basename(path))
    condition = False
    if (regex_ret):
        condition = True
        regex_dict = regex_ret.groupdict()
        for k, v in _conditions.iteritems():
            if (not (k in regex_dict)) or (regex_dict[k] != v):
                # print "false condition: k=", k, "v=", v
                condition = False
                break
    return condition


def parse_command_line(args):
    global _to_plot_list
    global _input_dir
    global _output_dir
    global _file_formats

    _to_plot_list = []

    for item in args:
        if item.startswith('-G'):
            for plot in item[2:].split(','):
                print 'plotargs=', plot
                if plot in _PLOT_TYPE:
                    _to_plot_list.append(plot)
        elif item.startswith('-D'):
            _input_dir = item[2:]
        elif item.startswith('-O'):
            _output_dir = item[2:]
        elif item.startswith('-COND'):
            parse_conditions(item[5:])
        elif item.startswith('-NP'):
            _file_formats.remove('png')

def parse_conditions(conditions):
    global _conditions
    l = []

    for kv in conditions[5:].split(','):
        if kv.startswith('WL'):
            k, v = kv.split('=')
            k = k.lower() + '_'
            for sub in v.split('_'):
                sub_k, sub_v = sub.split(':')
                sub_k = _CONDITION_TRANSLATE_TABLE[sub_k]
                l.append((k + sub_k, sub_v))
        else:
            k, v = kv.split('=')
            k = _CONDITION_TRANSLATE_TABLE[k]
            l.append((k,v))
    _conditions = dict(l)

    
def main():
    global _sim_results

    for path in generate_file_paths(_input_dir):
        # print 'scan', path
        if (test_condition(path)):
            print path, 'is passes filter'
            obj = SimResult(path)
            _sim_results[os.path.basename(obj.path)] = obj

    # plot graphs
    for plot in _to_plot_list:
        if plot in _PLOT_TYPE:
            eval('plot_' + plot)()
        

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print_usage(sys.argv[0])
        exit()
    elif sys.argv[1] == '-h' or sys.argv[1] == '-help':
        print_usage(sys.argv[0])
        exit()

    parse_command_line(sys.argv[1:])
    main()
