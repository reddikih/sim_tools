#!/usr/bin/env python

import os
import sys
import re

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
path_filter = re.compile(r'DD(?P<num_dd>\d+)CD(?P<num_cd>\d+)NM(?P<num_mem>\d+)MS(?P<mem_size>\d+)R(?P<rep_level>\d+)SM(?P<storage_manager>[a-zA-Z])CMA(?P<mem_assignor>[a-zA-Z]+)CMF(?P<memory_manager>[a-zA-Z]+)BS\d+BM(?P<buffer_manager>[a-zA-Z]+)_Wworkload\.(?P<wl_hour>\d+)h\.rr(?P<wl_read_ratio>\d)\.lam(?P<wl_lambda>\d+)\.the(?P<wl_zipf_factor>\d+)\.ds(?P<wl_data_size>\d+)[KMGT]B')

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
    'Normal': 'Normal',
    'RAPoSDABufferManagerFactory': 'RAPoSDA',
    'FlushToAllSpinningDiskBufferManagerFactory': 'WithAllSpins',
    'SpinupEnergyEfficientDisksBufferManagerFactory': 'SpinupEE',
}

_to_plot_list = []
_input_dir = '.'
_conditions = {}
_sim_results = {}


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
                self.replicalevel = line.split()[5];
            elif line.startswith("memory size"):
                self.memsize = line.split()[4][0:-4].replace(',','')
            elif line.startswith("block size  "):
                self.blocksize = line.split()[3][0:-4].replace(',','')
            elif line.startswith("cacheMemoryAssignor"):
                self.memoryassignor = line.split()[2]
            elif line.startswith("cacheMemoryFactory"):
                line = line.split()[2].split('.')
                line = line[len(line)-1]
                self.memoryfactory = line[0:line.find('region')]
            elif line.startswith("storageManagerFactory"):
                line = line.split()[2].split('.')
                line = line[len(line)-1]
                self.memoryfactory = line[0:line.find('storage')]
            elif line.startswith("bufferManagerFactory"):
                line = line.split()[2].split('.')
                line = line[len(line)-1]
                self.memoryfactory = line[0:line.find('buffer')]
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
                self.setmemoryaccesscount('read', line.split(':')[1])
            elif line.startswith("cache memory write count"):
                self.setmemoryaccesscount('write', line.split(':')[1])
            elif line.startswith("avg. data disk response time"):
                self.averagedatadiskresponsetime = line.split(':')[1].strip().replace(',','')
            elif line.startswith("data disk access count"):
                self.datadiskaccesscount = line.split(':')[1].strip().replace(',','')
                self.datadiskreadcount = f.readline().split(':')[1].strip().replace(',','')
                self.datadiskwritecount = f.readline().split(':')[1].strip().replace(',','')
            elif line.startswith("avg. cache disk response time"):
                self.averagecachediskresponsetime = line.split(':')[1].strip().replace(',','')
            elif line.startswith("cache disk access count"):
                self.setcachediskaccesscount(f)
            elif line.startswith("spindown count"):
                self.spindowncount = line.split(':')[1].strip().replace(',','')
            elif line.startswith("spinup   count"):
                self.spinupcount = line.split(':')[1].strip().replace(',','')
            elif line.startswith("buffer overflow count"):
                self.bufferoverflowcount = line.split(':')[1].strip().replace(',','')
            line = f.readline()

    def setrequestcount(self, f):
        ll = f.readline().lower().strip().split(':')[1]
        self.readrequestcount = ll[:ll.find(',')]
        ll = f.readline().lower().strip().split(':')[1]
        self.writerequestcount = ll[:ll.find(',')]

    def setmemoryaccesscount(self, attrname, l):
        l = l.strip().replace(',','').replace(')','')
        tmpl = l.split('(')
        setattr(self, "memory" + attrname + "count", tmpl[0])
        setattr(self, "memory" + attrname + "hit", tmpl[1])

    def setcachediskaccesscount(self, f):
        l = f.readline().split(':')[1].strip().replace(',','').replace(')','')
        tmpl = l.split('(')
        self.cachediskreadcount = tmpl[0]
        self.cachediskhit = tmpl[1]
        l = f.readline().split(':')[1].strip().replace(',','').replace(')','')
        self.cachediskwritecoutn = l.split('(')[0]
                

class WorkloadParam:

    def __init__(self, args):
        self.hour = args[1][:-1]
        self.readratio = args[2][2:]
        self.arrivalrate = args[3][3:]
        self.zipffactor = args[4][3]
        self.datasize = args[5][2:]

class Energy:

    def __init__(self, f):
        self.getenergyvalue("active", f.readline().lower().strip())
        self.getenergyvalue("idle", f.readline().lower().strip())
        self.getenergyvalue("standby", f.readline().lower().strip())
        self.getenergyvalue("spindown", f.readline().lower().strip())
        self.getenergyvalue("spinup", f.readline().lower().strip())
        self.totalenergy = (
            float(self.activeenergy) + float(self.idleenergy) + float(self.standbyenergy)
            + float(self.spindownenergy) + float(self.spinupenergy))

    def getenergyvalue(self, attrname, line):
        tmpl = line.split(':')[1].strip().split('(')
        setattr(self, attrname + "energy", tmpl[0].replace(',',''))
        setattr(self, attrname + "totaltime", tmpl[1].replace(',',''))
        tmpl = line.split(':')[2].strip()[:-1]
        setattr(self, attrname + "averagetime", tmpl.replace(',',''))


def generate_file_paths(root):
    '''
    This generator traverses from the root to the most deep offspring
    directories. it traverses the directories with depth-first search.
    '''
    for path in os.listdir(root):
        path = os.path.join(root, path)
        if os.path.isdir(path):
            for subpath in generatefilepaths(path):
                yield subpath
        elif os.path.isfile(path):
            yield path

def print_usage(command_name):
    print '''
Usage:

python %s -G[energy] [,response] [,overflow] [,spinupdown] [,cachehit] [,statetime] \
-D<dir> \
-CONDNM=n,R=n,SM=[r, n],CMA=[dga, cs],CMF=[share, simple],BM=[raposda, withallspins, spinupee],\
WL=h:n_rr:n
''' % command_name
        
        
def plot_energy():
    # x axis: buffer manager
    # y axis: disk status

    
    pass

def plot_avg_response_time():
    pass

def plot_overflow():
    pass

def plot_spindownup():
    pass

def plot_cache_hit():
    pass

def plot_state_times():
    pass

def test_condition(path):
    regex_ret = None
    regex_ret = path_filter.match(os.path.basename(path))
    condition = True
    if (regex_ret):
        regex_dict = regex_ret.groupdict()
        for k, v in _conditions.iteritems():
            if (not (k in regex_dict) or (not (regex_dict[k] == v))):
                # print "false condition: k=", k, "v=", v
                condition = False
                break
    return condition


def parse_command_line(args):
    global _to_plot_list
    global  _input_dir

    _to_plot_list = []

    for item in args:
        if item.startswith('-G'):
            for plot in item[2:].split(','):
                if plot in _PLOT_TYPE:
                    _to_plot_list.append(plot)
        elif item.startswith('-D'):
            _input_dir = item[2:]
        elif item.startswith('-COND'):
            parse_conditions(item[5:])

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
        if (test_condition(path)):
            obj = SimResult(path)
            _sim_results[os.path.basename(obj.path)] = obj

    # plot graphs

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print_usage(sys.argv[0])
        exit()
    elif sys.argv[1] == '-h' or sys.argv[1] == '-help':
        print_usage(sys.argv[0])
        exit()

    parse_command_line(sys.argv[1:])
    main()
