#!/usr/bin/awk
# This script calculate summarize the access performance of individual disks.
# 
# Usage:
#     awk -f <thisscript> CacheDiskPerf.out(DataDiskPerf.out) | sort
#
# The output format is as follows:
#  diskid:0000
#  rdcnt, rdavgresp   ... a number of read accesses and average response time of it.
#  wtcnt, wtavgresp   ... a number of write accesses and average response time of it.
#  bgwcnt, bgwavgresp ... a number of background write accesses and average response time of it.
#  totalcnt, avgresp  ... a number of total accesses and average response time all it.
#
# S.Hikida 2012/10/19 @ yokota lab.

BEGIN {
    FS=","
}
{
    if (NR != 1) {
        if ($6 == "READ") {
            stats[$1, "rdcnt"] += 1
            stats[$1, "rdresp"] += $5
        } else if ($6 == "WRITE") {
            stats[$1, "wtcnt"] += 1
            stats[$1, "wtresp"] += $5
        } else if ($6 == "BG_WRITE") {
            stats[$1, "bgwcnt"] += 1
            stats[$1, "bgwresp"] += $5
        }
        stats[$1, "totalresp"] += $5
        stats[$1, "totalcnt"] += 1

        if (! ($1 in diskIds)) {
            diskIds[$1] = $1
        }
    }
}
END {
    for (id in diskIds) {
        printf "diskid:%04d\trdcnt:%d\trdavgresp:%.8f\twtcnt:%d\twtavgresp:%.8f\tbgwcnt:%d\tbgwavgresp:%.8f\tcnt:%d\tavgresp:%.8f\n", id,
            stats[id, "rdcnt"], stats[id, "rdcnt"] ? stats[id, "rdresp"] / stats[id, "rdcnt"] : 0,
            stats[id, "wtcnt"], stats[id, "wtcnt"] ? stats[id, "wtresp"] / stats[id, "wtcnt"] : 0,
            stats[id, "bgwcnt"], stats[id, "bgwcnt"] ? stats[id, "bgwresp"] / stats[id, "bgwcnt"] : 0,
            stats[id, "totalcnt"], stats[id, "totalcnt"] ? stats[id, "totalresp"] / stats[id, "totalcnt"] : 0
    }
}
