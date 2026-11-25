/* The reference (ref_crc.c): register-level calls for the host test and the
 * proofs, and the three reference adapters. */
#pragma once
#include "crc.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The register of the reference's form (ref_crc.c says which form). */
uint32_t ref_start(crc_id id);
uint32_t ref_update(crc_id id, uint32_t reg, const void *data, size_t len);
uint32_t ref_final(crc_id id, uint32_t reg);
uint32_t ref_crc(crc_id id, const void *data, size_t len);

uint32_t ref32_start(void), ref16_start(void), ref8_start(void);
uint32_t ref32_update(uint32_t reg, const void *data, size_t len);
uint32_t ref16_update(uint32_t reg, const void *data, size_t len);
uint32_t ref8_update(uint32_t reg, const void *data, size_t len);
uint32_t ref32_final(uint32_t reg), ref16_final(uint32_t reg), ref8_final(uint32_t reg);

extern const crc_adapter adapter_ref32, adapter_ref16, adapter_ref8;

#ifdef __cplusplus
}
#endif
