# Stress campaign overnight-20261106T215245Z

Runs started: 32; valid: 24; did not finish: 3; invalid (control not caught): 5.

**No errors in any real library across all valid runs.**

## Per library (valid runs)

| Library | Runs | Bytes | Interrupts | Errors | Full reached isr→main / main→isr | Empty reached isr→main / main→isr |
|---|---|---|---|---|---|---|
| pxq RingBuffer_PackedState (C++) | 24 | 10,200,048 | 57,047,191 | 0 | 24 / 22 | 24 / 24 |
| lwrb (C) | 24 | 10,200,081 | 93,032,667 | 0 | 24 / 17 | 24 / 24 |
| AndersKaloer Ring-Buffer (C) | 24 | 10,200,075 | 52,064,785 | 0 | 24 / 22 | 24 / 24 |
| jnk0le Ringbuffer (C++) | 24 | 10,200,060 | 48,985,039 | 0 | 24 / 22 | 24 / 24 |
| ETL queue_spsc_isr (C++) | 24 | 10,200,062 | 50,188,394 | 0 | 24 / 22 | 24 / 24 |
| ETL queue_spsc_atomic (C++) | 24 | 10,200,066 | 50,573,051 | 0 | 24 / 22 | 24 / 24 |
| QuantumLeaps LFRB (C) | 24 | 10,200,054 | 56,156,692 | 0 | 24 / 19 | 24 / 24 |
| EmbeddedArtistry cbuf threadsafe (C) | 24 | 10,200,067 | 57,993,961 | 0 | 24 / 19 | 24 / 24 |
| ece-mohammad RingBuffer (C) | 24 | 10,200,061 | 60,391,905 | 0 | 24 / 22 | 24 / 24 |
| micoring SPSC mode (C) | 24 | 10,200,105 | 72,703,311 | 0 | 24 / 16 | 24 / 24 |
| kostyk348 lf_spsc (C) | 24 | 10,200,149 | 59,040,657 | 0 | 24 / 19 | 24 / 24 |
| diffstorm cb (C) | 24 | 10,200,073 | 65,177,189 | 0 | 24 / 19 | 24 / 24 |
| RIOT tsrb (C) | 24 | 10,200,061 | 53,927,689 | 0 | 24 / 23 | 24 / 24 |
| Contiki-NG ringbuf (C) | 24 | 10,200,063 | 56,950,753 | 0 | 24 / 19 | 24 / 24 |
| rigtorp SPSCQueue (C++) | 24 | 10,200,070 | 56,013,962 | 0 | 24 / 19 | 24 / 24 |
| wizard97 as shipped (C++) *(not ISR-safe by its own docs)* | 24 | 10,200,072 | 49,407,982 | 219,737 | 24 / 22 | 24 / 24 |
| wizard97 + PRIMASK macros (C++) | 24 | 10,200,080 | 52,730,971 | 0 | 24 / 19 | 24 / 24 |
| polycratia spscring (C++) | 24 | 10,200,056 | 48,940,641 | 0 | 24 / 22 | 24 / 24 |
| rt-spsc (C++) | 24 | 10,200,058 | 50,802,064 | 0 | 24 / 22 | 24 / 24 |

## Runs

