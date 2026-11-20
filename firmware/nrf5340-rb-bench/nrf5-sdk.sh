#!/bin/bash
# Take the files of nrf5-sdk.lock from the nRF5 SDK zip into
# build/libs/nrf5-sdk/, after checking the zip's SHA-256.
# Usage: bash nrf5-sdk.sh PATH/TO/nRF5_SDK_17.1.1_8173c8a.zip
# (or NRF5_SDK=PATH in the environment). Download it yourself from
# nordicsemi.com: its licence does not let us redistribute it.
set -euo pipefail
cd "$(dirname "$0")"
zip=${1:-${NRF5_SDK:-}}
[ -n "$zip" ] && [ -f "$zip" ] || { echo "usage: nrf5-sdk.sh ZIP (the nRF5 SDK, nrf5-sdk.lock)" >&2; exit 2; }
want=$(awk '$1 == "sha256" {print $2}' nrf5-sdk.lock)
got=$(sha256sum "$zip" | cut -d' ' -f1)
[ "$got" = "$want" ] || { echo "$zip: SHA-256 $got, nrf5-sdk.lock pins $want" >&2; exit 1; }
out=build/libs/nrf5-sdk
rm -rf "${out:?}"; mkdir -p "$out"
# shellcheck disable=SC2046
unzip -q -o "$zip" $(awk '$1 == "file" {print $2}' nrf5-sdk.lock) -d "$out"
echo "$got" > "$out/SHA256"
echo "nrf5-sdk $(awk '$1 == "version" {print $2}' nrf5-sdk.lock) ($(find "$out" -type f -name '*.[ch]' | wc -l) files)"
