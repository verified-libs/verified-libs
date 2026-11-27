/* lwIP options for the pools kind: lwIP's memp alone, without its stack.
 * NO_SYS 1 (no OS); every protocol off, so that memp_std.h declares no pool
 * of the stack; one pool of ours declared with LWIP_MEMPOOL_DECLARE (the
 * documented way to make a private pool, include/lwip/memp.h); no statistics
 * and no extra checks (lwIP's defaults for both are off). SYS_LIGHTWEIGHT_PROT
 * stays at lwIP's default (1), so memp guards its free list with
 * SYS_ARCH_PROTECT, the port's sys_arch_protect (shims/lwip/sys_arch.c). */
#pragma once
#define NO_SYS                 1
#define SYS_LIGHTWEIGHT_PROT   1
#define LWIP_RAW               0
#define LWIP_UDP               0
#define LWIP_TCP               0
#define LWIP_ICMP              0
#define LWIP_IGMP              0
#define LWIP_DNS               0
#define LWIP_DHCP              0
#define LWIP_AUTOIP            0
#define LWIP_ARP               0
#define LWIP_ETHERNET          0
#define LWIP_IPV4              1
#define LWIP_IPV6              0
#define LWIP_NETCONN           0
#define LWIP_SOCKET            0
#define LWIP_TIMERS            0
#define IP_REASSEMBLY          0
#define IP_FRAG                0
#define PBUF_POOL_SIZE         0
#define MEMP_NUM_PBUF          0
#define LWIP_STATS             0
#define MEMP_OVERFLOW_CHECK    0
#define MEMP_SANITY_CHECK      0
#define MEM_ALIGNMENT          4
