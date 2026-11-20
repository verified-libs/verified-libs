/* Port functions and task-API stubs for FreeRTOS's stream_buffer.c without
 * the scheduler (see portmacro.h). The task functions are only reached when
 * a task blocks on the stream buffer or has to be woken; with zero timeouts
 * and no tasks that never happens, so they are inert stubs. */
#include "FreeRTOS.h"
#include "task.h"

static uint32_t crit_nesting, crit_saved;
void vPortEnterCritical(void)
{
    uint32_t p;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(p) :: "memory");
    if (crit_nesting++ == 0) crit_saved = p;
}
void vPortExitCritical(void)
{
    if (--crit_nesting == 0) __asm volatile("msr primask, %0" :: "r"(crit_saved) : "memory");
}
uint32_t ulPortSetInterruptMask(void)
{
    uint32_t p;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(p) :: "memory");
    return p;
}
void vPortClearInterruptMask(uint32_t p) { __asm volatile("msr primask, %0" :: "r"(p) : "memory"); }

TaskHandle_t xTaskGetCurrentTaskHandle(void) { return NULL; }
void vTaskSuspendAll(void) {}
BaseType_t xTaskResumeAll(void) { return pdFALSE; }
void vTaskSetTimeOutState(TimeOut_t *const t) { (void)t; }
BaseType_t xTaskCheckForTimeOut(TimeOut_t *const t, TickType_t *const w) { (void)t; (void)w; return pdTRUE; }
BaseType_t xTaskGenericNotify(TaskHandle_t h, UBaseType_t i, uint32_t v, eNotifyAction a, uint32_t *p)
{ (void)h; (void)i; (void)v; (void)a; (void)p; return pdPASS; }
BaseType_t xTaskGenericNotifyFromISR(TaskHandle_t h, UBaseType_t i, uint32_t v, eNotifyAction a, uint32_t *p,
                                     BaseType_t *w)
{ (void)h; (void)i; (void)v; (void)a; (void)p; (void)w; return pdPASS; }
BaseType_t xTaskGenericNotifyWait(UBaseType_t i, uint32_t c, uint32_t e, uint32_t *p, TickType_t t)
{ (void)i; (void)c; (void)e; (void)p; (void)t; return pdFALSE; }
BaseType_t xTaskGenericNotifyStateClear(TaskHandle_t h, UBaseType_t i) { (void)h; (void)i; return pdFALSE; }
