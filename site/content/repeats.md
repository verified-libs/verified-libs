# Repeated by others

Every number on these pages was measured in one lab, on one board of each
model. This page lists every time someone outside the project ran our tests
on their own board and sent us the result, whether it agreed with ours or
not.

## Take part

You need one of the six board models of the
[comparison](../../site/content/compare.html), a Linux machine and the USB
cable of the board's own debug probe. Then, in a clone of the
[repository](../../README.md):

```sh
./repeat.sh --check     # tools, toolchain image and board
./repeat.sh             # 15-25 minutes; --level full: 1-2 hours
```

`repeat.sh` builds the firmware we ran, byte for byte, runs it on your
board, compares your results with ours and packs everything into one
archive. Mail the archive to contact@verified-libs.org. The details are on
[Reproduce](../../site/content/reproduce.md).

Each test writes the board's flash once. Nothing else on the board is
changed.

## What happens with your result

- We check that the firmware is the one we ran (`fw_sha256`) and compare
  your numbers and stress verdicts with ours, the same way `repeat.sh` did.
- With your consent, it is listed below, under the name or handle you choose,
  or anonymously, and the archive goes into the repository.
- A result that disagrees with ours is looked into before anything else. It
  is listed as it is, together with what we found. If the error is ours, the
  page is corrected and says so.

There is no payment. What we can offer is the credit here, and a test setup
you can reuse for your own buffer code.

## Results received

| Date | By | Board (revision) | Probe firmware | Level | Our commit | Agrees with ours |
|---|---|---|---|---|---|---|
| | | | | | | none received yet |