| Run | Start (UTC) | Mode | Prescaler | Cache | Code | Bytes/lib/dir | Seeds | Status |
|---|---|---|---|---|---|---|---|---|
| 0 | 2026-11-06T21:52:45Z | single | 0 | on | flash | 300,000 | 0x014cf585u / 0x10636950u | valid |
| 1 | 2026-11-06T22:18:18Z | block | 0 | on | flash | 300,000 | 0x93963416u / 0x953274bau | valid |
| 2 | 2026-11-06T22:23:05Z | single | 2 | on | flash | 200,000 | 0x98d4b6c6u / 0x3b47dcccu | valid |
| 3 | 2026-11-06T22:34:27Z | block | 2 | on | flash | 200,000 | 0xde668053u / 0xcbb6c540u | valid |
| 4 | 2026-11-06T22:36:41Z | single | 4 | on | flash | 100,000 | 0x0f63ce7bu / 0x7fbb39cau | valid |
| 5 | 2026-11-06T22:44:30Z | block | 4 | on | flash | 100,000 | 0xee228679u / 0x45162526u | invalid (control) |
| 6 | 2026-11-06T22:47:45Z | single | 0 | off | flash | 300,000 | 0x8260c7eau / 0xfb58a890u | did not finish (exit 2) |
| 7 | 2026-11-07T00:06:01Z | block | 2 | off | flash | 200,000 | 0x4aa5bf78u / 0xfbf59006u | valid |
| 8 | 2026-11-07T00:10:02Z | single | 2 | on | SRAM | 200,000 | 0xdddf51adu / 0x37be9519u | valid |
| 9 | 2026-11-07T00:23:40Z | block | 0 | on | SRAM | 300,000 | 0x130db22bu / 0x5de86794u | valid |
| 10 | 2026-11-07T00:31:44Z | single | 4 | off | flash | 100,000 | 0x1c507682u / 0x70806adcu | valid |
| 11 | 2026-11-07T00:42:20Z | block | 4 | on | SRAM | 100,000 | 0x3b35cf80u / 0x2f327a3du | invalid (control) |
| 12 | 2026-11-07T00:45:35Z | single | 0 | on | flash | 300,000 | 0x768cafb7u / 0x06c9c773u | valid |
| 13 | 2026-11-07T01:11:08Z | block | 0 | on | flash | 300,000 | 0xd3c02844u / 0xe150cb0eu | valid |
| 14 | 2026-11-07T01:15:55Z | single | 2 | on | flash | 200,000 | 0x4611da2fu / 0x9c4a3813u | valid |
| 15 | 2026-11-07T01:27:16Z | block | 2 | on | flash | 200,000 | 0x341c468bu / 0xbfa853b2u | valid |
| 16 | 2026-11-07T01:29:30Z | single | 4 | on | flash | 100,000 | 0xa715709eu / 0x3691c0afu | valid |
| 17 | 2026-11-07T01:37:19Z | block | 4 | on | flash | 100,000 | 0xca0fe5ffu / 0x438d778fu | invalid (control) |
| 18 | 2026-11-07T01:40:35Z | single | 0 | off | flash | 300,000 | 0x45e92159u / 0xdf85e9b6u | did not finish (exit 2) |
| 19 | 2026-11-07T02:58:50Z | block | 2 | off | flash | 200,000 | 0x1a9c8db8u / 0xf03d1373u | valid |
| 20 | 2026-11-07T03:02:51Z | single | 2 | on | SRAM | 200,000 | 0x9e5b1408u / 0xe3a2d902u | valid |
| 21 | 2026-11-07T03:16:29Z | block | 0 | on | SRAM | 300,000 | 0xee6999fau / 0x28528632u | valid |
| 22 | 2026-11-07T03:24:33Z | single | 4 | off | flash | 100,000 | 0xaf6c4284u / 0xc5fbe33du | valid |
| 23 | 2026-11-07T03:35:09Z | block | 4 | on | SRAM | 100,000 | 0x75872ebeu / 0x15299a03u | invalid (control) |
| 24 | 2026-11-07T03:38:25Z | single | 0 | on | flash | 300,000 | 0x79a48dd2u / 0x3bf56394u | valid |
| 25 | 2026-11-07T04:03:58Z | block | 0 | on | flash | 300,000 | 0x0c54aa1fu / 0x2c75da26u | valid |
| 26 | 2026-11-07T04:08:44Z | single | 2 | on | flash | 200,000 | 0x967ab069u / 0x015be8b5u | valid |
| 27 | 2026-11-07T04:20:06Z | block | 2 | on | flash | 200,000 | 0xa74b664au / 0x75b277f9u | valid |
| 28 | 2026-11-07T04:22:20Z | single | 4 | on | flash | 100,000 | 0x73b83164u / 0xe0856317u | valid |
| 29 | 2026-11-07T04:30:10Z | block | 4 | on | flash | 100,000 | 0x3acb208au / 0x908153b5u | invalid (control) |
| 30 | 2026-11-07T04:33:25Z | single | 0 | off | flash | 300,000 | 0xd1b65f76u / 0x1722b718u | did not finish (exit 2) |
| 31 | 2026-11-07T05:51:41Z | block | 2 | off | flash | 200,000 | 0x7b618b8bu / 0x869e02c9u | valid |
