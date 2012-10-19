# This script calculate the ratio of disk rotation per disk accesses for each disk.
# Usage:
#     awk -f <thisscript> DiskRotationRatio.out | sort
#
# The output format is as follows:
#  diskid: 0000\t  hit:    XXXXX\t  miss:  XXXXX\t  hit ratio: 0.XXXX\n
#  ...
# where
#  hit:   a number of disk is rotating when disk is accessed 
#  miss:  a number of disk isn't rotating when disk is accessed
#  ratio: the ratio of hit / accesses
#
# S.Hikida 2012/09/12 @ yokota lab.

BEGIN {
    FS=","
}
{
    if (NR != 1) {
        disks[$3, "num"] += 1
        if ($6 == "true") {
            disks[$3, "hit"] += 1
        } else {
            disks[$3, "miss"] += 1
        }
        disks[$3, "ratio"] = 0

        if (disks[$3, "hit"] < 1) disks[$3, "hit"] = 0
        if (disks[$3, "miss"] < 1) disks[$3, "miss"] = 0

        if (! ($3 in diskIds)) {
            diskIds[$3] = $3
        }
    }
}
END {
    for (id in diskIds) {
        printf "diskid: %04d\thit: %8d\tmiss: %6d\thit ratio: %.4f\n",
            id, disks[id, "hit"], disks[id, "miss"], 
            disks[id, "hit"] / (disks[id, "hit"] + disks[id, "miss"])
    }
}
