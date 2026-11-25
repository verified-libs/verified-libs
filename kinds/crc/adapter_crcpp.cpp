/* CRC++ (inc/CRC.h): CRC::CRC_16_CCITTFALSE() with a CRC::Table, which the
 * library computes at run time into RAM when the table is constructed (its
 * README: "CRC++ also supports lookup tables"). init() constructs the table
 * once in static storage (placement new, so no global constructor is needed
 * on a board). Streaming: Calculate() with the previous CRC value as the last
 * argument, as the README's examples do for data in two parts. */
#include <new>
#include "adapters.h"
#include "CRC.h"

using T16 = CRC::Table<crcpp_uint16, 16>;
alignas(T16) static unsigned char cpp16_store[sizeof(T16)];
static const T16 *cpp16_table;
static void cpp16_init(void) { cpp16_table = new (cpp16_store) T16(CRC::CRC_16_CCITTFALSE()); }
static uint32_t cpp16_crc(uintptr_t a, uintptr_t b) { return CRC::Calculate((const void *)a, (crcpp_size)b, *cpp16_table); }
static crcpp_uint16 cpp16_state;
static int cpp16_started;
static uint32_t cpp16_begin(uintptr_t, uintptr_t) { cpp16_started = 0; return 0; }
static uint32_t cpp16_update(uintptr_t a, uintptr_t b)
{
    cpp16_state = cpp16_started ? CRC::Calculate((const void *)a, (crcpp_size)b, *cpp16_table, cpp16_state)
                                : CRC::Calculate((const void *)a, (crcpp_size)b, *cpp16_table);
    cpp16_started = 1;
    return 0;
}
static uint32_t cpp16_final(uintptr_t, uintptr_t)
{
    return cpp16_started ? cpp16_state : CRC::Calculate("", 0, *cpp16_table);
}
extern "C" const crc_adapter adapter_crcpp_ccittfalse_table = { "crcpp CRC_16_CCITTFALSE Table", "crcpp", CRC16_IBM_3740, CLS_TABLE256, 0, 1, NULL,
    cpp16_init, cpp16_crc, CRC_STREAM(cpp16_begin, cpp16_update, cpp16_final) };
