# Nordic nRF5 SDK nrf_ringbuf (SET=nordic, BOARD=nrf5340 only): the SDK's
# files from nrf5-sdk.sh (build/libs/nrf5-sdk), with the shims in shims/nrf5
# in place of the device and SoftDevice headers. Shared with the stress test.
NRF5 = $(BENCH)/build/libs/nrf5-sdk
NRF5_I = -I$(BENCH)/shims/nrf5 -I$(NRF5)/components/libraries/ringbuf -I$(NRF5)/components/libraries/atomic \
         -I$(NRF5)/components/libraries/util -I$(NRF5)/components/drivers_nrf/nrf_soc_nosd -I$(NRF5)/modules/nrfx/mdk
NORDIC_OBJS = build/nordic_adapter.o build/nrf_ringbuf.o build/nrf_atomic.o
build/nordic_adapter.o: $(BENCH)/adapters_nordic/adapter_nrf_ringbuf.c | build
	$(CC_LIB) $(CFLAGS) $(NRF5_I) -c $< -o $@
build/nrf_ringbuf.o: $(NRF5)/components/libraries/ringbuf/nrf_ringbuf.c | build
	$(CC_LIB) $(CFLAGS) $(NRF5_I) -c $< -o $@
build/nrf_atomic.o: $(NRF5)/components/libraries/atomic/nrf_atomic.c | build
	$(CC_LIB) $(CFLAGS) $(NRF5_I) -c $< -o $@
