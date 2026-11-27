/* Shim: the one macro of Contiki-NG's os/sys/cc.h that os/lib/memb.h uses
 * (in MEMB(), which the adapter does not use). As in cc.h. */
#pragma once
#define CC_CONCAT2(s1, s2) s1##s2
#define CC_CONCAT(s1, s2) CC_CONCAT2(s1, s2)
