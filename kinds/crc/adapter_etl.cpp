/* ETL etl::crc* (include/etl/crc32.h, crc16_ccitt.h, crc8_ccitt.h): the
 * tables of 256 and of 16 entries for the three CRCs. ETL names
 * CRC-16/IBM-3740 crc16_ccitt and CRC-8/SMBUS crc8_ccitt; their parameters
 * are in include/etl/private/crc_parameters.h. The one-shot call is what a
 * user writes: a CRC object, add(begin, end), value(). */
#include "adapters.h"
#include "etl/crc32.h"
#include "etl/crc16_ccitt.h"
#include "etl/crc8_ccitt.h"

namespace {
template <typename T> struct etl_adapter {
    static T s;
    static uint32_t crc(uintptr_t a, uintptr_t b)
    {
        const uint8_t *p = reinterpret_cast<const uint8_t *>(a);
        T c;
        c.add(p, p + b);
        return c.value();
    }
    static uint32_t begin(uintptr_t, uintptr_t) { s.reset(); return 0; }
    static uint32_t update(uintptr_t a, uintptr_t b)
    {
        const uint8_t *p = reinterpret_cast<const uint8_t *>(a);
        s.add(p, p + b);
        return 0;
    }
    static uint32_t final(uintptr_t, uintptr_t) { return s.value(); }
};
template <typename T> T etl_adapter<T>::s;
}

#define ETL_ADAPTER(N, T, NAME, ID, CLS)                                              \
    extern "C" const crc_adapter adapter_##N = { NAME, "etl", ID, CLS, 0, 0, NULL, NULL, \
        etl_adapter<T>::crc, CRC_STREAM(etl_adapter<T>::begin, etl_adapter<T>::update, etl_adapter<T>::final) };

ETL_ADAPTER(etl_crc32_t256, etl::crc32_t256, "etl crc32_t256", CRC32_ISO_HDLC, CLS_TABLE256)
ETL_ADAPTER(etl_crc32_t16, etl::crc32_t16, "etl crc32_t16", CRC32_ISO_HDLC, CLS_TABLE16)
ETL_ADAPTER(etl_crc16_t256, etl::crc16_ccitt_t256, "etl crc16_ccitt_t256", CRC16_IBM_3740, CLS_TABLE256)
ETL_ADAPTER(etl_crc16_t16, etl::crc16_ccitt_t16, "etl crc16_ccitt_t16", CRC16_IBM_3740, CLS_TABLE16)
ETL_ADAPTER(etl_crc8_t256, etl::crc8_ccitt_t256, "etl crc8_ccitt_t256", CRC8_SMBUS, CLS_TABLE256)
ETL_ADAPTER(etl_crc8_t16, etl::crc8_ccitt_t16, "etl crc8_ccitt_t16", CRC8_SMBUS, CLS_TABLE16)
