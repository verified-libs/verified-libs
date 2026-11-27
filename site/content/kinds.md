# Results

Three kinds of library are tested so far. Each has its own results, method
and records; the numbers of one kind are not compared with another's.
The kinds are in the order they were added.

## Embedded ring buffers

- **What is measured:** cycles per push and pop and per block, code size, an
  interrupt stress test in which a deliberately broken buffer must be
  caught, and model checks where a library promises lock-free concurrency.
- **Libraries:** 29 (counted by repository), in 38 configurations.
- **Boards:** 6.
- **Results:** [results page](../../RESULTS.md)
- **Method:** [method page](method.md)
- **Comparison page:** [Compare](compare.html)
- **Records:** [`records/`](../../records/README.md)
- **How to repeat:** [Reproduce](reproduce.md)

## CRC calculation

- **What is measured:** cycles of one call that computes a CRC, for messages
  of 1 to 1024 bytes, with the cache off and on, and the bytes of flash and
  RAM it takes; by libraries that compute the CRC in software and, on the
  boards that have one, by the board's CRC unit as a row beside them. Every
  call's result is checked against a reference.
- **Libraries:** 8, in 35 configurations, for 3 CRCs.
- **The board's CRC unit:** on 4 boards, driven by our code (not a library), a row beside the libraries.
- **Boards:** 6.
- **Results:** [results page](results-crc.md)
- **Method:** [method page](method-crc.md)
- **Comparison page:** [Compare](compare-crc.html)
- **Records:** [`records/crc`](../../records/README.md)
- **How to repeat:** [Reproduce, "The CRC records"](reproduce.md#the-crc-records)

## Fixed-block memory pools

- **What is measured:** cycles of alloc and free of one block size (32
  blocks of 32 bytes) in six scenarios and of creating the pool, with the
  cache off and on, and the bytes of flash and RAM it takes; every call is
  checked on the board. Measured in one context: what a library documents
  about use from interrupts is shown, not tested.
- **Libraries:** 10, in 10 configurations, and a row of ours (not a library).
- **Boards:** 6.
- **Results:** [results page](results-pools.md)
- **Method:** [method page](method-pools.md)
- **Comparison page:** [Compare](compare-pools.html)
- **Records:** [`records/pools`](../../records/README.md)
- **How to repeat:** [Reproduce, "The pools records"](reproduce.md#the-pools-records)

The counts are written from the data by
[`site/kinds_page.py`](../kinds_page.py); the site is not built if this
page and the data disagree.
