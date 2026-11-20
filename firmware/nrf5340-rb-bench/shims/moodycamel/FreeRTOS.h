/* Declarations only, so that moodycamel's atomicops.h can be built bare-metal
 * through its FreeRTOS branch (-DFREERTOS). atomicops.h needs a semaphore
 * wrapper even though only BlockingReaderWriterQueue uses one; the adapter
 * uses the non-blocking ReaderWriterQueue. Nothing here is defined: any use
 * of a semaphore would fail to link. */
#pragma once
#include <stdint.h>
typedef void *SemaphoreHandle_t;
typedef uint32_t TickType_t;
typedef unsigned long UBaseType_t;
typedef long BaseType_t;
#define pdTRUE ((BaseType_t)1)
#define portMAX_DELAY ((TickType_t)0xffffffffu)
#define portTICK_PERIOD_MS ((TickType_t)1)
extern "C" {
SemaphoreHandle_t xSemaphoreCreateCounting(UBaseType_t max, UBaseType_t initial);
void vSemaphoreDelete(SemaphoreHandle_t s);
BaseType_t xSemaphoreTake(SemaphoreHandle_t s, TickType_t ticks);
BaseType_t xSemaphoreTakeFromISR(SemaphoreHandle_t s, BaseType_t *woken);
BaseType_t xSemaphoreGive(SemaphoreHandle_t s);
BaseType_t xSemaphoreGiveFromISR(SemaphoreHandle_t s, BaseType_t *woken);
BaseType_t xPortIsInsideInterrupt(void);
}
