# ARQ protocol explanations

## Stop-and-Wait
The sender transmits one packet and waits for its ACK. If the data or ACK is lost, the sender waits for a timeout and retries. The receiver suppresses duplicate delivery. It is simple but has low utilization when delay is high.

## Go-Back-N
The sender may transmit up to the configured window size. The receiver accepts in-order data and discards out-of-order packets. A timeout causes the sender to restart from the oldest unacknowledged packet, retransmitting the remaining window. ACKs are cumulative.

## Selective Repeat
The sender may have several outstanding packets. Each packet is acknowledged individually, and out-of-order data can be buffered. Only packets without a successful ACK are retried.

## Simulation assumptions
This prototype uses non-wrapping sequence numbers and simplified window rounds. It is intended to make protocol behavior visible, not to reproduce all timing details of a production transport implementation.


## Result interpretation

The simulator reports three distinct outcomes:

- **Receiver complete:** all original packet IDs have arrived at the receiver.
- **Sender completed:** the sender received the acknowledgements needed by the implemented protocol before retry limits were reached.
- **Integrity:** the complete reconstructed payload matches the original payload using SHA-256.

These outcomes are intentionally separate. For example, if the receiver gets the complete payload but the final ACK is repeatedly lost, receiver completion and integrity may be `YES`/`PASS` while sender completion is `NO`. Overall completion is successful only when sender completion, receiver completion, and integrity all pass.

Go-Back-N now sends the entire current window before handling cumulative ACK progress; out-of-order packets are discarded and duplicate cumulative ACKs can be generated. Selective Repeat tracks acknowledgements and retries per packet within a window and suppresses duplicate receiver delivery. Both remain simplified event simulations: packet/ACK events are processed sequentially and simulated time is not a cycle-accurate model of a real network.
