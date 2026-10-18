# 0060 — Spribe settles over its own SFS socket, and we tap it

Date: 2026-10-18
Status: accepted (shipped)

## Context

Item 5 of decision 0057 asked for every provider wallet proxy to be fixed. Four
publishers were already done — Pragmatic (HTTP money calls, pinned to our
origin), Play'n GO (a SignalR socket the bridge taps), PG Soft (an interposed
RGS) and Hacksaw (an interposed RGS). **Spribe** was the leftover, recorded as
"settles over a binary AMF socket our tap does not decode".

That description was wrong in its second half. The socket is not AMF, and the
tap that Play'n GO uses decodes nothing like it.

## What the wire actually is

Aviator opens `wss://app-demo.spribegaming.com/BlueBox/websocket` — a
SmartFoxServer socket the page holds. Its messages are the SFS2X **binary**
protocol, not AMF3:

```
frame  = <flag:1> <len:2 BE> <body>
body   = a stream of type-tagged values
  0x12 <count:2>            SFS_OBJECT
       <klen:2><utf8 key> <value> ×count
  0x07 <8 bytes>            DOUBLE, big endian
  0x08 <len:2><utf8>        STRING
  0x04 <4 bytes>            INT        (0x02=byte, 0x03=short, 0x05=long …)
  0x11 <count:2>            SFS_ARRAY
```

Keys are written literally every time — there is no symbol table — so a frame is
readable without re-encoding any of it. That is the whole trick behind the tap.

The messages that matter, all measured on a live round:

| frame | direction | meaning |
|---|---|---|
| `p.user.balance` in the join answer | in | the opening saldo (50000.0) |
| `betHandler {bet, clientSeed, betId}` | out | **our** bet, and its stake |
| `newBalance {newBalance}` | in | our saldo after every change |
| `roundChartInfo {maxMultiplier, roundId}` | in | the round crashed |

A bet debits the publisher saldo once (`newBalance` drops by the stake). A
cash-out credits it once (`newBalance` rises by the payout — the *total*, not
the profit: a 1.51× cash-out of a 460.82 bet pays 695.84, which is 460.82×1.51).
A crash changes nothing more, so the stake simply stays gone.

## The tap

`spribeWatch(ws)` in the bridge, attached by the same `WebSocket` wrapper that
already picks up Play'n GO's game hub, gated on the publisher's host so no other
game is touched:

- the opening saldo seeds `last` from the join answer;
- a `newBalance` **drop** is the stake leaving, so it becomes the pending round's
  stake;
- a later `newBalance` **rise** is our cash-out, reported with the delta as the
  payout;
- a `roundChartInfo` while a round is pending is the crash, reported with a
  payout of 0;
- a second bet while one is pending settles the first as a loss, so a loss can
  never be dragged forward.

Every report goes to `/api/wallet/round`, the same idempotent write the other
taps use, so a replayed frame cannot charge or pay twice. The publisher's own
server is never in the loop — we only read what the page already receives, the
same rule as decision 0027.

## The two traps that cost the time

1. **A large SFS frame is zlib.** The flag byte is `0xa0` (not `0x80`) and the
   body is a zlib stream — and the join answer, which carries the opening saldo,
   is one of them. Without inflating it the tap has no baseline: the first
   `newBalance` it sees is already *after* the bet, so the first stake reads as a
   delta of zero and the bet is silently lost. The bridge inflates with the
   browser's own `DecompressionStream('deflate')` and serialises the frames
   through a promise chain so an inflated frame cannot overtake the ones behind
   it.
2. **The cash-out control is not the bet button.** It is
   `button.btn-warning.cashout`, it appears only in flight, and it starts as
   `Cashout 0 BRL` with the `disabled` class. A click delivered while the plane
   is up is ignored outright, which makes "I clicked and nothing happened" a
   test bug rather than a product bug: only accept a placement once a button
   reads `Cancelar`. Driving the socket by hand with a rebuilt `cashOutHandler`
   frame does not help — it desyncs the session and the round then never lands.

## Evidence (live, this deploy)

A real Chromium over CDP against the local operator and the publisher's live
demo, betting R$1.00:

```
before                                     balance_minor 500000
bet, no cash-out (crash)                   /wallet/round stake 100 payout 0
after                                      balance_minor 499900

before                                     balance_minor 498500
12 bets, 10 cash-outs at 1.01×–1.09×
 ws-1 stake 100 payout   0     (crash)
 ws-2 stake 100 payout 104     (cash-out 1.04×)
 ws-3 stake 200 payout 100
 ws-5 stake 100 payout 105
 ws-7 stake 100 payout 105
 ws-9 stake 100 payout 105
after                                      balance_minor 498019
```

498500 − 481 = 498019, and 481 is exactly Σpayout − Σstake over the nine rounds
posted — the mirror is not approximately right, it is exact.

The **deploy** was then verified the same way, against the bridge the deployed
site actually serves (byte-identical to the local one): a live test account on
`https://cadiback.onrender.com` placed 11 bets with 10 cash-outs (1.01×–1.10×)
and its wallet moved `50000 → 49524`, again exactly Σpayout − Σstake (−476).

## Consequence

Spribe titles load with our saldo HUD and now **settle on our books**: a bet
debits, a cash-out credits, a crash keeps the stake, and the round appears in
the player's history like any other publisher round.

One honest limit: the publisher's demo saldo is its own, so the tap mirrors
rather than interposes. A bet our ledger cannot cover is refused by
`/wallet/round` and silently dropped — there is no way to gate the publisher's
own button without interposing its socket. That is the same footing Play'n GO
already stands on.
