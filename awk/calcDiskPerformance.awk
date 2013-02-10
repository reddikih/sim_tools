# This script calculate the summary the access performance of individual disks.
# 
# Usage:
#     awk -f <thisscript> CacheDiskPerf.out(DataDiskPerf.out) | sort
#
# The output format is as follows:
#  diskid: 0000\t access count: XXXX\t avg.response: X.XXXXXXXX
#  ...
#
# S.Hikida 2012/09/12 @ yokota lab.

BEGIN {
    FS=","
}
{
    if (NR != 1) {
        stats[$1, "sumofresponse"] += $5
        stats[$1, "count"] += 1
    }
}
END {
    for (record in stats) {
        split(record, sep, SUBSEP)

        if (sep[2] == "count") {
            # data[sep[1]] = "diskid: %4d" sep[1] "\taccess count: " stats[sep[1], sep[2]] \
            #     "\tavg.response: " stats[sep[1], "sumofresponse"] / stats[sep[1], "count"]
            # print data[sep[1]]

            printf "diskid: %04d\taccess count: %d\tavg.response: %.8f\n", sep[1], stats[sep[1], sep[2]],
                stats[sep[1], "sumofresponse"] / stats[sep[1], "count"]
        }
    }
}
